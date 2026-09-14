from unittest.mock import patch

from django.db import connection
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from django.conf import settings
import redis


class ReadinessContractTests(SimpleTestCase):
    def test_db_unavailable_returns_generic_503(self):
        with (
            patch(
                'config.urls.check_postgres',
                side_effect=OperationalError(
                    'could not connect to host=db.internal password=hunter2'
                ),
            ),
            patch('config.urls.check_redis'),
        ):
            response = self.client.get('/api/v1/ready/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        body = response.content.decode()
        self.assertNotIn('hunter2', body)
        self.assertNotIn('db.internal', body)
        self.assertNotIn('password', body.lower())

    def test_redis_unavailable_returns_generic_503(self):
        with (
            patch('config.urls.check_postgres'),
            patch(
                'config.urls.check_redis',
                side_effect=ConnectionError(
                    'Error 111 connecting to redis://:supersecret@redis-host:6379/0'
                ),
            ),
        ):
            response = self.client.get('/api/v1/ready/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        body = response.content.decode()
        self.assertNotIn('supersecret', body)
        self.assertNotIn('redis-host', body)
        self.assertNotIn('6379', body)

    def test_ready_when_dependencies_ok(self):
        with patch('config.urls.check_postgres'), patch('config.urls.check_redis'):
            response = self.client.get('/api/v1/ready/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        body = response.content.decode()
        self.assertNotIn('postgres', body.lower())
        self.assertNotIn('redis', body.lower())

    def test_ready_is_read_only(self):
        self.assertEqual(self.client.post('/api/v1/ready/').status_code, 405)

    def test_liveness_stays_process_only(self):
        with (
            patch('config.urls.check_postgres', side_effect=OperationalError('down')),
            patch('config.urls.check_redis', side_effect=ConnectionError('down')),
        ):
            response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'service': 'parallel-api'})


class LiveReadinessTests(TestCase):
    def test_ready_against_live_postgres_and_redis(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL required')
        client = redis.Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1
        )
        try:
            if client.ping() is not True:
                self.skipTest('Redis required')
        except Exception:
            self.skipTest('Redis required')
        finally:
            client.close()
        response = self.client.get('/api/v1/ready/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    @override_settings(REDIS_URL='redis://:ci-secret@127.0.0.1:9/0')
    def test_live_redis_down_does_not_leak_secret(self):
        response = self.client.get('/api/v1/ready/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        self.assertNotIn('ci-secret', response.content.decode())
