"""紅色測試 — 累計訓練量里程碑慶祝 banner.

學員突破累計訓練量里程碑 (10/50/100/500/1000 噸) 時插🏅 banner。
PT SaaS 招牌的 retention/motivation 元素。

milestones (kg): 10000, 50000, 100000, 500000, 1000000
- 偵測單堂使學員 cumulative tonnage 跨越某 milestone → 慶祝
- 同堂跨多個 milestone → 取最高
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coaching import (  # noqa: E402
    MILESTONES_KG,
    compute_cumulative_tonnage_before,
    detect_milestone_crossed,
    render_milestone_banner,
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


class TestDetectMilestoneCrossed(unittest.TestCase):
    def test_no_crossing_returns_none(self) -> None:
        # 5000 → 8000 都低於 10,000 → None
        self.assertIsNone(detect_milestone_crossed(5000.0, 8000.0))

    def test_single_crossing(self) -> None:
        # 9000 → 11000 跨越 10000 milestone
        self.assertEqual(detect_milestone_crossed(9000.0, 11000.0), 10000)

    def test_multiple_crossings_returns_highest(self) -> None:
        # 9000 → 60000 跨越 10000 + 50000 → 取最高 50000
        self.assertEqual(detect_milestone_crossed(9000.0, 60000.0), 50000)

    def test_exact_milestone_value_counts_as_crossing(self) -> None:
        # 9000 → 10000 (恰好 = milestone) → 跨越
        self.assertEqual(detect_milestone_crossed(9000.0, 10000.0), 10000)

    def test_already_above_does_not_recount(self) -> None:
        # 11000 → 12000 (已過 10000) → None
        self.assertIsNone(detect_milestone_crossed(11000.0, 12000.0))

    def test_milestones_constant_includes_expected_levels(self) -> None:
        # 設計鎖定:10/50/100/500/1000 噸 (kg) 都該存在
        for m in (10_000, 50_000, 100_000, 500_000, 1_000_000):
            self.assertIn(m, MILESTONES_KG)


class TestComputeCumulativeTonnageBefore(unittest.TestCase):
    def test_no_prior_sessions_returns_zero(self) -> None:
        cur = _make("林阿明", 1, "2026-05-10",
                    [_set("BENCH_PRESS", 4, "8", 50.0)])
        self.assertEqual(
            compute_cumulative_tonnage_before([cur], "林阿明", cur), 0.0,
        )

    def test_sums_prior_same_student(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-01", [_set("BENCH_PRESS", 4, "8", 50.0)])  # 1600
        s2 = _make("林阿明", 2, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 50.0)])  # 1600
        cur = _make("林阿明", 3, "2026-05-15", [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_cumulative_tonnage_before([s1, s2, cur], "林阿明", cur)
        self.assertEqual(result, 3200.0)  # s1 + s2 (不含 cur)

    def test_excludes_current_session(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-01", [_set("BENCH_PRESS", 4, "8", 50.0)])
        cur = _make("林阿明", 2, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 99.0)])
        result = compute_cumulative_tonnage_before([s1, cur], "林阿明", cur)
        self.assertEqual(result, 1600.0)  # 只 s1

    def test_excludes_other_students(self) -> None:
        s_w = _make("王小華", 1, "2026-05-01", [_set("BENCH_PRESS", 4, "8", 99.0)])
        s_a = _make("林阿明", 1, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 50.0)])
        cur = _make("林阿明", 2, "2026-05-15", [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_cumulative_tonnage_before([s_w, s_a, cur], "林阿明", cur)
        self.assertEqual(result, 1600.0)


class TestRenderMilestoneBanner(unittest.TestCase):
    def test_none_returns_empty(self) -> None:
        self.assertEqual(render_milestone_banner(None), "")

    def test_10k_milestone_format(self) -> None:
        result = render_milestone_banner(10_000)
        self.assertIn("🏅", result)
        self.assertIn("10,000 kg", result)
        self.assertIn("10 噸", result)
        self.assertIn("里程碑", result)

    def test_100k_milestone_format(self) -> None:
        result = render_milestone_banner(100_000)
        self.assertIn("100,000 kg", result)
        self.assertIn("100 噸", result)


class TestCliBatchProducesMilestoneBanner(unittest.TestCase):
    def test_milestone_crossed_session_includes_banner(self) -> None:
        # 第 1 堂 6000 kg, 第 2 堂 6000 → 累計 12000 跨越 10000 → s2 該慶祝
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            for i in (1, 2):
                p = json.loads(json.dumps(SAMPLE_PAYLOAD))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
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
            # s1 累計 6,200 < 10,000 → 不該有 🏅
            self.assertNotIn("🏅", s1_md)
            # s2 累計 12,400 > 10,000 → 該慶祝
            self.assertIn("🏅", s2_md)
            self.assertIn("10,000 kg", s2_md)


if __name__ == "__main__":
    unittest.main()
