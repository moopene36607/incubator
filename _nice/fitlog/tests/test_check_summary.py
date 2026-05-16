"""紅色測試 — --check 結尾印總結統計行.

--check 每檔印 PASS/FAIL,但批次驗 20 檔時,PT 想一眼知道「幾檔過、
幾檔錯」。本輪在 --check 結尾加一行總結:「N 檔:X PASS / Y FAIL」。
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


class TestCheckSummaryLine(unittest.TestCase):
    def test_batch_check_prints_summary(self) -> None:
        with TemporaryDirectory() as td:
            # 2 好 1 壞
            for i in range(1, 3):
                p = json.loads(json.dumps(SAMPLE_PAYLOAD))
                p["student"]["name"] = f"Stu{i}"
                p["session"]["session_no"] = i
                (Path(td) / f"good{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            bad = json.loads(json.dumps(SAMPLE_PAYLOAD))
            del bad["session"]["sets"]
            (Path(td) / "bad.json").write_text(
                json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", td, "--check"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            combined = r.stdout + r.stderr
            # 總結行該含 3 檔、PASS 與 FAIL 數
            self.assertIn("3", combined)
            self.assertIn("2 PASS", combined)
            self.assertIn("1 FAIL", combined)

    def test_all_pass_summary(self) -> None:
        with TemporaryDirectory() as td:
            for i in range(1, 4):
                p = json.loads(json.dumps(SAMPLE_PAYLOAD))
                p["session"]["session_no"] = i
                (Path(td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", td, "--check"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("3 PASS", r.stdout + r.stderr)

    def test_single_file_check_summary(self) -> None:
        with TemporaryDirectory() as td:
            p = Path(td) / "in.json"
            p.write_text(json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                         encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(p), "--check"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("1 PASS", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
