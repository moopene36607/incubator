"""紅色測試 — `--batch-line` 批次模式每堂同時產 LINE 純文字版.

批次模式目前每堂產 .md (+ .one_liner.txt 短摘要),但 PT 真正要貼進 LINE
給學員的是「完整 LINE 純文字報告」(render_line_friendly 的輸出)。目前那只
能在單堂模式用 --out-line 拿到。本輪加 --batch-line,與 --batch-html /
--batch-csv 平行,每堂寫一份 <stem>.line.txt。
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


def _write_inputs(in_dir: Path, n: int) -> None:
    for i in range(1, n + 1):
        p = json.loads(json.dumps(SAMPLE_PAYLOAD))
        p["student"]["name"] = f"Stu{i}"
        p["session"]["session_no"] = i
        p["session"]["date"] = f"2026-05-1{i}"
        (in_dir / f"s{i}.json").write_text(
            json.dumps(p, ensure_ascii=False), encoding="utf-8")


class TestBatchLineFlag(unittest.TestCase):
    def test_batch_line_writes_line_txt_per_session(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _write_inputs(Path(in_td), 2)
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--batch-line"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            out = Path(out_td)
            self.assertTrue((out / "s1.line.txt").exists())
            self.assertTrue((out / "s2.line.txt").exists())

    def test_line_txt_has_line_friendly_format(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _write_inputs(Path(in_td), 1)
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--batch-line"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "s1.line.txt").read_text(encoding="utf-8")
            # LINE 版特徵:emoji 分隔線 + 課後報告字樣
            self.assertIn("課後報告", content)
            self.assertIn("━", content)
            # 不該有 markdown 粗體標記
            self.assertNotIn("**", content)

    def test_no_batch_line_flag_no_line_txt(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _write_inputs(Path(in_td), 1)
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse((Path(out_td) / "s1.line.txt").exists())

    def test_batch_line_respects_summary_only(self) -> None:
        # --summary-only 跳過個別 session → 也不該產 .line.txt
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _write_inputs(Path(in_td), 1)
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--batch-line",
                 "--summary-only"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse((Path(out_td) / "s1.line.txt").exists())


if __name__ == "__main__":
    unittest.main()
