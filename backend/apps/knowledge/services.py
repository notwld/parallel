from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.events.services import record_world_mutation
from apps.knowledge.models import (
    Claim,
    ClaimEvidenceLink,
    Evidence,
    Fact,
    KnowledgeEdge,
    Transmission,
)


class KnowledgeError(ValidationError):
    def __init__(self, message, code=None):
        super().__init__(message, code=code)
        self.rejection_code = code


def _validate_confidence(confidence) -> Decimal:
    value = Decimal(str(confidence))
    if value < 0 or value > 1:
        raise KnowledgeError('Confidence must be between 0 and 1.', code='bad_confidence')
    return value


def create_fact(
    *,
    world,
    fact_type: str,
    subject_ref: str,
    predicate: str,
    value_json=None,
    valid_from=None,
    valid_to=None,
    system_confidence=Decimal('1'),
    sensitivity=Fact.Sensitivity.SECRET,
    idempotency_key: str,
) -> Fact:
    created: dict = {}
    payload = {
        'fact_type': fact_type,
        'subject_ref': subject_ref,
        'predicate': predicate,
        'value_json': value_json or {},
    }

    def mutate():
        created['f'] = Fact.objects.create(
            world=world,
            fact_type=fact_type,
            subject_ref=subject_ref,
            predicate=predicate,
            value_json=value_json or {},
            valid_from=valid_from or timezone.now(),
            valid_to=valid_to,
            system_confidence=_validate_confidence(system_confidence),
            sensitivity=sensitivity,
        )

    record_world_mutation(
        world=world,
        event_type='knowledge.fact_created',
        idempotency_key=idempotency_key,
        payload=payload,
        mutate=mutate,
    )
    return created['f']


def create_claim(
    *,
    world,
    normalized_proposition: str,
    origin_type: str,
    origin_ref: str = '',
    subject_refs=None,
    linked_fact: Fact | None = None,
    idempotency_key: str,
) -> Claim:
    if linked_fact is not None and linked_fact.world_id != world.id:
        raise KnowledgeError('linked_fact must belong to the same world.', code='cross_world')
    created: dict = {}
    payload = {
        'proposition': normalized_proposition,
        'origin_type': origin_type,
        'origin_ref': origin_ref,
    }

    def mutate():
        created['c'] = Claim.objects.create(
            world=world,
            normalized_proposition=normalized_proposition,
            subject_refs=list(subject_refs or []),
            origin_type=origin_type,
            origin_ref=origin_ref,
            linked_fact=linked_fact,
        )

    record_world_mutation(
        world=world,
        event_type='knowledge.claim_created',
        idempotency_key=idempotency_key,
        payload=payload,
        mutate=mutate,
    )
    return created['c']


def mutate_claim(
    *,
    source_claim: Claim,
    new_proposition: str,
    from_ref: str,
    to_ref: str,
    channel: str = Transmission.Channel.RUMOR,
    source_object_id: str = '',
    idempotency_key: str,
) -> tuple[Claim, Transmission]:
    """Create a derived claim + transmission; never overwrite the source."""
    created: dict = {}
    payload = {
        'source_claim_id': str(source_claim.id),
        'new_proposition': new_proposition,
        'from_ref': from_ref,
        'to_ref': to_ref,
        'channel': channel,
    }

    def mutate():
        derived = Claim.objects.create(
            world=source_claim.world,
            normalized_proposition=new_proposition,
            subject_refs=list(source_claim.subject_refs or []),
            origin_type=Claim.OriginType.MUTATION,
            origin_ref=str(source_claim.id),
            linked_fact=None,
        )
        tx = Transmission.objects.create(
            world=source_claim.world,
            source_claim=source_claim,
            resulting_claim=derived,
            from_ref=from_ref,
            to_ref=to_ref,
            channel=channel,
            source_object_id=source_object_id,
            transmitted_at=timezone.now(),
        )
        created['pair'] = (derived, tx)

    record_world_mutation(
        world=source_claim.world,
        event_type='knowledge.claim_mutated',
        idempotency_key=idempotency_key,
        payload=payload,
        mutate=mutate,
    )
    return created['pair']


