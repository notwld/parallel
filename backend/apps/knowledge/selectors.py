"""Audience allowlist projections. Build dicts from scratch — never pop secrets off full models."""

from apps.characters.models import Character
from apps.knowledge import policies
from apps.knowledge.models import Claim, ClaimEvidenceLink, Evidence, KnowledgeEdge

UNAVAILABLE = {'code': 'not_found', 'detail': 'Not found.'}

# Positive allowlists only.
CLAIM_FIELDS = ('id', 'proposition', 'my_state', 'sources', 'evidence', 'allowed_actions')
MY_STATE_FIELDS = ('stance', 'confidence', 'verification', 'shareability', 'acquired_at')
EVIDENCE_FIELDS = ('id', 'media_type', 'metadata', 'visibility', 'created_at')


def project_source_for_character(edge: KnowledgeEdge) -> dict:
    if policies.source_is_confidential(edge):
        return {'type': edge.source_type, 'display': 'Confidential source'}
    body = {'type': edge.source_type, 'display': edge.source_type.replace('_', ' ')}
    if edge.source_ref:
        body['ref'] = edge.source_ref
    return body


def project_evidence_for_character(evidence: Evidence, character: Character) -> dict | None:
    if not policies.can_access_evidence(character, evidence):
        return None
    return {
        'id': str(evidence.id),
        'media_type': evidence.media_type,
        'metadata': dict(evidence.metadata_json or {}),
        'visibility': evidence.visibility,
        'created_at': evidence.created_at.isoformat(),
    }


def visible_evidence_ids_for_claim(claim: Claim, character: Character) -> list[str]:
    ids: list[str] = []
    for link in ClaimEvidenceLink.objects.filter(claim=claim).select_related('evidence'):
        if policies.can_access_evidence(character, link.evidence):
            ids.append(str(link.evidence_id))
    return ids


def project_claim_for_character(claim: Claim, character: Character) -> dict | None:
    """Allowlisted claim projection. None means unavailable (caller maps to identical 404)."""
    if character.world_id != claim.world_id:
        return None
    edge = policies.knowledge_edge_for(character, claim)
    if edge is None:
        return None
    return {
        'id': str(claim.id),
        'proposition': claim.normalized_proposition,
        'my_state': {
            'stance': edge.stance,
            'confidence': float(edge.confidence),
            'verification': edge.verification,
            'shareability': edge.shareability,
            'acquired_at': edge.acquired_at.isoformat(),
        },
        'sources': [project_source_for_character(edge)],
        'evidence': visible_evidence_ids_for_claim(claim, character),
        'allowed_actions': _allowed_actions(edge),
    }


def _allowed_actions(edge: KnowledgeEdge) -> list[str]:
    actions = ['add_private_note', 'request_verification']
    if policies.can_redistribute(edge):
        actions.insert(0, 'share')
    return actions


def select_intel_claims_for_character(character: Character, *, q: str = '') -> list[dict]:
    """List only claims the character knows. Search never reveals unknown matches."""
    edges = (
        KnowledgeEdge.objects.filter(
            owner_character=character,
            awareness=KnowledgeEdge.Awareness.AWARE,
            world_id=character.world_id,
        )
        .select_related('claim')
        .order_by('-acquired_at')
    )
    needle = (q or '').strip().lower()
    out: list[dict] = []
    for edge in edges:
        claim = edge.claim
        if needle and needle not in claim.normalized_proposition.lower():
            continue
        projected = project_claim_for_character(claim, character)
        if projected is not None:
            out.append(projected)
    return out


def select_claim_detail(claim_id, character: Character) -> dict | None:
    claim = Claim.objects.filter(pk=claim_id, world_id=character.world_id).first()
    if claim is None:
        return None
    return project_claim_for_character(claim, character)


def select_evidence_detail(evidence_id, character: Character) -> dict | None:
    evidence = Evidence.objects.filter(pk=evidence_id, world_id=character.world_id).first()
    if evidence is None:
        return None
    return project_evidence_for_character(evidence, character)


def assert_no_truth_leak(payload: dict) -> None:
    """Dev/test helper: forbidden keys must never appear in audience payloads."""
    forbidden = {
        'linked_fact',
        'fact_id',
        'is_true',
        'truth',
        'system_confidence',
        'sensitivity',
        'canonical',
    }
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if key in forbidden:
                    raise AssertionError(f'Truth leak key present: {key}')
                stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)
