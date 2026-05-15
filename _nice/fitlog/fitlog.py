"""fitlog — 台灣健身教練 課後訓練報告產生器

Usage:
    python fitlog.py samples/sample_input.json
    python fitlog.py samples/sample_input.json --out report.md --out-line report_line.txt
    python fitlog.py samples/sample_input.json --no-ai  # 骨架版

每堂 1 對 1 PT 課後,教練輸入學員姓名 + 動作清單 (組數/重量/RPE) + 觀察 + 學員主訴,
30 秒產出一份學員拿了會看完的繁中課後報告 (markdown + LINE 純文字版)。

設計重點:
- 純函式組裝報告標頭、訓練量化表格、LINE 純文字版
- AI 只寫「文字段落」(今日摘要、進步觀察、身體反應、下次重點、恢復建議)
- 動作 grounding 用 exercise_db 維持台灣健身圈通用詞
- 不編造學員未提到的飲食 / 數據,不下醫療診斷

ANTHROPIC_API_KEY 在 AI 模式必要 (--no-ai 跳過,輸出骨架)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from exercise_db import EXERCISES, Exercise, lookup
from aggregate import (
    aggregate_batch,
    compute_absent_students,
    compute_bw_reps_progression,
    compute_day_of_week_distribution,
    compute_duration_progression,
    compute_exercise_progression,
    compute_favorite_exercise,
    compute_goal_etas,
    compute_training_streak,
    detect_new_prs,
    compute_goal_progress,
    compute_student_1rm_progression,
    compute_student_bw_prs,
    compute_student_density_progression,
    compute_student_prs,
    compute_student_rpe_progression,
    compute_student_session_frequency,
    compute_student_trend,
    compute_weekly_tonnage,
    find_newly_achieved_goals,
    find_prev_session,
    render_absent_students,
    render_batch_one_liner,
    render_batch_summary,
    render_day_of_week_distribution,
    render_new_pr_banner,
    render_session_goal_banner,
    render_session_one_liner,
    render_student_trend,
)
from batch import discover_session_jsons
from coaching import (
    compute_cumulative_tonnage_before,
    compute_session_1rm_estimates,
    detect_deload_signal,
    detect_imbalance_warning,
    detect_milestone_crossed,
    render_1rm_estimates,
    render_deload_banner,
    render_imbalance_warning,
    render_milestone_banner,
    render_next_weight_suggestions,
    suggest_next_session_weights,
)
from metrics import compute_total_tonnage
from html_export import markdown_to_html, render_html_page
from csv_export import write_batch_csv, write_session_csv
from metrics import (
    CATEGORY_EMOJI,
    CATEGORY_ZH,
    compute_rpe_zone_distribution,
    render_category_breakdown,
    render_rpe_zone_distribution,
    render_training_density,
    render_volume_summary,
)
from progress import (
    compute_bw_reps_deltas,
    compute_duration_deltas,
    compute_pr_deltas,
    render_pr_summary,
)
from schema import validate_payload_schema
from validation import validate_session
from voice import build_session_skeleton, make_blank_session_template, parse_voice_transcript


REPORT_SYSTEM = """你是台灣健身教練 (PT) 的課後報告助理,協助教練把訓練紀錄與觀察轉成
學員當天會看完的課後報告 (傳到 LINE 用)。

## 寫作原則

- 繁體中文,第二人稱對學員 (例:「你今天 squat 表現…」),語氣是「教練朋友」,
  不是「健身房 sales」。專業但有溫度,不油膩。
- 用台灣健身圈常見詞:RPE、組數、超負荷、TUT、deload、bodyweight、訓練量、力竭。
  不要過度使用簡體中文式術語 (避免:「卧推」「桑拿」「肌肥大」)。
- **絕不編造**教練沒提供的數據 — 不亂猜學員體重、體脂、卡路里、心率
- **絕不下醫療診斷** — 學員提到不適時用「建議下次回來告知狀況」「下次會視情況調整」,
  不要寫「你可能有 XX 症」
- 量化資料優先:寫「Bench Press 從 47.5 kg 進步到 50 kg」, 不要寫「你變強了」

