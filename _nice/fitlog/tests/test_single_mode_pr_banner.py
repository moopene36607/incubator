"""紅色測試 — 單堂模式 --prev 也產 all-time PR 突破 banner.

detect_new_prs / render_new_pr_banner 目前只在 --batch 模式被呼叫。單堂
模式即使帶了 --prev,也只算 prev-vs-curr 的「進步亮點」(pr_summary),
沒有頂端那條醒目的「🏆 PR 突破!」banner。

本輪:單堂模式有 --prev 時,用 [prev, curr] 兩堂跑 detect_new_prs,
curr 打破 prev 的 max → banner 出現在報告頂端。
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


def _payload(student: str, sno: int, date: str, bench_w: float) -> dict:
    p = json.loads(json.dumps(SAMPLE_PAYLOAD))
    p["student"]["name"] = student
    p["session"]["session_no"] = sno
    p["session"]["date"] = date
    for s in p["session"]["sets"]:
        if s["exercise_code"] == "BENCH_PRESS":
            s["weight_kg"] = bench_w
    return p


class TestSingleModePrBanner(unittest.TestCase):
    def test_prev_with_improvement_emits_pr_banner(self) -> None:
        with TemporaryDirectory() as td:
            prev = Path(td) / "prev.json"
            curr = Path(td) / "curr.json"
            out = Path(td) / "out.md"
            prev.write_text(json.dumps(
                _payload("林阿明", 1, "2026-04-22", 45.0), ensure_ascii=False),
                encoding="utf-8")
            curr.write_text(json.dumps(
                _payload("林阿明", 2, "2026-04-29", 55.0), ensure_ascii=False),
                encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(curr),
                 "--prev", str(prev), "--out", str(out), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = out.read_text(encoding="utf-8")
            self.assertIn("PR 突破", content)
            self.assertIn("槓鈴臥推", content)

    def test_prev_without_improvement_no_banner(self) -> None:
        # curr 比 prev 輕 → 沒 PR
        with TemporaryDirectory() as td:
            prev = Path(td) / "prev.json"
            curr = Path(td) / "curr.json"
            out = Path(td) / "out.md"
            prev.write_text(json.dumps(
                _payload("林阿明", 1, "2026-04-22", 60.0), ensure_ascii=False),
                encoding="utf-8")
            curr.write_text(json.dumps(
                _payload("林阿明", 2, "2026-04-29", 50.0), ensure_ascii=False),
                encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(curr),
                 "--prev", str(prev), "--out", str(out), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = out.read_text(encoding="utf-8")
            self.assertNotIn("PR 突破", content)

    def test_no_prev_no_banner(self) -> None:
        # 沒 --prev → 沒歷史可比 → 沒 banner
        with TemporaryDirectory() as td:
            curr = Path(td) / "curr.json"
            out = Path(td) / "out.md"
            curr.write_text(json.dumps(
                _payload("林阿明", 2, "2026-04-29", 55.0), ensure_ascii=False),
                encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(curr),
                 "--out", str(out), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = out.read_text(encoding="utf-8")
            self.assertNotIn("PR 突破", content)

    def test_missing_prev_file_does_not_crash(self) -> None:
        # --prev 指到不存在的檔 → warning 但不 crash,也沒 banner
        with TemporaryDirectory() as td:
            curr = Path(td) / "curr.json"
            out = Path(td) / "out.md"
            curr.write_text(json.dumps(
                _payload("林阿明", 2, "2026-04-29", 55.0), ensure_ascii=False),
                encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(curr),
                 "--prev", str(Path(td) / "nope.json"),
                 "--out", str(out), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