def upsert_knowledge_edge(
    *,
    world,
    claim: Claim,
    stance: str,
    confidence,
    source_type: str,
    acquired_at=None,
    owner_character=None,
    owner_organization=None,
    source_ref: str = '',
    shareability: str = KnowledgeEdge.Shareability.PRIVATE,
    verification: str = KnowledgeEdge.Verification.UNVERIFIED,
    awareness: str = KnowledgeEdge.Awareness.AWARE,
    idempotency_key: str,
) -> KnowledgeEdge:
    if bool(owner_character) == bool(owner_organization):
        raise KnowledgeError('Exactly one owner required.', code='bad_owner')
    if claim.world_id != world.id:
        raise KnowledgeError('Claim must belong to the world.', code='cross_world')
    if owner_character is not None and owner_character.world_id != world.id:
        raise KnowledgeError('Character must belong to the world.', code='cross_world')
    if owner_organization is not None and owner_organization.world_id != world.id:
        raise KnowledgeError('Organization must belong to the world.', code='cross_world')
    conf = _validate_confidence(confidence)
    created: dict = {}
    payload = {
        'claim_id': str(claim.id),
        'owner_character_id': str(getattr(owner_character, 'id', '') or ''),
        'owner_organization_id': str(getattr(owner_organization, 'id', '') or ''),
        'stance': stance,
        'confidence': str(conf),
    }

    def mutate():
        defaults = {
            'world': world,
            'awareness': awareness,
            'stance': stance,
            'confidence': conf,
            'source_type': source_type,
            'source_ref': source_ref,
            'shareability': shareability,
            'verification': verification,
            'acquired_at': acquired_at or timezone.now(),
        }
        if owner_character is not None:
            edge, _ = KnowledgeEdge.objects.update_or_create(
                claim=claim,
                owner_character=owner_character,
                defaults={**defaults, 'owner_organization': None},
            )
        else:
            edge, _ = KnowledgeEdge.objects.update_or_create(
                claim=claim,
                owner_organization=owner_organization,
                defaults={**defaults, 'owner_character': None},
            )
        created['e'] = edge

    record_world_mutation(
        world=world,
        event_type='knowledge.edge_upserted',
        idempotency_key=idempotency_key,
        payload=payload,
        mutate=mutate,
    )
    return created['e']


def create_evidence(
    *,
    world,
    owner_character=None,
    owner_organization=None,
    media_type: str = 'text/plain',
    metadata_json=None,
    integrity_hash: str = '',
    storage_key: str = '',
    visibility: str = Evidence.Visibility.PRIVATE,
    chain_of_custody=None,
    idempotency_key: str,
) -> Evidence:
    if bool(owner_character) == bool(owner_organization):
        raise KnowledgeError('Exactly one owner required.', code='bad_owner')
    if owner_character is not None and owner_character.world_id != world.id:
        raise KnowledgeError('Character must belong to the world.', code='cross_world')
    if owner_organization is not None and owner_organization.world_id != world.id:
        raise KnowledgeError('Organization must belong to the world.', code='cross_world')
    created: dict = {}

    def mutate():
        created['ev'] = Evidence.objects.create(
            world=world,
            owner_character=owner_character,
            owner_organization=owner_organization,
            storage_key=storage_key,
            media_type=media_type,
            metadata_json=metadata_json or {},
            integrity_hash=integrity_hash,
            visibility=visibility,
            chain_of_custody=list(chain_of_custody or []),
        )

    record_world_mutation(
        world=world,
        event_type='knowledge.evidence_created',
        idempotency_key=idempotency_key,
        payload={'media_type': media_type, 'storage_key': storage_key},
        mutate=mutate,
    )
    return created['ev']


@transaction.atomic
def link_evidence(
    *,
    claim: Claim,
    evidence: Evidence,
    relation: str,
    assessment: str = '',
) -> ClaimEvidenceLink:
    if claim.world_id != evidence.world_id:
        raise KnowledgeError('Claim and evidence must share a world.', code='cross_world')
    return ClaimEvidenceLink.objects.create(
        claim=claim,
        evidence=evidence,
        relation=relation,
        assessment=assessment,
    )


def ordinary_claim_read(claim: Claim) -> dict:
    """Audience-safe claim shape for tests: no truth flags or fact ids."""
    return {
        'id': str(claim.id),
        'proposition': claim.normalized_proposition,
        'origin_type': claim.origin_type,
        'origin_ref': claim.origin_ref,
        'status': claim.status,
        'created_at': claim.created_at.isoformat(),
    }


