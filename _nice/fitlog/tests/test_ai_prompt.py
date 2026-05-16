"""紅色測試 — AI prompt 注入純函式算好的量化指標.

專案核心規範:數字一律純函式算,LLM 絕不能自己算。但目前 ai_write_body
只把「原始 sets」丟給 AI,AI 若要在「進步突破」段提數字就得自己算 —
有算錯風險。本輪把 prompt 構建抽成純函式 build_ai_user_prompt,並在裡面
附上已算好的指標 (總噸位 / 分類訓練量 / 估計 1RM),明確要 AI 直接引用。

TDD 的是 prompt 構建 (純函式,可測),不是 AI 回應。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SessionInput, SetRecord, build_ai_user_prompt  # noqa: E402


def _session(sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="增肌",
        session_no=5, session_date="2026-05-15", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="推系日", sets=sets,
        coach_observations=["深蹲深度進步"], student_subjective=["右肩緊"],
        next_session={"theme": "拉系日"}, recovery_diet={"notes": "睡好"},
    )


class TestBuildAiUserPrompt(unittest.TestCase):
    def test_returns_string(self) -> None:
        sess = _session([SetRecord("BENCH_PRESS", 4, "8", 50.0, 8)])
        prompt = build_ai_user_prompt(sess)
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip())

    def test_includes_raw_session_data(self) -> None:
        sess = _session([SetRecord("BENCH_PRESS", 4, "8", 50.0, 8)])
        prompt = build_ai_user_prompt(sess)
        self.assertIn("林阿明", prompt)
        self.assertIn("推系日", prompt)

    def test_includes_precomputed_tonnage(self) -> None:
        # 4×8×50 = 1600
        sess = _session([SetRecord("BENCH_PRESS", 4, "8", 50.0, 8)])
        prompt = build_ai_user_prompt(sess)
        self.assertIn("1600", prompt)

    def test_includes_precomputed_1rm(self) -> None:
        sess = _session([SetRecord("BENCH_PRESS", 4, "8", 50.0, 8)])
        prompt = build_ai_user_prompt(sess)
        # Epley 1RM 估算應出現在 prompt
        self.assertIn("1RM", prompt)

    def test_instructs_ai_to_quote_not_recompute(self) -> None:
        sess = _session([SetRecord("BENCH_PRESS", 4, "8", 50.0, 8)])
        prompt = build_ai_user_prompt(sess)
        # 必須明確要 AI 引用而非自算
        self.assertTrue("直接引用" in prompt or "不要自己" in prompt
                        or "不要自行" in prompt)

    def test_includes_coach_observations(self) -> None:
        sess = _session([SetRecord("BENCH_PRESS", 4, "8", 50.0, 8)])
        prompt = build_ai_user_prompt(sess)
        self.assertIn("深蹲深度進步", prompt)

    def test_all_bw_session_no_crash(self) -> None:
        sess = _session([SetRecord("PULL_UP", 3, "8", None, 9)])
        prompt = build_ai_user_prompt(sess)
        self.assertIn("林阿明", prompt)

    def test_category_breakdown_in_prompt(self) -> None:
        sess = _session([
            SetRecord("BENCH_PRESS", 4, "8", 50.0, 8),
            SetRecord("BB_BACK_SQUAT", 4, "8", 70.0, 8),
        ])
        prompt = build_ai_user_prompt(sess)
        # 分類訓練量 (推系 / 腿系) 應出現
        self.assertTrue("推系" in prompt or "腿系" in prompt)


if __name__ == "__main__":
    unittest.main()
