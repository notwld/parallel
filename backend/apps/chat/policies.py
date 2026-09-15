from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.chat import permissions as P
from apps.chat.models import (
    Channel,
    ChannelPermissionOverwrite,
    DmParticipant,
    MemberRole,
    Role,
    Server,
    ServerBan,
    ServerMember,
)


def is_server_member(user, server: Server) -> bool:
    return ServerMember.objects.filter(server=server, user=user).exists()


def is_banned(user, server: Server) -> bool:
    return ServerBan.objects.filter(server=server, user=user).exists()


def base_permissions(user, server: Server) -> int:
    if not is_server_member(user, server):
        return 0
    if server.owner_id == user.id:
        return P.ALL
    everyone = Role.objects.filter(server=server, is_everyone=True).first()
    perms = everyone.permissions if everyone else P.DEFAULT_EVERYONE
    for link in MemberRole.objects.filter(server=server, user=user).select_related('role'):
        perms |= link.role.permissions
    if perms & P.ADMINISTRATOR:
        return P.ALL
    return perms


def channel_permissions(user, channel: Channel) -> int:
    if channel.channel_type in (Channel.Type.DM, Channel.Type.GROUP_DM):
        if DmParticipant.objects.filter(channel=channel, user=user).exists():
            return P.VIEW_CHANNEL | P.SEND_MESSAGES | P.MANAGE_MESSAGES
        return 0
    if channel.server_id is None:
        return 0
    server = channel.server
    if is_banned(user, server):
        return 0
    perms = base_permissions(user, server)
    if perms & P.ADMINISTRATOR:
        return P.ALL
    # Apply role overwrites then member overwrites (deny then allow).
    role_ids = set(
        MemberRole.objects.filter(server=server, user=user).values_list('role_id', flat=True)
    )
    everyone = Role.objects.filter(server=server, is_everyone=True).first()
    if everyone:
        role_ids.add(everyone.id)
    for ow in ChannelPermissionOverwrite.objects.filter(
        channel=channel, target_type=ChannelPermissionOverwrite.TargetType.ROLE, target_id__in=role_ids
    ):
        perms = (perms & ~ow.deny) | ow.allow
    member_ow = ChannelPermissionOverwrite.objects.filter(
        channel=channel,
        target_type=ChannelPermissionOverwrite.TargetType.MEMBER,
        target_user=user,
    ).first()
    if member_ow:
        perms = (perms & ~member_ow.deny) | member_ow.allow
    return perms


def require_perm(user, channel: Channel, bit: int) -> None:
    if channel_permissions(user, channel) & bit:
        # timeout check for server channels
        if channel.server_id:
            member = ServerMember.objects.filter(server_id=channel.server_id, user=user).first()
            if member and member.timeout_until and member.timeout_until > timezone.now():
                if bit == P.SEND_MESSAGES:
                    raise PermissionDenied('Timed out.')
        return
    raise PermissionDenied('Missing channel permission.')


def require_server_perm(user, server: Server, bit: int) -> None:
    if is_banned(user, server):
        raise PermissionDenied('Banned from server.')
    perms = base_permissions(user, server)
    if perms & bit or perms & P.ADMINISTRATOR:
        return
    raise PermissionDenied('Missing server permission.')
