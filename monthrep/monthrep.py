"""monthrep — 台灣才藝班 / 補習班老師月報自動產生器

Usage:
    python monthrep.py samples/sample_input.json
    python monthrep.py samples/sample_input.json --out report.md
    python monthrep.py samples/sample_input.json --no-ai     # 骨架版

每月月底,老師輸入學生本月的:出席、學習重點、進步、需加強之處、家長提醒、
下月計畫,30 秒產出一份 LINE 友好版 + 正式 PDF 雙版本月報草稿。

設計重點:
- 純函式組裝月報標頭 + 結構化欄位
- AI 只負責「文字段落」(本月學習概況、給家長的話、下月學習計畫)
- 不同年齡層自動切換語氣調性 (學齡前 / 國小 / 國中 / 高中)
- 不同科目使用對應 grounding (鋼琴 / 美術 / 英文 / 數學 / 舞蹈 / 圍棋…)

ANTHROPIC_API_KEY 在 AI 模式必要 (--no-ai 跳過,輸出骨架)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from report_template import (
    AGE_BANDS,
    SUBJECT_TEMPLATES,
    AgeBandTone,
    SubjectTemplate,
    lookup_age_band,
    lookup_subject,
)


REPORT_SYSTEM = """你是台灣才藝班 / 補習班老師的助理,協助老師月底為每位學生寫月報給家長看。
你的目標是把老師原始的勾選表單與簡短觀察文字轉成一份溫暖、專業、家長願意讀完的繁中月報。

## 寫作原則

- 繁體中文,語氣溫暖但專業,不過度甜膩、不過度冷淡
- 第三人稱敘述學生 (例:「○○ 本月在…」), 第二人稱面對家長 (例:「建議家長可…」)
- **不要**編造老師沒提供的事實 — 沒提過的進步 / 比賽成績 / 出席日數絕對不能補
- **不要**用「您的孩子超棒!」這種空泛家長式 marketing 語
- 具體舉例優先:寫「本月完成《拜爾》第 14-16 課」,不要寫「本月有許多進步」
- 弱點要說但要 constructive:用「下月可加強…」「建議家長協助…」,不用「孩子做不好」

## 結構

請輸出 4 段,markdown 格式,**只回這 4 段**,不要前後解說、不要重複學生標頭資料:

### 一、本月學習概況
2-4 句,寫出席、整體狀態、本月主要學習主題或曲目 / 章節。

### 二、本月觀察到的進步
3-5 個 bullet point,每點具體舉例。

### 三、需要加強的地方
2-4 個 bullet point,每點寫「現況 + 下月會怎麼處理 + 家長可以怎麼協助」。

### 四、給家長的話 + 下月學習計畫
1 段話作結,先回應家長最在意的點 (依年齡帶口吻),再給出下月 1-2 個明確學習目標。

## 嚴格規則

