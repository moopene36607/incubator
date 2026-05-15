"""紅色測試 — `--student NAME` 批次模式只跑指定學員.

PT 工作室 20 個學員時,每改一份 JSON 就要重跑整批太慢。本輪加
`--student 林阿明` 旗標讓 batch 只渲染該學員的 sessions + trend +
batch_summary 只含他的資料。其他學員的 .json 直接 skip。

純 CLI 增強,沒有新的純函式 (filter 用 list comprehension 即可)。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _write_session(in_dir: Path, fname: str, student: str, sno: int,
                   date: str) -> None:
    p = json.loads(json.dumps(SAMPLE_PAYLOAD))
    p["student"]["name"] = student
    p["session"]["session_no"] = sno
    p["session"]["date"] = date
    (in_dir / fname).write_text(
        json.dumps(p, ensure_ascii=False), encoding="utf-8")


class TestStudentFilterFlag(unittest.TestCase):
    def test_only_matching_student_session_md_written(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            in_dir = Path(in_td)
            _write_session(in_dir, "s1.json", "林阿明", 1, "2026-05-11")
            _write_session(in_dir, "s2.json", "王小華", 1, "2026-05-12")
            _write_session(in_dir, "s3.json", "林阿明", 2, "2026-05-13")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--student", "林阿明"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            out_dir = Path(out_td)
            # 林阿明 的 s1.md / s3.md 存在
            self.assertTrue((out_dir / "s1.md").exists())
            self.assertTrue((out_dir / "s3.md").exists())
            # 王小華 的 s2.md 不存在 (被 filter 掉)
            self.assertFalse((out_dir / "s2.md").exists())

    def test_only_matching_student_trend_md_written(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            in_dir = Path(in_td)
            _write_session(in_dir, "s1.json", "林阿明", 1, "2026-05-11")
            _write_session(in_dir, "s2.json", "王小華", 1, "2026-05-12")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--student", "林阿明"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            out_dir = Path(out_td)
            self.assertTrue((out_dir / "_student_林阿明.md").exists())
            self.assertFalse((out_dir / "_student_王小華.md").exists())

    def test_batch_summary_excludes_other_students(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            in_dir = Path(in_td)
            _write_session(in_dir, "s1.json", "林阿明", 1, "2026-05-11")
            _write_session(in_dir, "s2.json", "王小華", 1, "2026-05-12")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--student", "林阿明"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_batch_summary.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("林阿明", content)
            self.assertNotIn("王小華", content)

    def test_unknown_student_results_in_zero_sessions_warning(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            in_dir = Path(in_td)
            _write_session(in_dir, "s1.json", "林阿明", 1, "2026-05-11")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--student", "不存在的人"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            # 沒匹配的學員 → 正常退出 0,但 stderr 提醒
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("不存在的人", r.stderr)
            # 沒任何 session 被處理 → 沒 _batch_summary.md (沒資料可彙)
            self.assertFalse((Path(out_td) / "_batch_summary.md").exists())

    def test_no_student_flag_keeps_default_behavior(self) -> None:
        # 沒帶 --student → 全跑 (確認向後相容)
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            in_dir = Path(in_td)
            _write_session(in_dir, "s1.json", "林阿明", 1, "2026-05-11")
            _write_session(in_dir, "s2.json", "王小華", 1, "2026-05-12")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            out_dir = Path(out_td)
            self.assertTrue((out_dir / "s1.md").exists())
            self.assertTrue((out_dir / "s2.md").exists())


if __name__ == "__main__":
    unittest.main()
