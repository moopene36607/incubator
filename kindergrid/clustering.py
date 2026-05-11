"""kindergrid — Hierarchical Agglomerative Clustering + DBSCAN (pure stdlib).

Hierarchical Agglomerative Clustering (Ward 1963): start each point as its own
cluster, iteratively merge the pair minimizing ESS (error sum of squares) increase.

DBSCAN (Ester, Kriegel, Sander, Xu 1996): density-based; core points (≥ min_pts
in ε-radius) form clusters via density-reachability, others are noise.

Lance-Williams update for Ward:
  d²(i∪j, k) = ((n_i + n_k) × d²(i,k) + (n_j + n_k) × d²(j,k) - n_k × d²(i,j))
              / (n_i + n_j + n_k)

Pure stdlib (math + dataclass + collections). No numpy / no scipy.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field


# ============== Distance ==============
def euclidean(a: list[float], b: list[float]) -> float:
    """Euclidean distance between two vectors."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def squared_euclidean(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ============== Hierarchical Agglomerative Clustering ==============
@dataclass
class MergeStep:
    """One step of dendrogram building."""
    cluster_a: int          # cluster id merged
    cluster_b: int
    new_cluster_id: int
    height: float           # the distance / ESS at which they merged
    n_members: int          # total members in new cluster


@dataclass
class HACResult:
    n_points: int
    merge_history: list[MergeStep]
    cluster_members_at_step: list[dict[int, list[int]]]    # snapshot per merge


def hac_ward(points: list[list[float]]) -> HACResult:
    """Hierarchical Agglomerative Clustering with Ward linkage."""
    n = len(points)
    if n == 0:
        return HACResult(n_points=0, merge_history=[], cluster_members_at_step=[])

    # Initialize: each point its own cluster
    # cluster_id → members (list of original point indices)
    next_cluster_id = n
    active_clusters: dict[int, list[int]] = {i: [i] for i in range(n)}
    centroids: dict[int, list[float]] = {i: points[i][:] for i in range(n)}
    # Pairwise squared distance dict
    # Use squared distance for Ward
    sq_dist: dict[tuple[int, int], float] = {}
    for i in range(n):
        for j in range(i + 1, n):
            sq_dist[(i, j)] = squared_euclidean(points[i], points[j])

    merge_history: list[MergeStep] = []
    snapshots = [dict(active_clusters)]

    while len(active_clusters) > 1:
        # Find pair minimizing Ward ESS increase:
        # ΔESS = (n_i × n_j) / (n_i + n_j) × d²(centroid_i, centroid_j)
        best_pair = None
        best_dESS = float("inf")
        for (i, j), d2 in sq_dist.items():
            if i not in active_clusters or j not in active_clusters:
                continue
            n_i = len(active_clusters[i])
            n_j = len(active_clusters[j])
            dess = (n_i * n_j) / (n_i + n_j) * d2
            if dess < best_dESS:
                best_dESS = dess
                best_pair = (i, j)

        if best_pair is None:
            break
        i, j = best_pair
        new_id = next_cluster_id
        next_cluster_id += 1

        new_members = active_clusters[i] + active_clusters[j]
        # New centroid = weighted average
        n_i = len(active_clusters[i])
        n_j = len(active_clusters[j])
        new_centroid = [
            (centroids[i][k] * n_i + centroids[j][k] * n_j) / (n_i + n_j)
            for k in range(len(centroids[i]))
        ]
        active_clusters[new_id] = new_members
        centroids[new_id] = new_centroid

        # Update distances using Lance-Williams or simple recomputation
        for other_id in list(active_clusters.keys()):
            if other_id in (i, j, new_id):
                continue
            d_squared = squared_euclidean(centroids[other_id], new_centroid)
            key = (min(other_id, new_id), max(other_id, new_id))
            sq_dist[key] = d_squared

        # Remove merged clusters
        del active_clusters[i]
        del active_clusters[j]
        del centroids[i]
        del centroids[j]

        merge_history.append(MergeStep(
            cluster_a=i, cluster_b=j,
            new_cluster_id=new_id,
            height=best_dESS,
            n_members=len(new_members),
        ))
        snapshots.append(dict(active_clusters))

    return HACResult(
        n_points=n,
        merge_history=merge_history,
        cluster_members_at_step=snapshots,
    )


def cut_dendrogram(result: HACResult, n_clusters: int) -> dict[int, list[int]]:
    """Return flat clustering with exactly `n_clusters` clusters."""
    n = result.n_points
    if n_clusters >= n:
        return {i: [i] for i in range(n)}
    if n_clusters <= 0 or not result.merge_history:
        return {}

    # Need to undo last (n - n_clusters) merges → start with all merges and
    # rewind to get exactly n_clusters
    target_step = n - n_clusters
    if target_step >= len(result.cluster_members_at_step):
        return result.cluster_members_at_step[-1]
    return result.cluster_members_at_step[target_step]


