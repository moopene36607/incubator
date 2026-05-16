"""fitlog 語音/口述轉文字 → SetRecord parser (純規則 no LLM, no I/O).

PT 上完課想立刻把訓練紀錄打成文字 (或未來接 Whisper 轉錄結果),手打
完整 JSON 太累。本模組接受結構化文字,每行一個 set,語法:

  <exercise_name> <sets>x<reps> <weight|BW> [RPE<n>] [#<note>]

範例:
  槓鈴背蹲舉 4x10 70kg RPE8 #深度突破
  Bench Press 4x8 50kg RPE8
  Pull-up 3x6 BW RPE9
  Plank 3x60sec BW

設計準則:
- 純規則 parser,不靠 LLM (符合「demo 不依賴 ANTHROPIC_API_KEY」原則)
- 未識別的 exercise 直接跳過,不破壞整體 (PT 隨手寫的閒話可以混在裡面)
- exercise name 由 db.chinese / db.english 反向 lookup,longest match 優先
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from exercise_db import EXERCISES

if TYPE_CHECKING:
    from fitlog import SetRecord


def _build_name_index() -> dict[str, str]:
    """中文 / 英文 / 代碼 (lower) → exercise_code。"""
    idx: dict[str, str] = {}
    for ex in EXERCISES:
        idx[ex.chinese] = ex.code
        idx[ex.english.lower()] = ex.code
        idx[ex.code.lower()] = ex.code  # 直接用代碼也能解析
    return idx


_NAME_INDEX = _build_name_index()
_NAMES_LONGEST_FIRST = sorted(_NAME_INDEX.keys(), key=len, reverse=True)

# sets x reps,reps 可帶單位 (sec/min/m/km) 或純整數
_SETS_REPS_RE = re.compile(
    r"(\d+)\s*[xX×]\s*(\d+(?:\s*(?:sec|min|m|km))?)",
    re.IGNORECASE,
)
# 中文量詞記法:N組M下 / N組M次 / N組M秒 / N組M分 (Whisper 轉錄中文口述用)
_SETS_REPS_ZH_RE = re.compile(
    r"(\d+)\s*組\s*(\d+)\s*(下|次|秒|分)?",
)
# 中文時間單位 → reps_or_duration 慣用後綴
_ZH_UNIT_MAP = {"秒": "sec", "分": "min"}
_RPE_RE = re.compile(r"RPE\s*(\d+)", re.IGNORECASE)
_WEIGHT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:kg|公斤)?", re.IGNORECASE)


# 中文數字 → int (支援 0-999,涵蓋 sets/reps/weight/RPE 所有實際範圍)
_ZH_DIGITS = {
    "零": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
_ZH_NUM_RUN = re.compile(r"[零一二三四五六七八九十百兩]+")


def _zh_num_to_int(s: str) -> int:
    """純中文數字字串 → int。十一→11、三十五→35、一百二十→120。"""
    total = 0
    section = 0
    for ch in s:
        if ch in _ZH_DIGITS:
            section = _ZH_DIGITS[ch]
        elif ch == "十":
            section = (section or 1) * 10
            total += section
            section = 0
        elif ch == "百":
            section = (section or 1) * 100
            total += section
            section = 0
    return total + section


def _zh_to_arabic(text: str) -> str:
    """把 text 中的中文數字串就地換成阿拉伯數字。
    注意:呼叫端必須先抽掉 exercise name (例「三頭下壓」含「三」)。"""
    return _ZH_NUM_RUN.sub(lambda m: str(_zh_num_to_int(m.group())), text)


def _find_exercise(line: str) -> tuple[str | None, str]:
    """找出 line 中最長匹配的 exercise name,回傳 (code, 移除 name 後的剩餘)。"""
    line_lower = line.lower()
    for name in _NAMES_LONGEST_FIRST:
        idx = line_lower.find(name.lower())
        if idx >= 0:
            code = _NAME_INDEX[name]
            rest = (line[:idx] + line[idx + len(name):]).strip()
            return code, rest
    return None, line


def parse_voice_transcript(text: str) -> list["SetRecord"]:
    """把多行口述文字解析成 SetRecord list;未識別 exercise 行跳過。"""
    from fitlog import SetRecord
    results: list[SetRecord] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        ex_code, rest = _find_exercise(line)
        if ex_code is None:
            continue

        # 抽 note (# 之後)
        note = ""
        if "#" in rest:
            rest, note = rest.split("#", 1)
            rest, note = rest.strip(), note.strip()

        # 中文數字 → 阿拉伯 (exercise name 已抽掉,不會誤傷「三頭下壓」之類)
        rest = _zh_to_arabic(rest)

        # 抽 RPE
        rpe: int | None = None
        rpe_m = _RPE_RE.search(rest)
        if rpe_m:
            rpe = int(rpe_m.group(1))
            rest = (rest[:rpe_m.start()] + rest[rpe_m.end():]).strip()

        # 抽 sets x reps:先試書寫式 NxM,再試中文 N組M下
        sr_m = _SETS_REPS_RE.search(rest)
        if sr_m:
            sets_count = int(sr_m.group(1))
            reps_raw = re.sub(r"\s+", "", sr_m.group(2))  # "60 sec" → "60sec"
            rest_after_sr = (rest[:sr_m.start()] + rest[sr_m.end():]).strip()
        else:
            zh_m = _SETS_REPS_ZH_RE.search(rest)
            if not zh_m:
                continue
            sets_count = int(zh_m.group(1))
            reps_num = zh_m.group(2)
            zh_unit = zh_m.group(3)  # 下/次/秒/分 or None
            reps_raw = reps_num + _ZH_UNIT_MAP.get(zh_unit or "", "")
            rest_after_sr = (rest[:zh_m.start()] + rest[zh_m.end():]).strip()

        # 抽 weight: BW / 數字
        weight_kg: float | None = None
        if rest_after_sr:
            up = rest_after_sr.upper()
            if up.startswith("BW") or up == "BW":
                weight_kg = None
            else:
                wm = _WEIGHT_RE.search(rest_after_sr)
                if wm:
                    weight_kg = float(wm.group(1))

        results.append(SetRecord(
            exercise_code=ex_code,
            sets=sets_count,
            reps_or_duration=reps_raw,
            weight_kg=weight_kg,
            rpe=rpe,
            note=note,
        ))
    return results


def diagnose_voice_lines(text: str) -> list[tuple[int, str]]:
    """找出「看起來是 set 但 exercise 沒被認出」的行 — 強烈疑似動作名打錯
    或不在 db。回傳 [(行號 1-based, 行內容)]。
    判定:該行有組數×次數訊號 (NxM 或 N組M) 但 _find_exercise 找不到動作。
    純閒話 (無組數訊號) 不會被列入。"""
    problems: list[tuple[int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        has_sets_reps = bool(
            _SETS_REPS_RE.search(line)
            or _SETS_REPS_ZH_RE.search(_zh_to_arabic(line))
        )
        if not has_sets_reps:
            continue
        ex_code, _ = _find_exercise(line)
        if ex_code is None:
            problems.append((lineno, line))
    return problems


def make_blank_session_template() -> dict[str, Any]:
    """產出一份通過 schema 的「新 session 樣板」,含 placeholder 提示。
    PT 用 `fitlog.py --template > new.json` 後手動填學員/動作資料。"""
    from datetime import date as _date
    return {
        "student": {
            "name": "(請填學員姓名)",
            "age": None,
            "goal": "(請填訓練目標,例如:減脂 + 增肌)",
        },
        "coach": {
            "name": "(請填教練姓名)",
            "studio_name": "(請填工作室名稱)",
            "contact": "",
        },
        "session": {
            "session_no": 1,
            "date": _date.today().isoformat(),
            "duration_min": 60,
            "theme": "(請填今日訓練主題)",
            "sets": [
                {
                    "exercise_code": "BENCH_PRESS",
                    "sets": 4,
                    "reps_or_duration": "8",
                    "weight_kg": 50.0,
                    "rpe": 8,
                    "note": "範例 set — 請替換成今日實際訓練紀錄",
                },
            ],
        },
        "coach_observations": [],
        "student_subjective": [],
        "next_session": {},
        "recovery_diet": {},
    }


def build_session_skeleton(sets: list["SetRecord"]) -> dict[str, Any]:
    """把解析出來的 sets 包成一份 JSON skeleton (其餘欄位 placeholder,
    讓 PT 拿去填 student/coach metadata 後跑正常 CLI)。"""
    from datetime import date
    return {
        "student": {"name": "", "age": None, "goal": ""},
        "coach": {"name": "", "studio_name": "", "contact": ""},
        "session": {
            "session_no": 1,
            "date": date.today().isoformat(),
            "duration_min": 60,
            "theme": "(請填寫主題)",
            "sets": [
                {
                    "exercise_code": s.exercise_code,
                    "sets": s.sets,
                    "reps_or_duration": s.reps_or_duration,
                    "weight_kg": s.weight_kg,
                    "rpe": s.rpe,
                    "note": s.note,
                }
                for s in sets
            ],
        },
        "coach_observations": [],
        "student_subjective": [],
        "next_session": {},
        "recovery_diet": {},
    }