# Shareability that may leave the sender's possession (P008).
_REDISTRIBUTABLE = frozenset({
    KnowledgeEdge.Shareability.CONFIDENTIAL,
    KnowledgeEdge.Shareability.SHAREABLE,
    KnowledgeEdge.Shareability.PUBLIC,
})

_RECIPIENT_CONF_FACTOR = Decimal('0.70')


class ShareResult:
    __slots__ = ('transmission', 'resulting_claim', 'recipient_edge')

    def __init__(self, transmission, resulting_claim, recipient_edge):
        self.transmission = transmission
        self.resulting_claim = resulting_claim
        self.recipient_edge = recipient_edge


def _recipient_shareability(sender_share: str) -> str:
    if sender_share == KnowledgeEdge.Shareability.PUBLIC:
        return KnowledgeEdge.Shareability.SHAREABLE
    if sender_share == KnowledgeEdge.Shareability.SHAREABLE:
        return KnowledgeEdge.Shareability.SHAREABLE
    # confidential: recipient may know the claim but must not expose Alice's identity.
    return KnowledgeEdge.Shareability.CONFIDENTIAL


def share_claim(
    *,
    sender,
    recipient,
    claim: Claim,
    evidence_ids=None,
    derived_proposition: str | None = None,
    channel: str = Transmission.Channel.MESSAGE,
    idempotency_key: str,
) -> ShareResult:
    """
    Transmit a claim (and optional evidence) to another character in the same world.
    Atomic Transmission + recipient KnowledgeEdge + audit/outbox. Never copies Fact truth.
    """
    from apps.knowledge import policies

    if sender.world_id != recipient.world_id or sender.world_id != claim.world_id:
        raise KnowledgeError('Sender, recipient, and claim must share a world.', code='cross_world')
    if sender.id == recipient.id:
        raise KnowledgeError('Cannot share to self.', code='bad_recipient')

    sender_edge = policies.knowledge_edge_for(sender, claim)
    if sender_edge is None:
        raise KnowledgeError('Claim not in your knowledge.', code='not_found')
    if sender_edge.shareability not in _REDISTRIBUTABLE:
        raise KnowledgeError('This knowledge may not be redistributed.', code='not_shareable')

    evidence_ids = list(evidence_ids or [])
    evidence_rows = []
    for eid in evidence_ids:
        ev = Evidence.objects.filter(pk=eid, world_id=claim.world_id).first()
        if ev is None or not policies.can_access_evidence(sender, ev):
            raise KnowledgeError('Evidence not available to share.', code='evidence_denied')
        evidence_rows.append(ev)

    derived_text = (derived_proposition or '').strip()
    mutate_wording = bool(derived_text) and derived_text != claim.normalized_proposition
    if channel not in dict(Transmission.Channel.choices):
        raise KnowledgeError('Invalid channel.', code='bad_channel')

    from_ref = f'character:{sender.id}'
    to_ref = f'character:{recipient.id}'
    conf = max(
        Decimal('0.05'),
        min(Decimal('1'), (sender_edge.confidence * _RECIPIENT_CONF_FACTOR).quantize(Decimal('0.001'))),
    )
    stance = (
        KnowledgeEdge.Stance.SUSPECTS
        if sender_edge.stance == KnowledgeEdge.Stance.ACCEPTS
        else sender_edge.stance
    )
    recipient_share = _recipient_shareability(sender_edge.shareability)
    # Confidential citation: store transmission id as source_ref; projection hides it.
    created: dict = {}
    payload = {
        'claim_id': str(claim.id),
        'from_ref': from_ref,
        'to_ref': to_ref,
        'channel': channel,
        'evidence_ids': [str(e.id) for e in evidence_rows],
        'derived': mutate_wording,
        'derived_proposition': derived_text if mutate_wording else '',
    }

    def mutate():
        resulting = claim
        if mutate_wording:
            resulting = Claim.objects.create(
                world=claim.world,
                normalized_proposition=derived_text,
                subject_refs=list(claim.subject_refs or []),
                origin_type=Claim.OriginType.MUTATION,
                origin_ref=str(claim.id),
                linked_fact=None,
            )
        tx = Transmission.objects.create(
            world=claim.world,
            source_claim=claim,
            resulting_claim=resulting,
            from_ref=from_ref,
            to_ref=to_ref,
            channel=channel,
            source_object_id='',
            transmitted_at=timezone.now(),
        )
        for ev in evidence_rows:
            if ev.visibility == Evidence.Visibility.PRIVATE:
                ev.visibility = Evidence.Visibility.SHARED
                ev.save(update_fields=['visibility'])
            custody = list(ev.chain_of_custody or [])
            custody.append(
                {
                    'at': timezone.now().isoformat(),
                    'action': 'shared',
                    'from': from_ref,
                    'to': to_ref,
                    'transmission_id': str(tx.id),
                }
            )
            ev.chain_of_custody = custody
            ev.save(update_fields=['chain_of_custody'])

        edge, _ = KnowledgeEdge.objects.update_or_create(
            claim=resulting,
            owner_character=recipient,
            defaults={
                'world': claim.world,
                'owner_organization': None,
                'awareness': KnowledgeEdge.Awareness.AWARE,
                'stance': stance,
                'confidence': conf,
                'source_type': KnowledgeEdge.SourceType.MESSAGE,
                'source_ref': f'transmission:{tx.id}',
                'shareability': recipient_share,
                'verification': KnowledgeEdge.Verification.UNVERIFIED,
                'acquired_at': timezone.now(),
            },
        )
        created['result'] = ShareResult(tx, resulting, edge)

    record_world_mutation(
        world=claim.world,
        event_type='knowledge.claim_shared',
        idempotency_key=idempotency_key,
        payload=payload,
        actor_type='character',
        actor_id=sender.id,
        actor_label=sender.display_name,
        cause_type='claim',
        cause_ref=claim.id,
        mutate=mutate,
    )
    if 'result' in created:
        return created['result']
    # Idempotent retry: reconstruct from Transmission + edge.
    tx = (
        Transmission.objects.filter(
            world=claim.world,
            source_claim=claim,
            from_ref=from_ref,
            to_ref=to_ref,
            channel=channel,
        )
        .order_by('-created_at')
        .first()
    )
    if tx is None:
        raise KnowledgeError('Share retry could not locate transmission.', code='share_missing')
    edge = KnowledgeEdge.objects.get(claim=tx.resulting_claim, owner_character=recipient)
    return ShareResult(tx, tx.resulting_claim, edge)


