"""紅色測試 — 訓練密度 (tonnage / minute) 量化「有多操」.

CrossFit / HIIT / 高密度肌力訓練最常用的 KPI。學員 60 分鐘做 6,200 kg
= 103 kg/min,直接量化單位時間搬了多少重量。

純函式 compute_training_density + render_training_density;整合進兩種
報告 (markdown + LINE)。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import (  # noqa: E402
    SetRecord,
    parse_payload,
    render_full_report,
    render_line_friendly,
    render_skeleton_body,
)
from metrics import (  # noqa: E402
    compute_training_density,
    render_training_density,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


def _load_sample():
    p = PROJECT_ROOT / "samples" / "sample_input.json"
    return parse_payload(json.loads(p.read_text(encoding="utf-8")))


class TestComputeTrainingDensity(unittest.TestCase):
    def test_typical_session(self) -> None:
        # 6200 / 60 = 103.33
        self.assertAlmostEqual(compute_training_density(6200.0, 60), 103.33, places=1)

    def test_zero_duration_returns_none(self) -> None:
        self.assertIsNone(compute_training_density(6200.0, 0))

    def test_negative_duration_returns_none(self) -> None:
        self.assertIsNone(compute_training_density(6200.0, -5))

    def test_zero_tonnage_returns_zero(self) -> None:
        self.assertEqual(compute_training_density(0.0, 60), 0.0)


class TestRenderTrainingDensity(unittest.TestCase):
    def test_typical_session_format(self) -> None:
        sess = _load_sample()
        # sample tonnage = 6200, duration = 60
        result = render_training_density(sess)
        self.assertIsNotNone(result)
        self.assertIn("訓練密度", result)
        self.assertIn("103", result)  # 103.33 → round to 103
        self.assertIn("60", result)   # duration_min in 註腳
        self.assertIn("kg", result)

    def test_all_bw_session_returns_none(self) -> None:
        # 全 BW (tonnage 0) → 沒密度可講
        sess = _load_sample()
        sess.sets = [_set("PULL_UP", 4, "8", None)]
        self.assertIsNone(render_training_density(sess))

    def test_zero_duration_returns_none(self) -> None:
        sess = _load_sample()
        sess.duration_min = 0
        self.assertIsNone(render_training_density(sess))


class TestReportIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _load_sample()
        self.body = render_skeleton_body()

    def test_markdown_includes_density(self) -> None:
        density = render_training_density(self.session)
        out = render_full_report(self.session, self.body, density_summary=density)
        self.assertIn("訓練密度", out)

    def test_line_includes_density(self) -> None:
        density = render_training_density(self.session)
        out = render_line_friendly(self.session, self.body, density_summary=density)
        # LINE 用「⚡ 密度:」前綴
        self.assertIn("密度", out)

    def test_markdown_omits_density_when_none(self) -> None:
        # 不傳 density → 不該出現「訓練密度」
        out = render_full_report(self.session, self.body)
        self.assertNotIn("訓練密度", out)


if __name__ == "__main__":
    unittest.main()
