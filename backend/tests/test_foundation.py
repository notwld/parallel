import uuid

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.permissions import IsAuthenticated
from rest_framework.settings import api_settings


class HealthTests(SimpleTestCase):
    def test_liveness_has_only_operational_status(self):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'service': 'parallel-api'})

    def test_liveness_is_read_only(self):
        self.assertEqual(self.client.post('/api/v1/health/').status_code, 405)

    def test_api_defaults_require_authentication(self):
        self.assertEqual(api_settings.DEFAULT_PERMISSION_CLASSES, [IsAuthenticated])


class UserTests(TestCase):
    def test_accounts_use_uuid_and_hash_passwords(self):
        user = get_user_model().objects.create_user(
            username='test-citizen', password='test-only-password'
        )
        self.assertIsInstance(user.pk, uuid.UUID)
        self.assertNotEqual(user.password, 'test-only-password')
        self.assertTrue(user.check_password('test-only-password'))
