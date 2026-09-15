import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase, TransactionTestCase

from apps.characters.models import Character
from apps.organizations.models import Organization, OrgMembership
from apps.organizations.policies import (
    CAP_LEADER,
    CAP_MANAGE,
    CAP_PUBLISH,
    CAP_READ_INTERNAL,
)
from apps.organizations.services import (
    OrgError,
    add_member,
    allocate_leadership,
    create_organization,
    publish_as_org,
    read_internal_record,
    revoke_membership,
)
from apps.worlds.models import RoleTemplate, World, WorldMembership

User = get_user_model()


class OrgAuthorityTests(TestCase):
    def setUp(self):
        self.world = World.objects.create(
            slug='org-world',
            title='Org World',
            premise='Institutions.',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )
        self.role = RoleTemplate.objects.create(world=self.world, name='Citizen')
        self.leader_user = User.objects.create_user('lead', email='l@example.com', password='x')
        self.member_user = User.objects.create_user('mem', email='m@example.com', password='x')
        self.outsider_user = User.objects.create_user('out', email='o@example.com', password='x')
        for u in (self.leader_user, self.member_user, self.outsider_user):
            WorldMembership.objects.create(world=self.world, account=u)
        self.leader = Character.objects.create(
            world=self.world, account=self.leader_user, role_template=self.role, display_name='Lead'
        )
        self.member = Character.objects.create(
            world=self.world, account=self.member_user, role_template=self.role, display_name='Mem'
        )
        other = World.objects.create(
            slug='other',
            title='Other',
            premise='x',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )
        other_role = RoleTemplate.objects.create(world=other, name='X')
        WorldMembership.objects.create(world=other, account=self.outsider_user)
        self.foreign = Character.objects.create(
            world=other, account=self.outsider_user, role_template=other_role, display_name='Foreign'
        )
        self.org = create_organization(world=self.world, name='Newsroom', slug='newsroom', max_leaders=1)
        add_member(
            organization=self.org,
            character=self.leader,
            role_name='editor',
            capabilities=[CAP_MANAGE, CAP_PUBLISH, CAP_READ_INTERNAL, CAP_LEADER],
            actor_character=self.leader,
            idempotency_key='add-leader',
        )
        add_member(
            organization=self.org,
            character=self.member,
            role_name='reporter',
            capabilities=[CAP_READ_INTERNAL],
            actor_character=self.leader,
            idempotency_key='add-member',
        )

    def test_ordinary_member_cannot_publish_as_org(self):
        with self.assertRaises(PermissionDenied):
            publish_as_org(organization=self.org, character=self.member, body='Official lie')
        ok = publish_as_org(organization=self.org, character=self.leader, body='We investigated')
        self.assertEqual(ok['authored_as'], 'organization')

    def test_outsider_cannot_read_internal(self):
        secret = {'title': 'Source list'}
        with self.assertRaises(PermissionDenied):
            read_internal_record(organization=self.org, character=self.foreign, record=secret)
        self.assertEqual(
            read_internal_record(organization=self.org, character=self.member, record=secret),
            secret,
        )

    def test_revocation_takes_effect_immediately(self):
        revoke_membership(
            organization=self.org,
            character=self.member,
            actor_character=self.leader,
            idempotency_key='revoke-1',
        )
        with self.assertRaises(PermissionDenied):
            read_internal_record(organization=self.org, character=self.member, record={'x': 1})
        with self.assertRaises(PermissionDenied):
            publish_as_org(organization=self.org, character=self.member, body='nope')

    def test_cross_world_character_rejected(self):
        with self.assertRaises(OrgError):
            add_member(
                organization=self.org,
                character=self.foreign,
                idempotency_key='cross',
            )
        bad = OrgMembership(
            organization=self.org, character=self.foreign, capabilities=[CAP_READ_INTERNAL]
        )
        with self.assertRaises(ValidationError):
            bad.save()


