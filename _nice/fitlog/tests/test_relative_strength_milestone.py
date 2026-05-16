"""紅色測試 — 相對肌力里程碑 banner.

健身圈強度里程碑都以「自身體重倍數」表達:0.5× / 1× / 1.5× / 2× / 2.5×。
「臥推終於破自身體重」是 PT 招牌慶祝時刻。本輪偵測:當堂某加重動作的
(最重 / 當堂體重) 首次跨過某個里程碑倍數 (歷史 prior session 都沒到過)。

純數字函式;沒記體重的 session 不納入比較。
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
    detect_relative_strength_milestones,
    render_relative_strength_milestones,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, sno: int, date: str,
          bench: float, bw: float | None) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=sno, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=bench, rpe=7)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
        student_bodyweight_kg=bw,
    )


class TestDetectRelativeStrengthMilestones(unittest.TestCase):
    def test_no_bodyweight_current_returns_empty(self) -> None:
        curr = _make("林阿明", 1, "2026-05-10", 70.0, None)
        self.assertEqual(
            detect_relative_strength_milestones([curr], "林阿明", curr), [])

    def test_first_session_crossing_one_bw(self) -> None:
        # 第一堂就 70 kg / 70 kg = 1.0× → 跨 0.5× 與 1.0×,取最高 1.0×
        curr = _make("林阿明", 1, "2026-05-10", 70.0, 70.0)
        result = detect_relative_strength_milestones([curr], "林阿明", curr)
        self.assertEqual(len(result), 1)
        code, milestone = result[0]
        self.assertEqual(code, "BENCH_PRESS")
        self.assertEqual(milestone, 1.0)

    def test_crossing_one_bw_after_prior_below(self) -> None:
        # 上堂 60/70 = 0.86×;本堂 75/70 ≈ 1.07× → 跨 1.0×
        prev = _make("林阿明", 1, "2026-05-01", 60.0, 70.0)
        curr = _make("林阿明", 2, "2026-05-08", 75.0, 70.0)
        result = detect_relative_strength_milestones(
            [prev, curr], "林阿明", curr)
        self.assertEqual(result, [("BENCH_PRESS", 1.0)])

    def test_already_crossed_not_repeated(self) -> None:
        # 上堂已 1.07×,本堂 1.1× → 沒新里程碑
        prev = _make("林阿明", 1, "2026-05-01", 75.0, 70.0)
        curr = _make("林阿明", 2, "2026-05-08", 77.0, 70.0)
        self.assertEqual(
            detect_relative_strength_milestones([prev, curr], "林阿明", curr),
            [])

    def test_no_progress_no_milestone(self) -> None:
        prev = _make("林阿明", 1, "2026-05-01", 60.0, 70.0)
        curr = _make("林阿明", 2, "2026-05-08", 60.0, 70.0)
        self.assertEqual(
            detect_relative_strength_milestones([prev, curr], "林阿明", curr),
            [])

    def test_bodyweight_drop_can_cross_milestone(self) -> None:
        # 體重從 80 降到 70,臥推都 70 kg → 0.875× 變 1.0× → 跨 1.0×
        prev = _make("林阿明", 1, "2026-05-01", 70.0, 80.0)
        curr = _make("林阿明", 2, "2026-05-08", 70.0, 70.0)
        result = detect_relative_strength_milestones(
            [prev, curr], "林阿明", curr)
        self.assertEqual(result, [("BENCH_PRESS", 1.0)])

    def test_other_students_excluded(self) -> None:
        a = _make("王小華", 1, "2026-05-01", 200.0, 70.0)
        curr = _make("林阿明", 1, "2026-05-08", 35.0, 70.0)  # 0.5×
        result = detect_relative_strength_milestones([a, curr], "林阿明", curr)
        self.assertEqual(result, [("BENCH_PRESS", 0.5)])


class TestRenderRelativeStrengthMilestones(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        self.assertIsNone(render_relative_strength_milestones([]))

    def test_single_milestone(self) -> None:
        out = render_relative_strength_milestones([("BENCH_PRESS", 1.0)])
        assert out is not None
        self.assertIn("🏆", out)
        self.assertIn("相對肌力里程碑", out)
        self.assertIn("槓鈴臥推", out)
        self.assertIn("自身體重", out)

    def test_one_bw_says_one_times(self) -> None:
        out = render_relative_strength_milestones([("BENCH_PRESS", 1.0)])
        assert out is not None
        self.assertIn("1", out)


class TestCliEmitsRelativeStrengthMilestone(unittest.TestCase):
    def test_batch_session_md_shows_milestone(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, bench in enumerate([60.0, 75.0], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                p["session"]["bodyweight_kg"] = 70.0
                for s in p["session"]["sets"]:
                    if s["exercise_code"] == "BENCH_PRESS":
                        s["weight_kg"] = bench
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            s2 = (Path(out_td) / "s2.md").read_text(encoding="utf-8")
            self.assertIn("相對肌力里程碑", s2)


if __name__ == "__main__":
    unittest.main()
