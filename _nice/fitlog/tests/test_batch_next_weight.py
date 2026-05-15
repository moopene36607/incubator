"""紅色測試 — 批次模式補上 next_weight_summary (round 17 漏掉的功能).

單堂模式 (python3 fitlog.py X.json) 的 markdown 含「下次建議重量」段,
但批次模式 (python3 fitlog.py --batch DIR) 的個別 .md 不含。本輪修這個
consistency gap,讓批次與單堂輸出對齊。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _run_batch(input_dir: str, out_dir: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "fitlog.py", "--batch", input_dir,
         "--out-dir", out_dir, "--no-ai"],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )


class TestBatchIncludesNextWeightSummary(unittest.TestCase):
    def test_batch_md_contains_next_weight_when_weighted_with_rpe(self) -> None:
        # sample 有 BENCH_PRESS 50 kg RPE 8 → 該出現「下次建議重量」段
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            (Path(in_td) / "s1.json").write_text(
                json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False), encoding="utf-8")
            r = _run_batch(in_td, out_td)
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "s1.md").read_text(encoding="utf-8")
            self.assertIn("下次建議重量", content)

    def test_batch_md_omits_next_weight_when_all_bw(self) -> None:
        # 全 BW + 沒 RPE → 不該出現該段
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            payload = json.loads(json.dumps(SAMPLE_PAYLOAD))
            payload["session"]["sets"] = [
                {"exercise_code": "PULL_UP", "sets": 4,
                 "reps_or_duration": "8", "weight_kg": None, "rpe": None,
                 "note": ""},
            ]
            (Path(in_td) / "s1.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            r = _run_batch(in_td, out_td)
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "s1.md").read_text(encoding="utf-8")
            self.assertNotIn("下次建議重量", content)

    def test_batch_consistent_with_single_shot(self) -> None:
        # 跑同一份 input,單堂與批次該都產出含 next_weight section 的 .md
        with TemporaryDirectory() as work_td:
            input_path = Path(work_td) / "input.json"
            input_path.write_text(
                json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False), encoding="utf-8")
            single_out = Path(work_td) / "single.md"
            subprocess.run(
                [sys.executable, "fitlog.py", str(input_path),
                 "--no-ai", "--out", str(single_out)],
                cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
            )
            single_content = single_out.read_text(encoding="utf-8")

            batch_dir = Path(work_td) / "batch_in"
            batch_dir.mkdir()
            (batch_dir / "input.json").write_text(
                json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False), encoding="utf-8")
            batch_out_dir = Path(work_td) / "batch_out"
            _run_batch(str(batch_dir), str(batch_out_dir))
            batch_content = (batch_out_dir / "input.md").read_text(encoding="utf-8")

            # 兩邊都該含「下次建議重量」section
            self.assertIn("下次建議重量", single_content)
            self.assertIn("下次建議重量", batch_content)


if __name__ == "__main__":
    unittest.main()
