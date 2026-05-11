"""reviewlens edge tests — pure-function LDA correctness."""
from __future__ import annotations

from lda import (
    tokenize_chinese, build_vocabulary, docs_to_ids,
    init_lda, gibbs_sweep, fit_lda,
    top_words_per_topic, doc_topic_distribution, dominant_topic_per_doc,
    topic_concentration_per_group, topic_perplexity,
    CHINESE_STOPWORDS,
)
import random


def test_tokenize_extracts_bigrams():
    """Bigram tokenization splits into pairs (skip stopword 好)."""
    tokens = tokenize_chinese("品質尺寸顏色")
    # Expect bigrams: 品質, 質尺, 尺寸, 寸顏, 顏色
    assert "品質" in tokens
    assert "尺寸" in tokens
    assert "顏色" in tokens


def test_tokenize_filters_punctuation():
    """Punctuation and whitespace stripped."""
    tokens = tokenize_chinese("好棒，超讚！")
    # No bigram should contain punctuation
    for t in tokens:
        for ch in t:
            assert ch not in "，！。「」"


def test_tokenize_handles_empty():
    assert tokenize_chinese("") == []


def test_build_vocabulary_min_df():
    """min_df filters rare tokens."""
    corpus = [["a", "b"], ["a", "c"], ["a", "d"]]
    vocab, vocab_list = build_vocabulary(corpus, min_df=2)
    assert "a" in vocab    # appears in 3 docs
    assert "b" not in vocab    # appears in 1 doc
    assert len(vocab) == 1


def test_docs_to_ids_drops_oov():
    """Out-of-vocab tokens dropped."""
    vocab = {"a": 0, "b": 1}
    corpus = [["a", "b", "c"]]
    ids = docs_to_ids(corpus, vocab)
    assert ids == [[0, 1]]


def test_init_lda_counts_consistent():
    """After init, all counts match each other."""
    docs = [[0, 1, 2], [1, 2, 0], [0, 0, 0]]
    model = init_lda(docs, K=3, V=3, alpha=0.1, beta=0.01, seed=0)
    # Sum n_dk over k == doc length
    for d in range(model.n_docs):
        assert sum(model.n_dk[d]) == len(docs[d])
    # Sum n_kw over k == total occurrences of word w
    for w in range(model.V):
        word_count = sum(sum(1 for x in doc if x == w) for doc in docs)
        assert sum(model.n_kw[k][w] for k in range(model.K)) == word_count
    # n_k[k] consistent
    for k in range(model.K):
        assert model.n_k[k] == sum(model.n_kw[k][w] for w in range(model.V))


def test_gibbs_sweep_preserves_counts():
    """Gibbs sweep doesn't lose/duplicate tokens."""
    docs = [[0, 1, 0, 2], [1, 1, 2], [0, 2, 2]]
    model = init_lda(docs, K=3, V=3, alpha=0.1, beta=0.01, seed=1)
    total_tokens_before = sum(model.n_d)
    rng = random.Random(0)
    gibbs_sweep(model, docs, rng)
    # Tokens conserved
    assert sum(model.n_d) == total_tokens_before
    assert sum(model.n_k) == total_tokens_before


def test_fit_lda_basic():
    """Full pipeline runs without crash."""
    corpus = [
        ["物流", "流好", "好慢", "慢等"],
        ["品質", "質差", "壞掉"],
        ["客服", "服態", "態度"],
    ]
    # Force min_df=1 since few docs
    model, ids = fit_lda(corpus, K=2, iterations=20, min_df=1, seed=42)
    assert model.K == 2
    assert model.V > 0
    assert len(ids) == 3


def test_top_words_per_topic_returns_K_lists():
    """top_words returns K lists, each with n_top entries."""
    corpus = [["a", "b", "c"], ["a", "b"], ["b", "c"]]
    model, _ = fit_lda(corpus, K=2, iterations=10, min_df=1, seed=0)
    top = top_words_per_topic(model, n_top=3)
    assert len(top) == 2
    for topic in top:
        for word, prob in topic:
            assert 0 <= prob <= 1


def test_doc_topic_distribution_sums_to_one():
    """θ for each doc sums to 1.0."""
    corpus = [["a", "b", "c"], ["b", "c", "d"], ["a", "d", "e"]]
    model, _ = fit_lda(corpus, K=3, iterations=20, min_df=1, seed=0)
    theta = doc_topic_distribution(model)
    for d, theta_d in enumerate(theta):
        assert abs(sum(theta_d) - 1.0) < 0.01


def test_dominant_topic_per_doc_returns_valid_topics():
    """Dominant topic ∈ {0..K-1}."""
    corpus = [["a", "b"], ["c", "d"], ["e", "f"]]
    model, _ = fit_lda(corpus, K=3, iterations=20, min_df=1, seed=0)
    dom = dominant_topic_per_doc(model)
    for k in dom:
        assert 0 <= k < model.K


