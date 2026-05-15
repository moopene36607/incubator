"""紅色測試 — CSV BOM (UTF-8 byte order mark) for Excel 相容性.

台灣 PT 多在 Windows + Excel 環境。Excel 開沒 BOM 的 UTF-8 CSV 會把
中文當 Big5 解 → 亂碼:陳美玉 → 闃ぐ縐.

本輪在 write_session_csv / write_batch_csv 加 with_bom=False 參數
(default 不寫 BOM 維持向後相容),CLI 提供 --csv-bom 旗標開啟。
有了 BOM,Excel 2007+ 會正確以 UTF-8 解析。

BOM 的位元組是 \\xef\\xbb\\xbf (U+FEFF UTF-8 編碼)。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from csv_export import write_batch_csv, write_session_csv  # noqa: E402
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)

UTF8_BOM = b"\xef\xbb\xbf"


def _make_session() -> SessionInput:
    return SessionInput(
        student_name="陳美玉", student_age=30, student_goal="",
        session_no=1, session_date="2026-05-15", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=1,
                        reps_or_duration="8", weight_kg=50.0, rpe=7)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestSessionCsvBomFlag(unittest.TestCase):
    def test_default_no_bom_backward_compat(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "out.csv"
            write_session_csv(_make_session(), path)
            data = path.read_bytes()
            self.assertFalse(data.startswith(UTF8_BOM))

    def test_with_bom_true_writes_bom(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "out.csv"
            write_session_csv(_make_session(), path, with_bom=True)
            data = path.read_bytes()
            self.assertTrue(data.startswith(UTF8_BOM))

    def test_content_after_bom_still_valid(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "out.csv"
            write_session_csv(_make_session(), path, with_bom=True)
            data = path.read_bytes()
            # 移除 BOM 後仍是正常 UTF-8 CSV
            content = data[len(UTF8_BOM):].decode("utf-8")
            self.assertIn("date,student_name", content)
            self.assertIn("陳美玉", content)


class TestBatchCsvBomFlag(unittest.TestCase):
    def test_default_no_bom(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "_batch.csv"
            write_batch_csv([_make_session()], path)
            data = path.read_bytes()
            self.assertFalse(data.startswith(UTF8_BOM))

    def test_with_bom_true_writes_bom(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "_batch.csv"
            write_batch_csv([_make_session()], path, with_bom=True)
            data = path.read_bytes()
            self.assertTrue(data.startswith(UTF8_BOM))


class TestCliCsvBomFlag(unittest.TestCase):
    def test_single_csv_with_bom_flag(self) -> None:
        with TemporaryDirectory() as td:
            in_path = Path(td) / "in.json"
            in_path.write_text(
                json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                encoding="utf-8",
            )
            csv_path = Path(td) / "out.csv"
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(in_path),
                 "--csv", str(csv_path), "--csv-bom", "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            data = csv_path.read_bytes()
            self.assertTrue(data.startswith(UTF8_BOM),
                            f"CSV should start with BOM, got first 10 bytes: {data[:10]!r}")

    def test_batch_csv_with_bom_flag(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            p = json.loads(json.dumps(SAMPLE_PAYLOAD))
            p["session"]["session_no"] = 1
            (Path(in_td) / "s1.json").write_text(
                json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--batch-csv", "--csv-bom", "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            data = (Path(out_td) / "_batch.csv").read_bytes()
            self.assertTrue(data.startswith(UTF8_BOM))


if __name__ == "__main__":
    unittest.main()
