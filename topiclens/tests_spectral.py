"""Edge-case tests for spectral.py -- spectral clustering via Jacobi eigendecomp.

Run: python3 tests_spectral.py
"""
from __future__ import annotations

import math
import sys

from spectral import (
    jaccard_similarity, build_coerror_affinity, normalised_laplacian,
    jacobi_eigendecomp, _max_off_diagonal, _matmul, _zeros, _eye,
    kmeans, spectral_cluster, silhouette_score, cluster_members,
)


def assert_close(a, b, tol=1e-6, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol {tol})")


# ============================ jaccard / affinity ====================== #


def test_jaccard_identical_sets():
    assert_close(jaccard_similarity({1, 2, 3}, {1, 2, 3}), 1.0)


def test_jaccard_disjoint_sets():
    assert_close(jaccard_similarity({1, 2}, {3, 4}), 0.0)


def test_jaccard_partial_overlap():
    # |{1,2,3} ∩ {2,3,4}| / |union| = 2 / 4 = 0.5
    assert_close(jaccard_similarity({1, 2, 3}, {2, 3, 4}), 0.5)


def test_jaccard_empty_sets():
    assert_close(jaccard_similarity(set(), set()), 0.0)


def test_jaccard_one_empty():
    assert_close(jaccard_similarity({1, 2}, set()), 0.0)


def test_build_coerror_affinity_diagonal_zero():
    responses = {"a": {1: 0, 2: 1, 3: 0}, "b": {1: 0, 2: 0, 3: 1}}
    W = build_coerror_affinity(responses, [1, 2, 3])
    for i in range(3):
        assert W[i][i] == 0.0


def test_build_coerror_affinity_symmetric():
    responses = {"a": {1: 0, 2: 1, 3: 0}, "b": {1: 0, 2: 0, 3: 1}, "c": {1: 1, 2: 0, 3: 0}}
    W = build_coerror_affinity(responses, [1, 2, 3])
    for i in range(3):
        for j in range(3):
            assert_close(W[i][j], W[j][i], msg=f"symmetric at [{i}][{j}]")


def test_build_coerror_perfect_overlap():
    # Two students, both wrong on Q1 and Q2 -> W[Q1][Q2] = 1.0
    responses = {"a": {1: 0, 2: 0}, "b": {1: 0, 2: 0}}
    W = build_coerror_affinity(responses, [1, 2])
    assert_close(W[0][1], 1.0)


# ============================ jacobi eigendecomp ====================== #


def test_jacobi_identity_eigenvalues_one():
    I = _eye(4)
    evals, V = jacobi_eigendecomp(I)
    for e in evals:
        assert_close(e, 1.0)


def test_jacobi_diagonal_matrix_eigenvalues_match_diagonal():
    A = [[3.0, 0.0, 0.0], [0.0, 7.0, 0.0], [0.0, 0.0, 2.0]]
    evals, V = jacobi_eigendecomp(A)
    sorted_evals = sorted(evals)
    assert_close(sorted_evals[0], 2.0)
    assert_close(sorted_evals[1], 3.0)
    assert_close(sorted_evals[2], 7.0)


def test_jacobi_2x2_known_eigenvalues():
    # A = [[4, 1], [1, 3]] -> eigenvalues are 4.618 and 2.382 (roots of λ²-7λ+11)
    A = [[4.0, 1.0], [1.0, 3.0]]
    evals, _ = jacobi_eigendecomp(A)
    sorted_evals = sorted(evals)
    expected = sorted([7/2 - math.sqrt(5)/2, 7/2 + math.sqrt(5)/2])
    assert_close(sorted_evals[0], expected[0], tol=1e-6)
    assert_close(sorted_evals[1], expected[1], tol=1e-6)


def test_jacobi_eigenvectors_are_orthonormal():
    A = [[4.0, 1.0, 0.5], [1.0, 3.0, 0.2], [0.5, 0.2, 5.0]]
    _, V = jacobi_eigendecomp(A)
    n = len(V)
    # V^T V should be identity
    for i in range(n):
        for j in range(n):
            dot = sum(V[k][i] * V[k][j] for k in range(n))
            expected = 1.0 if i == j else 0.0
            assert_close(dot, expected, tol=1e-6, msg=f"V orthonormal [{i}][{j}]")


def test_jacobi_reconstruct_a_via_eigendecomp():
    # A = V * Λ * V^T should reconstruct A.
    A = [[2.0, -1.0, 0.5], [-1.0, 3.0, 1.0], [0.5, 1.0, 4.0]]
    evals, V = jacobi_eigendecomp(A)
    n = len(A)
    Lambda = [[evals[i] if i == j else 0.0 for j in range(n)] for i in range(n)]
    V_T = [[V[j][i] for j in range(n)] for i in range(n)]
    A_recon = _matmul(_matmul(V, Lambda), V_T)
    for i in range(n):
        for j in range(n):
            assert_close(A_recon[i][j], A[i][j], tol=1e-5,
                          msg=f"reconstruction at [{i}][{j}]")