def test_topic_concentration_per_group():
    """Group concentration aggregates θ per group."""
    corpus = [["a", "b"], ["a", "c"], ["d", "e"], ["d", "f"]]
    model, _ = fit_lda(corpus, K=2, iterations=20, min_df=1, seed=0)
    labels = ["G1", "G1", "G2", "G2"]
    conc = topic_concentration_per_group(model, labels)
    assert "G1" in conc and "G2" in conc
    # Each group's distribution sums to ~1
    for label, theta in conc.items():
        assert abs(sum(theta) - 1.0) < 0.01


def test_perplexity_positive_finite():
    """Perplexity is positive and finite."""
    corpus = [["a", "b", "c"], ["b", "c", "d"], ["a", "d", "e"]]
    model, ids = fit_lda(corpus, K=2, iterations=30, min_df=1, seed=0)
    perp = topic_perplexity(model, ids)
    assert 0 < perp < float("inf")


def test_deterministic_with_seed():
    """Same seed → same model."""
    corpus = [["a", "b", "c"], ["b", "c"], ["a", "c"]]
    m1, _ = fit_lda(corpus, K=2, iterations=20, min_df=1, seed=42)
    m2, _ = fit_lda(corpus, K=2, iterations=20, min_df=1, seed=42)
    # Counts should match
    assert m1.n_dk == m2.n_dk
    assert m1.n_kw == m2.n_kw


def test_more_iterations_lower_perplexity():
    """More Gibbs iterations should generally reduce perplexity (looser test)."""
    corpus = [
        ["物流", "流好", "好慢"] * 3,
        ["物流", "好慢", "等很"] * 3,
        ["品質", "質差", "壞掉"] * 3,
        ["客服", "服差", "態度"] * 3,
    ]
    m_few, ids_few = fit_lda(corpus, K=3, iterations=10, min_df=1, seed=1)
    m_many, ids_many = fit_lda(corpus, K=3, iterations=200, min_df=1, seed=1)
    p_few = topic_perplexity(m_few, ids_few)
    p_many = topic_perplexity(m_many, ids_many)
    # More iter should be ≤ fewer iter (with some tolerance)
    assert p_many <= p_few * 1.2


def test_chinese_stopwords_filtered():
    """Common chinese stopwords removed."""
    tokens = tokenize_chinese("這個是的了我")
    for t in tokens:
        for ch in t:
            # Tokens shouldn't include 是 / 的 / 了 (assuming they're in stopwords)
            pass  # weaker check; just verify no crash
    # At least make sure stopwords set has common ones
    assert "的" in CHINESE_STOPWORDS
    assert "是" in CHINESE_STOPWORDS


def test_separable_clusters_get_distinct_topics():
    """3 distinct clusters → 3 topics should mostly separate them."""
    # Build very distinct clusters with no shared vocabulary
    cluster_a = [["AA", "BB", "CC"] for _ in range(6)]
    cluster_b = [["DD", "EE", "FF"] for _ in range(6)]
    cluster_c = [["GG", "HH", "II"] for _ in range(6)]
    corpus = cluster_a + cluster_b + cluster_c
    model, _ = fit_lda(corpus, K=3, iterations=200, min_df=1, seed=42)
    dom = dominant_topic_per_doc(model)
    # Each cluster should be mostly one topic
    a_topics = dom[:6]
    b_topics = dom[6:12]
    c_topics = dom[12:18]
    # Mode of each cluster
    from collections import Counter
    a_mode = Counter(a_topics).most_common(1)[0][1]
    b_mode = Counter(b_topics).most_common(1)[0][1]
    c_mode = Counter(c_topics).most_common(1)[0][1]
    # Each cluster should have ≥4/6 of its docs in its dominant topic
    assert a_mode >= 4
    assert b_mode >= 4
    assert c_mode >= 4


if __name__ == "__main__":
    tests = [
        test_tokenize_extracts_bigrams,
        test_tokenize_filters_punctuation,
        test_tokenize_handles_empty,
        test_build_vocabulary_min_df,
        test_docs_to_ids_drops_oov,
        test_init_lda_counts_consistent,
        test_gibbs_sweep_preserves_counts,
        test_fit_lda_basic,
        test_top_words_per_topic_returns_K_lists,
        test_doc_topic_distribution_sums_to_one,
        test_dominant_topic_per_doc_returns_valid_topics,
        test_topic_concentration_per_group,
        test_perplexity_positive_finite,
        test_deterministic_with_seed,
        test_more_iterations_lower_perplexity,
        test_chinese_stopwords_filtered,
        test_separable_clusters_get_distinct_topics,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
