import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.worlds.models import Location, RoleTemplate, World


class Character(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active'
        RETIRED = 'retired'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name='characters')
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='characters',
    )
    role_template = models.ForeignKey(
        RoleTemplate, on_delete=models.PROTECT, related_name='characters'
    )
    location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.SET_NULL, related_name='characters'
    )
    display_name = models.CharField(max_length=80)
    bio = models.TextField(blank=True)
    avatar = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    public_profile = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['world', 'account'], name='one_character_per_account_world'
            ),
        ]

    def clean(self):
        super().clean()
        if self.role_template_id and self.role_template.world_id != self.world_id:
            raise ValidationError(
                {'role_template': 'Role template must belong to the same world.'}
            )
        if self.location_id and self.location.world_id != self.world_id:
            raise ValidationError({'location': 'Location must belong to the same world.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
