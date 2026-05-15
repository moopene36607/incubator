"""紅色測試 — --batch-html 旗標 (批次模式同時產出 .md + .html).

Round 36 加單堂 --html。本輪批次也支援:--batch-html 後每堂 session
產出 student.md + student.html (同 stem),PT 一次跑出能 LINE 分享 +
留檔的雙份報告。
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


def _run_batch(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "fitlog.py", *args],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )


class TestBatchHtmlFlag(unittest.TestCase):
    def test_batch_html_produces_html_per_session(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            r = _run_batch("--batch", in_td, "--out-dir", out_td,
                           "--no-ai", "--batch-html")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(out_td) / "aming.html").exists())
            self.assertTrue((Path(out_td) / "wang.html").exists())
            # .md 也該還在 (不是替代)
            self.assertTrue((Path(out_td) / "aming.md").exists())

    def test_batch_html_content_is_valid_html(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            _run_batch("--batch", in_td, "--out-dir", out_td,
                       "--no-ai", "--batch-html")
            content = (Path(out_td) / "aming.html").read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("林阿明", content)
            self.assertIn("<table>", content)

    def test_no_batch_html_default_no_html_files(self) -> None:
        # 沒給 --batch-html → 不該產 .html (向後相容)
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            _run_batch("--batch", in_td, "--out-dir", out_td, "--no-ai")
            self.assertFalse((Path(out_td) / "aming.html").exists())
            self.assertFalse((Path(out_td) / "wang.html").exists())

    def test_batch_html_writes_alongside_md_without_out_dir(self) -> None:
        # 沒 --out-dir 時 .html 該寫在原 .json 旁
        with TemporaryDirectory() as in_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            _run_batch("--batch", in_td, "--no-ai", "--batch-html")
            self.assertTrue((Path(in_td) / "aming.html").exists())
            self.assertTrue((Path(in_td) / "wang.html").exists())

    def test_summary_only_with_batch_html_skips_per_session(self) -> None:
        # --summary-only 跳 per-session → 即使 --batch-html 也不該產個別 .html
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            _run_batch("--batch", in_td, "--out-dir", out_td,
                       "--no-ai", "--batch-html", "--summary-only")
            self.assertFalse((Path(out_td) / "aming.html").exists())
            # .md 也該不在 (summary-only 已跳)
            self.assertFalse((Path(out_td) / "aming.md").exists())


if __name__ == "__main__":
    unittest.main()
