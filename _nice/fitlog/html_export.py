"""fitlog markdown → HTML 純函式 (no LLM, no I/O — caller 自己存檔).

PT 想把報告分享給學員 (LINE 內嵌瀏覽器、email、列印),markdown 不夠,
需要 HTML。本模組支援 fitlog 用到的 markdown subset:

- # / ## / ### headings
- bullet (- ) / numbered (1. ) lists
- | tables | with |---|---|---| separator rows
- **bold** + `code` inline
- --- horizontal rules
- paragraphs (空行分段, line break = <br>)

純 Python 實作,無第三方 markdown 依賴。HTML special chars 自動 escape。
"""
from __future__ import annotations

import html as _html_lib
import re


def _convert_inline(text: str) -> str:
    """Escape HTML + 處理 **bold** 和 `code`。"""
    text = _html_lib.escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_NUMBERED_LIST_RE = re.compile(r"^\d+\.\s+(.+)$")
_TABLE_SEPARATOR_RE = re.compile(r"^\|[\s\-:|]+\|?\s*$")


def markdown_to_html(md: str) -> str:
    """Minimal markdown → HTML for fitlog reports."""
    if not md.strip():
        return ""
    lines = md.split("\n")
    out: list[str] = []
    in_list = False
    in_table = False
    p_buf: list[str] = []

    def flush_p() -> None:
        if p_buf:
            out.append("<p>" + "<br>".join(p_buf) + "</p>")
            p_buf.clear()

    def flush_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def flush_table() -> None:
        nonlocal in_table
        if in_table:
            out.append("</table>")
            in_table = False

    for raw in lines:
        line = raw.rstrip()
        if not line:
            flush_p(); flush_list(); flush_table()
            continue

        m = _HEADING_RE.match(line)
        if m:
            flush_p(); flush_list(); flush_table()
            level = len(m.group(1))
            out.append(f"<h{level}>{_convert_inline(m.group(2))}</h{level}>")
            continue

        if line == "---":
            flush_p(); flush_list(); flush_table()
            out.append("<hr>")
            continue

        if line.startswith("- "):
            flush_p(); flush_table()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_convert_inline(line[2:])}</li>")
            continue

        m = _NUMBERED_LIST_RE.match(line)
        if m:
            flush_p(); flush_table()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_convert_inline(m.group(1))}</li>")
            continue

        if line.startswith("|"):
            flush_p(); flush_list()
            if _TABLE_SEPARATOR_RE.match(line):
                continue
            if not in_table:
                out.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            row = "".join(f"<td>{_convert_inline(c)}</td>" for c in cells)
            out.append(f"<tr>{row}</tr>")
            continue

        flush_list(); flush_table()
        p_buf.append(_convert_inline(line))

    flush_p(); flush_list(); flush_table()
    return "\n".join(out)


def render_html_page(title: str, body_html: str) -> str:
    """Wrap body_html in HTML5 page with monospace-friendly CSS。"""
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html_lib.escape(title)}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Microsoft JhengHei",
       "PingFang TC", sans-serif;
       max-width: 720px; margin: 2em auto; padding: 0 1em;
       line-height: 1.6; color: #222; background: #fafafa; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: .3em; }}
h2 {{ color: #444; margin-top: 1.6em; border-left: 4px solid #888;
      padding-left: .5em; }}
h3 {{ color: #555; }}
table {{ border-collapse: collapse; width: 100%; margin: .8em 0; }}
td {{ border: 1px solid #ccc; padding: .4em .6em; }}
tr:first-child td {{ background: #f0f0f0; font-weight: bold; }}
strong {{ color: #c00; }}
hr {{ border: none; border-top: 1px solid #ddd; margin: 2em 0; }}
code {{ background: #eee; padding: .1em .3em; border-radius: 3px;
        font-family: "SF Mono", Menlo, monospace; }}
ul {{ padding-left: 1.4em; }}
li {{ margin: .2em 0; }}
</style>
</head>
<body>
{body_html}
</body>
</html>
"""
