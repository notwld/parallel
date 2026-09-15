from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.chat.models import Channel, Message, Server
from apps.chat.services import (
    ChatError,
    ban_member,
    channel_public,
    create_channel,
    create_group_dm,
    create_invite,
    create_server,
    edit_message,
    join_invite,
    list_channels,
    list_messages,
    list_servers,
    list_typing,
    message_public,
    open_dm,
    send_message,
    server_public,
    soft_delete_message,
    trigger_typing,
    update_read_state,
)

User = get_user_model()


def _err(exc, status=400):
    code = getattr(exc, 'rejection_code', None) or 'invalid'
    detail = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
    return Response({'code': code, 'detail': detail}, status=status)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def servers(request):
    if request.method == 'GET':
        return Response({'servers': [server_public(s) for s in list_servers(request.user)]})
    try:
        server = create_server(
            owner=request.user,
            name=request.data.get('name', ''),
            description=request.data.get('description', ''),
        )
    except ChatError as exc:
        return _err(exc)
    return Response(server_public(server), status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def server_detail(request, server_id):
    server = get_object_or_404(Server, pk=server_id)
    from apps.chat import policies

    if not policies.is_server_member(request.user, server):
        return Response({'code': 'forbidden', 'detail': 'Not a member.'}, status=403)
    return Response(server_public(server))


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def server_channels(request, server_id):
    server = get_object_or_404(Server, pk=server_id)
    if request.method == 'GET':
        try:
            rows = list_channels(request.user, server)
        except Exception as exc:
            return Response({'code': 'forbidden', 'detail': str(exc)}, status=403)
        return Response({'channels': [channel_public(c) for c in rows]})
    try:
        ch = create_channel(
            server=server,
            actor=request.user,
            name=request.data.get('name', ''),
            channel_type=int(request.data.get('type', Channel.Type.TEXT)),
        )
    except ChatError as exc:
        return _err(exc)
    except Exception as exc:
        return Response({'code': 'forbidden', 'detail': str(exc)}, status=403)
    return Response(channel_public(ch), status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dm_open(request):
    other_id = request.data.get('user_id')
    other = get_object_or_404(User, pk=other_id)
    try:
        channel = open_dm(user=request.user, other=other)
    except ChatError as exc:
        return _err(exc)
    return Response(channel_public(channel), status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def group_dm_create(request):
    ids = request.data.get('user_ids') or []
    try:
        channel = create_group_dm(creator=request.user, user_ids=ids)
    except ChatError as exc:
        return _err(exc)
    return Response(channel_public(channel), status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def channel_messages(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    if request.method == 'GET':
        before = request.query_params.get('before')
        try:
            rows = list_messages(
                channel=channel,
                user=request.user,
                before=int(before) if before else None,
                limit=int(request.query_params.get('limit', 50)),
            )
        except Exception as exc:
            return Response({'code': 'forbidden', 'detail': str(exc)}, status=403)
        return Response({'messages': [message_public(m) for m in rows]})
    try:
        msg = send_message(
            channel=channel,
            author=request.user,
            content=request.data.get('content', ''),
            reply_to_id=request.data.get('reply_to_id'),
            idempotency_key=request.headers.get('Idempotency-Key') or request.data.get('idempotency_key'),
        )
    except ChatError as exc:
        status = 429 if exc.rejection_code == 'rate_limited' else 400
        return _err(exc, status=status)
    except Exception as exc:
        return Response({'code': 'forbidden', 'detail': str(exc)}, status=403)
    return Response(message_public(msg), status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def message_detail(request, message_id):
    message = get_object_or_404(Message, pk=message_id)
    try:
        if request.method == 'PATCH':
            msg = edit_message(message=message, editor=request.user, content=request.data.get('content', ''))
            return Response(message_public(msg))
        msg = soft_delete_message(message=message, actor=request.user)
        return Response(message_public(msg))
    except Exception as exc:
        return Response({'code': 'forbidden', 'detail': str(exc)}, status=403)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invites_create(request, server_id):
    server = get_object_or_404(Server, pk=server_id)
    try:
        invite = create_invite(server=server, actor=request.user)
    except Exception as exc:
        return Response({'code': 'forbidden', 'detail': str(exc)}, status=403)
    return Response({'code': invite.code, 'server_id': str(server.id)}, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invites_join(request):
    try:
        server = join_invite(user=request.user, code=request.data.get('code', ''))
    except ChatError as exc:
        return _err(exc)
    except Exception as exc:
        return Response({'code': 'forbidden', 'detail': str(exc)}, status=403)
    return Response(server_public(server))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def server_ban(request, server_id):
    server = get_object_or_404(Server, pk=server_id)
    target = get_object_or_404(User, pk=request.data.get('user_id'))
    try:
        ban_member(server=server, actor=request.user, target=target, reason=request.data.get('reason', ''))
    except ChatError as exc:
        return _err(exc)
    except Exception as exc:
        return Response({'code': 'forbidden', 'detail': str(exc)}, status=403)
    return Response({'detail': 'banned'})


@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def channel_typing(request, channel_id):
    """POST: start/refresh typing (10s). GET: who is currently typing (ephemeral)."""
    channel = get_object_or_404(Channel, pk=channel_id)
    if request.method == 'GET':
        try:
            return Response({'typing': list_typing(channel=channel, user=request.user)})
        except Exception as exc:
            return Response({'code': 'forbidden', 'detail': str(exc)}, status=403)
    try:
        trigger_typing(channel=channel, user=request.user)
    except Exception as exc:
        return Response({'code': 'forbidden', 'detail': str(exc)}, status=403)
    return Response(status=204)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def read_state(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    try:
        state = update_read_state(
            user=request.user,
            channel=channel,
            last_read_message_id=int(request.data.get('last_read_message_id', 0)),
        )
    except Exception as exc:
        return Response({'code': 'forbidden', 'detail': str(exc)}, status=403)
    return Response({
        'channel_id': str(channel.id),
        'last_read_message_id': str(state.last_read_message_id),
    })
