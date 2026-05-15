"""紅色測試 — --summary-only 旗標 (批次模式只產彙總、不產個別 session .md).

PT 跑週報時可能只想看「整批彙總 + 學員 trend」,個別 session 已經在
日常 LINE 給學員了不需重複。--summary-only 跳過個別 .md 寫入,只保留:
- _batch_summary.md
- _student_<name>.md (per unique student)

Pass 1 (parse) 仍跑,因為彙總需要;只是 Pass 2 (per-session render+write)
被略過。
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


def _seed(input_dir: Path, names: list[str]) -> None:
    for stem, name in zip(("aming", "wang"), names):
        payload = json.loads(json.dumps(SAMPLE_PAYLOAD))
        payload["student"]["name"] = name
        (input_dir / f"{stem}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class TestSummaryOnlyFlag(unittest.TestCase):
    def test_summary_only_skips_per_session_md(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--summary-only"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            # per-session .md 不該存在
            self.assertFalse((Path(out_td) / "aming.md").exists())
            self.assertFalse((Path(out_td) / "wang.md").exists())

    def test_summary_only_still_produces_batch_summary(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--summary-only"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertTrue((Path(out_td) / "_batch_summary.md").exists())

    def test_summary_only_still_produces_student_trends(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--summary-only"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertTrue((Path(out_td) / "_student_林阿明.md").exists())
            self.assertTrue((Path(out_td) / "_student_王小華.md").exists())

    def test_default_behavior_unchanged_without_flag(self) -> None:
        # 沒給 --summary-only → per-session .md 該存在 (向後相容)
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertTrue((Path(out_td) / "aming.md").exists())
            self.assertTrue((Path(out_td) / "wang.md").exists())
            self.assertTrue((Path(out_td) / "_batch_summary.md").exists())

    def test_summary_only_stderr_includes_info_message(self) -> None:
        # 該印 info 告知略過個別 session,讓 PT 知道是否設錯旗標
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明"])
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--summary-only"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertIn("--summary-only", r.stderr)


if __name__ == "__main__":
    unittest.main()
