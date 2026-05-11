"""Linear Discriminant Analysis (Fisher 1936) -- pure stdlib.

Generative classifier:
    P(x | class=k)  ~  Normal(mu_k, Sigma)   (shared covariance across classes)
    P(class=k)      =  pi_k                   (class prior)

The linear discriminant function (log-posterior up to constant) is:
    delta_k(x) = x^T Sigma^-1 mu_k - 0.5 * mu_k^T Sigma^-1 mu_k + log(pi_k)

Predict argmax_k delta_k(x). Posterior P(k | x) via softmax over {delta_k}.

We avoid computing Sigma^-1 explicitly; instead we solve Sigma * z_k = mu_k
via Gauss-Jordan elimination on the augmented matrix. This is more
numerically stable and faster for small feature counts.

Pure stdlib: math + statistics + dataclasses + collections.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import fmean


# ============================ small matrix kit ============================ #


Matrix = list[list[float]]
Vector = list[float]


def _zeros(rows: int, cols: int) -> Matrix:
    return [[0.0] * cols for _ in range(rows)]


def _eye(n: int) -> Matrix:
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def _matvec(M: Matrix, v: Vector) -> Vector:
    return [sum(M[i][j] * v[j] for j in range(len(v))) for i in range(len(M))]


def _vecdot(a: Vector, b: Vector) -> float:
    return sum(ai * bi for ai, bi in zip(a, b))


def _vecsub(a: Vector, b: Vector) -> Vector:
    return [ai - bi for ai, bi in zip(a, b)]


def gauss_jordan_solve(A_in: Matrix, B_in: Matrix) -> Matrix:
    """Solve A X = B by Gauss-Jordan elimination on [A | B].

    A is n x n, B is n x m (right-hand sides). Returns X of shape n x m.
    Uses partial pivoting for numerical stability. Raises ValueError if A is
    singular (used to signal "covariance ill-conditioned, add jitter").
    """
    n = len(A_in)
    m = len(B_in[0]) if B_in else 0
    # Build augmented matrix.
    aug = [list(A_in[i]) + list(B_in[i]) for i in range(n)]

    for col in range(n):
        # Partial pivoting: find row with largest |aug[r][col]| for r >= col.
        pivot_row = col
        pivot_val = abs(aug[col][col])
        for r in range(col + 1, n):
            if abs(aug[r][col]) > pivot_val:
                pivot_val = abs(aug[r][col])
                pivot_row = r
        if pivot_val < 1e-12:
            raise ValueError("singular matrix in gauss_jordan_solve")
        if pivot_row != col:
            aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        # Normalise pivot row.
        pv = aug[col][col]
        for j in range(col, n + m):
            aug[col][j] /= pv
        # Eliminate column in other rows.
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor == 0.0:
                continue
            for j in range(col, n + m):
                aug[r][j] -= factor * aug[col][j]

    return [[aug[i][n + j] for j in range(m)] for i in range(n)]


# ============================== LDA fit ================================== #


@dataclass
class LDAModel:
    class_names: list[str]
    class_priors: dict[str, float]
    class_means: dict[str, Vector]
    # solver_solutions[k] = Sigma^-1 mu_k  (the "discriminant weight vector" for class k)
    solver_solutions: dict[str, Vector]
    # bias_term[k] = -0.5 * mu_k^T Sigma^-1 mu_k + log(pi_k)
    bias_term: dict[str, float]
    feature_names: list[str]
    n_training: int
    n_classes: int
    pooled_covariance: Matrix          # Sigma (for diagnostics / display)
    feature_means_global: Vector       # for displaying centred values
    feature_stds_global: Vector        # for displaying scale-relative contribs


def _class_means(
    X: list[Vector], labels: list[str], classes: list[str]
) -> dict[str, Vector]:
    p = len(X[0])
    out: dict[str, Vector] = {}
    for k in classes:
        rows = [X[i] for i in range(len(X)) if labels[i] == k]
        if not rows:
            out[k] = [0.0] * p
            continue
        out[k] = [fmean(r[j] for r in rows) for j in range(p)]
    return out


def _pooled_covariance(
    X: list[Vector], labels: list[str], means: dict[str, Vector],
    jitter: float = 1e-4,
) -> Matrix:
    """Pooled within-class covariance with diagonal jitter for stability.

    Sigma_pooled = (1 / (N - K)) * sum_i (x_i - mu_{y_i}) (x_i - mu_{y_i})^T

    where N = #samples and K = #classes. The jitter * I term keeps the matrix
    well-conditioned when features are nearly co-linear (common in small
    samples with discrete-valued symptom scores).
    """
    n = len(X)
    p = len(X[0])
    k = len(set(labels))
    denom = max(n - k, 1)

    cov: Matrix = _zeros(p, p)
    for i in range(n):
        mu = means[labels[i]]
        d = _vecsub(X[i], mu)
        for a in range(p):
            for b in range(p):
                cov[a][b] += d[a] * d[b]
    for a in range(p):
        for b in range(p):
            cov[a][b] /= denom
    # Tikhonov-style ridge on the diagonal to ensure positive-definiteness.
    for a in range(p):
        cov[a][a] += jitter
    return cov


def fit_lda(
    X: list[Vector], labels: list[str], feature_names: list[str],
    jitter: float = 1e-4,
) -> LDAModel:
    """Train LDA. Returns a model with precomputed Sigma^-1 mu_k for each class."""
    if not X:
        raise ValueError("fit_lda 需要至少 1 個 sample")
    if len(X) != len(labels):
        raise ValueError("X 和 labels 長度不一致")

    p = len(X[0])
    # Class index in insertion order (stable, reproducible).
    seen: list[str] = []
    seen_set: set[str] = set()
    for L in labels:
        if L not in seen_set:
            seen.append(L)
            seen_set.add(L)

    classes = seen
    n_total = len(X)
    class_counts = {k: sum(1 for L in labels if L == k) for k in classes}
    class_priors = {k: class_counts[k] / n_total for k in classes}
    class_means_d = _class_means(X, labels, classes)

    Sigma = _pooled_covariance(X, labels, class_means_d, jitter=jitter)
    # Solve Sigma * Z = M (where M is matrix with columns mu_k).
    M = [[class_means_d[k][i] for k in classes] for i in range(p)]
    Z = gauss_jordan_solve(Sigma, M)
    solver_solutions: dict[str, Vector] = {}
    for idx, k in enumerate(classes):
        solver_solutions[k] = [Z[i][idx] for i in range(p)]

    bias_term: dict[str, float] = {}
    for k in classes:
        mu = class_means_d[k]
        z = solver_solutions[k]
        bias_term[k] = -0.5 * _vecdot(mu, z) + math.log(class_priors[k])

    # Diagnostics: global feature mean / std (for display only).
    feature_means_global = [fmean(row[j] for row in X) for j in range(p)]
    feature_stds_global = []
    for j in range(p):
        m_j = feature_means_global[j]
        v_j = sum((row[j] - m_j) ** 2 for row in X) / max(n_total - 1, 1)
        feature_stds_global.append(math.sqrt(max(v_j, 1e-12)))

    return LDAModel(
        class_names=classes,
        class_priors=class_priors,
        class_means=class_means_d,
        solver_solutions=solver_solutions,
        bias_term=bias_term,
        feature_names=feature_names,
        n_training=n_total,
        n_classes=len(classes),
        pooled_covariance=Sigma,
        feature_means_global=feature_means_global,
        feature_stds_global=feature_stds_global,
    )


# ============================ predict / explain ========================= #


@dataclass
class LDAPrediction:
    predicted_class: str
    class_probabilities: dict[str, float]
    class_discriminants: dict[str, float]   # raw delta_k(x), unnormalised log-posteriors
    feature_contributions: list[tuple[str, float, float]]
    # top features that pushed prediction TOWARD the winning class
    # vs the runner-up. Each entry: (feature_name, value, signed_contribution).


def _softmax(scores: dict[str, float]) -> dict[str, float]:
    """Numerically stable softmax over a dict of scores."""
    mx = max(scores.values())
    exp = {k: math.exp(v - mx) for k, v in scores.items()}
    s = sum(exp.values())
    return {k: v / s for k, v in exp.items()}


def predict_one(model: LDAModel, x: Vector) -> LDAPrediction:
    """Predict class for one observation; return posteriors + feature contributions.

    delta_k(x) = z_k^T x + bias_term[k]
    The 'contribution' of feature j to class k (relative to other classes)
    is z_k[j] * x[j].
    """
    discriminants: dict[str, float] = {}
    for k in model.class_names:
        z = model.solver_solutions[k]
        discriminants[k] = _vecdot(z, x) + model.bias_term[k]
    probs = _softmax(discriminants)
    pred = max(discriminants, key=discriminants.get)

    # Feature contribution to winning class minus average of other classes.
    other_classes = [c for c in model.class_names if c != pred]
    other_avg_weights: Vector = [
        fmean(model.solver_solutions[c][j] for c in other_classes)
        for j in range(len(x))
    ]
    win_weights = model.solver_solutions[pred]
    contribs = []
    for j, val in enumerate(x):
        relative_w = win_weights[j] - other_avg_weights[j]
        contribs.append((model.feature_names[j], val, relative_w * val))
    contribs.sort(key=lambda t: -abs(t[2]))

    return LDAPrediction(
        predicted_class=pred,
        class_probabilities=probs,
        class_discriminants=discriminants,
        feature_contributions=contribs,
    )


def accuracy(model: LDAModel, X: list[Vector], labels: list[str]) -> float:
    if not X:
        return 0.0
    correct = 0
    for x, y in zip(X, labels):
        if predict_one(model, x).predicted_class == y:
            correct += 1
    return correct / len(X)


def confusion_matrix(
    model: LDAModel, X: list[Vector], labels: list[str]
) -> dict[str, dict[str, int]]:
    cm: dict[str, dict[str, int]] = {
        true: {pred: 0 for pred in model.class_names} for true in model.class_names
    }
    for x, y in zip(X, labels):
        pred = predict_one(model, x).predicted_class
        if y in cm:
            cm[y][pred] += 1
    return cm


def loo_evaluate(
    X: list[Vector], labels: list[str], feature_names: list[str],
    jitter: float = 1e-4,
) -> dict:
    """Leave-one-out cross-validation accuracy (honest evaluation)."""
    n = len(X)
    correct = 0
    skipped = 0
    for i in range(n):
        X_train = X[:i] + X[i + 1 :]
        y_train = labels[:i] + labels[i + 1 :]
        # Skip fold if removing this sample makes any class empty.
        if len(set(y_train)) < len(set(labels)):
            skipped += 1
            continue
        try:
            m = fit_lda(X_train, y_train, feature_names, jitter=jitter)
        except ValueError:
            skipped += 1
            continue
        if predict_one(m, X[i]).predicted_class == labels[i]:
            correct += 1
    n_used = n - skipped
    return {
        "accuracy": correct / n_used if n_used else 0.0,
        "n_folds": n_used,
        "n_skipped": skipped,
    }


def class_centroid_distance(
    model: LDAModel, x: Vector,
) -> dict[str, float]:
    """Mahalanobis-like distance from x to each class centroid using pooled Sigma.

    Useful diagnostic showing 'which class is the observation closest to in
    LDA's metric'. Uses dM(x, mu_k) = sqrt((x - mu_k)^T Sigma^-1 (x - mu_k)).
    Computed via the already-solved discriminant weights to avoid re-inverting.
    """
    # We have z_k = Sigma^-1 mu_k. Sigma^-1 (x - mu_k) = Sigma^-1 x - z_k.
    # Solve Sigma * w = x to get Sigma^-1 x.
    Sigma = model.pooled_covariance
    rhs = [[xi] for xi in x]
    w = gauss_jordan_solve(Sigma, rhs)
    sigma_inv_x = [row[0] for row in w]

    out: dict[str, float] = {}
    for k in model.class_names:
        z_k = model.solver_solutions[k]
        mu_k = model.class_means[k]
        diff_weight = [sigma_inv_x[j] - z_k[j] for j in range(len(x))]
        diff_val = [x[j] - mu_k[j] for j in range(len(x))]
        sq = _vecdot(diff_val, diff_weight)
        out[k] = math.sqrt(max(sq, 0.0))
    return out
