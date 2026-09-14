from django.contrib import admin
from django.urls import path
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    """Process liveness only; this does not assert database or worker readiness."""
    return Response({'status': 'ok', 'service': 'parallel-api'})


urlpatterns = [
    path('api/v1/health/', health, name='health'),
    path('admin/', admin.site.urls),
]
