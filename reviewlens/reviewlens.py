"""reviewlens CLI — 蝦皮 / 露天 / Yahoo 賣家商品評論 LDA 主題分析。

Usage:
    python reviewlens.py --seller samples/seller.json --no-ai
    python reviewlens.py --seller samples/seller.json --topics 6 --iterations 500
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from lda import (
    tokenize_chinese, fit_lda,
    top_words_per_topic, doc_topic_distribution, dominant_topic_per_doc,
    topic_concentration_per_group, topic_perplexity,
)


def load_seller(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_no_ai(data: dict, model, docs_ids: list[list[int]],
                  topic_words: list[list[tuple[str, float]]],
                  doc_topics: list[list[float]],
                  dom_topics: list[int],
                  group_conc: dict[str, list[float]],
                  K: int) -> str:
    reviews = data["reviews"]
    products = {p["product_id"]: p for p in data["products"]}
    perp = topic_perplexity(model, docs_ids)

    lines = [
        f"# reviewlens — {data['seller_name']} 商品評論 LDA 主題分析",
        "",
        f"**店鋪**: {data.get('shop_url', 'N/A')}",
        f"**月訂單**: {data.get('monthly_orders', 'N/A')}  ·  **評論總數**: {len(reviews)}",
        f"**商品數**: {len(products)}  ·  **主題數 K**: {K}",
        f"**LDA perplexity**: {perp:.1f} (越低越好)",
        "",
        "## 🎯 抽出的 K 個 latent topics",
        "",
        "| 主題 | Top 6 代表 bigram | 出現的評論數 |",
        "|---|---|---|",
    ]

    # Count docs dominated by each topic
    topic_doc_count = [0] * K
    for t in dom_topics:
        topic_doc_count[t] += 1

    for k in range(K):
        words_str = ", ".join(f"`{w}`" for w, p in topic_words[k][:6])
        lines.append(f"| **Topic {k}** | {words_str} | {topic_doc_count[k]} 條 |")

    lines.append("")
    lines.append("## 📊 各商品主題集中度 (θ̄ per product)")
    lines.append("")
    header = "| 商品 | 評論數 | 評分 | " + " | ".join(f"T{k}" for k in range(K)) + " |"
    sep = "|---|---|---|" + "|".join(["---"] * K) + "|"
    lines.append(header)
    lines.append(sep)

    # Compute per-product avg rating
    product_ratings = defaultdict(list)
    product_review_count = defaultdict(int)
    for r in reviews:
        product_ratings[r["product_id"]].append(r["rating"])
        product_review_count[r["product_id"]] += 1

    for pid, prod in products.items():
        avg_rating = sum(product_ratings[pid]) / len(product_ratings[pid]) if product_ratings[pid] else 0
        n = product_review_count[pid]
        theta = group_conc.get(pid, [0] * K)
        # Format: highlight top topic
        theta_strs = []
        max_k = max(range(K), key=lambda i: theta[i])
        for k in range(K):
            if k == max_k:
                theta_strs.append(f"**{theta[k]:.2f}**")
            else:
                theta_strs.append(f"{theta[k]:.2f}")
        lines.append(f"| {prod['name']} | {n} | {avg_rating:.1f}⭐ | " + " | ".join(theta_strs) + " |")

    lines.append("")
    lines.append("## 🔍 主題 → 痛點翻譯 (按 dominant topic 分組顯示樣本評論)")
    lines.append("")

    # Group reviews by dominant topic
    by_topic: dict[int, list[int]] = defaultdict(list)
    for i, t in enumerate(dom_topics):
        by_topic[t].append(i)

    for k in range(K):
        review_indices = by_topic.get(k, [])
        if not review_indices:
            continue
        # Identify likely theme from top words
        top_word_str = " / ".join(w for w, _ in topic_words[k][:4])
        lines.append(f"### Topic {k}: {top_word_str}")
        lines.append("")
        # Show up to 3 sample reviews
        for ri in review_indices[:3]:
            r = reviews[ri]
            pid = r["product_id"]
            prod_name = products.get(pid, {}).get("name", pid)
            lines.append(f"- ({prod_name}, {r['rating']}⭐) {r['text']}")
        lines.append("")

    lines.append("## 📉 哪些商品 × 哪個主題最痛 (低評分 + 高 topic 集中度)")
    lines.append("")
    lines.append("| 商品 | 平均評分 | 主導主題 | 主導 θ | 主題關鍵詞 |")
    lines.append("|---|---|---|---|---|")
    for pid, prod in products.items():
        avg_r = sum(product_ratings[pid]) / len(product_ratings[pid]) if product_ratings[pid] else 0
        theta = group_conc.get(pid, [0] * K)
        max_k = max(range(K), key=lambda i: theta[i])
        max_theta = theta[max_k]
        top_words = " / ".join(w for w, _ in topic_words[max_k][:3])
        pain_marker = "🔴" if avg_r < 3.0 else ("🟡" if avg_r < 4.0 else "🟢")
        lines.append(f"| {pain_marker} {prod['name']} | {avg_r:.1f}⭐ | T{max_k} | {max_theta:.2f} | {top_words} |")

    lines.append("")
    lines.append("## ⚠️ LDA 模型假設與限制")
    lines.append("")
    lines.append("- **K 必須預先指定** — K 太小主題糊在一起,K 太大主題會分裂;建議 5-12 之間")
    lines.append("- **bag-of-words 忽略順序** — 「不慢」「慢不慢」會被當同義,prototype 限制")
    lines.append("- **char-bigram tokenization** — 不用 jieba 適合 prototype,但語意精度低於分詞")
    lines.append("- **Gibbs sampling 有隨機性** — 同樣 seed → 同樣結果,但不同 seed 可能略不同")
    lines.append("- **小樣本 risk** — < 50 評論時主題會 overfit;Pro 版需要 ≥200 評論")
    lines.append("- **LDA 不告訴你嚴重程度** — 只告訴你「在抱怨什麼」,評分結合才知道哪個最痛")
    lines.append("")
    lines.append("---")
    lines.append("*reviewlens = Blei et al. 2003 LDA × 台灣電商賣家 niche = 從 200 條 review 自動找出 5-10 個痛點主題,而非逐條看到眼花。*")
    return "\n".join(lines)


def render_with_ai(data: dict, model, docs_ids, topic_words, doc_topics,
                    dom_topics, group_conc, K: int) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, docs_ids, topic_words, doc_topics, dom_topics, group_conc, K)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, docs_ids, topic_words, doc_topics, dom_topics, group_conc, K)

    base = render_no_ai(data, model, docs_ids, topic_words, doc_topics, dom_topics, group_conc, K)

    # Build per-product topic snapshot for the AI
    products = {p["product_id"]: p for p in data["products"]}
    product_ratings = defaultdict(list)
    for r in data["reviews"]:
        product_ratings[r["product_id"]].append(r["rating"])

    facts_lines = []
    for pid, prod in products.items():
        avg_r = sum(product_ratings[pid]) / len(product_ratings[pid])
        theta = group_conc.get(pid, [0] * K)
        max_k = max(range(K), key=lambda i: theta[i])
        top_words = " / ".join(w for w, _ in topic_words[max_k][:4])
        facts_lines.append(f"- {prod['name']}: avg {avg_r:.1f}⭐, 主導主題 T{max_k} ({top_words}, θ={theta[max_k]:.2f})")

    facts = "\n".join(facts_lines)
    all_topics = "\n".join(
        f"- T{k}: {', '.join(w for w, _ in topic_words[k][:6])}"
        for k in range(K)
    )

    prompt = f"""你是一位資深台灣電商營運顧問。下面是用 LDA (Latent Dirichlet Allocation) 純函式分析 {len(data['reviews'])} 條評論抽出的 K={K} 個主題 + 5 個商品的主導主題。

