from datetime import datetime, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.characters.models import Character
from apps.knowledge.models import Claim, ClaimEvidenceLink, Evidence, Fact, KnowledgeEdge, Transmission
from apps.knowledge.services import (
    KnowledgeError,
    create_claim,
    create_evidence,
    create_fact,
    link_evidence,
    mutate_claim,
    ordinary_claim_read,
    upsert_knowledge_edge,
)
from apps.organizations.services import add_member, create_organization
from apps.worlds.models import RoleTemplate, World, WorldMembership

User = get_user_model()


class KnowledgeModelTests(TestCase):
    def setUp(self):
        self.world = World.objects.create(
            slug='know-world',
            title='Know',
            premise='Epistemic.',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )
        self.other = World.objects.create(
            slug='other-know',
            title='Other',
            premise='x',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )
        self.role = RoleTemplate.objects.create(world=self.world, name='Citizen')
        other_role = RoleTemplate.objects.create(world=self.other, name='X')
        self.user = User.objects.create_user('k', email='k@example.com', password='x')
        WorldMembership.objects.create(world=self.world, account=self.user)
        WorldMembership.objects.create(world=self.other, account=self.user)
        self.chen = Character.objects.create(
            world=self.world, account=self.user, role_template=self.role, display_name='Chen'
        )
        self.foreign = Character.objects.create(
            world=self.other, account=self.user, role_template=other_role, display_name='Foreign'
        )
        self.org = create_organization(world=self.world, name='Lab', slug='lab')

    def test_competing_false_claims_persist_without_truth_in_ordinary_read(self):
        fact = create_fact(
            world=self.world,
            fact_type='casualty',
            subject_ref='event:e-883',
            predicate='death_count',
            value_json={'count': 3},
            idempotency_key='fact-1',
        )
        trueish = create_claim(
            world=self.world,
            normalized_proposition='Three researchers died during transport.',
            origin_type=Claim.OriginType.DIRECT_OBSERVATION,
            linked_fact=fact,
            idempotency_key='claim-true',
        )
        false_rumor = create_claim(
            world=self.world,
            normalized_proposition='Nobody died; it was a drill.',
            origin_type=Claim.OriginType.RUMOR,
            idempotency_key='claim-false',
        )
        self.assertEqual(Claim.objects.filter(world=self.world).count(), 2)
        for claim in (trueish, false_rumor):
            body = ordinary_claim_read(claim)
            self.assertNotIn('linked_fact', body)
            self.assertNotIn('fact_id', body)
            self.assertNotIn('is_true', body)
            self.assertNotIn('truth', body)

    def test_mutate_preserves_source_via_transmission(self):
        source = create_claim(
            world=self.world,
            normalized_proposition='At least two are dead.',
            origin_type=Claim.OriginType.DIRECT_OBSERVATION,
            idempotency_key='src',
        )
        derived, tx = mutate_claim(
            source_claim=source,
            new_proposition='Sources say multiple researchers died.',
            from_ref=f'character:{self.chen.id}',
            to_ref='audience:public',
            channel=Transmission.Channel.POST,
            idempotency_key='mutate-1',
        )
        source.refresh_from_db()
        self.assertEqual(source.normalized_proposition, 'At least two are dead.')
        self.assertEqual(derived.origin_type, Claim.OriginType.MUTATION)
        self.assertEqual(derived.origin_ref, str(source.id))
        self.assertEqual(tx.source_claim_id, source.id)
        self.assertEqual(tx.resulting_claim_id, derived.id)

    def test_knowledge_edge_xor_owner_and_confidence(self):
        claim = create_claim(
            world=self.world,
            normalized_proposition='Signal is intentional.',
            origin_type=Claim.OriginType.INFERENCE,
            idempotency_key='edge-claim',
        )
        edge = upsert_knowledge_edge(
            world=self.world,
            claim=claim,
            owner_character=self.chen,
            stance=KnowledgeEdge.Stance.ACCEPTS,
            confidence='0.82',
            source_type=KnowledgeEdge.SourceType.DIRECT_OBSERVATION,
            idempotency_key='edge-1',
        )
        self.assertEqual(edge.confidence, Decimal('0.820'))
        with self.assertRaises(KnowledgeError):
            upsert_knowledge_edge(
                world=self.world,
                claim=claim,
                owner_character=self.chen,
                stance=KnowledgeEdge.Stance.ACCEPTS,
                confidence='1.5',
                source_type=KnowledgeEdge.SourceType.RUMOR,
                idempotency_key='edge-bad-conf',
            )
        with self.assertRaises(KnowledgeError):
            upsert_knowledge_edge(
                world=self.world,
                claim=claim,
                stance=KnowledgeEdge.Stance.ACCEPTS,
                confidence='0.5',
                source_type=KnowledgeEdge.SourceType.RUMOR,
                idempotency_key='edge-no-owner',
            )
        with self.assertRaises(KnowledgeError):
            upsert_knowledge_edge(
                world=self.world,
                claim=claim,
                owner_character=self.chen,
                owner_organization=self.org,
                stance=KnowledgeEdge.Stance.ACCEPTS,
                confidence='0.5',
                source_type=KnowledgeEdge.SourceType.RUMOR,
                idempotency_key='edge-both',
            )

    def test_cross_world_rejected(self):
        claim = create_claim(
            world=self.world,
            normalized_proposition='Local secret.',
            origin_type=Claim.OriginType.SYSTEM,
            idempotency_key='xw-claim',
        )
        with self.assertRaises(KnowledgeError):
            upsert_knowledge_edge(
                world=self.world,
                claim=claim,
                owner_character=self.foreign,
                stance=KnowledgeEdge.Stance.SUSPECTS,
                confidence='0.4',
                source_type=KnowledgeEdge.SourceType.RUMOR,
                idempotency_key='xw-edge',
            )
        foreign_claim = create_claim(
            world=self.other,
            normalized_proposition='Other world claim.',
            origin_type=Claim.OriginType.SYSTEM,
            idempotency_key='other-claim',
        )
        with self.assertRaises(KnowledgeError):
            upsert_knowledge_edge(
                world=self.world,
                claim=foreign_claim,
                owner_character=self.chen,
                stance=KnowledgeEdge.Stance.UNCERTAIN,
                confidence='0.1',
                source_type=KnowledgeEdge.SourceType.RUMOR,
                idempotency_key='xw-claim-world',
            )

    def test_evidence_relations_and_world_check(self):
        claim = create_claim(
            world=self.world,
            normalized_proposition='Object emits 9.4 kHz.',
            origin_type=Claim.OriginType.DOCUMENT,
            idempotency_key='ev-claim',
        )
        evidence = create_evidence(
            world=self.world,
            owner_character=self.chen,
            media_type='image/png',
            metadata_json={'label': 'spectrogram'},
            integrity_hash='abc',
            idempotency_key='ev-1',
        )
        link = link_evidence(
            claim=claim,
            evidence=evidence,
            relation=ClaimEvidenceLink.Relation.SUPPORTS,
            assessment='matches frequency',
        )
        self.assertEqual(link.relation, ClaimEvidenceLink.Relation.SUPPORTS)
        other_ev = create_evidence(
            world=self.other,
            owner_character=self.foreign,
            idempotency_key='ev-other',
        )
        with self.assertRaises(KnowledgeError):
            link_evidence(
                claim=claim,
                evidence=other_ev,
                relation=ClaimEvidenceLink.Relation.CONTRADICTS,
            )

    def test_fact_has_no_public_serializer_module(self):
        import importlib.util

        spec = importlib.util.find_spec('apps.knowledge.serializers')
        self.assertIsNone(spec)
        self.assertTrue(hasattr(Fact, '_meta'))

    def test_indexes_cover_owner_world_time(self):
        ke_names = {idx.name for idx in KnowledgeEdge._meta.indexes}
        self.assertIn('ke_owner_char_acquired', ke_names)
        self.assertIn('ke_world_verification', ke_names)
        claim_names = {idx.name for idx in Claim._meta.indexes}
        self.assertIn('claim_world_created', claim_names)
        fact_names = {idx.name for idx in Fact._meta.indexes}
        self.assertIn('fact_world_valid_from', fact_names)
