from django.core.exceptions import PermissionDenied

from apps.characters.models import Character
from apps.knowledge.models import Claim, Evidence, KnowledgeEdge
from apps.worlds.models import WorldMembership

# Shareability levels that must not expose upstream source identity.
_CONFIDENTIAL_SHARE = frozenset({
    KnowledgeEdge.Shareability.PRIVATE,
    KnowledgeEdge.Shareability.CONFIDENTIAL,
    KnowledgeEdge.Shareability.OFF_RECORD,
})

# Levels that may be redistributed to another character (P008).
_REDISTRIBUTABLE = frozenset({
    KnowledgeEdge.Shareability.CONFIDENTIAL,
    KnowledgeEdge.Shareability.SHAREABLE,
    KnowledgeEdge.Shareability.PUBLIC,
})


def require_active_world_membership(account, world) -> WorldMembership:
    membership = WorldMembership.objects.filter(
        world=world, account=account, status=WorldMembership.Status.ACTIVE
    ).first()
    if membership is None:
        raise PermissionDenied('Active world membership required.')
    return membership


def character_in_world(account, world) -> Character | None:
    return Character.objects.filter(world=world, account=account).first()


def require_character_in_world(account, world) -> Character:
    require_active_world_membership(account, world)
    character = character_in_world(account, world)
    if character is None:
        raise PermissionDenied('Character required in this world.')
    return character


def knowledge_edge_for(character: Character, claim: Claim) -> KnowledgeEdge | None:
    if character.world_id != claim.world_id:
        return None
    return (
        KnowledgeEdge.objects.filter(
            claim=claim,
            owner_character=character,
            awareness=KnowledgeEdge.Awareness.AWARE,
        )
        .first()
    )


def can_access_claim(character: Character, claim: Claim) -> bool:
    return knowledge_edge_for(character, claim) is not None


def can_access_evidence(character: Character, evidence: Evidence) -> bool:
    if character.world_id != evidence.world_id:
        return False
    if evidence.owner_character_id == character.id:
        return True
    if evidence.visibility in (Evidence.Visibility.PUBLIC, Evidence.Visibility.SHARED):
        # Still require the character to know a linked claim (no bare evidence enumeration).
        return Evidence.objects.filter(
            pk=evidence.pk,
            claim_links__claim__knowledge_edges__owner_character=character,
            claim_links__claim__knowledge_edges__awareness=KnowledgeEdge.Awareness.AWARE,
        ).exists()
    return False


def can_redistribute(edge: KnowledgeEdge) -> bool:
    return edge.shareability in _REDISTRIBUTABLE


def source_is_confidential(edge: KnowledgeEdge) -> bool:
    return edge.shareability in _CONFIDENTIAL_SHARE
