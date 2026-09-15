import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.characters.models import Character
from apps.organizations.models import Organization
from apps.worlds.models import World


def _xor_owner_q(character_field='owner_character', org_field='owner_organization'):
    return (
        Q(**{f'{character_field}__isnull': False, f'{org_field}__isnull': True})
        | Q(**{f'{character_field}__isnull': True, f'{org_field}__isnull': False})
    )


class Fact(models.Model):
    """Canonical world truth. Server-only — no public serializer (P006/P007)."""

    class Sensitivity(models.TextChoices):
        PUBLIC = 'public'
        RESTRICTED = 'restricted'
        SECRET = 'secret'
        TOP_SECRET = 'top_secret'

    class SystemStatus(models.TextChoices):
        ACTIVE = 'active'
        SUPERSEDED = 'superseded'
        RETRACTED = 'retracted'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name='facts')
    fact_type = models.CharField(max_length=64)
    subject_ref = models.CharField(max_length=200)
    predicate = models.CharField(max_length=200)
    value_json = models.JSONField(default=dict, blank=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(null=True, blank=True)
    system_confidence = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=Decimal('1.000'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
    )
    system_status = models.CharField(
        max_length=16, choices=SystemStatus.choices, default=SystemStatus.ACTIVE
    )
    sensitivity = models.CharField(
        max_length=16, choices=Sensitivity.choices, default=Sensitivity.SECRET
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['world', 'valid_from'], name='fact_world_valid_from'),
            models.Index(fields=['world', 'subject_ref'], name='fact_world_subject'),
        ]


class Claim(models.Model):
    class OriginType(models.TextChoices):
        DIRECT_OBSERVATION = 'direct_observation'
        MESSAGE = 'message'
        MEDIA = 'media'
        DOCUMENT = 'document'
        INFERENCE = 'inference'
        RUMOR = 'rumor'
        AI_NPC = 'ai_npc'
        SYSTEM = 'system'
        MUTATION = 'mutation'

    class Status(models.TextChoices):
        ACTIVE = 'active'
        SUPERSEDED = 'superseded'
        ARCHIVED = 'archived'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name='claims')
    normalized_proposition = models.TextField()
    subject_refs = models.JSONField(default=list, blank=True)
    origin_type = models.CharField(max_length=32, choices=OriginType.choices)
    origin_ref = models.CharField(max_length=200, blank=True, default='')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    # Server-only optional link; never expose via ordinary claim reads (P007).
    linked_fact = models.ForeignKey(
        Fact, null=True, blank=True, on_delete=models.SET_NULL, related_name='claims'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['world', 'created_at'], name='claim_world_created'),
            models.Index(fields=['world', 'status'], name='claim_world_status'),
        ]


