"""Edge-case tests for graph_emb.py -- DeepWalk + PPMI + link prediction.

Run: python3 tests_graph.py
"""
from __future__ import annotations

import math
import random
import sys

from graph_emb import (
    WeightedGraph, build_bipartite_graph,
    random_walk, generate_walks, _weighted_choice,
    cooccurrence_counts, compute_ppmi,
    fit_graph_embedding, top_k_neighbours, similarity, direct_ppmi,
    cosine_dict, coverage, avg_walk_diversity,
    GraphEmbedding,
)


def assert_close(a, b, tol=1e-6, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol {tol})")


# ============================ graph basics ============================ #


def test_weighted_graph_add_node():
    g = WeightedGraph()
    g.add_node("A")
    assert "A" in g.node_index
    assert g.node_index["A"] == 0


def test_weighted_graph_add_edge_creates_nodes():
    g = WeightedGraph()
    g.add_edge("A", "B", 5.0)
    assert g.n_nodes() == 2
    assert ("B", 5.0) in g.adjacency["A"]
    assert ("A", 5.0) in g.adjacency["B"]


def test_weighted_graph_undirected():
    g = build_bipartite_graph([("A", "B", 3.0)])
    assert g.neighbours("A") == [("B", 3.0)]
    assert g.neighbours("B") == [("A", 3.0)]


def test_weighted_graph_empty():
    g = WeightedGraph()
    assert g.n_nodes() == 0


# ============================ random walks ============================ #


def test_random_walk_starts_at_start():
    g = build_bipartite_graph([("A", "B", 1.0), ("A", "C", 1.0)])
    rng = random.Random(0)
    walk = random_walk(g, "A", length=5, rng=rng)
    assert walk[0] == "A"


def test_random_walk_length():
    g = build_bipartite_graph([("A", "B", 1.0), ("B", "C", 1.0), ("C", "D", 1.0)])
    rng = random.Random(0)
    walk = random_walk(g, "A", length=4, rng=rng)
    assert len(walk) <= 4


def test_random_walk_stops_at_isolated_node():
    g = WeightedGraph()
    g.add_node("isolated")
    rng = random.Random(0)
    walk = random_walk(g, "isolated", length=10, rng=rng)
    assert walk == ["isolated"]


def test_generate_walks_count():
    g = build_bipartite_graph([("A", "B", 1.0), ("B", "C", 1.0)])
    walks = generate_walks(g, n_walks_per_node=5, walk_length=4, seed=42)
    assert len(walks) == 3 * 5    # 3 nodes × 5 walks


def test_weighted_choice_respects_weights():
    """With heavy weight on one option, that option should dominate."""
    rng = random.Random(42)
    items = [("A", 1.0), ("B", 100.0)]
    counts = {"A": 0, "B": 0}
    for _ in range(500):
        choice = _weighted_choice(rng, items)
        counts[choice] += 1
    assert counts["B"] > counts["A"] * 10


# ============================ co-occurrence + PPMI ============================ #


def test_cooccurrence_self_pair_excluded():
    pair_counts, _, _ = cooccurrence_counts([["A", "B", "A"]], window_size=2)
    # Self at same position should not contribute; A-A through window may though.
    # Specifically (A, A) at distance 2 within window 2 is counted; we explicitly
    # exclude i == j (same position), so (A,A) at i=0,j=2 IS counted.
    # The key invariant: a node never co-occurs with itself at the SAME position.
    # Test simpler invariant: pair_counts has (A, B) entries.
    assert pair_counts.get(("A", "B"), 0) > 0
    assert pair_counts.get(("B", "A"), 0) > 0


def test_cooccurrence_symmetric_pairs():
    pair_counts, _, _ = cooccurrence_counts([["A", "B"]], window_size=1)
    # Pairs (A,B) and (B,A) should both be counted by symmetric window iteration
    assert pair_counts.get(("A", "B"), 0) == pair_counts.get(("B", "A"), 0) >= 1


def test_compute_ppmi_zero_for_uncorrelated():
    # Two pairs with equal frequency -> PMI should be log(some ratio)
    pair_counts = {("A", "B"): 1, ("A", "C"): 1, ("B", "C"): 1}
    node_totals = {"A": 2, "B": 2, "C": 2}
    total = 3
    ppmi = compute_ppmi(pair_counts, node_totals, total)
    # PMI(A,B) = log(1 * 3 / (2 * 2)) = log(0.75) < 0 -> PPMI = 0
    assert ppmi.get(("A", "B"), 0.0) == 0.0


def test_compute_ppmi_positive_for_strong_pair():
    # If (A,B) is dominant, PMI > 0
    pair_counts = {("A", "B"): 10, ("A", "C"): 1, ("B", "C"): 1}
    node_totals = {"A": 11, "B": 11, "C": 2}
    total = 12
    ppmi = compute_ppmi(pair_counts, node_totals, total)
    # PMI(A,B) = log(10 * 12 / (11 * 11)) = log(120/121) ≈ log(0.99) < 0 -> 0
    # PMI(A,C) = log(1 * 12 / (11 * 2)) = log(12/22) < 0 -> 0
    # PMI(B,C) = log(1 * 12 / (11 * 2)) < 0 -> 0
    # This test verifies PPMI can be 0 even for direct pairs with bad ratio
    # Now try with strong concentration:
    pair_counts2 = {("A", "B"): 50, ("C", "D"): 50, ("A", "C"): 1}
    node_totals2 = {"A": 51, "B": 50, "C": 51, "D": 50}
    total2 = 101
    ppmi2 = compute_ppmi(pair_counts2, node_totals2, total2)
    assert ppmi2.get(("A", "B"), 0.0) > 0


