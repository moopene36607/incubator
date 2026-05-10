"""weddingmatch — 婚攝師配對演算法 (純函式).

核心:cosine similarity (婚攝師風格 vector vs 用戶需求 vector) +
價格區間過濾 + 地區過濾 + 排序。

LLM 永不參與排序計算 — 只負責「自由文字 → style vector」與「最終推薦理由
撰寫」。本檔案完全可單元測試,確保配對邏輯可重現。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from photographers_db import (
    PHOTOGRAPHERS,
    Photographer,
    STYLE_DIMENSIONS,
    STYLE_LABELS_ZH,
)


@dataclass
class UserQuery:
    style_vector: tuple[int, ...]    # 12 維,順序對應 STYLE_DIMENSIONS
    budget_min_twd: int | None = None
    budget_max_twd: int | None = None
    region_preference: str | None = None  # "北部" / "中部" / "南部" / "全台" / None
    free_text: str = ""


@dataclass
class MatchResult:
    photographer: Photographer
    similarity: float                # cosine [0, 1]
    overlap_tags: list[str]          # 用戶與婚攝共同 = 1 的 tag 中文名(供推薦理由)
    price_fit: str                   # "in_budget" | "stretches_budget" | "below_budget"
    region_fit: str                  # "matches" | "全台" | "different"


def cosine_similarity(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _price_fit(p: Photographer, query: UserQuery) -> str:
    if query.budget_max_twd is None:
        return "in_budget"
    if p.price_range_max_twd <= query.budget_max_twd:
        return "in_budget"
    if p.price_range_min_twd <= query.budget_max_twd:
        return "stretches_budget"
    return "below_budget"


def _region_fit(p: Photographer, query: UserQuery) -> str:
    if query.region_preference is None:
        return "matches"
    if p.region == "全台":
        return "全台"
    if p.region == query.region_preference:
        return "matches"
    return "different"


def _overlap_tags(p: Photographer, query: UserQuery) -> list[str]:
    return [
        STYLE_LABELS_ZH[dim]
        for dim, photo_v, user_v in zip(STYLE_DIMENSIONS, p.style_tags, query.style_vector)
        if photo_v == 1 and user_v == 1
    ]


def match(query: UserQuery, top_n: int = 5,
          photographers: list[Photographer] | None = None) -> list[MatchResult]:
    pool = photographers if photographers is not None else PHOTOGRAPHERS

    results: list[MatchResult] = []
    for p in pool:
        sim = cosine_similarity(p.style_tags, query.style_vector)
        if sim == 0:
            continue
        results.append(MatchResult(
            photographer=p,
            similarity=sim,
            overlap_tags=_overlap_tags(p, query),
            price_fit=_price_fit(p, query),
            region_fit=_region_fit(p, query),
        ))

    # 過濾:預算 below_budget 的剔除(代表婚攝最低價就高於用戶上限)
    if query.budget_max_twd is not None:
        results = [r for r in results if r.price_fit != "below_budget"]
    # 過濾:地區完全 different 的剔除(全台 + matches 保留)
    if query.region_preference is not None:
        results = [r for r in results if r.region_fit != "different"]

    # 排序:similarity 主、其次價格適配(in_budget > stretches),再 region(matches > 全台)
    fit_score = {"in_budget": 1.0, "stretches_budget": 0.7, "below_budget": 0.0}
    region_score = {"matches": 1.0, "全台": 0.85, "different": 0.0}
    results.sort(
        key=lambda r: (
            -r.similarity,
            -fit_score.get(r.price_fit, 0),
            -region_score.get(r.region_fit, 0),
        )
    )

    return results[:top_n]
