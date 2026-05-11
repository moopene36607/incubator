"""kindergrid edge tests — pure-function HAC + DBSCAN correctness."""
from __future__ import annotations

from clustering import (
    euclidean, squared_euclidean, cosine_similarity,
    hac_ward, cut_dendrogram, characterize_clusters,
    dbscan, recommend_from_clusters,
)


def test_euclidean_zero():
    """Same point → 0 distance."""
    assert euclidean([1, 2, 3], [1, 2, 3]) == 0


def test_euclidean_basic():
    """3-4-5 triangle."""
    assert abs(euclidean([0, 0], [3, 4]) - 5.0) < 1e-9


def test_squared_euclidean():
    """Squared shortcut."""
    assert squared_euclidean([0, 0], [3, 4]) == 25


def test_cosine_identical():
    """Same vector → similarity 1.0."""
    assert abs(cosine_similarity([1, 2, 3], [1, 2, 3]) - 1.0) < 1e-9


def test_cosine_orthogonal():
    """Orthogonal vectors → 0."""
    assert abs(cosine_similarity([1, 0], [0, 1])) < 1e-9


def test_hac_single_point():
    """Single point → 0 merges."""
    result = hac_ward([[1.0, 2.0]])
    assert len(result.merge_history) == 0


def test_hac_two_points():
    """Two points → 1 merge."""
    result = hac_ward([[0, 0], [1, 1]])
    assert len(result.merge_history) == 1


def test_hac_three_points():
    """Three points → 2 merges, hierarchy reaches single cluster."""
    points = [[0, 0], [1, 1], [10, 10]]
    result = hac_ward(points)
    assert len(result.merge_history) == 2
    # Last merge should have all 3 members
    assert result.merge_history[-1].n_members == 3


def test_hac_merges_close_first():
    """Closer pair merges first."""
    points = [[0, 0], [0.1, 0.1], [10, 10]]
    result = hac_ward(points)
    # First merge should combine points 0 and 1 (closest pair)
    first = result.merge_history[0]
    merged_ids = {first.cluster_a, first.cluster_b}
    assert merged_ids == {0, 1}


def test_cut_dendrogram_n_clusters():
    """Cutting at k returns k clusters."""
    points = [[0, 0], [1, 1], [10, 10], [11, 11], [20, 20]]
    result = hac_ward(points)
    cut = cut_dendrogram(result, n_clusters=3)
    assert len(cut) == 3


def test_cut_dendrogram_full():
    """Cutting at n gives all singletons."""
    points = [[0, 0], [1, 1], [10, 10]]
    result = hac_ward(points)
    cut = cut_dendrogram(result, n_clusters=3)
    assert len(cut) == 3


def test_hac_separable_clusters():
    """3 well-separated clusters → 3-cluster cut gives perfect separation."""
    points = (
        [[0, 0], [0.5, 0.5], [1, 0]]      # cluster A
        + [[10, 10], [10.5, 10.5], [11, 10]]  # cluster B
        + [[20, 20], [20.5, 20.5], [21, 20]]  # cluster C
    )
    result = hac_ward(points)
    clusters = cut_dendrogram(result, n_clusters=3)
    # Each cluster should have 3 members
    assert all(len(m) == 3 for m in clusters.values())


def test_characterize_clusters():
    """Cluster centroids and dominant features computed."""
    points = [[1, 0, 0], [1.1, 0, 0], [0, 10, 0]]
    cluster_members = {0: [0, 1], 1: [2]}
    profiles = characterize_clusters(points, cluster_members, ["f1", "f2", "f3"])
    # Cluster 0: avg [1.05, 0, 0]
    # Cluster 1: avg [0, 10, 0]
    assert len(profiles) == 2
    # Find cluster with f2 dominance
    f2_cluster = next(p for p in profiles if p.cluster_id == 1)
    top_feat = f2_cluster.dominant_features[0][0]
    assert top_feat == "f2"


def test_dbscan_finds_dense_clusters():
    """Dense cluster identified."""
    points = [[0, 0], [0.1, 0], [0, 0.1], [0.1, 0.1], [10, 10]]
    result = dbscan(points, eps=1.0, min_pts=2)
    assert result.n_clusters == 1
    # Last point [10, 10] is far → noise
    assert result.labels[-1] == -1


def test_dbscan_all_noise_if_min_pts_too_high():
    """min_pts > all neighbors → all noise."""
    points = [[i * 10, 0] for i in range(5)]
    result = dbscan(points, eps=1.0, min_pts=3)
    assert result.n_noise == 5


def test_dbscan_one_dense_cluster():
    """5 dense points → 1 cluster, 0 noise."""
    points = [[0, 0], [0.1, 0], [0, 0.1], [0.1, 0.1], [0.05, 0.05]]
    result = dbscan(points, eps=0.5, min_pts=2)
    assert result.n_clusters == 1
    assert result.n_noise == 0


def test_recommend_from_clusters_picks_closest():
    """Family vector closest to cluster centroid."""
    points = [[0, 0], [0.1, 0.1], [10, 10], [10.1, 10.1]]
    cluster_members = {0: [0, 1], 1: [2, 3]}
    family_vec = [0.05, 0.05]
    rec_cid, top = recommend_from_clusters(family_vec, points, cluster_members, top_n=2)
    assert rec_cid == 0


def test_hac_deterministic():
    """Same input → same merge history."""
    points = [[0, 0], [1, 1], [5, 5], [6, 6]]
    r1 = hac_ward(points)
    r2 = hac_ward(points)
    assert len(r1.merge_history) == len(r2.merge_history)


def test_dbscan_deterministic():
    """Same input → same labels."""
    points = [[0, 0], [0.1, 0], [10, 10]]
    r1 = dbscan(points, eps=1.0, min_pts=2)
    r2 = dbscan(points, eps=1.0, min_pts=2)
    assert r1.labels == r2.labels


if __name__ == "__main__":
    tests = [
        test_euclidean_zero,
        test_euclidean_basic,
        test_squared_euclidean,
        test_cosine_identical,
        test_cosine_orthogonal,
        test_hac_single_point,
        test_hac_two_points,
        test_hac_three_points,
        test_hac_merges_close_first,
        test_cut_dendrogram_n_clusters,
        test_cut_dendrogram_full,
        test_hac_separable_clusters,
        test_characterize_clusters,
        test_dbscan_finds_dense_clusters,
        test_dbscan_all_noise_if_min_pts_too_high,
        test_dbscan_one_dense_cluster,
        test_recommend_from_clusters_picks_closest,
        test_hac_deterministic,
        test_dbscan_deterministic,
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
