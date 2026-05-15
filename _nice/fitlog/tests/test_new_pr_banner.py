"""紅色測試 — 當堂打破歷來最佳 PR 慶祝 banner.

現有 `compute_pr_deltas(prev, curr)` 只看上一堂 vs 這一堂,如果學員上週
力竭 47 → 本週 48 也會被標 PR,但其實 6 個月前他已經做過 50 — 那不是
真正的 all-time PR。

本輪加 `detect_new_prs(sessions, student, current)`,看當堂 max
weight (或 BW max reps) 是否 **嚴格大於所有早於當堂的 sessions 的 max**。
若是,回傳 NewPrRecord 給 banner。banner 在報告頂端慶祝:
  🏆 PR 突破!:槓鈴臥推 50 kg (打破 6 個月來最高 47.5 kg) ·
                引體向上 8 reps (打破上回最高 5 reps)

只比同 exercise 的最高紀錄,不算 tonnage 提升。BW reps 也納入。
數字邏輯純函式;LLM 不能算。
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
    NewPrRecord,
    detect_new_prs,
    render_new_pr_banner,
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


class TestDetectNewPrs(unittest.TestCase):
    def test_only_one_session_no_prior_so_no_banner(self) -> None:
        # 第一堂沒有歷史可比,不算 PR
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        self.assertEqual(detect_new_prs([sess], "林阿明", sess), [])

    def test_weight_pr_detected(self) -> None:
        prev = _make("林阿明", 1, "2026-04-22",
                     [_set("BENCH_PRESS", 4, "8", 45.0)])
        curr = _make("林阿明", 2, "2026-04-29",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = detect_new_prs([prev, curr], "林阿明", curr)
        self.assertEqual(len(result), 1)
        pr = result[0]
        self.assertEqual(pr.exercise_code, "BENCH_PRESS")
        self.assertEqual(pr.kind, "weight")
        self.assertEqual(pr.curr_value, 50.0)
        self.assertEqual(pr.prev_best, 45.0)

    def test_same_weight_not_pr(self) -> None:
        # 平歷史最高 ≠ PR (嚴格 > 才算 PR)
        prev = _make("林阿明", 1, "2026-04-22",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        curr = _make("林阿明", 2, "2026-04-29",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        self.assertEqual(detect_new_prs([prev, curr], "林阿明", curr), [])

    def test_lower_than_history_not_pr(self) -> None:
        # 6 個月前做過 60,今天只做 50 → 不是 PR
        long_ago = _make("林阿明", 1, "2025-11-01",
                         [_set("BENCH_PRESS", 4, "8", 60.0)])
        curr = _make("林阿明", 5, "2026-05-10",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        self.assertEqual(detect_new_prs([long_ago, curr], "林阿明", curr), [])

    def test_bw_reps_pr_detected(self) -> None:
        prev = _make("林阿明", 1, "2026-04-22",
                     [_set("PULL_UP", 3, "5", None)])
        curr = _make("林阿明", 2, "2026-04-29",
                     [_set("PULL_UP", 3, "8", None)])
        result = detect_new_prs([prev, curr], "林阿明", curr)
        self.assertEqual(len(result), 1)
        pr = result[0]
        self.assertEqual(pr.exercise_code, "PULL_UP")
        self.assertEqual(pr.kind, "bw_reps")
        self.assertEqual(pr.curr_value, 8)
        self.assertEqual(pr.prev_best, 5)

    def test_first_time_exercise_is_pr(self) -> None:
        # 從沒做過這個動作 → 當堂第一次就是 PR
        prev = _make("林阿明", 1, "2026-04-22",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        curr = _make("林阿明", 2, "2026-04-29",
                     [_set("DEADLIFT", 4, "5", 80.0)])
        result = detect_new_prs([prev, curr], "林阿明", curr)
        # DEADLIFT 第一次出現 → PR (prev_best=None / 0)
        codes = {pr.exercise_code for pr in result}
        self.assertIn("DEADLIFT", codes)

    def test_other_students_ignored(self) -> None:
        # 王小華比 林阿明 PR 高不影響
        a = _make("王小華", 1, "2026-04-22",
                  [_set("BENCH_PRESS", 4, "8", 100.0)])
        prev = _make("林阿明", 1, "2026-04-22",
                     [_set("BENCH_PRESS", 4, "8", 45.0)])
        curr = _make("林阿明", 2, "2026-04-29",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = detect_new_prs([a, prev, curr], "林阿明", curr)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].exercise_code, "BENCH_PRESS")

    def test_multiple_prs_in_one_session(self) -> None:
        prev = _make("林阿明", 1, "2026-04-22", [
            _set("BENCH_PRESS", 4, "8", 45.0),
            _set("PULL_UP", 3, "5", None),
        ])
        curr = _make("林阿明", 2, "2026-04-29", [
            _set("BENCH_PRESS", 4, "8", 50.0),
            _set("PULL_UP", 3, "8", None),
        ])
        result = detect_new_prs([prev, curr], "林阿明", curr)
        self.assertEqual(len(result), 2)
        kinds = {pr.kind for pr in result}
        self.assertEqual(kinds, {"weight", "bw_reps"})


class TestRenderNewPrBanner(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        self.assertIsNone(render_new_pr_banner([]))

    def test_single_weight_pr(self) -> None:
        prs = [NewPrRecord(
            exercise_code="BENCH_PRESS", kind="weight",
            curr_value=50.0, prev_best=45.0,
        )]
        line = render_new_pr_banner(prs)
        assert line is not None
        self.assertIn("🏆", line)
        self.assertIn("PR 突破", line)
        self.assertIn("槓鈴臥推", line)
        self.assertIn("50", line)
        self.assertIn("45", line)

    def test_single_bw_reps_pr(self) -> None:
        prs = [NewPrRecord(
            exercise_code="PULL_UP", kind="bw_reps",
            curr_value=8, prev_best=5,
        )]
        line = render_new_pr_banner(prs)
        assert line is not None
        self.assertIn("引體向上", line)
        self.assertIn("8", line)
        self.assertIn("reps", line)

    def test_first_time_exercise_no_history_mentioned(self) -> None:
        # prev_best 0 / None 表示第一次,banner 應該說「首次」
        prs = [NewPrRecord(
            exercise_code="DEADLIFT", kind="weight",
            curr_value=80.0, prev_best=0.0,
        )]
        line = render_new_pr_banner(prs)
        assert line is not None
        self.assertIn("傳統硬舉", line)
        self.assertIn("80", line)
        self.assertIn("首次", line)

    def test_multiple_prs_joined(self) -> None:
        prs = [
            NewPrRecord(exercise_code="BENCH_PRESS", kind="weight",
                        curr_value=50.0, prev_best=45.0),
            NewPrRecord(exercise_code="PULL_UP", kind="bw_reps",
                        curr_value=8, prev_best=5),
        ]
        line = render_new_pr_banner(prs)
        assert line is not None
        self.assertIn("槓鈴臥推", line)
        self.assertIn("引體向上", line)


class TestCliBatchEmitsNewPrBanner(unittest.TestCase):
    def test_session_md_has_pr_banner_when_new_max(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, w in enumerate([45.0, 50.0], 1):
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
            # 第二堂 .md 應包含 PR 突破 banner
            s2_md = (Path(out_td) / "s2.md").read_text(encoding="utf-8")
            self.assertIn("PR 突破", s2_md)
            self.assertIn("槓鈴臥推", s2_md)


if __name__ == "__main__":
    unittest.main()
