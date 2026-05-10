"""teachsay — 台灣國中小老師家長 LINE 溝通 AI 助手 + active learning CLI.

純函式做 style features + intent + style match score(style.py + intent.py)。
LLM 負責:
  ① 用老師 style profile + 訊息 intent 生成 3 個草稿(formal / warm / brief 3 個 tone)
  ② 為每個草稿寫「為什麼這樣寫」(讓老師看得懂風格選擇)
  ③ 在「老師選擇 + 微調」後 → 純函式 update profile + LLM 解釋「學到什麼」

LLM 永不算 style_match_score。
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from dataclasses import asdict
from pathlib import Path

from intent import INTENT_LABEL_ZH, Intent, classify_parent_message
from style import (
    FeatureDelta,
    StyleFeatures,
    TeacherStyleProfile,
    compute_diff,
    compute_profile,
    style_match_score,
    update_profile_with_new_sample,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣國中小老師家長 LINE 溝通的 AI 助手。

    輸入:
      - 老師個資(學校 / 任教科目)
      - 老師過去回覆 corpus(5-10 則)— 用於學習風格
      - 老師的 style profile(已從 corpus 純函式抽出 12 個特徵)
      - 新進家長訊息 + intent 分類

    工作:
      1. 為老師生成 3 個草稿,**每個都符合老師 style profile** 但語氣略不同:
         - 第 1 個:formal 偏正式
         - 第 2 個:warm 偏暖意(預設,通常老師最常選)
         - 第 3 個:brief 偏簡短(忙的時候用)
      2. 為每個草稿寫 30-50 字「為什麼這樣寫」(讓老師看得懂風格選擇)
      3. 推薦 1 個版本(基於 intent + urgency)

    硬規則:
      - 你**絕不**改變老師的核心稱呼模式(若 profile 顯示『家長您好』開頭就照用)
      - 你**絕不**用罐頭式語句「已收到」「會處理」(老師最反感)
      - 草稿要引用具體事件 / 行動(profile event_reference_count > 1 表示老師愛這樣寫)
      - 草稿要給具體 action items(profile specific_action_count > 1 表示老師愛這樣寫)
      - 不超過老師 avg_length × 1.5(避免過長)
      - 用台灣繁體中文 + 在地用語(請假單 / 學習單 / 午休 / 早自習)

    回覆 JSON:
    {
      "drafts": [
        {"tone": "formal", "text": "...", "explanation": "..."},
        {"tone": "warm", "text": "...", "explanation": "..."},
        {"tone": "brief", "text": "...", "explanation": "..."}
      ],
      "recommended_tone": "warm",
      "recommendation_reasoning": "..."
    }
""").strip()


LEARN_SYSTEM_PROMPT = textwrap.dedent("""
    你是 active learning 助手,負責讓老師了解「系統從這次互動學到什麼」。

    輸入:
      - profile diff(top 5 feature changes,純函式計算)

    工作:用 50-100 字的人話跟老師說:
      - 系統觀察到老師這次的編輯帶來什麼風格變化(暖度 / 長度 / 敬語 / emoji ...)
      - 下次系統會更傾向 ___(具體說明)

    硬規則:
      - 不要列特徵名稱(老師不懂)— 用「您這次用了較多 / 較少 ___」的人話
      - 不要超過 100 字

    純文字回應(不需 JSON)。
""").strip()


def llm_generate_drafts(
    teacher_data: dict,
    profile: TeacherStyleProfile,
    parent_msg: str,
    intent: Intent,
) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "teacher_name": teacher_data.get("teacher_name"),
        "school": teacher_data.get("school"),
        "history_replies": [h["teacher_reply"] for h in teacher_data["history"]],
        "style_profile": profile.to_dict(),
        "new_parent_message": parent_msg,
        "intent": {
            "category": intent.category,
            "category_zh": INTENT_LABEL_ZH.get(intent.category, intent.category),
            "urgency": intent.urgency,
            "confidence": intent.confidence,
        },
    }
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)}],
    )
    text = resp.content[0].text
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


