"""紅色測試 — 本堂訓練肌群同步到 LINE 版 + JSON 匯出.

round 59 的 compute_muscles_worked 只進了 markdown 報告。本輪把它擴到
另外兩個輸出管道,保持一致:
- LINE 純文字版 (學員最常看的管道)
- --out-json metrics JSON (dashboard 整合)
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import (  # noqa: E402
    SessionInput,
    SetRecord,
    render_line_friendly,
    render_skeleton_body,
)
from metrics import build_session_metrics_json  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _session(codes: list[str]) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=3, session_date="2026-05-15", duration_min=60,
        coach_name="陳教練", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code=c, sets=4, reps_or_duration="8",
                        weight_kg=50.0, rpe=8) for c in codes],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestLineMusclesWorked(unittest.TestCase):
    def test_line_includes_muscles(self) -> None:
        sess = _session(["BB_BACK_SQUAT"])
        out = render_line_friendly(sess, render_skeleton_body(sess))
        self.assertIn("訓練肌群", out)
        self.assertIn("股四頭", out)

    def test_line_no_known_exercise_no_muscles(self) -> None:
        sess = _session(["NOT_A_CODE"])
        out = render_line_friendly(sess, render_skeleton_body(sess))
        self.assertNotIn("訓練肌群", out)


class TestJsonMusclesWorked(unittest.TestCase):
    def test_metrics_json_has_muscles_worked(self) -> None:
        result = build_session_metrics_json(_session(["BB_BACK_SQUAT"]))
        self.assertIn("muscles_worked", result)
        self.assertIn("股四頭", result["muscles_worked"])
        json.dumps(result)

    def test_metrics_json_muscles_empty_for_unknown(self) -> None:
        result = build_session_metrics_json(_session(["NOT_A_CODE"]))
        self.assertEqual(result["muscles_worked"], [])


class TestCliOutJsonMuscles(unittest.TestCase):
    def test_out_json_includes_muscles_worked(self) -> None:
        with TemporaryDirectory() as td:
            in_path = Path(td) / "in.json"
            in_path.write_text(json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                               encoding="utf-8")
            json_path = Path(td) / "m.json"
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(in_path),
                 "--out-json", str(json_path), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("muscles_worked", data)
            self.assertIsInstance(data["muscles_worked"], list)


if __name__ == "__main__":
    unittest.main()
