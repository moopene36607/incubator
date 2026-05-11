"""Embedding pre-filter — cosine similarity over OpenAI embeddings.

We embed each tender + each user profile once, then cosine-prefilter before
sending to the LLM. Below threshold → skip LLM (cheap miss). Above → send.
Keeps token cost at ~20% of naive "LLM-every-tender" baseline.
"""

from __future__ import annotations

import math
from typing import Sequence

from app.config import get_settings


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=get_settings().openai_api_key)
    return _client


def embed(text: str) -> list[float]:
    resp = _get_client().embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dim mismatch: len(a)={len(a)} vs len(b)={len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def should_send_to_llm(
    profile_emb: Sequence[float],
    tender_emb: Sequence[float],
    threshold: float | None = None,
) -> bool:
    if threshold is None:
        threshold = get_settings().semantic_sim_threshold
    return cosine(profile_emb, tender_emb) >= threshold
