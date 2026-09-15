from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.events.services import record_world_mutation
from apps.organizations import policies
from apps.organizations.models import OrgInvitation, OrgMembership, Organization
from apps.organizations.policies import CAP_LEADER, CAP_MANAGE, CAP_PUBLISH, CAP_READ_INTERNAL


class OrgError(ValidationError):
    def __init__(self, message, code=None):
        super().__init__(message, code=code)
        self.rejection_code = code


def create_organization(*, world, name: str, slug: str, org_type=Organization.OrgType.CUSTOM, max_leaders=1, location=None) -> Organization:
    return Organization.objects.create(
        world=world,
        name=name,
        slug=slug,
        org_type=org_type,
        max_leaders=max_leaders,
        location=location,
    )


def add_member(
    *,
    organization: Organization,
    character,
    role_name: str = 'member',
    capabilities: list | None = None,
    actor_character=None,
    idempotency_key: str,
) -> OrgMembership:
    if character.world_id != organization.world_id:
        raise OrgError('Character must belong to the organization world.', code='cross_world')
    caps = list(capabilities or [CAP_READ_INTERNAL])
    created: dict = {}

    def mutate():
        membership, _ = OrgMembership.objects.update_or_create(
            organization=organization,
            character=character,
            defaults={
                'role_name': role_name,
                'capabilities': caps,
                'status': OrgMembership.Status.ACTIVE,
            },
        )
        created['m'] = membership

    record_world_mutation(
        world=organization.world,
        event_type='org.member_added',
        idempotency_key=idempotency_key,
        payload={
            'organization_id': str(organization.id),
            'character_id': str(character.id),
            'role_name': role_name,
            'capabilities': caps,
        },
        actor_type='character',
        actor_id=getattr(actor_character, 'id', None),
        actor_label=getattr(actor_character, 'display_name', 'system'),
        mutate=mutate,
    )
    return created['m']


@transaction.atomic
def invite_character(*, organization, character, invited_by, role_name='member', capabilities=None) -> OrgInvitation:
    membership = policies.require_org_membership(invited_by, organization)
    policies.require_capability(membership, CAP_MANAGE)
    if character.world_id != organization.world_id:
        raise OrgError('Character must belong to the organization world.', code='cross_world')
    return OrgInvitation.objects.create(
        organization=organization,
        character=character,
        invited_by=invited_by,
        role_name=role_name,
        capabilities=list(capabilities or [CAP_READ_INTERNAL]),
    )


@transaction.atomic
def accept_invitation(*, invitation: OrgInvitation, idempotency_key: str) -> OrgMembership:
    if invitation.accepted_at is not None:
        existing = OrgMembership.objects.filter(
            organization=invitation.organization, character=invitation.character
        ).first()
        if existing:
            return existing
        raise OrgError('Invitation already used.', code='invite_used')
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=['accepted_at'])
    return add_member(
        organization=invitation.organization,
        character=invitation.character,
        role_name=invitation.role_name,
        capabilities=invitation.capabilities,
        actor_character=invitation.character,
        idempotency_key=idempotency_key,
    )


@transaction.atomic
def change_role(
    *,
    organization: Organization,
    character,
    role_name: str,
    capabilities: list,
    actor_character,
    idempotency_key: str,
) -> OrgMembership:
    actor_membership = policies.require_org_membership(actor_character, organization)
    policies.require_capability(actor_membership, CAP_MANAGE)
    target = policies.require_org_membership(character, organization)
    caps = list(capabilities)

    def mutate():
        target.role_name = role_name
        target.capabilities = caps
        target.save(update_fields=['role_name', 'capabilities', 'updated_at'])

    record_world_mutation(
        world=organization.world,
        event_type='org.role_changed',
        idempotency_key=idempotency_key,
        payload={
            'organization_id': str(organization.id),
            'character_id': str(character.id),
            'role_name': role_name,
            'capabilities': caps,
        },
        actor_type='character',
        actor_id=actor_character.id,
        actor_label=actor_character.display_name,
        mutate=mutate,
    )
    target.refresh_from_db()
    return target


@transaction.atomic
def allocate_leadership(
    *,
    organization: Organization,
    character,
    actor_character,
    idempotency_key: str,
) -> OrgMembership:
    org = Organization.objects.select_for_update().get(pk=organization.pk)
    actor_membership = policies.require_org_membership(actor_character, org)
    policies.require_capability(actor_membership, CAP_MANAGE)
    target = (
        OrgMembership.objects.select_for_update()
        .filter(organization=org, character=character, status=OrgMembership.Status.ACTIVE)
        .first()
    )
    if target is None:
        raise OrgError('Target is not an active member.', code='not_member')
    # Count in Python: JSONField __contains is unreliable on SQLite smoke DB.
    members = list(
        OrgMembership.objects.select_for_update().filter(
            organization=org, status=OrgMembership.Status.ACTIVE
        )
    )
    leaders = sum(1 for m in members if CAP_LEADER in (m.capabilities or []))
    if CAP_LEADER not in (target.capabilities or []) and leaders >= org.max_leaders:
        raise OrgError('No leadership slots remaining.', code='leader_full')

    caps = list(dict.fromkeys([*(target.capabilities or []), CAP_LEADER, CAP_PUBLISH, CAP_READ_INTERNAL, CAP_MANAGE]))

    def mutate():
        target.role_name = 'leader'
        target.capabilities = caps
        target.save(update_fields=['role_name', 'capabilities', 'updated_at'])

    record_world_mutation(
        world=org.world,
        event_type='org.leadership_allocated',
        idempotency_key=idempotency_key,
        payload={'organization_id': str(org.id), 'character_id': str(character.id)},
        actor_type='character',
        actor_id=actor_character.id,
        actor_label=actor_character.display_name,
        mutate=mutate,
    )
    target.refresh_from_db()
    return target


@transaction.atomic
def revoke_membership(*, organization: Organization, character, actor_character, idempotency_key: str) -> OrgMembership:
    actor_membership = policies.require_org_membership(actor_character, organization)
    policies.require_capability(actor_membership, CAP_MANAGE)
    target = policies.require_org_membership(character, organization)

    def mutate():
        target.status = OrgMembership.Status.REVOKED
        target.capabilities = []
        target.save(update_fields=['status', 'capabilities', 'updated_at'])

    record_world_mutation(
        world=organization.world,
        event_type='org.member_revoked',
        idempotency_key=idempotency_key,
        payload={'organization_id': str(organization.id), 'character_id': str(character.id)},
        actor_type='character',
        actor_id=actor_character.id,
        actor_label=actor_character.display_name,
        mutate=mutate,
    )
    target.refresh_from_db()
    return target


def publish_as_org(*, organization: Organization, character, body: str) -> dict:
    """Authority check for org statements; persistence of posts is P015."""
    if not policies.can_publish_as_org(character, organization):
        raise PermissionDenied('Ordinary members cannot publish as the organization.')
    return {
        'organization_id': str(organization.id),
        'authored_as': 'organization',
        'body': body,
        'speaker_character_id': str(character.id),
    }


def read_internal_record(*, organization: Organization, character, record: dict) -> dict:
    if not policies.can_read_internal(character, organization):
        raise PermissionDenied('Internal records require organization membership.')
    return record
