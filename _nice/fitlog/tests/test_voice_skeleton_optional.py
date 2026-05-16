"""紅色測試 — build_session_skeleton (--voice 輸出) 也帶選填欄位骨架.

round 76 讓 --template 樣板展示 targets / bodyweight / 計畫結構。但
--voice 產出的 skeleton 還是舊的空殼。本輪讓兩者一致 — voice 流程的 PT
同樣該從 skeleton 發現這些選填功能。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SetRecord  # noqa: E402
from voice import build_session_skeleton  # noqa: E402


def _skeleton():
    sets = [SetRecord(exercise_code="BENCH_PRESS", sets=4,
                      reps_or_duration="8", weight_kg=50.0, rpe=8)]
    return build_session_skeleton(sets)


class TestVoiceSkeletonOptionalFields(unittest.TestCase):
    def test_has_targets_skeleton(self) -> None:
        skel = _skeleton()
        self.assertIn("targets", skel["student"])

    def test_has_bodyweight_field(self) -> None:
        skel = _skeleton()
        self.assertIn("bodyweight_kg", skel["session"])

    def test_next_session_has_structure(self) -> None:
        skel = _skeleton()
        self.assertIn("theme", skel["next_session"])
        self.assertIn("focus", skel["next_session"])

    def test_recovery_diet_has_structure(self) -> None:
        skel = _skeleton()
        self.assertTrue(skel["recovery_diet"])

    def test_parsed_sets_still_intact(self) -> None:
        # 解析出的 sets 不可被選填欄位改動影響
        skel = _skeleton()
        self.assertEqual(len(skel["session"]["sets"]), 1)
        self.assertEqual(skel["session"]["sets"][0]["exercise_code"],
                         "BENCH_PRESS")

    def test_schema_passes_after_filling_names(self) -> None:
        from schema import validate_payload_schema
        skel = _skeleton()
        skel["student"]["name"] = "請填寫"
        skel["coach"]["name"] = "請填寫"
        skel["coach"]["studio_name"] = "請填寫"
        self.assertEqual(validate_payload_schema(skel), [])


if __name__ == "__main__":
    unittest.main()
