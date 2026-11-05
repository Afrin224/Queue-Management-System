import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import SimpleTestCase, TestCase

from config.database import database_configuration
from config.supabase import check_project_api


class DatabaseConfigurationTests(SimpleTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)

    def test_absent_url_preserves_sqlite_with_immediate_transactions(self):
        config = database_configuration(self.base, {})
        self.assertEqual(config["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(config["OPTIONS"]["transaction_mode"], "IMMEDIATE")

    def test_supabase_direct_url_uses_tls_and_decodes_password(self):
        config = database_configuration(self.base, {"DATABASE_URL": "postgresql://postgres:secret%40test@db.project.supabase.co:5432/postgres"})
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["PASSWORD"], "secret@test")
        self.assertEqual(config["OPTIONS"]["sslmode"], "require")
        self.assertTrue(config["DISABLE_SERVER_SIDE_CURSORS"])

    def test_pooler_disables_prepared_statements(self):
        config = database_configuration(self.base, {"DATABASE_URL": "postgres://postgres.project:test@pooler.supabase.com:6543/postgres?sslmode=require"})
        self.assertEqual(config["USER"], "postgres.project")
        self.assertIsNone(config["OPTIONS"]["prepare_threshold"])
        self.assertNotIn("transaction_mode", config["OPTIONS"])

    def test_invalid_urls_and_placeholder_fail_without_echoing_credentials(self):
        for url in ["https://project.supabase.co", "postgres://postgres:[YOUR-PASSWORD]@db.project.supabase.co:5432/postgres", "postgres://postgres@db.project.supabase.co/postgres", "postgres://postgres:do-not-log-me@db.project.supabase.co:invalid/postgres"]:
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured) as context:
                database_configuration(self.base, {"DATABASE_URL": url})
            self.assertNotIn("do-not-log-me", str(context.exception))

    def test_remote_connections_cannot_disable_tls(self):
        with self.assertRaises(ImproperlyConfigured):
            database_configuration(self.base, {"DATABASE_URL": "postgres://user:test@db.project.supabase.co/postgres?sslmode=disable"})

    def test_loopback_postgres_can_use_local_test_server(self):
        config = database_configuration(self.base, {"DATABASE_URL": "postgres://test@127.0.0.1:55438/queueflow_test"})
        self.assertNotIn("sslmode", config["OPTIONS"])


class SupabaseConnectivityTests(SimpleTestCase):
    def test_probe_sends_publishable_key_as_apikey_not_bearer(self):
        opener = MagicMock()
        opener.return_value.__enter__.return_value.read.return_value = b'{"external": {"email": true}}'
        host = check_project_api("https://example.supabase.co", "sb_publishable_test", opener=opener)
        self.assertEqual(host, "example.supabase.co")
        request = opener.call_args.args[0]
        self.assertEqual(request.get_header("Apikey"), "sb_publishable_test")
        self.assertFalse(request.has_header("Authorization"))
        self.assertEqual(request.full_url, "https://example.supabase.co/auth/v1/settings")

    def test_probe_rejects_malformed_url_before_sending_key(self):
        opener = MagicMock()
        with self.assertRaises(ImproperlyConfigured):
            check_project_api("https://example.supabase.coSUPABASE_KEY=accidental", "sb_publishable_test", opener=opener)
        opener.assert_not_called()

    def test_probe_does_not_need_or_accept_secret_key(self):
        with self.assertRaises(ImproperlyConfigured):
            check_project_api("https://example.supabase.co", "sb_secret_not-for-this-check")


class PostgreSQLPrivacyTests(TestCase):
    def test_django_auth_and_queue_tables_have_rls_on_postgres(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-only RLS integration test")
        names = ["queues_manager", "queues_queue", "queues_token", "queues_ratelimit", "django_session", "django_migrations", "queues_manager_groups"]
        with connection.cursor() as cursor:
            cursor.execute("SELECT relname, relrowsecurity FROM pg_class WHERE oid IN (SELECT to_regclass(name) FROM unnest(%s::text[]) AS name)", [names])
            states = dict(cursor.fetchall())
        self.assertEqual(set(states), set(names))
        self.assertTrue(all(states.values()))

    def test_supabase_browser_roles_have_no_direct_queue_grants(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-only grants integration test")
        with connection.cursor() as cursor:
            cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
            roles = [row[0] for row in cursor.fetchall()]
            if not roles:
                self.skipTest("Supabase-style roles are not present on this PostgreSQL server")
            for role in roles:
                for table in ["queues_manager", "queues_queue", "queues_token", "django_session"]:
                    cursor.execute("SELECT has_table_privilege(%s, %s, 'SELECT')", [role, table])
                    self.assertFalse(cursor.fetchone()[0], (role, table))
