"""紅色測試 — --batch-html 也產 _batch_summary.html + _student_*.html.

Round 37 加 per-session HTML;但 _batch_summary.md / _student_*.md
還沒 HTML 版。本輪補完:--batch-html 後所有 .md 對應的 .html 都該產。
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


class TestBatchHtmlForSummaryAndStudent(unittest.TestCase):
    def test_batch_html_produces_summary_html(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            r = _run_batch("--batch", in_td, "--out-dir", out_td,
                           "--no-ai", "--batch-html")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(out_td) / "_batch_summary.html").exists())

    def test_batch_html_produces_student_html_per_unique_student(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            _run_batch("--batch", in_td, "--out-dir", out_td,
                       "--no-ai", "--batch-html")
            self.assertTrue((Path(out_td) / "_student_林阿明.html").exists())
            self.assertTrue((Path(out_td) / "_student_王小華.html").exists())

    def test_summary_html_content_valid(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            _run_batch("--batch", in_td, "--out-dir", out_td,
                       "--no-ai", "--batch-html")
            content = (Path(out_td) / "_batch_summary.html").read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("批次彙總", content)

    def test_student_html_content_valid(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            _run_batch("--batch", in_td, "--out-dir", out_td,
                       "--no-ai", "--batch-html")
            content = (Path(out_td) / "_student_林阿明.html").read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("林阿明", content)

    def test_no_batch_html_no_summary_html(self) -> None:
        # 無 --batch-html → 不該產 .html (向後相容)
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華"])
            _run_batch("--batch", in_td, "--out-dir", out_td, "--no-ai")
            self.assertFalse((Path(out_td) / "_batch_summary.html").exists())
            self.assertFalse((Path(out_td) / "_student_林阿明.html").exists())


if __name__ == "__main__":
    unittest.main()
