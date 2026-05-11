"""furnimatch CLI — 台灣二手家具 Item-Item Collaborative Filtering 媒合。

Usage:
    python furnimatch.py --marketplace samples/marketplace.json --profile samples/buyer.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from cf import (
    Item, User, Marketplace, QueryProfile, Recommendation,
    compute_item_similarities, recommend_for_profile, coverage_stats,
    item_popularity, style_based_fallback,
)


def load_marketplace(path: Path) -> Marketplace:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    valid_item_fields = set(Item.__dataclass_fields__.keys())
    items = [Item(**{k: v for k, v in d.items() if k in valid_item_fields})
             for d in data["items"]]
    users = [User(**d) for d in data["users"]]
    return Marketplace(items=items, users=users)


def load_buyer_profile(path: Path) -> QueryProfile:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    valid = set(QueryProfile.__dataclass_fields__.keys())
    return QueryProfile(**{k: v for k, v in data.items() if k in valid})


def render_no_ai(marketplace: Marketplace, profile: QueryProfile,
                  recs: list[Recommendation], sims_stats: dict) -> str:
    items_by_id = {it.item_id: it for it in marketplace.items}
    seed_names = []
    for fav_id in profile.seed_favorites:
        it = items_by_id.get(fav_id)
        if it:
            seed_names.append(f"{it.name} ({it.style_tag}, NT${it.price_ntd:,})")

    lines = [
        f"# furnimatch — {profile.user_name} 二手家具個人化推薦",
        "",
        f"**Marketplace**: {len(marketplace.items)} listings × {len(marketplace.users)} buyers favorite history",
        f"**Similarity 矩陣**: {sims_stats['n_similarity_pairs']} pairs ({100 - sims_stats['sparsity_pct']:.1f}% dense)",
        f"**Average user 收藏**: {sims_stats['avg_favs_per_user']} 件",
        "",
        "## 🎯 買家 profile",
        "",
        f"**已收藏 ({len(profile.seed_favorites)} 件)**:",
    ]
    for name in seed_names:
        lines.append(f"- 💛 {name}")
    lines.extend([
        "",
        f"**Hard filters**:",
        f"- 預算上限: NT${profile.budget_max_ntd:,}" if profile.budget_max_ntd else "- 預算: 無上限",
        f"- 地區: {', '.join(profile.location_filter) if profile.location_filter else '不限'}",
        f"- 類別: {', '.join(profile.category_filter) if profile.category_filter else '不限'}",
        f"- 偏好風格 (soft hint): {', '.join(profile.style_preference) if profile.style_preference else '無'}",
        "",
        f"## 🛋️ Top {len(recs)} 推薦 listings",
        "",
        "| # | 商品 | 風格 | 價格 | 地區 | 狀態 | CF score | 因為你愛 |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for i, r in enumerate(recs):
        top_contrib = ", ".join(n for n, s in r.contributing_favorites[:2])
        lines.append(
            f"| {i + 1} | {r.item.name} | {r.item.style_tag} | "
            f"NT${r.item.price_ntd:,} | {r.item.location} | {r.item.condition} | "
            f"**{r.score:.3f}** | {top_contrib} |"
        )

    lines.append("")
    lines.append("## 📊 推薦邏輯透明化 (純函式 cosine similarity)")
    lines.append("")
    if not recs:
        lines.append("⚠️ 沒有推薦 — 可能 seed 太少或 filter 太嚴格。建議放寬預算 / 地區 / 增加 seed favorites。")
    else:
        for i, r in enumerate(recs[:3]):
            lines.append(f"### #{i+1} {r.item.name} (CF score {r.score:.3f})")
            lines.append("")
            lines.append(f"**為什麼推薦這件**: 因為你已 favorite 的下列物件,其他買家也常 favorite 這件 →")
            for name, sim in r.contributing_favorites:
                lines.append(f"  - 「{name}」co-favorite 相似度 {sim:.3f}")
            lines.append("")

    lines.append("## 統計")
    lines.append("")
    pop = item_popularity(marketplace)
    sorted_pop = sorted(pop.items(), key=lambda x: -x[1])[:5]
    items_by_id_dict = {it.item_id: it.name for it in marketplace.items}
    lines.append("Top 5 最熱門 listings (整個 marketplace):")
    lines.append("")
    for iid, count in sorted_pop:
        lines.append(f"- {items_by_id_dict.get(iid, iid)}: {count} 人收藏")

    lines.append("")
    lines.append("## ⚠️ CF 模型假設與限制")
    lines.append("")
    lines.append("- **Cold start**: 新買家 < 3 個 seed favorites,CF score 不穩定;Pro 版加 content-based fallback (style 強制 + 圖片相似度)")
    lines.append("- **Popularity bias**: 熱門 listings 容易被推到所有買家面前,小眾 listings 看不見;Pro 版加 inverse-popularity weighting")
    lines.append("- **無語意理解**: CF 不知道「沙發跟茶几是搭配」,只看 user co-favorite 模式;與 content-based hybrid 較好")
    lines.append("- **二手家具特性**: 一件物品一個 owner,賣掉就消失,跟 Netflix/Amazon 不一樣;需要 churn-aware re-ranking")
    lines.append("- **小樣本**: < 50 users CF 不穩定;Pro 版要求 ≥ 200 active users")
    lines.append("")
    lines.append("---")
    lines.append("*furnimatch = Sarwar et al. 2001 Item-Item CF × 台灣二手家具 niche = 從 30 件 listings 給買家 top 8 個人化推薦 + 透明 why-recommended。*")
    return "\n".join(lines)


def render_with_ai(marketplace: Marketplace, profile: QueryProfile,
                    recs: list[Recommendation], sims_stats: dict) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(marketplace, profile, recs, sims_stats)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(marketplace, profile, recs, sims_stats)

    base = render_no_ai(marketplace, profile, recs, sims_stats)
    items_by_id = {it.item_id: it for it in marketplace.items}

    seed_summary = "\n".join(
        f"- {items_by_id[fid].name} ({items_by_id[fid].style_tag})"
        for fid in profile.seed_favorites if fid in items_by_id
    )

    top3_summary = "\n".join(
        f"- #{i+1} {r.item.name} (score {r.score}, {r.item.style_tag}, NT${r.item.price_ntd:,}, {r.item.location})"
        for i, r in enumerate(recs[:3])
    )

    prompt = f"""你是一位有家具品味的台灣居家風格顧問。下面是用 Item-Item Collaborative Filtering 純函式算出的推薦結果:

