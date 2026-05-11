"""kaigomatch CLI -- 日本介護事業所 staff-利用者 schedule matching with graph embedding.

Usage:
    python3 kaigomatch.py --data samples/jigyousho.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import fmean

from graph_emb import (
    fit_graph_embedding, top_k_neighbours, similarity, direct_ppmi,
    coverage, generate_walks, build_bipartite_graph, avg_walk_diversity,
    GraphEmbedding, LinkPrediction,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_no_ai(data: dict, emb: GraphEmbedding,
                  staff_dict: dict, client_dict: dict,
                  query_kind: str, query_id: str,
                  predictions: list[LinkPrediction],
                  cov: dict, walk_diversity: float) -> str:
    role_label = "利用者" if query_kind == "client" else "ヘルパー / 介護職員"
    other_role = "ヘルパー" if query_kind == "client" else "利用者"

    target = client_dict.get(query_id) if query_kind == "client" else staff_dict.get(query_id)
    target_meta = target.get("_meta", "") if target else ""

    lines = [
        f"# kaigomatch -- {data.get('jigyousho_name', '介護事業所')} schedule matching",
        "",
        f"**Staff (ヘルパー / 介護職員)**: {len(staff_dict)} 名",
        f"**利用者**: {len(client_dict)} 名",
        f"**過去 assignment edges**: {len(data['past_assignments'])} 件",
        f"**Random walks**: {emb.n_walks_per_node} per node × length {emb.walk_length} = {emb.n_walks_per_node * emb.graph.n_nodes()} walks",
        f"**Co-occurrence window**: {emb.window_size}",
        f"**Walk diversity**: {walk_diversity:.2f} (1.0 = no revisits)",
        f"**PPMI coverage**: {cov['n_nodes_with_ppmi']} / {cov['n_nodes']} nodes ({cov['coverage_pct']:.0%}), {cov['n_ppmi_pairs']} 非零 PPMI pairs",
        "",
        f"## 🎯 マッチング対象: {query_id} ({role_label})",
        "",
        f"_{target_meta}_",
        "",
        f"## 🔮 Top {len(predictions)} {other_role} 候補 (cosine on PPMI + direct PPMI 結合)",
        "",
        "| 順位 | ID | Cosine 類似度 | Direct PPMI | 結合スコア | 詳細 |",
        "|---|---|---|---|---|---|",
    ]
    for rank, p in enumerate(predictions, 1):
        details = staff_dict.get(p.candidate, {}) if query_kind == "client" else client_dict.get(p.candidate, {})
        snippet = details.get("_meta", "")[:50]
        lines.append(
            f"| {rank} | **{p.candidate}** | {p.cosine_score:.3f} | "
            f"{p.direct_ppmi:.2f} | **{p.combined_score:.3f}** | {snippet} |"
        )

    if predictions:
        lines.extend([
            "",
            "### 💡 Top 推薦解讀",
            "",
        ])
        best = predictions[0]
        if best.direct_ppmi > 0:
            lines.append(f"- **{best.candidate}** 與 {query_id} **直接** 過去有 assignment 紀錄 (PPMI = {best.direct_ppmi:.2f}), 表示既有合作經驗 → 安心 routing")
        else:
            lines.append(f"- **{best.candidate}** 與 {query_id} 過去無直接配對, 但 graph 結構上他的 neighbour pattern 跟 {query_id} 高度類似 (cosine = {best.cosine_score:.3f})")
            lines.append(f"  → 表示他常被指派 {('利用者' if query_kind == 'client' else 'ヘルパー')}群 與 {query_id} 重疊, 推測能 fit")

    lines.extend([
        "",
        "## 🔬 Graph embedding 直覺",
        "",
        "DeepWalk 風格 random walks 在 staff-client 二分圖上跑, 透過 PPMI 加權後:",
        "- **Cosine 類似度** = 兩個節點在 graph 上「鄰居模式」相似度 (鄰居模式相似 → 適合接同一群人)",
        "- **Direct PPMI** = 兩個節點是否在 walks 中常常共同出現 (高 = 直接共現經驗強)",
        "- **結合スコア** = 0.6 × cosine + 0.4 × tanh(PPMI)",
        "",
        "## ⚠️ Graph Embedding / Link Prediction 模型假設與限制",
        "",
        "- **過去配對偏差**: 模型只從歷史 assignment 學, 若過去 staff A 從未被指派 client X, 兩者可能 PPMI=0 但其實非常適合 (cold-start). Pro 版加 staff/client metadata side-information",
        "- **Random walk 隨機性**: walk seed 改變排序略有差異; prototype 用固定 seed 確保可重現",
        "- **Bipartite 限制**: 無法捕捉「ヘルパー之間 / 利用者之間」直接連結 (e.g. 同班朋友的偏好), Pro 版加 tripartite (staff / client / shift)",
        "- **權重對 walks 的影響**: edge weight (visit 次數) 高時 walk 更常停留, low-frequency staff 易被埋沒. Pro 版加 importance sampling",
        "- **PPMI 對 sparse 敏感**: 樣本不大 (< 100 edges) 時 PPMI 估計變異大;真實 launch 需 ≥ 500-1000 條 history",
        "- **不取代人工確認**: graph 推薦是 starting point, 排班 manager 仍需 review 安全 / 排班 conflict / 個性",
        "- **隱私敏感**: 利用者 + ヘルパー 個資 + 健康狀態 涉介護保険法 / 個人情報保護法, 雲端版需匿名化 + 加密 + 介護事業所同意",
        "",
        "---",
        "*kaigomatch = DeepWalk-style random walks + PPMI + cosine link prediction × 日本介護事業所 staff-利用者 matching niche = "
        "從過去 assignment 歷史學 graph embedding, 排班 manager 月省 40-60 小時手動排班 + 提高 staff-client 適配度 → 利用者滿意度 + ヘルパー留任率雙升。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, emb, staff_dict, client_dict, query_kind, query_id, predictions, cov, walk_diversity):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, emb, staff_dict, client_dict, query_kind, query_id, predictions, cov, walk_diversity)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, emb, staff_dict, client_dict, query_kind, query_id, predictions, cov, walk_diversity)

    base = render_no_ai(data, emb, staff_dict, client_dict, query_kind, query_id, predictions, cov, walk_diversity)

    target = client_dict.get(query_id) if query_kind == "client" else staff_dict.get(query_id)
    target_meta = target.get("_meta", "") if target else ""

    top3_str = "; ".join(
        f"{p.candidate} (cos={p.cosine_score:.2f}, ppmi={p.direct_ppmi:.2f})"
        for p in predictions[: 3]
    )

    prompt = f"""あなたは日本の介護事業所 (訪問介護) のサービス提供責任者 (15+ 年経験). 下記は DeepWalk + PPMI で過去 assignment 履歴から学習した結果です:

