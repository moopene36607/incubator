"""紅色測試 — 每日彙總 1 行 emoji 摘要 (mobile-friendly LINE 推播).

PT 跑批次後想直接複製貼到 LINE 群組告訴老闆「今日業績」:
  💪 今日 6 堂 / 41,000 kg · 3 位學員 · 領先 王嘉偉 6,200 kg

純文字單行,寫到 _one_liner.txt 方便 mobile 複製貼上。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import (  # noqa: E402
    BatchSummary,
    SessionRanking,
    render_batch_one_liner,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _seed(input_dir: Path, names: list[str]) -> None:
    for stem, name in zip(("aming", "wang", "chen"), names):
        payload = json.loads(json.dumps(SAMPLE_PAYLOAD))
        payload["student"]["name"] = name
        (input_dir / f"{stem}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class TestRenderBatchOneLiner(unittest.TestCase):
    def test_empty_summary_returns_empty(self) -> None:
        # 0 sessions → 沒東西可講
        s = BatchSummary(n_sessions=0, total_tonnage_kg=0.0,
                         students={}, top_exercises=[])
        self.assertEqual(render_batch_one_liner(s), "")

    def test_typical_summary_format(self) -> None:
        s = BatchSummary(
            n_sessions=6, total_tonnage_kg=41000.0,
            students={"王嘉偉": 2, "林阿明": 2, "陳美玉": 2},
            top_exercises=[("BENCH_PRESS", 8000.0)],
            leaderboard=[
                SessionRanking(student_name="王嘉偉", session_no=1,
                               session_date="2026-05-10", tonnage_kg=6200.0),
            ],
        )
        result = render_batch_one_liner(s)
        self.assertIn("💪", result)
        self.assertIn("6 堂", result)
        self.assertIn("41,000 kg", result)
        self.assertIn("3 位學員", result)
        self.assertIn("王嘉偉", result)
        self.assertIn("6,200 kg", result)

    def test_no_leaderboard_no_lead_section(self) -> None:
        # 無 leaderboard → 不該有 "領先" 段
        s = BatchSummary(
            n_sessions=2, total_tonnage_kg=4000.0,
            students={"A": 1, "B": 1},
            top_exercises=[],
            leaderboard=[],
        )
        result = render_batch_one_liner(s)
        self.assertNotIn("領先", result)
        self.assertIn("2 堂", result)


class TestCliBatchProducesOneLinerFile(unittest.TestCase):
    def test_one_liner_txt_written(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed(Path(in_td), ["林阿明", "王小華", "陳美玉"])
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            one_liner = Path(out_td) / "_one_liner.txt"
            self.assertTrue(one_liner.exists())
            content = one_liner.read_text(encoding="utf-8")
            self.assertIn("💪", content)
            self.assertIn("3 堂", content)
            self.assertIn("位學員", content)


if __name__ == "__main__":
    unittest.main()
