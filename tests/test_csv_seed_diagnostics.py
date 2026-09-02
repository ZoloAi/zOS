# zOS/tests/test_csv_seed_diagnostics.py
"""zOS#27 — an unquoted comma in a seed CSV names the file, the row, and the fix.

The pandas C-tokenizer error ("Expected 7 fields in line 3, saw 8") named
neither the file, the offending row, nor the cause; the whole reel came back
empty and the visible failure was a blank render layers away. The loader now
re-raises with a full diagnosis.
"""

import tempfile
import unittest
from pathlib import Path

from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends.csv_helpers.file_operations import (
    load_table_from_csv,
)

_HEADER = "id,q,r,terrain,label,difficulty,blurb"
_GOOD_ROW = "1,0,0,water,Deep Lake,1,Still and cold."
_BAD_ROW = "2,1,0,grass,Amber Meadow,2,A slope of tall grass gone gold, humming with unseen insects."
_QUOTED_ROW = '2,1,0,grass,Amber Meadow,2,"A slope of tall grass gone gold, humming with unseen insects."'


class TestUnquotedCommaDiagnostic(unittest.TestCase):

    def _write(self, *rows) -> Path:
        tmp = tempfile.NamedTemporaryFile(  # pylint: disable=consider-using-with
            mode="w", suffix=".csv", prefix="tiles_", delete=False, encoding="utf-8"
        )
        tmp.write("\n".join(rows) + "\n")
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        return Path(tmp.name)

    def test_unquoted_comma_names_file_line_and_fix(self):
        path = self._write(_HEADER, _GOOD_ROW, _BAD_ROW)
        with self.assertRaises(ValueError) as ctx:
            load_table_from_csv(path)
        msg = str(ctx.exception)
        self.assertIn(str(path), msg)                      # the file
        self.assertIn("file line 3", msg)                  # the row
        self.assertIn("7 column(s)", msg)                  # schema arity
        self.assertIn("splits into 8", msg)                # what pandas saw
        self.assertIn("UNQUOTED comma", msg)               # the cause
        self.assertIn("double quotes", msg)                # the fix
        self.assertIn("Amber Meadow", msg)                 # the raw offending line

    def test_quoted_prose_loads_clean(self):
        path = self._write(_HEADER, _GOOD_ROW, _QUOTED_ROW)
        df = load_table_from_csv(path)
        self.assertEqual(len(df), 2)
        self.assertIn("humming", df.iloc[1]["blurb"])

    def test_long_offending_line_is_truncated(self):
        long_blurb = "word, " * 100
        path = self._write(_HEADER, _GOOD_ROW, f"2,0,0,grass,Long,1,{long_blurb}")
        with self.assertRaises(ValueError) as ctx:
            load_table_from_csv(path)
        self.assertIn("…", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
