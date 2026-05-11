"""phonefix CLI — 兒童國語注音發音矯正 (構音異常居家輔助)。

Usage:
    python phonefix.py --session samples/practice_session.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from editdist import (
    analyze_pronunciation, detect_systematic_pattern,
    PronunciationReport, weighted_edit_distance, tokenize_phrase,
    PHONEME_CLASSES, PHONEME_TO_CLASS,
)


def load_session(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_alignment_visual(target_tokens: list[str], actual_tokens: list[str],
                              ops: list[tuple[str, str, str]]) -> str:
    """Render alignment as paired strings with op markers."""
    lines = []
    target_row = []
    actual_row = []
    op_row = []
    for op, t, a in ops:
        if op == "=":
            target_row.append(f"{t}")
            actual_row.append(f"{a}")
            op_row.append("  ")
        elif op == "sub":
            target_row.append(f"{t}")
            actual_row.append(f"{a}")
            op_row.append("✗ ")
        elif op == "ins":
            target_row.append("  ")
            actual_row.append(f"{a}")
            op_row.append("+ ")
        elif op == "del":
            target_row.append(f"{t}")
            actual_row.append("  ")
            op_row.append("- ")
    return " ".join(target_row), " ".join(actual_row), " ".join(op_row)


def render_no_ai(session: dict, all_reports: list[tuple[dict, PronunciationReport]]) -> str:
    # Aggregate stats
    total_phonemes = sum(r.n_phonemes_target for _, r in all_reports)
    total_cost = sum(r.total_edit_cost for _, r in all_reports)
    overall_accuracy = (1.0 - total_cost / total_phonemes) * 100 if total_phonemes else 0

    # Combined error patterns
    combined_patterns: Counter = Counter()
    for _, r in all_reports:
        for p, c in r.error_patterns.items():
            combined_patterns[p] += c

    # Most common substitution phoneme pairs
    pair_counter: Counter = Counter()
    for _, r in all_reports:
        for d in r.error_details:
            pair_counter[(d["target_phoneme"], d["actual_phoneme"])] += 1

    lines = [
        f"# phonefix — {session['child_name']} 注音構音分析報告",
        "",
        f"**年齡**: {session['child_age_years']} 歲 {session['child_age_months']} 個月",
        f"**練習日期**: {session['session_date']}",
        f"**練習主題**: {session.get('practice_topic', 'N/A')}",
        f"**總練習句數**: {len(all_reports)}  ·  **總音素數**: {total_phonemes}",
        "",
        "## 🎯 整體準確度",
        "",
        f"### {overall_accuracy:.1f}%",
        "",
        f"- **總編輯成本**: {total_cost:.2f} (Levenshtein with phoneme cost)",
        f"- **總音素**: {total_phonemes} 個",
        "",
        "## 📊 各句練習結果",
        "",
        "| # | 中文 | 準確度 | 替換 | 刪除 | 插入 |",
        "|---|---|---|---|---|---|",
    ]
    for i, (ex, r) in enumerate(all_reports):
        lines.append(
            f"| {i + 1} | {ex['phrase_chinese']} | {r.accuracy_pct}% | "
            f"{sum(s.n_substitutions for s in r.syllable_alignments)} | "
            f"{sum(s.n_deletions for s in r.syllable_alignments)} | "
            f"{sum(s.n_insertions for s in r.syllable_alignments)} |"
        )

    lines.extend([
        "",
        "## 🔍 系統性構音模式",
        "",
        "| 模式 | 出現次數 | 說明 |",
        "|---|---|---|",
    ])
    for pattern, count in sorted(combined_patterns.items(), key=lambda x: -x[1]):
        marker = "🔴" if count >= 3 else ("🟡" if count >= 2 else "🟢")
        lines.append(f"| {marker} {pattern} | **{count}**x | 系統性 = 治療目標 / 零星 = 自然發展 |")

    lines.extend([
        "",
        "## 🔤 最常錯的音素對 (target → actual)",
        "",
        "| 排序 | 應念 | 實際念 | 出現次數 |",
        "|---|---|---|---|",
    ])
    for rank, ((t, a), cnt) in enumerate(pair_counter.most_common(8)):
        lines.append(f"| {rank + 1} | **{t}** | **{a}** | {cnt}x |")

    lines.append("")
    lines.append("## 各句 phoneme alignment 細節")
    lines.append("")
    for i, (ex, r) in enumerate(all_reports):
        if r.error_details:    # 只顯示有錯的句子
            lines.append(f"### {i + 1}. {ex['phrase_chinese']}")
            lines.append("")
            lines.append(f"- target: `{ex['target_bopomofo']}`")
            lines.append(f"- actual: `{ex['actual_bopomofo']}`")
            lines.append(f"- accuracy: {r.accuracy_pct}%  ·  cost: {r.total_edit_cost}")
            lines.append("")
            for d in r.error_details:
                lines.append(f"  - 第 {d['syllable_idx'] + 1} 音節: `{d['target_phoneme']}` → `{d['actual_phoneme']}` ({d['pattern']})")
            lines.append("")

    # Systematic pattern detection
    top_pattern = max(combined_patterns.items(), key=lambda x: x[1])[0] if combined_patterns else None
    top_count = combined_patterns.get(top_pattern, 0) if top_pattern else 0

    lines.append("## 純函式診斷")
    lines.append("")
    if top_pattern and top_count >= 3:
        lines.append(f"🔴 **發現系統性構音錯誤**: `{top_pattern}` 出現 {top_count} 次")
        lines.append("")
        lines.append("這個模式跨多個句子出現,屬於**典型構音異常**(非 自然發展中的偶發錯誤)。")
        lines.append(f"")
        lines.append(f"**建議**: 安排語言治療師評估 (健保 / 自費 NT$1,500-3,000/次)")
    elif top_pattern and top_count >= 2:
        lines.append(f"🟡 **發現潛在構音模式**: `{top_pattern}` 出現 {top_count} 次")
        lines.append("")
        lines.append("可在家持續練習 4-6 週觀察是否改善,若持續再諮詢語言治療師。")
    else:
        lines.append("🟢 整體發音準確,零星錯誤屬正常發展。")

    lines.append("")
    lines.append("## ⚠️ 模型假設與限制")
    lines.append("")
    lines.append("- **依賴家長輸入**: prototype 用家長記錄的注音對照, 真實 launch 版需要錄音 → MFCC 抽取 + auto-phoneme 識別 (Whisper / Pin1Yin1)")
    lines.append("- **substitution cost 是 hand-crafted**: 12 對最常見構音錯誤先驗 cost 0.3-0.5;Pro 版用大樣本臨床資料學 cost matrix")
    lines.append("- **聲調未深入比對**: 簡化版聲調用 _toneN token, 真實 launch 需要 prosodic analysis")
    lines.append("- **不取代語言治療師**: 工具用於 home practice + 監控進度, 確診 / 治療仍需專業評估")
    lines.append("- **發展期錯誤**: 4-5 歲 ㄓㄔㄕ 還在發展中是正常的, 6 歲後還系統性錯誤才算構音異常")
    lines.append("")
    lines.append("---")
    lines.append("*phonefix = Levenshtein 1965 weighted edit distance × 台灣 3-8 歲兒童構音矯正 niche = 在家練習 + 系統性錯誤偵測, 補語言治療師排隊空檔。*")
    return "\n".join(lines)


def render_with_ai(session, all_reports):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(session, all_reports)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(session, all_reports)

    base = render_no_ai(session, all_reports)

    # Aggregate facts
    combined_patterns: Counter = Counter()
    pair_counter: Counter = Counter()
    for _, r in all_reports:
        for p, c in r.error_patterns.items():
            combined_patterns[p] += c
        for d in r.error_details:
            pair_counter[(d["target_phoneme"], d["actual_phoneme"])] += 1

    top_pattern = max(combined_patterns.items(), key=lambda x: x[1])[0] if combined_patterns else "無"
    top_count = combined_patterns.get(top_pattern, 0) if top_pattern else 0
    top_pairs = pair_counter.most_common(5)

    age = session['child_age_years'] + session['child_age_months'] / 12
    total_acc = sum(r.accuracy_pct for _, r in all_reports) / len(all_reports)

    prompt = f"""你是一位資深台灣語言治療師, 處理過上千兒童構音案例。下面是用 Levenshtein 加權編輯距離純函式分析 {len(all_reports)} 句發音練習的結果:

