import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    preferences = models.JSONField(default=dict, blank=True)


class AccountToken(models.Model):
    class Purpose(models.TextChoices):
        EMAIL_VERIFY = 'email_verify'
        PASSWORD_RESET = 'password_reset'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tokens')
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def issue(cls, account, purpose: str, ttl_hours: int = 24) -> str:
        raw = secrets.token_urlsafe(32)
        cls.objects.create(
            account=account,
            purpose=purpose,
            token_hash=cls.hash_token(raw),
            expires_at=timezone.now() + timedelta(hours=ttl_hours),
        )
        return raw

    @classmethod
    def consume(cls, raw: str, purpose: str):
        token = (
            cls.objects.select_related('account')
            .filter(token_hash=cls.hash_token(raw), purpose=purpose, used_at__isnull=True)
            .first()
        )
        if token is None or token.expires_at < timezone.now():
            return None
        token.used_at = timezone.now()
        token.save(update_fields=['used_at'])
        return token


class AccountSession(models.Model):
    """Tracks Django session keys for listing/revocation. Deletion-safe via CASCADE on account."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='account_sessions'
    )
    session_key = models.CharField(max_length=40, unique=True)
    user_agent = models.CharField(max_length=256, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
