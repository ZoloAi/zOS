# zOS/tests/test_csv_adapter_bugs.py
"""CSV adapter field bugs — zOS#59 (dtype clash on update) + zOS#58 (auto-provision).

#59: a digits-only form string arrives at the adapter as int (the token-injection
round trip drops the quotes on numeric-looking text). pandas' string dtype — the
`str` default read_csv infers from pandas 3 — REJECTS non-string scalars at .loc
assignment (`TypeError: Invalid value '182' for dtype 'str'`). Pins
_dtype_safe_assignment: non-string scalar → string column stores str(value);
the pre-existing str → numeric-column object relaxation is unchanged.

#58: DataFacade.insert into a not-yet-created table raised FileNotFoundError
while the declarative zData path provisioned from schema. Pins _load_table's
auto-provision (schema registered → create + proceed; no schema → still loud).
"""
# pylint: disable=protected-access
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends.csv_helpers import (  # noqa: E402
    dml_operations as dml_ops,
)
from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends.csv_adapter import (  # noqa: E402
    CSVAdapter,
)


def _string_col_df():
    """A df whose text column carries pandas' strict string dtype (the shape
    read_csv produces by default from pandas 3 — assignment of an int raises)."""
    return pd.DataFrame({
        "id": pd.array([1, 2], dtype="Int64"),
        "id_number": pd.array(["׳009217142", "x55"], dtype="string"),
    })


class TestDtypeSafeUpdate(unittest.TestCase):
    """zOS#59 — update() must not let a value's Python type fight the column dtype."""

    def _update(self, df, fields, values, where):
        store = {}
        return dml_ops.update(
            table="people", fields=fields, values=values, where=where,
            load_table_func=lambda t: df,
            save_table_func=lambda t, d: store.__setitem__(t, d),
            tables_cache={}, logger=None,
        ), df

    def test_int_into_string_column_stores_string_form(self):
        df = _string_col_df()
        affected, df = self._update(df, ["id_number"], [182], {"id": 1})
        self.assertEqual(affected, 1)
        self.assertEqual(df.loc[df["id"] == 1, "id_number"].iloc[0], "182")

    def test_multi_field_update_with_mixed_types(self):
        # The field report only saw the crash on multi-field saves — pin that shape.
        df = _string_col_df()
        df["age"] = pd.array([30, 40], dtype="Int64")
        affected, df = self._update(
            df, ["id_number", "age"], [182, 31], {"id": 1}
        )
        self.assertEqual(affected, 1)
        self.assertEqual(df.loc[df["id"] == 1, "id_number"].iloc[0], "182")
        self.assertEqual(int(df.loc[df["id"] == 1, "age"].iloc[0]), 31)

    def test_str_into_numeric_column_keeps_object_relaxation(self):
        # Pre-existing guard direction: a str landing in an Int64 column relaxes
        # the column to object rather than raising.
        df = _string_col_df()
        affected, df = self._update(df, ["id"], ["not-a-number"], {"id_number": "x55"})
        self.assertEqual(affected, 1)
        self.assertEqual(df["id"].dtype, object)

    def test_none_into_string_column_stays_missing(self):
        df = _string_col_df()
        affected, df = self._update(df, ["id_number"], [None], {"id": 1})
        self.assertEqual(affected, 1)
        self.assertTrue(pd.isna(df.loc[df["id"] == 1, "id_number"].iloc[0]))

    def test_upsert_update_branch_coerces_too(self):
        df = _string_col_df()
        store = {}
        dml_ops.upsert(
            table="people", fields=["id", "id_number"], values=[1, 182],
            conflict_fields=["id"],
            load_table_func=lambda t: df,
            save_table_func=lambda t, d: store.__setitem__(t, d),
            tables_cache={}, logger=None,
        )
        saved = store["people"]
        self.assertEqual(saved.loc[saved["id"] == 1, "id_number"].iloc[0], "182")


class TestInsertAutoProvision(unittest.TestCase):
    """zOS#58 — plugin-door insert provisions a schema-registered table like the form door."""

    def _adapter(self, tmpdir):
        adapter = CSVAdapter({"db_path": tmpdir}, logger=MagicMock())
        adapter.base_path = Path(tmpdir)
        adapter.connect()
        return adapter

    def test_insert_into_missing_table_provisions_from_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            adapter.register_schema("guests", {
                "id": {"type": "int", "auto_increment": True},
                "name": {"type": "str"},
            })
            row_id = adapter.insert("guests", ["name"], ["Alice"])
            self.assertEqual(row_id, 1)
            self.assertTrue((Path(tmp) / "guests.csv").exists())
            rows = adapter.select("guests")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "Alice")

    def test_missing_table_without_schema_still_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            with self.assertRaises(FileNotFoundError):
                adapter.insert("tpyo_table", ["name"], ["Bob"])

    def test_select_on_missing_schema_table_returns_empty(self):
        # Parity with the declarative path, which ensure_tables()-creates even
        # before a read — a facade upsert's probing select no longer crashes.
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            adapter.register_schema("events", {"id": {"type": "int"}, "kind": {"type": "str"}})
            self.assertEqual(adapter.select("events"), [])


if __name__ == "__main__":
    unittest.main()