兒童: {session['child_name']} {age:.1f} 歲
整體準確度: {total_acc:.1f}%
最常見構音錯誤: {top_pattern} ({top_count}x)
錯誤音素對: {top_pairs}

請寫 250-350 字「家長居家練習建議」:
1. 一句翻譯系統性錯誤 (避免「Levenshtein」「phoneme」等技術詞), 用家長聽得懂的話
2. **3 個今天就能做的家庭練習**(具體口訣 / 鏡子練習 / 遊戲, 每個 5-10 分鐘)
3. **何時必看語言治療師**(年齡紅旗 / 持續時間紅旗 / 影響日常溝通紅旗)
4. 1 個情緒安撫: 給可能焦慮的家長一句話 (不要套話)

**嚴格規則**:
- 不要重算數字, 引用上面 facts
- 不要套話 ("加油", "辛苦了")
- 不超過 350 字
- 不要 markdown 標題

直接寫居家練習腳本。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 語言治療師家長指引\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="phonefix — 兒童注音構音矯正")
    p.add_argument("--session", default="samples/practice_session.json")
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    session = load_session(Path(args.session))
    all_reports = []
    for ex in session["exercises"]:
        report = analyze_pronunciation(ex["target_bopomofo"], ex["actual_bopomofo"])
        all_reports.append((ex, report))

    if args.no_ai:
        print(render_no_ai(session, all_reports))
    else:
        print(render_with_ai(session, all_reports))


if __name__ == "__main__":
    main()
