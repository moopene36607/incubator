"""紅色測試 — 新 session JSON 樣板產生器 (`--template` CLI).

PT 第一次用 fitlog 不知道 JSON 該長怎樣。`--template` 輸出 fillable
樣板 + placeholder 提示,PT 可 `> new.json` 後填寫實際資料。

樣板必須:
- 通過 schema 驗證 (PT 直接拿來填不會 schema error)
- 能被 parse_payload 接收 (符合 SessionInput 形狀)
- 含「請填...」placeholder 提示哪些欄位該換
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import parse_payload  # noqa: E402
from schema import validate_payload_schema  # noqa: E402
from voice import make_blank_session_template  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestMakeBlankSessionTemplate(unittest.TestCase):
    def test_template_passes_schema(self) -> None:
        template = make_blank_session_template()
        self.assertEqual(validate_payload_schema(template), [])

    def test_template_parse_payload_succeeds(self) -> None:
        template = make_blank_session_template()
        sess = parse_payload(template)
        # 至少有一個範例 set 讓 PT 知道格式
        self.assertGreaterEqual(len(sess.sets), 1)

    def test_template_has_required_top_level_keys(self) -> None:
        template = make_blank_session_template()
        for key in ("student", "coach", "session"):
            self.assertIn(key, template)

    def test_template_contains_placeholder_hints(self) -> None:
        # 至少含「請填」字樣讓 PT 知道哪些欄位待填
        template = make_blank_session_template()
        as_json = json.dumps(template, ensure_ascii=False)
        self.assertIn("請填", as_json)

    def test_template_session_date_is_today(self) -> None:
        # date 預設今天讓 PT 不用查日期
        from datetime import date
        template = make_blank_session_template()
        self.assertEqual(template["session"]["date"], date.today().isoformat())


class TestCliTemplateFlag(unittest.TestCase):
    def test_template_flag_outputs_valid_json(self) -> None:
        r = subprocess.run(
            [sys.executable, "fitlog.py", "--template"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        # stdout 該是有效 JSON
        data = json.loads(r.stdout)
        self.assertIn("student", data)
        self.assertIn("session", data)
        self.assertEqual(validate_payload_schema(data), [])

    def test_template_flag_no_input_needed(self) -> None:
        # 不需 input/batch,單獨給 --template 即可
        r = subprocess.run(
            [sys.executable, "fitlog.py", "--template"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
