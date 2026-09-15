import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.chat.models import Channel
from apps.chat.services import trigger_typing, user_can_subscribe


class ChannelConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        channel_id = self.scope['url_route']['kwargs']['channel_id']
        if not await database_sync_to_async(user_can_subscribe)(user, int(channel_id)):
            await self.close(code=4403)
            return
        self.channel_id = int(channel_id)
        self.group_name = f'chat.channel.{channel_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        msg_type = data.get('type')
        if msg_type == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))
            return
        if msg_type in ('typing.start', 'typing'):
            user = self.scope.get('user')
            try:
                channel = await database_sync_to_async(Channel.objects.get)(pk=self.channel_id)
                await database_sync_to_async(trigger_typing)(channel=channel, user=user)
            except Exception:
                await self.send(
                    text_data=json.dumps({'type': 'error', 'code': 'typing_denied'})
                )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({'type': 'message.create', 'message': event['message']}))

    async def chat_typing(self, event):
        # Clients hide after expires_in (10s) or when message.create arrives from same user.
        await self.send(text_data=json.dumps({'type': 'typing.start', 'typing': event['typing']}))
