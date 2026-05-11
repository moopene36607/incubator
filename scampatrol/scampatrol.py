"""scampatrol CLI -- LINE 詐騙訊息個人端 weak-supervision 多 rule 偵測.

Usage:
    python3 scampatrol.py --data samples/messages.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from wsup import (
    apply_lfs, apply_lfs_batch, majority_vote,
    fit_dawid_skene, predict_one,
    lf_coverage, lf_estimated_accuracy,
    DEFAULT_LFS, CLASS_NAMES, N_CLASSES, ABSTAIN,
)


# Class-specific defensive advice
CLASS_ADVICE: dict[int, dict[str, str]] = {
    0: {
        "urgency": "正常",
        "action": "看起來像合法訊息 -- 但若仍覺得可疑, 對對方做反向驗證 (打官方電話 / LINE 既有對話確認)",
        "report": "若不放心, 截圖 + 提交 165 確認 (打電話 165 或下載 165 APP)",
    },
    1: {
        "urgency": "🔴 高度懷疑",
        "action": "**立刻封鎖** + 不點任何連結 + 不轉帳;告知家人朋友這個 LINE 帳號;不要單獨進入「投資群組」",
        "report": "165 反詐騙專線 + 警政署「打詐儀表板」https://165dashboard.tw 通報",
    },
    2: {
        "urgency": "🔴 高度懷疑",
        "action": "**真實警察 / 銀行絕不會在 LINE 要求個資 / 驗證碼 / 匯款**。立刻封鎖;打官方電話確認 (銀行卡背面號碼)",
        "report": "165 + 該銀行客服 (官方電話) 雙重通報",
    },
    3: {
        "urgency": "🔴 高度懷疑",
        "action": "**絕不點連結**, 不輸入個資;若已點, 立刻清除 LINE / 瀏覽器快取 + 改密碼 + 監控信用卡帳單",
        "report": "165 + iWin 網路內容防護機構 通報 (網址帶疑似 phishing domain)",
    },
    4: {
        "urgency": "🔴 高度懷疑",
        "action": "**透過原本認識的管道 (打電話 / 直接見面) 二次確認**。真實親友失聯時不會只在 LINE 急借錢",
        "report": "若確認被詐騙 (對方拒絕電話確認 / 不肯露臉), 165 通報",
    },
}


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_no_ai(data: dict, model, training_msgs: list[dict],
                  test_msg: dict, test_lfs: list[int], pred: dict,
                  coverage: list[float], accuracies: list[float]) -> str:
    lines = [
        "# scampatrol -- LINE 詐騙訊息 weak-supervision 個人端偵測",
        "",
        f"**LFs (labelling functions)**: {len(DEFAULT_LFS)}",
        f"**Classes**: {N_CLASSES} ({', '.join(CLASS_NAMES)})",
        f"**訓練 messages (無標註)**: {len(training_msgs)}",
        f"**Dawid-Skene EM 收斂**: {model.n_iter_used} iterations (log-lik {model.final_log_lik:.1f})",
        "",
        "## 📡 LF 診斷",
        "",
        "| LF | 覆蓋率 | 估計準確度 (E[pi·diag]) |",
        "|---|---|---|",
    ]
    for j, (name, _) in enumerate(DEFAULT_LFS):
        lines.append(f"| `{name}` | {coverage[j]:.0%} | {accuracies[j]:.0%} |")

    lines.extend([
        "",
        "> **覆蓋率**: 該 LF 不 abstain 的訊息比例; 太低 (< 5%) 代表 LF 太嚴; 太高 (> 80%) 代表 LF 太寬鬆",
        "> **準確度**: Dawid-Skene EM 估計的「對齊真實類別」機率, 反映該 LF 的可信度",
        "",
        "## 📊 訓練先驗 P(類別)",
        "",
        "| 類別 | π (prior) |",
        "|---|---|",
    ])
    for c, name in enumerate(CLASS_NAMES):
        lines.append(f"| {name} | {model.pi[c]:.1%} |")

    lines.append("")
    lines.append("## 🎯 待檢驗訊息")
    lines.append("")
    lines.append(f"> _{test_msg.get('_meta', '')}_")
    lines.append("")
    lines.append("```")
    lines.append(test_msg["text"])
    lines.append("```")
    lines.append("")

    lines.append("## 🔍 LF 對此訊息的判決")
    lines.append("")
    lines.append("| LF | 輸出 | 意義 |")
    lines.append("|---|---|---|")
    for j, (name, _) in enumerate(DEFAULT_LFS):
        L = test_lfs[j]
        if L == ABSTAIN:
            lines.append(f"| `{name}` | -- | (abstain) |")
        else:
            lines.append(f"| `{name}` | {L} | {CLASS_NAMES[L]} |")
    lines.append("")

    mv_class, mv_votes = majority_vote(test_lfs)
    lines.extend([
        "## 🗳️ Majority Vote (簡單基準)",
        "",
        f"**簡單票數**: {dict((CLASS_NAMES[c], v) for c, v in mv_votes.items())}",
        f"**贏家**: {CLASS_NAMES[mv_class]}",
        "",
        "## 🧠 Dawid-Skene EM 後驗",
        "",
        "| 類別 | 後驗 P(y \\| LF 輸出) |",
        "|---|---|",
    ])
    sorted_idx = sorted(range(N_CLASSES), key=lambda c: -pred["probs"][c])
    for c in sorted_idx:
        bar = "█" * int(pred["probs"][c] * 30)
        marker = "⭐" if c == pred["predicted_class"] else "  "
        lines.append(f"| {marker} {CLASS_NAMES[c]} | {pred['probs'][c]:.1%} `{bar}` |")

    winner = pred["predicted_class"]
    advice = CLASS_ADVICE.get(winner, {})
    lines.extend([
        "",
        f"## 🚨 對應建議 ({CLASS_NAMES[winner]})",
        "",
        f"- **緊急度**: {advice.get('urgency', '請判斷')}",
        f"- **個人應對**: {advice.get('action', '保守處理')}",
        f"- **通報管道**: {advice.get('report', '165 反詐騙專線')}",
        "",
        "## ⚠️ Weak Supervision 模型假設與限制",
        "",
        "- **LF 獨立性假設**: Dawid-Skene 假設「給定真實類別, LF 輸出彼此條件獨立」; 真實有相依 (LF1 LF8 都看 '%'), Pro 版用 Snorkel-style generative model with LF correlations",
        "- **LF 是手工規則**: 規則太嚴 → 覆蓋率低; 太寬 → 雜訊高;Pro 版加 ML LFs (BERT-classifier 當 LF 之一)",
        "- **訓練無標註**: Dawid-Skene 是 unsupervised, 完全依賴 LF 輸出投票 + EM 推估;若所有 LF 系統性錯誤, 整體就錯",
        "- **不含視覺資訊**: 真實詐騙圖片 / 假網址截圖, prototype 只看文字; Pro 版加 vision",
        "- **不含時序 / 帳號信譽**: 同一帳號連發 100 則, 純文字模型看不出; Pro 版加 sender history",
        "- **法律邊界**: 工具只給「值得警覺」分流, **最終判定 / 報警仍需 165 反詐騙專線 / 警政署**; 不取代專業",
        "- **隱私敏感**: 私訊內容可能涉個資, 本地版完全在用戶設備不上傳;雲端版需加密 + 用戶同意 + 訊息匿名化",
        "",
        "---",
        "*scampatrol = Ratner et al. 2016 Snorkel weak supervision + Dawid & Skene 1979 EM × LINE 詐騙偵測 niche = "
        "10 個手工 weak rules 投票 + EM 學每個 rule 的可信度 → 5 類詐騙分流 + 通報路徑, "
        "個人端工具補 165 反詐騙專線只能事後通報的缺口。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, model, training_msgs, test_msg, test_lfs, pred, coverage, accuracies):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, training_msgs, test_msg, test_lfs, pred, coverage, accuracies)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, training_msgs, test_msg, test_lfs, pred, coverage, accuracies)

    base = render_no_ai(data, model, training_msgs, test_msg, test_lfs, pred, coverage, accuracies)
    winner = pred["predicted_class"]
    winner_p = pred["probs"][winner]
    sorted_idx = sorted(range(N_CLASSES), key=lambda c: -pred["probs"][c])
    runner_up = sorted_idx[1] if len(sorted_idx) > 1 else None

    active_lfs = []
    for j, (name, _) in enumerate(DEFAULT_LFS):
        if test_lfs[j] != ABSTAIN:
            active_lfs.append(f"{name} → {CLASS_NAMES[test_lfs[j]]}")
    active_str = "; ".join(active_lfs) or "(全部 abstain)"

    prompt = f"""你是反詐騙志工 + 警政署 165 反詐騙專線資深接線員 (10+ 年). 下面是用 Snorkel-style weak supervision 純函式分析的結果:

