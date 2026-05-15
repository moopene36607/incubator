"""紅色測試 — 單堂 RPE 強度區間分布 (warmup / working / max).

PT 看完報告會問:「這堂課的強度分配合理嗎?」目前報告只有 avg RPE 一個
數字,無法分辨「全堂 RPE 7 平穩」vs「3 set RPE 5 + 3 set RPE 10
(熱身過頭 / 極限太多)」。

本輪加 zone breakdown,把每 set 分為:
- 熱身 zone (RPE 1–5)
- 工作 zone (RPE 6–8)
- 極限 zone (RPE 9–10)

純函式回傳 count + percent,render 一行整合進 session markdown 報告。
RPE 是 None 的 set 不計入(沒判斷依據)。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from metrics import compute_rpe_zone_distribution, render_rpe_zone_distribution  # noqa: E402
from fitlog import SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _set(rpe: int | None) -> SetRecord:
    return SetRecord(
        exercise_code="BENCH_PRESS", sets=1, reps_or_duration="8",
        weight_kg=50.0, rpe=rpe,
    )


class TestComputeRpeZoneDistribution(unittest.TestCase):
    def test_empty_sets_returns_none(self) -> None:
        self.assertIsNone(compute_rpe_zone_distribution([]))

    def test_all_sets_no_rpe_returns_none(self) -> None:
        # 沒任何 set 有 RPE → 沒判斷依據,回 None
        self.assertIsNone(compute_rpe_zone_distribution([_set(None), _set(None)]))

    def test_warmup_zone_rpe_1_to_5(self) -> None:
        result = compute_rpe_zone_distribution(
            [_set(1), _set(3), _set(5)]
        )
        self.assertIsNotNone(result)
        assert result is not None  # for mypy
        self.assertEqual(result.warmup_count, 3)
        self.assertEqual(result.working_count, 0)
        self.assertEqual(result.max_count, 0)
        self.assertEqual(result.total_rated, 3)

    def test_working_zone_rpe_6_to_8(self) -> None:
        result = compute_rpe_zone_distribution(
            [_set(6), _set(7), _set(8)]
        )
        assert result is not None
        self.assertEqual(result.working_count, 3)
        self.assertEqual(result.warmup_count, 0)
        self.assertEqual(result.max_count, 0)

    def test_max_zone_rpe_9_and_10(self) -> None:
        result = compute_rpe_zone_distribution([_set(9), _set(10)])
        assert result is not None
        self.assertEqual(result.max_count, 2)
        self.assertEqual(result.warmup_count, 0)
        self.assertEqual(result.working_count, 0)

    def test_mixed_zones(self) -> None:
        # 2 熱身 + 5 工作 + 1 極限 = 8 total
        sets = (
            [_set(4), _set(5)]
            + [_set(6), _set(7), _set(7), _set(8), _set(8)]
            + [_set(10)]
        )
        result = compute_rpe_zone_distribution(sets)
        assert result is not None
        self.assertEqual(result.warmup_count, 2)
        self.assertEqual(result.working_count, 5)
        self.assertEqual(result.max_count, 1)
        self.assertEqual(result.total_rated, 8)
        # percents
        self.assertAlmostEqual(result.warmup_pct, 25.0, places=1)
        self.assertAlmostEqual(result.working_pct, 62.5, places=1)
        self.assertAlmostEqual(result.max_pct, 12.5, places=1)

    def test_none_rpes_skipped(self) -> None:
        result = compute_rpe_zone_distribution(
            [_set(7), _set(None), _set(8), _set(None)]
        )
        assert result is not None
        self.assertEqual(result.working_count, 2)
        self.assertEqual(result.total_rated, 2)

    def test_out_of_range_rpe_skipped(self) -> None:
        # RPE 0 / 11 / -1 不在 1-10,跳過 (validation 會警告但本函式仍要乾淨)
        result = compute_rpe_zone_distribution(
            [_set(0), _set(7), _set(11), _set(-1)]
        )
        assert result is not None
        self.assertEqual(result.working_count, 1)
        self.assertEqual(result.total_rated, 1)


class TestRenderRpeZoneDistribution(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(render_rpe_zone_distribution(None))

    def test_renders_one_line_with_counts_and_percents(self) -> None:
        dist = compute_rpe_zone_distribution(
            [_set(4), _set(7), _set(7), _set(10)]
        )
        line = render_rpe_zone_distribution(dist)
        assert line is not None
        self.assertIn("強度分布", line)
        self.assertIn("熱身", line)
        self.assertIn("工作", line)
        self.assertIn("極限", line)
        # 4 set total, 1 warmup (25%) / 2 working (50%) / 1 max (25%)
        self.assertIn("1 set", line)
        self.assertIn("2 set", line)
        self.assertIn("25%", line)
        self.assertIn("50%", line)

    def test_zero_zone_still_shown(self) -> None:
        # 全 working 也要顯示 0 set 熱身、0 set 極限 — 給 PT 完整視角
        dist = compute_rpe_zone_distribution([_set(7), _set(8)])
        line = render_rpe_zone_distribution(dist)
        assert line is not None
        self.assertIn("0 set", line)  # warmup + max 都 0
        self.assertIn("2 set", line)
        self.assertIn("100%", line)

    def test_format_starts_with_bolded_label(self) -> None:
        dist = compute_rpe_zone_distribution([_set(7)])
        line = render_rpe_zone_distribution(dist)
        assert line is not None
        self.assertTrue(line.startswith("**強度分布**:"))


class TestCliIncludesRpeZoneInSessionReport(unittest.TestCase):
    def test_session_md_includes_zone_line(self) -> None:
        # 確保 single-session report 有強度分布行
        with TemporaryDirectory() as td:
            payload_path = Path(td) / "in.json"
            payload_path.write_text(
                json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                encoding="utf-8",
            )
            out_path = Path(td) / "out.md"
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(payload_path),
                 "--out", str(out_path), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("強度分布", content)


if __name__ == "__main__":
    unittest.main()
