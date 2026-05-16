"""紅色測試 — 本堂訓練肌群清單.

exercise_db 每個動作有 target_muscles ("股四頭/臀大肌/下背"),目前只在
動作表顯示。本輪彙整成「本堂練到的肌群」清單 — 學員一眼看懂今天練了
哪些肌群。純函式:拆 "/"、跨動作去重、按出現次數排序。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SessionInput, SetRecord  # noqa: E402
from metrics import compute_muscles_worked, render_muscles_worked  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _session(codes: list[str]) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=1, session_date="2026-05-15", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code=c, sets=4, reps_or_duration="8",
                        weight_kg=50.0, rpe=8) for c in codes],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestComputeMusclesWorked(unittest.TestCase):
    def test_empty_session(self) -> None:
        self.assertEqual(compute_muscles_worked(_session([])), [])

    def test_single_exercise_splits_slash(self) -> None:
        # BB_BACK_SQUAT target_muscles = "股四頭/臀大肌/下背"
        result = compute_muscles_worked(_session(["BB_BACK_SQUAT"]))
        self.assertIn("股四頭", result)
        self.assertIn("臀大肌", result)
        self.assertIn("下背", result)

    def test_dedup_across_exercises(self) -> None:
        # SQUAT 與 ROMANIAN_DL 都練臀大肌 → 只出現一次
        result = compute_muscles_worked(
            _session(["BB_BACK_SQUAT", "ROMANIAN_DL"]))
        self.assertEqual(result.count("臀大肌"), 1)

    def test_unknown_exercise_skipped(self) -> None:
        result = compute_muscles_worked(_session(["NOT_A_CODE"]))
        self.assertEqual(result, [])

    def test_sorted_by_frequency(self) -> None:
        # 3 個動作都練臀大肌 → 臀大肌 出現次數最高,排第一
        result = compute_muscles_worked(_session([
            "BB_BACK_SQUAT",   # 股四頭/臀大肌/下背
            "ROMANIAN_DL",     # 股二頭/臀大肌/下背
            "HIP_THRUST",      # 臀大肌/股二頭
        ]))
        self.assertEqual(result[0], "臀大肌")


class TestRenderMusclesWorked(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        self.assertIsNone(render_muscles_worked([]))

    def test_renders_muscle_list(self) -> None:
        out = render_muscles_worked(["臀大肌", "股四頭", "下背"])
        assert out is not None
        self.assertIn("訓練肌群", out)
        self.assertIn("臀大肌", out)
        self.assertIn("股四頭", out)


class TestCliEmitsMusclesWorked(unittest.TestCase):
    def test_session_md_has_muscles_worked(self) -> None:
        with TemporaryDirectory() as td:
            in_path = Path(td) / "in.json"
            in_path.write_text(json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                               encoding="utf-8")
            out_path = Path(td) / "out.md"
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(in_path),
                 "--out", str(out_path), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("訓練肌群", out_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
