"""Faz 4: üretim ayarları ve Supabase RLS migration'ı."""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

BASE_DIR = Path(settings.BASE_DIR)


def load_settings(**env):
    """settings.py'yi ayrı bir süreçte verilen ortam değişkenleriyle içe aktarıp seçili değerleri döner."""
    code = (
        "import json, sys\n"
        "try:\n"
        "    from config import settings as s\n"
        "except Exception as e:\n"
        "    print(json.dumps({'error': type(e).__name__ + ': ' + str(e)}))\n"
        "    sys.exit(0)\n"
        "keys = ['DEBUG', 'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE',\n"
        "        'SECURE_SSL_REDIRECT', 'SECURE_PROXY_SSL_HEADER', 'SECURE_HSTS_SECONDS', 'DATABASES', 'STORAGES']\n"
        "print(json.dumps({k: getattr(s, k, None) for k in keys}, default=str))\n"
    )
    full_env = {**os.environ, "DJANGO_DEBUG": "", "DJANGO_SECRET_KEY": "", "DATABASE_URL": "", "DJANGO_ALLOWED_HOSTS": ""}
    full_env.update(env)
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BASE_DIR, env=full_env, capture_output=True, text=True, timeout=60
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


class ProductionSettingsTests(SimpleTestCase):
    SECRET = "x" * 60

    def prod(self, **env):
        return load_settings(DJANGO_DEBUG="False", DJANGO_SECRET_KEY=self.SECRET, **env)

    def test_secret_key_required_when_debug_is_off(self):
        result = load_settings(DJANGO_DEBUG="False", DJANGO_SECRET_KEY="")
        self.assertIn("DJANGO_SECRET_KEY", result["error"])

    def test_debug_defaults_to_off(self):
        result = load_settings(DJANGO_SECRET_KEY=self.SECRET)
        self.assertFalse(result["DEBUG"])

    def test_secure_flags_when_debug_off(self):
        s = self.prod()
        self.assertFalse(s["DEBUG"])
        self.assertTrue(s["SESSION_COOKIE_SECURE"])
        self.assertTrue(s["CSRF_COOKIE_SECURE"])
        self.assertFalse(s["SECURE_SSL_REDIRECT"])
        self.assertEqual(s["SECURE_PROXY_SSL_HEADER"], ["HTTP_X_FORWARDED_PROTO", "https"])
        self.assertGreater(s["SECURE_HSTS_SECONDS"], 0)

    def test_secure_flags_not_forced_in_development(self):
        s = load_settings(DJANGO_DEBUG="True")
        self.assertTrue(s["DEBUG"])
        self.assertFalse(s["SESSION_COOKIE_SECURE"])
        self.assertFalse(s["CSRF_COOKIE_SECURE"])

    def test_hosts_and_csrf_origins(self):
        s = self.prod(DJANGO_ALLOWED_HOSTS="kararsizim.example.com, www.example.com")
        for host in ("localhost", "127.0.0.1", ".vercel.app", "kararsizim.example.com", "www.example.com"):
            self.assertIn(host, s["ALLOWED_HOSTS"])
        self.assertIn("https://*.vercel.app", s["CSRF_TRUSTED_ORIGINS"])
        self.assertIn("https://kararsizim.example.com", s["CSRF_TRUSTED_ORIGINS"])

    def test_sqlite_without_database_url(self):
        self.assertIn("sqlite3", self.prod()["DATABASES"]["default"]["ENGINE"])

    def test_supabase_pooler_settings(self):
        s = self.prod(DATABASE_URL="postgres://postgres.abcd:p%40ss@aws-0-eu-central-1.pooler.supabase.com:6543/postgres")
        db = s["DATABASES"]["default"]
        self.assertIn("postgresql", db["ENGINE"])
        self.assertEqual(db["PORT"], 6543)
        self.assertEqual(db["USER"], "postgres.abcd")
        self.assertEqual(db["PASSWORD"], "p@ss")
        self.assertEqual(db["CONN_MAX_AGE"], 0)
        self.assertTrue(db["DISABLE_SERVER_SIDE_CURSORS"])
        self.assertEqual(db["OPTIONS"]["sslmode"], "require")
        self.assertIsNone(db["OPTIONS"]["prepare_threshold"])

    def test_database_url_must_be_a_postgres_url(self):
        for bad in ("Kararsizim99", "abc", "mysql://u:p@h/db", "[YOUR-PASSWORD]"):
            with self.subTest(value=bad):
                result = self.prod(DATABASE_URL=bad)
                self.assertIn("DATABASE_URL", result["error"])
                self.assertIn("postgresql://", result["error"])

    def test_manifest_static_storage_only_in_production(self):
        prod = self.prod()["STORAGES"]["staticfiles"]["BACKEND"]
        dev = load_settings(DJANGO_DEBUG="True")["STORAGES"]["staticfiles"]["BACKEND"]
        self.assertIn("CompressedManifestStaticFilesStorage", prod)
        self.assertNotIn("Manifest", dev)

    def test_wsgi_entrypoint_for_vercel(self):
        self.assertEqual(settings.WSGI_APPLICATION, "config.wsgi.application")
        wsgi = importlib.import_module("config.wsgi")
        self.assertTrue(callable(wsgi.application))


class EnableRlsMigrationTests(SimpleTestCase):
    migration = importlib.import_module("polls.migrations.0002_enable_rls")

    def make_schema_editor(self, vendor, tables):
        connection = mock.MagicMock()
        connection.vendor = vendor
        connection.introspection.table_names.return_value = tables
        connection.ops.quote_name.side_effect = lambda name: f'"{name}"'
        cursor = connection.cursor.return_value.__enter__.return_value
        return mock.Mock(connection=connection), cursor

    def test_enables_rls_on_every_table_in_postgres(self):
        editor, cursor = self.make_schema_editor("postgresql", ["accounts_user", "polls_poll", "django_session"])
        self.migration.enable_rls(None, editor)
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertEqual(
            statements,
            [
                'ALTER TABLE "accounts_user" ENABLE ROW LEVEL SECURITY',
                'ALTER TABLE "polls_poll" ENABLE ROW LEVEL SECURITY',
                'ALTER TABLE "django_session" ENABLE ROW LEVEL SECURITY',
            ],
        )

    def test_reverse_disables_rls(self):
        editor, cursor = self.make_schema_editor("postgresql", ["polls_poll"])
        self.migration.disable_rls(None, editor)
        cursor.execute.assert_called_once_with('ALTER TABLE "polls_poll" DISABLE ROW LEVEL SECURITY')

    def test_noop_on_sqlite(self):
        editor, cursor = self.make_schema_editor("sqlite", ["polls_poll"])
        self.migration.enable_rls(None, editor)
        cursor.execute.assert_not_called()

    def test_migration_depends_on_all_apps_that_create_tables(self):
        deps = {app for app, _ in self.migration.Migration.dependencies}
        self.assertTrue({"polls", "accounts", "admin", "auth", "contenttypes", "sessions"} <= deps)
