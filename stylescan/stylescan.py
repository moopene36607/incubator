"""stylescan — 繁中作文 AI 代筆風險偵測 CLI.

純函式做所有 stylometric 抽取 + cosine 計算(style_features.py),LLM 只負責:
  ① 為純函式找出的差異特徵寫人性化解釋(老師易讀)
  ② 提供文體改善建議(無論本人寫還是 AI 寫都適用)

LLM 永遠不下「是否為 AI 代寫」的最終結論 — 那是老師的判斷,工具只給證據。

模式:
  --no-ai   只跑純函式 (免 API key)
  full      加上 Claude 寫風格分析報告
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from style_features import (
    FEATURE_NAMES,
    FeatureDiff,
    average_features,
    cosine_similarity,
    extract_features,
    top_differing_features,
)


# --- 判定門檻 ---
SIM_TO_STUDENT_CONSISTENT = 0.85   # ≥ 視為與本人風格一致
SIM_TO_STUDENT_DRIFT = 0.78        # < 視為顯著漂移
SIM_TO_AI_HIGH = 0.88              # ≥ 視為高度疑似 AI

# --- LLM ---
SYSTEM_PROMPT = textwrap.dedent("""
    你是國高中國文老師的助教,專長作文風格分析。

    輸入會給你三組 stylometric features 摘要:
      - student_avg: 學生過去 5 篇作文平均
      - new_essay  : 本次繳交作文
      - ai_reference: GPT/Claude 中文範文平均
    以及純函式算出的 cosine 相似度與 verdict。

    你的工作:
      1. 用「老師看得懂」的中文,挑 3-5 個最關鍵的特徵差異寫風格分析(不是逐項解釋每個 feature)
      2. 寫文體改善建議 3 條(學生看得懂 + 可立刻練習)
      3. 給老師的 follow-up 建議(訪談 / 課堂寫作 / 觀察)

    硬規則:
      - 你**絕不**自己算 cosine 或 features — 那些都是純函式算出的。直接引用提供的數字。
      - 你**絕不**下「這篇就是 AI 寫的」這種斷論。工具只列證據,**最終由老師判讀**。
        用語應為「風格大幅偏離本人」/「與 AI 風格高度相似」/「建議老師訪談確認」。
      - 行動建議必須具體可執行(壞例:「多練筆」;好例:「請學生課堂上 30 分鐘現場寫一段 200 字,觀察句長與用詞」)。
      - 不指控學生作弊;保留誠實的可能性(學生可能臨時讀了一本散文)。

    回覆 JSON:
    {
      "style_analysis": "3-5 段風格差異分析(150-250 字)...",
      "writing_advice_for_student": ["...", "...", "..."],
      "follow_up_for_teacher": ["...", "...", "..."],
      "verdict_summary": "一句話結論(根據純函式 verdict 翻譯成老師易讀的話,不下 AI 代寫斷論)"
    }
