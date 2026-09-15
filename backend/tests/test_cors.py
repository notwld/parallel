from django.test import TestCase, override_settings


@override_settings(
    CORS_ALLOWED_ORIGINS=['http://127.0.0.1:5173'],
    CORS_ALLOW_CREDENTIALS=True,
)
class CorsCredentialTests(TestCase):
    def test_preflight_allows_vite_origin_with_credentials(self):
        response = self.client.options(
            '/api/v1/health/',
            HTTP_ORIGIN='http://127.0.0.1:5173',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Access-Control-Allow-Origin'], 'http://127.0.0.1:5173')
        self.assertEqual(response['Access-Control-Allow-Credentials'], 'true')

    def test_disallowed_origin_omits_allow_origin(self):
        response = self.client.get('/api/v1/health/', HTTP_ORIGIN='http://evil.example')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Access-Control-Allow-Origin', response)
