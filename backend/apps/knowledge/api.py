from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.characters.models import Character
from apps.events.services import IdempotencyConflict
from apps.knowledge import policies, selectors
from apps.knowledge.models import Claim
from apps.knowledge.services import KnowledgeError, share_claim, submit_verification_assessment
from apps.worlds.models import World


def _unavailable():
    # Identical body for missing vs unauthorized — no existence side channel.
    return Response(selectors.UNAVAILABLE, status=404)


def _character_or_unavailable(request, world):
    try:
        return policies.require_character_in_world(request.user, world), None
    except PermissionDenied:
        return None, _unavailable()


def _idempotency_key(request) -> str:
    return (
        request.headers.get('Idempotency-Key')
        or request.data.get('idempotency_key')
        or ''
    ).strip()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def intel_claim_list(request, slug):
    world = get_object_or_404(World, slug=slug)
    character, err = _character_or_unavailable(request, world)
    if err is not None:
        return err
    q = request.query_params.get('q', '')
    items = selectors.select_intel_claims_for_character(character, q=q)
    return Response({'results': items})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def intel_claim_detail(request, slug, claim_id):
    world = get_object_or_404(World, slug=slug)
    character, err = _character_or_unavailable(request, world)
    if err is not None:
        return err
    body = selectors.select_claim_detail(claim_id, character)
    if body is None:
        return _unavailable()
    selectors.assert_no_truth_leak(body)
    return Response(body)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def intel_evidence_detail(request, slug, evidence_id):
    world = get_object_or_404(World, slug=slug)
    character, err = _character_or_unavailable(request, world)
    if err is not None:
        return err
    body = selectors.select_evidence_detail(evidence_id, character)
    if body is None:
        return _unavailable()
    return Response(body)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def intel_claim_share(request, slug, claim_id):
    world = get_object_or_404(World, slug=slug)
    character, err = _character_or_unavailable(request, world)
    if err is not None:
        return err
    claim = Claim.objects.filter(pk=claim_id, world=world).first()
    if claim is None or not policies.can_access_claim(character, claim):
        return _unavailable()

    key = _idempotency_key(request)
    if not key:
        return Response(
            {'code': 'idempotency_required', 'detail': 'Idempotency-Key required.'},
            status=400,
        )

    recipient_id = request.data.get('recipient_character_id')
    recipient = Character.objects.filter(pk=recipient_id, world=world).first()
    if recipient is None:
        return Response(
            {'code': 'bad_recipient', 'detail': 'Recipient not found in world.'},
            status=400,
        )

    evidence_ids = request.data.get('evidence_ids') or []
    try:
        result = share_claim(
            sender=character,
            recipient=recipient,
            claim=claim,
            evidence_ids=evidence_ids,
            derived_proposition=request.data.get('derived_proposition') or None,
            channel=request.data.get('channel') or 'message',
            idempotency_key=key,
        )
    except KnowledgeError as exc:
        if exc.rejection_code in {'not_found', 'not_shareable'}:
            return _unavailable()
        return Response({'code': exc.rejection_code or 'rejected', 'detail': str(exc.messages[0] if exc.messages else exc)}, status=400)
    except IdempotencyConflict as exc:
        return Response({'code': 'idempotency_conflict', 'detail': str(exc)}, status=409)
    except ValidationError as exc:
        return Response({'code': 'rejected', 'detail': str(exc)}, status=400)

    return Response(
        {
            'transmission_id': str(result.transmission.id),
            'claim_id': str(result.resulting_claim.id),
            'recipient_character_id': str(recipient.id),
        },
        status=201,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def intel_claim_verify(request, slug, claim_id):
    world = get_object_or_404(World, slug=slug)
    character, err = _character_or_unavailable(request, world)
    if err is not None:
        return err
    claim = Claim.objects.filter(pk=claim_id, world=world).first()
    if claim is None or not policies.can_access_claim(character, claim):
        return _unavailable()

    key = _idempotency_key(request)
    if not key:
        return Response(
            {'code': 'idempotency_required', 'detail': 'Idempotency-Key required.'},
            status=400,
        )

    verification = request.data.get('verification', '')
    try:
        edge = submit_verification_assessment(
            character=character,
            claim=claim,
            verification=verification,
            notes=request.data.get('notes') or '',
            evidence_id=request.data.get('evidence_id') or None,
            idempotency_key=key,
        )
    except KnowledgeError as exc:
        if exc.rejection_code == 'not_found':
            return _unavailable()
        return Response(
            {
                'code': exc.rejection_code or 'rejected',
                'detail': str(exc.messages[0] if exc.messages else exc),
            },
            status=400,
        )
    except IdempotencyConflict as exc:
        return Response({'code': 'idempotency_conflict', 'detail': str(exc)}, status=409)

    return Response(
        {
            'claim_id': str(claim.id),
            'verification': edge.verification,
        }
    )
