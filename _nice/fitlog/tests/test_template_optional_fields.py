"""紅色測試 — --template 樣板加入選填欄位骨架.

目前 --template 樣板沒展示 student.targets (目標)、session.bodyweight_kg
(體重)、next_session / recovery_diet 結構 — PT 從樣板起步不會知道這些
功能存在。本輪在樣板補上這些欄位的可填骨架 (含 placeholder)。

樣板仍須通過 schema 驗證。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schema import validate_payload_schema  # noqa: E402
from voice import make_blank_session_template  # noqa: E402


class TestTemplateOptionalFields(unittest.TestCase):
    def setUp(self) -> None:
        self.tpl = make_blank_session_template()

    def test_still_passes_schema(self) -> None:
        errors = validate_payload_schema(self.tpl)
        self.assertEqual(errors, [], f"樣板不該有 schema 錯誤: {errors}")

    def test_has_targets(self) -> None:
        self.assertIn("targets", self.tpl["student"])
        self.assertTrue(self.tpl["student"]["targets"],
                        "targets 應有至少一筆範例")

    def test_target_has_exercise_and_value(self) -> None:
        t = self.tpl["student"]["targets"][0]
        self.assertIn("exercise_code", t)
        self.assertTrue(
            "target_weight_kg" in t or "target_reps" in t
            or "target_duration" in t)

    def test_has_bodyweight_field(self) -> None:
        self.assertIn("bodyweight_kg", self.tpl["session"])

    def test_next_session_has_structure(self) -> None:
        ns = self.tpl["next_session"]
        self.assertIn("theme", ns)
        self.assertIn("focus", ns)

    def test_recovery_diet_has_structure(self) -> None:
        self.assertTrue(self.tpl["recovery_diet"])

    def test_observations_have_placeholder(self) -> None:
        self.assertTrue(self.tpl["coach_observations"])
        self.assertTrue(self.tpl["student_subjective"])

    def test_template_parses_and_renders(self) -> None:
        # 樣板能 parse_payload 不噴錯
        from fitlog import parse_payload, render_skeleton_body
        session = parse_payload(self.tpl)
        body = render_skeleton_body(session)
        self.assertIn("今日訓練摘要", body)


if __name__ == "__main__":
    unittest.main()
