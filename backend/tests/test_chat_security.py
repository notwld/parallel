from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase

from apps.chat import permissions as P
from apps.chat.models import Channel, Message, Server, ServerMember
from apps.chat.policies import channel_permissions
from apps.chat.services import (
    ban_member,
    create_invite,
    create_server,
    join_invite,
    list_messages,
    open_dm,
    send_message,
)
from config.asgi import application

User = get_user_model()


class ChatServerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user('owner', email='o@example.com', password='x')
        self.member = User.objects.create_user('member', email='m@example.com', password='x')
        self.outsider = User.objects.create_user('out', email='x@example.com', password='x')

    def test_create_server_and_permissions(self):
        server = create_server(owner=self.owner, name='Ops')
        self.assertEqual(server.member_count, 1)
        self.client.force_login(self.owner)
        res = self.client.get(f'/api/v1/chat/servers/{server.id}/channels/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any(c['name'] == 'general' for c in res.json()['channels']))
        general = Channel.objects.get(server=server, name='general')
        self.assertTrue(channel_permissions(self.owner, general) & P.ADMINISTRATOR)
        self.assertEqual(channel_permissions(self.outsider, general), 0)

    def test_invite_join_and_ban(self):
        server = create_server(owner=self.owner, name='Crew')
        invite = create_invite(server=server, actor=self.owner)
        joined = join_invite(user=self.member, code=invite.code)
        self.assertEqual(joined.id, server.id)
        self.assertTrue(ServerMember.objects.filter(server=server, user=self.member).exists())
        ban_member(server=server, actor=self.owner, target=self.member, reason='spam')
        self.assertFalse(ServerMember.objects.filter(server=server, user=self.member).exists())
        with self.assertRaises(Exception):
            join_invite(user=self.member, code=create_invite(server=server, actor=self.owner).code)

    def test_dm_isolation_and_reuse(self):
        a = open_dm(user=self.owner, other=self.member)
        b = open_dm(user=self.member, other=self.owner)
        self.assertEqual(a.id, b.id)
        msg = send_message(channel=a, author=self.owner, content='hi')
        self.assertEqual(msg.content, 'hi')
        with self.assertRaises(Exception):
            list_messages(channel=a, user=self.outsider)

    def test_message_timeline_and_outsider(self):
        server = create_server(owner=self.owner, name='Chat')
        channel = Channel.objects.get(server=server, name='general')
        send_message(channel=channel, author=self.owner, content='one')
        send_message(channel=channel, author=self.owner, content='two')
        rows = list_messages(channel=channel, user=self.owner)
        self.assertEqual([m.content for m in rows], ['two', 'one'])
        self.client.force_login(self.outsider)
        res = self.client.get(f'/api/v1/chat/channels/{channel.id}/messages/')
        self.assertEqual(res.status_code, 403)

    def test_api_create_server(self):
        self.client.force_login(self.owner)
        res = self.client.post(
            '/api/v1/chat/servers/',
            data={'name': 'Alpha'},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['name'], 'Alpha')
        self.assertNotIn('discord', res.json().get('name', '').lower())

    def test_typing_indicator(self):
        server = create_server(owner=self.owner, name='Type')
        channel = Channel.objects.get(server=server, name='general')
        self.client.force_login(self.owner)
        res = self.client.post(f'/api/v1/chat/channels/{channel.id}/typing/')
        self.assertEqual(res.status_code, 204)
        self.client.force_login(self.member)
        # member not in server
        res = self.client.post(f'/api/v1/chat/channels/{channel.id}/typing/')
        self.assertEqual(res.status_code, 403)
        from apps.chat.services import join_invite, create_invite

        join_invite(user=self.member, code=create_invite(server=server, actor=self.owner).code)
        self.client.force_login(self.member)
        res = self.client.post(f'/api/v1/chat/channels/{channel.id}/typing/')
        self.assertEqual(res.status_code, 204)
        self.client.force_login(self.owner)
        listed = self.client.get(f'/api/v1/chat/channels/{channel.id}/typing/')
        self.assertEqual(listed.status_code, 200)
        user_ids = {t['user_id'] for t in listed.json()['typing']}
        self.assertIn(str(self.member.id), user_ids)
        self.assertNotIn(str(self.owner.id), user_ids)  # exclude self


class ChatWebsocketTests(TransactionTestCase):
    def _communicator(self, path, user):
        communicator = WebsocketCommunicator(application, path)
        communicator.scope['user'] = user
        communicator.scope['headers'] = [
            (b'host', b'localhost'),
            (b'origin', b'http://localhost'),
        ]
        return communicator

    async def test_unauthorized_ws_rejected(self):
        owner = await User.objects.acreate(username='wso', email='wso@example.com')
        outsider = await User.objects.acreate(username='wsx', email='wsx@example.com')
        server = await create_server_async(owner)
        channel = await Channel.objects.aget(server=server, name='general')
        communicator = self._communicator(f'/ws/chat/channels/{channel.id}/', outsider)
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_authorized_ws_accepts(self):
        owner = await User.objects.acreate(username='wso2', email='wso2@example.com')
        server = await create_server_async(owner)
        channel = await Channel.objects.aget(server=server, name='general')
        communicator = self._communicator(f'/ws/chat/channels/{channel.id}/', owner)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.send_json_to({'type': 'typing.start'})
        event = await communicator.receive_json_from(timeout=2)
        self.assertEqual(event['type'], 'typing.start')
        self.assertEqual(event['typing']['user_id'], str(owner.id))
        self.assertEqual(event['typing']['expires_in'], 10)
        await communicator.disconnect()


async def create_server_async(owner):
    from asgiref.sync import sync_to_async

    return await sync_to_async(create_server)(owner=owner, name='WS')
