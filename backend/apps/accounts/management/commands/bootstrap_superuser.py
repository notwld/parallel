from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Create or update a staff superuser from DJANGO_SUPERUSER_* env vars.'

    def handle(self, *args, **options):
        import os

        username = (os.environ.get('DJANGO_SUPERUSER_USERNAME') or '').strip()
        email = (os.environ.get('DJANGO_SUPERUSER_EMAIL') or '').strip().lower()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD') or ''
        if not username or not email or not password:
            raise CommandError(
                'Set DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, and '
                'DJANGO_SUPERUSER_PASSWORD in the environment.'
            )

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        created = user is None
        if created:
            # Bypass password validators for local bootstrap; operator chose the password.
            user = User(username=username, email=email)
            user.set_password(password)
        else:
            user.email = email
            user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        if user.email_verified_at is None:
            user.email_verified_at = timezone.now()
        user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} superuser {username} <{email}>"
            )
        )