def llm_summarize_learning(diffs: list[FeatureDelta]) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        return "(API key 未設定,無法產出 active learning 摘要)"
    client = Anthropic()
    payload = {
        "feature_changes": [
            {
                "feature": d.feature,
                "old_value": d.old_value,
                "new_value": d.new_value,
                "delta": d.delta,
                "interpretation": d.interpretation,
            }
            for d in diffs
        ]
    }
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=LEARN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)}],
    )
    return resp.content[0].text.strip()


def render_no_ai_report(teacher_data: dict, profile: TeacherStyleProfile, intent: Intent,
                          new_profile: TeacherStyleProfile, diffs: list[FeatureDelta]) -> str:
    parts = ["# teachsay 老師家長 LINE 溝通助手報告\n"]
    parts.append("**模式**: 純函式 style + intent(免 API key)\n")
    parts.append(f"## 老師基本資料\n")
    parts.append(f"- **老師**: {teacher_data.get('teacher_name')}")
    parts.append(f"- **學校 / 班級**: {teacher_data.get('school')}")
    parts.append(f"- **歷史回覆 corpus**: {profile.n_samples} 則")
    parts.append("")

    parts.append("## 新進家長訊息\n")
    parts.append(f"> {teacher_data['new_parent_message']}")
    parts.append("")
    parts.append(f"**Intent 分類**: `{intent.category}` ({INTENT_LABEL_ZH[intent.category]})")
    parts.append(f"**Urgency**: `{intent.urgency}` / **Confidence**: {intent.confidence}")
    parts.append("")

    parts.append("## 老師當前風格 Profile(12 features)\n")
    parts.append("| 特徵 | 值 | 解讀 |")
    parts.append("|---|---|---|")
    feat = profile.features
    parts.append(f"| 平均字數 | {feat.avg_length} | {'長 (>150)' if feat.avg_length > 150 else ('中等' if feat.avg_length > 80 else '短 (<80)')} |")
    parts.append(f"| 開頭暖度 | {feat.opener_warmth_score}/10 | {'高 (常用「家長您好」)' if feat.opener_warmth_score > 5 else '低'} |")
    parts.append(f"| 結尾正式度 | {feat.closer_formality_score}/10 | {'高' if feat.closer_formality_score > 5 else ('中' if feat.closer_formality_score > 1 else '低')} |")
    parts.append(f"| 敬語密度 (/100 字) | {feat.honorific_density_per100} | - |")
    parts.append(f"| 引用具體事件次數 | {feat.event_reference_count} | {'常引用 (個人化)' if feat.event_reference_count >= 1 else '少引用'} |")
    parts.append(f"| 具體行動次數 | {feat.specific_action_count} | {'常給 action items' if feat.specific_action_count >= 1 else '少給'} |")
    parts.append(f"| emoji 密度 | {feat.emoji_density_per100} | {'高' if feat.emoji_density_per100 > 1 else '低 / 不用'} |")
    parts.append(f"| 驚嘆密度 | {feat.exclamation_density_per100} | {'高 (語氣熱情)' if feat.exclamation_density_per100 > 3 else '中'} |")
    parts.append("")

    parts.append("## Active Learning 模擬\n")
    parts.append(f"假設老師選擇了某個草稿 + 微調,最終送出的版本是:\n")
    parts.append(f"> {teacher_data['simulated_teacher_edit']}")
    parts.append("")
    parts.append(f"純函式 update profile (n: {profile.n_samples} → {new_profile.n_samples}):\n")
    parts.append("**Top 5 風格變化**:")
    for d in diffs:
        parts.append(f"- `{d.feature}`: {d.old_value} → {d.new_value} ({d.delta:+.2f}) — {d.interpretation}")
    parts.append("")
    new_match = style_match_score(teacher_data['simulated_teacher_edit'], new_profile)
    parts.append(f"**老師編輯版本 vs 新 profile 的 style match**: {new_match}")
    parts.append("")
    parts.append("---")
    parts.append("*純函式模式無 AI 草稿生成。AI 模式會生成 3 個 tone(formal / warm / brief)+ 解釋。*")
    parts.append("*teachsay 是輔助工具,**最終訊息送出前老師審閱**。重要案件(行為 / 投訴)建議親自完整撰寫。*")
    return "\n".join(parts)


