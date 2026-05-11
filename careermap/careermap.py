"""careermap CLI -- 台灣 高中 / 大學 畢業生 個人職涯方向 SOM 2D map.

Usage:
    python3 careermap.py --data samples/profiles.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import fmean

from som import (
    init_som, fit_som, assign_labels, quantisation_error, topographic_error,
    fit_minmax_scaler, apply_minmax, predict,
    SOM, PredictionResult,
)


CAREER_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "軟體工程師": {
        "core": "用程式解決問題, 寫 code 是日常",
        "growth_path": "Junior 軟工 → Senior 工程師 → Tech Lead → 架構師 / 技術 VP",
        "salary_range": "新鮮人 NT$45-75K / 中階 NT$80-150K / 資深 NT$150K+",
        "must_have_skills": "Python / Java / Go / 演算法 / 系統設計",
    },
    "行銷企劃": {
        "core": "理解市場、文案、活動策劃、品牌經營",
        "growth_path": "行銷專員 → 行銷主管 → 品牌經理 → CMO",
        "salary_range": "新鮮人 NT$32-45K / 中階 NT$50-90K / 資深 NT$100K+",
        "must_have_skills": "文案能力 / 數據分析 / 廣告投放 / 社群經營",
    },
    "業務銷售": {
        "core": "把產品賣出去, 業績是 KPI",
        "growth_path": "業務代表 → 業務經理 → 區域業務總監 → 業務 VP",
        "salary_range": "底薪 NT$30-40K + 提成 / 中階 月入 NT$80K-200K+",
        "must_have_skills": "口說表達 / 關係維繫 / 抗壓性 / 提案能力",
    },
    "設計師": {
        "core": "視覺 / 介面 / 體驗 設計, 平衡美感與功能",
        "growth_path": "UI Designer → Senior Designer → Design Lead → 設計總監",
        "salary_range": "新鮮人 NT$38-55K / 中階 NT$60-100K / 資深 NT$120K+",
        "must_have_skills": "Figma / Sketch / 視覺感 / 使用者研究",
    },
    "顧問": {
        "core": "深度分析 + 結構化建議 + 客戶溝通",
        "growth_path": "Analyst → Associate → Manager → Partner",
        "salary_range": "新鮮人 NT$50-80K / 中階 NT$100-180K / Partner NT$300K+",
        "must_have_skills": "邏輯 / 簡報 / 商業敏感度 / 英文",
    },
    "老師教育": {
        "core": "教學設計 + 學生互動, 影響下一代",
        "growth_path": "代課老師 → 正式教師 → 導師 → 主任 → 校長",
        "salary_range": "公立中小學 NT$45-70K (含加給) / 補習班 NT$50-150K",
        "must_have_skills": "教學熱忱 / 學科專業 / 班級經營 / 親師溝通",
    },
    "研究員": {
        "core": "深度探究問題, 產出論文 / 報告 / 專利",
        "growth_path": "研究助理 → Researcher → 資深研究員 → 首席科學家",
        "salary_range": "博士後 NT$60-90K / 中研院 / 工研院 NT$70-120K",
        "must_have_skills": "領域專業 / 論文寫作 / 統計 / 持續學習",
    },
    "創業家": {
        "core": "從 0 到 1 打造產品 / 公司, 高風險高報酬",
        "growth_path": "Side project → Solo founder → 共同創辦人 → CEO → exit",
        "salary_range": "前 3 年常常 NT$0-30K, 成功後上不封頂",
        "must_have_skills": "Generalist / 募資 / 領導 / 抗壓 / 商業敏感度",
    },
}


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_no_ai(data: dict, som: SOM, query_profile: dict, pred: PredictionResult,
                  feature_names: list[str], train_qe: float, train_te: float,
                  n_train: int) -> str:
    lines = [
        f"# careermap -- {data.get('cohort_name', '')} SOM 2D 職涯方向 map",
        "",
        f"**訓練 profile 數**: {n_train}",
        f"**SOM grid**: {som.grid_h} × {som.grid_w} 個 neurons",
        f"**Input dimension**: {som.input_dim} 個 features",
        f"**訓練 epochs**: {som.epochs_used}",
        f"**Quantisation error** (mean ||x - w_BMU||): {train_qe:.3f}",
        f"**Topographic error** (BMU 與第二近不相鄰比例): {train_te:.1%}",
        "",
        "## 🗺️ 2D 職涯方向 SOM map",
        "",
        "(每格顯示該 cell 在訓練中最常映射到的職涯類別; 空格表示沒訓練樣本對應)",
        "",
    ]

    # Build a label grid display
    cell_width = 6
    short = {
        "軟體工程師": "軟工",
        "行銷企劃": "行銷",
        "業務銷售": "業務",
        "設計師": "設計",
        "顧問": "顧問",
        "老師教育": "老師",
        "研究員": "研究",
        "創業家": "創業",
    }

    # Header column indices
    header = "    | " + " | ".join(f"{c:^4}" for c in range(som.grid_w)) + " |"
    sep = "----+" + "+".join("------" for _ in range(som.grid_w)) + "+"
    lines.append("```")
    lines.append(header)
    lines.append(sep)
    for r in range(som.grid_h):
        row_cells = []
        for c in range(som.grid_w):
            label = som.label_grid[r][c]
            row_cells.append(f"{short.get(label or '', '.'):^4}")
        lines.append(f" {r:>2} | " + " | ".join(row_cells) + " |")
    lines.append("```")
    lines.append("")

    # Query
    lines.extend([
        "## 🎯 個人 profile 查詢",
        "",
        f"_{data['query'].get('_meta', '')}_",
        "",
        "| Feature | 分數 (0-10) |",
        "|---|---|",
    ])
    for f in feature_names:
        v = query_profile.get(f, 0)
        bar = "█" * int(v) + "░" * (10 - int(v))
        lines.append(f"| {f} | `{bar}` {v} |")

    # If BMU is unlabeled, fall back to nearest labeled cell.
    final_label = pred.bmu_label or pred.best_labeled_label
    label_distance = pred.bmu_distance if pred.bmu_label else (pred.best_labeled_distance or pred.bmu_distance)
    label_cell = (pred.bmu_row, pred.bmu_col) if pred.bmu_label else (pred.best_labeled_row, pred.best_labeled_col)

    lines.extend([
        "",
        "## 💡 SOM 預測: 最適合的職涯方向",
        "",
        f"### ⭐ **預測 = {final_label or '(訓練樣本不足)'}** (cell [{label_cell[0]}][{label_cell[1]}], 距離 = {label_distance:.3f})",
        "",
    ])
    if not pred.bmu_label and pred.best_labeled_label:
        lines.append(f"> BMU 落在 cell [{pred.bmu_row}][{pred.bmu_col}] 沒有訓練樣本對應 (位於兩個職涯 zone 中間), 用「最近的有標籤 cell」作為推薦 — 這也是 SOM 的自然回退策略。")
        lines.append("")

    if final_label and final_label in CAREER_DESCRIPTIONS:
        d = CAREER_DESCRIPTIONS[final_label]
        lines.append(f"- **核心職能**: {d['core']}")
        lines.append(f"- **發展路徑**: {d['growth_path']}")
        lines.append(f"- **薪資區間**: {d['salary_range']}")
        lines.append(f"- **必備技能**: {d['must_have_skills']}")

    lines.append("")
    if pred.label_distribution:
        lines.append("**BMU cell 上的訓練樣本分布**:")
        for lab, n in sorted(pred.label_distribution.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {lab}: {n} 人")
        lines.append("")

    lines.append("## 🧭 鄰近 cells (相近但不同的選項)")
    lines.append("")
    lines.append("| 距離 | Cell 位置 | 主要標籤 |")
    lines.append("|---|---|---|")
    seen_labels = {pred.bmu_label}
    for r, c, lab, d in pred.nearby_cells[:6]:
        marker = " *新方向*" if lab and lab not in seen_labels else ""
        if lab:
            seen_labels.add(lab)
        lines.append(f"| {d:.3f} | [{r}][{c}] | {lab or '(未標籤)'}{marker} |")

    lines.extend([
        "",
        "## ⚠️ SOM 模型假設與限制",
        "",
        "- **2D 拓樸**: SOM 假設「相似 profile 距離近」是 2D 平面結構, 真實人格可能多維(SOM 強制壓平 → 邊界職涯可能不準)",
        "- **訓練樣本量**: prototype 用 80 個 profile, real launch 需 ≥ 500 個各職涯實際工作 1-3 年滿意人士的 profile",
        "- **Cold-start**: 新職涯類型 (e.g. AI 訓練師) 沒訓練樣本就找不到對應 cell, Pro 版需持續加新 profile",
        "- **Feature 主觀**: 12 個自評 score 受主觀影響, Pro 版加客觀指標 (學測級分 / 程式作業 / 實習評價)",
        "- **個性 ≠ 命運**: SOM 給「目前 profile 最像哪群人」, **不代表只能走那條路**;鄰近 cells 是合理的相近選項, 探索 mindset 比 dogmatic 更重要",
        "- **不取代深度諮詢**: 大型決定 (轉行 / 換系 / 出國) 仍需學校輔導室 / 職涯顧問 / 業界 mentor 一對一輔導",
        "- **隱私敏感**: 個人 profile 涉個資, 雲端版需匿名化 + 用戶同意 + 不販售給雇主",
        "",
        "---",
        "*careermap = Kohonen 1982 Self-Organizing Map × 台灣 高中 / 大學 畢業生 niche = "
        "把 12 維個性 / 技能 / 偏好向量投影到 2D 拓樸 map, 找到「跟你最像的人通常選什麼職涯」+ 鄰近 cells 提示相近選項, "
        "比 104 / 1111 / Cake 職位列表多一層個人化 + 比輔導室 1:200 比例可及性高。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, som, query_profile, pred, feature_names, train_qe, train_te, n_train):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, som, query_profile, pred, feature_names, train_qe, train_te, n_train)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, som, query_profile, pred, feature_names, train_qe, train_te, n_train)

    base = render_no_ai(data, som, query_profile, pred, feature_names, train_qe, train_te, n_train)

    top_features = sorted(query_profile.items(), key=lambda kv: -kv[1])[:3]
    feat_str = " / ".join(f"{k}={v}" for k, v in top_features)
    nearby_str = ", ".join(f"{lab}({d:.2f})" for _, _, lab, d in pred.nearby_cells[:3] if lab)

    prompt = f"""你是台灣大學 / 高中職涯輔導 + 業界 mentor (15+ 年, 帶過 500+ 學生 / 新鮮人轉職). 下面是用 Self-Organizing Map 純函式分析的結果:

