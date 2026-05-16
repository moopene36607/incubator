"""紅色測試 — schema 驗證 session.date 必須是合法 ISO 日期.

目前 schema 只檢查 date 是「非空字串」。但 '2026/05/15'、'May 15'、
'2026-13-01' 這種會通過 schema,然後在 batch 模式的 compute_training_streak
/ ACWR / weekly tonnage 等 date.fromisoformat 處 **crash (ValueError)**。

本輪在 schema 層擋下:date 必須能被 date.fromisoformat 解析。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schema import validate_payload_schema  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _with_date(date_str: str) -> dict:
    p = json.loads(json.dumps(SAMPLE_PAYLOAD))
    p["session"]["date"] = date_str
    return p


class TestSchemaIsoDate(unittest.TestCase):
    def test_valid_iso_date_passes(self) -> None:
        self.assertEqual(validate_payload_schema(_with_date("2026-05-15")), [])

    def test_slash_date_rejected(self) -> None:
        errors = validate_payload_schema(_with_date("2026/05/15"))
        self.assertTrue(any("date" in e for e in errors))

    def test_text_date_rejected(self) -> None:
        errors = validate_payload_schema(_with_date("May 15 2026"))
        self.assertTrue(any("date" in e for e in errors))

    def test_impossible_date_rejected(self) -> None:
        # 2026-13-01 月份不存在
        errors = validate_payload_schema(_with_date("2026-13-01"))
        self.assertTrue(any("date" in e for e in errors))

    def test_empty_date_still_rejected(self) -> None:
        # 既有「非空字串」檢查不可退化
        errors = validate_payload_schema(_with_date(""))
        self.assertTrue(any("date" in e for e in errors))

    def test_error_message_mentions_iso(self) -> None:
        errors = validate_payload_schema(_with_date("2026/05/15"))
        date_errs = [e for e in errors if "date" in e]
        self.assertTrue(date_errs)
        # 訊息該提示正確格式
        self.assertTrue(any("YYYY-MM-DD" in e or "ISO" in e
                            for e in date_errs))


class TestCliRejectsBadDate(unittest.TestCase):
    def test_batch_skips_bad_date_file_without_crash(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            good = json.loads(json.dumps(SAMPLE_PAYLOAD))
            good["student"]["name"] = "好日期"
            good["session"]["date"] = "2026-05-10"
            (Path(in_td) / "good.json").write_text(
                json.dumps(good, ensure_ascii=False), encoding="utf-8")
            bad = _with_date("2026/05/15")
            bad["student"]["name"] = "壞日期"
            (Path(in_td) / "bad.json").write_text(
                json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            # 不可 crash;壞檔被 schema 擋下跳過,好檔照產
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("date", r.stderr)
            self.assertTrue((Path(out_td) / "good.md").exists())
            self.assertFalse((Path(out_td) / "bad.md").exists())


if __name__ == "__main__":
    unittest.main()
