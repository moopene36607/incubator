"""紅色測試 — 基於 RPE 的下次重量建議 (純函式,no LLM).

PT 招牌可主動建議的事:看本堂課每個 set 的 RPE,自動推下次該加多少。
台灣 / 國際健身圈通用「線性 RPE 推進」法則:

- RPE ≤ 6 (太輕鬆) → +5 kg
- RPE 7 (尚有餘裕) → +2.5 kg
- RPE 8-9 (剛好 / 略吃力) → 維持
- RPE 10 (力竭) → deload -5 kg

四捨五入到 2.5 kg (台灣槓片最小單位)。BW 動作不適用。沒填 RPE 就跳過
(教練沒判斷依據,LLM 也不該瞎猜)。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coaching import (  # noqa: E402
    WeightSuggestion,
    render_next_weight_suggestions,
    suggest_next_session_weights,
    suggest_next_weight,
)
from fitlog import (  # noqa: E402
    SetRecord,
    parse_payload,
    render_full_report,
    render_line_friendly,
    render_skeleton_body,
)


def _set(code: str, sets: int, reps: str, weight: float | None,
         rpe: int | None = 7) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=rpe)


def _load_sample():
    p = Path(__file__).resolve().parent.parent / "samples" / "sample_input.json"
    return parse_payload(json.loads(p.read_text(encoding="utf-8")))


class TestSuggestNextWeight(unittest.TestCase):
    def test_rpe_6_plus_five(self) -> None:
        self.assertEqual(suggest_next_weight(50.0, 6), 55.0)

    def test_rpe_5_plus_five(self) -> None:
        # ≤ 6 都是 +5
        self.assertEqual(suggest_next_weight(50.0, 5), 55.0)

    def test_rpe_1_plus_five(self) -> None:
        self.assertEqual(suggest_next_weight(50.0, 1), 55.0)

    def test_rpe_7_plus_two_point_five(self) -> None:
        self.assertEqual(suggest_next_weight(47.5, 7), 50.0)

    def test_rpe_8_maintained(self) -> None:
        self.assertEqual(suggest_next_weight(50.0, 8), 50.0)

    def test_rpe_9_maintained(self) -> None:
        self.assertEqual(suggest_next_weight(50.0, 9), 50.0)

    def test_rpe_10_deload(self) -> None:
        self.assertEqual(suggest_next_weight(50.0, 10), 45.0)

    def test_deload_does_not_go_negative(self) -> None:
        # 極輕重量 + RPE 10 → 至少 0,不變負值
        self.assertGreaterEqual(suggest_next_weight(2.0, 10), 0.0)


class TestSuggestNextSessionWeights(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(suggest_next_session_weights([]), {})

    def test_single_weighted_with_rpe(self) -> None:
        sets = [_set("BENCH_PRESS", 4, "8", 50.0, rpe=8)]
        result = suggest_next_session_weights(sets)
        self.assertIn("BENCH_PRESS", result)
        s = result["BENCH_PRESS"]
        self.assertEqual(s.curr_top_weight, 50.0)
        self.assertEqual(s.suggested_weight, 50.0)
        self.assertEqual(s.delta, 0.0)
        self.assertIn("8", s.rationale)

    def test_bw_skipped(self) -> None:
        sets = [_set("PULL_UP", 4, "8", None, rpe=9)]
        self.assertEqual(suggest_next_session_weights(sets), {})

    def test_missing_rpe_skipped(self) -> None:
        sets = [_set("BENCH_PRESS", 4, "8", 50.0, rpe=None)]
        self.assertEqual(suggest_next_session_weights(sets), {})

    def test_uses_heaviest_set_per_exercise(self) -> None:
        # 多 set 不同重量 → 取最重的 RPE 做推算
        sets = [
            _set("BENCH_PRESS", 1, "10", 40.0, rpe=6),
            _set("BENCH_PRESS", 1, "8", 47.5, rpe=7),
            _set("BENCH_PRESS", 1, "5", 50.0, rpe=8),  # top
        ]
        s = suggest_next_session_weights(sets)["BENCH_PRESS"]
        self.assertEqual(s.curr_top_weight, 50.0)
        self.assertEqual(s.suggested_weight, 50.0)  # RPE 8 → 維持

    def test_returns_weight_suggestion_dataclass(self) -> None:
        sets = [_set("BENCH_PRESS", 4, "8", 50.0, rpe=7)]
        s = suggest_next_session_weights(sets)["BENCH_PRESS"]
        self.assertIsInstance(s, WeightSuggestion)
        self.assertEqual(s.suggested_weight, 52.5)
        self.assertEqual(s.delta, 2.5)


class TestRenderNextWeightSuggestions(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        self.assertIsNone(render_next_weight_suggestions({}))

    def test_increase_format(self) -> None:
        s = WeightSuggestion(
            exercise_code="BENCH_PRESS",
            curr_top_weight=47.5, suggested_weight=50.0, delta=2.5,
            rationale="RPE 7 +2.5kg",
        )
        result = render_next_weight_suggestions({"BENCH_PRESS": s})
        self.assertIsNotNone(result)
        self.assertIn("槓鈴臥推", result)
        self.assertIn("47.5→50 kg", result)
        self.assertIn("RPE 7", result)

    def test_maintain_format(self) -> None:
        s = WeightSuggestion(
            exercise_code="BENCH_PRESS",
            curr_top_weight=50.0, suggested_weight=50.0, delta=0.0,
            rationale="RPE 8 維持",
        )
        result = render_next_weight_suggestions({"BENCH_PRESS": s})
        self.assertIn("維持", result)
        self.assertIn("50 kg", result)

    def test_deload_format(self) -> None:
        s = WeightSuggestion(
            exercise_code="BENCH_PRESS",
            curr_top_weight=50.0, suggested_weight=45.0, delta=-5.0,
            rationale="RPE 10 deload",
        )
        result = render_next_weight_suggestions({"BENCH_PRESS": s})
        self.assertIn("50→45 kg", result)
        self.assertIn("deload", result)

    def test_sorted_by_delta_desc(self) -> None:
        sugs = {
            "BENCH_PRESS": WeightSuggestion(
                exercise_code="BENCH_PRESS", curr_top_weight=47.5,
                suggested_weight=50.0, delta=2.5, rationale="RPE 7 +2.5kg",
            ),
            "BB_BACK_SQUAT": WeightSuggestion(
                exercise_code="BB_BACK_SQUAT", curr_top_weight=70.0,
                suggested_weight=75.0, delta=5.0, rationale="RPE 6 +5kg",
            ),
        }
        result = render_next_weight_suggestions(sugs)
        # squat (+5) 應排在 bench (+2.5) 前
        self.assertLess(result.find("槓鈴背蹲舉"), result.find("槓鈴臥推"))


class TestReportIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _load_sample()
        self.body = render_skeleton_body()

    def test_markdown_includes_next_weight_suggestions(self) -> None:
        from coaching import suggest_next_session_weights, render_next_weight_suggestions
        next_w = render_next_weight_suggestions(suggest_next_session_weights(self.session.sets))
        out = render_full_report(self.session, self.body, next_weight_summary=next_w)
        self.assertIn("下次建議重量", out)
        # sample 有 squat RPE 8 / bench RPE 8 / RDL RPE 7 → 至少 RDL 該 +2.5
        self.assertIn("羅馬尼亞硬舉", out)

    def test_line_includes_next_weight_suggestions(self) -> None:
        from coaching import suggest_next_session_weights, render_next_weight_suggestions
        next_w = render_next_weight_suggestions(suggest_next_session_weights(self.session.sets))
        out = render_line_friendly(self.session, self.body, next_weight_summary=next_w)
        self.assertIn("下次建議", out)


if __name__ == "__main__":
    unittest.main()
