from django.core.exceptions import PermissionDenied

from apps.organizations.models import OrgMembership, Organization
from apps.worlds.models import WorldMembership

CAP_PUBLISH = 'publish_as_org'
CAP_READ_INTERNAL = 'read_internal'
CAP_MANAGE = 'manage_members'
CAP_LEADER = 'leader'


def active_world_membership(account, world) -> WorldMembership | None:
    return WorldMembership.objects.filter(
        world=world, account=account, status=WorldMembership.Status.ACTIVE
    ).first()


def require_active_world_membership(account, world) -> WorldMembership:
    membership = active_world_membership(account, world)
    if membership is None:
        raise PermissionDenied('Active world membership required.')
    return membership


def active_org_membership(character, organization: Organization) -> OrgMembership | None:
    return (
        OrgMembership.objects.filter(
            organization=organization,
            character=character,
            status=OrgMembership.Status.ACTIVE,
        )
        .first()
    )


def require_org_membership(character, organization: Organization) -> OrgMembership:
    if character.world_id != organization.world_id:
        raise PermissionDenied('Character is not in this organization world.')
    membership = active_org_membership(character, organization)
    if membership is None:
        raise PermissionDenied('Active organization membership required.')
    return membership


def has_capability(membership: OrgMembership, capability: str) -> bool:
    caps = membership.capabilities or []
    return capability in caps


def require_capability(membership: OrgMembership, capability: str) -> None:
    if not has_capability(membership, capability):
        raise PermissionDenied(f'Missing capability: {capability}')


def can_publish_as_org(character, organization: Organization) -> bool:
    try:
        membership = require_org_membership(character, organization)
    except PermissionDenied:
        return False
    return has_capability(membership, CAP_PUBLISH) or has_capability(membership, CAP_LEADER)


def can_read_internal(character, organization: Organization) -> bool:
    try:
        membership = require_org_membership(character, organization)
    except PermissionDenied:
        return False
    return has_capability(membership, CAP_READ_INTERNAL) or has_capability(membership, CAP_LEADER)