def render_full_report(teacher_data: dict, profile: TeacherStyleProfile, intent: Intent,
                        drafts_ai: dict, new_profile: TeacherStyleProfile,
                        diffs: list[FeatureDelta], learning_summary: str) -> str:
    parts = ["# teachsay 老師家長 LINE 溝通助手報告\n"]
    parts.append("**模式**: 純函式 style + intent + LLM 草稿 + active learning\n")
    parts.append(f"## 老師資料\n")
    parts.append(f"- **老師**: {teacher_data.get('teacher_name')}")
    parts.append(f"- **學校 / 班級**: {teacher_data.get('school')}")
    parts.append(f"- **歷史回覆學習樣本**: {profile.n_samples} 則")
    parts.append("")

    parts.append("## 新進家長訊息\n")
    parts.append(f"> {teacher_data['new_parent_message']}")
    parts.append("")
    parts.append(f"- **Intent**: `{intent.category}` ({INTENT_LABEL_ZH[intent.category]})")
    parts.append(f"- **Urgency**: `{intent.urgency}`")
    parts.append("")

    parts.append("## AI 生成草稿(3 個 tone)\n")
    for d in drafts_ai.get("drafts", []):
        match = style_match_score(d.get("text", ""), profile)
        parts.append(f"### Tone: **{d.get('tone', '?')}** (style match {match}/100)")
        parts.append(f"```")
        parts.append(d.get("text", ""))
        parts.append(f"```")
        parts.append(f"**為什麼這樣寫**: {d.get('explanation', '')}")
        parts.append("")
    if drafts_ai.get("recommended_tone"):
        parts.append(f"## 推薦版本: **{drafts_ai['recommended_tone']}**\n")
        parts.append(f"{drafts_ai.get('recommendation_reasoning', '')}")
        parts.append("")

    parts.append("## Active Learning 結果\n")
    parts.append(f"老師選擇 + 微調後送出版本:\n")
    parts.append(f"> {teacher_data['simulated_teacher_edit']}")
    parts.append("")
    parts.append(f"**Profile 更新**: n={profile.n_samples} → {new_profile.n_samples} 樣本\n")
    parts.append("**系統學到的變化(top 5)**:")
    for d in diffs:
        parts.append(f"- {d.interpretation} ({d.old_value} → {d.new_value}, Δ {d.delta:+.2f})")
    parts.append("")
    parts.append("### AI 解釋\n")
    parts.append(learning_summary)
    parts.append("")
    parts.append("---")
    parts.append("*teachsay 是輔助工具,**最終訊息送出前老師審閱**。重要案件(行為 / 投訴)建議親自完整撰寫。*")
    parts.append("*老師個資 + 家長訊息 + 學生資訊在企業版可走 self-host LLM(放校內伺服器)避免外流。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="teachsay — 老師家長 LINE 溝通 AI 助手")
    p.add_argument("teacher_data", help="teacher_data.json")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    data = json.loads(Path(args.teacher_data).read_text(encoding="utf-8"))

    history_replies = [h["teacher_reply"] for h in data["history"]]
    profile = compute_profile(history_replies)

    new_msg = data["new_parent_message"]
    intent = classify_parent_message(new_msg)

    # Simulate active learning step
    new_profile = update_profile_with_new_sample(profile, data["simulated_teacher_edit"])
    diffs = compute_diff(profile, new_profile, top_n=5)

    if args.no_ai:
        report = render_no_ai_report(data, profile, intent, new_profile, diffs)
    else:
        drafts = llm_generate_drafts(data, profile, new_msg, intent)
        learning_summary = llm_summarize_learning(diffs)
        report = render_full_report(data, profile, intent, drafts, new_profile, diffs, learning_summary)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
