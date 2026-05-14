"""fitlog 批次模式 — 純函式掃描單一目錄下的 session JSON (no I/O 副作用 over caller).

PT 一天 6-8 節 1 對 1 課,讓 CLI 一次跑整個目錄、把每份 student.json
產出對應的 student.md (寫在原檔旁) 是日常使用 UX 的關鍵省時。

設計選擇:
- flat (一層),不遞迴 — 教練最自然的工作流是「今日課表」放一個目錄
- 排序 alphabetical — 報告產出順序穩定,debug 易追
- 不存在的目錄 → [] (不 raise),caller 決定要不要警告
"""
from __future__ import annotations

from pathlib import Path


def discover_session_jsons(directory: Path) -> list[Path]:
    """掃描 directory 下所有 *.json 檔(不遞迴),依檔名排序回傳。"""
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix == ".json")
