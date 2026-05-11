"""furnimatch — Item-Item Collaborative Filtering (pure stdlib).

Sarwar, Karypis, Konstan, Riedl (2001) "Item-based collaborative filtering
recommendation algorithms": for each pair of items (i, j), compute similarity
based on overlap of users who have favorited both. Then for a new user with
favorites F, score each candidate item k as Σ_{i in F} sim(i, k).

Pure stdlib (math + dataclass + collections). No numpy / no scipy.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field


# ============== Domain types ==============
@dataclass
class Item:
    item_id: str
    name: str
    price_ntd: int
    location: str            # 台北 / 新北 / 桃園 / ...
    category: str            # 沙發 / 餐桌 / 衣櫥 / ...
    style_tag: str           # 日系木質 / 北歐簡約 / ...
    condition: str = "GOOD"  # NEW / GOOD / FAIR / WORN


@dataclass
class User:
    user_id: str
    name: str
    favorite_item_ids: list[str]


@dataclass
class Marketplace:
    items: list[Item]
    users: list[User]


# ============== Similarity metrics ==============
def cosine_similarity_binary(set_a: set[str], set_b: set[str]) -> float:
    """Cosine similarity of two binary indicator vectors.
       sim = |A ∩ B| / sqrt(|A| × |B|)
    """
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    return intersection / math.sqrt(len(set_a) * len(set_b))


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard = |A ∩ B| / |A ∪ B|."""
    if not set_a and not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union > 0 else 0.0


# ============== Build sparse matrices ==============
def build_item_user_index(marketplace: Marketplace) -> dict[str, set[str]]:
    """For each item, the set of user_ids who favorited it."""
    out: dict[str, set[str]] = defaultdict(set)
    for u in marketplace.users:
        for item_id in u.favorite_item_ids:
            out[item_id].add(u.user_id)
    return dict(out)


def build_user_item_index(marketplace: Marketplace) -> dict[str, set[str]]:
    """For each user, the set of items they favorited."""
    return {u.user_id: set(u.favorite_item_ids) for u in marketplace.users}


# ============== Item-item similarity ==============
def compute_item_similarities(marketplace: Marketplace,
                                metric: str = "cosine") -> dict[tuple[str, str], float]:
    """Sparse item-item similarity dictionary keyed by (i, j) with i < j (lexically)."""
    item_user = build_item_user_index(marketplace)
    item_ids = sorted(item_user.keys())
    sims: dict[tuple[str, str], float] = {}
    sim_fn = cosine_similarity_binary if metric == "cosine" else jaccard_similarity

    for idx_i, i in enumerate(item_ids):
        for j in item_ids[idx_i + 1:]:
            s = sim_fn(item_user[i], item_user[j])
            if s > 0:
                sims[(i, j)] = s
    return sims


def get_similarity(sims: dict[tuple[str, str], float], a: str, b: str) -> float:
    """Lookup helper (symmetric)."""
    if a == b:
        return 1.0
    key = (a, b) if a < b else (b, a)
    return sims.get(key, 0.0)


# ============== Recommendation ==============
@dataclass
class Recommendation:
    item: Item
    score: float
    contributing_favorites: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class QueryProfile:
    """The buyer's profile for filtering + recommendations."""
    user_name: str
    seed_favorites: list[str]
    budget_max_ntd: int | None = None
    location_filter: list[str] | None = None     # e.g., ["台北", "新北"]
    category_filter: list[str] | None = None     # e.g., ["沙發", "餐桌"]
    style_preference: list[str] | None = None    # optional soft signal


def recommend_for_profile(marketplace: Marketplace, profile: QueryProfile,
                            sims: dict[tuple[str, str], float],
                            top_n: int = 10) -> list[Recommendation]:
    """Score candidate items via sum of similarities to user's seed favorites."""
    items_by_id = {it.item_id: it for it in marketplace.items}
    seed_set = set(profile.seed_favorites)

    candidates = []
    for it in marketplace.items:
        if it.item_id in seed_set:
            continue
        # Hard filters
        if profile.budget_max_ntd is not None and it.price_ntd > profile.budget_max_ntd:
            continue
        if profile.location_filter and it.location not in profile.location_filter:
            continue
        if profile.category_filter and it.category not in profile.category_filter:
            continue
        # Score by sum of similarities
        total_score = 0.0
        contributors = []
        for fav_id in profile.seed_favorites:
            s = get_similarity(sims, fav_id, it.item_id)
            if s > 0:
                total_score += s
                fav_item = items_by_id.get(fav_id)
                if fav_item:
                    contributors.append((fav_item.name, round(s, 3)))
        # Optional style preference bonus
        if profile.style_preference and it.style_tag in profile.style_preference:
            total_score += 0.05  # mild soft boost
        if total_score > 0:
            contributors.sort(key=lambda x: -x[1])
            candidates.append(Recommendation(
                item=it, score=round(total_score, 3),
                contributing_favorites=contributors[:3],
            ))

    candidates.sort(key=lambda r: -r.score)
    return candidates[:top_n]


# ============== Cold-start fallback ==============
def style_based_fallback(marketplace: Marketplace, profile: QueryProfile,
                          top_n: int = 5) -> list[Item]:
    """When user has no seed favorites OR CF returns nothing, fallback to style + hard filters."""
    candidates = []
    for it in marketplace.items:
        if profile.budget_max_ntd is not None and it.price_ntd > profile.budget_max_ntd:
            continue
        if profile.location_filter and it.location not in profile.location_filter:
            continue
        if profile.category_filter and it.category not in profile.category_filter:
            continue
        if profile.style_preference and it.style_tag in profile.style_preference:
            candidates.append(it)
    return candidates[:top_n]


# ============== Diagnostics ==============
def item_popularity(marketplace: Marketplace) -> dict[str, int]:
    """How many users favorited each item."""
    out = defaultdict(int)
    for u in marketplace.users:
        for item_id in u.favorite_item_ids:
            out[item_id] += 1
    return dict(out)


def coverage_stats(marketplace: Marketplace, sims: dict[tuple[str, str], float]) -> dict:
    """Sparsity / coverage of the similarity matrix."""
    n_items = len(marketplace.items)
    n_users = len(marketplace.users)
    total_favorites = sum(len(u.favorite_item_ids) for u in marketplace.users)
    avg_user_favs = total_favorites / n_users if n_users else 0
    max_pairs = n_items * (n_items - 1) // 2
    return {
        "n_items": n_items,
        "n_users": n_users,
        "total_favorites": total_favorites,
        "avg_favs_per_user": round(avg_user_favs, 2),
        "n_similarity_pairs": len(sims),
        "max_possible_pairs": max_pairs,
        "sparsity_pct": round((1 - len(sims) / max_pairs) * 100, 1) if max_pairs > 0 else 0,
    }
