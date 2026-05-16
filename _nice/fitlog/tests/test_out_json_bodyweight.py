"""紅色測試 — build_session_metrics_json 補入體重 + 相對肌力.

round 21 的 --out-json metrics 是在體重/相對肌力 (round 49) 之前寫的,
所以 JSON 匯出缺這兩個欄位。dashboard 接 JSON 的人拿不到。本輪補上:
  bodyweight_kg     — 當堂體重 (沒記則 null)
  relative_strength — {exercise_code: 倍數} (沒體重則 null)
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
from metrics import build_session_metrics_json  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _session(bw: float | None) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=1, session_date="2026-05-15", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=70.0, rpe=8)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
        student_bodyweight_kg=bw,
    )


class TestMetricsJsonBodyweight(unittest.TestCase):
    def test_bodyweight_field_present_when_set(self) -> None:
        result = build_session_metrics_json(_session(70.0))
        self.assertEqual(result["bodyweight_kg"], 70.0)
        json.dumps(result)

    def test_bodyweight_null_when_absent(self) -> None:
        result = build_session_metrics_json(_session(None))
        self.assertIsNone(result["bodyweight_kg"])

    def test_relative_strength_present_when_bodyweight_set(self) -> None:
        result = build_session_metrics_json(_session(70.0))
        rel = result["relative_strength"]
        self.assertIsNotNone(rel)
        # 70 kg bench / 70 kg bw = 1.0
        self.assertAlmostEqual(rel["BENCH_PRESS"], 1.0, places=3)

    def test_relative_strength_null_when_no_bodyweight(self) -> None:
        result = build_session_metrics_json(_session(None))
        self.assertIsNone(result["relative_strength"])

    def test_existing_fields_still_present(self) -> None:
        result = build_session_metrics_json(_session(70.0))
        for key in ("total_tonnage_kg", "intensity_score", "rpe_zones",
                    "category_tonnage_kg"):
            self.assertIn(key, result)


class TestCliOutJsonBodyweight(unittest.TestCase):
    def test_out_json_includes_bodyweight_and_rel_strength(self) -> None:
        with TemporaryDirectory() as td:
            p = json.loads(json.dumps(SAMPLE_PAYLOAD))
            p["session"]["bodyweight_kg"] = 70.0
            in_path = Path(td) / "in.json"
            in_path.write_text(json.dumps(p, ensure_ascii=False),
                               encoding="utf-8")
            json_path = Path(td) / "metrics.json"
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(in_path),
                 "--out-json", str(json_path), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["bodyweight_kg"], 70.0)
            self.assertIsNotNone(data["relative_strength"])


if __name__ == "__main__":
    unittest.main()
