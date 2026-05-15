"""紅色測試 — per-session 1-liner 給單一學員 LINE 推播.

Round 40 加批次彙總 1-liner (給老闆/業績夥伴看)。本輪做 per-session:
PT 跑批次後每堂課多寫一份 stem.one_liner.txt,可複製給該學員 LINE:
  💪 林阿明 第 12 堂 · 6,200 kg · 60 min · 主題:全身肌力 · 5 PR

格式設計:
- 全 BW (tonnage 0) → 顯示 "BW only"
- 0 PR (無 prev session 對比) → 不顯示 PR 段
- 無 theme → 不顯示主題段
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import render_session_one_liner  # noqa: E402
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, session_no: int, date: str, duration: int, theme: str,
          sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date=date, duration_min=duration,
        coach_name="C", studio_name="S", contact="",
        theme=theme, sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


class TestRenderSessionOneLiner(unittest.TestCase):
    def test_basic_format(self) -> None:
        sess = _make("林阿明", 12, "2026-05-13", 60, "全身肌力",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = render_session_one_liner(sess)
        self.assertIn("💪", result)
        self.assertIn("林阿明", result)
        self.assertIn("第 12 堂", result)
        self.assertIn("1,600 kg", result)
        self.assertIn("60 min", result)
        self.assertIn("主題:全身肌力", result)

    def test_bw_only_session(self) -> None:
        sess = _make("林阿明", 1, "2026-05-13", 30, "BW circuit",
                     [_set("PULL_UP", 4, "8", None)])
        result = render_session_one_liner(sess)
        self.assertIn("BW only", result)
        # 不該有 "0 kg" 之類誤導
        self.assertNotIn("0 kg", result)

    def test_with_pr_count(self) -> None:
        sess = _make("林阿明", 12, "2026-05-13", 60, "test",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = render_session_one_liner(sess, pr_count=3)
        self.assertIn("3 PR", result)

    def test_zero_pr_count_not_shown(self) -> None:
        sess = _make("林阿明", 12, "2026-05-13", 60, "test",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = render_session_one_liner(sess, pr_count=0)
        self.assertNotIn("PR", result)

    def test_empty_theme_not_shown(self) -> None:
        sess = _make("林阿明", 12, "2026-05-13", 60, "",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = render_session_one_liner(sess)
        self.assertNotIn("主題:", result)


class TestCliBatchProducesSessionOneLinerFiles(unittest.TestCase):
    def test_batch_writes_one_liner_per_session(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for stem, name in (("aming", "林阿明"), ("wang", "王小華")):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = name
                (Path(in_td) / f"{stem}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(out_td) / "aming.one_liner.txt").exists())
            self.assertTrue((Path(out_td) / "wang.one_liner.txt").exists())
            content = (Path(out_td) / "aming.one_liner.txt").read_text(encoding="utf-8")
            self.assertIn("💪", content)
            self.assertIn("林阿明", content)


if __name__ == "__main__":
    unittest.main()
