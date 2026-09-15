import hashlib
import json
from typing import Any, Callable

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditRecord
from apps.events.models import OutboxEvent, WorldSequence
from apps.worlds.models import World


def payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _lock_world_sequence(world: World) -> WorldSequence:
    seq, _ = WorldSequence.objects.select_for_update().get_or_create(
        world=world, defaults={'next_value': 1}
    )
    return seq


def allocate_world_sequence(world: World) -> int:
    """Return the next sequence for world. Must run inside transaction.atomic()."""
    seq = _lock_world_sequence(world)
    value = seq.next_value
    seq.next_value = value + 1
    seq.save(update_fields=['next_value'])
    return value


class IdempotencyConflict(ValidationError):
    """Same scoped key with a different payload hash."""


def _existing_outbox(world: World, idempotency_key: str, digest: str) -> tuple[AuditRecord, OutboxEvent] | None:
    existing = (
        OutboxEvent.objects.select_related('audit_record')
        .filter(world=world, idempotency_key=idempotency_key)
        .first()
    )
    if existing is None:
        return None
    if existing.payload_hash != digest:
        raise IdempotencyConflict(
            'Idempotency key reused with a different payload.',
            code='idempotency_conflict',
        )
    return existing.audit_record, existing


@transaction.atomic
def record_world_mutation(
    *,
    world: World,
    event_type: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
    actor_type: str = 'system',
    actor_id=None,
    actor_label: str = '',
    cause_type: str = '',
    cause_ref=None,
    mutate: Callable[[], Any] | None = None,
) -> tuple[AuditRecord, OutboxEvent]:
    """
    Atomically run optional business mutate(), then append audit + outbox.
    Duplicate (world, idempotency_key) with the same payload returns the originals.
    Per-world sequence row is locked so concurrent writers serialize.
    """
    payload = payload or {}
    digest = payload_hash(payload)

    hit = _existing_outbox(world, idempotency_key, digest)
    if hit is not None:
        return hit

    # Serialize world writers: second concurrent same-key waits, then hits existing.
    seq = _lock_world_sequence(world)
    hit = _existing_outbox(world, idempotency_key, digest)
    if hit is not None:
        return hit

    if mutate is not None:
        mutate()

    sequence = seq.next_value
    seq.next_value = sequence + 1
    seq.save(update_fields=['next_value'])

    audit = AuditRecord(
        world=world,
        sequence=sequence,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_label=actor_label,
        cause_type=cause_type,
        cause_ref=cause_ref,
        payload=payload,
        payload_hash=digest,
        idempotency_key=idempotency_key,
    )
    audit.save()
    outbox = OutboxEvent(
        world=world,
        sequence=sequence,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_label=actor_label,
        cause_type=cause_type,
        cause_ref=cause_ref,
        payload=payload,
        payload_hash=digest,
        idempotency_key=idempotency_key,
        audit_record=audit,
    )
    outbox.save()
    return audit, outbox


@transaction.atomic
def mark_outbox_delivered(outbox: OutboxEvent) -> OutboxEvent:
    locked = OutboxEvent.objects.select_for_update().get(pk=outbox.pk)
    locked.delivery_state = OutboxEvent.DeliveryState.DELIVERED
    locked.delivered_at = timezone.now()
    locked.attempt_count = locked.attempt_count + 1
    locked.save(update_fields=['delivery_state', 'delivered_at', 'attempt_count'])
    return locked