各 topic 代表詞 (按純函式 LDA 算出):
{all_topics}

各商品主導主題快照:
{facts}

請寫一段 250-350 字「給賣家讀的行動建議」:
1. **每個商品**寫 1-2 句:這個商品最大抱怨主題是什麼,具體 action 是什麼 (例如:換物流商 / 改包裝 / 改商品說明 / 換廠 / 訓練客服)
2. **整體 1-2 句**: 賣家 5 個商品共通問題是什麼 (有沒有跨商品出現的主題, 可能是賣家自己的問題)
3. **1 個風險提醒**: LDA 主題不代表嚴重度 / 樣本可能不足 / 個別評論需另外看

**嚴格規則**:
- 不要重新算數字, 引用上面 facts
- 不要套話 ("加油", "祝生意興隆")
- 不超過 350 字
- 不要用 markdown 標題或表格

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 電商營運顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="reviewlens — 電商評論 LDA 主題分析")
    p.add_argument("--seller", default="samples/seller.json")
    p.add_argument("--topics", type=int, default=6, help="K 主題數 (default 6)")
    p.add_argument("--iterations", type=int, default=300, help="Gibbs sampling iterations")
    p.add_argument("--alpha", type=float, default=0.5)
    p.add_argument("--beta", type=float, default=0.1)
    p.add_argument("--min-df", type=int, default=2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_seller(Path(args.seller))
    reviews = data["reviews"]
    texts = [r["text"] for r in reviews]
    group_labels = [r["product_id"] for r in reviews]

    corpus = [tokenize_chinese(t) for t in texts]
    model, docs_ids = fit_lda(
        corpus, K=args.topics, alpha=args.alpha, beta=args.beta,
        iterations=args.iterations, min_df=args.min_df, seed=args.seed,
    )
    topic_words = top_words_per_topic(model, n_top=8)
    doc_topics = doc_topic_distribution(model)
    dom_topics = dominant_topic_per_doc(model)
    group_conc = topic_concentration_per_group(model, group_labels)

    if args.no_ai:
        print(render_no_ai(data, model, docs_ids, topic_words, doc_topics, dom_topics, group_conc, args.topics))
    else:
        print(render_with_ai(data, model, docs_ids, topic_words, doc_topics, dom_topics, group_conc, args.topics))


if __name__ == "__main__":
    main()
