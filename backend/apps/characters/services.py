from django.core.exceptions import ValidationError
from django.db import transaction

from apps.characters.models import Character
from apps.events.services import IdempotencyConflict, record_world_mutation
from apps.worlds.models import RoleTemplate, World, WorldMembership


class JoinRejected(ValidationError):
    def __init__(self, message, code=None):
        super().__init__(message, code=code)
        self.rejection_code = code


def character_public(character: Character) -> dict:
    """Public/own character projection — never includes account identity."""
    return {
        'id': str(character.id),
        'world_id': str(character.world_id),
        'display_name': character.display_name,
        'bio': character.bio,
        'avatar': character.avatar,
        'status': character.status,
        'role_template_id': str(character.role_template_id),
        'role_name': character.role_template.name,
        'location_id': str(character.location_id) if character.location_id else None,
        'public_profile': character.public_profile or {},
        'capability_codes': list(character.role_template.capability_codes or []),
    }


@transaction.atomic
def join_world(
    *,
    account,
    world: World,
    role_template_id,
    display_name: str,
    invite_ref: str = '',
    idempotency_key: str,
) -> Character:
    world = World.objects.select_for_update().get(pk=world.pk)

    if world.status in (World.Status.DRAFT, World.Status.ARCHIVED):
        raise JoinRejected('World is not open for joining.', code='world_closed')
    if world.status == World.Status.PAUSED:
        raise JoinRejected('World is paused.', code='world_paused')
    if world.visibility == World.Visibility.INVITE_ONLY:
        expected = (world.rules or {}).get('invite_code', '')
        invited = WorldMembership.objects.filter(
            world=world, account=account, status=WorldMembership.Status.INVITED
        ).exists()
        if not invited and (not invite_ref or invite_ref != expected):
            raise JoinRejected('Invite required.', code='invite_required')

    existing = Character.objects.filter(world=world, account=account).select_related('role_template').first()
    if existing is not None:
        # Idempotent re-join: same key or already a member returns the character.
        return existing

    role = (
        RoleTemplate.objects.select_for_update()
        .filter(pk=role_template_id, world=world)
        .first()
    )
    if role is None:
        raise JoinRejected('Role not found in this world.', code='role_not_found')
    if role.invite_only:
        raise JoinRejected('Role requires moderator invitation.', code='role_invite_only')
    if role.max_slots is not None:
        taken = Character.objects.filter(world=world, role_template=role).count()
        if taken >= role.max_slots:
            raise JoinRejected('Role has no remaining slots.', code='role_full')

    name = (display_name or '').strip()
    if not name:
        raise JoinRejected('display_name is required.', code='invalid_name')

    created: dict = {}

    def mutate():
        membership, _ = WorldMembership.objects.get_or_create(
            world=world,
            account=account,
            defaults={'status': WorldMembership.Status.ACTIVE, 'invite_ref': invite_ref},
        )
        if membership.status != WorldMembership.Status.ACTIVE:
            membership.status = WorldMembership.Status.ACTIVE
            membership.invite_ref = invite_ref or membership.invite_ref
            membership.save(update_fields=['status', 'invite_ref'])
        character = Character.objects.create(
            world=world,
            account=account,
            role_template=role,
            location=role.starter_location,
            display_name=name,
        )
        created['character'] = character

    try:
        record_world_mutation(
            world=world,
            event_type='world.joined',
            idempotency_key=idempotency_key,
            payload={
                'account_id': str(account.id),
                'role_template_id': str(role.id),
                'display_name': name,
            },
            actor_type='account',
            actor_id=account.id,
            actor_label=account.username,
            mutate=mutate,
        )
    except IdempotencyConflict as exc:
        raise JoinRejected(str(exc), code='idempotency_conflict') from exc

    character = created.get('character') or Character.objects.select_related('role_template').get(
        world=world, account=account
    )
    return character