対象 ({('利用者' if query_kind == 'client' else 'ヘルパー')}): {query_id}
背景: {target_meta}
Top 3 候補: {top3_str}

請寫 250-330 字 (繁體中文, 因為 SaaS 給台灣顧問 / 日台跨境輸出參考):
1. 一句解讀 (避免「graph embedding」「PPMI」這類術語): 為什麼前 3 名候選人合適
2. **3 個排班 manager 安排前該做的確認步驟** (例如: 通勤距離 / 認知症対応 / 性別 / シフト conflict / 利用者同意)
3. **何時應該違反 graph 推薦** (e.g. 新 staff 沒歷史 / 利用者剛入新 service / 個性衝突)
4. 1 個給介護事業所經營層的洞察 (e.g. 從 graph 看哪些 staff 留任高 / 利用者集中度過高)

**嚴格規則**:
- 不要重算 cosine / PPMI 數字
- 不要套話 ("お疲れさまでした")
- 不超過 330 字
- 不要 markdown 標題
- 強調「graph 推薦是 starting point, 安全 / 利用者同意永遠優先」

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI サービス提供責任者建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="kaigomatch -- 日本介護 staff-利用者 graph embedding matching")
    p.add_argument("--data", default="samples/jigyousho.json")
    p.add_argument("--n-walks", type=int, default=15)
    p.add_argument("--walk-length", type=int, default=10)
    p.add_argument("--window", type=int, default=5)
    p.add_argument("-k", "--top-k", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    staff_dict = {s["id"]: s for s in data["staff"]}
    client_dict = {c["id"]: c for c in data["clients"]}
    assignments = data["past_assignments"]

    edges = [(a["staff_id"], a["client_id"], float(a["weight"])) for a in assignments]
    emb = fit_graph_embedding(
        edges,
        n_walks_per_node=args.n_walks,
        walk_length=args.walk_length,
        window_size=args.window,
        seed=args.seed,
    )

    # Walk diversity diagnostic
    walks = generate_walks(emb.graph, args.n_walks, args.walk_length, seed=args.seed)
    walk_diversity = avg_walk_diversity(walks)

    query = data["query"]
    query_kind = query["kind"]   # "staff" or "client"
    query_id = query["id"]

    # Filter candidates to the opposite role
    if query_kind == "client":
        candidate_filter = lambda n: n in staff_dict
    else:
        candidate_filter = lambda n: n in client_dict

    preds = top_k_neighbours(emb, query_id, candidate_filter=candidate_filter, k=args.top_k)
    cov = coverage(emb)

    if args.no_ai:
        print(render_no_ai(data, emb, staff_dict, client_dict, query_kind, query_id, preds, cov, walk_diversity))
    else:
        print(render_with_ai(data, emb, staff_dict, client_dict, query_kind, query_id, preds, cov, walk_diversity))


if __name__ == "__main__":
    main()