訊息: 「{test_msg['text']}」

來自: {test_msg.get('_meta', '不明')}
分類結果: {CLASS_NAMES[winner]} (信心 {winner_p:.0%})
次高: {CLASS_NAMES[runner_up]} ({pred['probs'][runner_up]:.0%})
觸發的 LFs: {active_str}

請寫 250-330 字 給訊息接收者的「個人端應對 SOP」:
1. 一句解讀 (避免「weak supervision」「Dawid-Skene」「EM」這種詞): 為什麼這訊息可疑或安全
2. **3 個立刻 (5 分鐘內) 可做的具體 SOP** (封鎖 / 不點連結 / 反向驗證 / 截圖)
3. **如果已經點 / 已經輸入個資 / 已經匯款 -- 緊急止損步驟**
4. 1 個給家人朋友的衛教提醒 (e.g. 長輩特別容易中的話術 / 學生常見的陷阱)

**嚴格規則**:
- 不要重算 % / 信心, 引用 facts
- 不要套話 ("請小心" / "祝您平安")
- 不超過 330 字
- 不要 markdown 標題
- 強調「weak supervision 是分流參考, 真實判定請打 165」
- 若預測為合法 (class 0) 但有任何疑慮仍給「保守處理」建議

直接寫 SOP。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 165 反詐騙志工 SOP\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="scampatrol -- LINE 詐騙 weak supervision")
    p.add_argument("--data", default="samples/messages.json")
    p.add_argument("--n-iter", type=int, default=50)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))

    # 1. Apply LFs to ALL training messages (unsupervised: no label needed)
    training_texts = [m["text"] for m in data["training_messages"]]
    L_train = apply_lfs_batch(training_texts)

    # 2. Fit Dawid-Skene EM
    lf_names = [name for name, _ in DEFAULT_LFS]
    model = fit_dawid_skene(L_train, n_classes=N_CLASSES, lf_names=lf_names, n_iter=args.n_iter)

    # 3. Predict on test message
    test_msg = data["query"]
    test_lfs = apply_lfs(test_msg["text"])
    pred = predict_one(model, test_lfs)

    # 4. Diagnostics
    coverage = lf_coverage(L_train)
    accuracies = lf_estimated_accuracy(model)

    if args.no_ai:
        print(render_no_ai(data, model, data["training_messages"], test_msg, test_lfs, pred, coverage, accuracies))
    else:
        print(render_with_ai(data, model, data["training_messages"], test_msg, test_lfs, pred, coverage, accuracies))


if __name__ == "__main__":
    main()
