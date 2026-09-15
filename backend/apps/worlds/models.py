import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class World(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft'
        LIVE = 'live'
        PAUSED = 'paused'
        ARCHIVED = 'archived'

    class Visibility(models.TextChoices):
        PUBLIC = 'public'
        INVITE_ONLY = 'invite_only'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=200)
    premise = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    visibility = models.CharField(
        max_length=16, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    content_rating = models.CharField(max_length=32, blank=True)
    world_time = models.DateTimeField()
    tick_interval = models.DurationField(default=timedelta(days=1))
    rules = models.JSONField(default=dict, blank=True)
    simulation_config = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_worlds',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=['draft', 'live', 'paused', 'archived']),
                name='world_status_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(visibility__in=['public', 'invite_only']),
                name='world_visibility_valid',
            ),
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class WorldMembership(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active'
        INVITED = 'invited'
        LEFT = 'left'
        BANNED = 'banned'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name='memberships')
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='world_memberships',
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    joined_at = models.DateTimeField(auto_now_add=True)
    invite_ref = models.CharField(max_length=64, blank=True)
    safety_state = models.CharField(max_length=32, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['world', 'account'], name='one_membership_per_account_world'
            ),
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name='locations')
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT, related_name='children'
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80)
    kind = models.CharField(max_length=32, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['world', 'slug'], name='location_slug_per_world'),
            models.CheckConstraint(
                condition=~models.Q(parent=models.F('id')),
                name='location_parent_not_self',
            ),
        ]

    def clean(self):
        super().clean()
        if not self.parent_id:
            return
        if self.parent.world_id != self.world_id:
            raise ValidationError({'parent': 'Location parent must belong to the same world.'})
        if self.pk and self.parent_id == self.pk:
            raise ValidationError({'parent': 'Location cannot be its own parent.'})
        seen = {self.pk} if self.pk else set()
        current = self.parent
        while current is not None:
            if current.pk in seen:
                raise ValidationError({'parent': 'Location parent cycle is not allowed.'})
            seen.add(current.pk)
            current = current.parent

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class RoleTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name='role_templates')
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    capability_codes = models.JSONField(default=list, blank=True)
    starter_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    starter_relations = models.JSONField(default=list, blank=True)
    starter_knowledge = models.JSONField(default=list, blank=True)
    # ponytail: P004 must SELECT FOR UPDATE this row when assigning a limited role.
    max_slots = models.PositiveIntegerField(null=True, blank=True)
    invite_only = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['world', 'name'], name='role_name_per_world'),
        ]

    def clean(self):
        super().clean()
        if self.starter_location_id and self.starter_location.world_id != self.world_id:
            raise ValidationError(
                {'starter_location': 'Starter location must belong to the same world.'}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
