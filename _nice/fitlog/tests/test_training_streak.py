"""紅色測試 — 學員連續訓練週數 streak (retention 指標).

PT 在保留學員上最在意「他這個月還在不在」。本輪加 streak 計算:該學員
**到當週為止**,往回連續多少 ISO 週都有至少 1 堂 session。週中斷則歸零。

例:
- 學員 W18, W19, W20, W21 都訓練 (今天在 W21) → streak = 4 週
- 學員 W18 訓練、W19 沒練、W20 訓練 (今天 W20) → streak = 1 週 (W19 中斷)
- 學員 W21 沒練、之前 W18-W20 都訓練 (今天 W21) → streak = 0 (當週沒練)

純函式 compute_training_streak(sessions, student_name, today_iso_str)。
週用 ISO calendar (週一為週初)。沒任何 session → 0。"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import (  # noqa: E402
    StudentTrend,
    compute_training_streak,
    render_training_streak,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, session_no: int, date: str,
          sets: list[SetRecord] | None = None) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets or [
            SetRecord(exercise_code="BENCH_PRESS", sets=1,
                      reps_or_duration="8", weight_kg=50.0, rpe=7),
        ],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestComputeTrainingStreak(unittest.TestCase):
    def test_no_sessions_returns_zero(self) -> None:
        self.assertEqual(compute_training_streak([], "林阿明", "2026-05-15"), 0)

    def test_other_students_ignored(self) -> None:
        a = _make("王小華", 1, "2026-05-12")  # 同週但他人
        self.assertEqual(compute_training_streak([a], "林阿明", "2026-05-15"), 0)

    def test_session_only_in_current_week_returns_one(self) -> None:
        # today 2026-05-15 (週五),session 2026-05-13 (同週) → streak=1
        a = _make("林阿明", 1, "2026-05-13")
        self.assertEqual(
            compute_training_streak([a], "林阿明", "2026-05-15"), 1,
        )

    def test_today_no_session_streak_zero(self) -> None:
        # 上週 W19 練了,今天 W20 還沒練 → streak=0 (當週中斷)
        a = _make("林阿明", 1, "2026-05-05")  # 上週
        self.assertEqual(
            compute_training_streak([a], "林阿明", "2026-05-15"), 0,
        )

    def test_consecutive_weeks_streak(self) -> None:
        # W18, W19, W20, W21 各 1 堂,今天在 W21
        sessions = [
            _make("林阿明", 1, "2026-04-27"),  # W18 (週一)
            _make("林阿明", 2, "2026-05-04"),  # W19
            _make("林阿明", 3, "2026-05-11"),  # W20
            _make("林阿明", 4, "2026-05-15"),  # W20 (週五)
        ]
        # today 2026-05-15 → W20。檢查 streak 3 週 (W18 W19 W20)
        self.assertEqual(
            compute_training_streak(sessions, "林阿明", "2026-05-15"), 3,
        )

    def test_gap_resets_streak(self) -> None:
        # W18 練、W19 跳、W20 練,今天 W20 → streak=1
        sessions = [
            _make("林阿明", 1, "2026-04-27"),  # W18
            _make("林阿明", 3, "2026-05-13"),  # W20
        ]
        self.assertEqual(
            compute_training_streak(sessions, "林阿明", "2026-05-15"), 1,
        )

    def test_multiple_sessions_same_week_count_once(self) -> None:
        # 同週 3 堂只算 1 週
        sessions = [
            _make("林阿明", 1, "2026-05-11"),  # W20
            _make("林阿明", 2, "2026-05-13"),  # W20
            _make("林阿明", 3, "2026-05-15"),  # W20
        ]
        self.assertEqual(
            compute_training_streak(sessions, "林阿明", "2026-05-15"), 1,
        )


class TestRenderTrainingStreak(unittest.TestCase):
    def test_zero_returns_none(self) -> None:
        # 0 週不要洗版,避免每位剛斷的學員都被打臉
        self.assertIsNone(render_training_streak(0))

    def test_one_week_renders(self) -> None:
        line = render_training_streak(1)
        assert line is not None
        self.assertIn("連續訓練", line)
        self.assertIn("1", line)
        self.assertIn("週", line)

    def test_multi_week_renders_emoji(self) -> None:
        line = render_training_streak(4)
        assert line is not None
        self.assertIn("🔥", line)
        self.assertIn("4", line)
        self.assertIn("連續訓練", line)

    def test_starts_bolded(self) -> None:
        line = render_training_streak(2)
        assert line is not None
        self.assertIn("**", line)  # markdown bold


class TestRenderStudentTrendIncludesStreak(unittest.TestCase):
    def test_streak_section_appears_with_kwarg(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        out = render_student_trend(trend, training_streak=3)
        self.assertIn("連續訓練", out)
        self.assertIn("3", out)

    def test_zero_streak_no_section(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        out = render_student_trend(trend, training_streak=0)
        self.assertNotIn("連續訓練", out)


class TestCliBatchIncludesStreakInStudentMd(unittest.TestCase):
    def test_student_md_contains_streak_line(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            # 同學員 3 堂 連續 3 週 (W18 W19 W20)
            for i, dstr in enumerate(["2026-04-27", "2026-05-04", "2026-05-11"], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = dstr
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            # 應出現 streak 行 (最近一堂 W20 + 3 週連續)
            self.assertIn("連續訓練", content)


if __name__ == "__main__":
    unittest.main()
