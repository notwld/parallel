import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase

from apps.characters.models import Character
from apps.worlds.models import RoleTemplate, World, WorldMembership

User = get_user_model()


class OnboardingApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.world = World.objects.create(
            slug='earth-2097',
            title='Earth-2097',
            premise='A city appears in the Atlantic.',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
            rules={'invite_code': 'alpha-invite'},
        )
        self.citizen = RoleTemplate.objects.create(
            world=self.world, name='Citizen', description='Ordinary resident'
        )
        self.minister = RoleTemplate.objects.create(
            world=self.world, name='Minister', invite_only=True, max_slots=1
        )
        self.office = RoleTemplate.objects.create(
            world=self.world, name='Harbor Lead', max_slots=1
        )

    def _csrf_headers(self, client=None):
        client = client or self.csrf_client
        client.get('/api/v1/auth/csrf/')
        return {'HTTP_X_CSRFTOKEN': client.cookies['csrftoken'].value}

    def _signup_and_login(self, email='ada@example.com', password='test-only-password'):
        headers = self._csrf_headers()
        res = self.csrf_client.post(
            '/api/v1/auth/signup/',
            data={'email': email, 'password': password},
            content_type='application/json',
            **headers,
        )
        self.assertEqual(res.status_code, 201, res.content)
        token = res.json()['verification_token']
        res = self.csrf_client.post(
            '/api/v1/auth/verify-email/',
            data={'token': token},
            content_type='application/json',
            **self._csrf_headers(),
        )
        self.assertEqual(res.status_code, 200)
        res = self.csrf_client.post(
            '/api/v1/auth/login/',
            data={'email': email, 'password': password},
            content_type='application/json',
            **self._csrf_headers(),
        )
        self.assertEqual(res.status_code, 200, res.content)
        return res.json()

    def test_signup_login_logout_and_recover(self):
        self._signup_and_login()
        me = self.csrf_client.get('/api/v1/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.json()['email_verified'])

        reset = self.csrf_client.post(
            '/api/v1/auth/password-reset/',
            data={'email': 'ada@example.com'},
            content_type='application/json',
            **self._csrf_headers(),
        )
        self.assertEqual(reset.status_code, 200)
        raw = reset.json()['reset_token']
        confirm = self.csrf_client.post(
            '/api/v1/auth/password-reset/confirm/',
            data={'token': raw, 'password': 'new-only-password'},
            content_type='application/json',
            **self._csrf_headers(),
        )
        self.assertEqual(confirm.status_code, 200)

        login = self.csrf_client.post(
            '/api/v1/auth/login/',
            data={'email': 'ada@example.com', 'password': 'new-only-password'},
            content_type='application/json',
            **self._csrf_headers(),
        )
        self.assertEqual(login.status_code, 200)
        logout = self.csrf_client.post(
            '/api/v1/auth/logout/', content_type='application/json', **self._csrf_headers()
        )
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.csrf_client.get('/api/v1/auth/me/').status_code, 403)

    def test_login_without_csrf_rejected(self):
        User.objects.create_user('bob', email='bob@example.com', password='test-only-password')
        bare = Client(enforce_csrf_checks=True)
        res = bare.post(
            '/api/v1/auth/login/',
            data={'email': 'bob@example.com', 'password': 'test-only-password'},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 403)

    def test_auth_rate_limit(self):
        User.objects.create_user('lim', email='lim@example.com', password='test-only-password')
        headers = self._csrf_headers()
        for _ in range(20):
            self.csrf_client.post(
                '/api/v1/auth/login/',
                data={'email': 'lim@example.com', 'password': 'wrong'},
                content_type='application/json',
                **headers,
            )
        res = self.csrf_client.post(
            '/api/v1/auth/login/',
            data={'email': 'lim@example.com', 'password': 'wrong'},
            content_type='application/json',
            **self._csrf_headers(),
        )
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.json()['code'], 'rate_limited')

    def test_session_revocation(self):
        self._signup_and_login(email='rae@example.com')
        other = Client(enforce_csrf_checks=True)
        other.get('/api/v1/auth/csrf/')
        login = other.post(
            '/api/v1/auth/login/',
            data={'email': 'rae@example.com', 'password': 'test-only-password'},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=other.cookies['csrftoken'].value,
        )
        self.assertEqual(login.status_code, 200)
        sessions = other.get('/api/v1/auth/sessions/').json()['sessions']
        self.assertGreaterEqual(len(sessions), 2)
        foreign = next(s for s in sessions if not s['current'])
        res = other.delete(
            f'/api/v1/auth/sessions/{foreign["id"]}/',
            HTTP_X_CSRFTOKEN=other.cookies['csrftoken'].value,
        )
        self.assertEqual(res.status_code, 204)
        self.assertEqual(self.csrf_client.get('/api/v1/auth/me/').status_code, 403)
        self.assertEqual(other.get('/api/v1/auth/me/').status_code, 200)

    def test_preferences_persist(self):
        self._signup_and_login(email='pref@example.com')
        res = self.csrf_client.patch(
            '/api/v1/auth/me/preferences/',
            data={'timezone': 'UTC', 'notifications': {'email': False}},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.csrf_client.cookies['csrftoken'].value,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['preferences']['timezone'], 'UTC')
        me = self.csrf_client.get('/api/v1/auth/me/').json()
        self.assertEqual(me['preferences']['timezone'], 'UTC')

    def test_world_landing_and_join_profile_hides_account(self):
        landing = self.csrf_client.get('/api/v1/worlds/earth-2097/')
        self.assertEqual(landing.status_code, 200)
        body = landing.json()
        self.assertEqual(body['slug'], 'earth-2097')
        role_ids = {r['id'] for r in body['roles']}
        self.assertIn(str(self.citizen.id), role_ids)
        self.assertNotIn(str(self.minister.id), role_ids)

        self._signup_and_login(email='join@example.com')
        res = self.csrf_client.post(
            '/api/v1/worlds/earth-2097/join/',
            data={
                'role_template_id': str(self.citizen.id),
                'display_name': 'Ada',
                'idempotency_key': 'join-1',
            },
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.csrf_client.cookies['csrftoken'].value,
        )
        self.assertEqual(res.status_code, 201, res.content)
        profile = res.json()
        self.assertEqual(profile['display_name'], 'Ada')
        self.assertNotIn('account', profile)
        self.assertNotIn('email', profile)
        self.assertNotIn('user', profile)

        again = self.csrf_client.post(
            '/api/v1/worlds/earth-2097/join/',
            data={
                'role_template_id': str(self.citizen.id),
                'display_name': 'Ada',
                'idempotency_key': 'join-1',
            },
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.csrf_client.cookies['csrftoken'].value,
        )
        self.assertEqual(again.status_code, 201)
        self.assertEqual(Character.objects.filter(world=self.world).count(), 1)

        mine = self.csrf_client.get('/api/v1/worlds/earth-2097/character/')
        self.assertEqual(mine.status_code, 200)
        self.assertNotIn('account_id', mine.json())

    def test_paused_and_invite_only_and_privileged_role(self):
        self.world.status = World.Status.PAUSED
        self.world.save()
        self._signup_and_login(email='paused@example.com')
        res = self.csrf_client.post(
            '/api/v1/worlds/earth-2097/join/',
            data={
                'role_template_id': str(self.citizen.id),
                'display_name': 'P',
                'idempotency_key': 'p1',
            },
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.csrf_client.cookies['csrftoken'].value,
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()['code'], 'world_paused')

        self.world.status = World.Status.LIVE
        self.world.visibility = World.Visibility.INVITE_ONLY
        self.world.save()
        res = self.csrf_client.post(
            '/api/v1/worlds/earth-2097/join/',
            data={
                'role_template_id': str(self.citizen.id),
                'display_name': 'P',
                'idempotency_key': 'p2',
            },
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.csrf_client.cookies['csrftoken'].value,
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()['code'], 'invite_required')

        res = self.csrf_client.post(
            '/api/v1/worlds/earth-2097/join/',
            data={
                'role_template_id': str(self.citizen.id),
                'display_name': 'P',
                'invite_ref': 'alpha-invite',
                'idempotency_key': 'p3',
            },
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.csrf_client.cookies['csrftoken'].value,
        )
        self.assertEqual(res.status_code, 201, res.content)

        res = self.csrf_client.post(
            '/api/v1/worlds/earth-2097/join/',
            data={
                'role_template_id': str(self.minister.id),
                'display_name': 'Boss',
                'invite_ref': 'alpha-invite',
                'idempotency_key': 'p4',
            },
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.csrf_client.cookies['csrftoken'].value,
        )
        # Already has character — returns existing, does not grant minister.
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Character.objects.get(account__email='paused@example.com').role_template.name, 'Citizen')

        user2 = User.objects.create_user('u2', email='u2@example.com', password='test-only-password')
        c2 = Client(enforce_csrf_checks=True)
        c2.get('/api/v1/auth/csrf/')
        c2.post(
            '/api/v1/auth/login/',
            data={'email': 'u2@example.com', 'password': 'test-only-password'},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=c2.cookies['csrftoken'].value,
        )
        # Need signup flow for csrf session — user2 already created; just login worked
        res = c2.post(
            '/api/v1/worlds/earth-2097/join/',
            data={
                'role_template_id': str(self.minister.id),
                'display_name': 'M',
                'invite_ref': 'alpha-invite',
                'idempotency_key': 'm1',
            },
            content_type='application/json',
            HTTP_X_CSRFTOKEN=c2.cookies['csrftoken'].value,
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()['code'], 'role_invite_only')

    def test_role_slot_limit(self):
        self._signup_and_login(email='slot1@example.com')
        res = self.csrf_client.post(
            '/api/v1/worlds/earth-2097/join/',
            data={
                'role_template_id': str(self.office.id),
                'display_name': 'Lead',
                'idempotency_key': 'slot-a',
            },
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.csrf_client.cookies['csrftoken'].value,
        )
        self.assertEqual(res.status_code, 201)
        User.objects.create_user('slot2', email='slot2@example.com', password='test-only-password')
        other = Client(enforce_csrf_checks=True)
        other.get('/api/v1/auth/csrf/')
        other.post(
            '/api/v1/auth/login/',
            data={'email': 'slot2@example.com', 'password': 'test-only-password'},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=other.cookies['csrftoken'].value,
        )
        res = other.post(
            '/api/v1/worlds/earth-2097/join/',
            data={
                'role_template_id': str(self.office.id),
                'display_name': 'Lead2',
                'idempotency_key': 'slot-b',
            },
            content_type='application/json',
            HTTP_X_CSRFTOKEN=other.cookies['csrftoken'].value,
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()['code'], 'role_full')

    def test_oauth_unconfigured(self):
        res = self.csrf_client.get('/api/v1/auth/oauth/providers/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['providers'], [])


class ConcurrentJoinTests(TransactionTestCase):
    def setUp(self):
        self.world = World.objects.create(
            slug='slot-world',
            title='Slots',
            premise='Concurrency.',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )
        self.role = RoleTemplate.objects.create(world=self.world, name='Unique', max_slots=1)
        self.users = [
            User.objects.create_user(f'c{i}', email=f'c{i}@example.com', password='x')
            for i in range(4)
        ]

    def test_concurrent_joins_respect_slot_limit(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL required for concurrent join')

        from apps.characters.services import join_world

        barrier = threading.Barrier(4)
        results: list = []

        def worker(user):
            try:
                barrier.wait(timeout=10)
                character = join_world(
                    account=user,
                    world=self.world,
                    role_template_id=self.role.id,
                    display_name=user.username,
                    idempotency_key=f'cj-{user.id}',
                )
                results.append(('ok', character.id))
            except Exception as exc:  # noqa: BLE001
                code = getattr(exc, 'rejection_code', None) or type(exc).__name__
                results.append(('err', code))
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(worker, self.users))

        ok = [r for r in results if r[0] == 'ok']
        self.assertEqual(len(ok), 1)
        self.assertEqual(Character.objects.filter(world=self.world, role_template=self.role).count(), 1)
        self.assertEqual(WorldMembership.objects.filter(world=self.world).count(), 1)
