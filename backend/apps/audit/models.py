import uuid

from django.core.exceptions import PermissionDenied
from django.db import models

from apps.worlds.models import World


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Audit records are append-only.')

    def delete(self):
        raise PermissionDenied('Audit records are append-only.')


class AuditRecord(models.Model):
    """Immutable world-scoped change record. Actor refs survive account deletion."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.PROTECT, related_name='audit_records')
    sequence = models.PositiveBigIntegerField()
    event_type = models.CharField(max_length=128)
    actor_type = models.CharField(max_length=32)
    actor_id = models.UUIDField(null=True, blank=True)
    actor_label = models.CharField(max_length=200, blank=True)
    cause_type = models.CharField(max_length=64, blank=True)
    cause_ref = models.UUIDField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    payload_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['world', 'idempotency_key'],
                name='audit_idempotency_per_world',
            ),
            models.UniqueConstraint(
                fields=['world', 'sequence'],
                name='audit_sequence_per_world',
            ),
        ]
        indexes = [
            models.Index(fields=['world', 'created_at'], name='audit_world_created_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied('Audit records are append-only.')
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Audit records are append-only.')
