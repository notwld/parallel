import logging

from django.conf import settings
from django.contrib import admin
from django.db import connection
from django.urls import path
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import redis

logger = logging.getLogger(__name__)
READY_TIMEOUT_SECONDS = 1


def check_postgres():
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        if cursor.fetchone() is None:
            raise RuntimeError('postgres check returned no row')


def check_redis():
    client = redis.Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=READY_TIMEOUT_SECONDS,
        socket_timeout=READY_TIMEOUT_SECONDS,
    )
    try:
        if client.ping() is not True:
            raise ConnectionError('redis ping failed')
    finally:
        client.close()


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    """Process liveness only; this does not assert database or worker readiness."""
    return Response({'status': 'ok', 'service': 'parallel-api'})


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def ready(request):
    try:
        check_postgres()
        check_redis()
    except Exception:
        logger.warning('readiness check failed')
        return Response({'status': 'unavailable'}, status=503)
    return Response({'status': 'ok'})


urlpatterns = [
    path('api/v1/health/', health, name='health'),
    path('api/v1/ready/', ready, name='ready'),
    path('admin/', admin.site.urls),
]
