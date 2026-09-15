import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase

from apps.audit.models import AuditRecord
from apps.audit.policies import list_audit_for_world
from apps.events.models import OutboxEvent
from apps.events.services import IdempotencyConflict, mark_outbox_delivered, record_world_mutation
from apps.worlds.models import World

User = get_user_model()


class EventAtomicityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('auditor', password='test-only-password')
        self.staff = User.objects.create_user(
            'staff', password='test-only-password', is_staff=True
        )
        self.world = World.objects.create(
            slug='earth-2097',
            title='Earth-2097',
            premise='A city appears in the Atlantic.',
            status=World.Status.LIVE,
            visibility=World.Visibility.INVITE_ONLY,
            created_by=self.user,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )

    def test_rollback_leaves_neither_state_nor_outbox_nor_audit(self):
        before_title = self.world.title

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                record_world_mutation(
                    world=self.world,
                    event_type='world.title_changed',
                    idempotency_key='title-1',
                    payload={'title': 'Broken'},
                    actor_type='account',
                    actor_id=self.user.id,
                    actor_label=self.user.username,
                    mutate=lambda: World.objects.filter(pk=self.world.pk).update(title='Broken'),
                )
                raise RuntimeError('forced rollback')

        self.world.refresh_from_db()
        self.assertEqual(self.world.title, before_title)
        self.assertEqual(AuditRecord.objects.count(), 0)
        self.assertEqual(OutboxEvent.objects.count(), 0)

    def test_duplicate_idempotency_key_same_payload_returns_original(self):
        audit1, outbox1 = record_world_mutation(
            world=self.world,
            event_type='demo.ping',
            idempotency_key='ping-1',
            payload={'n': 1},
            actor_type='system',
            actor_label='system',
        )
        audit2, outbox2 = record_world_mutation(
            world=self.world,
            event_type='demo.ping',
            idempotency_key='ping-1',
            payload={'n': 1},
            actor_type='system',
            actor_label='system',
        )
        self.assertEqual(audit1.pk, audit2.pk)
        self.assertEqual(outbox1.pk, outbox2.pk)
        self.assertEqual(AuditRecord.objects.count(), 1)
        self.assertEqual(OutboxEvent.objects.count(), 1)

    def test_duplicate_idempotency_key_different_payload_conflicts(self):
        record_world_mutation(
            world=self.world,
            event_type='demo.ping',
            idempotency_key='ping-2',
            payload={'n': 1},
        )
        with self.assertRaises(IdempotencyConflict):
            record_world_mutation(
                world=self.world,
                event_type='demo.ping',
                idempotency_key='ping-2',
                payload={'n': 2},
            )
        self.assertEqual(OutboxEvent.objects.count(), 1)

    def test_ordinary_paths_cannot_edit_or_delete_history(self):
        audit, outbox = record_world_mutation(
            world=self.world,
            event_type='demo.ping',
            idempotency_key='ping-3',
            payload={'ok': True},
        )
        audit.payload = {'tampered': True}
        with self.assertRaises(PermissionDenied):
            audit.save()
        with self.assertRaises(PermissionDenied):
            audit.delete()
        with self.assertRaises(PermissionDenied):
            AuditRecord.objects.filter(pk=audit.pk).update(payload={'x': 1})
        with self.assertRaises(PermissionDenied):
            AuditRecord.objects.filter(pk=audit.pk).delete()

        outbox.payload = {'tampered': True}
        with self.assertRaises(PermissionDenied):
            outbox.save()
        with self.assertRaises(PermissionDenied):
            outbox.delete()
        with self.assertRaises(PermissionDenied):
            OutboxEvent.objects.filter(pk=outbox.pk).update(payload={'x': 1})

        delivered = mark_outbox_delivered(outbox)
        self.assertEqual(delivered.delivery_state, OutboxEvent.DeliveryState.DELIVERED)
        self.assertIsNotNone(delivered.delivered_at)

    def test_audit_reads_require_privileged_policy(self):
        record_world_mutation(
            world=self.world,
            event_type='demo.ping',
            idempotency_key='ping-4',
            payload={'ok': True},
        )
        with self.assertRaises(PermissionDenied):
            list_audit_for_world(self.user, self.world)
        with self.assertRaises(PermissionDenied):
            list_audit_for_world(None, self.world)
        rows = list(list_audit_for_world(self.staff, self.world))
        self.assertEqual(len(rows), 1)

    def test_actor_refs_are_deletion_safe(self):
        account_id = self.user.id
        record_world_mutation(
            world=self.world,
            event_type='demo.ping',
            idempotency_key='ping-5',
            payload={'ok': True},
            actor_type='account',
            actor_id=account_id,
            actor_label=self.user.username,
        )
        self.user.delete()
        audit = AuditRecord.objects.get()
        self.assertEqual(audit.actor_id, account_id)
        self.assertEqual(audit.actor_label, 'auditor')
        self.assertEqual(OutboxEvent.objects.count(), 1)

    def test_mutation_and_outbox_commit_together(self):
        record_world_mutation(
            world=self.world,
            event_type='world.title_changed',
            idempotency_key='title-ok',
            payload={'title': 'Renamed'},
            mutate=lambda: World.objects.filter(pk=self.world.pk).update(title='Renamed'),
        )
        self.world.refresh_from_db()
        self.assertEqual(self.world.title, 'Renamed')
        self.assertEqual(AuditRecord.objects.count(), 1)
        self.assertEqual(OutboxEvent.objects.get().sequence, 1)


class ConcurrentSequenceTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user('seq', password='test-only-password')
        self.world = World.objects.create(
            slug='seq-world',
            title='Seq',
            premise='Concurrency.',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            created_by=self.user,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )

    def test_sequence_allocation_safe_under_concurrent_transactions(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL required for concurrent sequence allocation')

        barrier = threading.Barrier(8)
        errors: list[BaseException] = []

        def worker(i: int):
            try:
                barrier.wait(timeout=10)
                record_world_mutation(
                    world=self.world,
                    event_type='demo.concurrent',
                    idempotency_key=f'c-{i}-{uuid.uuid4()}',
                    payload={'i': i},
                )
            except BaseException as exc:  # noqa: BLE001 — collect for assertion
                errors.append(exc)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(worker, range(8)))

        self.assertEqual(errors, [])
        sequences = list(
            OutboxEvent.objects.filter(world=self.world)
            .order_by('sequence')
            .values_list('sequence', flat=True)
        )
        self.assertEqual(sequences, list(range(1, 9)))
        self.assertEqual(AuditRecord.objects.filter(world=self.world).count(), 8)