class KnowledgeEdge(models.Model):
    class Awareness(models.TextChoices):
        UNAWARE = 'unaware'
        AWARE = 'aware'

    class Stance(models.TextChoices):
        ACCEPTS = 'accepts'
        SUSPECTS = 'suspects'
        UNCERTAIN = 'uncertain'
        REJECTS = 'rejects'
        KNOWS_FALSE = 'knows_false'

    class SourceType(models.TextChoices):
        DIRECT_OBSERVATION = 'direct_observation'
        MESSAGE = 'message'
        MEDIA = 'media'
        DOCUMENT = 'document'
        INFERENCE = 'inference'
        RUMOR = 'rumor'
        AI_NPC = 'ai_npc'

    class Shareability(models.TextChoices):
        PRIVATE = 'private'
        CONFIDENTIAL = 'confidential'
        OFF_RECORD = 'off_record'
        SHAREABLE = 'shareable'
        PUBLIC = 'public'

    class Verification(models.TextChoices):
        UNVERIFIED = 'unverified'
        CORROBORATED = 'corroborated'
        VERIFIED = 'verified'
        DISPUTED = 'disputed'
        DEBUNKED = 'debunked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name='knowledge_edges')
    owner_character = models.ForeignKey(
        Character, null=True, blank=True, on_delete=models.CASCADE, related_name='knowledge_edges'
    )
    owner_organization = models.ForeignKey(
        Organization, null=True, blank=True, on_delete=models.CASCADE, related_name='knowledge_edges'
    )
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='knowledge_edges')
    awareness = models.CharField(max_length=16, choices=Awareness.choices, default=Awareness.AWARE)
    stance = models.CharField(max_length=16, choices=Stance.choices)
    confidence = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
    )
    source_type = models.CharField(max_length=32, choices=SourceType.choices)
    source_ref = models.CharField(max_length=200, blank=True, default='')
    shareability = models.CharField(
        max_length=16, choices=Shareability.choices, default=Shareability.PRIVATE
    )
    verification = models.CharField(
        max_length=16, choices=Verification.choices, default=Verification.UNVERIFIED
    )
    acquired_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=_xor_owner_q(), name='knowledge_edge_xor_owner'),
            models.UniqueConstraint(
                fields=['claim', 'owner_character'],
                condition=Q(owner_character__isnull=False),
                name='knowledge_edge_unique_character',
            ),
            models.UniqueConstraint(
                fields=['claim', 'owner_organization'],
                condition=Q(owner_organization__isnull=False),
                name='knowledge_edge_unique_org',
            ),
        ]
        indexes = [
            models.Index(fields=['owner_character', '-acquired_at'], name='ke_owner_char_acquired'),
            models.Index(fields=['owner_organization', '-acquired_at'], name='ke_owner_org_acquired'),
            models.Index(fields=['claim', 'owner_character'], name='ke_claim_owner_char'),
            models.Index(fields=['world', 'verification'], name='ke_world_verification'),
        ]

    def clean(self):
        super().clean()
        if bool(self.owner_character_id) == bool(self.owner_organization_id):
            raise ValidationError('Exactly one of owner_character or owner_organization is required.')
        if self.claim_id and self.world_id and self.claim.world_id != self.world_id:
            raise ValidationError({'claim': 'Claim must belong to the same world.'})
        if self.owner_character_id and self.owner_character.world_id != self.world_id:
            raise ValidationError({'owner_character': 'Character must belong to the same world.'})
        if self.owner_organization_id and self.owner_organization.world_id != self.world_id:
            raise ValidationError({'owner_organization': 'Organization must belong to the same world.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Evidence(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = 'private'
        CONFIDENTIAL = 'confidential'
        SHARED = 'shared'
        PUBLIC = 'public'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name='evidence')
    owner_character = models.ForeignKey(
        Character, null=True, blank=True, on_delete=models.CASCADE, related_name='evidence'
    )
    owner_organization = models.ForeignKey(
        Organization, null=True, blank=True, on_delete=models.CASCADE, related_name='evidence'
    )
    # Binary upload deferred to P014; key may be empty for metadata-only evidence.
    storage_key = models.CharField(max_length=512, blank=True, default='')
    media_type = models.CharField(max_length=128, blank=True, default='text/plain')
    metadata_json = models.JSONField(default=dict, blank=True)
    integrity_hash = models.CharField(max_length=128, blank=True, default='')
    visibility = models.CharField(
        max_length=16, choices=Visibility.choices, default=Visibility.PRIVATE
    )
    chain_of_custody = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'evidence'
        constraints = [
            models.CheckConstraint(condition=_xor_owner_q(), name='evidence_xor_owner'),
        ]
        indexes = [
            models.Index(fields=['world', 'created_at'], name='evidence_world_created'),
            models.Index(fields=['owner_character', 'created_at'], name='evidence_owner_char'),
        ]

    def clean(self):
        super().clean()
        if bool(self.owner_character_id) == bool(self.owner_organization_id):
            raise ValidationError('Exactly one of owner_character or owner_organization is required.')
        if self.owner_character_id and self.owner_character.world_id != self.world_id:
            raise ValidationError({'owner_character': 'Character must belong to the same world.'})
        if self.owner_organization_id and self.owner_organization.world_id != self.world_id:
            raise ValidationError({'owner_organization': 'Organization must belong to the same world.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ClaimEvidenceLink(models.Model):
    class Relation(models.TextChoices):
        SUPPORTS = 'supports'
        CONTRADICTS = 'contradicts'
        CONTEXT = 'context'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='evidence_links')
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE, related_name='claim_links')
    relation = models.CharField(max_length=16, choices=Relation.choices)
    assessment = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['claim', 'evidence', 'relation'], name='claim_evidence_relation_unique'
            ),
        ]

    def clean(self):
        super().clean()
        if self.claim_id and self.evidence_id and self.claim.world_id != self.evidence.world_id:
            raise ValidationError('Claim and evidence must belong to the same world.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Transmission(models.Model):
    """Links source claim → derived claim when rumors mutate (never overwrite)."""

    class Channel(models.TextChoices):
        MESSAGE = 'message'
        POST = 'post'
        LEAK = 'leak'
        PUBLISH = 'publish'
        RUMOR = 'rumor'
        OTHER = 'other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name='transmissions')
    source_claim = models.ForeignKey(
        Claim, on_delete=models.CASCADE, related_name='outbound_transmissions'
    )
    resulting_claim = models.ForeignKey(
        Claim, on_delete=models.CASCADE, related_name='inbound_transmissions'
    )
    from_ref = models.CharField(max_length=200)
    to_ref = models.CharField(max_length=200)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    source_object_id = models.CharField(max_length=200, blank=True, default='')
    transmitted_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['world', 'transmitted_at'], name='tx_world_transmitted'),
            models.Index(fields=['source_claim'], name='tx_source_claim'),
            models.Index(fields=['resulting_claim'], name='tx_resulting_claim'),
        ]

    def clean(self):
        super().clean()
        if self.source_claim_id and self.world_id and self.source_claim.world_id != self.world_id:
            raise ValidationError({'source_claim': 'Must belong to the same world.'})
        if self.resulting_claim_id and self.world_id and self.resulting_claim.world_id != self.world_id:
            raise ValidationError({'resulting_claim': 'Must belong to the same world.'})
        if (
            self.source_claim_id
            and self.resulting_claim_id
            and self.source_claim_id == self.resulting_claim_id
            and self.channel not in (
                self.Channel.MESSAGE,
                self.Channel.LEAK,
                self.Channel.PUBLISH,
            )
        ):
            raise ValidationError('resulting_claim must differ from source_claim.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
