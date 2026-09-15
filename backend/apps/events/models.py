import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.db.models import Q

from apps.worlds.models import World

_DELIVERY_FIELDS = frozenset({'delivery_state', 'delivered_at', 'attempt_count'})


class OutboxQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if kwargs and set(kwargs) <= _DELIVERY_FIELDS:
            return super().update(**kwargs)
        raise PermissionDenied('Outbox payload fields are immutable.')

    def delete(self):
        raise PermissionDenied('Outbox events cannot be deleted.')


class WorldSequence(models.Model):
    """Per-world monotonic counter; allocate with select_for_update inside a transaction."""

    world = models.OneToOneField(World, on_delete=models.CASCADE, primary_key=True, related_name='sequence')
    next_value = models.PositiveBigIntegerField(default=1)


class OutboxEvent(models.Model):
    class DeliveryState(models.TextChoices):
        PENDING = 'pending'
        DELIVERED = 'delivered'
        FAILED = 'failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.PROTECT, related_name='outbox_events')
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
    delivery_state = models.CharField(
        max_length=16, choices=DeliveryState.choices, default=DeliveryState.PENDING
    )
    delivered_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    audit_record = models.OneToOneField(
        'audit.AuditRecord',
        on_delete=models.PROTECT,
        related_name='outbox_event',
    )

    objects = OutboxQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['world', 'idempotency_key'],
                name='outbox_idempotency_per_world',
            ),
            models.UniqueConstraint(
                fields=['world', 'sequence'],
                name='outbox_sequence_per_world',
            ),
            models.CheckConstraint(
                condition=Q(delivery_state__in=['pending', 'delivered', 'failed']),
                name='outbox_delivery_state_valid',
            ),
        ]
        indexes = [
            models.Index(
                fields=['created_at'],
                name='outbox_pending_created_idx',
                condition=Q(delivery_state='pending'),
            ),
            models.Index(fields=['world', 'created_at'], name='outbox_world_created_idx'),
        ]

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.full_clean()
            return super().save(*args, **kwargs)
        update_fields = kwargs.get('update_fields')
        if update_fields and set(update_fields) <= _DELIVERY_FIELDS:
            return super().save(*args, **kwargs)
        raise PermissionDenied('Outbox payload fields are immutable.')

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Outbox events cannot be deleted.')

    def clean(self):
        super().clean()
        if self.audit_record_id and self.audit_record.world_id != self.world_id:
            raise ValidationError({'audit_record': 'Audit record must belong to the same world.'})
