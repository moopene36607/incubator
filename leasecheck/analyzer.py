"""leasecheck — 純函式合約分析(no LLM, no I/O)。

責任:
  - keyword 比對:從 lease 文字中找出哪些 clauses 命中
  - 風險分數計算(純加總 severity_score,加上 red 條款數量加成)
  - 風險等級分檔(LOW / MEDIUM / HIGH / CRITICAL)
  - 將 LLM 結構化抽取結果交叉驗證 + 純函式重算分數

LLM 在 leasecheck.py 負責「從段落中精確抽出對應條款全文 + 寫談判建議」。
本檔案完全不碰 LLM。

關鍵守則:
  - 所有風險分數 100% 純函式;LLM 永不算分
  - keyword 比對是 fallback(no-AI 模式);AI 模式用 LLM 抽取的精確句子比對
  - 重複命中同一 clause code 不重複加分
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from clauses_db import CLAUSES, ClauseSpec, get_clause_by_code


# --- 風險分數門檻 ---
RISK_LOW_MAX = 15        # ≤ 15 = LOW
RISK_MEDIUM_MAX = 40     # ≤ 40 = MEDIUM
RISK_HIGH_MAX = 80       # ≤ 80 = HIGH
# > 80 = CRITICAL


@dataclass
class ClauseHit:
    """一條已命中的 clause(可能來自 keyword 或 LLM extraction)。"""
    code: str
    risk_level: str
    matched_text: str           # 從合約中抽出的具體文句
    matched_keywords: tuple[str, ...] = ()  # 命中的關鍵字(no-AI)
    source: str = "keyword"     # "keyword" | "llm"


@dataclass
class RiskAssessment:
    risk_score: int             # 0-100
    risk_level: str             # LOW / MEDIUM / HIGH / CRITICAL
    red_count: int
    yellow_count: int
    green_count: int
    summary: str


def _normalize(text: str) -> str:
    """移除中文字之間的空白(讓「7 日內遷離」匹配「7日內遷離」)。"""
    out: list[str] = []
    prev_is_zh = False
    for ch in text:
        is_space = ch in " \t"
        is_zh_or_digit = ("一" <= ch <= "鿿") or ch.isdigit() or ch in "壹貳參肆伍陸柒捌玖拾百千萬"
        if is_space and prev_is_zh:
            # peek next non-space char
            continue  # drop, will re-evaluate prev
        out.append(ch)
        prev_is_zh = is_zh_or_digit
    # second pass: drop space before zh/digit char
    text2 = "".join(out)
    return text2


def keyword_extract(lease_text: str) -> list[ClauseHit]:
    """no-AI 模式:keyword 命中 → 列為 hit。一條 clause 至少 1 個 keyword 命中即算 hit。

    僅作 fallback;真實合約多樣性高,**AI 模式會更準確**。
    """
    norm = _normalize(lease_text)
    hits: list[ClauseHit] = []
    seen_codes: set[str] = set()
    for spec in CLAUSES:
        matched = tuple(kw for kw in spec.keywords if kw in lease_text or kw in norm)
        if not matched:
            continue
        # 抽 matched_text:取第一個 keyword 周圍前後各 30 字
        kw0 = matched[0]
        idx = lease_text.find(kw0)
        start = max(0, idx - 30)
        end = min(len(lease_text), idx + len(kw0) + 30)
        snippet = lease_text[start:end].replace("\n", " ").strip()
        if spec.code in seen_codes:
            continue
        seen_codes.add(spec.code)
        hits.append(ClauseHit(
            code=spec.code,
            risk_level=spec.risk_level,
            matched_text=snippet,
            matched_keywords=matched,
            source="keyword",
        ))
    return hits


def assess_risk(hits: Iterable[ClauseHit]) -> RiskAssessment:
    """純函式風險評估。LLM 永不參與。

    分數計算:
      - 每個 unique hit 取對應 clause 的 severity_score 加總
      - red 條款額外 ×1.0;yellow ×1.0;green ×0(不扣分)
      - 風險等級依 RISK_*_MAX 切檔
    """
    seen: set[str] = set()
    score = 0
    red = yellow = green = 0
    for h in hits:
        if h.code in seen:
            continue
        seen.add(h.code)
        spec = get_clause_by_code(h.code)
        if spec is None:
            continue
        score += spec.severity_score
        if spec.risk_level == "red":
            red += 1
        elif spec.risk_level == "yellow":
            yellow += 1
        else:
            green += 1

    score = min(score, 100)  # cap

    if score <= RISK_LOW_MAX:
        level = "LOW"
        summary = "合約整體合理,無重大不利條款。"
    elif score <= RISK_MEDIUM_MAX:
        level = "MEDIUM"
        summary = "合約有少量需注意條款,建議談判 1-2 處後簽署。"
    elif score <= RISK_HIGH_MAX:
        level = "HIGH"
        summary = "合約存在多條紅色條款,**強烈建議**談判修改後再簽。"
    else:
        level = "CRITICAL"
        summary = "合約存在大量違法 / 嚴重不利條款,**不建議直接簽署**。建議要求房東依內政部範本重新草擬,或考慮放棄此租約。"

    return RiskAssessment(
        risk_score=score,
        risk_level=level,
        red_count=red,
        yellow_count=yellow,
        green_count=green,
        summary=summary,
    )


def merge_hits(keyword_hits: list[ClauseHit], llm_hits: list[ClauseHit]) -> list[ClauseHit]:
    """LLM hits 優先(精確抽句),keyword hits 補上 LLM 漏掉的。"""
    out: list[ClauseHit] = list(llm_hits)
    seen = {h.code for h in llm_hits}
    for h in keyword_hits:
        if h.code not in seen:
            out.append(h)
            seen.add(h.code)
    return out


def group_by_category(hits: list[ClauseHit]) -> dict[str, list[ClauseHit]]:
    out: dict[str, list[ClauseHit]] = {}
    for h in hits:
        spec = get_clause_by_code(h.code)
        if spec is None:
            continue
        out.setdefault(spec.category, []).append(h)
    return out
