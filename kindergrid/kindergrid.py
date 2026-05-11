"""kindergrid CLI — 家長挑幼兒園 Hierarchical Clustering 推薦工具。

Usage:
    python kindergrid.py --data samples/kindergartens.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from clustering import (
    hac_ward, cut_dendrogram, characterize_clusters, dbscan,
    recommend_from_clusters, euclidean, ClusterProfile,
    HACResult, DBSCANResult,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


FEATURE_DESC_ZH = {
    "tuition_NT_K": "學費 (K NTD/月)",
    "class_size": "班級人數",
    "english_pct": "英文比例 (%)",
    "outdoor_hr_per_day": "戶外時間 (小時/天)",
    "montessori_score": "蒙特梭利程度",
    "waldorf_score": "華德福程度",
    "exploration_score": "開放探索程度",
    "traditional_score": "傳統結構程度",
    "homework_load": "作業量",
    "parent_engage": "親師溝通頻率",
}


def render_no_ai(data: dict, hac_result: HACResult, profiles: list[ClusterProfile],
                  recommendation: tuple, db_result: DBSCANResult,
                  feature_names: list[str], n_clusters: int) -> str:
    schools = data["schools"]
    family = data["family_profile"]
    rec_cluster_id, top_recommendations = recommendation

    lines = [
        f"# kindergrid — {family['family_name']} 幼兒園挑選 Hierarchical Clustering 報告",
        "",
        f"**Marketplace**: {len(schools)} 家幼兒園 / 托嬰中心",
        f"**Features**: {len(feature_names)} 維 ({', '.join(FEATURE_DESC_ZH.get(f, f) for f in feature_names[:5])} ...)",
        f"**Hierarchical merges**: {len(hac_result.merge_history)} (Ward linkage)",
        f"**Cut to**: {n_clusters} clusters",
        "",
        "## 🎯 家長偏好",
        "",
        f"_{family.get('_meta', '')}_",
        "",
        "| 偏好 | 數值 |",
        "|---|---|",
    ]
    for fname in feature_names:
        v = family["preferences"][fname]
        lines.append(f"| {FEATURE_DESC_ZH.get(fname, fname)} | {v} |")

    lines.append("")
    lines.append(f"## 🏫 推薦 cluster: C{rec_cluster_id}")
    lines.append("")
    rec_profile = next((p for p in profiles if p.cluster_id == rec_cluster_id), None)
    if rec_profile:
        lines.append(f"**這個 cluster 的主導特徵**:")
        for fname, val in rec_profile.dominant_features:
            lines.append(f"- `{FEATURE_DESC_ZH.get(fname, fname)}`: {val:.2f}")
        lines.append("")

    lines.append(f"### Top {len(top_recommendations)} 推薦帶看清單 (cluster 內按距離排)")
    lines.append("")
    lines.append("| # | 學校 | 真實風格 (對比) | 距離家長偏好 |")
    lines.append("|---|---|---|---|")
    for i, (sidx, dist) in enumerate(top_recommendations):
        school = schools[sidx]
        lines.append(f"| {i + 1} | {school['name']} ({school['school_id']}) | {school['true_cluster']} | {dist:.2f} |")

    lines.append("")
    lines.append("## 📊 所有 cluster 摘要")
    lines.append("")
    lines.append("| Cluster | 規模 | 主導特徵 | 樣本學校 |")
    lines.append("|---|---|---|---|")
    for p in profiles:
        feats = ", ".join(f"`{f}` {v:.1f}" for f, v in p.dominant_features[:2])
        sample_names = ", ".join(schools[m]["true_cluster"] for m in p.members[:3])
        lines.append(f"| C{p.cluster_id} | {p.size} | {feats} | {sample_names} |")

    lines.append("")
    lines.append("## 🔍 DBSCAN 噪聲偵測 (找出風格 outlier)")
    lines.append("")
    lines.append(f"- DBSCAN with ε=12, min_pts=2 → **{db_result.n_clusters}** dense cluster + **{db_result.n_noise}** noise points")
    if db_result.n_noise > 0:
        noise_indices = [i for i, lbl in enumerate(db_result.labels) if lbl == -1]
        lines.append(f"- Noise / unique 學校 (跟主流不一樣):")
        for ni in noise_indices[:5]:
            lines.append(f"  - {schools[ni]['name']} ({schools[ni]['true_cluster']})")
        lines.append(f"- **Pro 用法**: noise points 是「特色園所」, 適合有特殊需求家庭 (e.g., 雙語+體育 / 蒙特梭利+早療)")

    lines.append("")
    lines.append("## 🌳 Dendrogram 高度視覺")
    lines.append("")
    lines.append("```")
    # Show last 10 merges as ASCII (relative bar by height)
    heights = [m.height for m in hac_result.merge_history[-15:]]
    max_h = max(heights) if heights else 1
    for m in hac_result.merge_history[-15:]:
        bar_len = int(40 * m.height / max_h)
        bar = "█" * bar_len
        lines.append(f"merge → C{m.new_cluster_id:3d} (n={m.n_members:2d}): h={m.height:8.1f} {bar}")
    lines.append("```")
    lines.append("- 高度跳躍處 (e.g., 從 h=1000 → h=18000) = 自然 cluster boundary")

    lines.append("")
    lines.append("## ⚠️ Hierarchical Clustering 模型假設與限制")
    lines.append("")
    lines.append("- **Ward linkage 假設特徵單位可比**: 學費 (千元) vs class_size (人) vs 分數 (0-10) 量級不同,Pro 版加 z-score 標準化")
    lines.append("- **n_clusters 是先驗**: prototype 設 5, Pro 版用 silhouette / elbow / gap statistic 自動選")
    lines.append("- **30 家 prototype 太小**: 真實 launch 需爬蟲 ≥ 500 家 + family-validated feature labels")
    lines.append("- **DBSCAN ε 是超參數**: 需要對 dataset 調 (12 = 1.2 std), Pro 版自動 k-distance 圖法找")
    lines.append("- **特徵 hand-crafted**: 蒙特梭利 / 華德福 程度由人工 annotate, 真實 launch 用 NLP 從學校描述自動抽取")
    lines.append("- **不取代實地參訪**: 推薦清單 = 帶看候選, 最後決策仍需家長自己感受教學環境 / 老師氣質")
    lines.append("")
    lines.append("---")
    lines.append("*kindergrid = Ward 1963 Hierarchical Clustering + Ester 1996 DBSCAN × 台灣 0-6 歲家長挑園 niche = 從 30 家自動分 5 教育理念 cluster + 對家長偏好推薦帶看清單。*")
    return "\n".join(lines)


def render_with_ai(data, hac_result, profiles, recommendation, db_result,
                    feature_names, n_clusters):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, hac_result, profiles, recommendation,
                             db_result, feature_names, n_clusters)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, hac_result, profiles, recommendation,
                             db_result, feature_names, n_clusters)

    base = render_no_ai(data, hac_result, profiles, recommendation,
                          db_result, feature_names, n_clusters)
    schools = data["schools"]
    family = data["family_profile"]
    rec_cid, top_recs = recommendation
    rec_profile = next((p for p in profiles if p.cluster_id == rec_cid), None)
    rec_feats = ", ".join(f"{f}: {v:.1f}" for f, v in (rec_profile.dominant_features if rec_profile else []))
    top_3_names = ", ".join(schools[i]["name"] for i, _ in top_recs[:3])

    prompt = f"""你是一位資深台灣兒童教育顧問。下面是用 Hierarchical Agglomerative Clustering 純函式分析的結果:

