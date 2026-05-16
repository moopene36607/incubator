"""紅色測試 — --no-ai 骨架版保留下次課程計畫 + 恢復飲食.

接續 round 55:section 四 (下次課程重點) 與 五 (恢復/飲食提醒) 在 --no-ai
模式仍是「(待 AI 填)」placeholder,但 PT 在 JSON 的 next_session /
recovery_diet 已填了具體計畫與目標數字 — 逐字呈現 (PT 自己填的數字,
非 AI 編造,符合規範)。
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


def _session(next_session: dict, recovery_diet: dict) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=1, session_date="2026-05-15", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=50.0, rpe=8)],
        coach_observations=[], student_subjective=[],
        next_session=next_session, recovery_diet=recovery_diet,
    )


class TestSkeletonNextSession(unittest.TestCase):
    def test_theme_rendered(self) -> None:
        sess = _session(
            {"theme": "下半身主導 + 核心", "date": "2026-05-22",
             "focus": ["深蹲加重", "Pallof Press"]},
            {})
        out = render_skeleton_body(sess)
        self.assertIn("下半身主導 + 核心", out)

    def test_focus_bullets_rendered(self) -> None:
        sess = _session(
            {"theme": "X", "focus": ["深蹲加重 2.5 kg", "新增引體向上"]},
            {})
        out = render_skeleton_body(sess)
        self.assertIn("深蹲加重 2.5 kg", out)
        self.assertIn("新增引體向上", out)

    def test_empty_next_session_keeps_placeholder(self) -> None:
        sess = _session({}, {})
        section = render_skeleton_body(sess).split("下次課程重點", 1)[1]
        section = section.split("###", 1)[0]
        self.assertIn("待 AI 填", section)


class TestSkeletonRecoveryDiet(unittest.TestCase):
    def test_recovery_notes_rendered(self) -> None:
        sess = _session({}, {"notes": "本週睡眠優先,減少額外有氧"})
        out = render_skeleton_body(sess)
        self.assertIn("本週睡眠優先,減少額外有氧", out)

    def test_recovery_numbers_rendered(self) -> None:
        sess = _session({}, {
            "protein_target_g": 130,
            "sleep_target_hr": 7,
        })
        out = render_skeleton_body(sess)
        # PT 填的具體數字逐字呈現
        self.assertIn("130", out)
        self.assertIn("7", out)

    def test_empty_recovery_keeps_placeholder(self) -> None:
        sess = _session({}, {})
        section = render_skeleton_body(sess).split("恢復", 1)[1]
        self.assertIn("待 AI 填", section)


class TestBackwardCompat(unittest.TestCase):
    def test_no_arg_unchanged(self) -> None:
        out = render_skeleton_body()
        self.assertIn("下次課程重點", out)
        self.assertIn("待 AI 填", out)


class TestCliNoAiPreservesPlan(unittest.TestCase):
    def test_no_ai_report_has_next_session_and_recovery(self) -> None:
        with TemporaryDirectory() as td:
            p = json.loads(json.dumps(SAMPLE_PAYLOAD))
            p["next_session"] = {
                "theme": "拉系日 + 心肺",
                "focus": ["Lat Pulldown 強化背闊肌"],
            }
            p["recovery_diet"] = {"notes": "睡眠至少 7 小時"}
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
            self.assertIn("拉系日 + 心肺", content)
            self.assertIn("睡眠至少 7 小時", content)


if __name__ == "__main__":
    unittest.main()