## 結構

請輸出 5 段,markdown 格式。**只回這 5 段**,不要前後說明、不要重複學員資料:

### 一、今日訓練摘要
2-3 句說明今日課程主題 (e.g. 全身肌力 / 上半身推 / 下半身) + 整體完成度。

### 二、本次主要進步 / 突破
2-4 個 bullet point。具體寫進步細節:
- 「Squat 深度從上次 90° 提升到本次 110° 完整深蹲」
- 「Bench Press 突破 47.5 kg 瓶頸,本次完成 4×8×50 kg, RPE 8」

### 三、身體反應與觀察
2-4 個 bullet。可包含:
- 教練看到的動作品質改善 / 退步
- 學員主述的不適 (用「下次留意」措辭,不下診斷)
- 疲勞趨勢、握力、核心控制等 qualitative 評估

### 四、下次課程重點
1-2 段。寫:
- 下次課的訓練主題與重點動作 (依教練輸入的 next session plan)
- 為什麼這樣安排 (e.g. 連續 2 次推系後該休)

### 五、本週恢復 / 飲食提醒 (只寫教練輸入的內容,不要編)
1 段。如果教練沒提供恢復或飲食目標,只寫「保持充足睡眠」這種通用建議,
**絕不發明「每日喝 3L 水」「攝取 2,000 大卡」這種具體數字**。

## 嚴格規則