家長 {family['family_name']} 偏好: {family.get('_meta', '')}
推薦 cluster (5 群中): C{rec_cid} (主導特徵 {rec_feats})
Top 3 帶看候選: {top_3_names}
DBSCAN 找到 {db_result.n_noise} 個 outlier / 特色園所

請寫 250-330 字「給家長讀的帶看 checklist + 風險」:
1. 一句解讀:這個 cluster 適合你家的原因 (避免「Ward linkage」這種詞)
2. **3 個帶看時必問的問題** (具體, 不要泛泛 — 例如「英文老師是 native 還是台灣本地」「戶外時間下雨怎麼辦」「老師流動率多高」)
3. **2 個你的偏好沒被滿足、可能要妥協的點** (具體, e.g., 全美學費高、傳統作業多)
4. 1 個風險提醒 (e.g., 看 6 家就決定 / 老師流動 / 與孩子個性的契合)

**嚴格規則**:
- 不要重算 distance / centroid, 引用 facts
- 不要套話 ("加油", "祝順利")
- 不超過 330 字
- 不要 markdown 標題

直接寫帶看建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 兒童教育顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="kindergrid — 幼兒園 Hierarchical Clustering")
    p.add_argument("--data", default="samples/kindergartens.json")
    p.add_argument("--n-clusters", type=int, default=5)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--dbscan-eps", type=float, default=12.0)
    p.add_argument("--dbscan-min-pts", type=int, default=2)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    feature_names = data["feature_names"]
    schools = data["schools"]
    points = [[s["features"][f] for f in feature_names] for s in schools]

    hac_result = hac_ward(points)
    clusters = cut_dendrogram(hac_result, args.n_clusters)
    profiles = characterize_clusters(points, clusters, feature_names)

    fam_vector = [data["family_profile"]["preferences"][f] for f in feature_names]
    recommendation = recommend_from_clusters(fam_vector, points, clusters, top_n=args.top)

    db_result = dbscan(points, eps=args.dbscan_eps, min_pts=args.dbscan_min_pts)

    if args.no_ai:
        print(render_no_ai(data, hac_result, profiles, recommendation, db_result,
                             feature_names, args.n_clusters))
    else:
        print(render_with_ai(data, hac_result, profiles, recommendation, db_result,
                               feature_names, args.n_clusters))


if __name__ == "__main__":
    main()
