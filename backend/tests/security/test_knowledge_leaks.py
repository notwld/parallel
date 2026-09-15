import json
import uuid
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.characters.models import Character
from apps.knowledge.models import Claim, ClaimEvidenceLink, KnowledgeEdge
from apps.knowledge.services import (
    create_claim,
    create_evidence,
    create_fact,
    link_evidence,
    upsert_knowledge_edge,
)
from apps.worlds.models import RoleTemplate, World, WorldMembership

User = get_user_model()

CANARY = 'CANARY_SECRET_OBJECT_X_EMIT_9_4_KHZ'
CANARY_SOURCE_REF = 'message:m_secret_chen_only'


def _dump(obj) -> str:
    return json.dumps(obj, default=str)


class KnowledgeLeakSuite(TestCase):
    """Character A knows a canary; B and foreign-world must not recover it."""

    def setUp(self):
        self.world = World.objects.create(
            slug='leak-world',
            title='Leak',
            premise='Secrets.',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )
        self.other_world = World.objects.create(
            slug='foreign-world',
            title='Foreign',
            premise='Elsewhere.',
            status=World.Status.LIVE,
            visibility=World.Visibility.PUBLIC,
            world_time=datetime(2097, 1, 1, tzinfo=timezone.utc),
        )
        self.role = RoleTemplate.objects.create(world=self.world, name='Citizen')
        self.other_role = RoleTemplate.objects.create(world=self.other_world, name='X')
        self.user_a = User.objects.create_user('alice', email='a@example.com', password='x')
        self.user_b = User.objects.create_user('bob', email='b@example.com', password='x')
        self.user_f = User.objects.create_user('foreign', email='f@example.com', password='x')
        for u in (self.user_a, self.user_b):
            WorldMembership.objects.create(world=self.world, account=u)
        WorldMembership.objects.create(world=self.other_world, account=self.user_f)
        self.char_a = Character.objects.create(
            world=self.world, account=self.user_a, role_template=self.role, display_name='Alice'
        )
        self.char_b = Character.objects.create(
            world=self.world, account=self.user_b, role_template=self.role, display_name='Bob'
        )
        self.char_f = Character.objects.create(
            world=self.other_world,
            account=self.user_f,
            role_template=self.other_role,
            display_name='Foreign',
        )

        self.fact = create_fact(
            world=self.world,
            fact_type='signal',
            subject_ref='object:x',
            predicate='emits',
            value_json={'hz': 9400, 'canary': CANARY},
            idempotency_key='leak-fact',
        )
        self.claim = create_claim(
            world=self.world,
            normalized_proposition=CANARY,
            origin_type=Claim.OriginType.DIRECT_OBSERVATION,
            linked_fact=self.fact,
            idempotency_key='leak-claim',
        )
        self.evidence = create_evidence(
            world=self.world,
            owner_character=self.char_a,
            media_type='application/json',
            metadata_json={'note': CANARY},
            integrity_hash='deadbeef',
            idempotency_key='leak-ev',
        )
        link_evidence(
            claim=self.claim,
            evidence=self.evidence,
            relation=ClaimEvidenceLink.Relation.SUPPORTS,
        )
        upsert_knowledge_edge(
            world=self.world,
            claim=self.claim,
            owner_character=self.char_a,
            stance=KnowledgeEdge.Stance.ACCEPTS,
            confidence='0.95',
            source_type=KnowledgeEdge.SourceType.MESSAGE,
            source_ref=CANARY_SOURCE_REF,
            shareability=KnowledgeEdge.Shareability.CONFIDENTIAL,
            idempotency_key='leak-edge-a',
        )

        self.client_a = APIClient()
        self.client_a.force_authenticate(self.user_a)
        self.client_b = APIClient()
        self.client_b.force_authenticate(self.user_b)
        self.client_f = APIClient()
        self.client_f.force_authenticate(self.user_f)

    def _assert_clean(self, payload):
        text = _dump(payload)
        self.assertNotIn(CANARY, text)
        self.assertNotIn(CANARY_SOURCE_REF, text)
        self.assertNotIn(str(self.fact.id), text)
        self.assertNotIn('linked_fact', text)
        self.assertNotIn('fact_id', text)
        self.assertNotIn('is_true', text)
        self.assertNotIn('system_confidence', text)

    def test_owner_sees_claim_without_truth_metadata(self):
        r = self.client_a.get(f'/api/v1/knowledge/worlds/leak-world/intel/claims/{self.claim.id}/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['proposition'], CANARY)
        self.assertNotIn('linked_fact', body)
        self.assertNotIn('fact_id', body)
        self.assertNotIn(str(self.fact.id), _dump(body))
        self.assertEqual(body['sources'][0]['display'], 'Confidential source')
        self.assertNotIn('ref', body['sources'][0])
        self.assertEqual(body['evidence'], [str(self.evidence.id)])

    def test_peer_list_detail_search_hide_canary(self):
        list_r = self.client_b.get('/api/v1/knowledge/worlds/leak-world/intel/claims/')
        self.assertEqual(list_r.status_code, 200)
        self._assert_clean(list_r.json())
        self.assertEqual(list_r.json()['results'], [])

        detail_r = self.client_b.get(
            f'/api/v1/knowledge/worlds/leak-world/intel/claims/{self.claim.id}/'
        )
        self.assertEqual(detail_r.status_code, 404)
        self._assert_clean(detail_r.json())

        missing = self.client_b.get(
            f'/api/v1/knowledge/worlds/leak-world/intel/claims/{uuid.uuid4()}/'
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(detail_r.json(), missing.json())

        search_r = self.client_b.get(
            '/api/v1/knowledge/worlds/leak-world/intel/claims/', {'q': CANARY}
        )
        self.assertEqual(search_r.status_code, 200)
        self.assertEqual(search_r.json()['results'], [])
        self._assert_clean(search_r.json())

        ev_r = self.client_b.get(
            f'/api/v1/knowledge/worlds/leak-world/intel/evidence/{self.evidence.id}/'
        )
        self.assertEqual(ev_r.status_code, 404)
        self._assert_clean(ev_r.json())

    def test_foreign_world_character_denied(self):
        r = self.client_f.get(f'/api/v1/knowledge/worlds/leak-world/intel/claims/{self.claim.id}/')
        self.assertEqual(r.status_code, 404)
        self._assert_clean(r.json())
        list_r = self.client_f.get('/api/v1/knowledge/worlds/leak-world/intel/claims/')
        self.assertEqual(list_r.status_code, 404)
        self._assert_clean(list_r.json())

    def test_revoked_access_denied(self):
        KnowledgeEdge.objects.filter(owner_character=self.char_a, claim=self.claim).delete()
        r = self.client_a.get(f'/api/v1/knowledge/worlds/leak-world/intel/claims/{self.claim.id}/')
        self.assertEqual(r.status_code, 404)
        self._assert_clean(r.json())
        list_r = self.client_a.get('/api/v1/knowledge/worlds/leak-world/intel/claims/')
        self.assertEqual(list_r.json()['results'], [])