# ============== DBSCAN ==============
@dataclass
class DBSCANResult:
    labels: list[int]            # cluster ID per point; -1 = noise
    n_clusters: int
    n_noise: int
    cluster_members: dict[int, list[int]] = field(default_factory=dict)


def dbscan(points: list[list[float]], eps: float, min_pts: int) -> DBSCANResult:
    """DBSCAN clustering."""
    n = len(points)
    labels = [None] * n            # None = unvisited, -1 = noise, ≥0 = cluster id
    cluster_id = 0

    def neighbors(idx: int) -> list[int]:
        return [j for j in range(n) if j != idx and euclidean(points[idx], points[j]) <= eps]

    for p in range(n):
        if labels[p] is not None:
            continue
        nbrs = neighbors(p)
        if len(nbrs) < min_pts:
            labels[p] = -1
            continue
        # Start new cluster
        labels[p] = cluster_id
        queue = list(nbrs)
        while queue:
            q = queue.pop(0)
            if labels[q] == -1:
                labels[q] = cluster_id
            if labels[q] is not None and labels[q] != cluster_id:
                continue
            if labels[q] is None:
                labels[q] = cluster_id
                q_nbrs = neighbors(q)
                if len(q_nbrs) >= min_pts:
                    queue.extend([x for x in q_nbrs if x not in queue])
        cluster_id += 1

    cluster_members: dict[int, list[int]] = defaultdict(list)
    for i, lbl in enumerate(labels):
        if lbl is not None and lbl >= 0:
            cluster_members[lbl].append(i)

    n_noise = sum(1 for l in labels if l == -1)
    return DBSCANResult(
        labels=labels,
        n_clusters=cluster_id,
        n_noise=n_noise,
        cluster_members=dict(cluster_members),
    )


# ============== Cluster characterization ==============
@dataclass
class ClusterProfile:
    cluster_id: int
    members: list[int]
    centroid: list[float]
    dominant_features: list[tuple[str, float]]    # (feature_name, value)
    size: int


def characterize_clusters(points: list[list[float]],
                            cluster_members: dict[int, list[int]],
                            feature_names: list[str]) -> list[ClusterProfile]:
    """For each cluster, compute centroid and identify dominant features.

    Dominant = feature with highest centroid value (normalized).
    """
    # Global feature mean (for relative dominance)
    n = len(points)
    if n == 0:
        return []
    global_mean = [sum(p[i] for p in points) / n for i in range(len(points[0]))]

    profiles = []
    for cid, members in cluster_members.items():
        if not members:
            continue
        cluster_points = [points[m] for m in members]
        centroid = [sum(p[i] for p in cluster_points) / len(cluster_points)
                     for i in range(len(cluster_points[0]))]
        # Dominance: feature value relative to global mean (normalized diff)
        diffs = []
        for i in range(len(centroid)):
            if global_mean[i] > 0:
                rel = (centroid[i] - global_mean[i]) / global_mean[i]
            else:
                rel = centroid[i]
            diffs.append((feature_names[i], rel, centroid[i]))
        # Top 3 dominant (most above global mean)
        diffs.sort(key=lambda x: -x[1])
        dominant = [(name, val) for name, _, val in diffs[:3]]
        profiles.append(ClusterProfile(
            cluster_id=cid, members=members, centroid=centroid,
            dominant_features=dominant, size=len(members),
        ))
    profiles.sort(key=lambda p: -p.size)
    return profiles


# ============== Preference-based recommendation ==============
def recommend_from_clusters(family_vector: list[float],
                              points: list[list[float]],
                              cluster_members: dict[int, list[int]],
                              top_n: int = 5) -> tuple[int, list[tuple[int, float]]]:
    """Given a family preference vector, recommend a cluster + top-N within it."""
    # Centroid-distance-based cluster pick
    best_cluster_id = None
    best_dist = float("inf")
    for cid, members in cluster_members.items():
        cluster_points = [points[m] for m in members]
        centroid = [sum(p[i] for p in cluster_points) / len(cluster_points)
                     for i in range(len(cluster_points[0]))]
        d = euclidean(family_vector, centroid)
        if d < best_dist:
            best_dist = d
            best_cluster_id = cid

    if best_cluster_id is None:
        return -1, []

    # Within cluster, rank by euclidean to family vector
    members = cluster_members[best_cluster_id]
    ranked = sorted(members, key=lambda m: euclidean(family_vector, points[m]))
    return best_cluster_id, [(m, round(euclidean(family_vector, points[m]), 3)) for m in ranked[:top_n]]
