"""紅色測試 — --no-ai 骨架版保留教練觀察 / 學員主述.

PT 在 JSON 填了 coach_observations / student_subjective,但 --no-ai 模式
的 render_skeleton_body 整段都是「(待 AI 填)」placeholder — PT 自己打的
觀察 notes 完全沒出現在報告裡,等於白填。

本輪:render_skeleton_body 接 optional session,若有觀察資料,「身體反應
與觀察」段落直接逐字列出 PT 輸入(教練自己的話,不是 AI 編造,安全)。
不傳 session → 維持舊 placeholder 行為 (向後相容)。
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


def _session(observations: list[str],
             subjective: list[str]) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=1, session_date="2026-05-15", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=50.0, rpe=8)],
        coach_observations=observations,
        student_subjective=subjective,
        next_session={}, recovery_diet={},
    )


class TestSkeletonBackwardCompat(unittest.TestCase):
    def test_no_arg_still_works(self) -> None:
        out = render_skeleton_body()
        self.assertIn("今日訓練摘要", out)
        self.assertIn("待 AI 填", out)

    def test_none_session_placeholder(self) -> None:
        out = render_skeleton_body(None)
        self.assertIn("身體反應與觀察", out)


class TestSkeletonEmbedsObservations(unittest.TestCase):
    def test_coach_observation_verbatim(self) -> None:
        sess = _session(["膝蓋追蹤良好", "髖鉸鏈有進步"], [])
        out = render_skeleton_body(sess)
        self.assertIn("膝蓋追蹤良好", out)
        self.assertIn("髖鉸鏈有進步", out)

    def test_student_subjective_verbatim(self) -> None:
        sess = _session([], ["下背稍緊", "睡眠不足"])
        out = render_skeleton_body(sess)
        self.assertIn("下背稍緊", out)
        self.assertIn("睡眠不足", out)

    def test_observations_replace_placeholder(self) -> None:
        # 有觀察資料時,該段不該再是「待 AI 填」
        sess = _session(["膝蓋追蹤良好"], ["下背稍緊"])
        out = render_skeleton_body(sess)
        section = out.split("身體反應與觀察", 1)[1].split("###", 1)[0]
        self.assertNotIn("待 AI 填", section)

    def test_empty_observations_keeps_placeholder(self) -> None:
        sess = _session([], [])
        out = render_skeleton_body(sess)
        section = out.split("身體反應與觀察", 1)[1].split("###", 1)[0]
        self.assertIn("待 AI 填", section)

    def test_subjective_labelled_distinctly(self) -> None:
        # 學員主述 應與教練觀察區分標示
        sess = _session(["教練看到的"], ["學員說的"])
        out = render_skeleton_body(sess)
        self.assertIn("學員主述", out)


class TestCliNoAiPreservesObservations(unittest.TestCase):
    def test_no_ai_report_contains_observations(self) -> None:
        with TemporaryDirectory() as td:
            p = json.loads(json.dumps(SAMPLE_PAYLOAD))
            p["coach_observations"] = ["深蹲深度明顯改善"]
            p["student_subjective"] = ["右肩有點緊"]
            in_path = Path(td) / "in.json"
            in_path.write_text(json.dumps(p, ensure_ascii=False),
                               encoding="utf-8")
            out_path = Path(td) / "out.md"
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(in_path),
                 "--out", str(out_path), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("深蹲深度明顯改善", content)
            self.assertIn("右肩有點緊", content)


if __name__ == "__main__":
    unittest.main()
