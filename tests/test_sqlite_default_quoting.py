"""Pins for the sqlite ALTER/CREATE default-quoting bug (found 2026-09-07).

zSchema `default: ""` on an added column made the sqlite adapter emit
`ALTER TABLE … ADD COLUMN x TEXT DEFAULT ` — sqlite answers "incomplete
input" and the whole migration dies (while the CLI still printed a success
line — separate issue). The parent SQLAdapter had already been fixed to
quote defaults (zOS#14); the sqlite override carried the same bug
independently. These pins hold BOTH builders to: strings quoted, numbers
bare, empty string a valid '' literal, and the required-without-default
fallback the bare NULL keyword — proven by executing every generated
statement against a real in-memory sqlite.
"""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from L3_Abstraction.m_zData.zData_modules.shared.backends.sqlite_adapter import (  # noqa: E402
    SQLiteAdapter,
)


def _adapter():
    # No connection needed — the builders are pure string functions.
    return SQLiteAdapter.__new__(SQLiteAdapter)


class TestAddColumnDefaults(unittest.TestCase):

    def setUp(self):
        self.a = _adapter()
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE Users (id INTEGER PRIMARY KEY)")

    def _exec(self, sql):
        """The real assertion: sqlite itself accepts the statement."""
        self.db.execute(sql)

    def test_empty_string_default_is_valid_literal(self):
        sql = self.a._build_add_column_sql(
            "Users", "email", {"type": "str", "default": ""})
        self.assertTrue(sql.endswith("DEFAULT ''"), sql)
        self._exec(sql)

    def test_string_default_is_quoted(self):
        sql = self.a._build_add_column_sql(
            "Users", "role", {"type": "str", "default": "viewer"})
        self.assertIn("DEFAULT 'viewer'", sql)
        self._exec(sql)

    def test_numeric_default_stays_bare(self):
        sql = self.a._build_add_column_sql(
            "Users", "score", {"type": "int", "default": 0})
        self.assertTrue(sql.endswith("DEFAULT 0"), sql)
        self._exec(sql)

    def test_required_without_default_falls_back_to_null_keyword(self):
        sql = self.a._build_add_column_sql(
            "Users", "note", {"type": "str", "required": True})
        self.assertTrue(sql.endswith("DEFAULT NULL"), sql)
        self.assertNotIn("'NULL'", sql)
        self._exec(sql)

    def test_required_with_empty_default_quoted(self):
        sql = self.a._build_add_column_sql(
            "Users", "tag", {"type": "str", "required": True, "default": ""})
        self.assertTrue(sql.endswith("DEFAULT ''"), sql)
        self._exec(sql)

    def test_quote_in_default_escaped(self):
        sql = self.a._build_add_column_sql(
            "Users", "label", {"type": "str", "default": "it's"})
        self.assertIn("DEFAULT 'it''s'", sql)
        self._exec(sql)


class TestCreateColumnDefinitionDefaults(unittest.TestCase):

    def test_create_table_empty_default_valid(self):
        a = _adapter()
        col = a._build_column_definition("email", {"type": "str", "default": ""})
        db = sqlite3.connect(":memory:")
        db.execute(f"CREATE TABLE T (id INTEGER PRIMARY KEY, {col})")
        self.assertIn("DEFAULT ''", col)


if __name__ == "__main__":
    unittest.main()
