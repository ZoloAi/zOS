# zOS/tests/test_postgresql_adapter.py
"""First pins for the PostgreSQL adapter (it shipped with ZERO tests).

Two layers, same philosophy as test_sqlite_default_quoting.py:

  · Builder pins — the SQL-string functions are pure; assert the statements
    they emit. The first suite-writing pass already found one real bug:
    _build_field_definitions silently DROPPED `default:` (a `default: viewer`
    column landed with no default at all), and the temporal `now` footgun
    (a quoted 'now' is parsed ONCE at CREATE TABLE, freezing that instant
    into every future row — the keyword CURRENT_TIMESTAMP is the fix).

  · Live pins — the emitted SQL executed against a REAL local Postgres
    (skipped cleanly when no server answers), in a disposable schema that is
    dropped in teardown. sqlite's :memory: equivalent for this backend.

Run:  python3 -m pytest tests/test_postgresql_adapter.py
"""

import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from L3_Abstraction.m_zData.zData_modules.shared.backends.postgresql_adapter import (  # noqa: E402
    PostgreSQLAdapter,
)

try:
    import psycopg2
    _PG_URL = dict(host=os.environ.get("ZOS_TEST_PG_HOST", "localhost"),
                   port=int(os.environ.get("ZOS_TEST_PG_PORT", "5432")),
                   user=os.environ.get("ZOS_TEST_PG_USER", os.environ.get("USER", "postgres")),
                   dbname=os.environ.get("ZOS_TEST_PG_DB", "postgres"))
    try:
        _probe = psycopg2.connect(connect_timeout=2, **_PG_URL)
        _probe.close()
        _PG_ALIVE = True
    except Exception:  # pylint: disable=broad-except
        _PG_ALIVE = False
except ImportError:
    psycopg2 = None
    _PG_ALIVE = False


def _adapter():
    # Builders are pure string functions — no connection needed.
    a = PostgreSQLAdapter.__new__(PostgreSQLAdapter)
    return a


SCHEMA = {
    "id": {"type": "int", "pk": True},
    "username": {"type": "str", "required": True, "unique": True},
    "role": {"type": "str", "default": "viewer"},
    "email": {"type": "str", "default": ""},
    "score": {"type": "int", "default": 0},
    "active": {"type": "bool", "default": True},
    "created_at": {"type": "datetime", "default": "now"},
}


class TestFieldDefinitionBuilders(unittest.TestCase):

    def setUp(self):
        self.a = _adapter()

    def _defs(self, schema=None):
        field_defs, _fks = self.a._build_field_definitions(schema or SCHEMA, None)
        return {d.split(" ", 1)[0]: d for d in field_defs}

    def test_int_pk_becomes_serial(self):
        self.assertIn("SERIAL PRIMARY KEY", self._defs()["id"])

    def test_string_default_is_quoted_literal(self):
        # THE bug this suite was written against: default: was dropped whole.
        self.assertIn("DEFAULT 'viewer'", self._defs()["role"])

    def test_empty_string_default_survives(self):
        self.assertIn("DEFAULT ''", self._defs()["email"])

    def test_numeric_default_stays_bare(self):
        self.assertTrue(self._defs()["score"].endswith("DEFAULT 0"))

    def test_bool_default_is_keyword(self):
        self.assertTrue(self._defs()["active"].endswith("DEFAULT TRUE"))

    def test_temporal_now_is_current_timestamp(self):
        # A quoted 'now' freezes CREATE TABLE time into every future row.
        d = self._defs()["created_at"]
        self.assertIn("DEFAULT CURRENT_TIMESTAMP", d)
        self.assertNotIn("'now'", d)

    def test_string_now_stays_a_literal(self):
        # Only TEMPORAL types get the keyword; a str column saying "now"
        # means the word.
        d = self._defs({"note": {"type": "str", "default": "now"}})
        self.assertIn("DEFAULT 'now'", d["note"])

    def test_required_and_unique_still_emitted(self):
        d = self._defs()["username"]
        self.assertIn("UNIQUE", d)
        self.assertIn("NOT NULL", d)

    def test_add_column_string_default_quoted(self):
        sql = self.a._build_add_column_sql(
            "Users", "email", {"type": "str", "default": ""})
        self.assertTrue(sql.endswith("DEFAULT ''"), sql)

    def test_add_column_temporal_now_keyword(self):
        sql = self.a._build_add_column_sql(
            "Users", "seen_at", {"type": "datetime", "default": "now"})
        self.assertTrue(sql.endswith("DEFAULT CURRENT_TIMESTAMP"), sql)

    def test_quote_in_default_escaped(self):
        sql = self.a._build_add_column_sql(
            "Users", "label", {"type": "str", "default": "it's"})
        self.assertIn("DEFAULT 'it''s'", sql)


