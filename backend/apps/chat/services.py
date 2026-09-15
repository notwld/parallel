import secrets

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.chat import permissions as P
from apps.chat import policies
from apps.chat.models import (
    Channel,
    DmParticipant,
    Invite,
    Message,
    ReadState,
    Role,
    Server,
    ServerBan,
    ServerMember,
)

TYPING_TTL_SECONDS = 10


class ChatError(ValidationError):
    def __init__(self, message, code=None):
        super().__init__(message, code=code)
        self.rejection_code = code


def _broadcast_message(message: Message) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    payload = message_public(message)
    async_to_sync(layer.group_send)(
        f'chat.channel.{message.channel_id}',
        {'type': 'chat.message', 'message': payload},
    )


def server_public(server: Server) -> dict:
    return {
        'id': str(server.id),
        'name': server.name,
        'description': server.description,
        'owner_id': str(server.owner_id),
        'member_count': server.member_count,
        'created_at': server.created_at.isoformat(),
    }


def channel_public(channel: Channel) -> dict:
    return {
        'id': str(channel.id),
        'server_id': str(channel.server_id) if channel.server_id else None,
        'type': channel.channel_type,
        'name': channel.name,
        'topic': channel.topic,
        'position': channel.position,
    }


def message_public(message: Message) -> dict:
    return {
        'id': str(message.id),
        'channel_id': str(message.channel_id),
        'author_id': str(message.author_id) if message.author_id else None,
        'content': '' if message.deleted_at else message.content,
        'reply_to_id': str(message.reply_to_id) if message.reply_to_id else None,
        'edited_at': message.edited_at.isoformat() if message.edited_at else None,
        'deleted': message.deleted_at is not None,
        'created_at': message.created_at.isoformat(),
    }


@transaction.atomic
def create_server(*, owner, name: str, description: str = '') -> Server:
    name = (name or '').strip()
    if not name:
        raise ChatError('name required', code='invalid_name')
    server = Server(owner=owner, name=name, description=description, member_count=1)
    server.save()
    Role.objects.create(
        server=server, name='everyone', permissions=P.DEFAULT_EVERYONE, position=0, is_everyone=True
    )
    ServerMember.objects.create(server=server, user=owner)
    Channel.objects.create(
        server=server, channel_type=Channel.Type.TEXT, name='general', position=0
    )
    return server


def list_servers(user):
    return Server.objects.filter(members__user=user).distinct().order_by('name')


@transaction.atomic
def create_channel(*, server: Server, actor, name: str, channel_type: int = Channel.Type.TEXT) -> Channel:
    policies.require_server_perm(actor, server, P.MANAGE_CHANNELS)
    name = (name or '').strip()
    if not name:
        raise ChatError('name required', code='invalid_name')
    return Channel.objects.create(
        server=server, channel_type=channel_type, name=name, position=server.channels.count()
    )


def list_channels(user, server: Server):
    if not policies.is_server_member(user, server):
        raise PermissionDenied('Not a server member.')
    return Channel.objects.filter(server=server).order_by('position', 'id')


@transaction.atomic
def open_dm(*, user, other) -> Channel:
    if other.id == user.id:
        raise ChatError('Cannot DM yourself', code='invalid_dm')
    existing_ids = DmParticipant.objects.filter(user=user).values_list('channel_id', flat=True)
    existing = (
        Channel.objects.filter(
            id__in=existing_ids,
            channel_type=Channel.Type.DM,
            server__isnull=True,
            dm_participants__user=other,
        )
        .distinct()
        .first()
    )
    if existing:
        return existing
    channel = Channel.objects.create(channel_type=Channel.Type.DM, name='')
    DmParticipant.objects.create(channel=channel, user=user)
    DmParticipant.objects.create(channel=channel, user=other)
    return channel


@transaction.atomic
def create_group_dm(*, creator, user_ids: list) -> Channel:
    users = list({creator.id, *user_ids})
    if len(users) < 2:
        raise ChatError('Need at least one other participant', code='invalid_group')
    channel = Channel.objects.create(channel_type=Channel.Type.GROUP_DM, name='Group')
    from django.contrib.auth import get_user_model

    User = get_user_model()
    for uid in users:
        u = User.objects.filter(pk=uid).first()
        if u:
            DmParticipant.objects.create(channel=channel, user=u)
    return channel


def check_send_rate(user, channel: Channel) -> None:
    key = f'chat-rl:{user.id}:{channel.id}'
    n = cache.get(key, 0)
    limit = 20
    if n >= limit:
        raise ChatError('Rate limited', code='rate_limited')
    if n == 0:
        cache.set(key, 1, 10)
    else:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, n + 1, 10)


@transaction.atomic
def send_message(*, channel: Channel, author, content: str, reply_to_id=None, idempotency_key: str | None = None) -> Message:
    policies.require_perm(author, channel, P.SEND_MESSAGES)
    check_send_rate(author, channel)
    content = (content or '').strip()
    if not content:
        raise ChatError('content required', code='empty')
    if idempotency_key:
        cache_key = f'chat-idem:{channel.id}:{author.id}:{idempotency_key}'
        prior = cache.get(cache_key)
        if prior:
            return Message.objects.get(pk=prior)
    reply = None
    if reply_to_id:
        reply = Message.objects.filter(pk=reply_to_id, channel=channel).first()
    msg = Message.objects.create(channel=channel, author=author, content=content, reply_to=reply)
    if idempotency_key:
        cache.set(cache_key, msg.id, 3600)
    transaction.on_commit(lambda: _broadcast_message(msg))
    return msg


