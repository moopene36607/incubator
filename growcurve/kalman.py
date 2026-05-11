"""growcurve — Kalman filter + RTS smoother for infant weight tracking (pure stdlib).

Kalman (1960) recursive Bayesian state estimation for linear-Gaussian systems.

State:  x_t = [weight_kg, velocity_kg_per_day]^T
Process: x_t = F × x_{t-1} + w,  F = [[1, dt], [0, 1]],  w ~ N(0, Q)
Observation: y_t = H × x_t + v,  H = [1, 0],  v ~ N(0, R)

Forward pass (filtering):
  Predict:  x̂_{t|t-1} = F × x̂_{t-1|t-1}
            P_{t|t-1} = F × P_{t-1|t-1} × F^T + Q
  Update:   K_t = P_{t|t-1} × H^T × (H × P × H^T + R)^-1
            x̂_{t|t} = x̂_{t|t-1} + K_t × (y_t - H × x̂_{t|t-1})
            P_{t|t} = (I - K_t × H) × P_{t|t-1}

Backward pass (RTS smoother):
  G_t = P_{t|t} × F^T × P_{t+1|t}^-1
  x̂_{t|T} = x̂_{t|t} + G_t × (x̂_{t+1|T} - x̂_{t+1|t})

Pure stdlib (math + dataclass). 2×2 matrix operations hand-coded.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ============== 2×2 matrix utilities ==============
def mat2x2_mul(A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
    """2×2 matrix multiplication."""
    return [
        [A[0][0] * B[0][0] + A[0][1] * B[1][0], A[0][0] * B[0][1] + A[0][1] * B[1][1]],
        [A[1][0] * B[0][0] + A[1][1] * B[1][0], A[1][0] * B[0][1] + A[1][1] * B[1][1]],
    ]


def mat2x2_transpose(A: list[list[float]]) -> list[list[float]]:
    return [[A[0][0], A[1][0]], [A[0][1], A[1][1]]]


def mat2x2_add(A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
    return [[A[0][0] + B[0][0], A[0][1] + B[0][1]],
            [A[1][0] + B[1][0], A[1][1] + B[1][1]]]


def mat2x2_sub(A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
    return [[A[0][0] - B[0][0], A[0][1] - B[0][1]],
            [A[1][0] - B[1][0], A[1][1] - B[1][1]]]


def mat2x2_inv(A: list[list[float]]) -> list[list[float]]:
    """Inverse of 2×2 matrix. Raises if singular."""
    det = A[0][0] * A[1][1] - A[0][1] * A[1][0]
    if abs(det) < 1e-12:
        raise ValueError("Singular matrix")
    return [[A[1][1] / det, -A[0][1] / det],
            [-A[1][0] / det, A[0][0] / det]]


def mat2x2_vec(A: list[list[float]], v: list[float]) -> list[float]:
    return [A[0][0] * v[0] + A[0][1] * v[1],
            A[1][0] * v[0] + A[1][1] * v[1]]


I2 = [[1.0, 0.0], [0.0, 1.0]]


# ============== Domain types ==============
@dataclass
class Measurement:
    day_idx: int                # 0-indexed days from start
    weight_kg: float            # observed weight
    note: str = ""              # 量秤條件 (餵奶前 / 後 etc.)


@dataclass
class KalmanResult:
    days: list[int]
    raw_measurements: list[float]
    filtered_weight: list[float]              # forward pass estimate
    filtered_velocity: list[float]            # forward pass velocity (kg/day)
    smoothed_weight: list[float]              # RTS smoothed
    smoothed_velocity: list[float]
    filtered_var: list[float]                 # P[0][0] forward
    smoothed_var: list[float]                 # smoothed variance


@dataclass
class KalmanConfig:
    dt_days: float = 1.0                      # time step (1 day)
    process_noise_weight: float = 0.0001      # σ²_w 體重隨機波動 (kg²)
    process_noise_velocity: float = 0.000001  # σ²_v 增重速率隨機波動 (kg/day)²
    obs_noise: float = 0.01                   # σ²_obs 量秤噪音 (kg²) = 0.1 kg std (typical home scale)
    init_weight_var: float = 1.0              # 初始體重不確定性
    init_velocity_var: float = 0.0001         # 初始 velocity 不確定性


# ============== Kalman filter forward pass ==============
def kalman_forward(measurements: list[Measurement],
                    config: KalmanConfig) -> tuple[list[list[float]], list[list[list[float]]], list[list[float]]]:
    """Returns (state_estimates, covariance_matrices, predicted_states)."""
    dt = config.dt_days
    F = [[1.0, dt], [0.0, 1.0]]
    H_row = [1.0, 0.0]
    Q = [[config.process_noise_weight, 0.0], [0.0, config.process_noise_velocity]]
    R = config.obs_noise

    # Initial state: first measurement, zero velocity
    x = [measurements[0].weight_kg, 0.0]
    P = [[config.init_weight_var, 0.0], [0.0, config.init_velocity_var]]

    state_history = [x[:]]
    cov_history = [[row[:] for row in P]]
    pred_history = [None]    # First step has no prediction

    for k in range(1, len(measurements)):
        # Predict
        x_pred = mat2x2_vec(F, x)
        P_pred = mat2x2_add(mat2x2_mul(mat2x2_mul(F, P), mat2x2_transpose(F)), Q)
        pred_history.append((x_pred[:], [row[:] for row in P_pred]))

        # Update
        y = measurements[k].weight_kg
        innov = y - (H_row[0] * x_pred[0] + H_row[1] * x_pred[1])
        S = H_row[0] * (H_row[0] * P_pred[0][0] + H_row[1] * P_pred[0][1]) + \
            H_row[1] * (H_row[0] * P_pred[1][0] + H_row[1] * P_pred[1][1]) + R
        # K = P_pred × H^T / S (vector since H is row)
        K = [P_pred[0][0] / S, P_pred[1][0] / S]

        x = [x_pred[0] + K[0] * innov, x_pred[1] + K[1] * innov]
        # P = (I - K × H) × P_pred where K is column, H is row
        # K × H = [[K[0]*1, K[0]*0], [K[1]*1, K[1]*0]]
        KH = [[K[0], 0.0], [K[1], 0.0]]
        IminusKH = mat2x2_sub(I2, KH)
        P = mat2x2_mul(IminusKH, P_pred)

        state_history.append(x[:])
        cov_history.append([row[:] for row in P])

    return state_history, cov_history, pred_history


# ============== RTS smoother (backward pass) ==============
def rts_smoother(state_hist: list[list[float]],
                  cov_hist: list[list[list[float]]],
                  pred_hist: list,
                  config: KalmanConfig) -> tuple[list[list[float]], list[list[list[float]]]]:
    """Rauch-Tung-Striebel backward smoothing."""
    dt = config.dt_days
    F = [[1.0, dt], [0.0, 1.0]]
    T = len(state_hist)

    smoothed_x = [None] * T
    smoothed_P = [None] * T
    smoothed_x[T - 1] = state_hist[T - 1][:]
    smoothed_P[T - 1] = [row[:] for row in cov_hist[T - 1]]

    for t in range(T - 2, -1, -1):
        if pred_hist[t + 1] is None:
            smoothed_x[t] = state_hist[t][:]
            smoothed_P[t] = [row[:] for row in cov_hist[t]]
            continue
        x_pred_t1, P_pred_t1 = pred_hist[t + 1]
        try:
            P_pred_inv = mat2x2_inv(P_pred_t1)
        except ValueError:
            smoothed_x[t] = state_hist[t][:]
            smoothed_P[t] = [row[:] for row in cov_hist[t]]
            continue

        Pt_FT = mat2x2_mul(cov_hist[t], mat2x2_transpose(F))
        G = mat2x2_mul(Pt_FT, P_pred_inv)

        # x_smooth = x_filt + G × (x_smooth_next - x_pred_next)
        diff = [smoothed_x[t + 1][0] - x_pred_t1[0],
                smoothed_x[t + 1][1] - x_pred_t1[1]]
        smoothed_x[t] = [state_hist[t][0] + G[0][0] * diff[0] + G[0][1] * diff[1],
                          state_hist[t][1] + G[1][0] * diff[0] + G[1][1] * diff[1]]

        # P_smooth = P_filt + G × (P_smooth_next - P_pred_next) × G^T
        Pdiff = mat2x2_sub(smoothed_P[t + 1], P_pred_t1)
        smoothed_P[t] = mat2x2_add(cov_hist[t],
                                     mat2x2_mul(mat2x2_mul(G, Pdiff), mat2x2_transpose(G)))

    return smoothed_x, smoothed_P


# ============== Main pipeline ==============
def kalman_pipeline(measurements: list[Measurement],
                     config: KalmanConfig | None = None) -> KalmanResult:
    if config is None:
        config = KalmanConfig()
    state_hist, cov_hist, pred_hist = kalman_forward(measurements, config)
    smoothed_x, smoothed_P = rts_smoother(state_hist, cov_hist, pred_hist, config)

    return KalmanResult(
        days=[m.day_idx for m in measurements],
        raw_measurements=[m.weight_kg for m in measurements],
        filtered_weight=[round(x[0], 4) for x in state_hist],
        filtered_velocity=[round(x[1], 5) for x in state_hist],
        smoothed_weight=[round(x[0], 4) for x in smoothed_x],
        smoothed_velocity=[round(x[1], 5) for x in smoothed_x],
        filtered_var=[round(P[0][0], 6) for P in cov_hist],
        smoothed_var=[round(P[0][0], 6) for P in smoothed_P],
    )


# ============== WHO growth standards (simplified 0-24 month) ==============
# Source: WHO Child Growth Standards, kg, P50, by age in months
WHO_BOY_P50_KG = {
    0: 3.3, 1: 4.5, 2: 5.6, 3: 6.4, 4: 7.0, 5: 7.5,
    6: 7.9, 9: 8.9, 12: 9.6, 15: 10.3, 18: 10.9, 21: 11.5, 24: 12.2,
}
WHO_GIRL_P50_KG = {
    0: 3.2, 1: 4.2, 2: 5.1, 3: 5.8, 4: 6.4, 5: 6.9,
    6: 7.3, 9: 8.2, 12: 8.9, 15: 9.6, 18: 10.2, 21: 10.9, 24: 11.5,
}
# Σ_age standard deviation grows with age (approx)
WHO_SIGMA_KG_BY_MONTH = {
    0: 0.5, 3: 0.7, 6: 0.9, 12: 1.1, 18: 1.2, 24: 1.3,
}


def interpolate_who(month: float, table: dict[int, float]) -> float:
    """Linear interpolation between WHO age points."""
    ages = sorted(table.keys())
    if month <= ages[0]:
        return table[ages[0]]
    if month >= ages[-1]:
        return table[ages[-1]]
    for i in range(len(ages) - 1):
        if ages[i] <= month <= ages[i + 1]:
            t = (month - ages[i]) / (ages[i + 1] - ages[i])
            return table[ages[i]] * (1 - t) + table[ages[i + 1]] * t
    return table[ages[-1]]


def who_percentile(weight_kg: float, age_months: float, sex: str) -> tuple[float, str]:
    """Estimate percentile + tier label for given weight + age + sex."""
    table = WHO_BOY_P50_KG if sex == "boy" else WHO_GIRL_P50_KG
    p50 = interpolate_who(age_months, table)
    sigma = interpolate_who(age_months, WHO_SIGMA_KG_BY_MONTH)
    z = (weight_kg - p50) / sigma
    # Approximate percentile via standard normal CDF
    # CDF(z) = 0.5 × (1 + erf(z / sqrt(2)))
    pct = 0.5 * (1 + math.erf(z / math.sqrt(2))) * 100
    tier = (
        "P3 以下 (顯著偏輕)" if pct < 3 else
        "P3-15 (偏輕)" if pct < 15 else
        "P15-50 (低標)" if pct < 50 else
        "P50-85 (中標)" if pct < 85 else
        "P85-97 (偏重)" if pct < 97 else
        "P97 以上 (顯著偏重)"
    )
    return round(pct, 1), tier


# ============== Anomaly detection ==============
@dataclass
class GrowthFlag:
    flag_type: str          # 'plateau' / 'rapid_loss' / 'below_p3' / 'velocity_below_normal'
    severity: str           # 'mild' / 'moderate' / 'urgent'
    description: str
    day_idx: int
    value: float


def detect_anomalies(result: KalmanResult,
                       age_months_at_start: float,
                       sex: str,
                       min_normal_velocity_g_day: float = 15.0) -> list[GrowthFlag]:
    """Identify concerning patterns in the smoothed growth curve.

    Default normal velocity ~ 15-30 g/day in months 0-6. Use lower threshold
    for months 6+ since growth naturally slows.
    """
    flags = []

    # Last 5 days smoothed velocity (g/day)
    if len(result.smoothed_velocity) >= 5:
        recent_velocity_kg_day = sum(result.smoothed_velocity[-5:]) / 5
        recent_velocity_g_day = recent_velocity_kg_day * 1000

        # Adjust expected velocity by age
        if age_months_at_start < 3:
            expected = 25.0
        elif age_months_at_start < 6:
            expected = 18.0
        elif age_months_at_start < 12:
            expected = 12.0
        else:
            expected = 7.0

        if recent_velocity_g_day < expected * 0.5:
            flags.append(GrowthFlag(
                flag_type="velocity_below_normal",
                severity="urgent",
                description=f"近 5 天 smoothed 增重速率 {recent_velocity_g_day:.1f} g/day, 低於該年齡正常 {expected:.0f} g/day 的 50%",
                day_idx=result.days[-1],
                value=recent_velocity_g_day,
            ))
        elif recent_velocity_g_day < expected * 0.75:
            flags.append(GrowthFlag(
                flag_type="velocity_below_normal",
                severity="moderate",
                description=f"近 5 天 smoothed 增重速率 {recent_velocity_g_day:.1f} g/day, 低於該年齡正常 {expected:.0f} g/day 的 75%",
                day_idx=result.days[-1],
                value=recent_velocity_g_day,
            ))

    # Plateau / weight loss
    if len(result.smoothed_weight) >= 7:
        # 7-day weight change
        delta_7d = result.smoothed_weight[-1] - result.smoothed_weight[-7]
        if delta_7d < -0.05:
            flags.append(GrowthFlag(
                flag_type="rapid_loss",
                severity="urgent",
                description=f"7 天內 smoothed 體重下降 {abs(delta_7d) * 1000:.0f} g (可能脫水 / 急性病)",
                day_idx=result.days[-1],
                value=delta_7d,
            ))
        elif abs(delta_7d) < 0.02:
            flags.append(GrowthFlag(
                flag_type="plateau",
                severity="moderate",
                description=f"7 天 smoothed 體重幾乎沒變化 ({delta_7d * 1000:+.0f} g) — 平台期",
                day_idx=result.days[-1],
                value=delta_7d,
            ))

    # Percentile check at end
    final_weight = result.smoothed_weight[-1]
    final_age_months = age_months_at_start + result.days[-1] / 30
    pct, tier = who_percentile(final_weight, final_age_months, sex)
    if pct < 3:
        flags.append(GrowthFlag(
            flag_type="below_p3",
            severity="urgent",
            description=f"目前體重 {final_weight:.2f} kg @ {final_age_months:.1f} 月齡 {sex} = P{pct:.1f} ({tier})",
            day_idx=result.days[-1],
            value=pct,
        ))

    return flags
