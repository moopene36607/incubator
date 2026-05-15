"""紅色測試 — 目標達成日預估 (linear projection).

PT 跟學員聊目標時最想說「按你現在的進步速率,2 個月後就能上 60 kg」,
這是激勵 + 設定預期的關鍵話術。本輪用 weight progression 跨堂資料做
線性回歸 (slope = kg/天),外推到 target_kg,輸出預估達成日。

純數字函式,LLM 絕不能算。

邊界:
- 點數 < 2 → 無 slope → None
- slope ≤ 0 (無進步 / 退步) → None
- current >= target (已達標) → None
- 預估超過 max_horizon_days (default 365) → None (太遠不切實際)
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
    GoalProgress,
    compute_goal_etas,
    project_goal_eta,
    render_goal_progress,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


class TestProjectGoalEta(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        self.assertIsNone(project_goal_eta([], 50.0, "2026-05-15"))

    def test_single_point_returns_none(self) -> None:
        self.assertIsNone(project_goal_eta(
            [("2026-05-10", 45.0)], 50.0, "2026-05-15"
        ))

    def test_linear_progress_projects_date(self) -> None:
        # +1 kg / 7 天;從 45 到 50 要 5 kg → 35 天
        # 起算 today=2026-05-15 → ETA 2026-06-19
        points = [
            ("2026-04-22", 45.0),
            ("2026-04-29", 46.0),
            ("2026-05-06", 47.0),
            ("2026-05-13", 48.0),
        ]
        eta = project_goal_eta(points, 50.0, "2026-05-15")
        # 從最後一點 48 kg → target 50 需要 2 kg → 2 kg / (1/7 kg/天) = 14 天
        # today 5-15 + 14 = 5-29
        self.assertEqual(eta, "2026-05-29")

    def test_flat_progress_returns_none(self) -> None:
        points = [
            ("2026-04-22", 45.0),
            ("2026-04-29", 45.0),
            ("2026-05-06", 45.0),
        ]
        self.assertIsNone(project_goal_eta(points, 50.0, "2026-05-15"))

    def test_declining_progress_returns_none(self) -> None:
        points = [
            ("2026-04-22", 50.0),
            ("2026-04-29", 48.0),
            ("2026-05-06", 45.0),
        ]
        self.assertIsNone(project_goal_eta(points, 60.0, "2026-05-15"))

    def test_already_at_or_over_target_returns_none(self) -> None:
        points = [
            ("2026-04-22", 45.0),
            ("2026-04-29", 48.0),
            ("2026-05-06", 50.0),
        ]
        self.assertIsNone(project_goal_eta(points, 50.0, "2026-05-15"))

    def test_projection_capped_at_max_horizon(self) -> None:
        # 速率極慢:1 kg / 100 天,從 45 到 100 需要 5500 天 → 超過 365 → None
        points = [
            ("2026-01-01", 45.0),
            ("2026-04-11", 46.0),  # 100 天 +1
        ]
        self.assertIsNone(project_goal_eta(points, 100.0, "2026-05-15"))

    def test_projection_just_under_horizon(self) -> None:
        # +1 kg / 7 天 從 45 → 100 (差 55 kg) = 385 天 → 超過 365 → None
        points = [("2026-01-01", 45.0), ("2026-01-08", 46.0)]
        self.assertIsNone(project_goal_eta(points, 100.0, "2026-05-15"))

    def test_custom_horizon(self) -> None:
        # +1 kg / 7 天 從 48 → 50 = 14 天;horizon=10 → 不容
        points = [("2026-05-01", 47.0), ("2026-05-08", 48.0)]
        self.assertIsNone(project_goal_eta(
            points, 50.0, "2026-05-15", max_horizon_days=10
        ))


class TestComputeGoalEtas(unittest.TestCase):
    def test_empty_returns_empty_dict(self) -> None:
        self.assertEqual(compute_goal_etas([], {}, "2026-05-15"), {})

    def test_matches_targets_with_progression_data(self) -> None:
        targets = [
            {"exercise_code": "BENCH_PRESS", "target_weight_kg": 50.0},
            {"exercise_code": "BB_BACK_SQUAT", "target_weight_kg": 80.0},
        ]
        progressions = {
            "BENCH_PRESS": [
                ("2026-04-22", 45.0), ("2026-04-29", 46.0),
                ("2026-05-06", 47.0), ("2026-05-13", 48.0),
            ],
            # BB_BACK_SQUAT 沒在 progressions 內 → 不該出現
        }
        result = compute_goal_etas(targets, progressions, "2026-05-15")
        self.assertIn("BENCH_PRESS", result)
        self.assertNotIn("BB_BACK_SQUAT", result)
        self.assertEqual(result["BENCH_PRESS"], "2026-05-29")

    def test_skips_already_achieved_targets(self) -> None:
        # current 50 >= target 50 → skip
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 50.0}]
        progressions = {
            "BENCH_PRESS": [("2026-04-22", 48.0), ("2026-05-13", 50.0)],
        }
        result = compute_goal_etas(targets, progressions, "2026-05-15")
        self.assertEqual(result, {})


class TestRenderGoalProgressWithEta(unittest.TestCase):
    def test_etas_appended_to_unachieved_rows(self) -> None:
        progress = [GoalProgress(
            exercise_code="BENCH_PRESS",
            current_kg=48.0, target_kg=50.0, percent=96.0,
        )]
        out = render_goal_progress(progress, etas={"BENCH_PRESS": "2026-05-29"})
        self.assertIn("槓鈴臥推", out)
        self.assertIn("預估達成", out)
        self.assertIn("2026-05-29", out)

    def test_etas_none_keeps_existing_format(self) -> None:
        # 向後相容:不傳 etas 跟之前一樣
        progress = [GoalProgress(
            exercise_code="BENCH_PRESS",
            current_kg=48.0, target_kg=50.0, percent=96.0,
        )]
        out_no_eta = render_goal_progress(progress)
        self.assertIn("槓鈴臥推", out_no_eta)
        self.assertNotIn("預估達成", out_no_eta)

    def test_achieved_goal_does_not_show_eta(self) -> None:
        # 已達標 (percent>=100) 不顯示預估 (沒意義)
        progress = [GoalProgress(
            exercise_code="BENCH_PRESS",
            current_kg=50.0, target_kg=50.0, percent=100.0,
            achieved_on_session_no=3, achieved_on_date="2026-05-13",
        )]
        out = render_goal_progress(progress, etas={"BENCH_PRESS": "2026-06-01"})
        self.assertNotIn("預估達成", out)


class TestCliBatchEmitsEta(unittest.TestCase):
    def test_student_md_includes_eta_when_target_set(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            # 4 堂 BENCH_PRESS 45 → 46 → 47 → 48,每堂間隔 7 天
            # target 設 50,應預估達成
            for i, (w, dstr) in enumerate([
                (45.0, "2026-04-22"), (46.0, "2026-04-29"),
                (47.0, "2026-05-06"), (48.0, "2026-05-13"),
            ], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["student"]["targets"] = [
                    {"exercise_code": "BENCH_PRESS",
                     "target_weight_kg": 50.0},
                ]
                p["session"]["session_no"] = i
                p["session"]["date"] = dstr
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
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("預估達成", content)


if __name__ == "__main__":
    unittest.main()