# ============================ k-means ============================== #


def test_kmeans_separable_clusters():
    points = [[0.0, 0.0], [0.1, 0.0], [0.0, 0.1],
              [10.0, 10.0], [10.1, 10.0], [10.0, 10.1]]
    labels, _ = kmeans(points, k=2, seed=42)
    # Points 0-2 should be in same cluster; 3-5 in another.
    assert labels[0] == labels[1] == labels[2]
    assert labels[3] == labels[4] == labels[5]
    assert labels[0] != labels[3]


def test_kmeans_handles_n_less_than_k():
    points = [[0.0, 0.0], [1.0, 1.0]]
    labels, centroids = kmeans(points, k=5, seed=42)
    assert len(labels) == 2
    assert len(centroids) == 2


def test_kmeans_empty_points():
    labels, centroids = kmeans([], k=3, seed=42)
    assert labels == []
    assert centroids == []


# ============================ spectral pipeline ====================== #


def test_spectral_cluster_separable_groups():
    """Two groups of questions co-erred by disjoint students."""
    # Students 1, 2, 3 wrong on questions 1, 2; students 4, 5, 6 wrong on 3, 4.
    responses = {
        "1": {1: 0, 2: 0, 3: 1, 4: 1},
        "2": {1: 0, 2: 0, 3: 1, 4: 1},
        "3": {1: 0, 2: 0, 3: 1, 4: 1},
        "4": {1: 1, 2: 1, 3: 0, 4: 0},
        "5": {1: 1, 2: 1, 3: 0, 4: 0},
        "6": {1: 1, 2: 1, 3: 0, 4: 0},
    }
    W = build_coerror_affinity(responses, [1, 2, 3, 4])
    result = spectral_cluster(W, k=2, seed=42)
    # Q1, Q2 should be in one cluster; Q3, Q4 in the other.
    assert result.labels[0] == result.labels[1], f"Q1,Q2 same cluster: {result.labels}"
    assert result.labels[2] == result.labels[3], f"Q3,Q4 same cluster: {result.labels}"
    assert result.labels[0] != result.labels[2], f"two groups distinct: {result.labels}"


def test_spectral_cluster_returns_correct_shape():
    responses = {
        f"s{i}": {1: (i % 2), 2: ((i + 1) % 2), 3: 1, 4: 0, 5: (i % 3)} for i in range(10)
    }
    W = build_coerror_affinity(responses, [1, 2, 3, 4, 5])
    result = spectral_cluster(W, k=3, seed=42)
    assert len(result.labels) == 5
    assert len(result.embedding) == 5
    assert result.n_clusters == 3
    for lab in result.labels:
        assert 0 <= lab < 3


def test_spectral_cluster_deterministic():
    responses = {
        "1": {1: 0, 2: 0, 3: 1, 4: 1},
        "2": {1: 0, 2: 0, 3: 1, 4: 1},
        "3": {1: 1, 2: 1, 3: 0, 4: 0},
    }
    W = build_coerror_affinity(responses, [1, 2, 3, 4])
    r1 = spectral_cluster(W, k=2, seed=42)
    r2 = spectral_cluster(W, k=2, seed=42)
    assert r1.labels == r2.labels


def test_normalised_laplacian_diagonal_is_one_for_connected_nodes():
    W = [[0.0, 0.5, 0.5], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]]
    L = normalised_laplacian(W)
    for i in range(3):
        assert_close(L[i][i], 1.0, tol=1e-9)


def test_max_off_diagonal_finds_largest():
    A = [[1.0, 0.2, 0.5], [0.2, 2.0, 0.8], [0.5, 0.8, 3.0]]
    p, q, val = _max_off_diagonal(A)
    assert (p, q) == (1, 2)
    assert_close(val, 0.8)


def test_silhouette_separable_clusters_high():
    """For well-separated clusters silhouette should be near 1."""
    points = [[0.0, 0.0], [0.1, 0.0], [0.0, 0.1],
              [10.0, 10.0], [10.1, 10.0], [10.0, 10.1]]
    labels = [0, 0, 0, 1, 1, 1]
    s = silhouette_score(points, labels)
    assert s > 0.9, f"separable clusters should have high silhouette; got {s}"


def test_cluster_members_groups_correctly():
    labels = [0, 1, 0, 2, 1]
    items = ["a", "b", "c", "d", "e"]
    grouped = cluster_members(labels, items, k=3)
    assert set(grouped[0]) == {"a", "c"}
    assert set(grouped[1]) == {"b", "e"}
    assert set(grouped[2]) == {"d"}


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
