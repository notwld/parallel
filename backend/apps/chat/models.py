from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.chat.snowflake import next_snowflake


def _snowflake_default():
    return next_snowflake()


class Server(models.Model):
    id = models.BigIntegerField(primary_key=True, default=_snowflake_default, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_chat_servers'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon_key = models.CharField(max_length=255, blank=True)
    member_count = models.PositiveIntegerField(default=0)
    flags = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = next_snowflake()
        super().save(*args, **kwargs)


class ServerMember(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_memberships'
    )
    nickname = models.CharField(max_length=64, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    flags = models.BigIntegerField(default=0)
    timeout_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['server', 'user'], name='chat_member_per_server'),
        ]
        indexes = [
            models.Index(fields=['user', 'server'], name='chat_members_user_idx'),
            models.Index(fields=['server', '-joined_at'], name='chat_members_joined_idx'),
        ]


class Role(models.Model):
    id = models.BigIntegerField(primary_key=True, default=_snowflake_default, editable=False)
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=100)
    permissions = models.BigIntegerField(default=0)
    position = models.IntegerField(default=0)
    color = models.IntegerField(null=True, blank=True)
    hoist = models.BooleanField(default=False)
    mentionable = models.BooleanField(default=False)
    is_everyone = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['server', '-position'], name='chat_roles_server_idx')]

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = next_snowflake()
        super().save(*args, **kwargs)


class MemberRole(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='+')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='member_links')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['server', 'user', 'role'], name='chat_member_role_unique'
            ),
        ]

    def clean(self):
        super().clean()
        if self.role_id and self.server_id and self.role.server_id != self.server_id:
            raise ValidationError({'role': 'Role must belong to the same server.'})


class Channel(models.Model):
    class Type(models.IntegerChoices):
        TEXT = 0
        DM = 1
        VOICE = 2
        GROUP_DM = 3
        CATEGORY = 4
        ANNOUNCEMENT = 5

    id = models.BigIntegerField(primary_key=True, default=_snowflake_default, editable=False)
    server = models.ForeignKey(
        Server, null=True, blank=True, on_delete=models.CASCADE, related_name='channels'
    )
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children'
    )
    channel_type = models.SmallIntegerField(choices=Type.choices, default=Type.TEXT)
    name = models.CharField(max_length=100, blank=True)
    topic = models.TextField(blank=True)
    position = models.IntegerField(default=0)
    nsfw = models.BooleanField(default=False)
    rate_limit_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['server', 'position', 'id'], name='chat_channels_server_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = next_snowflake()
        super().save(*args, **kwargs)


class ChannelPermissionOverwrite(models.Model):
    class TargetType(models.TextChoices):
        ROLE = 'role'
        MEMBER = 'member'

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='overwrites')
    target_type = models.CharField(max_length=16, choices=TargetType.choices)
    target_id = models.BigIntegerField()  # role id or hashed/user snowflake proxy: store user pk bits? 
    # Users are UUID — for member overwrites use a separate FK.
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='+',
    )
    allow = models.BigIntegerField(default=0)
    deny = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['channel', 'target_type', 'target_id'],
                condition=Q(target_type='role'),
                name='chat_overwrite_role_unique',
            ),
            models.UniqueConstraint(
                fields=['channel', 'target_user'],
                condition=Q(target_type='member', target_user__isnull=False),
                name='chat_overwrite_member_unique',
            ),
        ]


class DmParticipant(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='dm_participants')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dm_channels'
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['channel', 'user'], name='chat_dm_participant_unique'),
        ]
        indexes = [
            models.Index(fields=['user', 'channel'], name='chat_dm_by_user_idx'),
        ]


class Message(models.Model):
    id = models.BigIntegerField(primary_key=True, default=_snowflake_default, editable=False)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='chat_messages'
    )
    content = models.TextField()
    reply_to = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replies'
    )
    flags = models.BigIntegerField(default=0)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['channel', '-id'], name='chat_messages_timeline_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = next_snowflake()
        super().save(*args, **kwargs)


class ReadState(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_read_states'
    )
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='read_states')
    last_read_message_id = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'channel'], name='chat_read_state_unique'),
        ]


class Invite(models.Model):
    code = models.CharField(max_length=16, unique=True)
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='invites')
    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+'
    )
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    uses = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ServerBan(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='bans')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_bans'
    )
    reason = models.CharField(max_length=512, blank=True)
    banned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['server', 'user'], name='chat_ban_unique'),
        ]
