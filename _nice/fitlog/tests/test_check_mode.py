"""紅色測試 — `--check` 驗證 dry-run 模式.

PT 一天 6-8 份 JSON,AI 模式跑下去每份都花 token。本輪加 --check:
只驗 schema + validate_session,印每檔 PASS / FAIL 摘要,**不產任何
報告檔、不呼叫 AI**。PT 可先 --check 確認資料乾淨再正式跑。

支援單檔 (--check input.json) 與批次 (--check --batch DIR)。
有任何檔 schema 錯誤 → exit code 1;全乾淨 → 0。
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


class TestCheckModeSingle(unittest.TestCase):
    def test_good_file_passes(self) -> None:
        with TemporaryDirectory() as td:
            p = Path(td) / "in.json"
            p.write_text(json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                         encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(p), "--check"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            combined = r.stdout + r.stderr
            self.assertIn("PASS", combined)

    def test_bad_schema_file_fails(self) -> None:
        with TemporaryDirectory() as td:
            bad = json.loads(json.dumps(SAMPLE_PAYLOAD))
            del bad["session"]["sets"]
            p = Path(td) / "in.json"
            p.write_text(json.dumps(bad, ensure_ascii=False),
                         encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(p), "--check"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("FAIL", r.stdout + r.stderr)

    def test_check_writes_no_report(self) -> None:
        with TemporaryDirectory() as td:
            p = Path(td) / "in.json"
            p.write_text(json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                         encoding="utf-8")
            subprocess.run(
                [sys.executable, "fitlog.py", str(p), "--check"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            # 不該產出 .md
            self.assertFalse((Path(td) / "in.md").exists())


class TestCheckModeBatch(unittest.TestCase):
    def test_batch_check_reports_each_file(self) -> None:
        with TemporaryDirectory() as td:
            good = json.loads(json.dumps(SAMPLE_PAYLOAD))
            (Path(td) / "good.json").write_text(
                json.dumps(good, ensure_ascii=False), encoding="utf-8")
            bad = json.loads(json.dumps(SAMPLE_PAYLOAD))
            bad["session"]["date"] = "2026/05/15"  # 壞 ISO 日期
            (Path(td) / "bad.json").write_text(
                json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", td, "--check"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 1)
            combined = r.stdout + r.stderr
            self.assertIn("good.json", combined)
            self.assertIn("bad.json", combined)
            self.assertIn("PASS", combined)
            self.assertIn("FAIL", combined)

    def test_batch_check_writes_no_reports(self) -> None:
        with TemporaryDirectory() as td:
            (Path(td) / "s1.json").write_text(
                json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                encoding="utf-8")
            subprocess.run(
                [sys.executable, "fitlog.py", "--batch", td, "--check"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertFalse((Path(td) / "s1.md").exists())
            self.assertFalse((Path(td) / "_batch_summary.md").exists())

    def test_batch_check_all_good_exit_zero(self) -> None:
        with TemporaryDirectory() as td:
            for i in range(1, 3):
                p = json.loads(json.dumps(SAMPLE_PAYLOAD))
                p["session"]["session_no"] = i
                (Path(td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", td, "--check"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
