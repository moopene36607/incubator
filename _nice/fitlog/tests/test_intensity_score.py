"""紅色測試 — 單堂訓練強度分數 (intensity score).

PT 想跨堂比較「哪堂最操?」目前有總噸位 (3000 kg) 跟平均 RPE (8.0) 兩個
分開的數字,但學員會問「我這堂比上次累嗎?」沒有單一指標就會 hand-wave。

本輪用業界常見的 RPE-weighted volume:
    intensity_score = tonnage_kg × (avg_rpe / 10)

整數結果,沒有單位 (純比較用)。tonnage 0 (全 BW) 或無 RPE 的堂 → None
(無法計算,不勉強)。

純函式,LLM 不能算。
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
from metrics import (  # noqa: E402
    compute_session_intensity_score,
    render_session_intensity_score,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _session(sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=1, session_date="2026-05-15", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(reps: str, weight: float | None, rpe: int | None) -> SetRecord:
    return SetRecord(exercise_code="BENCH_PRESS", sets=1,
                     reps_or_duration=reps, weight_kg=weight, rpe=rpe)


class TestComputeSessionIntensityScore(unittest.TestCase):
    def test_empty_sets_returns_none(self) -> None:
        self.assertIsNone(compute_session_intensity_score(_session([])))

    def test_all_bw_returns_none(self) -> None:
        sess = _session([
            SetRecord(exercise_code="PULL_UP", sets=3,
                      reps_or_duration="8", weight_kg=None, rpe=7),
        ])
        self.assertIsNone(compute_session_intensity_score(sess))

    def test_no_rpe_returns_none(self) -> None:
        sess = _session([_set("8", 50.0, None), _set("8", 50.0, None)])
        self.assertIsNone(compute_session_intensity_score(sess))

    def test_single_set_score(self) -> None:
        # 1 × 8 × 50 = 400 tonnage;avg RPE 8 → score 400 × 0.8 = 320
        sess = _session([_set("8", 50.0, 8)])
        self.assertEqual(compute_session_intensity_score(sess), 320.0)

    def test_multiple_sets_avg_rpe(self) -> None:
        # RPE 7 + 8 + 9 → avg 8;tonnage 3 × 8 × 50 = 1200 → 1200 × 0.8 = 960
        sess = _session([
            _set("8", 50.0, 7),
            _set("8", 50.0, 8),
            _set("8", 50.0, 9),
        ])
        self.assertEqual(compute_session_intensity_score(sess), 960.0)

    def test_partial_rpe_uses_only_rated_sets_for_avg(self) -> None:
        # 1 set 有 RPE 8, 1 set 沒 → avg RPE = 8;tonnage 仍算全部 800
        # score = 800 × 0.8 = 640
        sess = _session([
            _set("8", 50.0, 8),
            _set("8", 50.0, None),
        ])
        self.assertEqual(compute_session_intensity_score(sess), 640.0)

    def test_mixed_bw_and_weighted(self) -> None:
        # weighted: 1×8×50 = 400, RPE 8
        # BW: PULL_UP 不計 tonnage,但 RPE 7 也算入 avg → avg=7.5
        # score = 400 × 0.75 = 300
        sess = _session([
            _set("8", 50.0, 8),
            SetRecord(exercise_code="PULL_UP", sets=1,
                      reps_or_duration="8", weight_kg=None, rpe=7),
        ])
        self.assertEqual(compute_session_intensity_score(sess), 300.0)


class TestRenderSessionIntensityScore(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(render_session_intensity_score(None))

    def test_renders_with_label_and_number(self) -> None:
        line = render_session_intensity_score(960.0)
        assert line is not None
        self.assertIn("訓練強度分數", line)
        self.assertIn("960", line)

    def test_starts_bolded(self) -> None:
        line = render_session_intensity_score(320.0)
        assert line is not None
        self.assertTrue(line.startswith("**訓練強度分數**"))


class TestCliEmitsIntensityScore(unittest.TestCase):
    def test_single_session_md_contains_intensity_score(self) -> None:
        with TemporaryDirectory() as td:
            in_path = Path(td) / "in.json"
            in_path.write_text(
                json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                encoding="utf-8",
            )
            out_path = Path(td) / "out.md"
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(in_path),
                 "--out", str(out_path), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("訓練強度分數", content)


if __name__ == "__main__":
    unittest.main()
