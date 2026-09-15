"""P008 sharing / transmission / verification — write failing tests first."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.characters.models import Character
from apps.events.models import OutboxEvent
from apps.knowledge.models import Claim, ClaimEvidenceLink, KnowledgeEdge, Transmission
from apps.knowledge.services import (
    KnowledgeError,
    create_claim,
    create_evidence,
    link_evidence,
    share_claim,
    submit_verification_assessment,
    upsert_knowledge_edge,
)
from apps.worlds.models import RoleTemplate, World, WorldMembership

User = get_user_model()


class TransmissionShareTests(TestCase):
    def setUp(self):
        self.world = World.objects.create(
            slug='share-world',
            title='Share',
            premise='Rumors.',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )
        self.role = RoleTemplate.objects.create(world=self.world, name='Citizen')
        self.alice_user = User.objects.create_user('alice', email='a@ex.com', password='x')
        self.bob_user = User.objects.create_user('bob', email='b@ex.com', password='x')
        self.carol_user = User.objects.create_user('carol', email='c@ex.com', password='x')
        for u in (self.alice_user, self.bob_user, self.carol_user):
            WorldMembership.objects.create(world=self.world, account=u)
        self.alice = Character.objects.create(
            world=self.world, account=self.alice_user, role_template=self.role, display_name='Alice'
        )
        self.bob = Character.objects.create(
            world=self.world, account=self.bob_user, role_template=self.role, display_name='Bob'
        )
        self.carol = Character.objects.create(
            world=self.world, account=self.carol_user, role_template=self.role, display_name='Carol'
        )
        self.claim = create_claim(
            world=self.world,
            normalized_proposition='Object X emits a 9.4 kHz tone.',
            origin_type=Claim.OriginType.DIRECT_OBSERVATION,
            idempotency_key='share-claim',
        )
        self.evidence = create_evidence(
            world=self.world,
            owner_character=self.alice,
            media_type='text/plain',
            metadata_json={'note': 'spectrogram'},
            idempotency_key='share-ev',
        )
        link_evidence(
            claim=self.claim,
            evidence=self.evidence,
            relation=ClaimEvidenceLink.Relation.SUPPORTS,
        )

    def _edge(self, character, *, shareability, key, source_ref='msg:1'):
        return upsert_knowledge_edge(
            world=self.world,
            claim=self.claim,
            owner_character=character,
            stance=KnowledgeEdge.Stance.ACCEPTS,
            confidence='0.90',
            source_type=KnowledgeEdge.SourceType.MESSAGE,
            source_ref=source_ref,
            shareability=shareability,
            idempotency_key=key,
        )

    def test_shareable_grants_recipient_edge_and_transmission(self):
        self._edge(self.alice, shareability=KnowledgeEdge.Shareability.SHAREABLE, key='e-a')
        result = share_claim(
            sender=self.alice,
            recipient=self.bob,
            claim=self.claim,
            evidence_ids=[self.evidence.id],
            idempotency_key='share-1',
        )
        self.assertEqual(result.transmission.from_ref, f'character:{self.alice.id}')
        self.assertEqual(result.transmission.to_ref, f'character:{self.bob.id}')
        self.assertEqual(result.transmission.source_claim_id, self.claim.id)
        bob_edge = KnowledgeEdge.objects.get(owner_character=self.bob, claim=self.claim)
        self.assertEqual(bob_edge.awareness, KnowledgeEdge.Awareness.AWARE)
        self.assertEqual(bob_edge.source_type, KnowledgeEdge.SourceType.MESSAGE)
        self.evidence.refresh_from_db()
        self.assertEqual(self.evidence.visibility, 'shared')
        # Lineage reconstructable for staff via Transmission rows.
        self.assertEqual(Transmission.objects.filter(world=self.world).count(), 1)

    def test_private_redistribution_rejected(self):
        self._edge(self.alice, shareability=KnowledgeEdge.Shareability.PRIVATE, key='e-priv')
        with self.assertRaises(KnowledgeError) as ctx:
            share_claim(
                sender=self.alice,
                recipient=self.bob,
                claim=self.claim,
                idempotency_key='share-priv',
            )
        self.assertEqual(ctx.exception.rejection_code, 'not_shareable')
        self.assertFalse(KnowledgeEdge.objects.filter(owner_character=self.bob).exists())

    def test_idempotent_share_does_not_duplicate_transmission(self):
        self._edge(self.alice, shareability=KnowledgeEdge.Shareability.SHAREABLE, key='e-id')
        a = share_claim(
            sender=self.alice,
            recipient=self.bob,
            claim=self.claim,
            idempotency_key='share-idem',
        )
        b = share_claim(
            sender=self.alice,
            recipient=self.bob,
            claim=self.claim,
            idempotency_key='share-idem',
        )
        self.assertEqual(a.transmission.id, b.transmission.id)
        self.assertEqual(Transmission.objects.filter(world=self.world).count(), 1)
        self.assertEqual(
            OutboxEvent.objects.filter(world=self.world, idempotency_key='share-idem').count(),
            1,
        )

    def test_weaker_derived_claim_preserves_original(self):
        self._edge(self.alice, shareability=KnowledgeEdge.Shareability.PUBLIC, key='e-mut')
        original = self.claim.normalized_proposition
        result = share_claim(
            sender=self.alice,
            recipient=self.bob,
            claim=self.claim,
            derived_proposition='Sources say Object X makes a weird noise.',
            idempotency_key='share-mut',
        )
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.normalized_proposition, original)
        self.assertNotEqual(result.resulting_claim.id, self.claim.id)
        self.assertEqual(
            result.resulting_claim.normalized_proposition,
            'Sources say Object X makes a weird noise.',
        )
        self.assertFalse(
            KnowledgeEdge.objects.filter(owner_character=self.bob, claim=self.claim).exists()
        )
        self.assertTrue(
            KnowledgeEdge.objects.filter(
                owner_character=self.bob, claim=result.resulting_claim
            ).exists()
        )

    def test_confidential_share_hides_source_identity_from_recipient_projection(self):
        from apps.knowledge.selectors import project_claim_for_character

        self._edge(
            self.alice,
            shareability=KnowledgeEdge.Shareability.CONFIDENTIAL,
            key='e-conf',
            source_ref='message:secret_chen',
        )
        share_claim(
            sender=self.alice,
            recipient=self.bob,
            claim=self.claim,
            idempotency_key='share-conf',
        )
        body = project_claim_for_character(self.claim, self.bob)
        self.assertIsNotNone(body)
        self.assertEqual(body['sources'][0]['display'], 'Confidential source')
        self.assertNotIn('ref', body['sources'][0])
        self.assertNotIn('secret_chen', str(body))

    def test_recipient_cannot_see_unshared_evidence(self):
        from apps.knowledge import policies

        self._edge(self.alice, shareability=KnowledgeEdge.Shareability.SHAREABLE, key='e-ev')
        share_claim(
            sender=self.alice,
            recipient=self.bob,
            claim=self.claim,
            evidence_ids=[],  # claim only
            idempotency_key='share-no-ev',
        )
        self.assertFalse(policies.can_access_evidence(self.bob, self.evidence))

    def test_verification_does_not_copy_canonical_truth(self):
        from apps.knowledge.services import create_fact

        fact = create_fact(
            world=self.world,
            fact_type='signal',
            subject_ref='object:x',
            predicate='emits',
            value_json={'hz': 9400},
            idempotency_key='fact-v',
        )
        claim = create_claim(
            world=self.world,
            normalized_proposition='Tone is real.',
            origin_type=Claim.OriginType.INFERENCE,
            linked_fact=fact,
            idempotency_key='claim-v',
        )
        upsert_knowledge_edge(
            world=self.world,
            claim=claim,
            owner_character=self.alice,
            stance=KnowledgeEdge.Stance.SUSPECTS,
            confidence='0.5',
            source_type=KnowledgeEdge.SourceType.INFERENCE,
            shareability=KnowledgeEdge.Shareability.SHAREABLE,
            idempotency_key='e-v',
        )
        edge = submit_verification_assessment(
            character=self.alice,
            claim=claim,
            verification=KnowledgeEdge.Verification.CORROBORATED,
            notes='Lab matched the spectrogram.',
            idempotency_key='verify-1',
        )
        self.assertEqual(edge.verification, KnowledgeEdge.Verification.CORROBORATED)
        fact.refresh_from_db()
        self.assertEqual(fact.system_status, 'active')
        outbox = OutboxEvent.objects.get(idempotency_key='verify-1')
        self.assertNotIn('fact_id', outbox.payload)
        self.assertNotIn(str(fact.id), str(outbox.payload))
        self.assertEqual(outbox.payload.get('verification'), 'corroborated')

    def test_share_api_and_unauthorized(self):
        self._edge(self.alice, shareability=KnowledgeEdge.Shareability.SHAREABLE, key='e-api')
        client = APIClient()
        client.force_authenticate(self.alice_user)
        res = client.post(
            f'/api/v1/knowledge/worlds/{self.world.slug}/intel/claims/{self.claim.id}/share/',
            {
                'recipient_character_id': str(self.bob.id),
                'evidence_ids': [str(self.evidence.id)],
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(res.status_code, 201, res.content)
        self.assertIn('transmission_id', res.json())

        # Bob without knowledge trying to reshare → 404 identical unavailable
        client.force_authenticate(self.bob_user)
        # Give bob private edge somehow? Bob now has shareable from alice share.
        # Carol has nothing — share attempt is unavailable
        client.force_authenticate(self.carol_user)
        denied = client.post(
            f'/api/v1/knowledge/worlds/{self.world.slug}/intel/claims/{self.claim.id}/share/',
            {'recipient_character_id': str(self.alice.id)},
            format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(denied.status_code, 404)
        self.assertEqual(denied.json()['code'], 'not_found')