class OrgLeadershipSlotTests(TestCase):
    def setUp(self):
        self.world = World.objects.create(
            slug='lead-world',
            title='Lead',
            premise='x',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )
        self.role = RoleTemplate.objects.create(world=self.world, name='Citizen')
        self.admin_u = User.objects.create_user('adm', email='a@example.com', password='x')
        self.a_u = User.objects.create_user('aa', email='aa@example.com', password='x')
        self.b_u = User.objects.create_user('bb', email='bb@example.com', password='x')
        for u in (self.admin_u, self.a_u, self.b_u):
            WorldMembership.objects.create(world=self.world, account=u)
        self.admin = Character.objects.create(
            world=self.world, account=self.admin_u, role_template=self.role, display_name='Admin'
        )
        self.a = Character.objects.create(
            world=self.world, account=self.a_u, role_template=self.role, display_name='A'
        )
        self.b = Character.objects.create(
            world=self.world, account=self.b_u, role_template=self.role, display_name='B'
        )
        self.org = create_organization(world=self.world, name='Office', slug='office', max_leaders=1)
        add_member(
            organization=self.org,
            character=self.admin,
            capabilities=[CAP_MANAGE, CAP_READ_INTERNAL],
            idempotency_key='adm',
        )
        add_member(
            organization=self.org, character=self.a, capabilities=[CAP_READ_INTERNAL], idempotency_key='a'
        )
        add_member(
            organization=self.org, character=self.b, capabilities=[CAP_READ_INTERNAL], idempotency_key='b'
        )

    def test_second_leader_rejected(self):
        allocate_leadership(
            organization=self.org, character=self.a, actor_character=self.admin, idempotency_key='L1'
        )
        with self.assertRaises(OrgError) as ctx:
            allocate_leadership(
                organization=self.org, character=self.b, actor_character=self.admin, idempotency_key='L2'
            )
        self.assertEqual(ctx.exception.rejection_code, 'leader_full')
        self.assertEqual(
            sum(
                1
                for m in OrgMembership.objects.filter(organization=self.org, status='active')
                if CAP_LEADER in (m.capabilities or [])
            ),
            1,
        )


class ConcurrentLeadershipTests(TransactionTestCase):
    def setUp(self):
        self.world = World.objects.create(
            slug='c-lead',
            title='C',
            premise='x',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )
        self.role = RoleTemplate.objects.create(world=self.world, name='Citizen')
        self.admin_u = User.objects.create_user('cadm', email='cadm@example.com', password='x')
        WorldMembership.objects.create(world=self.world, account=self.admin_u)
        self.admin = Character.objects.create(
            world=self.world, account=self.admin_u, role_template=self.role, display_name='Admin'
        )
        self.org = create_organization(world=self.world, name='Seat', slug='seat', max_leaders=1)
        add_member(
            organization=self.org,
            character=self.admin,
            capabilities=[CAP_MANAGE, CAP_READ_INTERNAL],
            idempotency_key='cadm',
        )
        self.candidates = []
        for i in range(4):
            u = User.objects.create_user(f'c{i}', email=f'c{i}@example.com', password='x')
            WorldMembership.objects.create(world=self.world, account=u)
            ch = Character.objects.create(
                world=self.world, account=u, role_template=self.role, display_name=f'C{i}'
            )
            add_member(
                organization=self.org,
                character=ch,
                capabilities=[CAP_READ_INTERNAL],
                idempotency_key=f'cm{i}',
            )
            self.candidates.append(ch)

    def test_concurrent_leadership_obeys_max(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL required for concurrent leadership')

        barrier = threading.Barrier(4)
        results = []

        def worker(ch):
            try:
                barrier.wait(timeout=10)
                allocate_leadership(
                    organization=self.org,
                    character=ch,
                    actor_character=self.admin,
                    idempotency_key=f'lead-{ch.id}',
                )
                results.append('ok')
            except Exception as exc:  # noqa: BLE001
                results.append(getattr(exc, 'rejection_code', type(exc).__name__))
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(worker, self.candidates))

        self.assertEqual(results.count('ok'), 1)
        self.assertEqual(
            sum(
                1
                for m in OrgMembership.objects.filter(organization=self.org, status='active')
                if CAP_LEADER in (m.capabilities or [])
            ),
            1,
        )
