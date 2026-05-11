"""topiclens CLI -- 國高中題庫學生答題 Spectral Clustering 找概念群.

Usage:
    python3 topiclens.py --data samples/exam_responses.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import fmean

from spectral import (
    build_coerror_affinity, spectral_cluster,
    cluster_members, cluster_centroid_topics, silhouette_score,
    SpectralResult,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_no_ai(data: dict, result: SpectralResult,
                  responses: dict, questions: list[dict],
                  members_by_cluster: dict, topics_per_cluster: dict,
                  silhouette: float) -> str:
    n_students = len(responses)
    n_questions = len(questions)

    # Aggregate per-question error rate
    wrong_counts = []
    for q in questions:
        wrong = sum(1 for s, r in responses.items() if r.get(q["id"], 1) == 0)
        wrong_counts.append((q, wrong))

    lines = [
        f"# topiclens -- {data['class_name']} 題庫 Spectral Clustering 概念群分析",
        "",
        f"**學生數**: {n_students}  /  **題目數**: {n_questions}  /  **K clusters**: {result.n_clusters}",
        f"**Affinity**: Jaccard(共錯學生集合); **Laplacian**: 對稱化 L_sym = I - D^(-1/2) W D^(-1/2)",
        f"**Eigendecomp**: Jacobi rotation 純函式;  **Embedding**: 取 top-{result.n_clusters} 特徵向量;  **k-means**: kmeans++ 5 restarts",
        f"**輪廓係數 (silhouette)**: {silhouette:.3f} (越大表示分群越乾淨, > 0.3 算可用)",
        "",
        "## 📊 整體答題正確率",
        "",
        f"**全班平均錯誤率**: {fmean(w for _, w in wrong_counts) / n_students:.1%}",
        "",
        "## 🎯 概念群集",
        "",
    ]

    for c in range(result.n_clusters):
        members = members_by_cluster.get(c, [])
        topics = topics_per_cluster.get(c, [])
        topic_str = ", ".join(f"{t} ({n})" for t, n in topics) if topics else "(no tag info)"

        # Avg wrong rate among cluster members
        cluster_wrongs = []
        for q in members:
            wrong = sum(1 for s, r in responses.items() if r.get(q["id"], 1) == 0)
            cluster_wrongs.append(wrong / n_students)
        avg_wrong = fmean(cluster_wrongs) if cluster_wrongs else 0.0

        lines.append(f"### Cluster {c} (n={len(members)} 題, 平均錯誤率 {avg_wrong:.1%})")
        lines.append("")
        lines.append(f"**主要 topic tags**: {topic_str}")
        lines.append("")
        lines.append("| 題號 | 題目 | 錯誤率 |")
        lines.append("|---|---|---|")
        for q in members[:10]:
            wrong = sum(1 for s, r in responses.items() if r.get(q["id"], 1) == 0)
            err = wrong / n_students
            stem = q.get("stem", "")[:80]
            lines.append(f"| Q{q['id']} | {stem} | {err:.0%} |")
        if len(members) > 10:
            lines.append(f"| ... | ... | (其他 {len(members) - 10} 題省略) |")
        lines.append("")

    # Per-student cluster mastery (top 3 students vs bottom 3)
    student_cluster_wrong: dict[str, dict[int, int]] = {}
    student_cluster_total: dict[str, dict[int, int]] = {}
    for s_id, r in responses.items():
        student_cluster_wrong[s_id] = {c: 0 for c in range(result.n_clusters)}
        student_cluster_total[s_id] = {c: 0 for c in range(result.n_clusters)}
        for i, q in enumerate(questions):
            c = result.labels[i]
            student_cluster_total[s_id][c] += 1
            if r.get(q["id"], 1) == 0:
                student_cluster_wrong[s_id][c] += 1

    lines.append("## 👨‍🎓 每位學生 × 概念群 錯誤率")
    lines.append("")
    header = "| 學生 | " + " | ".join(f"C{c}" for c in range(result.n_clusters)) + " | 整體 |"
    lines.append(header)
    sep = "|---|" + "---|" * (result.n_clusters + 1)
    lines.append(sep)
    sorted_students = sorted(responses.keys())
    for s_id in sorted_students:
        row = f"| {s_id} | "
        cells = []
        for c in range(result.n_clusters):
            tot = student_cluster_total[s_id][c]
            w = student_cluster_wrong[s_id][c]
            if tot == 0:
                cells.append("--")
            else:
                pct = w / tot
                cells.append(f"{pct:.0%}")
        # overall
        total_q = sum(student_cluster_total[s_id].values())
        total_w = sum(student_cluster_wrong[s_id].values())
        overall = total_w / total_q if total_q else 0
        row += " | ".join(cells)
        row += f" | {overall:.0%} |"
        lines.append(row)

    lines.extend([
        "",
        "## 🔍 補救教學優先順序 (錯誤率最高的 cluster)",
        "",
    ])
    cluster_avg_wrong = []
    for c in range(result.n_clusters):
        members = members_by_cluster.get(c, [])
        wrongs = []
        for q in members:
            w = sum(1 for s, r in responses.items() if r.get(q["id"], 1) == 0)
            wrongs.append(w / n_students)
        cluster_avg_wrong.append((c, fmean(wrongs) if wrongs else 0, topics_per_cluster.get(c, [])))
    cluster_avg_wrong.sort(key=lambda t: -t[1])

    for rank, (c, awr, topics) in enumerate(cluster_avg_wrong, 1):
        topic_str = ", ".join(t for t, _ in topics) or "(no tag)"
        lines.append(f"{rank}. **Cluster {c}**: 錯誤率 {awr:.1%} -- {topic_str}")
    lines.append("")

    lines.extend([
        "## ⚠️ Spectral Clustering 模型假設與限制",
        "",
        "- **共錯 ≠ 同概念**: 兩題都錯可能因「概念不熟」也可能「粗心 / 時間不夠 / 計算錯」;Pro 版加 IRT (Item Response Theory) latent 估計區分",
        "- **Jaccard 對 abstention 敏感**: 全班只 30 學生時, Jaccard 估計變異大;real launch 需 ≥ 200 學生答題 + 多次測驗",
        "- **k 需先指定**: 自動選 k 用 eigengap heuristic, prototype 預設 k=4; Pro 版加 eigengap + silhouette 自動選 k",
        "- **不含題目難度**: 過於簡單 / 過於困難題目錯誤率近 0% / 100%, Jaccard 失效, Pro 版加 IRT 難度過濾",
        "- **不取代教師判斷**: cluster 是統計分群, 真實「概念」歸屬還需出題老師 / 學科主任人工 review",
        "- **概念群名稱靠 LLM 解釋**: 純函式只給統計群集, 「這 cluster 是什麼概念」LLM 寫但**仍需老師覆核**",
        "- **隱私敏感**: 學生答題資料涉個資 + 教育記錄, 雲端版需匿名化 + 學校 / 家長同意 + 教育資料保護法合規",
        "",
        "---",
        "*topiclens = Shi-Malik 2000 / Ng-Jordan-Weiss 2002 Spectral Clustering × 國高中題庫 niche = "
        "從學生答題 co-error pattern 找出「題目-題目」社群, 給老師 / 補習班 / 家教 「補救教學優先順序」+ 「概念群 vs 個人弱點」分析, "
        "比 Excel 看錯題單獨統計多一個維度的洞察。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, result, responses, questions, members_by_cluster,
                    topics_per_cluster, silhouette):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, result, responses, questions, members_by_cluster, topics_per_cluster, silhouette)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, result, responses, questions, members_by_cluster, topics_per_cluster, silhouette)

    base = render_no_ai(data, result, responses, questions, members_by_cluster, topics_per_cluster, silhouette)

    cluster_summary = []
    for c in range(result.n_clusters):
        members = members_by_cluster.get(c, [])
        topics = topics_per_cluster.get(c, [])
        topic_str = ", ".join(f"{t}({n})" for t, n in topics)
        wrongs = []
        for q in members:
            w = sum(1 for s, r in responses.items() if r.get(q["id"], 1) == 0)
            wrongs.append(w / len(responses))
        avg = fmean(wrongs) if wrongs else 0
        cluster_summary.append(f"C{c} (n={len(members)} 題, 錯誤率 {avg:.0%}): {topic_str}")

    summary = " | ".join(cluster_summary)

    prompt = f"""你是台灣國高中資深數學 / 國文 / 英文老師 (15+ 年教學經驗 + 補救教學專家). 下面是用 Spectral Clustering 純函式分析的結果:

