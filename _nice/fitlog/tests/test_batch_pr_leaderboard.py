"""紅色測試 — _batch_summary 加批次 PR 突破榜.

batch summary 已有訓練量排行,但沒有「進步」維度的榜。count_student_prs
(round 28) 能算單一學員整期破紀錄次數,本輪把它做成跨學員排行,讓工作室
一眼看出「這批誰進步最多」— 課後群組貼出來很激勵。

純函式 compute_batch_pr_leaderboard(sessions) → list[(student, pr_count)]
按 pr_count desc;0 次的學員不列入。
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
    compute_batch_pr_leaderboard,
    render_batch_pr_leaderboard,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, sno: int, date: str, weight: float) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=sno, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=weight, rpe=7)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestComputeBatchPrLeaderboard(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(compute_batch_pr_leaderboard([]), [])

    def test_single_session_no_prs(self) -> None:
        # 各只 1 堂 → 沒歷史可破
        sessions = [_make("林阿明", 1, "2026-05-10", 50.0)]
        self.assertEqual(compute_batch_pr_leaderboard(sessions), [])

    def test_progressive_student_counted(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-04-22", 45.0),
            _make("林阿明", 2, "2026-04-29", 50.0),  # PR
            _make("林阿明", 3, "2026-05-06", 55.0),  # PR
        ]
        result = compute_batch_pr_leaderboard(sessions)
        self.assertEqual(result, [("林阿明", 2)])

    def test_ranked_by_pr_count_desc(self) -> None:
        sessions = [
            # 林阿明 3 次 PR
            _make("林阿明", 1, "2026-04-22", 45.0),
            _make("林阿明", 2, "2026-04-29", 47.0),
            _make("林阿明", 3, "2026-05-06", 49.0),
            _make("林阿明", 4, "2026-05-13", 51.0),
            # 王小華 1 次 PR
            _make("王小華", 1, "2026-04-22", 60.0),
            _make("王小華", 2, "2026-04-29", 65.0),
        ]
        result = compute_batch_pr_leaderboard(sessions)
        self.assertEqual(result[0][0], "林阿明")
        self.assertEqual(result[0][1], 3)
        self.assertEqual(result[1][0], "王小華")
        self.assertEqual(result[1][1], 1)

    def test_zero_pr_student_excluded(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-04-22", 45.0),
            _make("林阿明", 2, "2026-04-29", 50.0),   # PR
            # 王小華 持平 → 0 PR
            _make("王小華", 1, "2026-04-22", 60.0),
            _make("王小華", 2, "2026-04-29", 60.0),
        ]
        result = compute_batch_pr_leaderboard(sessions)
        names = [r[0] for r in result]
        self.assertIn("林阿明", names)
        self.assertNotIn("王小華", names)

    def test_tie_break_by_name(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-04-22", 45.0),
            _make("林阿明", 2, "2026-04-29", 50.0),
            _make("王小華", 1, "2026-04-22", 45.0),
            _make("王小華", 2, "2026-04-29", 50.0),
        ]
        result = compute_batch_pr_leaderboard(sessions)
        # 同 1 次 → 林 (0x6797) < 王 (0x738B)
        self.assertEqual([r[0] for r in result], ["林阿明", "王小華"])


class TestRenderBatchPrLeaderboard(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_batch_pr_leaderboard([]), "")

    def test_renders_ranked_list(self) -> None:
        out = render_batch_pr_leaderboard([("林阿明", 3), ("王小華", 1)])
        self.assertIn("PR 突破榜", out)
        self.assertIn("林阿明", out)
        self.assertIn("3", out)
        self.assertLess(out.find("林阿明"), out.find("王小華"))


class TestCliBatchEmitsPrLeaderboard(unittest.TestCase):
    def test_batch_summary_has_pr_leaderboard(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, w in enumerate([45.0, 50.0, 55.0], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
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
            content = (Path(out_td) / "_batch_summary.md").read_text(encoding="utf-8")
            self.assertIn("PR 突破榜", content)


if __name__ == "__main__":
    unittest.main()
