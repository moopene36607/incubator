"""reviewlens — Latent Dirichlet Allocation via Collapsed Gibbs Sampling.

Pure-stdlib LDA (Blei et al. 2003, Griffiths & Steyvers 2004) for Chinese
e-commerce product reviews. No numpy / no jieba / no gensim.

Tokenization uses char-bigrams (works well for Chinese; no need for word
segmentation), with a hand-built stopword list (虛詞 / 標點 / 助詞).

Collapsed Gibbs sampling:
  P(z_i = k | z_{-i}, w) ∝ (n_dk + α) × (n_kw + β) / (n_k + V × β)

Outputs:
  - Topic-word distributions (top N words per topic)
  - Doc-topic distributions (review → topic mixture)
  - Per-product topic concentration (which products complain about what)

All math 100% stdlib (random + math + dataclass + collections).
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field


# ============== Chinese stopwords (handcrafted for review domain) ==============
CHINESE_STOPWORDS = set(
    "的了是我也都很在和就不要可以這個那因為所以但有沒會去過來"
    "對沒有但是然後又一直還是真的好棒讚耶啊喔嗯哈呢吧呀啦"
    "你妳他她它我們你們他們妳們大家自己這樣那樣怎麼為什麼"
    " ，。!?！?「」『』:、（）()【】[]…—-_"
)

# Whitespace and digits to ignore in bigrams
_IGNORE_CHARS = set(" \n\t\r0123456789")


def tokenize_chinese(text: str, min_token_freq: int = 1) -> list[str]:
    """Extract char-bigram tokens from Chinese text. Filters punctuation / digits."""
    # Strip punctuation by replacing with spaces
    cleaned = []
    for ch in text:
        if ch in _IGNORE_CHARS or ch in CHINESE_STOPWORDS:
            cleaned.append(" ")
        else:
            cleaned.append(ch)
    cleaned_str = "".join(cleaned)

    # Split on space to get character runs, then char-bigrams
    tokens = []
    for chunk in cleaned_str.split():
        if len(chunk) >= 2:
            for i in range(len(chunk) - 1):
                tokens.append(chunk[i:i + 2])
        elif len(chunk) == 1:
            # Keep single Chinese chars too
            tokens.append(chunk)
    return tokens


def build_vocabulary(corpus: list[list[str]], min_df: int = 2) -> tuple[dict[str, int], list[str]]:
    """Build word→id mapping. Filter tokens appearing in fewer than min_df docs."""
    df_counter: Counter[str] = Counter()
    for doc in corpus:
        for tok in set(doc):
            df_counter[tok] += 1
    vocab_list = [tok for tok, df in df_counter.items() if df >= min_df]
    vocab_list.sort()  # deterministic
    vocab = {tok: i for i, tok in enumerate(vocab_list)}
    return vocab, vocab_list


def docs_to_ids(corpus: list[list[str]], vocab: dict[str, int]) -> list[list[int]]:
    """Convert token list to integer IDs, dropping out-of-vocab tokens."""
    return [[vocab[t] for t in doc if t in vocab] for doc in corpus]


# ============== Collapsed Gibbs LDA ==============
@dataclass
class LDAModel:
    K: int                                  # number of topics
    V: int                                  # vocab size
    n_docs: int
    alpha: float
    beta: float
    n_dk: list[list[int]]                   # doc × topic counts
    n_kw: list[list[int]]                   # topic × word counts
    n_k: list[int]                          # topic totals
    n_d: list[int]                          # doc lengths
    z: list[list[int]]                      # topic assignment per word in each doc
    vocab_list: list[str] = field(default_factory=list)


def init_lda(docs: list[list[int]], K: int, V: int, alpha: float, beta: float,
              seed: int = 42, vocab_list: list[str] | None = None) -> LDAModel:
    """Random topic initialization."""
    rng = random.Random(seed)
    n_docs = len(docs)
    n_dk = [[0] * K for _ in range(n_docs)]
    n_kw = [[0] * V for _ in range(K)]
    n_k = [0] * K
    n_d = [len(doc) for doc in docs]
    z = []
    for d, doc in enumerate(docs):
        topics_d = []
        for w in doc:
            k = rng.randrange(K)
            topics_d.append(k)
            n_dk[d][k] += 1
            n_kw[k][w] += 1
            n_k[k] += 1
        z.append(topics_d)
    return LDAModel(
        K=K, V=V, n_docs=n_docs, alpha=alpha, beta=beta,
        n_dk=n_dk, n_kw=n_kw, n_k=n_k, n_d=n_d, z=z,
        vocab_list=vocab_list or [],
    )


def _sample_categorical(weights: list[float], rng: random.Random) -> int:
    """Multinomial sampling with raw (unnormalized) weights."""
    total = sum(weights)
    if total <= 0:
        return rng.randrange(len(weights))
    r = rng.uniform(0, total)
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if r <= acc:
            return i
    return len(weights) - 1


def gibbs_sweep(model: LDAModel, docs: list[list[int]], rng: random.Random) -> None:
    """One full Gibbs sweep over all word tokens."""
    K = model.K
    V = model.V
    alpha = model.alpha
    beta = model.beta
    Vbeta = V * beta

    for d, doc in enumerate(docs):
        for i, w in enumerate(doc):
            k_old = model.z[d][i]
            # Remove current assignment
            model.n_dk[d][k_old] -= 1
            model.n_kw[k_old][w] -= 1
            model.n_k[k_old] -= 1

            # Compute conditional posterior over all topics
            p = [0.0] * K
            for k in range(K):
                p[k] = ((model.n_dk[d][k] + alpha) *
                        (model.n_kw[k][w] + beta) /
                        (model.n_k[k] + Vbeta))

            k_new = _sample_categorical(p, rng)
            model.z[d][i] = k_new
            model.n_dk[d][k_new] += 1
            model.n_kw[k_new][w] += 1
            model.n_k[k_new] += 1


def fit_lda(corpus_tokens: list[list[str]], K: int = 8,
            alpha: float = 0.1, beta: float = 0.01,
            iterations: int = 200, min_df: int = 2,
            seed: int = 42) -> tuple[LDAModel, list[list[int]]]:
    """Full pipeline: tokenize → build vocab → init → run Gibbs → return model."""
    rng = random.Random(seed)
    vocab, vocab_list = build_vocabulary(corpus_tokens, min_df=min_df)
    docs = docs_to_ids(corpus_tokens, vocab)
    model = init_lda(docs, K=K, V=len(vocab), alpha=alpha, beta=beta,
                      seed=seed, vocab_list=vocab_list)
    for _ in range(iterations):
        gibbs_sweep(model, docs, rng)
    return model, docs


# ============== Post-processing ==============
def top_words_per_topic(model: LDAModel, n_top: int = 8) -> list[list[tuple[str, float]]]:
    """Return top-N words per topic with φ[k][w] probabilities."""
    Vbeta = model.V * model.beta
    out = []
    for k in range(model.K):
        # phi[k][w] = (n_kw[k][w] + beta) / (n_k[k] + V*beta)
        scores = []
        for w in range(model.V):
            phi = (model.n_kw[k][w] + model.beta) / (model.n_k[k] + Vbeta)
            scores.append((model.vocab_list[w], phi))
        scores.sort(key=lambda x: -x[1])
        out.append(scores[:n_top])
    return out


def doc_topic_distribution(model: LDAModel) -> list[list[float]]:
    """Return θ[d][k] for every doc."""
    Kalpha = model.K * model.alpha
    out = []
    for d in range(model.n_docs):
        theta_d = []
        denom = model.n_d[d] + Kalpha
        for k in range(model.K):
            theta_d.append((model.n_dk[d][k] + model.alpha) / denom)
        out.append(theta_d)
    return out


def dominant_topic_per_doc(model: LDAModel) -> list[int]:
    """For each doc, the topic with highest probability."""
    dist = doc_topic_distribution(model)
    return [max(range(model.K), key=lambda k: theta[k]) for theta in dist]


def topic_concentration_per_group(model: LDAModel, group_labels: list[str]) -> dict[str, list[float]]:
    """Aggregate topic probability per group (e.g., per product)."""
    dist = doc_topic_distribution(model)
    grouped: dict[str, list[list[float]]] = defaultdict(list)
    for d, label in enumerate(group_labels):
        grouped[label].append(dist[d])
    out = {}
    for label, theta_list in grouped.items():
        avg = [sum(theta[k] for theta in theta_list) / len(theta_list)
               for k in range(model.K)]
        out[label] = avg
    return out


def topic_perplexity(model: LDAModel, docs: list[list[int]]) -> float:
    """Held-out perplexity (lower = better fit)."""
    Vbeta = model.V * model.beta
    Kalpha = model.K * model.alpha
    log_likelihood = 0.0
    total_words = 0
    for d, doc in enumerate(docs):
        denom_theta = model.n_d[d] + Kalpha
        for w in doc:
            prob = 0.0
            for k in range(model.K):
                theta = (model.n_dk[d][k] + model.alpha) / denom_theta
                phi = (model.n_kw[k][w] + model.beta) / (model.n_k[k] + Vbeta)
                prob += theta * phi
            if prob > 0:
                log_likelihood += math.log(prob)
            total_words += 1
    if total_words == 0:
        return float("inf")
    return math.exp(-log_likelihood / total_words)
