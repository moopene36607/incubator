"""紅色測試 — HTML 報告目錄可點擊.

markdown 報告的「## 目錄」section 列出各 section 名稱 (純文字 bullet)。
轉成 HTML 後,這些 bullet 若能變成跳轉連結 (錨點),在 LINE 內嵌瀏覽器
讀長報告時可一鍵跳到該段。

做法:markdown_to_html 給每個 <h2> 加 id;<li> 文字若完全等於某個 h2
標題文字,就包成 <a href="#id">。.md 檔本身不變 (純文字 bullet)。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from html_export import markdown_to_html  # noqa: E402


class TestHtmlHeadingIds(unittest.TestCase):
    def test_h2_gets_id(self) -> None:
        html = markdown_to_html("## 各堂訓練量\n\n內容")
        # h2 應有 id 屬性
        self.assertRegex(html, r"<h2 id=\"[^\"]+\">各堂訓練量</h2>")

    def test_h1_no_id_needed(self) -> None:
        # h1 (報告標題) 不必加 id,不強制
        html = markdown_to_html("# 標題\n\n內容")
        self.assertIn("<h1>", html)


class TestHtmlTocLinks(unittest.TestCase):
    def test_toc_bullet_matching_heading_becomes_link(self) -> None:
        md = (
            "# 報告\n\n"
            "## 目錄\n\n"
            "- 各堂訓練量\n\n"
            "## 各堂訓練量\n\n"
            "內容"
        )
        html = markdown_to_html(md)
        # 目錄裡的「各堂訓練量」bullet 應是連結
        self.assertIn("<a href=\"#", html)
        # 連結文字是 section 名
        self.assertRegex(html, r"<a href=\"#[^\"]+\">各堂訓練量</a>")

    def test_toc_link_target_matches_heading_id(self) -> None:
        md = (
            "## 目錄\n\n- 動作排行\n\n## 動作排行\n\n內容"
        )
        html = markdown_to_html(md)
        import re
        hid = re.search(r"<h2 id=\"([^\"]+)\">動作排行</h2>", html)
        self.assertIsNotNone(hid)
        self.assertIn(f"href=\"#{hid.group(1)}\"", html)

    def test_non_matching_bullet_stays_plain(self) -> None:
        md = "## 目錄\n\n- 普通項目沒對應標題\n\n## 別的段\n\n內容"
        html = markdown_to_html(md)
        # 「普通項目...」沒有對應 h2 → 不該被包成連結
        self.assertIn("<li>普通項目沒對應標題</li>", html)

    def test_no_toc_no_links(self) -> None:
        # 沒目錄的一般 bullet 不受影響
        md = "## 段落\n\n- 一般 bullet\n\n內容"
        html = markdown_to_html(md)
        self.assertIn("<li>一般 bullet</li>", html)


class TestHtmlBackwardCompat(unittest.TestCase):
    def test_existing_structure_unchanged(self) -> None:
        md = "# T\n\n## A\n\n- x\n- y\n\n| a | b |\n|---|---|\n| 1 | 2 |"
        html = markdown_to_html(md)
        self.assertIn("<table>", html)
        self.assertIn("<ul>", html)
        self.assertIn("<h1>T</h1>", html)


if __name__ == "__main__":
    unittest.main()
