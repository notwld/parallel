import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts import services as auth_services
from apps.accounts.services import AuthRateLimited

User = get_user_model()


def _client_ip(request) -> str:
    return request.META.get('REMOTE_ADDR', '')


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as exc:
        raise ValidationError('Invalid JSON body.') from exc
    if not isinstance(data, dict):
        raise ValidationError('JSON object required.')
    return data


def _error(exc: Exception, status: int = 400):
    code = getattr(exc, 'code', None)
    if hasattr(exc, 'error_list') and exc.error_list:
        msg = exc.error_list[0].messages[0]
        code = getattr(exc.error_list[0], 'code', code)
    else:
        msg = str(exc)
    body = {'code': code or 'invalid', 'detail': msg}
    return JsonResponse(body, status=status)


@ensure_csrf_cookie
@require_GET
def csrf_bootstrap(request):
    return JsonResponse({'detail': 'CSRF cookie set'})


@csrf_protect
@require_http_methods(['POST'])
def signup(request):
    try:
        auth_services.check_auth_rate_limit(scope='signup', ip=_client_ip(request))
        data = _json_body(request)
        user, raw = auth_services.register_account(
            email=data.get('email', ''),
            password=data.get('password', ''),
            username=data.get('username'),
        )
    except AuthRateLimited as exc:
        return _error(exc, status=429)
    except ValidationError as exc:
        return _error(exc)
    # Raw verify token returned only so automated tests and local console flows work
    # without an email provider (documented external prerequisite).
    return JsonResponse(
        {**auth_services.account_public(user), 'verification_token': raw},
        status=201,
    )


@csrf_protect
@require_http_methods(['POST'])
def login_view(request):
    try:
        auth_services.check_auth_rate_limit(scope='login', ip=_client_ip(request), limit=20)
        data = _json_body(request)
        user = auth_services.login_account(
            request, email=data.get('email', ''), password=data.get('password', '')
        )
    except AuthRateLimited as exc:
        return _error(exc, status=429)
    except ValidationError as exc:
        return _error(exc, status=401)
    return JsonResponse(auth_services.account_public(user))


@csrf_protect
@require_http_methods(['POST'])
def logout_view(request):
    auth_services.logout_account(request)
    return JsonResponse({'detail': 'ok'})


@csrf_protect
@require_http_methods(['POST'])
def verify_email(request):
    try:
        data = _json_body(request)
        user = auth_services.verify_email(data.get('token', ''))
    except ValidationError as exc:
        return _error(exc)
    return JsonResponse(auth_services.account_public(user))


@csrf_protect
@require_http_methods(['POST'])
def password_reset_request(request):
    try:
        auth_services.check_auth_rate_limit(scope='reset', ip=_client_ip(request))
        data = _json_body(request)
        raw = auth_services.request_password_reset(data.get('email', ''))
    except AuthRateLimited as exc:
        return _error(exc, status=429)
    except ValidationError as exc:
        return _error(exc)
    body = {'detail': 'If that email exists, a reset token was sent.'}
    if raw is not None:
        body['reset_token'] = raw  # local/test without mail provider
    return JsonResponse(body)


@csrf_protect
@require_http_methods(['POST'])
def password_reset_confirm(request):
    try:
        data = _json_body(request)
        auth_services.confirm_password_reset(data.get('token', ''), data.get('password', ''))
    except ValidationError as exc:
        return _error(exc)
    return JsonResponse({'detail': 'Password updated.'})


@require_GET
def oauth_providers(request):
    return JsonResponse({
        'providers': [],
        'detail': (
            'No OAuth provider configured. Choose a provider and email delivery service '
            'before marking external login complete (see docs/DECISIONS.md).'
        ),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(auth_services.account_public(request.user))


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def preferences(request):
    prefs = auth_services.update_preferences(request.user, request.data if isinstance(request.data, dict) else {})
    return Response({'preferences': prefs})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sessions(request):
    return Response({'sessions': auth_services.list_sessions(request.user, request.session.session_key)})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def revoke_session(request, session_id):
    try:
        auth_services.revoke_session(request.user, session_id)
    except ValidationError as exc:
        return Response({'code': 'not_found', 'detail': str(exc)}, status=404)
    return Response(status=204)
