"""紅色測試 — _batch_summary 加工作室肌群分類訓練量分布.

batch summary 已有「動作訓練量排行」(個別動作),但沒有更高一層的
「這間工作室整體練了多少推/拉/腿」。店長想看訓練處方是否均衡 — 例如
全店 60% 訓練量集中在 push,代表課程設計偏頗。

純函式 compute_studio_category_distribution(sessions)
→ list[(category, tonnage, pct)] 按 tonnage desc。
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
    compute_studio_category_distribution,
    render_studio_category_distribution,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, codes_weights: list[tuple[str, float]]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=1, session_date="2026-05-15", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code=c, sets=4, reps_or_duration="8",
                        weight_kg=w, rpe=7) for c, w in codes_weights],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestComputeStudioCategoryDistribution(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(compute_studio_category_distribution([]), [])

    def test_single_category(self) -> None:
        # BENCH_PRESS push,4×8×50 = 1600
        sess = _make("林阿明", [("BENCH_PRESS", 50.0)])
        result = compute_studio_category_distribution([sess])
        self.assertEqual(len(result), 1)
        cat, ton, pct = result[0]
        self.assertEqual(cat, "push")
        self.assertEqual(ton, 1600.0)
        self.assertEqual(pct, 100.0)

    def test_multi_category_sorted_and_pct(self) -> None:
        # push 1600 + legs 2400 (BB_BACK_SQUAT 4×8×75)
        sess = _make("林阿明", [
            ("BENCH_PRESS", 50.0),       # push 1600
            ("BB_BACK_SQUAT", 75.0),     # legs 2400
        ])
        result = compute_studio_category_distribution([sess])
        # legs (2400) 排在 push (1600) 前
        self.assertEqual(result[0][0], "legs")
        self.assertEqual(result[1][0], "push")
        # legs pct = 2400/4000 = 60%
        self.assertAlmostEqual(result[0][2], 60.0, places=1)
        self.assertAlmostEqual(result[1][2], 40.0, places=1)

    def test_aggregates_across_students(self) -> None:
        a = _make("林阿明", [("BENCH_PRESS", 50.0)])   # push 1600
        b = _make("王小華", [("BENCH_PRESS", 50.0)])   # push 1600
        result = compute_studio_category_distribution([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], 3200.0)

    def test_bw_only_excluded(self) -> None:
        # 全 BW (tonnage 0) → 無分類分布
        sess = SessionInput(
            student_name="林阿明", student_age=30, student_goal="",
            session_no=1, session_date="2026-05-15", duration_min=60,
            coach_name="C", studio_name="S", contact="", theme="t",
            sets=[SetRecord(exercise_code="PULL_UP", sets=3,
                            reps_or_duration="8", weight_kg=None, rpe=7)],
            coach_observations=[], student_subjective=[],
            next_session={}, recovery_diet={},
        )
        self.assertEqual(compute_studio_category_distribution([sess]), [])


class TestRenderStudioCategoryDistribution(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_studio_category_distribution([]), "")

    def test_renders_section(self) -> None:
        rows = [("legs", 2400.0, 60.0), ("push", 1600.0, 40.0)]
        out = render_studio_category_distribution(rows)
        self.assertIn("肌群分類分布", out)
        self.assertIn("腿系", out)
        self.assertIn("推系", out)
        self.assertIn("60%", out)
        self.assertIn("2,400", out)


class TestCliBatchEmitsStudioCategory(unittest.TestCase):
    def test_batch_summary_has_category_distribution(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i in range(1, 3):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = f"Stu{i}"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-1{i}"
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_batch_summary.md").read_text(encoding="utf-8")
            self.assertIn("肌群分類分布", content)


if __name__ == "__main__":
    unittest.main()