def submit_verification_assessment(
    *,
    character,
    claim: Claim,
    verification: str,
    notes: str = '',
    evidence_id=None,
    idempotency_key: str,
) -> KnowledgeEdge:
    """
    Character-scoped verification assessment. Never copies or reveals Fact truth.
    """
    from apps.knowledge import policies

    if character.world_id != claim.world_id:
        raise KnowledgeError('Claim must belong to the character world.', code='cross_world')
    if verification not in dict(KnowledgeEdge.Verification.choices):
        raise KnowledgeError('Invalid verification state.', code='bad_verification')
    edge = policies.knowledge_edge_for(character, claim)
    if edge is None:
        raise KnowledgeError('Claim not in your knowledge.', code='not_found')

    if evidence_id is not None:
        ev = Evidence.objects.filter(pk=evidence_id, world_id=claim.world_id).first()
        if ev is None or not policies.can_access_evidence(character, ev):
            raise KnowledgeError('Evidence not available.', code='evidence_denied')

    created: dict = {}
    payload = {
        'claim_id': str(claim.id),
        'character_id': str(character.id),
        'verification': verification,
        'notes': notes[:2000],
        'evidence_id': str(evidence_id) if evidence_id else '',
    }

    def mutate():
        edge.verification = verification
        edge.save(update_fields=['verification', 'updated_at'])
        if evidence_id is not None:
            link = ClaimEvidenceLink.objects.filter(claim=claim, evidence_id=evidence_id).first()
            if link is not None:
                link.assessment = notes[:2000]
                link.save(update_fields=['assessment'])
        created['edge'] = edge

    record_world_mutation(
        world=claim.world,
        event_type='knowledge.verification_assessed',
        idempotency_key=idempotency_key,
        payload=payload,
        actor_type='character',
        actor_id=character.id,
        actor_label=character.display_name,
        cause_type='claim',
        cause_ref=claim.id,
        mutate=mutate,
    )
    if 'edge' in created:
        return created['edge']
    return KnowledgeEdge.objects.get(claim=claim, owner_character=character)
