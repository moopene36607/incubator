"""紅色測試 — --no-ai 骨架版自動填「今日訓練摘要」段.

round 55-56 讓骨架版保留 PT 觀察 / 計畫 / 恢復。但 section 一 (今日訓練摘要)
仍是 placeholder。其實這段可以純資料事實填:主題 + 動作數 + 時長 + 總噸位
(全是純函式算出的數字,非 AI 編造) — 讓完全不用 AI 的 PT 也有可讀摘要。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SessionInput, SetRecord, render_skeleton_body  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _session(theme: str, sets: list[SetRecord],
             duration: int = 60) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=1, session_date="2026-05-15", duration_min=duration,
        coach_name="C", studio_name="S", contact="",
        theme=theme, sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(weight: float | None) -> SetRecord:
    return SetRecord(exercise_code="BENCH_PRESS", sets=4,
                     reps_or_duration="8", weight_kg=weight, rpe=8)


class TestSkeletonSummarySection(unittest.TestCase):
    def test_theme_in_summary(self) -> None:
        sess = _session("下肢主導 + 核心", [_set(50.0)])
        out = render_skeleton_body(sess)
        section = out.split("今日訓練摘要", 1)[1].split("###", 1)[0]
        self.assertIn("下肢主導 + 核心", section)
        self.assertNotIn("待 AI 填", section)

    def test_exercise_count_in_summary(self) -> None:
        sess = _session("X", [
            SetRecord("BENCH_PRESS", 4, "8", 50.0, 8),
            SetRecord("BB_BACK_SQUAT", 4, "8", 70.0, 8),
            SetRecord("PULL_UP", 3, "8", None, 9),
        ])
        out = render_skeleton_body(sess)
        section = out.split("今日訓練摘要", 1)[1].split("###", 1)[0]
        # 3 個動作項目
        self.assertIn("3", section)

    def test_duration_in_summary(self) -> None:
        sess = _session("X", [_set(50.0)], duration=75)
        out = render_skeleton_body(sess)
        section = out.split("今日訓練摘要", 1)[1].split("###", 1)[0]
        self.assertIn("75", section)

    def test_tonnage_in_summary_when_weighted(self) -> None:
        # 4×8×50 = 1600
        sess = _session("X", [_set(50.0)])
        out = render_skeleton_body(sess)
        section = out.split("今日訓練摘要", 1)[1].split("###", 1)[0]
        self.assertIn("1,600", section)

    def test_all_bw_no_tonnage_no_crash(self) -> None:
        sess = _session("X", [_set(None)])
        out = render_skeleton_body(sess)
        # 全 BW → 不該硬寫 0 kg 噸位 (誤導),但仍要有摘要
        section = out.split("今日訓練摘要", 1)[1].split("###", 1)[0]
        self.assertNotIn("待 AI 填", section)

    def test_no_session_keeps_placeholder(self) -> None:
        out = render_skeleton_body()
        section = out.split("今日訓練摘要", 1)[1].split("###", 1)[0]
        self.assertIn("待 AI 填", section)


class TestCliNoAiSummary(unittest.TestCase):
    def test_no_ai_report_summary_filled(self) -> None:
        with TemporaryDirectory() as td:
            in_path = Path(td) / "in.json"
            in_path.write_text(json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                               encoding="utf-8")
            out_path = Path(td) / "out.md"
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(in_path),
                 "--out", str(out_path), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = out_path.read_text(encoding="utf-8")
            summary = content.split("今日訓練摘要", 1)[1].split("###", 1)[0]
            self.assertNotIn("待 AI 填", summary)


if __name__ == "__main__":
    unittest.main()
