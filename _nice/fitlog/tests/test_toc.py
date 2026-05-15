"""紅色測試 — 學員 .md 自動生成 ToC (目錄).

學員 .md 已有 5+ sections (各堂訓練量 / 訓練量趨勢 / 主要動作進度 /
目標達成進度 / 歷來最佳),頁面長了不易導覽。本輪自動生成 ToC 列出
所有 ## headers,讓學員可一眼看到頁面結構。

設計準則:
- 0 / 1 個 section 不生 ToC (太短沒必要)
- ToC 自身不該被列入 (避免遞迴)
- ToC 插在 # title 後 / 第一個 ## section 前
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
    AllTimeBest,
    StudentTrend,
    StudentTrendPoint,
    _insert_toc,
    render_student_trend,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


class TestInsertToc(unittest.TestCase):
    def test_no_sections_no_toc(self) -> None:
        text = "# Title\n\n"
        self.assertEqual(_insert_toc(text), text)

    def test_single_section_no_toc(self) -> None:
        text = "# Title\n\n## Section A\n\nbody\n"
        self.assertEqual(_insert_toc(text), text)

    def test_two_sections_inserts_toc(self) -> None:
        text = "# Title\n\n## Section A\n\nbody A\n\n## Section B\n\nbody B\n"
        result = _insert_toc(text)
        self.assertIn("## 目錄", result)
        self.assertIn("- Section A", result)
        self.assertIn("- Section B", result)

    def test_toc_appears_after_title_before_first_section(self) -> None:
        text = "# Title\n\n## Section A\n\nbody A\n\n## Section B\n\nbody B\n"
        result = _insert_toc(text)
        self.assertLess(result.find("## 目錄"), result.find("## Section A"))

    def test_toc_does_not_self_reference(self) -> None:
        # 確保 ToC 自己的 ## 目錄 不會被列進 ToC list
        text = "# Title\n\n## Section A\n\nbody\n\n## Section B\n\nbody\n"
        result = _insert_toc(text)
        # ToC body 不該有 "- 目錄" entry
        toc_section = result.split("## 目錄")[1].split("## Section A")[0]
        self.assertNotIn("- 目錄", toc_section)

    def test_chinese_section_names_listed(self) -> None:
        text = "# 林阿明\n\n## 各堂訓練量\n\nbody\n\n## 歷來最佳\n\nbody\n"
        result = _insert_toc(text)
        self.assertIn("- 各堂訓練量", result)
        self.assertIn("- 歷來最佳", result)


class TestRenderStudentTrendIncludesToc(unittest.TestCase):
    def test_multi_section_trend_has_toc(self) -> None:
        trend = StudentTrend(
            student_name="林阿明",
            points=[StudentTrendPoint(date="2026-05-10", session_no=1,
                                       tonnage_kg=1600.0)],
            total_tonnage=1600.0,
        )
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=50.0,
            on_session_no=1, on_session_date="2026-05-10",
        )}
        out = render_student_trend(trend, all_time_prs=prs)
        # 至少 2 sections (各堂訓練量 + 歷來最佳) → 該有 ToC
        self.assertIn("## 目錄", out)
        self.assertIn("- 各堂訓練量", out)
        self.assertIn("- 歷來最佳", out)

    def test_minimal_trend_no_toc(self) -> None:
        # 只有 trend 表 (1 section) → 不該有 ToC
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        out = render_student_trend(trend)
        self.assertNotIn("## 目錄", out)


class TestCliBatchProducesToc(unittest.TestCase):
    def test_student_md_includes_toc(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            base["student"]["name"] = "林阿明"
            base["student"]["targets"] = [
                {"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0},
            ]
            (Path(in_td) / "s1.json").write_text(
                json.dumps(base, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("## 目錄", content)


if __name__ == "__main__":
    unittest.main()