@unittest.skipUnless(_PG_ALIVE, "no local PostgreSQL answering — live pins skipped")
class TestLiveAgainstPostgres(unittest.TestCase):
    """The emitted SQL, executed for real — a disposable schema per run."""

    @classmethod
    def setUpClass(cls):
        cls.schema_name = f"zos_test_{uuid.uuid4().hex[:8]}"
        cls.conn = psycopg2.connect(**_PG_URL)
        cls.conn.autocommit = True
        with cls.conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {cls.schema_name}")
            cur.execute(f"SET search_path TO {cls.schema_name}")

    @classmethod
    def tearDownClass(cls):
        with cls.conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA {cls.schema_name} CASCADE")
        cls.conn.close()

    def _cur(self):
        cur = self.conn.cursor()
        cur.execute(f"SET search_path TO {self.schema_name}")
        return cur

    def test_create_table_from_schema_executes(self):
        a = _adapter()
        field_defs, fks = a._build_field_definitions(SCHEMA, None)
        sql = f"CREATE TABLE users_t ({', '.join(field_defs + fks)})"
        with self._cur() as cur:
            cur.execute(sql)
            # DB-backstop defaults actually fire:
            cur.execute("INSERT INTO users_t (username) VALUES ('gal') "
                        "RETURNING role, email, score, active, created_at")
            role, email, score, active, created = cur.fetchone()
        self.assertEqual((role, email, score, active), ("viewer", "", 0, True))
        self.assertIsNotNone(created)

    def test_two_inserts_get_distinct_serial_ids(self):
        a = _adapter()
        field_defs, _ = a._build_field_definitions(
            {"id": {"type": "int", "pk": True},
             "name": {"type": "str", "default": ""}}, None)
        with self._cur() as cur:
            cur.execute(f"CREATE TABLE serial_t ({', '.join(field_defs)})")
            cur.execute("INSERT INTO serial_t (name) VALUES ('a') RETURNING id")
            first = cur.fetchone()[0]
            cur.execute("INSERT INTO serial_t (name) VALUES ('b') RETURNING id")
            second = cur.fetchone()[0]
        self.assertEqual((first, second), (1, 2))

    def test_add_column_with_empty_default_executes(self):
        a = _adapter()
        with self._cur() as cur:
            cur.execute("CREATE TABLE alter_t (id SERIAL PRIMARY KEY)")
            cur.execute(a._build_add_column_sql(
                "alter_t", "email", {"type": "str", "default": ""}))
            cur.execute("INSERT INTO alter_t DEFAULT VALUES RETURNING email")
            self.assertEqual(cur.fetchone()[0], "")

    def test_bare_word_default_would_have_died_here(self):
        # The zOS#14 failure shape on Postgres: an UNQUOTED string default
        # reads as a column reference and CREATE TABLE refuses. Pins WHY the
        # shared formatter exists.
        with self._cur() as cur:
            with self.assertRaises(Exception):
                cur.execute("CREATE TABLE bad_t (role TEXT DEFAULT viewer)")

    def test_temporal_now_default_is_live_not_frozen(self):
        a = _adapter()
        field_defs, _ = a._build_field_definitions(
            {"id": {"type": "int", "pk": True},
             "created_at": {"type": "datetime", "default": "now"}}, None)
        with self._cur() as cur:
            cur.execute(f"CREATE TABLE now_t ({', '.join(field_defs)})")
            cur.execute("SELECT pg_get_expr(d.adbin, d.adrelid) "
                        "FROM pg_attrdef d JOIN pg_attribute a "
                        "  ON a.attrelid = d.adrelid AND a.attnum = d.adnum "
                        "WHERE d.adrelid = 'now_t'::regclass "
                        "  AND a.attname = 'created_at'")
            expr = cur.fetchone()[0]
        # The stored default is the FUNCTION, not a frozen timestamp literal.
        self.assertIn("CURRENT_TIMESTAMP", expr.upper())


if __name__ == "__main__":
    unittest.main()
