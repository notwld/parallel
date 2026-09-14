import uuid
from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.characters.models import Character
from apps.worlds.models import Location, RoleTemplate, World, WorldMembership

User = get_user_model()


class WorldModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('citizen', password='test-only-password')
        self.world = World.objects.create(
            slug='earth-2097',
            title='Earth-2097',
            premise='A city appears in the Atlantic.',
            status=World.Status.LIVE,
            visibility=World.Visibility.INVITE_ONLY,
            created_by=self.user,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )

    def test_status_is_independent_of_visibility(self):
        self.assertEqual(self.world.status, World.Status.LIVE)
        self.assertEqual(self.world.visibility, World.Visibility.INVITE_ONLY)

    def test_one_membership_per_account_world(self):
        WorldMembership.objects.create(world=self.world, account=self.user)
        duplicate = WorldMembership(
            world=self.world, account=self.user, status=WorldMembership.Status.ACTIVE
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorldMembership.objects.bulk_create([duplicate])

    def test_one_character_per_account_world(self):
        role = RoleTemplate.objects.create(world=self.world, name='Citizen')
        Character.objects.create(
            world=self.world, account=self.user, role_template=role, display_name='Ada'
        )
        duplicate = Character(
            world=self.world, account=self.user, role_template=role, display_name='Other'
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Character.objects.bulk_create([duplicate])

    def test_cross_world_role_assignment_rejected(self):
        other = World.objects.create(
            slug='earth-1842',
            title='Earth-1842',
            premise='Elsewhere.',
            status=World.Status.DRAFT,
            visibility=World.Visibility.PUBLIC,
            created_by=self.user,
            world_time=datetime(1842, 1, 1, tzinfo=timezone.utc),
        )
        foreign_role = RoleTemplate.objects.create(world=other, name='Scientist')
        character = Character(
            world=self.world,
            account=self.user,
            role_template=foreign_role,
            display_name='Ada',
        )
        with self.assertRaises(ValidationError):
            character.save()

    def test_cross_world_location_assignment_rejected(self):
        other = World.objects.create(
            slug='earth-1842',
            title='Earth-1842',
            premise='Elsewhere.',
            status=World.Status.DRAFT,
            visibility=World.Visibility.PUBLIC,
            created_by=self.user,
            world_time=datetime(1842, 1, 1, tzinfo=timezone.utc),
        )
        foreign_place = Location.objects.create(world=other, name='Antarctica', slug='antarctica')
        role = RoleTemplate.objects.create(world=self.world, name='Citizen')
        character = Character(
            world=self.world,
            account=self.user,
            role_template=role,
            location=foreign_place,
            display_name='Ada',
        )
        with self.assertRaises(ValidationError):
            character.save()

    def test_location_parent_must_share_world(self):
        other = World.objects.create(
            slug='earth-1842',
            title='Earth-1842',
            premise='Elsewhere.',
            status=World.Status.DRAFT,
            visibility=World.Visibility.PUBLIC,
            created_by=self.user,
            world_time=datetime(1842, 1, 1, tzinfo=timezone.utc),
        )
        parent = Location.objects.create(world=other, name='Atlantic', slug='atlantic')
        child = Location(world=self.world, name='City', slug='city', parent=parent)
        with self.assertRaises(ValidationError):
            child.save()

    def test_location_parent_cycles_rejected(self):
        region = Location.objects.create(world=self.world, name='Atlantic', slug='atlantic')
        city = Location.objects.create(
            world=self.world, name='New City', slug='new-city', parent=region
        )
        region.parent = city
        with self.assertRaises(ValidationError):
            region.save()

    def test_location_cannot_be_its_own_parent(self):
        place = Location.objects.create(world=self.world, name='Site', slug='site')
        place.parent = place
        with self.assertRaises(ValidationError):
            place.save()

    def test_role_templates_unique_per_world_and_carry_slot_limit(self):
        RoleTemplate.objects.create(world=self.world, name='Minister', max_slots=1)
        duplicate = RoleTemplate(world=self.world, name='Minister', max_slots=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RoleTemplate.objects.bulk_create([duplicate])

    def test_records_use_uuids(self):
        role = RoleTemplate.objects.create(world=self.world, name='Journalist', max_slots=3)
        place = Location.objects.create(world=self.world, name='Harbor', slug='harbor')
        membership = WorldMembership.objects.create(world=self.world, account=self.user)
        character = Character.objects.create(
            world=self.world,
            account=self.user,
            role_template=role,
            location=place,
            display_name='Rae',
        )
        for obj in (self.world, role, place, membership, character):
            self.assertIsInstance(obj.pk, uuid.UUID)

    def test_tick_interval_default_is_one_day(self):
        self.assertEqual(self.world.tick_interval, timedelta(days=1))
