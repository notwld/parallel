import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.characters.models import Character
from apps.worlds.models import Location, World


class Organization(models.Model):
    class OrgType(models.TextChoices):
        GOVERNMENT = 'government'
        COMPANY = 'company'
        NEWSROOM = 'newsroom'
        SCIENCE = 'science'
        FACTION = 'faction'
        NGO = 'ngo'
        INTELLIGENCE = 'intelligence'
        GUILD = 'guild'
        CUSTOM = 'custom'

    class Status(models.TextChoices):
        ACTIVE = 'active'
        DISBANDED = 'disbanded'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name='organizations')
    org_type = models.CharField(max_length=32, choices=OrgType.choices, default=OrgType.CUSTOM)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80)
    public_profile = models.JSONField(default=dict, blank=True)
    location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.SET_NULL, related_name='organizations'
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    # ponytail: authored leadership cap; allocate with SELECT FOR UPDATE.
    max_leaders = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['world', 'slug'], name='org_slug_per_world'),
        ]

    def clean(self):
        super().clean()
        if self.location_id and self.location.world_id != self.world_id:
            raise ValidationError({'location': 'Location must belong to the same world.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class OrgMembership(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active'
        INVITED = 'invited'
        REVOKED = 'revoked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='org_memberships')
    role_name = models.CharField(max_length=64, default='member')
    capabilities = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'character'], name='one_org_membership_per_character'
            ),
        ]

    def clean(self):
        super().clean()
        if self.character_id and self.organization_id:
            if self.character.world_id != self.organization.world_id:
                raise ValidationError(
                    {'character': 'Character must belong to the organization world.'}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class OrgInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='invitations')
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='org_invitations')
    role_name = models.CharField(max_length=64, default='member')
    capabilities = models.JSONField(default=list, blank=True)
    invited_by = models.ForeignKey(
        Character, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'character'],
                condition=models.Q(accepted_at__isnull=True),
                name='one_open_org_invite_per_character',
            ),
        ]

    def clean(self):
        super().clean()
        if self.character.world_id != self.organization.world_id:
            raise ValidationError({'character': 'Invite character must share the org world.'})
        if self.invited_by_id and self.invited_by.world_id != self.organization.world_id:
            raise ValidationError({'invited_by': 'Inviter must share the org world.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