買家 {profile.user_name} 已收藏:
{seed_summary}
預算 NT${profile.budget_max_ntd:,} / 地區 {', '.join(profile.location_filter or ['不限'])}

CF 算出 Top 3 推薦:
{top3_summary}

請寫 200-280 字「個人化推薦理由 + 採買順序建議」:
1. **每件 1-2 句**: 這件為什麼適合(用「跟你愛的 X 是同 family」+「實用搭配」邏輯, 不要技術詞)
2. **採買順序**: 哪件先看、哪件可以再等(考慮搭配 / 議價空間 / 物流複雜度)
3. **1 個風險提醒**: 二手家具 試坐 / 議價 / 距離 / 物流費 / 品質檢查

**嚴格規則**:
- 不要重新算 score, 引用 facts
- 不要套話 ("加油")
- 不超過 280 字
- 不要 markdown 標題

直接寫推薦理由。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 居家風格顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="furnimatch — 二手家具 Item-Item CF 媒合")
    p.add_argument("--marketplace", default="samples/marketplace.json")
    p.add_argument("--profile", default="samples/buyer.json")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--metric", choices=["cosine", "jaccard"], default="cosine")
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    marketplace = load_marketplace(Path(args.marketplace))
    profile = load_buyer_profile(Path(args.profile))
    sims = compute_item_similarities(marketplace, metric=args.metric)
    recs = recommend_for_profile(marketplace, profile, sims, top_n=args.top)
    sims_stats = coverage_stats(marketplace, sims)

    if args.no_ai:
        print(render_no_ai(marketplace, profile, recs, sims_stats))
    else:
        print(render_with_ai(marketplace, profile, recs, sims_stats))


if __name__ == "__main__":
    main()