- 不寫具體藥物 / 補充劑品牌 (避免廣告嫌疑與責任)
- 不寫具體飲食卡路里數字,除非教練明確提供
- 報告結尾不署名 (教練資料由純函式模板帶入)
"""


@dataclass
class SetRecord:
    exercise_code: str
    sets: int
    reps_or_duration: str   # "10" or "60 sec" or "500 m"
    weight_kg: float | None
    rpe: int | None
    note: str = ""


@dataclass
class SessionInput:
    student_name: str
    student_age: int | None
    student_goal: str
    session_no: int
    session_date: str
    duration_min: int
    coach_name: str
    studio_name: str
    contact: str
    theme: str               # 今日主題: e.g. "全身肌力 / Day A"
    sets: list[SetRecord]
    coach_observations: list[str]
    student_subjective: list[str]      # 學員主述 (如「下背稍緊」)
    next_session: dict[str, Any]       # {"date": "...", "theme": "...", "focus": [...]}
    recovery_diet: dict[str, Any] = field(default_factory=dict)
    student_targets: list[dict[str, Any]] = field(default_factory=list)
    # student.targets: list of {"exercise_code": str, "target_weight_kg": number}
    # 用於跨堂計算「達成 60 kg 目標 X%」progress bar


def parse_payload(payload: dict[str, Any]) -> SessionInput:
    s = payload["student"]
    c = payload["coach"]
    se = payload["session"]
    return SessionInput(
        student_name=s["name"],
        student_age=s.get("age"),
        student_goal=s.get("goal", ""),
        session_no=int(se["session_no"]),
        session_date=se["date"],
        duration_min=int(se["duration_min"]),
        coach_name=c["name"],
        studio_name=c["studio_name"],
        contact=c.get("contact", ""),
        theme=se["theme"],
        sets=[
            SetRecord(
                exercise_code=s["exercise_code"],
                sets=int(s["sets"]),
                reps_or_duration=str(s["reps_or_duration"]),
                weight_kg=(float(s["weight_kg"]) if s.get("weight_kg") not in (None, "") else None),
                rpe=(int(s["rpe"]) if s.get("rpe") is not None else None),
                note=s.get("note", ""),
            )
            for s in se["sets"]
        ],
        coach_observations=list(payload.get("coach_observations", [])),
        student_subjective=list(payload.get("student_subjective", [])),
        next_session=payload.get("next_session", {}),
        recovery_diet=payload.get("recovery_diet", {}),
        student_targets=list(s.get("targets", []) or []),
    )


def render_session_table(session: SessionInput) -> list[str]:
    out: list[str] = []
    out.append("| # | 動作 | 組數 × 次/秒/m | 重量 | RPE | 備註 |")
    out.append("|---|------|---------------|------|------|------|")
    for i, s in enumerate(session.sets, 1):
        ex = lookup(s.exercise_code)
        if ex:
            emoji = CATEGORY_EMOJI.get(ex.category, "")
            prefix = f"{emoji} " if emoji else ""
            name = f"{prefix}{ex.chinese} ({ex.english})"
        else:
            name = f"{s.exercise_code}(代碼未知)"
        weight = f"{s.weight_kg} kg" if s.weight_kg is not None else "BW"
        rpe_str = f"{s.rpe}" if s.rpe is not None else "—"
        out.append(f"| {i} | {name} | {s.sets} × {s.reps_or_duration} | {weight} | {rpe_str} | {s.note} |")
    return out


def render_exercise_listing() -> str:
    """印出 exercise_db 所有動作 (依分類分組),給 PT 查 exercise_code 用。
    純函式,不需 input 檔,不會碰 LLM。"""
    by_cat: dict[str, list[Exercise]] = {}
    for ex in EXERCISES:
        by_cat.setdefault(ex.category, []).append(ex)
    # CATEGORY_ZH 排序鎖死 (legs/pull/push/core/cardio/mobility)
    category_order = list(CATEGORY_ZH.keys())
    # 其餘 (未來新分類) 排在最後
    extra = [c for c in by_cat if c not in category_order]
    ordered = [c for c in category_order if c in by_cat] + sorted(extra)

    lines: list[str] = [f"# fitlog 動作清單 ({len(EXERCISES)} 個)", ""]
    # 找最長 code 對齊
    width = max(len(ex.code) for ex in EXERCISES)
    for cat in ordered:
        zh = CATEGORY_ZH.get(cat, cat)
        items = sorted(by_cat[cat], key=lambda e: e.code)
        lines.append(f"## {zh} ({len(items)})")
        lines.append("")
        for ex in items:
            lines.append(
                f"- `{ex.code.ljust(width)}`  {ex.chinese} ({ex.english})"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_skeleton_body() -> str:
    return (
        "### 一、今日訓練摘要\n(待 AI 填:今日主題 + 整體完成度)\n\n"
        "### 二、本次主要進步 / 突破\n- (待 AI 填)\n- (待 AI 填)\n\n"
        "### 三、身體反應與觀察\n- (待 AI 填)\n- (待 AI 填)\n\n"
        "### 四、下次課程重點\n(待 AI 填)\n\n"
        "### 五、本週恢復 / 飲食提醒\n(待 AI 填,不要編造學員未提到的具體數字)\n"
    )


def ai_write_body(session: SessionInput) -> str:
    import anthropic

    detail = {
        "學員": {"姓名": session.student_name, "年齡": session.student_age, "目標": session.student_goal},
        "課程": {"次數": session.session_no, "日期": session.session_date,
                "時長分鐘": session.duration_min, "主題": session.theme},
        "訓練動作": [
            {
                "動作": (lookup(s.exercise_code).chinese if lookup(s.exercise_code) else s.exercise_code),
                "代碼": s.exercise_code,
                "組數": s.sets,
                "次或秒": s.reps_or_duration,
                "重量公斤": s.weight_kg,
                "RPE": s.rpe,
                "備註": s.note,
            }
            for s in session.sets
        ],
        "教練觀察": session.coach_observations,
        "學員主述": session.student_subjective,
        "下次課程計畫": session.next_session,
        "恢復飲食目標 (學員或教練輸入)": session.recovery_diet,
    }
    user = (
        "以下為這堂課的完整資料,請寫一份學員會看完的課後報告 (5 段 markdown):\n\n"
        f"```json\n{json.dumps(detail, ensure_ascii=False, indent=2)}\n```"
    )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2200,
        system=[{"type": "text", "text": REPORT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def render_full_report(
    session: SessionInput,
    body: str,
    pr_summary: str | None = None,
    next_weight_summary: str | None = None,
    goal_banner: str | None = None,
    one_rm_summary: str | None = None,
    density_summary: str | None = None,
    deload_banner: str | None = None,
    imbalance_banner: str | None = None,
    milestone_banner: str | None = None,
    new_pr_banner: str | None = None,
) -> str:
    out: list[str] = []
    out.append(f"# {session.student_name} 課後訓練報告 (第 {session.session_no} 堂)")
    out.append("")
    out.append(f"**日期**: {session.session_date}    "
               f"**時長**: {session.duration_min} 分鐘    "
               f"**今日主題**: {session.theme}")
    out.append("")
    if new_pr_banner:
        out.append(new_pr_banner)
        out.append("")
    if goal_banner:
        out.append(goal_banner)
    if milestone_banner:
        out.append(milestone_banner)
        out.append("")
    if deload_banner:
        out.append(deload_banner)
        out.append("")
    if imbalance_banner:
        out.append(imbalance_banner)
        out.append("")
    out.append("## 學員資料")
    out.append("")
    out.append(f"- 姓名: {session.student_name}"
               + (f"   /  年齡: {session.student_age}" if session.student_age else ""))
    if session.student_goal:
        out.append(f"- 訓練目標: {session.student_goal}")
    out.append("")
    out.append("## 訓練量化紀錄")
    out.append("")
    out.extend(render_session_table(session))
    summary = render_volume_summary(session.sets)
    breakdown = render_category_breakdown(session.sets)
    zone_summary = render_rpe_zone_distribution(
        compute_rpe_zone_distribution(session.sets)
    )
    if (summary or breakdown or density_summary or zone_summary or pr_summary
            or next_weight_summary or one_rm_summary):
        out.append("")
    if summary:
        out.append(summary)
    if breakdown:
        out.append(breakdown)
    if density_summary:
        out.append(density_summary)
    if zone_summary:
        out.append(zone_summary)
    if pr_summary:
        out.append(pr_summary)
    if one_rm_summary:
        out.append(one_rm_summary)
    if next_weight_summary:
        out.append(next_weight_summary)
    out.append("")
    out.append("---")
    out.append("")
    out.append(body)
    out.append("")
    out.append("---")
    out.append("")
    out.append(f"**教練**: {session.coach_name}  /  **工作室**: {session.studio_name}")
    if session.contact:
        out.append(f"**聯絡**: {session.contact}")
    out.append("")
    out.append(f"*由 fitlog 自動產生於 {date.today().isoformat()} — 教練確認後傳給學員*")
    return "\n".join(out) + "\n"


def render_line_friendly(
    session: SessionInput,
    body: str,
    pr_summary: str | None = None,
    next_weight_summary: str | None = None,
    one_rm_summary: str | None = None,
    density_summary: str | None = None,
) -> str:
    """LINE 純文字版,去 markdown 符號,加 emoji 分段。"""
    plain = body.replace("### ", "\n").replace("## ", "\n").replace("**", "")
    quick_table_rows = []
    for i, s in enumerate(session.sets, 1):
        ex = lookup(s.exercise_code)
        name = ex.chinese if ex else s.exercise_code
        weight = f"{s.weight_kg}kg" if s.weight_kg is not None else "BW"
        rpe = f" RPE{s.rpe}" if s.rpe is not None else ""
        quick_table_rows.append(f"  {i}. {name} {s.sets}×{s.reps_or_duration} @{weight}{rpe}")
    summary = render_volume_summary(session.sets)
    breakdown = render_category_breakdown(session.sets)
    summary_parts: list[str] = []
    if summary:
        summary_parts.append(f"🏋️ 總噸位:{summary.split(': ', 1)[1]}")
    if breakdown:
        summary_parts.append(f"📦 分解:{breakdown.split(': ', 1)[1]}")
    if density_summary:
        summary_parts.append(f"⚡ 密度:{density_summary.split(': ', 1)[1]}")
    if pr_summary:
        summary_parts.append(f"🏆 進步:{pr_summary.split(': ', 1)[1]}")
    if one_rm_summary:
        summary_parts.append(f"💪 1RM 估:{one_rm_summary.split(': ', 1)[1]}")
    if next_weight_summary:
        summary_parts.append(f"➡️ 下次建議:{next_weight_summary.split(': ', 1)[1]}")
    summary_line = "\n" + "\n".join(summary_parts) + "\n" if summary_parts else "\n"
    return (
        f"💪 {session.student_name} 第 {session.session_no} 堂課後報告\n"
        f"📅 {session.session_date}  ⏱ {session.duration_min} min\n"
        f"📌 主題:{session.theme}\n"
        f"━━━━━━━━━━━━━━\n"
        "📊 訓練紀錄:\n"
        + "\n".join(quick_table_rows)
        + summary_line
        + "━━━━━━━━━━━━━━\n"
        + plain.strip()
        + f"\n━━━━━━━━━━━━━━\n"
        f"教練 {session.coach_name} | {session.studio_name}\n"
        f"有任何不適請隨時告知 ☺️"
    )


def _run_batch(args: argparse.Namespace) -> int:
    """批次模式:掃 args.batch 目錄下的 *.json,各產一份 <stem>.md。
    --out-dir 指定時寫到該目錄;否則寫在原檔旁 (向後相容)。"""
    sessions = discover_session_jsons(args.batch)
    if not sessions:
        print(f"warning: 在 {args.batch} 找不到任何 session JSON", file=sys.stderr)
        return 0
    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,批次輸出骨架版", file=sys.stderr)
    out_dir: Path | None = args.out_dir
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    # Pass 1: parse 全部,只收集 (path, session) 對 (還不渲染)
    pairs: list[tuple[Path, SessionInput]] = []
    for path in sessions:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"warning: 跳過 {path.name}: JSON 解析錯誤 {e}", file=sys.stderr)
            continue
        schema_errors = validate_payload_schema(payload)
        if schema_errors:
            for e in schema_errors:
                print(f"warning [{path.name}]: schema {e}", file=sys.stderr)
            continue
        try:
            session = parse_payload(payload)
        except (KeyError, ValueError) as e:
            print(f"warning: 跳過 {path.name}: {e}", file=sys.stderr)
            continue
        for w in validate_session(session, today_iso=date.today().isoformat()):
            print(f"warning [{path.name}]: {w}", file=sys.stderr)
        pairs.append((path, session))

    parsed_sessions: list[SessionInput] = [s for _, s in pairs]

    # --student NAME 過濾 (放在 parse 完之後,讓 schema/validation 警告仍會印)
    if args.student:
        target = args.student.strip()
        before = len(parsed_sessions)
        pairs = [(p, s) for p, s in pairs if s.student_name == target]
        parsed_sessions = [s for _, s in pairs]
        if not parsed_sessions:
            print(
                f"warning: --student {target} 沒匹配到任何 session "
                f"({before} 堂掃過),不產出任何檔",
                file=sys.stderr,
            )
            return 0
        else:
            print(
                f"info: --student {target} → 保留 {len(parsed_sessions)} / "
                f"{before} 堂",
                file=sys.stderr,
            )

    # Pass 2: 為每堂找同學員的 prev,渲染時帶 pr_summary + next_weight_summary
    # --summary-only 時跳過個別 session 渲染與寫檔 (Pass 1 仍跑供彙總用)
    if args.summary_only:
        print("info: --summary-only,跳過個別 session .md", file=sys.stderr)
    for path, session in (pairs if not args.summary_only else []):
        prev = find_prev_session(session, parsed_sessions)
        pr_summary: str | None = None
        if prev is not None:
            pr_summary = render_pr_summary(
                compute_pr_deltas(prev.sets, session.sets),
                compute_bw_reps_deltas(prev.sets, session.sets),
                compute_duration_deltas(prev.sets, session.sets),
            )
        next_weight_summary = render_next_weight_suggestions(
            suggest_next_session_weights(session.sets)
        )
        one_rm_summary = render_1rm_estimates(
            compute_session_1rm_estimates(session.sets)
        )
        density_summary = render_training_density(session)
        goal_banner = render_session_goal_banner(
            find_newly_achieved_goals(session, parsed_sessions, session.student_targets)
        )
        deload_banner = render_deload_banner(
            detect_deload_signal(parsed_sessions, session.student_name, session)
        )
        imbalance_banner = render_imbalance_warning(
            detect_imbalance_warning(parsed_sessions, session.student_name, session)
        )
        prev_total = compute_cumulative_tonnage_before(
            parsed_sessions, session.student_name, session,
        )
        current_total = prev_total + compute_total_tonnage(session.sets)
        milestone_banner = render_milestone_banner(
            detect_milestone_crossed(prev_total, current_total)
        )
        new_pr_banner = render_new_pr_banner(
            detect_new_prs(parsed_sessions, session.student_name, session)
        )
        body = ai_write_body(session) if use_ai else render_skeleton_body()
        full = render_full_report(session, body, pr_summary, next_weight_summary,
                                  goal_banner=goal_banner,
                                  one_rm_summary=one_rm_summary,
                                  density_summary=density_summary,
                                  deload_banner=deload_banner,
                                  imbalance_banner=imbalance_banner,
                                  milestone_banner=milestone_banner,
                                  new_pr_banner=new_pr_banner)
        out_path = (out_dir / f"{path.stem}.md") if out_dir is not None else path.with_suffix(".md")
        out_path.write_text(full, encoding="utf-8")
        print(f"已寫入 {out_path}", file=sys.stderr)
        # PR count = 三類 deltas 加總 (粗略估計;只算非空)
        pr_count = 0
        if prev is not None:
            pr_count = (
                len(compute_pr_deltas(prev.sets, session.sets))
                + len(compute_bw_reps_deltas(prev.sets, session.sets))
                + len(compute_duration_deltas(prev.sets, session.sets))
            )
        one_liner = render_session_one_liner(session, pr_count=pr_count)
        one_liner_path = out_path.with_suffix(".one_liner.txt")
        one_liner_path.write_text(one_liner + "\n", encoding="utf-8")
        if args.batch_html:
            html_path = out_path.with_suffix(".html")
            html_title = f"{session.student_name} 第 {session.session_no} 堂"
            html_path.write_text(
                render_html_page(html_title, markdown_to_html(full)),
                encoding="utf-8",
            )
            print(f"已寫入 {html_path}", file=sys.stderr)
    if parsed_sessions:
        summary_dir = out_dir if out_dir is not None else args.batch
        summary_path = summary_dir / "_batch_summary.md"
        batch_summary_obj = aggregate_batch(parsed_sessions)
        summary_md = render_batch_summary(batch_summary_obj)
        # 用批次中最近一堂的日期當 "as_of",讓 demo/test 可預測
        latest_date = max(
            (s.session_date for s in parsed_sessions),
            default=None,
        )
        if latest_date:
            absent_section = render_absent_students(
                compute_absent_students(parsed_sessions, latest_date)
            )
            if absent_section:
                # 插在末尾 footer (---) 之前
                summary_md = summary_md.rstrip("\n") + "\n\n" + absent_section
        dow_section = render_day_of_week_distribution(
            compute_day_of_week_distribution(parsed_sessions)
        )
        if dow_section:
            summary_md = summary_md.rstrip("\n") + "\n\n" + dow_section
        summary_path.write_text(summary_md, encoding="utf-8")
        print(f"已寫入彙總: {summary_path}", file=sys.stderr)
        if args.batch_csv:
            batch_csv_path = summary_dir / "_batch.csv"
            write_batch_csv(parsed_sessions, batch_csv_path)
            print(f"已寫入批次 CSV: {batch_csv_path}", file=sys.stderr)
        one_liner = render_batch_one_liner(batch_summary_obj)
        if one_liner:
            one_liner_path = summary_dir / "_one_liner.txt"
            one_liner_path.write_text(one_liner + "\n", encoding="utf-8")
            print(f"已寫入單行摘要: {one_liner_path}", file=sys.stderr)
        if args.batch_html:
            summary_html_path = summary_path.with_suffix(".html")
            summary_html_path.write_text(
                render_html_page("批次彙總報告", markdown_to_html(summary_md)),
                encoding="utf-8",
            )
            print(f"已寫入彙總 HTML: {summary_html_path}", file=sys.stderr)
        for name in sorted({s.student_name for s in parsed_sessions}):
            trend = compute_student_trend(parsed_sessions, name)
            prs = compute_student_prs(parsed_sessions, name)
            bw_prs = compute_student_bw_prs(parsed_sessions, name)
            progressions = compute_exercise_progression(parsed_sessions, name)
            one_rm_progressions = compute_student_1rm_progression(parsed_sessions, name)
            density_progression = compute_student_density_progression(parsed_sessions, name)
            frequency = compute_student_session_frequency(parsed_sessions, name)
            weekly_tonnage = compute_weekly_tonnage(parsed_sessions, name)
            rpe_progression = compute_student_rpe_progression(parsed_sessions, name)
            bw_reps_progressions = compute_bw_reps_progression(parsed_sessions, name)
            duration_progressions = compute_duration_progression(parsed_sessions, name)
            student_dates = [
                s.session_date for s in parsed_sessions if s.student_name == name
            ]
            latest_date = max(student_dates) if student_dates else None
            training_streak = (
                compute_training_streak(parsed_sessions, name, latest_date)
                if latest_date else 0
            )
            # 取該學員最近一堂的 targets (學員可能會調整目標)
            student_sorted = sorted(
                (s for s in parsed_sessions if s.student_name == name),
                key=lambda s: (s.session_date, s.session_no),
            )
            latest_targets = student_sorted[-1].student_targets if student_sorted else []
            goals = compute_goal_progress(
                latest_targets, prs,
                sessions=parsed_sessions, student_name=name,
            )
            goal_etas = compute_goal_etas(
                latest_targets, progressions, latest_date,
            ) if latest_date else {}
            favorite_exercise = compute_favorite_exercise(parsed_sessions, name)
            safe = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
            student_path = summary_dir / f"_student_{safe}.md"
            student_md = render_student_trend(
                trend,
                all_time_prs=prs,
                all_time_bw_prs=bw_prs,
                progressions=progressions,
                goals=goals,
                one_rm_progressions=one_rm_progressions,
                density_progression=density_progression,
                frequency=frequency,
                weekly_tonnage=weekly_tonnage,
                rpe_progression=rpe_progression,
                bw_reps_progressions=bw_reps_progressions,
                duration_progressions=duration_progressions,
                training_streak=training_streak,
                goal_etas=goal_etas,
                favorite_exercise=favorite_exercise,
            )
            student_path.write_text(student_md, encoding="utf-8")
            print(f"已寫入學員趨勢: {student_path}", file=sys.stderr)
            if args.batch_html:
                student_html_path = student_path.with_suffix(".html")
                student_html_path.write_text(
                    render_html_page(f"{name} 個人訓練趨勢",
                                     markdown_to_html(student_md)),
                    encoding="utf-8",
                )
                print(f"已寫入學員趨勢 HTML: {student_html_path}", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, nargs="?", help="本堂課訓練紀錄 JSON (單堂模式)")
    parser.add_argument("--batch", type=Path, help="批次模式:掃描目錄下所有 *.json 各產一份 .md")
    parser.add_argument("--out-dir", type=Path,
                        help="批次模式輸出目錄 (預設寫在原 .json 檔旁)")
    parser.add_argument("--summary-only", action="store_true",
                        help="批次模式只產 _batch_summary.md + _student_*.md,跳過個別 session .md")
    parser.add_argument("--batch-html", action="store_true",
                        help="批次模式同時產出 .html (與 .md 同名,適合 LINE 分享)")
    parser.add_argument("--batch-csv", action="store_true",
                        help="批次模式同時寫 _batch.csv (所有 sessions 的 sets concat,Excel pivot 用)")
    parser.add_argument("--student", type=str,
                        help="批次模式只跑指定學員 (其他學員 .json 略過)")
    parser.add_argument("--out", type=Path, help="markdown 輸出路徑 (省略 stdout;批次模式忽略)")
    parser.add_argument("--out-line", type=Path, help="LINE 純文字版輸出路徑")
    parser.add_argument("--csv", type=Path, help="把單堂訓練紀錄匯出成 CSV (Excel-friendly)")
    parser.add_argument("--html", type=Path, help="把單堂報告匯出成 HTML 網頁 (適合 LINE / email / 列印)")
    parser.add_argument("--prev", type=Path, help="上次課程 JSON,用來算 PR / 噸位 delta")
    parser.add_argument("--voice", type=Path,
                        help="口述/語音轉文字 → JSON skeleton 印到 stdout (預處理模式)")
    parser.add_argument("--template", action="store_true",
                        help="輸出新 session JSON 樣板到 stdout (PT 可 > new.json 後填寫)")
    parser.add_argument("--list-exercises", action="store_true",
                        help="列出 exercise_db 所有動作代碼 (依分類分組);PT 查 code 用")
    parser.add_argument("--no-ai", action="store_true", help="不呼叫 AI,輸出骨架")
    args = parser.parse_args()

    if args.list_exercises:
        sys.stdout.write(render_exercise_listing() + "\n")
        return 0

    if args.template:
        template = make_blank_session_template()
        sys.stdout.write(json.dumps(template, ensure_ascii=False, indent=2) + "\n")
        return 0

    if args.voice:
        if not args.voice.exists():
            print(f"error: --voice 找不到 {args.voice}", file=sys.stderr)
            return 2
        text = args.voice.read_text(encoding="utf-8")
        sets = parse_voice_transcript(text)
        skeleton = build_session_skeleton(sets)
        sys.stdout.write(json.dumps(skeleton, ensure_ascii=False, indent=2) + "\n")
        return 0

    if args.batch:
        return _run_batch(args)

    if args.input is None:
        print("error: 請指定 input JSON 或用 --batch DIR / --voice TXT", file=sys.stderr)
        return 2

    if not args.input.exists():
        print(f"error: 找不到 {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))

    schema_errors = validate_payload_schema(payload)
    if schema_errors:
        for e in schema_errors:
            print(f"error: schema {e}", file=sys.stderr)
        return 2

    session = parse_payload(payload)

    for w in validate_session(session, today_iso=date.today().isoformat()):
        print(f"warning: {w}", file=sys.stderr)

    pr_summary: str | None = None
    if args.prev:
        if not args.prev.exists():
            print(f"warning: --prev 檔案找不到: {args.prev}", file=sys.stderr)
        else:
            prev_payload = json.loads(args.prev.read_text(encoding="utf-8"))
            prev_session = parse_payload(prev_payload)
            pr_summary = render_pr_summary(
                compute_pr_deltas(prev_session.sets, session.sets),
                compute_bw_reps_deltas(prev_session.sets, session.sets),
                compute_duration_deltas(prev_session.sets, session.sets),
            )

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,輸出骨架版", file=sys.stderr)

    next_weight_summary = render_next_weight_suggestions(
        suggest_next_session_weights(session.sets)
    )
    one_rm_summary = render_1rm_estimates(
        compute_session_1rm_estimates(session.sets)
    )
    density_summary = render_training_density(session)

    body = ai_write_body(session) if use_ai else render_skeleton_body()
    full = render_full_report(session, body, pr_summary, next_weight_summary,
                              one_rm_summary=one_rm_summary,
                              density_summary=density_summary)

    if args.out:
        args.out.write_text(full, encoding="utf-8")
        print(f"已寫入 markdown: {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(full)

    if args.out_line:
        args.out_line.write_text(
            render_line_friendly(session, body, pr_summary, next_weight_summary,
                                 one_rm_summary=one_rm_summary,
                                 density_summary=density_summary),
            encoding="utf-8")
        print(f"已寫入 LINE 版: {args.out_line}", file=sys.stderr)

    if args.csv:
        write_session_csv(session, args.csv)
        print(f"已寫入 CSV: {args.csv}", file=sys.stderr)

    if args.html:
        body_html = markdown_to_html(full)
        title = f"{session.student_name} 課後訓練報告 (第 {session.session_no} 堂)"
        args.html.write_text(render_html_page(title, body_html), encoding="utf-8")
        print(f"已寫入 HTML: {args.html}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
