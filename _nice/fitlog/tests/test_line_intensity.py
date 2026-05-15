"""紅色測試 — LINE 純文字版補強度分數 + RPE 強度分布.

LINE 推播是台灣 PT 把報告傳給學員的主要管道。markdown 報告早已有
「訓練強度分數」與「強度分布 (熱身/工作/極限)」,但 render_line_friendly
還停在舊版的噸位/分解/密度/進步,沒帶這兩個。本輪補上 — 純函式從
session 算 (no LLM),整合進 LINE summary 區塊。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import (  # noqa: E402
    SetRecord,
    SessionInput,
    render_line_friendly,
    render_skeleton_body,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _session(sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=3, session_date="2026-05-15", duration_min=60,
        coach_name="陳教練", studio_name="硬舉工作室", contact="",
        theme="推系日", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(reps: str, weight: float | None, rpe: int | None) -> SetRecord:
    return SetRecord(exercise_code="BENCH_PRESS", sets=1,
                     reps_or_duration=reps, weight_kg=weight, rpe=rpe)


class TestLineIntensityScore(unittest.TestCase):
    def test_line_includes_intensity_score(self) -> None:
        sess = _session([_set("8", 50.0, 8)])
        out = render_line_friendly(sess, render_skeleton_body())
        self.assertIn("強度分數", out)
        # 1×8×50=400, RPE 8 → 320
        self.assertIn("320", out)

    def test_all_bw_session_no_intensity_score(self) -> None:
        # 全 BW → intensity None → LINE 不該出現強度分數行
        sess = _session([
            SetRecord(exercise_code="PULL_UP", sets=3,
                      reps_or_duration="8", weight_kg=None, rpe=7),
        ])
        out = render_line_friendly(sess, render_skeleton_body())
        self.assertNotIn("強度分數", out)


class TestLineRpeZone(unittest.TestCase):
    def test_line_includes_rpe_zone(self) -> None:
        sess = _session([
            _set("8", 50.0, 4),    # warmup
            _set("8", 50.0, 7),    # working
            _set("8", 50.0, 10),   # max
        ])
        out = render_line_friendly(sess, render_skeleton_body())
        self.assertIn("強度分布", out)
        self.assertIn("熱身", out)
        self.assertIn("工作", out)
        self.assertIn("極限", out)

    def test_no_rpe_session_no_zone(self) -> None:
        # 沒任何 RPE → zone None → 不出現
        sess = _session([_set("8", 50.0, None)])
        out = render_line_friendly(sess, render_skeleton_body())
        self.assertNotIn("強度分布", out)


class TestLineBackwardCompat(unittest.TestCase):
    def test_existing_sections_still_present(self) -> None:
        sess = _session([_set("8", 50.0, 8)])
        out = render_line_friendly(sess, render_skeleton_body())
        # 既有區塊不退化
        self.assertIn("總噸位", out)
        self.assertIn("林阿明", out)
        self.assertIn("第 3 堂", out)


if __name__ == "__main__":
    unittest.main()
