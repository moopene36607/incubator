"""紅色測試 — `--out-json` 單堂指標結構化輸出.

PT 想把 fitlog 接 dashboard / LINE bot,markdown 不好 parse。本輪加
build_session_metrics_json(session) → dict,把所有純函式算出的數字
(噸位 / 密度 / 強度分數 / RPE zone / 分類訓練量) 包成可 json.dumps 的
dict。CLI 加 --out-json PATH 旗標。

只放純函式算出的數字 — AI 散文不進 JSON (那不是結構化資料)。
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


def _session(sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="增肌",
        session_no=7, session_date="2026-05-15", duration_min=60,
        coach_name="陳教練", studio_name="硬舉工作室", contact="",
        theme="推系日", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, sets: int, reps: str, weight: float | None,
         rpe: int | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=rpe)


class TestBuildSessionMetricsJson(unittest.TestCase):
    def test_returns_json_serializable_dict(self) -> None:
        sess = _session([_set("BENCH_PRESS", 4, "8", 50.0, 8)])
        result = build_session_metrics_json(sess)
        self.assertIsInstance(result, dict)
        # 一定要能 json.dumps 不噴錯
        json.dumps(result)

    def test_includes_session_metadata(self) -> None:
        sess = _session([_set("BENCH_PRESS", 4, "8", 50.0, 8)])
        result = build_session_metrics_json(sess)
        self.assertEqual(result["student_name"], "林阿明")
        self.assertEqual(result["session_no"], 7)
        self.assertEqual(result["session_date"], "2026-05-15")
        self.assertEqual(result["duration_min"], 60)
        self.assertEqual(result["theme"], "推系日")

    def test_includes_total_tonnage(self) -> None:
        # 4 × 8 × 50 = 1600
        sess = _session([_set("BENCH_PRESS", 4, "8", 50.0, 8)])
        result = build_session_metrics_json(sess)
        self.assertEqual(result["total_tonnage_kg"], 1600.0)

    def test_includes_intensity_score(self) -> None:
        # 1600 × 0.8 = 1280
        sess = _session([_set("BENCH_PRESS", 4, "8", 50.0, 8)])
        result = build_session_metrics_json(sess)
        self.assertEqual(result["intensity_score"], 1280.0)

    def test_includes_training_density(self) -> None:
        sess = _session([_set("BENCH_PRESS", 4, "8", 50.0, 8)])
        result = build_session_metrics_json(sess)
        # 1600 / 60 分鐘
        self.assertAlmostEqual(result["training_density_kg_per_min"],
                               1600.0 / 60, places=4)

    def test_includes_category_tonnage(self) -> None:
        sess = _session([
            _set("BENCH_PRESS", 4, "8", 50.0, 8),     # push 1600
            _set("BB_BACK_SQUAT", 5, "5", 60.0, 7),   # legs 1500
        ])
        result = build_session_metrics_json(sess)
        cats = result["category_tonnage_kg"]
        self.assertEqual(cats["push"], 1600.0)
        self.assertEqual(cats["legs"], 1500.0)

    def test_includes_rpe_zone_distribution(self) -> None:
        sess = _session([
            _set("BENCH_PRESS", 1, "8", 50.0, 4),   # warmup
            _set("BENCH_PRESS", 1, "8", 50.0, 7),   # working
            _set("BENCH_PRESS", 1, "8", 50.0, 10),  # max
        ])
        result = build_session_metrics_json(sess)
        zone = result["rpe_zones"]
        self.assertEqual(zone["warmup"], 1)
        self.assertEqual(zone["working"], 1)
        self.assertEqual(zone["max"], 1)

    def test_includes_set_count(self) -> None:
        sess = _session([
            _set("BENCH_PRESS", 4, "8", 50.0, 8),
            _set("PULL_UP", 3, "8", None, 7),
        ])
        result = build_session_metrics_json(sess)
        self.assertEqual(result["n_set_records"], 2)

    def test_all_bw_session_handles_none_metrics(self) -> None:
        # 全 BW → tonnage 0,intensity / density 應為 None (json null) 不報錯
        sess = _session([_set("PULL_UP", 3, "8", None, 7)])
        result = build_session_metrics_json(sess)
        json.dumps(result)  # 不噴錯
        self.assertEqual(result["total_tonnage_kg"], 0.0)
        self.assertIsNone(result["intensity_score"])


class TestCliOutJsonFlag(unittest.TestCase):
    def test_out_json_writes_valid_json_file(self) -> None:
        with TemporaryDirectory() as td:
            in_path = Path(td) / "in.json"
            in_path.write_text(json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                               encoding="utf-8")
            json_path = Path(td) / "metrics.json"
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(in_path),
                 "--out-json", str(json_path), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(json_path.exists())
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("total_tonnage_kg", data)
            self.assertIn("student_name", data)
            self.assertIn("rpe_zones", data)


if __name__ == "__main__":
    unittest.main()
