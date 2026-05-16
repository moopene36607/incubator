"""紅色測試 — _batch_summary.md 自動目錄 (ToC).

batch summary 已累積 ~11 個 ## section (學員出席 / 動作排行 / 多種排行 /
工作室週量 / 開課日分布 / 教練工作量 / 肌群分布 / PR 突破榜 / 缺席名單)。
學員 trend 早有自動 ToC (_insert_toc),但 batch summary 沒有 — 因為附加
section 是在 render_batch_summary 之後才 append 上去的。

本輪在所有 section append 完成後對最終 summary_md 套 _insert_toc,
讓這份長報告也能一眼導覽。
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


def _run_batch(n_students: int) -> str:
    with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
        for i in range(1, n_students + 1):
            p = json.loads(json.dumps(SAMPLE_PAYLOAD))
            p["student"]["name"] = f"Stu{i}"
            p["session"]["session_no"] = i
            p["session"]["date"] = f"2026-05-1{i}"
            (Path(in_td) / f"s{i}.json").write_text(
                json.dumps(p, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(
            [sys.executable, "fitlog.py", "--batch", in_td,
             "--out-dir", out_td, "--no-ai"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
        return (Path(out_td) / "_batch_summary.md").read_text(encoding="utf-8")


class TestBatchSummaryToc(unittest.TestCase):
    def test_has_toc_section(self) -> None:
        content = _run_batch(2)
        self.assertIn("## 目錄", content)

    def test_toc_lists_appended_sections(self) -> None:
        # ToC 必須涵蓋 render_batch_summary 之後 append 的 section
        content = _run_batch(3)
        toc_part = content.split("## 目錄", 1)[1].split("##", 1)[0]
        self.assertIn("開課日分布", toc_part)
        self.assertIn("學員出席", toc_part)

    def test_toc_before_first_real_section(self) -> None:
        content = _run_batch(2)
        # 目錄 應在「學員出席」這個第一個內容 section 之前
        self.assertLess(content.find("## 目錄"),
                        content.find("## 學員出席"))

    def test_toc_appears_once(self) -> None:
        content = _run_batch(2)
        self.assertEqual(content.count("## 目錄"), 1)


if __name__ == "__main__":
    unittest.main()
