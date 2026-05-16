"""紅色測試 — csv_export.format_session_csv_rows + write_session_csv.

PT 把多堂課的訓練紀錄帶進 Excel/Google Sheets 是業界標準做法 (做學員
進步 dashboard / 一年總噸位曲線 / 對外報稅單)。fitlog 必須支援
匯出單堂課 CSV,才能讓 PT 在 fitlog 之外做進階分析。

每筆 set 一行,加 header 一行;欄位設計要 Excel-friendly
(date 欄是 ISO、數值欄是純數字、無 markdown 符號)。
"""
from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from csv_export import format_session_csv_rows, write_session_csv  # noqa: E402
from fitlog import parse_payload  # noqa: E402


def _load_sample():
    p = Path(__file__).resolve().parent.parent / "samples" / "sample_input.json"
    return parse_payload(json.loads(p.read_text(encoding="utf-8")))


EXPECTED_HEADER = [
    "date",
    "student_name",
    "session_no",
    "set_index",
    "exercise_code",
    "exercise_zh",
    "exercise_en",
    "category",
    "sets",
    "reps_or_duration",
    "weight_kg",
    "rpe",
    "tonnage_kg",
    "note",
    "bodyweight_kg",
]


class TestFormatSessionCsvRows(unittest.TestCase):
    def test_first_row_is_header(self) -> None:
        rows = format_session_csv_rows(_load_sample())
        self.assertEqual(rows[0], EXPECTED_HEADER)

    def test_one_row_per_set_plus_header(self) -> None:
        s = _load_sample()
        rows = format_session_csv_rows(s)
        self.assertEqual(len(rows), len(s.sets) + 1)

    def test_set_index_is_one_based(self) -> None:
        rows = format_session_csv_rows(_load_sample())
        # row[1] 是第 1 set; set_index 欄是 row[1][3]
        self.assertEqual(rows[1][3], "1")
        self.assertEqual(rows[2][3], "2")

    def test_known_exercise_resolves_chinese_and_english_names(self) -> None:
        # sample 第 2 set 是 BB_BACK_SQUAT
        rows = format_session_csv_rows(_load_sample())
        bb_squat_row = rows[2]
        self.assertEqual(bb_squat_row[4], "BB_BACK_SQUAT")
        self.assertEqual(bb_squat_row[5], "槓鈴背蹲舉")
        self.assertEqual(bb_squat_row[6], "Barbell Back Squat")
        self.assertEqual(bb_squat_row[7], "legs")

    def test_unknown_exercise_code_uses_empty_zh_en_category(self) -> None:
        s = _load_sample()
        s.sets[0].exercise_code = "XXX_UNKNOWN_CODE"
        rows = format_session_csv_rows(s)
        first_set_row = rows[1]
        self.assertEqual(first_set_row[4], "XXX_UNKNOWN_CODE")
        self.assertEqual(first_set_row[5], "")  # zh
        self.assertEqual(first_set_row[6], "")  # en
        self.assertEqual(first_set_row[7], "")  # category

    def test_tonnage_column_for_weighted_set(self) -> None:
        # sample 第 2 set: BB_BACK_SQUAT 4 × 10 × 70 = 2800
        rows = format_session_csv_rows(_load_sample())
        self.assertEqual(rows[2][12], "2800")

    def test_tonnage_column_zero_for_bodyweight(self) -> None:
        # sample 第 5 set: PULL_UP 3 × 6 × BW → tonnage = 0
        rows = format_session_csv_rows(_load_sample())
        self.assertEqual(rows[5][12], "0")

    def test_tonnage_column_zero_for_time_based(self) -> None:
        # sample 第 6 set: PLANK 3 × 60 sec → tonnage = 0
        rows = format_session_csv_rows(_load_sample())
        self.assertEqual(rows[6][12], "0")

    def test_weight_kg_empty_for_bodyweight(self) -> None:
        # weight_kg=None → 空字串(讓 Excel 把 BW 當無數值,而不是 0)
        rows = format_session_csv_rows(_load_sample())
        self.assertEqual(rows[5][10], "")  # PULL_UP weight_kg

    def test_weight_kg_drops_decimal_when_integer(self) -> None:
        # 70.0 → "70" (Excel-friendly,不是 "70.0")
        rows = format_session_csv_rows(_load_sample())
        self.assertEqual(rows[2][10], "70")

    def test_weight_kg_keeps_decimal_when_fractional(self) -> None:
        s = _load_sample()
        s.sets[2].weight_kg = 47.5  # bench
        rows = format_session_csv_rows(s)
        self.assertEqual(rows[3][10], "47.5")

    def test_rpe_empty_when_none(self) -> None:
        s = _load_sample()
        s.sets[0].rpe = None
        rows = format_session_csv_rows(s)
        self.assertEqual(rows[1][11], "")

    def test_session_metadata_in_each_row(self) -> None:
        # 每行都帶 date / student / session_no (方便多堂 concat)
        rows = format_session_csv_rows(_load_sample())
        for row in rows[1:]:
            self.assertEqual(row[0], "2026-05-10")
            self.assertEqual(row[1], "林阿明")
            self.assertEqual(row[2], "12")


class TestWriteSessionCsv(unittest.TestCase):
    def test_writes_file_round_trips_via_csv_reader(self) -> None:
        with TemporaryDirectory() as td:
            out = Path(td) / "out.csv"
            write_session_csv(_load_sample(), out)
            self.assertTrue(out.exists())
            with out.open(encoding="utf-8") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], EXPECTED_HEADER)
            # 6 sets + 1 header = 7 rows
            self.assertEqual(len(rows), 7)

    def test_writes_utf8_handles_chinese_correctly(self) -> None:
        with TemporaryDirectory() as td:
            out = Path(td) / "out.csv"
            write_session_csv(_load_sample(), out)
            content = out.read_text(encoding="utf-8")
            self.assertIn("槓鈴背蹲舉", content)
            self.assertIn("林阿明", content)


class TestCliCsvFlag(unittest.TestCase):
    def test_cli_csv_flag_writes_file(self) -> None:
        import subprocess
        with TemporaryDirectory() as td:
            out = Path(td) / "out.csv"
            project_root = Path(__file__).resolve().parent.parent
            result = subprocess.run(
                [sys.executable, "fitlog.py",
                 "samples/sample_input.json",
                 "--no-ai",
                 "--csv", str(out)],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out.exists())
            with out.open(encoding="utf-8") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], EXPECTED_HEADER)


if __name__ == "__main__":
    unittest.main()