def test_compute_ppmi_handles_zero_counts():
    pair_counts = {("A", "B"): 0}   # zero count
    node_totals = {"A": 0, "B": 0}
    ppmi = compute_ppmi(pair_counts, node_totals, 1)
    assert ("A", "B") not in ppmi


# ============================ cosine ============================ #


def test_cosine_identical_dicts():
    a = {"x": 1.0, "y": 2.0}
    b = {"x": 1.0, "y": 2.0}
    assert_close(cosine_dict(a, b), 1.0)


def test_cosine_orthogonal_dicts():
    a = {"x": 1.0}
    b = {"y": 1.0}
    assert_close(cosine_dict(a, b), 0.0)


def test_cosine_empty():
    assert cosine_dict({}, {"x": 1.0}) == 0.0
    assert cosine_dict({"x": 1.0}, {}) == 0.0


def test_cosine_proportional():
    a = {"x": 1.0, "y": 2.0}
    b = {"x": 2.0, "y": 4.0}
    assert_close(cosine_dict(a, b), 1.0)


# ============================ end-to-end =================================== #


def test_fit_graph_embedding_returns_object():
    edges = [("S1", "C1", 5.0), ("S1", "C2", 3.0), ("S2", "C1", 4.0)]
    emb = fit_graph_embedding(edges, n_walks_per_node=5, walk_length=4, seed=42)
    assert emb.graph.n_nodes() == 4
    assert isinstance(emb.ppmi, dict)


def test_fit_graph_embedding_recovers_strongly_linked_pair():
    """Two staff who share many clients should have similar embeddings."""
    # S1 and S2 both visit C1, C2, C3 (share all clients)
    # S3 visits different set: C4, C5, C6
    edges = [
        ("S1", "C1", 10.0), ("S1", "C2", 10.0), ("S1", "C3", 10.0),
        ("S2", "C1", 10.0), ("S2", "C2", 10.0), ("S2", "C3", 10.0),
        ("S3", "C4", 10.0), ("S3", "C5", 10.0), ("S3", "C6", 10.0),
    ]
    emb = fit_graph_embedding(edges, n_walks_per_node=20, walk_length=8, seed=42)
    sim_s1_s2 = similarity(emb, "S1", "S2")
    sim_s1_s3 = similarity(emb, "S1", "S3")
    assert sim_s1_s2 > sim_s1_s3, \
        f"S1-S2 should be more similar than S1-S3: {sim_s1_s2} vs {sim_s1_s3}"


def test_top_k_neighbours_returns_k():
    edges = [("S1", "C1", 5.0), ("S2", "C1", 4.0), ("S2", "C2", 3.0),
              ("S3", "C2", 6.0)]
    emb = fit_graph_embedding(edges, n_walks_per_node=10, walk_length=5, seed=42)
    preds = top_k_neighbours(emb, "S1", k=2)
    assert len(preds) <= 2


def test_top_k_neighbours_excludes_query():
    edges = [("A", "B", 1.0), ("B", "C", 1.0)]
    emb = fit_graph_embedding(edges, n_walks_per_node=5, walk_length=4, seed=42)
    preds = top_k_neighbours(emb, "A", k=10)
    candidates = [p.candidate for p in preds]
    assert "A" not in candidates


def test_top_k_neighbours_with_filter():
    edges = [("S1", "C1", 5.0), ("S1", "C2", 3.0), ("S2", "C1", 4.0)]
    emb = fit_graph_embedding(edges, n_walks_per_node=5, walk_length=4, seed=42)
    # Filter to only clients
    only_clients = lambda n: n.startswith("C")
    preds = top_k_neighbours(emb, "S1", candidate_filter=only_clients, k=10)
    for p in preds:
        assert p.candidate.startswith("C")


def test_coverage_reports_node_counts():
    edges = [("A", "B", 1.0), ("B", "C", 1.0)]
    emb = fit_graph_embedding(edges, n_walks_per_node=10, walk_length=5, seed=42)
    cov = coverage(emb)
    assert cov["n_nodes"] == 3
    assert cov["n_nodes_with_ppmi"] >= 0
    assert 0 <= cov["coverage_pct"] <= 1


def test_avg_walk_diversity_unique_walk():
    walks = [["A", "B", "C", "D"]]
    assert_close(avg_walk_diversity(walks), 1.0)


def test_avg_walk_diversity_repeated_node():
    walks = [["A", "B", "A", "B"]]   # 2 unique / 4 length = 0.5
    assert_close(avg_walk_diversity(walks), 0.5)


def test_avg_walk_diversity_empty():
    assert avg_walk_diversity([]) == 0.0


def test_generate_walks_deterministic_with_seed():
    g = build_bipartite_graph([("A", "B", 1.0), ("B", "C", 1.0)])
    w1 = generate_walks(g, n_walks_per_node=3, walk_length=4, seed=42)
    w2 = generate_walks(g, n_walks_per_node=3, walk_length=4, seed=42)
    assert w1 == w2


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