詢問人: {data['query'].get('_meta', '')}
Top 3 自評 feature: {feat_str}
SOM 推薦最像的職涯: {pred.bmu_label} (BMU 距離 {pred.bmu_distance:.3f})
鄰近職涯: {nearby_str}

請寫 280-340 字「給應屆 / 在學生的職涯探索行動」:
1. 一句解讀 (避免「SOM」「BMU」「neuron」這類術語): 為什麼這個職涯適合, 為什麼鄰近的也值得探索
2. **3 個本月可做的具體探索動作** (例如:特定 podcast / book / side project / mentor 訪談 / 實習)
3. **辨識「我真的喜歡」vs「家人 / 朋友推薦」訊號** (sustained interest test)
4. 1 個風險提醒 (e.g. 起薪低但 5 年後高 / 起薪高但 burnout / 創業統計 / 證照)

**嚴格規則**:
- 不要重算距離 / 機率, 引用 facts
- 不要套話 ("加油" / "祝您找到好工作")
- 不超過 340 字
- 不要 markdown 標題
- 強調「SOM 是個性 mapping 輔助, 真實選擇仍需多次實習 + mentor 訪談」

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 職涯輔導 mentor 建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="careermap -- 個人職涯 SOM 2D map")
    p.add_argument("--data", default="samples/profiles.json")
    p.add_argument("--grid-h", type=int, default=8)
    p.add_argument("--grid-w", type=int, default=8)
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    feature_names = data["feature_names"]

    profiles = data["training_profiles"]
    X_raw = [[float(p["features"][f]) for f in feature_names] for p in profiles]
    y = [p["career"] for p in profiles]

    # Min-max scale to [0, 1] -- standard practice for SOMs.
    mins, maxs = fit_minmax_scaler(X_raw)
    X = apply_minmax(X_raw, mins, maxs)

    som = init_som(args.grid_h, args.grid_w, input_dim=len(feature_names), seed=args.seed)
    som.feature_names = feature_names
    som = fit_som(som, X, epochs=args.epochs, seed=args.seed)
    assign_labels(som, X, y)

    train_qe = quantisation_error(som, X)
    train_te = topographic_error(som, X)

    query_profile = data["query"]["features"]
    x_q_raw = [float(query_profile[f]) for f in feature_names]
    x_q = apply_minmax([x_q_raw], mins, maxs)[0]
    pred = predict(som, x_q)

    if args.no_ai:
        print(render_no_ai(data, som, query_profile, pred, feature_names, train_qe, train_te, len(profiles)))
    else:
        print(render_with_ai(data, som, query_profile, pred, feature_names, train_qe, train_te, len(profiles)))


if __name__ == "__main__":
    main()
