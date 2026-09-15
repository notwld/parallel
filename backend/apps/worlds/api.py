from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.characters.models import Character
from apps.characters.services import JoinRejected, character_public, join_world
from apps.worlds.models import RoleTemplate, World, WorldMembership


def _world_landing(world: World) -> dict:
    population = WorldMembership.objects.filter(
        world=world, status=WorldMembership.Status.ACTIVE
    ).count()
    roles = [
        {
            'id': str(r.id),
            'name': r.name,
            'description': r.description,
            'invite_only': r.invite_only,
            'max_slots': r.max_slots,
            # Do not advertise invite-only privileged roles as freely claimable.
            'claimable': not r.invite_only,
        }
        for r in RoleTemplate.objects.filter(world=world).order_by('name')
        if not r.invite_only
    ]
    return {
        'id': str(world.id),
        'slug': world.slug,
        'title': world.title,
        'premise': world.premise,
        'status': world.status,
        'visibility': world.visibility,
        'content_rating': world.content_rating,
        'world_time': world.world_time.isoformat(),
        'population': population,
        'roles': roles,
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def world_landing(request, slug):
    world = get_object_or_404(World, slug=slug)
    return Response(_world_landing(world))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def world_join(request, slug):
    world = get_object_or_404(World, slug=slug)
    data = request.data if isinstance(request.data, dict) else {}
    idem = request.headers.get('Idempotency-Key') or data.get('idempotency_key')
    if not idem:
        return Response({'code': 'missing_idempotency_key', 'detail': 'Idempotency-Key required.'}, status=400)
    try:
        character = join_world(
            account=request.user,
            world=world,
            role_template_id=data.get('role_template_id'),
            display_name=data.get('display_name', ''),
            invite_ref=data.get('invite_ref', ''),
            idempotency_key=str(idem),
        )
    except JoinRejected as exc:
        code = exc.rejection_code or 'join_rejected'
        detail = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
        return Response({'code': code, 'detail': detail}, status=409)
    return Response(character_public(character), status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_character(request, slug):
    world = get_object_or_404(World, slug=slug)
    character = (
        Character.objects.select_related('role_template')
        .filter(world=world, account=request.user)
        .first()
    )
    if character is None:
        return Response({'code': 'not_joined', 'detail': 'No character in this world.'}, status=404)
    body = character_public(character)
    # Explicit: never leak account identity on character profile.
    assert 'account' not in body and 'email' not in body and 'user' not in body
    return Response(body)