def list_messages(*, channel: Channel, user, before: int | None = None, limit: int = 50):
    policies.require_perm(user, channel, P.VIEW_CHANNEL)
    qs = Message.objects.filter(channel=channel).order_by('-id')
    if before:
        qs = qs.filter(id__lt=before)
    return list(qs[: min(limit, 100)])


@transaction.atomic
def edit_message(*, message: Message, editor, content: str) -> Message:
    if message.author_id != editor.id:
        policies.require_perm(editor, message.channel, P.MANAGE_MESSAGES)
    else:
        policies.require_perm(editor, message.channel, P.SEND_MESSAGES)
    message.content = content.strip()
    message.edited_at = timezone.now()
    message.save(update_fields=['content', 'edited_at'])
    return message


@transaction.atomic
def soft_delete_message(*, message: Message, actor) -> Message:
    if message.author_id != actor.id:
        policies.require_perm(actor, message.channel, P.MANAGE_MESSAGES)
    else:
        policies.require_perm(actor, message.channel, P.SEND_MESSAGES)
    message.deleted_at = timezone.now()
    message.save(update_fields=['deleted_at'])
    return message


@transaction.atomic
def create_invite(*, server: Server, actor, max_uses=None) -> Invite:
    policies.require_server_perm(actor, server, P.CREATE_INVITE)
    code = secrets.token_urlsafe(8)[:12]
    return Invite.objects.create(code=code, server=server, inviter=actor, max_uses=max_uses)


@transaction.atomic
def join_invite(*, user, code: str) -> Server:
    invite = Invite.objects.select_for_update().filter(code=code).select_related('server').first()
    if invite is None:
        raise ChatError('Invalid invite', code='invalid_invite')
    if invite.expires_at and invite.expires_at < timezone.now():
        raise ChatError('Invite expired', code='invite_expired')
    if invite.max_uses is not None and invite.uses >= invite.max_uses:
        raise ChatError('Invite exhausted', code='invite_exhausted')
    server = invite.server
    if policies.is_banned(user, server):
        raise PermissionDenied('Banned from server.')
    _, created = ServerMember.objects.get_or_create(server=server, user=user)
    if created:
        Server.objects.filter(pk=server.pk).update(member_count=server.member_count + 1)
        invite.uses += 1
        invite.save(update_fields=['uses'])
    return server


@transaction.atomic
def ban_member(*, server: Server, actor, target, reason: str = '') -> ServerBan:
    policies.require_server_perm(actor, server, P.BAN_MEMBERS)
    if target.id == server.owner_id:
        raise ChatError('Cannot ban owner', code='cannot_ban_owner')
    ServerMember.objects.filter(server=server, user=target).delete()
    ban, _ = ServerBan.objects.update_or_create(
        server=server, user=target, defaults={'reason': reason, 'banned_by': actor}
    )
    Server.objects.filter(pk=server.pk).update(
        member_count=ServerMember.objects.filter(server=server).count()
    )
    return ban


def update_read_state(*, user, channel: Channel, last_read_message_id: int) -> ReadState:
    policies.require_perm(user, channel, P.VIEW_CHANNEL)
    state, _ = ReadState.objects.update_or_create(
        user=user,
        channel=channel,
        defaults={'last_read_message_id': last_read_message_id},
    )
    return state


def user_can_subscribe(user, channel_id: int) -> bool:
    channel = Channel.objects.filter(pk=channel_id).first()
    if channel is None or user is None or not user.is_authenticated:
        return False
    try:
        policies.require_perm(user, channel, P.VIEW_CHANNEL)
        return True
    except PermissionDenied:
        return False


def trigger_typing(*, channel: Channel, user) -> dict:
    """
    Ephemeral typing indicator (Discord-shaped): requires SEND_MESSAGES,
    lasts TYPING_TTL_SECONDS, not persisted. Clients should refresh while typing
    and hide after expires_in (or when a message arrives from that user).
    """
    policies.require_perm(user, channel, P.SEND_MESSAGES)
    throttle_key = f'chat-typing-throttle:{channel.id}:{user.id}'
    if cache.get(throttle_key):
        # Still return payload so REST stays 204-friendly; skip rebroadcast spam.
        return {
            'channel_id': str(channel.id),
            'user_id': str(user.id),
            'timestamp': int(timezone.now().timestamp()),
            'expires_in': TYPING_TTL_SECONDS,
            'throttled': True,
        }
    cache.set(throttle_key, 1, 2)
    # Optional Redis presence of typers for reconnect snapshots.
    typers_key = f'chat-typers:{channel.id}'
    typers = cache.get(typers_key) or {}
    typers[str(user.id)] = int(timezone.now().timestamp()) + TYPING_TTL_SECONDS
    # Drop expired
    now = int(timezone.now().timestamp())
    typers = {uid: exp for uid, exp in typers.items() if exp > now}
    cache.set(typers_key, typers, TYPING_TTL_SECONDS + 5)
    payload = {
        'channel_id': str(channel.id),
        'user_id': str(user.id),
        'timestamp': now,
        'expires_in': TYPING_TTL_SECONDS,
    }
    layer = get_channel_layer()
    if layer is not None:
        async_to_sync(layer.group_send)(
            f'chat.channel.{channel.id}',
            {'type': 'chat.typing', 'typing': payload},
        )
    return payload


def list_typing(*, channel: Channel, user) -> list[dict]:
    policies.require_perm(user, channel, P.VIEW_CHANNEL)
    now = int(timezone.now().timestamp())
    typers = cache.get(f'chat-typers:{channel.id}') or {}
    return [
        {
            'channel_id': str(channel.id),
            'user_id': uid,
            'expires_in': max(0, exp - now),
        }
        for uid, exp in typers.items()
        if exp > now and uid != str(user.id)
    ]
