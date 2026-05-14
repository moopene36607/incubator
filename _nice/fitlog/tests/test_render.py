"""紅色測試 — render_volume_summary 純函式格式化訓練總噸位行 + 整合進報告渲染.

PT 看課後報告時最想知道「這堂課搬了幾噸」(訓練量化指標),整合進 markdown 與
LINE 兩種輸出,讓報告一眼看出本堂訓練量;若整堂都是 BW / 時間型則不顯示這行
(顯示 0 kg 反而誤導,讓學員以為今天沒練到)。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import (  # noqa: E402
    SetRecord,
    parse_payload,
    render_full_report,
    render_line_friendly,
    render_skeleton_body,
)
from metrics import render_volume_summary  # noqa: E402


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


class TestRenderVolumeSummary(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        self.assertIsNone(render_volume_summary([]))

    def test_all_bodyweight_returns_none(self) -> None:
        # 整堂瑜珈 / 暖身 / 棒式 → 沒有 tonnage 可顯示
        sets = [
            _set("PULL_UP", 4, "8", None),
            _set("PLANK", 3, "60 sec", None),
            _set("WORLDS_GREATEST", 2, "5 reps/side", None),
        ]
        self.assertIsNone(render_volume_summary(sets))

    def test_simple_weighted_under_thousand(self) -> None:
        # 1×10×50 = 500 kg → 沒千位逗號
        result = render_volume_summary([_set("BENCH_PRESS", 1, "10", 50.0)])
        self.assertEqual(result, "**訓練總噸位**: 500 kg")

    def test_weighted_with_thousands_separator(self) -> None:
        # 4×10×70 = 2800 kg → "2,800"
        result = render_volume_summary([_set("BB_BACK_SQUAT", 4, "10", 70.0)])
        self.assertEqual(result, "**訓練總噸位**: 2,800 kg")

    def test_real_sample_session(self) -> None:
        # 與 samples/sample_input.json 同 sets: 2800 + 1600 + 1800 = 6200
        sets = [
            _set("WORLDS_GREATEST", 2, "5 reps/side", None),
            _set("BB_BACK_SQUAT", 4, "10", 70.0),
            _set("BENCH_PRESS", 4, "8", 50.0),
            _set("ROMANIAN_DL", 3, "10", 60.0),
            _set("PULL_UP", 3, "6", None),
            _set("PLANK", 3, "60 sec", None),
        ]
        self.assertEqual(render_volume_summary(sets), "**訓練總噸位**: 6,200 kg")

    def test_drops_decimal_when_integer_value(self) -> None:
        # 47.5 × 8 × 1 = 380.0 → 顯示 "380 kg",不是 "380.0 kg"
        result = render_volume_summary([_set("BENCH_PRESS", 1, "8", 47.5)])
        self.assertEqual(result, "**訓練總噸位**: 380 kg")

    def test_keeps_decimal_when_fractional(self) -> None:
        # 47.5 × 7 × 1 = 332.5 → 顯示 "332.5 kg"
        result = render_volume_summary([_set("BENCH_PRESS", 1, "7", 47.5)])
        self.assertEqual(result, "**訓練總噸位**: 332.5 kg")


class TestReportIntegration(unittest.TestCase):
    """確認 tonnage 行有真的進到報告 markdown 與 LINE 純文字版。"""

    def setUp(self) -> None:
        payload = json.loads(
            (Path(__file__).resolve().parent.parent / "samples" / "sample_input.json").read_text(encoding="utf-8")
        )
        self.session = parse_payload(payload)
        self.body = render_skeleton_body()

    def test_full_report_includes_tonnage_when_weighted(self) -> None:
        out = render_full_report(self.session, self.body)
        self.assertIn("訓練總噸位", out)
        self.assertIn("6,200 kg", out)

    def test_full_report_omits_tonnage_when_all_bodyweight(self) -> None:
        # 換掉 sets 變全 BW → 報告不能出現「訓練總噸位」
        self.session.sets = [
            _set("PULL_UP", 4, "8", None),
            _set("PLANK", 3, "60 sec", None),
        ]
        out = render_full_report(self.session, self.body)
        self.assertNotIn("訓練總噸位", out)

    def test_line_friendly_includes_tonnage_when_weighted(self) -> None:
        out = render_line_friendly(self.session, self.body)
        self.assertIn("總噸位", out)
        self.assertIn("6,200", out)

    def test_line_friendly_omits_tonnage_when_all_bodyweight(self) -> None:
        self.session.sets = [_set("PLANK", 3, "60 sec", None)]
        out = render_line_friendly(self.session, self.body)
        self.assertNotIn("總噸位", out)


if __name__ == "__main__":
    unittest.main()
