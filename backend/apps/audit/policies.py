from django.core.exceptions import PermissionDenied


def can_read_audit(user) -> bool:
    return bool(user is not None and getattr(user, 'is_authenticated', False) and user.is_staff)


def list_audit_for_world(user, world):
    if not can_read_audit(user):
        raise PermissionDenied('Audit records require privileged staff access.')
    from apps.audit.models import AuditRecord

    return AuditRecord.objects.filter(world=world).order_by('sequence')