班級: {data['class_name']}
學生數: {len(responses)} / 題目數: {len(questions)}
分成 {result.n_clusters} 個概念群:
{summary}
輪廓係數 (cluster 乾淨度): {silhouette:.3f}

請寫 280-340 字「給導師 / 學科老師 / 家長 的兩週補救教學行動」:
1. 一句解讀 (避免「Spectral」「Laplacian」「eigendecomp」「Jaccard」這類術語): 哪些概念群最值得補強, 跟哪個 cluster 對應
2. **3 個本週可立刻做的補救教學 SOP** (e.g. 出題策略 / 學生分組 / 個別教練 / LINE 跟家長溝通)
3. **辨識「真正不會」vs「粗心 / 時間」的 2 個訊號** (考試 / 練習表現對比 / 課堂發問 / 訪談)
4. 1 個風險提醒 (e.g. 過度 label 學生 / 進度被群拖累 / 家長壓力)

**嚴格規則**:
- 不要重算 % / silhouette, 引用 facts
- 不要套話 ("辛苦了" / "加油")
- 不超過 340 字
- 不要 markdown 標題
- 強調「Spectral clustering 是統計分群輔助, 真正概念歸屬還需出題老師 review」

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 學科老師 補救教學建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="topiclens -- 題庫 Spectral Clustering")
    p.add_argument("--data", default="samples/exam_responses.json")
    p.add_argument("-k", "--n-clusters", type=int, default=4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    questions = data["questions"]
    # JSON object keys are always strings; coerce question-id keys back to int.
    responses = {
        s_id: {int(k): v for k, v in r.items()}
        for s_id, r in data["responses"].items()
    }

    question_ids = [q["id"] for q in questions]
    W = build_coerror_affinity(responses, question_ids)
    result = spectral_cluster(W, k=args.n_clusters, seed=args.seed)

    members_by_cluster = cluster_members(result.labels, questions, args.n_clusters)
    item_topics = [q.get("tags", []) for q in questions]
    topics_per_cluster = cluster_centroid_topics(result.labels, item_topics, args.n_clusters, top_n=3)
    silhouette = silhouette_score(result.embedding, result.labels)

    if args.no_ai:
        print(render_no_ai(data, result, responses, questions, members_by_cluster, topics_per_cluster, silhouette))
    else:
        print(render_with_ai(data, result, responses, questions, members_by_cluster, topics_per_cluster, silhouette))


if __name__ == "__main__":
    main()
