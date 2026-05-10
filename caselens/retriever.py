"""caselens — 純函式案例檢索 + 賠償統計(no LLM, no I/O).

Stage 1 vector retrieval(keyword Jaccard 相似度;真實產品會用 sentence-transformers
或 BAAI/bge-zh embedding)。Stage 2 LLM re-rank 在 caselens.py。

100% stdlib(只用 set + statistics)。
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


# 中文法律 / 車禍關鍵字 token map(觸發 keyword extraction 時用)
# 每個關鍵字代表一個結構化特徵,實際 token 也會直接 fall-through 計算
LEGAL_KEYWORD_GROUPS = {
    # 車輛種類
    "汽車": ["汽車", "轎車", "小客車", "計程車", "貨車"],
    "機車": ["機車", "摩托車", "重機", "輕機"],

    # 違規類型
    "闖紅燈": ["闖紅燈", "紅燈"],
    "酒駕": ["酒駕", "酒測"],
    "逆向": ["逆向", "逆向行駛"],
    "未禮讓": ["未禮讓", "未讓"],
    "未打方向燈": ["未打方向燈", "未打燈"],
    "變換車道": ["變換車道", "切換車道"],
    "違規停車": ["違規停車", "違停", "違規停"],
    "緊急煞車": ["緊急煞車", "急煞"],
    "車速過快": ["車速過快", "超速", "速度過快"],
    "未保持安全距離": ["未保持安全距離", "安全距離"],
    "超車": ["超車", "右方超車"],
    "開門": ["開門", "開啟車門"],

    # 安全裝備
    "戴安全帽": ["戴安全帽", "有戴安全帽"],
    "未戴安全帽": ["未戴安全帽", "沒戴安全帽", "無戴安全帽"],

    # 路況
    "號誌路口": ["號誌", "紅綠燈", "路口"],
    "無號誌路口": ["無號誌", "沒有號誌"],
    "巷弄": ["巷弄", "巷子", "巷道"],
    "夜間": ["夜間", "晚上", "深夜"],

    # 衝撞型態
    "追撞": ["追撞", "從後方撞", "後方撞擊"],
    "對撞": ["對撞", "對向撞擊"],
    "擦撞": ["擦撞"],
    "左轉": ["左轉"],

    # 傷勢
    "骨折": ["骨折"],
    "粉碎性骨折": ["粉碎性骨折", "粉碎骨折"],
    "腦震盪": ["腦震盪"],
    "揮鞭症候群": ["揮鞭症候群", "頸部揮鞭"],
    "撕裂傷": ["撕裂傷", "裂傷"],
    "擦挫傷": ["擦挫傷", "擦傷"],
    "輕傷": ["輕傷"],
    "重傷": ["重傷"],
    "住院": ["住院"],
    "復健": ["復健"],
    "內出血": ["內出血"],

    # 賠償項目
    "醫療費": ["醫療費"],
    "工作損失": ["工作損失"],
    "精神慰撫金": ["精神慰撫金"],
    "車輛維修": ["車輛維修", "維修"],
    "看護費": ["看護費"],
}


@dataclass
class Candidate:
    """檢索候選案件 + 相似度分數。"""
    case: dict
    keyword_score: float
    matched_keywords: tuple[str, ...]
    rank: int = 0  # 0-indexed final rank after re-ranking


def extract_legal_keywords(text: str) -> set[str]:
    """從中文情境描述抽出法律關鍵字。

    用同義詞展開:若文中提到「沒戴安全帽」會匹配到關鍵字「未戴安全帽」。
    """
    out: set[str] = set()
    for canonical, synonyms in LEGAL_KEYWORD_GROUPS.items():
        if any(s in text for s in synonyms):
            out.add(canonical)
    return out


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard = |intersection| / |union|. 0..1。"""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def case_to_keyword_set(case: dict) -> set[str]:
    """從 case dict(summary + key_factors)抽出 keyword set。"""
    combined = case["summary"] + " " + " ".join(case.get("key_factors", []))
    return extract_legal_keywords(combined)


def find_top_k_candidates(query_keywords: set[str], cases: list[dict], k: int = 8) -> list[Candidate]:
    """純函式 Stage 1 檢索:keyword Jaccard 相似度排序 → top k。"""
    scored: list[Candidate] = []
    for case in cases:
        case_keywords = case_to_keyword_set(case)
        score = jaccard_similarity(query_keywords, case_keywords)
        if score > 0:
            scored.append(Candidate(
                case=case,
                keyword_score=round(score, 4),
                matched_keywords=tuple(sorted(query_keywords & case_keywords)),
            ))
    scored.sort(key=lambda c: -c.keyword_score)
    return scored[:k]


@dataclass
class CompensationStats:
    """從 top N 案件聚合的賠償統計(純函式,LLM 永不算)。"""
    n_cases: int
    min_amount: int
    median_amount: int
    max_amount: int
    avg_amount: int
    plaintiff_full_no_fault_count: int  # 原告 0% 過失的案件數
    plaintiff_partial_fault_count: int  # 原告有 1-49% 過失的案件數
    plaintiff_major_fault_count: int    # 原告 50%+ 過失的案件數
    responsibility_split_distribution: list[dict]  # 每個案件的 plaintiff/defendant %


def compute_compensation_stats(cases: list[dict]) -> CompensationStats:
    """純函式聚合 top-N 案件的賠償金額與責任比例。"""
    amounts = [c["compensation_amount"] for c in cases if c.get("compensation_amount") is not None]
    if not amounts:
        return CompensationStats(0, 0, 0, 0, 0, 0, 0, 0, [])

    splits = [c.get("responsibility_split", {}) for c in cases]
    plaintiff_fault = [s.get("plaintiff", 0) for s in splits]

    full = sum(1 for p in plaintiff_fault if p == 0)
    partial = sum(1 for p in plaintiff_fault if 0 < p < 50)
    major = sum(1 for p in plaintiff_fault if p >= 50)

    return CompensationStats(
        n_cases=len(amounts),
        min_amount=min(amounts),
        median_amount=int(statistics.median(amounts)),
        max_amount=max(amounts),
        avg_amount=int(statistics.mean(amounts)),
        plaintiff_full_no_fault_count=full,
        plaintiff_partial_fault_count=partial,
        plaintiff_major_fault_count=major,
        responsibility_split_distribution=splits,
    )