""").strip()


@dataclass
class Verdict:
    code: str        # CONSISTENT | MILD_DRIFT | STRONG_DRIFT | LIKELY_AI
    summary: str
    sim_to_student: float
    sim_to_ai: float
    student_internal_consistency: float


def decide_verdict(
    sim_to_student: float,
    sim_to_ai: float,
    student_internal: float,
) -> Verdict:
    """純函式判定。LLM 永不參與。

    判定優先序(LIKELY_AI 條件比 STRONG_DRIFT 寬,因為 AI 風格相似度高就足夠警示):
      A. CONSISTENT  - 與本人相似度高,且 AI 沒有壓倒本人
      B. LIKELY_AI   - 兩種情境之一:
          B1. sim_to_student < 漂移門檻 AND sim_to_ai 高(經典 AI 代筆)
          B2. sim_to_ai 高 AND ai_dominance ≥ 0.10(本次明顯比學生更像 AI,
              即使 sim_to_student 因中文作文共通底噪未跌破門檻)
      C. STRONG_DRIFT - 與本人相似度低但 AI 也不高,可能成熟 / 模仿
      D. MILD_DRIFT   - 一切都在合理範圍
    """
    ai_dominance = sim_to_ai - sim_to_student  # > 0 表示比本人更像 AI

    consistent = (
        sim_to_student >= SIM_TO_STUDENT_CONSISTENT
        and ai_dominance < 0.05
    )
    likely_ai_classic = (
        sim_to_student < SIM_TO_STUDENT_DRIFT
        and sim_to_ai >= SIM_TO_AI_HIGH
    )
    likely_ai_dominance = (
        sim_to_ai >= SIM_TO_AI_HIGH
        and ai_dominance >= 0.10
    )

    if consistent:
        code = "CONSISTENT"
        summary = (f"作文風格與學生過去作品一致 (cosine {sim_to_student:.2f} ≥ "
                   f"{SIM_TO_STUDENT_CONSISTENT})。AI 代筆風險低。")
    elif likely_ai_classic or likely_ai_dominance:
        code = "LIKELY_AI"
        which = "風格漂移 + AI 高度相似" if likely_ai_classic else "AI 相似度遠超本人相似度"
        summary = (f"高警示({which}):本次作文 vs 本人 cosine {sim_to_student:.2f}, "
                   f"vs AI 範本 cosine {sim_to_ai:.2f},AI 主導度 +{ai_dominance:.2f}。"
                   f"建議老師訪談 + 現場寫作驗證。")
    elif sim_to_student < SIM_TO_STUDENT_DRIFT:
        code = "STRONG_DRIFT"
        summary = (f"風格顯著漂移:本次作文與學生過去 5 篇平均相似度 "
                   f"{sim_to_student:.2f},低於漂移門檻 {SIM_TO_STUDENT_DRIFT}。"
                   f"AI 風險中等 (cosine vs AI = {sim_to_ai:.2f})。"
                   f"可能原因:成熟、模仿散文、AI 代筆。建議老師觀察。")
    else:
        code = "MILD_DRIFT"
        summary = (f"風格略有變化但仍在合理範圍 (cosine vs 本人 {sim_to_student:.2f}, "
                   f"vs AI {sim_to_ai:.2f}, 學生內部一致度 {student_internal:.2f})。"
                   f"風險低,正常作文成長皆可解釋。")
    return Verdict(
        code=code,
        summary=summary,
        sim_to_student=sim_to_student,
        sim_to_ai=sim_to_ai,
        student_internal_consistency=student_internal,
    )


def _strip_header(raw: str) -> str:
    """剝掉「題目: / 作者: / 日期:」這種 metadata 前置行。"""
    lines = raw.splitlines()
    body: list[str] = []
    in_body = False
    for line in lines:
        s = line.strip()
        if not in_body and (
            s.startswith("題目")
            or s.startswith("作者")
            or s.startswith("日期")
            or s.startswith("Title")
            or s.startswith("Author")
        ):
            continue
        if s == "" and not in_body:
            continue
        in_body = True
        body.append(line)
    return "\n".join(body).strip()


def _format_diff_table(diffs: list[FeatureDiff]) -> str:
    rows = ["| 特徵 | 學生平均 | 本次作文 | AI 範本 | 偏離 | 趨向 AI? |",
            "|---|---|---|---|---|---|"]
    for d in diffs:
        rows.append(
            f"| `{d.feature}` | {d.student_value} | {d.new_value} | "
            f"{d.ai_value} | {d.abs_drift_from_student} | "
            f"{'✓' if d.closer_to_ai else '—'} |"
        )
    return "\n".join(rows)


def render_no_ai_report(
    student_name: str,
    title: str,
    verdict: Verdict,
    diffs: list[FeatureDiff],
    history_internal_pairs: list[tuple[str, float]],
) -> str:
    parts: list[str] = []
    parts.append(f"# stylescan 作文書寫指紋偵測 — {student_name}")
    parts.append(f"\n**作文題目**: {title}")
    parts.append(f"**判定**: `{verdict.code}`")
    parts.append("")
    parts.append("## 純函式判定摘要\n")
    parts.append(verdict.summary)
    parts.append("")
    parts.append(f"- cosine(本次, 學生過去 5 篇平均): **{verdict.sim_to_student:.4f}**")
    parts.append(f"- cosine(本次, AI 範本平均): **{verdict.sim_to_ai:.4f}**")
    parts.append(f"- 學生內部一致度(過去 5 篇 vs 平均 之 mean): **{verdict.student_internal_consistency:.4f}**")
    parts.append("")
    parts.append("## 學生過去 5 篇 vs 本人平均(內部一致度基線)\n")
    for title_, sim in history_internal_pairs:
        parts.append(f"- {title_} → cosine **{sim:.4f}**")
    parts.append("")
    parts.append("## Top 6 偏離特徵(本次 vs 學生平均)\n")
    parts.append(_format_diff_table(diffs))
    parts.append("")
    parts.append("---")
    parts.append("*純函式模式:無 AI 解釋。最終是否認定為代筆,請由老師依照本表 + 訪談判讀。*")
    return "\n".join(parts)


def render_full_report(
    student_name: str,
    title: str,
    verdict: Verdict,
    diffs: list[FeatureDiff],
    history_internal_pairs: list[tuple[str, float]],
    ai: dict,
) -> str:
    parts: list[str] = []
    parts.append(f"# stylescan 作文書寫指紋偵測 — {student_name}")
    parts.append(f"\n**作文題目**: {title}")
    parts.append(f"**判定**: `{verdict.code}`")
    parts.append("")
    parts.append("## 結論摘要\n")
    parts.append(ai.get("verdict_summary", verdict.summary))
    parts.append("")
    parts.append(f"- cosine(本次, 學生過去 5 篇平均): **{verdict.sim_to_student:.4f}**")
    parts.append(f"- cosine(本次, AI 範本平均): **{verdict.sim_to_ai:.4f}**")
    parts.append(f"- 學生內部一致度: **{verdict.student_internal_consistency:.4f}**")
    parts.append("")
    parts.append("## 學生過去 5 篇 vs 本人平均(內部一致度基線)\n")
    for title_, sim in history_internal_pairs:
        parts.append(f"- {title_} → cosine **{sim:.4f}**")
    parts.append("")
    parts.append("## 風格分析(由 AI 撰寫,僅作老師參考)\n")
    parts.append(ai.get("style_analysis", ""))
    parts.append("")
    parts.append("## Top 6 偏離特徵(本次 vs 學生平均)\n")
    parts.append(_format_diff_table(diffs))
    parts.append("")
    parts.append("## 給學生的文體建議\n")
    for tip in ai.get("writing_advice_for_student", []):
        parts.append(f"- {tip}")
    parts.append("")
    parts.append("## 給老師的 follow-up 建議\n")
    for tip in ai.get("follow_up_for_teacher", []):
        parts.append(f"- {tip}")
    parts.append("")
    parts.append("---")
    parts.append("*stylescan 不下最終結論。AI 代筆判定權仍在老師。*")
    return "\n".join(parts)


def ai_explain(
    student_name: str,
    verdict: Verdict,
    diffs: list[FeatureDiff],
    student_avg: dict[str, float],
    new_feats: dict[str, float],
    ai_avg: dict[str, float],
) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "student_name": student_name,
        "verdict_code": verdict.code,
        "verdict_summary": verdict.summary,
        "sim_to_student": verdict.sim_to_student,
        "sim_to_ai": verdict.sim_to_ai,
        "student_internal_consistency": verdict.student_internal_consistency,
        "top_differing_features": [
            {
                "feature": d.feature,
                "student_avg": d.student_value,
                "new_essay": d.new_value,
                "ai_reference": d.ai_value,
                "closer_to_ai": d.closer_to_ai,
            }
            for d in diffs
        ],
        "feature_legend": {
            "avg_sentence_len": "平均句長(字)",
            "sentence_len_std": "句長標準差",
            "short_sentence_ratio": "<12 字短句佔比",
            "long_sentence_ratio": ">30 字長句佔比",
            "comma_per1k": "逗號 / 1000 字",
            "transition_per1k": "連接詞(因此/然而/所以) / 1000 字",
            "modal_per1k": "語氣詞(啊/呀/啦/吧/嗎) / 1000 字",
            "lyrical_per1k": "抒情比擬詞(彷彿/如同) / 1000 字",
            "abstract_per1k": "抽象思辨詞(感悟/體悟/啟發) / 1000 字",
            "literary_per1k": "古文書面語(彼時/然則/不禁) / 1000 字",
            "structure_kw_per1k": "結構關鍵詞(首先/總而言之) / 1000 字",
        },
    }
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)}],
    )
    text = resp.content[0].text
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


def main() -> None:
    p = argparse.ArgumentParser(description="stylescan — 繁中作文書寫指紋 AI 代筆偵測")
    p.add_argument("--history", required=True, help="學生過去作文 JSON")
    p.add_argument("--new-essay", required=True, help="本次作文 .txt")
    p.add_argument("--ai-corpus", required=True, help="AI 範本 corpus JSON")
    p.add_argument("--title", default="(未命名)", help="本次作文題目")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    history_raw = json.loads(Path(args.history).read_text(encoding="utf-8"))
    ai_corpus = json.loads(Path(args.ai_corpus).read_text(encoding="utf-8"))
    new_text = _strip_header(Path(args.new_essay).read_text(encoding="utf-8"))

    student_name = history_raw.get("student_name", "(未命名學生)")

    student_feats_list = [extract_features(e["text"]) for e in history_raw["essays"]]
    student_avg = average_features(student_feats_list)
    ai_feats_list = [extract_features(e["text"]) for e in ai_corpus["essays"]]
    ai_avg = average_features(ai_feats_list)

    new_feats = extract_features(new_text)

    sim_to_student = cosine_similarity(new_feats, student_avg)
    sim_to_ai = cosine_similarity(new_feats, ai_avg)

    # 學生內部一致度 = 過去 5 篇各自 vs student_avg cosine 的平均
    history_internal_pairs = [
        (e["title"], cosine_similarity(student_feats_list[i], student_avg))
        for i, e in enumerate(history_raw["essays"])
    ]
    student_internal = round(
        sum(sim for _, sim in history_internal_pairs) / len(history_internal_pairs), 4
    )

    verdict = decide_verdict(sim_to_student, sim_to_ai, student_internal)
    diffs = top_differing_features(student_avg, new_feats, ai_avg, top_n=6)

    if args.no_ai:
        report = render_no_ai_report(
            student_name, args.title, verdict, diffs, history_internal_pairs
        )
    else:
        ai = ai_explain(student_name, verdict, diffs, student_avg, new_feats, ai_avg)
        report = render_full_report(
            student_name, args.title, verdict, diffs, history_internal_pairs, ai
        )

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