- 不要編造任何老師沒提供的數字、比賽結果、出席數
- 不要寫具體下次上課時間 / 收費 / 行政事務 (留給老師的另外通知)
- 不要在月報內結尾署名 (老師資料由模板自動帶入)
"""


@dataclass
class StudentInfo:
    name: str
    age: int
    grade: str           # e.g. "國小四年級"
    age_band_code: str   # PRESCHOOL / ELEMENTARY / JUNIOR_HIGH / SENIOR_HIGH


@dataclass
class TeacherInfo:
    name: str
    studio_name: str
    contact: str = ""


@dataclass
class MonthData:
    year: int
    month: int
    attendance_actual: int
    attendance_planned: int
    main_topics: list[str]              # ["拜爾 14-16 課", "小奏鳴曲 Op.39 No.7"]
    progress_observations: list[str]    # 老師觀察到的進步點
    weak_points: list[str]              # 老師觀察到需加強之處
    homework_done_pct: int | None = None
    parent_concerns_responding_to: list[str] | None = None  # 老師想特別回應家長的疑慮
    next_month_plan: list[str] | None = None
    extra_note: str = ""                # 老師自由補充


def parse_payload(payload: dict[str, Any]) -> tuple[StudentInfo, TeacherInfo, MonthData, str]:
    s = payload["student"]
    t = payload["teacher"]
    m = payload["month_data"]
    return (
        StudentInfo(
            name=s["name"],
            age=int(s["age"]),
            grade=s.get("grade", ""),
            age_band_code=s.get("age_band_code", "ELEMENTARY"),
        ),
        TeacherInfo(name=t["name"], studio_name=t["studio_name"], contact=t.get("contact", "")),
        MonthData(
            year=int(m["year"]),
            month=int(m["month"]),
            attendance_actual=int(m["attendance_actual"]),
            attendance_planned=int(m["attendance_planned"]),
            main_topics=list(m.get("main_topics", [])),
            progress_observations=list(m.get("progress_observations", [])),
            weak_points=list(m.get("weak_points", [])),
            homework_done_pct=m.get("homework_done_pct"),
            parent_concerns_responding_to=list(m.get("parent_concerns_responding_to", []) or []),
            next_month_plan=list(m.get("next_month_plan", []) or []),
            extra_note=m.get("extra_note", ""),
        ),
        payload.get("subject_code", "PIANO"),
    )


def build_grounding(subject: SubjectTemplate | None, age_band: AgeBandTone | None) -> str:
    parts: list[str] = []
    if subject:
        parts.append(
            f"## 科目 grounding\n科目: {subject.chinese}\n"
            f"通常評論的學習面向: {', '.join(subject.typical_focus)}\n"
            f"家長最在意的點: {', '.join(subject.parent_concerns)}\n"
        )
    if age_band:
        parts.append(
            f"## 年齡層口吻\n年齡帶: {age_band.label}\n口吻指引: {age_band.voice_note}\n"
        )
    return "\n".join(parts)


def ai_write_report_body(student: StudentInfo, month: MonthData,
                         subject: SubjectTemplate | None, age_band: AgeBandTone | None) -> str:
    import anthropic

    grounding = build_grounding(subject, age_band)
    user_data = {
        "學生": {"姓名": student.name, "年齡": student.age, "年級": student.grade},
        "月份": f"{month.year} 年 {month.month} 月",
        "出席": f"{month.attendance_actual} / {month.attendance_planned} 次",
        "本月學習主題": month.main_topics,
        "老師觀察到的進步": month.progress_observations,
        "需要加強的地方": month.weak_points,
        "作業完成率": (f"{month.homework_done_pct}%" if month.homework_done_pct is not None else "未記錄"),
        "想特別回應家長的疑慮": month.parent_concerns_responding_to or [],
        "老師預定的下月計畫": month.next_month_plan or [],
        "老師補充": month.extra_note,
    }
    user = (
        f"{grounding}\n\n## 老師輸入的本月資料\n\n"
        f"```json\n{json.dumps(user_data, ensure_ascii=False, indent=2)}\n```\n\n"
        f"請依上述資料寫出 4 段月報內容。"
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=[{"type": "text", "text": REPORT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def render_skeleton_body(month: MonthData) -> str:
    return (
        "### 一、本月學習概況\n(請填入:出席 / 整體狀態 / 本月主要學習主題或曲目)\n\n"
        "### 二、本月觀察到的進步\n- (具體進步點 1)\n- (具體進步點 2)\n- (具體進步點 3)\n\n"
        "### 三、需要加強的地方\n- (現況 + 下月怎麼處理 + 家長可協助)\n- (同上)\n\n"
        "### 四、給家長的話 + 下月學習計畫\n(1 段話作結,先回應家長關心的點,再給下月學習目標)\n"
    )


def render_full_report(student: StudentInfo, teacher: TeacherInfo, month: MonthData,
                       subject: SubjectTemplate | None, body: str) -> str:
    out: list[str] = []
    subject_label = subject.chinese if subject else "(未指定科目)"

    out.append(f"# {month.year} 年 {month.month} 月 學習月報")
    out.append("")
    out.append(f"## {student.name} 同學  /  {subject_label}")
    out.append("")
    out.append("## 學生資訊")
    out.append("")
    out.append(f"- **姓名**: {student.name}")
    out.append(f"- **年齡 / 年級**: {student.age} 歲 / {student.grade}")
    out.append(f"- **科目**: {subject_label}")
    out.append("")
    out.append("## 出席統計")
    out.append("")
    pct = (
        round(month.attendance_actual * 100 / month.attendance_planned)
        if month.attendance_planned > 0 else 0
    )
    out.append(
        f"- 本月課程: **{month.attendance_actual} / {month.attendance_planned}** "
        f"次到課 ({pct}%)"
    )
    if month.homework_done_pct is not None:
        out.append(f"- 作業完成率: **{month.homework_done_pct}%**")
    out.append("")
    if month.main_topics:
        out.append("## 本月學習主題")
        out.append("")
        for topic in month.main_topics:
            out.append(f"- {topic}")
        out.append("")

    out.append("---")
    out.append("")
    out.append(body)
    out.append("")

    out.append("---")
    out.append("")
    out.append(f"**承辦老師**: {teacher.name}")
    out.append(f"**教室**: {teacher.studio_name}")
    if teacher.contact:
        out.append(f"**聯絡方式**: {teacher.contact}")
    out.append("")
    out.append(f"*由月報先生 (monthrep) 自動產生於 {date.today().isoformat()} — 老師確認後寄送*")
    return "\n".join(out) + "\n"


def render_line_friendly(student: StudentInfo, teacher: TeacherInfo, month: MonthData, body: str) -> str:
    """產生方便直接複製貼到 LINE 的純文字版本 (去掉 markdown 標題符號)。"""
    plain = body.replace("### ", "\n").replace("## ", "\n").replace("**", "")
    return (
        f"📚 {student.name} 同學 {month.year}/{month.month:02d} 月學習月報\n"
        f"教室:{teacher.studio_name}\n"
        f"出席:{month.attendance_actual}/{month.attendance_planned} 次\n"
        f"━━━━━━━━━━━━━━\n"
        f"{plain.strip()}\n"
        f"━━━━━━━━━━━━━━\n"
        f"老師:{teacher.name}\n"
        f"如有疑問歡迎隨時聯繫 ☺️"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="月報資料 JSON")
    parser.add_argument("--out", type=Path, help="輸出 markdown 月報路徑 (省略 stdout)")
    parser.add_argument("--out-line", type=Path, help="另存 LINE 友好純文字版路徑")
    parser.add_argument("--no-ai", action="store_true", help="不呼叫 AI,輸出骨架版")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: 找不到 {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    student, teacher, month, subject_code = parse_payload(payload)
    subject = lookup_subject(subject_code)
    age_band = lookup_age_band(student.age_band_code)

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,輸出骨架版", file=sys.stderr)

    body = (ai_write_report_body(student, month, subject, age_band)
            if use_ai else render_skeleton_body(month))
    full = render_full_report(student, teacher, month, subject, body)

    if args.out:
        args.out.write_text(full, encoding="utf-8")
        print(f"已寫入 markdown: {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(full)

    if args.out_line:
        line_text = render_line_friendly(student, teacher, month, body)
        args.out_line.write_text(line_text, encoding="utf-8")
        print(f"已寫入 LINE 版: {args.out_line}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
