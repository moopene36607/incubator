"""紅色測試 — CSV 匯出加 bodyweight_kg 欄.

round 49 加了 session.bodyweight_kg。CSV 匯出 (per-set 一行) 還沒帶體重。
補上後 PT 可在 Excel 直接算 per-set 相對肌力 (weight_kg / bodyweight_kg)。

欄位加在最後 (note 之後),避免動到既有欄位索引。沒記體重 → 空字串。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from csv_export import CSV_HEADER, format_session_csv_rows  # noqa: E402
from fitlog import SessionInput, SetRecord  # noqa: E402


def _session(bw: float | None) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=1, session_date="2026-05-15", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=70.0, rpe=8)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
        student_bodyweight_kg=bw,
    )


class TestCsvBodyweightColumn(unittest.TestCase):
    def test_header_has_bodyweight_column(self) -> None:
        self.assertIn("bodyweight_kg", CSV_HEADER)

    def test_bodyweight_is_last_column(self) -> None:
        # 加在最後,既有欄位索引不動
        self.assertEqual(CSV_HEADER[-1], "bodyweight_kg")

    def test_existing_columns_unchanged(self) -> None:
        # weight_kg / tonnage_kg / note 索引不變 (向後相容)
        self.assertEqual(CSV_HEADER.index("weight_kg"), 10)
        self.assertEqual(CSV_HEADER.index("tonnage_kg"), 12)
        self.assertEqual(CSV_HEADER.index("note"), 13)

    def test_row_includes_bodyweight_value(self) -> None:
        rows = format_session_csv_rows(_session(72.0))
        self.assertEqual(rows[0][-1], "bodyweight_kg")  # header
        self.assertEqual(rows[1][-1], "72")  # 整數格式

    def test_no_bodyweight_empty_string(self) -> None:
        rows = format_session_csv_rows(_session(None))
        self.assertEqual(rows[1][-1], "")

    def test_fractional_bodyweight(self) -> None:
        rows = format_session_csv_rows(_session(72.5))
        self.assertEqual(rows[1][-1], "72.5")

    def test_every_row_has_full_width(self) -> None:
        rows = format_session_csv_rows(_session(72.0))
        for r in rows:
            self.assertEqual(len(r), len(CSV_HEADER))


if __name__ == "__main__":
    unittest.main()
