"""紅色測試 — --batch-csv 旗標把多堂 sessions 合併成一份大 CSV.

單堂 --csv 已存在 (Excel-friendly),但 PT 跑完一週 6-8 堂後,想把整批 sessions
一次拉進 Excel / Sheets 做 pivot,目前要手動 concat 各檔。本輪加 --batch-csv
旗標,在 _batch_summary.md 旁同步寫一份 _batch.csv (所有學員所有 sets 串接,
header 共用)。

純函式:format_batch_csv_rows(sessions) — 同 sessions 順序逐一展開,單一 header
在最頂端。空 sessions → 只回 header。
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from csv_export import CSV_HEADER, format_batch_csv_rows, write_batch_csv  # noqa: E402
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, session_no: int, date: str,
          sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, sets: int, reps: str, weight: float | None,
         rpe: int | None = None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=rpe)


class TestFormatBatchCsvRows(unittest.TestCase):
    def test_empty_sessions_returns_header_only(self) -> None:
        rows = format_batch_csv_rows([])
        self.assertEqual(rows, [list(CSV_HEADER)])

    def test_single_session_matches_single_csv_layout(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("BENCH_PRESS", 4, "8", 50.0, rpe=7)])
        rows = format_batch_csv_rows([sess])
        # header + 1 data row
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], list(CSV_HEADER))
        self.assertEqual(rows[1][1], "林阿明")
        self.assertEqual(rows[1][4], "BENCH_PRESS")
        self.assertEqual(rows[1][10], "50")  # weight 整數

    def test_multi_sessions_rows_concatenated_in_order(self) -> None:
        a = _make("林阿明", 1, "2026-05-10",
                  [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("王小華", 2, "2026-05-11",
                  [_set("BB_BACK_SQUAT", 3, "5", 60.0),
                   _set("PULL_UP", 3, "8", None)])
        rows = format_batch_csv_rows([a, b])
        # header + 1 + 2 = 4
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[1][1], "林阿明")
        self.assertEqual(rows[2][1], "王小華")
        self.assertEqual(rows[3][1], "王小華")
        # set_index 每個 session 從 1 開始 reset
        self.assertEqual(rows[1][3], "1")
        self.assertEqual(rows[2][3], "1")
        self.assertEqual(rows[3][3], "2")

    def test_bw_weight_renders_empty_string(self) -> None:
        sess = _make("王小華", 1, "2026-05-11",
                     [_set("PULL_UP", 3, "8", None)])
        rows = format_batch_csv_rows([sess])
        self.assertEqual(rows[1][10], "")
        # tonnage 0
        self.assertEqual(rows[1][12], "0")


class TestWriteBatchCsv(unittest.TestCase):
    def test_writes_utf8_csv_round_trip(self) -> None:
        a = _make("林阿明", 1, "2026-05-10",
                  [_set("BENCH_PRESS", 4, "8", 47.5, rpe=7)])
        b = _make("王小華", 2, "2026-05-11",
                  [_set("BB_BACK_SQUAT", 3, "5", 60.0)])
        with TemporaryDirectory() as td:
            csv_path = Path(td) / "_batch.csv"
            write_batch_csv([a, b], csv_path)
            self.assertTrue(csv_path.exists())
            text = csv_path.read_text(encoding="utf-8")
            reader = csv.reader(StringIO(text))
            rows = list(reader)
            self.assertEqual(rows[0], list(CSV_HEADER))
            self.assertEqual(rows[1][1], "林阿明")
            self.assertEqual(rows[1][10], "47.5")  # 非整數保留一位小數
            self.assertEqual(rows[2][1], "王小華")


class TestCliBatchCsvFlag(unittest.TestCase):
    def test_batch_csv_flag_writes_batch_csv_file(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, w in enumerate([45.0, 50.0], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                for s in p["session"]["sets"]:
                    if s["exercise_code"] == "BENCH_PRESS":
                        s["weight_kg"] = w
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--batch-csv"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            csv_path = Path(out_td) / "_batch.csv"
            self.assertTrue(csv_path.exists(),
                            f"_batch.csv not written. stdout={r.stdout}")
            content = csv_path.read_text(encoding="utf-8")
            # 至少含 header + 一筆 BENCH_PRESS
            self.assertIn("date,student_name", content)
            self.assertIn("BENCH_PRESS", content)
            self.assertIn("林阿明", content)


if __name__ == "__main__":
    unittest.main()
