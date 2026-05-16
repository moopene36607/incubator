"""紅色測試 — 體重 + 相對肌力 (strength-to-bodyweight ratio).

PT 招牌話術:「你臥推終於破自身體重了」「深蹲 1.5 倍體重」。需要學員體重。
本輪在 session 加 optional bodyweight_kg,算每個加重動作的「最重 / 體重」
倍數。純函式;沒填體重 → None (不瞎猜)。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SessionInput, SetRecord, parse_payload  # noqa: E402
from metrics import (  # noqa: E402
    compute_relative_strength,
    render_relative_strength,
)
from schema import validate_payload_schema  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _session(sets: list[SetRecord], bw: float | None) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=1, session_date="2026-05-15", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
        student_bodyweight_kg=bw,
    )


def _set(code: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=4, reps_or_duration="8",
                     weight_kg=weight, rpe=7)


class TestComputeRelativeStrength(unittest.TestCase):
    def test_no_bodyweight_returns_none(self) -> None:
        sess = _session([_set("BENCH_PRESS", 50.0)], bw=None)
        self.assertIsNone(compute_relative_strength(sess))

    def test_zero_bodyweight_returns_none(self) -> None:
        sess = _session([_set("BENCH_PRESS", 50.0)], bw=0.0)
        self.assertIsNone(compute_relative_strength(sess))

    def test_single_exercise_ratio(self) -> None:
        # 臥推 70 kg / 體重 70 kg = 1.0×
        sess = _session([_set("BENCH_PRESS", 70.0)], bw=70.0)
        result = compute_relative_strength(sess)
        assert result is not None
        self.assertAlmostEqual(result["BENCH_PRESS"], 1.0, places=3)

    def test_takes_max_weight_per_exercise(self) -> None:
        sess = _session([
            _set("BENCH_PRESS", 50.0),
            _set("BENCH_PRESS", 65.0),
        ], bw=70.0)
        result = compute_relative_strength(sess)
        assert result is not None
        self.assertAlmostEqual(result["BENCH_PRESS"], 65.0 / 70.0, places=3)

    def test_bw_exercise_excluded(self) -> None:
        sess = _session([
            _set("BENCH_PRESS", 70.0),
            _set("PULL_UP", None),
        ], bw=70.0)
        result = compute_relative_strength(sess)
        assert result is not None
        self.assertIn("BENCH_PRESS", result)
        self.assertNotIn("PULL_UP", result)

    def test_no_weighted_sets_returns_none(self) -> None:
        sess = _session([_set("PULL_UP", None)], bw=70.0)
        self.assertIsNone(compute_relative_strength(sess))


class TestRenderRelativeStrength(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(render_relative_strength(None))

    def test_renders_ratios_sorted_desc(self) -> None:
        out = render_relative_strength(
            {"BENCH_PRESS": 1.0, "BB_BACK_SQUAT": 1.5})
        assert out is not None
        self.assertIn("相對肌力", out)
        self.assertIn("槓鈴臥推", out)
        self.assertIn("槓鈴背蹲舉", out)
        # squat 1.5 排在 bench 1.0 前
        self.assertLess(out.find("槓鈴背蹲舉"), out.find("槓鈴臥推"))
        self.assertIn("×", out)


class TestSchemaBodyweight(unittest.TestCase):
    def test_bodyweight_optional_absent_ok(self) -> None:
        self.assertEqual(validate_payload_schema(SAMPLE_PAYLOAD), [])

    def test_bodyweight_number_ok(self) -> None:
        p = json.loads(json.dumps(SAMPLE_PAYLOAD))
        p["session"]["bodyweight_kg"] = 72.5
        self.assertEqual(validate_payload_schema(p), [])

    def test_bodyweight_non_number_rejected(self) -> None:
        p = json.loads(json.dumps(SAMPLE_PAYLOAD))
        p["session"]["bodyweight_kg"] = "heavy"
        errors = validate_payload_schema(p)
        self.assertTrue(any("bodyweight" in e for e in errors))


class TestParsePayloadBodyweight(unittest.TestCase):
    def test_parse_reads_bodyweight(self) -> None:
        p = json.loads(json.dumps(SAMPLE_PAYLOAD))
        p["session"]["bodyweight_kg"] = 68.0
        session = parse_payload(p)
        self.assertEqual(session.student_bodyweight_kg, 68.0)

    def test_parse_absent_bodyweight_is_none(self) -> None:
        p = json.loads(json.dumps(SAMPLE_PAYLOAD))
        p["session"].pop("bodyweight_kg", None)
        session = parse_payload(p)
        self.assertIsNone(session.student_bodyweight_kg)


class TestCliEmitsRelativeStrength(unittest.TestCase):
    def test_session_md_shows_relative_strength(self) -> None:
        with TemporaryDirectory() as td:
            p = json.loads(json.dumps(SAMPLE_PAYLOAD))
            p["session"]["bodyweight_kg"] = 70.0
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
            self.assertIn("相對肌力", out_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
