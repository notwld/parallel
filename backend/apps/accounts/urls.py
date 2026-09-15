from django.urls import path

from apps.accounts import api as views

urlpatterns = [
    path('csrf/', views.csrf_bootstrap, name='auth-csrf'),
    path('signup/', views.signup, name='auth-signup'),
    path('login/', views.login_view, name='auth-login'),
    path('logout/', views.logout_view, name='auth-logout'),
    path('verify-email/', views.verify_email, name='auth-verify-email'),
    path('password-reset/', views.password_reset_request, name='auth-password-reset'),
    path('password-reset/confirm/', views.password_reset_confirm, name='auth-password-reset-confirm'),
    path('oauth/providers/', views.oauth_providers, name='auth-oauth-providers'),
    path('me/', views.me, name='auth-me'),
    path('me/preferences/', views.preferences, name='auth-preferences'),
    path('sessions/', views.sessions, name='auth-sessions'),
    path('sessions/<uuid:session_id>/', views.revoke_session, name='auth-revoke-session'),
]
