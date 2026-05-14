"""紅色測試 — 訓練量「按肌群分類」分解.

PT 看完總噸位後,下一個問題永遠是「今天訓練平衡嗎?」。讓報告自動算出
腿系 / 推系 / 拉系 / 核心 / 心肺 / 活動度各自的 tonnage,並由高到低排序
顯示,讓教練一眼看出「今天偏腿,下次該補背」。

跟總噸位一樣,只計算「有重量 + reps 是整數」的紀錄,避免 BW / 時間型
被誤算進去。
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
from metrics import (  # noqa: E402
    CATEGORY_ZH,
    compute_category_tonnage,
    render_category_breakdown,
)


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


class TestComputeCategoryTonnage(unittest.TestCase):
    def test_empty_returns_empty_dict(self) -> None:
        self.assertEqual(compute_category_tonnage([]), {})

    def test_all_bodyweight_returns_empty(self) -> None:
        sets = [
            _set("PULL_UP", 4, "8", None),
            _set("PLANK", 3, "60 sec", None),
        ]
        self.assertEqual(compute_category_tonnage(sets), {})

    def test_single_category(self) -> None:
        # 4×10×70 = 2800 → legs
        result = compute_category_tonnage([_set("BB_BACK_SQUAT", 4, "10", 70.0)])
        self.assertEqual(result, {"legs": 2800.0})

    def test_real_sample_breakdown(self) -> None:
        # samples/sample_input.json 完整 sets:
        #   Squat (legs) 2800 + RDL (legs) 1800 + Bench (push) 1600
        sets = [
            _set("WORLDS_GREATEST", 2, "5 reps/side", None),
            _set("BB_BACK_SQUAT", 4, "10", 70.0),
            _set("BENCH_PRESS", 4, "8", 50.0),
            _set("ROMANIAN_DL", 3, "10", 60.0),
            _set("PULL_UP", 3, "6", None),
            _set("PLANK", 3, "60 sec", None),
        ]
        result = compute_category_tonnage(sets)
        self.assertEqual(result, {"legs": 4600.0, "push": 1600.0})

    def test_unknown_exercise_code_skipped(self) -> None:
        # 不在 exercise_db 的代碼 → 跳過 (不歸到 "unknown" bucket;避免污染分類)
        sets = [
            _set("BENCH_PRESS", 4, "8", 50.0),
            _set("XXX_UNKNOWN_CODE", 4, "8", 50.0),
        ]
        self.assertEqual(compute_category_tonnage(sets), {"push": 1600.0})

    def test_multiple_exercises_same_category_summed(self) -> None:
        # Squat + RDL 都是 legs → 應該加總
        sets = [
            _set("BB_BACK_SQUAT", 4, "10", 70.0),  # 2800
            _set("ROMANIAN_DL", 3, "10", 60.0),    # 1800
        ]
        self.assertEqual(compute_category_tonnage(sets), {"legs": 4600.0})


class TestRenderCategoryBreakdown(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        self.assertIsNone(render_category_breakdown([]))

    def test_all_bodyweight_returns_none(self) -> None:
        sets = [
            _set("PULL_UP", 4, "8", None),
            _set("PLANK", 3, "60 sec", None),
        ]
        self.assertIsNone(render_category_breakdown(sets))

    def test_single_category_format(self) -> None:
        # 只一個分類 → 顯示一項即可
        result = render_category_breakdown([_set("BB_BACK_SQUAT", 4, "10", 70.0)])
        self.assertEqual(result, "**訓練量分解**: 腿系 2,800 kg")

    def test_descending_order_by_tonnage(self) -> None:
        # 即使腿系後加入,顯示時也要由高到低
        sets = [
            _set("BENCH_PRESS", 4, "8", 50.0),     # push 1600
            _set("BB_BACK_SQUAT", 4, "10", 70.0),  # legs 2800
            _set("ROMANIAN_DL", 3, "10", 60.0),    # legs +1800 → legs 4600
        ]
        result = render_category_breakdown(sets)
        self.assertEqual(result, "**訓練量分解**: 腿系 4,600 kg · 推系 1,600 kg")

    def test_uses_chinese_category_labels(self) -> None:
        # CATEGORY_ZH 必須涵蓋 exercise_db 六大類
        for key in ("legs", "pull", "push", "core", "cardio", "mobility"):
            self.assertIn(key, CATEGORY_ZH)
            self.assertTrue(CATEGORY_ZH[key].strip())  # 非空

    def test_unknown_code_does_not_appear(self) -> None:
        # 未知代碼不能出現在分解中
        sets = [
            _set("BENCH_PRESS", 4, "8", 50.0),
            _set("XXX_UNKNOWN", 4, "8", 50.0),
        ]
        result = render_category_breakdown(sets)
        self.assertEqual(result, "**訓練量分解**: 推系 1,600 kg")
        self.assertNotIn("unknown", result.lower())


class TestReportIntegration(unittest.TestCase):
    def setUp(self) -> None:
        payload = json.loads(
            (Path(__file__).resolve().parent.parent / "samples" / "sample_input.json").read_text(encoding="utf-8")
        )
        self.session = parse_payload(payload)
        self.body = render_skeleton_body()

    def test_markdown_includes_breakdown(self) -> None:
        out = render_full_report(self.session, self.body)
        self.assertIn("訓練量分解", out)
        self.assertIn("腿系 4,600 kg", out)
        self.assertIn("推系 1,600 kg", out)

    def test_markdown_omits_breakdown_when_all_bodyweight(self) -> None:
        self.session.sets = [
            _set("PULL_UP", 4, "8", None),
            _set("PLANK", 3, "60 sec", None),
        ]
        out = render_full_report(self.session, self.body)
        self.assertNotIn("訓練量分解", out)

    def test_line_friendly_includes_breakdown(self) -> None:
        out = render_line_friendly(self.session, self.body)
        # LINE 版用 emoji 起頭 "📦 分解:" 而非 markdown 粗體
        self.assertIn("分解", out)
        self.assertIn("腿系", out)
        self.assertIn("推系", out)

    def test_line_friendly_omits_breakdown_when_all_bodyweight(self) -> None:
        self.session.sets = [_set("PLANK", 3, "60 sec", None)]
        out = render_line_friendly(self.session, self.body)
        self.assertNotIn("分解", out)


if __name__ == "__main__":
    unittest.main()
