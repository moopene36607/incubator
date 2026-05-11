"""lawmate — BM25 sparse retrieval for Chinese legal text(純函式 / no I/O / no LLM).

BM25 公式(Robertson & Spärck Jones 1976,Okapi BM25):
  score(q, d) = Σ_t∈q IDF(t) × tf(t, d) × (k1 + 1) / (tf(t, d) + k1 × (1 - b + b × |d| / avgdl))
  IDF(t) = log((N - df(t) + 0.5) / (df(t) + 0.5) + 1)

中文 tokenization:用 character bigrams(2 字滑窗)— 簡單且 stdlib-only,
不需 jieba。對短法律文字相當有效。

100% stdlib(math + dataclass + re)。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


# BM25 parameters
K1 = 1.5
B = 0.75


def tokenize(text: str) -> list[str]:
    """中文 character bigram tokenization。

    把連續中文字 / 數字 / 英文抽出來,然後 char-bigram(每 2 字一個 token)。
    保留單一英文 / 數字字詞作 fallback。
    """
    # 先把標點符號去除,把 text 切成 chunks(中英文混合處理)
    chunks = re.findall(r"[一-鿿]+|[A-Za-z0-9]+", text)
    tokens: list[str] = []
    for chunk in chunks:
        if re.match(r"[A-Za-z0-9]+", chunk):
            # 英文 / 數字直接當一個 token
            tokens.append(chunk.lower())
        else:
            # 中文 char-bigram
            if len(chunk) == 1:
                tokens.append(chunk)
            else:
                for i in range(len(chunk) - 1):
                    tokens.append(chunk[i:i + 2])
    return tokens


@dataclass
class BM25Index:
    n_docs: int
    avg_doc_length: float
    doc_lengths: list[int]
    inverted_index: dict[str, list[tuple[int, int]]]   # token -> [(doc_idx, term_freq)]
    df: dict[str, int]                                  # document frequency per token
    doc_ids: list[str]                                  # parallel to doc indices


def build_index(documents: list[tuple[str, str]]) -> BM25Index:
    """從 [(doc_id, text)] 建 BM25 index。"""
    doc_ids = [d[0] for d in documents]
    tokenized = [tokenize(d[1]) for d in documents]
    doc_lengths = [len(t) for t in tokenized]
    avg_len = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1.0

    inv_idx: dict[str, list[tuple[int, int]]] = {}
    df: dict[str, int] = {}
    for di, tokens in enumerate(tokenized):
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        for t, c in tf.items():
            inv_idx.setdefault(t, []).append((di, c))
            df[t] = df.get(t, 0) + 1

    return BM25Index(
        n_docs=len(documents),
        avg_doc_length=avg_len,
        doc_lengths=doc_lengths,
        inverted_index=inv_idx,
        df=df,
        doc_ids=doc_ids,
    )


def bm25_score(query: str, index: BM25Index) -> list[float]:
    """為每個 document 計算 BM25 score。"""
    q_tokens = tokenize(query)
    scores = [0.0] * index.n_docs
    for q in q_tokens:
        if q not in index.inverted_index:
            continue
        df_q = index.df[q]
        # IDF (BM25+ smoothed version)
        idf = math.log((index.n_docs - df_q + 0.5) / (df_q + 0.5) + 1)
        for di, tf in index.inverted_index[q]:
            doc_len = index.doc_lengths[di]
            denom = tf + K1 * (1 - B + B * doc_len / index.avg_doc_length)
            scores[di] += idf * (tf * (K1 + 1) / denom)
    return scores


@dataclass
class RetrievalResult:
    doc_id: str
    score: float
    rank: int


def top_k(query: str, index: BM25Index, k: int = 10) -> list[RetrievalResult]:
    """回傳 top-k 文件(by BM25 score)。"""
    scores = bm25_score(query, index)
    ranked = sorted(enumerate(scores), key=lambda x: -x[1])[:k]
    return [
        RetrievalResult(doc_id=index.doc_ids[di], score=round(s, 4), rank=rank)
        for rank, (di, s) in enumerate(ranked, 1) if s > 0
    ]


# ===== Index hit detail (for explanation) =====
@dataclass
class QueryTermHit:
    query_term: str                  # bigram token
    df: int                          # 多少文件包含
    idf: float                       # log((N-df+0.5)/(df+0.5)+1)
    matched_doc_ids: list[str]


def explain_query(query: str, index: BM25Index, top_n: int = 6) -> list[QueryTermHit]:
    """解釋 query 各 term 的 IDF / DF — 用於 debug + 顯示。"""
    q_tokens = tokenize(query)
    seen: set[str] = set()
    out: list[QueryTermHit] = []
    for q in q_tokens:
        if q in seen:
            continue
        seen.add(q)
        if q not in index.inverted_index:
            continue
        df_q = index.df[q]
        idf = math.log((index.n_docs - df_q + 0.5) / (df_q + 0.5) + 1)
        matched_dids = [index.doc_ids[di] for di, _ in index.inverted_index[q]]
        out.append(QueryTermHit(
            query_term=q,
            df=df_q,
            idf=round(idf, 4),
            matched_doc_ids=matched_dids,
        ))
    # 排序 by IDF descending(高 IDF = 更 discriminative)
    out.sort(key=lambda h: -h.idf)
    return out[:top_n]
