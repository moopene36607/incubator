"""紅色測試 — single session 達標慶祝 banner.

學員突破目標那一刻是 PT 招牌時刻 — 該堂報告該有「🎉 目標達成!」段落
明顯告訴學員「你今天突破了 60 kg 目標」。本輪偵測該堂是否「第一次達標」
(本堂 weight >= target,且歷史所有 prior session 該動作都 < target),
渲染慶祝 banner 進 markdown 報告。

設計準則:
- 只在「第一次達標」那堂顯示,後續堂繼續達標不重複慶祝 (避免疲乏)
- 同學員的 prior sessions 才算歷史;其他學員不影響
- 多個 target 同堂達標 → 各自一行
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import (  # noqa: E402
    GoalAchievement,
    find_newly_achieved_goals,
    render_session_goal_banner,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, session_no: int, date: str,
          sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


class TestFindNewlyAchievedGoals(unittest.TestCase):
    def test_no_targets_returns_empty(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 60.0)])
        self.assertEqual(find_newly_achieved_goals(sess, [sess], []), [])

    def test_session_below_target_returns_empty(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)])
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        self.assertEqual(find_newly_achieved_goals(sess, [sess], targets), [])

    def test_first_session_hitting_target_returns_achievement(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 60.0)])
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        result = find_newly_achieved_goals(sess, [sess], targets)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].exercise_code, "BENCH_PRESS")
        self.assertEqual(result[0].target_kg, 60.0)

    def test_subsequent_session_hitting_target_no_banner(self) -> None:
        # 第二堂也達標 → 不該重複顯示 banner
        s1 = _make("林阿明", 1, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 60.0)])
        s2 = _make("林阿明", 2, "2026-05-15", [_set("BENCH_PRESS", 4, "8", 60.0)])
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        result = find_newly_achieved_goals(s2, [s1, s2], targets)
        self.assertEqual(result, [])

    def test_first_session_after_prior_below_target(self) -> None:
        # s1 47.5 (未達) → s2 60 (首次達標) → 該慶祝
        s1 = _make("林阿明", 1, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 47.5)])
        s2 = _make("林阿明", 2, "2026-05-15", [_set("BENCH_PRESS", 4, "8", 60.0)])
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        result = find_newly_achieved_goals(s2, [s1, s2], targets)
        self.assertEqual(len(result), 1)

    def test_other_students_dont_count_as_prior(self) -> None:
        # 王小華 s1 達標,林阿明 s1 也達標 → 林阿明 仍該慶祝 (彼此獨立)
        s_w = _make("王小華", 1, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 60.0)])
        s_a = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 60.0)])
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        result = find_newly_achieved_goals(s_a, [s_w, s_a], targets)
        self.assertEqual(len(result), 1)

    def test_multiple_targets_same_session_all_listed(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 4, "8", 60.0),
            _set("BB_BACK_SQUAT", 4, "10", 80.0),
        ])
        targets = [
            {"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0},
            {"exercise_code": "BB_BACK_SQUAT", "target_weight_kg": 80.0},
        ]
        result = find_newly_achieved_goals(sess, [sess], targets)
        self.assertEqual(len(result), 2)

    def test_takes_max_weight_within_session(self) -> None:
        # 同 session 多 set,最重那組才比 target
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 1, "10", 40.0),
            _set("BENCH_PRESS", 1, "3", 60.0),
        ])
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        result = find_newly_achieved_goals(sess, [sess], targets)
        self.assertEqual(len(result), 1)

    def test_returns_goal_achievement_dataclass(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 60.0)])
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        result = find_newly_achieved_goals(sess, [sess], targets)
        self.assertIsInstance(result[0], GoalAchievement)


class TestRenderSessionGoalBanner(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_session_goal_banner([]), "")

    def test_single_achievement_format(self) -> None:
        result = render_session_goal_banner([
            GoalAchievement(exercise_code="BENCH_PRESS", target_kg=60.0),
        ])
        self.assertIn("🎉", result)
        self.assertIn("目標達成", result)
        self.assertIn("槓鈴臥推", result)
        self.assertIn("60 kg", result)

    def test_multiple_achievements_each_listed(self) -> None:
        result = render_session_goal_banner([
            GoalAchievement(exercise_code="BENCH_PRESS", target_kg=60.0),
            GoalAchievement(exercise_code="BB_BACK_SQUAT", target_kg=80.0),
        ])
        self.assertIn("槓鈴臥推", result)
        self.assertIn("槓鈴背蹲舉", result)


class TestCliBatchProducesBanner(unittest.TestCase):
    def test_session_md_includes_banner_when_newly_achieved(self) -> None:
        # bench target=50 → s1 達 47.5 不顯示, s2 達 50 → s2.md 該有 banner
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            for i, w in enumerate([47.5, 50.0], 1):
                p = json.loads(json.dumps(SAMPLE_PAYLOAD))
                p["student"]["name"] = "林阿明"
                p["student"]["targets"] = [
                    {"exercise_code": "BENCH_PRESS", "target_weight_kg": 50.0},
                ]
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                for s in p["session"]["sets"]:
                    if s["exercise_code"] == "BENCH_PRESS":
                        s["weight_kg"] = w
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            s1_md = (Path(out_td) / "s1.md").read_text(encoding="utf-8")
            s2_md = (Path(out_td) / "s2.md").read_text(encoding="utf-8")
            self.assertNotIn("🎉", s1_md)  # s1 未達
            self.assertIn("🎉", s2_md)     # s2 首次達
            self.assertIn("目標達成", s2_md)


if __name__ == "__main__":
    unittest.main()
