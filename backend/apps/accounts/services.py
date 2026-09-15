from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import AccountSession, AccountToken

User = get_user_model()


class AuthRateLimited(ValidationError):
    pass


def check_auth_rate_limit(*, scope: str, ip: str, limit: int = 10, window: int = 60) -> None:
    key = f'auth-rl:{scope}:{ip or "unknown"}'
    count = cache.get(key, 0)
    if count >= limit:
        raise AuthRateLimited('Too many attempts. Try again later.', code='rate_limited')
    if count == 0:
        cache.set(key, 1, window)
    else:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, count + 1, window)


def register_account(*, email: str, password: str, username: str | None = None) -> tuple:
    email = email.strip().lower()
    if not email or not password:
        raise ValidationError('Email and password are required.')
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError('Email already registered.', code='email_taken')
    username = (username or email.split('@')[0])[:150]
    base = username
    n = 0
    while User.objects.filter(username=username).exists():
        n += 1
        username = f'{base[:140]}{n}'
    user = User.objects.create_user(username=username, email=email, password=password)
    raw = AccountToken.issue(user, AccountToken.Purpose.EMAIL_VERIFY)
    send_mail(
        'Verify your Parallel account',
        f'Your verification token: {raw}',
        None,
        [email],
        fail_silently=True,
    )
    return user, raw


def verify_email(raw_token: str) -> User:
    token = AccountToken.consume(raw_token, AccountToken.Purpose.EMAIL_VERIFY)
    if token is None:
        raise ValidationError('Invalid or expired verification token.', code='invalid_token')
    user = token.account
    user.email_verified_at = timezone.now()
    user.save(update_fields=['email_verified_at'])
    return user


def request_password_reset(email: str) -> str | None:
    user = User.objects.filter(email__iexact=email.strip().lower()).first()
    if user is None:
        return None
    raw = AccountToken.issue(user, AccountToken.Purpose.PASSWORD_RESET, ttl_hours=2)
    send_mail(
        'Reset your Parallel password',
        f'Your reset token: {raw}',
        None,
        [user.email],
        fail_silently=True,
    )
    return raw


def confirm_password_reset(raw_token: str, new_password: str) -> User:
    if not new_password:
        raise ValidationError('Password required.')
    token = AccountToken.consume(raw_token, AccountToken.Purpose.PASSWORD_RESET)
    if token is None:
        raise ValidationError('Invalid or expired reset token.', code='invalid_token')
    user = token.account
    user.set_password(new_password)
    user.save(update_fields=['password'])
    Session.objects.filter(
        session_key__in=AccountSession.objects.filter(account=user).values_list(
            'session_key', flat=True
        )
    ).delete()
    AccountSession.objects.filter(account=user).delete()
    return user


def login_account(request, *, email: str, password: str) -> User:
    user = User.objects.filter(email__iexact=email.strip().lower()).first()
    if user is None:
        raise ValidationError('Invalid credentials.', code='invalid_credentials')
    authed = authenticate(request, username=user.username, password=password)
    if authed is None:
        raise ValidationError('Invalid credentials.', code='invalid_credentials')
    login(request, authed)
    if request.session.session_key:
        AccountSession.objects.update_or_create(
            session_key=request.session.session_key,
            defaults={
                'account': authed,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:256],
            },
        )
    return authed


def logout_account(request) -> None:
    key = request.session.session_key
    logout(request)
    if key:
        AccountSession.objects.filter(session_key=key).delete()


def list_sessions(account, current_key: str | None):
    rows = []
    for row in AccountSession.objects.filter(account=account).order_by('-created_at'):
        if not Session.objects.filter(session_key=row.session_key).exists():
            row.delete()
            continue
        rows.append({
            'id': str(row.id),
            'created_at': row.created_at.isoformat(),
            'last_seen_at': row.last_seen_at.isoformat(),
            'user_agent': row.user_agent,
            'current': row.session_key == current_key,
        })
    return rows


@transaction.atomic
def revoke_session(account, session_id) -> None:
    row = AccountSession.objects.select_for_update().filter(account=account, id=session_id).first()
    if row is None:
        raise ValidationError('Session not found.', code='not_found')
    Session.objects.filter(session_key=row.session_key).delete()
    row.delete()


def update_preferences(account, patch: dict) -> dict:
    allowed = {'notifications', 'safety', 'privacy', 'accessibility', 'timezone'}
    prefs = dict(account.preferences or {})
    for key, value in patch.items():
        if key in allowed:
            prefs[key] = value
    account.preferences = prefs
    account.save(update_fields=['preferences'])
    return prefs


def account_public(user) -> dict:
    return {
        'id': str(user.id),
        'username': user.username,
        'email': user.email,
        'email_verified': user.email_verified_at is not None,
        'preferences': user.preferences or {},
    }
