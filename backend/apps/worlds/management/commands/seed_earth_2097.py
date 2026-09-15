from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from apps.worlds.models import Location, RoleTemplate, World


class Command(BaseCommand):
    help = 'Idempotently seed the Earth-2097 flagship world and claimable roles.'

    def handle(self, *args, **options):
        world, created = World.objects.get_or_create(
            slug='earth-2097',
            defaults={
                'title': 'Earth-2097',
                'premise': (
                    'A mysterious city appears in the Atlantic Ocean. '
                    'Journalists, scientists, officials, and citizens receive '
                    'different accounts of what it contains.'
                ),
                'status': World.Status.LIVE,
                'visibility': World.Visibility.PUBLIC,
                'content_rating': 'mature',
                'world_time': datetime(2097, 1, 1, tzinfo=timezone.utc),
                'rules': {'invite_code': 'alpha-invite'},
            },
        )
        if not created and world.status != World.Status.LIVE:
            world.status = World.Status.LIVE
            world.save(update_fields=['status', 'updated_at'])

        harbor, _ = Location.objects.get_or_create(
            world=world,
            slug='atlantic-harbor',
            defaults={'name': 'Atlantic Harbor', 'kind': 'port'},
        )

        roles = [
            ('Citizen', 'Ordinary resident watching events unfold.', False, None, harbor),
            ('Journalist', 'Investigate, publish, and chase sources.', False, None, harbor),
            ('Scientist', 'Study the city and produce evidence.', False, None, harbor),
            ('Harbor Lead', 'Coordinate the local response.', False, 1, harbor),
            ('Minister', 'Invite-only official seat.', True, 1, harbor),
        ]
        for name, description, invite_only, max_slots, location in roles:
            RoleTemplate.objects.update_or_create(
                world=world,
                name=name,
                defaults={
                    'description': description,
                    'invite_only': invite_only,
                    'max_slots': max_slots,
                    'starter_location': location,
                    'capability_codes': [],
                },
            )

        claimable = RoleTemplate.objects.filter(world=world, invite_only=False).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} earth-2097 "
                f"({claimable} claimable roles)."
            )
        )
