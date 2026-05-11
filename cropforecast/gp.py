"""Gaussian Process Regression (Rasmussen & Williams 2006) -- pure stdlib.

We use the squared-exponential (RBF) kernel:

    k(x, x') = sigma_f^2 * exp( -(x - x')^2 / (2 * ell^2) )

Given training points (X, y) with independent Gaussian observation noise
y_i = f(x_i) + N(0, sigma_n^2), the posterior over f at test points X* is:

    K = kernel(X, X)
    K_noise = K + sigma_n^2 * I
    Solve K_noise * alpha = y    (one linear system)
    For each test x*:
        k_star = kernel(x*, X)
        post_mean(x*)     = k_star . alpha
        Solve K_noise * v = k_star
        post_var(x*)      = kernel(x*, x*) - k_star . v
        95% CI            = post_mean ± 1.96 * sqrt(post_var)

We avoid Cholesky and reuse Gauss-Jordan elimination (also used in r59 LDA's
matrix kit) to keep the code compact and pure-stdlib.

Pure stdlib: math + statistics + dataclasses.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import fmean, pstdev


Matrix = list[list[float]]
Vector = list[float]


# ============================ small matrix kit =========================== #


def _zeros(rows: int, cols: int) -> Matrix:
    return [[0.0] * cols for _ in range(rows)]


def gauss_jordan_solve(A_in: Matrix, B_in: Matrix) -> Matrix:
    """Solve A X = B by Gauss-Jordan with partial pivoting. A is n x n, B is n x m."""
    n = len(A_in)
    m = len(B_in[0]) if B_in and B_in[0] else 0
    aug = [list(A_in[i]) + list(B_in[i]) for i in range(n)]

    for col in range(n):
        pivot_row = col
        pivot_val = abs(aug[col][col])
        for r in range(col + 1, n):
            if abs(aug[r][col]) > pivot_val:
                pivot_val = abs(aug[r][col])
                pivot_row = r
        if pivot_val < 1e-12:
            raise ValueError("singular matrix -- increase noise or jitter")
        if pivot_row != col:
            aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        pv = aug[col][col]
        for j in range(col, n + m):
            aug[col][j] /= pv
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor == 0.0:
                continue
            for j in range(col, n + m):
                aug[r][j] -= factor * aug[col][j]

    return [[aug[i][n + j] for j in range(m)] for i in range(n)]


# ============================ kernel =================================== #


def rbf_kernel(x1: float, x2: float, sigma_f: float, ell: float) -> float:
    """Squared-exponential (RBF) kernel for scalar inputs."""
    diff = x1 - x2
    return sigma_f * sigma_f * math.exp(-(diff * diff) / (2.0 * ell * ell))


def kernel_matrix(
    X_a: Vector, X_b: Vector, sigma_f: float, ell: float
) -> Matrix:
    """Compute K[i][j] = k(X_a[i], X_b[j])."""
    n = len(X_a)
    m = len(X_b)
    K = _zeros(n, m)
    for i in range(n):
        for j in range(m):
            K[i][j] = rbf_kernel(X_a[i], X_b[j], sigma_f, ell)
    return K


# ============================ GP model ================================ #


@dataclass
class GPModel:
    X_train: Vector
    y_train: Vector
    sigma_f: float
    ell: float
    sigma_n: float
    # Precomputed quantities:
    K_noise: Matrix                  # K + sigma_n^2 * I
    alpha: Vector                    # solution of K_noise * alpha = y
    K_inv: Matrix                    # full inverse (used for variance computation)
    y_mean: float                    # subtracted before training to centre data
    n: int


def fit_gp(
    X: Vector, y: Vector,
    sigma_f: float | None = None,
    ell: float | None = None,
    sigma_n: float | None = None,
) -> GPModel:
    """Fit Gaussian Process regression.

    Hyperparameters auto-default to sensible heuristics when not supplied:
      sigma_f = stdev(y)     (signal scale)
      ell     = (max(X) - min(X)) / 10   (length-scale ~ 10% of range)
      sigma_n = 0.10 * stdev(y)          (10% observation noise)

    Returns a model with precomputed alpha and K_inv for fast prediction.
    """
    if not X:
        raise ValueError("fit_gp 需要至少 2 個 training points")
    if len(X) != len(y):
        raise ValueError("X 和 y 長度不一致")
    if len(X) < 2:
        raise ValueError("fit_gp 需要至少 2 個 training points 才能估計噪音")

    n = len(X)
    y_mean = fmean(y)
    y_centred = [yi - y_mean for yi in y]

    y_std = pstdev(y_centred) if n >= 2 else 1.0
    if y_std < 1e-12:
        y_std = 1.0  # zero-variance guard

    if sigma_f is None:
        sigma_f = y_std
    if ell is None:
        rng = max(X) - min(X)
        ell = max(rng / 10.0, 1.0)
    if sigma_n is None:
        sigma_n = max(0.10 * y_std, 1e-3)

    K = kernel_matrix(X, X, sigma_f, ell)
    K_noise = [row[:] for row in K]
    for i in range(n):
        K_noise[i][i] += sigma_n * sigma_n

    # alpha = K_noise^-1 y_centred  (via solve)
    y_col: Matrix = [[v] for v in y_centred]
    alpha_col = gauss_jordan_solve(K_noise, y_col)
    alpha = [r[0] for r in alpha_col]

    # Full inverse: solve K_noise * X = I
    identity = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    K_inv = gauss_jordan_solve(K_noise, identity)

    return GPModel(
        X_train=list(X),
        y_train=list(y),
        sigma_f=sigma_f,
        ell=ell,
        sigma_n=sigma_n,
        K_noise=K_noise,
        alpha=alpha,
        K_inv=K_inv,
        y_mean=y_mean,
        n=n,
    )


@dataclass
class GPPrediction:
    x_test: Vector
    mean: Vector
    variance: Vector
    std: Vector
    ci_low_95: Vector
    ci_high_95: Vector
    ci_low_80: Vector
    ci_high_80: Vector


def predict_gp(model: GPModel, X_test: Vector) -> GPPrediction:
    """Predict posterior mean + variance + 80% / 95% credible intervals."""
    mean: Vector = []
    var: Vector = []
    for xs in X_test:
        k_star: Vector = [
            rbf_kernel(xs, xt, model.sigma_f, model.ell) for xt in model.X_train
        ]
        # posterior mean
        post_mean = model.y_mean + sum(k_star[i] * model.alpha[i] for i in range(model.n))
        # posterior variance: k(x*,x*) - k_star^T K_inv k_star
        # compute K_inv @ k_star
        v: Vector = [sum(model.K_inv[i][j] * k_star[j] for j in range(model.n)) for i in range(model.n)]
        post_var = rbf_kernel(xs, xs, model.sigma_f, model.ell) - sum(k_star[i] * v[i] for i in range(model.n))
        post_var = max(post_var, 1e-9)
        mean.append(post_mean)
        var.append(post_var)

    std = [math.sqrt(v) for v in var]
    ci95_lo = [mean[i] - 1.96 * std[i] for i in range(len(mean))]
    ci95_hi = [mean[i] + 1.96 * std[i] for i in range(len(mean))]
    ci80_lo = [mean[i] - 1.28 * std[i] for i in range(len(mean))]
    ci80_hi = [mean[i] + 1.28 * std[i] for i in range(len(mean))]

    return GPPrediction(
        x_test=list(X_test),
        mean=mean,
        variance=var,
        std=std,
        ci_low_95=ci95_lo,
        ci_high_95=ci95_hi,
        ci_low_80=ci80_lo,
        ci_high_80=ci80_hi,
    )


def log_marginal_likelihood(model: GPModel) -> float:
    """log p(y | X, hyperparams).

    LML = -0.5 * y_c^T K_noise^-1 y_c - 0.5 * log|K_noise| - n/2 * log(2 pi)

    Computed via the cached alpha and determinant from the augmented Gauss-Jordan
    reduction. We re-derive the determinant by running Gaussian elimination on a
    copy and tracking pivot products -- cheaper than full Cholesky, sufficient
    for diagnostic display (not used for inference).
    """
    n = model.n
    y_centred = [yi - model.y_mean for yi in model.y_train]
    # quadratic form: y_c . alpha (alpha = K_noise^-1 y_c)
    quad = sum(y_centred[i] * model.alpha[i] for i in range(n))
    # determinant: product of pivots during LU forward pass
    # Use a copy of K_noise; eliminate rows; multiply pivots.
    A = [row[:] for row in model.K_noise]
    det_sign = 1.0
    log_abs_det = 0.0
    for col in range(n):
        # Find pivot
        pivot_row = col
        pivot_val = abs(A[col][col])
        for r in range(col + 1, n):
            if abs(A[r][col]) > pivot_val:
                pivot_val = abs(A[r][col])
                pivot_row = r
        if pivot_val < 1e-12:
            return float("-inf")
        if pivot_row != col:
            A[col], A[pivot_row] = A[pivot_row], A[col]
            det_sign = -det_sign
        pv = A[col][col]
        if pv < 0:
            det_sign = -det_sign
            pv = -pv
        log_abs_det += math.log(pv)
        # Eliminate below
        for r in range(col + 1, n):
            factor = A[r][col] / A[col][col]
            for j in range(col, n):
                A[r][j] -= factor * A[col][j]

    lml = -0.5 * quad - 0.5 * log_abs_det - 0.5 * n * math.log(2.0 * math.pi)
    return lml


# ============================ diagnostics ============================== #


def empirical_coverage(
    model: GPModel, X_holdout: Vector, y_holdout: Vector,
    confidence: float = 0.95,
) -> float:
    """Fraction of holdout points whose true value falls inside the predicted CI."""
    if not X_holdout:
        return 0.0
    pred = predict_gp(model, X_holdout)
    if confidence == 0.95:
        lo, hi = pred.ci_low_95, pred.ci_high_95
    elif confidence == 0.80:
        lo, hi = pred.ci_low_80, pred.ci_high_80
    else:
        # general case: re-scale by z
        from math import sqrt
        z = 1.96 if confidence >= 0.95 else 1.28
        lo = [pred.mean[i] - z * pred.std[i] for i in range(len(pred.mean))]
        hi = [pred.mean[i] + z * pred.std[i] for i in range(len(pred.mean))]
    hits = sum(1 for i, y in enumerate(y_holdout) if lo[i] <= y <= hi[i])
    return hits / len(y_holdout)


def rmse(model: GPModel, X: Vector, y: Vector) -> float:
    pred = predict_gp(model, X)
    sq = sum((pred.mean[i] - y[i]) ** 2 for i in range(len(y)))
    return math.sqrt(sq / max(len(y), 1))


def mean_band_width(pred: GPPrediction, confidence: float = 0.95) -> float:
    if confidence == 0.95:
        widths = [pred.ci_high_95[i] - pred.ci_low_95[i] for i in range(len(pred.mean))]
    else:
        widths = [pred.ci_high_80[i] - pred.ci_low_80[i] for i in range(len(pred.mean))]
    return fmean(widths) if widths else 0.0
