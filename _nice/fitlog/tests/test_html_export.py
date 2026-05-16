"""紅色測試 — markdown → HTML 純函式 + CLI --html 旗標.

PT 想把報告分享給學員 (LINE 內嵌瀏覽器、email、列印),markdown 不夠,
需要 HTML。本模組支援 fitlog 用到的 markdown subset:
  # / ## / ### headings
  - bullet lists
  | tables | with |---|---|---| separator rows
  **bold**
  --- horizontal rules
  paragraphs

純 Python 實作,無第三方 markdown library 依賴。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from html_export import markdown_to_html, render_html_page  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestMarkdownToHtml(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(markdown_to_html(""), "")

    def test_h1_h2_h3(self) -> None:
        md = "# Top\n\n## Mid\n\n### Sub\n"
        result = markdown_to_html(md)
        self.assertIn("<h1>Top</h1>", result)
        # h2 帶錨點 id (供目錄跳轉);用 regex 容忍 id 值
        self.assertRegex(result, r'<h2 id="[^"]+">Mid</h2>')
        self.assertIn("<h3>Sub</h3>", result)

    def test_bullet_list(self) -> None:
        md = "- item A\n- item B\n"
        result = markdown_to_html(md)
        self.assertIn("<ul>", result)
        self.assertIn("<li>item A</li>", result)
        self.assertIn("<li>item B</li>", result)
        self.assertIn("</ul>", result)

    def test_numbered_list(self) -> None:
        md = "1. First\n2. Second\n"
        result = markdown_to_html(md)
        self.assertIn("<li>First</li>", result)
        self.assertIn("<li>Second</li>", result)

    def test_table(self) -> None:
        md = "| Date | Tonnage |\n|------|---------|\n| 5/10 | 6200 kg |\n"
        result = markdown_to_html(md)
        self.assertIn("<table>", result)
        self.assertIn("<td>Date</td>", result)
        self.assertIn("<td>5/10</td>", result)
        self.assertIn("<td>6200 kg</td>", result)
        # separator row 不該變 td
        self.assertNotIn("---", result)

    def test_bold_inline(self) -> None:
        md = "Hello **world** today."
        result = markdown_to_html(md)
        self.assertIn("<strong>world</strong>", result)

    def test_horizontal_rule(self) -> None:
        md = "Above\n\n---\n\nBelow\n"
        result = markdown_to_html(md)
        self.assertIn("<hr>", result)

    def test_paragraph(self) -> None:
        md = "Just plain text here."
        result = markdown_to_html(md)
        self.assertIn("<p>Just plain text here.</p>", result)

    def test_html_special_chars_escaped(self) -> None:
        md = "Use <script> & co."
        result = markdown_to_html(md)
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)
        self.assertIn("&amp;", result)

    def test_mixed_real_fitlog_output(self) -> None:
        md = (
            "# 林阿明 課後訓練報告\n\n"
            "**訓練總噸位**: 6,200 kg\n\n"
            "## 訓練量化紀錄\n\n"
            "| # | 動作 | 重量 |\n"
            "|---|------|------|\n"
            "| 1 | Squat | 70 kg |\n\n"
            "---\n"
        )
        result = markdown_to_html(md)
        self.assertIn("<h1>", result)
        self.assertIn("<strong>", result)
        self.assertIn("<table>", result)
        self.assertIn("<hr>", result)


class TestRenderHtmlPage(unittest.TestCase):
    def test_includes_doctype(self) -> None:
        result = render_html_page("Title", "<p>body</p>")
        self.assertIn("<!DOCTYPE html>", result)

    def test_includes_title(self) -> None:
        result = render_html_page("林阿明 第 12 堂", "<p>body</p>")
        self.assertIn("<title>林阿明 第 12 堂</title>", result)

    def test_title_escaped(self) -> None:
        result = render_html_page("Title <script>", "<p>body</p>")
        self.assertNotIn("<title>Title <script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_body_embedded(self) -> None:
        result = render_html_page("X", "<p>my body</p>")
        self.assertIn("<p>my body</p>", result)

    def test_includes_css_for_readability(self) -> None:
        # 該有 style 內含基本 CSS
        result = render_html_page("X", "<p>body</p>")
        self.assertIn("<style>", result)


class TestCliHtmlFlag(unittest.TestCase):
    def test_html_flag_writes_file(self) -> None:
        with NamedTemporaryFile(suffix=".html", mode="r", delete=False) as f:
            html_path = f.name
        try:
            r = subprocess.run(
                [sys.executable, "fitlog.py",
                 "samples/sample_input.json", "--no-ai",
                 "--html", html_path],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = Path(html_path).read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("林阿明", content)
            self.assertIn("<table>", content)
        finally:
            Path(html_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
