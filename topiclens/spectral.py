"""Spectral Clustering with Jacobi eigendecomposition -- pure stdlib.

Pipeline (Shi & Malik 2000 / Ng-Jordan-Weiss 2002):

  1. Build symmetric affinity matrix W from co-error patterns:
       W[i][j] = Jaccard(S_i, S_j)
       where S_i = set of students who got question i wrong.
  2. D = diag(row sums of W).
  3. Normalised graph Laplacian L_sym = I - D^{-1/2} W D^{-1/2}.
  4. Eigendecomposition of L_sym (Jacobi rotation, symmetric matrices).
  5. Take the eigenvectors of the k smallest eigenvalues > 0 -> embed
     nodes into R^k.
  6. Row-normalise embeddings to unit length.
  7. k-means on embedded rows -> cluster assignment per question.

Pure stdlib: math + random + statistics + dataclasses + collections.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from statistics import fmean


Matrix = list[list[float]]
Vector = list[float]


# ============================ matrix utils ============================== #


def _zeros(rows: int, cols: int) -> Matrix:
    return [[0.0] * cols for _ in range(rows)]


def _eye(n: int) -> Matrix:
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def _copy_matrix(A: Matrix) -> Matrix:
    return [row[:] for row in A]


def _matmul(A: Matrix, B: Matrix) -> Matrix:
    n = len(A)
    m = len(B[0])
    k = len(B)
    C = _zeros(n, m)
    for i in range(n):
        Ai = A[i]
        for kk in range(k):
            aik = Ai[kk]
            if aik == 0.0:
                continue
            Brow = B[kk]
            for j in range(m):
                C[i][j] += aik * Brow[j]
    return C


# ============================ Jacobi eigendecomp ====================== #


def _max_off_diagonal(A: Matrix) -> tuple[int, int, float]:
    """Find indices (p, q) p<q with largest |A[p][q]|."""
    n = len(A)
    p, q = 0, 1
    max_val = abs(A[0][1]) if n > 1 else 0.0
    for i in range(n):
        for j in range(i + 1, n):
            if abs(A[i][j]) > max_val:
                max_val = abs(A[i][j])
                p, q = i, j
    return p, q, max_val


def jacobi_eigendecomp(
    A: Matrix, max_sweeps: int = 100, tol: float = 1e-10,
) -> tuple[Vector, Matrix]:
    """Jacobi rotation for symmetric matrices.

    Returns (eigenvalues, eigenvectors_columns):
      eigenvalues[i] is the i-th eigenvalue
      eigenvectors[k][i] is the i-th component of the i-th eigenvector
      (columns of eigenvectors are eigenvectors).
    """
    n = len(A)
    M = _copy_matrix(A)
    V = _eye(n)

    for sweep in range(max_sweeps):
        p, q, max_off = _max_off_diagonal(M)
        if max_off < tol:
            break

        app = M[p][p]
        aqq = M[q][q]
        apq = M[p][q]

        if abs(app - aqq) < 1e-30:
            theta = math.pi / 4.0
        else:
            theta = 0.5 * math.atan2(2.0 * apq, app - aqq)
        c = math.cos(theta)
        s = math.sin(theta)

        # Givens rotation R with R[p][p] = c, R[q][q] = c, R[p][q] = -s, R[q][p] = s.
        # M' = R^T M R. Closed-form updates for symmetric M:
        new_app = c * c * app + 2.0 * s * c * apq + s * s * aqq
        new_aqq = s * s * app - 2.0 * s * c * apq + c * c * aqq
        M[p][p] = new_app
        M[q][q] = new_aqq
        M[p][q] = 0.0
        M[q][p] = 0.0

        for i in range(n):
            if i == p or i == q:
                continue
            aip = M[i][p]
            aiq = M[i][q]
            # row/col p update:  m_ip' = c * m_ip + s * m_iq
            # row/col q update:  m_iq' = -s * m_ip + c * m_iq
            M[i][p] = c * aip + s * aiq
            M[p][i] = M[i][p]
            M[i][q] = -s * aip + c * aiq
            M[q][i] = M[i][q]

        # Accumulate rotation into V (apply R from the right).
        for i in range(n):
            vip = V[i][p]
            viq = V[i][q]
            V[i][p] = c * vip + s * viq
            V[i][q] = -s * vip + c * viq

    eigenvalues = [M[i][i] for i in range(n)]
    return eigenvalues, V


# ============================ affinity matrix ========================= #


def jaccard_similarity(set_a: set[int], set_b: set[int]) -> float:
    if not set_a and not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def build_coerror_affinity(
    responses: dict[int, dict[int, int]],
    question_ids: list[int],
    sparsify_zero: bool = False,
) -> Matrix:
    """Build W where W[i][j] = Jaccard(students wrong on q_i, students wrong on q_j).

    responses: {student_id: {question_id: 0|1}}  where 0 = wrong, 1 = correct.
    question_ids: list of question identifiers in matrix order.
    """
    n = len(question_ids)
    wrong_sets: dict[int, set[int]] = {}
    for q in question_ids:
        wrong_sets[q] = {
            s for s, r in responses.items() if r.get(q, 1) == 0
        }

    W = _zeros(n, n)
    for i in range(n):
        for j in range(i, n):
            if i == j:
                W[i][j] = 0.0   # spectral conv: zero diagonal
            else:
                sim = jaccard_similarity(wrong_sets[question_ids[i]], wrong_sets[question_ids[j]])
                if sparsify_zero and sim < 0.05:
                    sim = 0.0
                W[i][j] = sim
                W[j][i] = sim
    return W


def normalised_laplacian(W: Matrix) -> Matrix:
    """L_sym = I - D^{-1/2} W D^{-1/2}.

    Components with zero degree get D^{-1/2} = 0 to avoid divide-by-zero.
    """
    n = len(W)
    deg = [sum(W[i]) for i in range(n)]
    d_inv_sqrt = [
        (1.0 / math.sqrt(d)) if d > 1e-12 else 0.0 for d in deg
    ]
    L = _zeros(n, n)
    for i in range(n):
        for j in range(n):
            wij = W[i][j]
            normalised = d_inv_sqrt[i] * wij * d_inv_sqrt[j]
            L[i][j] = (1.0 if i == j and deg[i] > 1e-12 else (1.0 if i == j else 0.0)) - normalised
    return L


# ============================ k-means =============================== #


def _euclidean_sq(a: Vector, b: Vector) -> float:
    return sum((ai - bi) * (ai - bi) for ai, bi in zip(a, b))


def kmeans(
    points: list[Vector], k: int, seed: int = 42, n_iter: int = 100, n_restarts: int = 5,
) -> tuple[list[int], list[Vector]]:
    """Lloyd's algorithm with kmeans++ init + multi-restart.

    Returns (labels, centroids). best_inertia restart wins.
    """
    rng = random.Random(seed)
    n = len(points)
    if n == 0 or k <= 0:
        return [], []
    if n <= k:
        return list(range(n)), [list(p) for p in points]

    best_labels: list[int] = []
    best_centroids: list[Vector] = []
    best_inertia = float("inf")

    for restart in range(n_restarts):
        # kmeans++ init
        centroids: list[Vector] = []
        # Pick first centroid uniformly
        first = rng.randrange(n)
        centroids.append(list(points[first]))
        while len(centroids) < k:
            # Compute distance from each point to nearest existing centroid
            d2 = []
            for p in points:
                best = min(_euclidean_sq(p, c) for c in centroids)
                d2.append(best)
            total = sum(d2)
            if total < 1e-12:
                # All points identical -> pick random
                idx = rng.randrange(n)
            else:
                # Sample weighted by d2
                u = rng.random() * total
                cum = 0.0
                idx = 0
                for i, w in enumerate(d2):
                    cum += w
                    if cum >= u:
                        idx = i
                        break
            centroids.append(list(points[idx]))

        # Lloyd iterations
        labels = [0] * n
        for it in range(n_iter):
            # Assign
            changed = False
            for i, p in enumerate(points):
                best_c = 0
                best_d = float("inf")
                for ci, c in enumerate(centroids):
                    d = _euclidean_sq(p, c)
                    if d < best_d:
                        best_d = d
                        best_c = ci
                if labels[i] != best_c:
                    labels[i] = best_c
                    changed = True
            if not changed:
                break
            # Update
            new_centroids: list[Vector] = []
            for ci in range(k):
                members = [points[i] for i in range(n) if labels[i] == ci]
                if not members:
                    # Empty cluster: keep old centroid
                    new_centroids.append(centroids[ci])
                else:
                    dim = len(members[0])
                    new_centroids.append([fmean(m[d] for m in members) for d in range(dim)])
            centroids = new_centroids

        # Compute inertia
        inertia = sum(_euclidean_sq(points[i], centroids[labels[i]]) for i in range(n))
        if inertia < best_inertia:
            best_inertia = inertia
            best_labels = list(labels)
            best_centroids = [list(c) for c in centroids]

    return best_labels, best_centroids


# ============================ spectral clustering ===================== #


@dataclass
class SpectralResult:
    labels: list[int]
    embedding: list[Vector]
    eigenvalues_ascending: list[float]
    n_clusters: int
    affinity: Matrix


def spectral_cluster(
    W: Matrix, k: int, seed: int = 42,
) -> SpectralResult:
    """Ng-Jordan-Weiss 2002 spectral clustering.

    Steps:
      1. L = D^{-1/2} W D^{-1/2}  (the "normalised" affinity)
      2. Eigendecompose L -> take TOP-k eigenvectors (largest eigenvalues)
      3. Row-normalise eigenvector matrix to unit length
      4. k-means on rows
    """
    n = len(W)
    deg = [sum(W[i]) for i in range(n)]
    d_inv_sqrt = [
        (1.0 / math.sqrt(d)) if d > 1e-12 else 0.0 for d in deg
    ]

    L_aff = _zeros(n, n)
    for i in range(n):
        for j in range(n):
            L_aff[i][j] = d_inv_sqrt[i] * W[i][j] * d_inv_sqrt[j]

    eigenvalues, V = jacobi_eigendecomp(L_aff)

    # Take top-k eigenvectors (largest eigenvalues of normalised affinity).
    indexed = sorted(range(n), key=lambda i: -eigenvalues[i])
    top_idx = indexed[: k]

    # Build n x k embedding matrix (rows are nodes).
    Y = _zeros(n, k)
    for i in range(n):
        for col, e_idx in enumerate(top_idx):
            Y[i][col] = V[i][e_idx]

    # Row-normalise to unit length.
    for i in range(n):
        norm = math.sqrt(sum(y * y for y in Y[i]))
        if norm > 1e-12:
            for j in range(k):
                Y[i][j] /= norm

    labels, _ = kmeans(Y, k, seed=seed)

    eigenvalues_ascending = sorted(eigenvalues)
    return SpectralResult(
        labels=labels,
        embedding=Y,
        eigenvalues_ascending=eigenvalues_ascending,
        n_clusters=k,
        affinity=W,
    )


# ============================ diagnostics ============================ #


def cluster_members(labels: list[int], items: list, k: int) -> dict[int, list]:
    """Group items by cluster label."""
    out: dict[int, list] = {c: [] for c in range(k)}
    for i, c in enumerate(labels):
        if c in out:
            out[c].append(items[i])
        else:
            out[c] = [items[i]]
    return out


def cluster_centroid_topics(
    labels: list[int], item_topics: list[list[str]], k: int, top_n: int = 3,
) -> dict[int, list[tuple[str, int]]]:
    """For each cluster, return the (top_n) most common topic tags across its items.

    item_topics[i] is the list of topic tags for question/item i.
    """
    from collections import Counter
    out: dict[int, list[tuple[str, int]]] = {}
    for c in range(k):
        ctr: Counter[str] = Counter()
        for i, lab in enumerate(labels):
            if lab == c:
                for t in item_topics[i]:
                    ctr[t] += 1
        out[c] = ctr.most_common(top_n)
    return out


def silhouette_score(points: list[Vector], labels: list[int]) -> float:
    """Mean silhouette across all points -- diagnostic for cluster quality."""
    n = len(points)
    if n <= 1:
        return 0.0
    cluster_of: dict[int, list[int]] = {}
    for i, c in enumerate(labels):
        cluster_of.setdefault(c, []).append(i)

    s_vals = []
    for i in range(n):
        same = [j for j in cluster_of[labels[i]] if j != i]
        if not same:
            s_vals.append(0.0)
            continue
        a = fmean(math.sqrt(_euclidean_sq(points[i], points[j])) for j in same)
        b = float("inf")
        for c, members in cluster_of.items():
            if c == labels[i]:
                continue
            mean_d = fmean(math.sqrt(_euclidean_sq(points[i], points[j])) for j in members)
            if mean_d < b:
                b = mean_d
        denom = max(a, b)
        s_vals.append((b - a) / denom if denom > 1e-12 else 0.0)
    return fmean(s_vals) if s_vals else 0.0
