"""stagetrack — Hidden Markov Model 純函式 (no I/O, no LLM).

責任:
  - Forward algorithm: 計算 α_t(i) = P(obs_1..t, state_t = i)
  - Backward algorithm: 計算 β_t(i) = P(obs_{t+1..T} | state_t = i)
  - Posterior: γ_t(i) = P(state_t = i | obs_1..T) = α × β / norm
  - Viterbi: 求最可能 state sequence

100% stdlib(只用 math + dataclass)。

模型參數:
  - 4 個 hidden states: Hot / Warm / Cold / Closed (absorbing)
  - 5 個觀察值: activity_level 0-4
    - 0 = 無活動(無詢問 / 帶看 / 議價)
    - 1 = 低活動(1-2 詢問,無帶看)
    - 2 = 中活動(3-5 詢問 + 1 帶看)
    - 3 = 高活動(6+ 詢問 + 2+ 帶看)
    - 4 = 議價中(議價 + 帶看)
  - Transition matrix A (4×4),Emission B (4×5),Initial π (4)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ===== HMM 參數(domain knowledge,基於台灣房仲訪談經驗)=====

STATES = ("Hot", "Warm", "Cold", "Closed")
N_STATES = 4

# 觀察值 (0-4)
OBSERVATION_LABELS = (
    "無活動",          # 0
    "低活動",          # 1
    "中活動",          # 2
    "高活動",          # 3
    "議價中",          # 4
)
N_OBSERVATIONS = 5


# 初始分布 π:新 listing 不太可能一開始就 Closed
INITIAL_DIST = [0.30, 0.40, 0.30, 0.0]


# Transition matrix A[i][j] = P(state_{t+1} = j | state_t = i)
# 行 = 來自;欄 = 去往
TRANSITION_MATRIX = [
    # Hot,  Warm, Cold, Closed
    [0.55, 0.25, 0.08, 0.12],   # Hot → mostly stay Hot or 升級成交
    [0.18, 0.55, 0.20, 0.07],   # Warm → 可上可下
    [0.06, 0.15, 0.70, 0.09],   # Cold → 多半繼續 Cold 或撤回
    [0.00, 0.00, 0.00, 1.00],   # Closed = absorbing
]


# Emission matrix B[i][k] = P(observation = k | state = i)
EMISSION_MATRIX = [
    # obs_0  obs_1  obs_2  obs_3  obs_4
    [0.03,  0.07,  0.20,  0.40,  0.30],   # Hot — 多半中-高活動 / 議價
    [0.10,  0.30,  0.40,  0.18,  0.02],   # Warm — 多半低-中活動
    [0.50,  0.35,  0.12,  0.03,  0.00],   # Cold — 多半無-低活動
    [0.95,  0.04,  0.01,  0.00,  0.00],   # Closed — 幾乎無活動
]


# ===== Forward algorithm =====
@dataclass
class ForwardResult:
    """Forward algorithm 結果。alpha[t][i] = P(obs_1..t, state_t = i)。"""
    alpha: list[list[float]]                 # T × N
    log_likelihood: float                    # log P(obs_1..T)
    scaling_factors: list[float]             # 每個 t 的歸一化常數 c_t


def forward(observations: list[int]) -> ForwardResult:
    """跑 forward algorithm,用 scaling 避免數值溢位。"""
    T = len(observations)
    if T == 0:
        return ForwardResult(alpha=[], log_likelihood=0.0, scaling_factors=[])

    alpha = [[0.0] * N_STATES for _ in range(T)]
    scaling = [0.0] * T

    # t = 0
    for i in range(N_STATES):
        alpha[0][i] = INITIAL_DIST[i] * EMISSION_MATRIX[i][observations[0]]
    c0 = sum(alpha[0])
    if c0 > 0:
        for i in range(N_STATES):
            alpha[0][i] /= c0
        scaling[0] = c0
    else:
        scaling[0] = 1e-30

    # t = 1..T-1
    for t in range(1, T):
        for j in range(N_STATES):
            alpha[t][j] = sum(alpha[t - 1][i] * TRANSITION_MATRIX[i][j]
                              for i in range(N_STATES)) * EMISSION_MATRIX[j][observations[t]]
        ct = sum(alpha[t])
        if ct > 0:
            for j in range(N_STATES):
                alpha[t][j] /= ct
            scaling[t] = ct
        else:
            scaling[t] = 1e-30

    log_likelihood = sum(math.log(s) for s in scaling if s > 0)
    return ForwardResult(alpha=alpha, log_likelihood=log_likelihood, scaling_factors=scaling)


# ===== Backward algorithm =====
def backward(observations: list[int], scaling_factors: list[float]) -> list[list[float]]:
    """跑 backward algorithm(用 forward 的 scaling 維持數值一致)。"""
    T = len(observations)
    if T == 0:
        return []
    beta = [[0.0] * N_STATES for _ in range(T)]

    # t = T-1
    for i in range(N_STATES):
        beta[T - 1][i] = 1.0 / scaling_factors[T - 1] if scaling_factors[T - 1] > 0 else 0.0

    # t = T-2..0
    for t in range(T - 2, -1, -1):
        for i in range(N_STATES):
            beta[t][i] = sum(
                TRANSITION_MATRIX[i][j] * EMISSION_MATRIX[j][observations[t + 1]] * beta[t + 1][j]
                for j in range(N_STATES)
            )
            if scaling_factors[t] > 0:
                beta[t][i] /= scaling_factors[t]

    return beta


# ===== Posterior =====
def compute_posterior(alpha: list[list[float]], beta: list[list[float]]) -> list[list[float]]:
    """gamma_t(i) = α_t(i) × β_t(i) / norm — P(state_t = i | obs_1..T)。"""
    T = len(alpha)
    gamma = [[0.0] * N_STATES for _ in range(T)]
    for t in range(T):
        total = sum(alpha[t][i] * beta[t][i] for i in range(N_STATES))
        if total > 0:
            for i in range(N_STATES):
                gamma[t][i] = alpha[t][i] * beta[t][i] / total
    return gamma


# ===== Viterbi =====
@dataclass
class ViterbiResult:
    state_sequence: list[int]                # 最可能 state sequence
    state_labels: list[str]
    log_probability: float                   # log P(best path, observations)


def viterbi(observations: list[int]) -> ViterbiResult:
    """求最可能的 state sequence。"""
    T = len(observations)
    if T == 0:
        return ViterbiResult(state_sequence=[], state_labels=[], log_probability=0.0)

    # delta_t(i) = max prob of any path ending in state i at time t
    log_delta = [[-math.inf] * N_STATES for _ in range(T)]
    psi = [[0] * N_STATES for _ in range(T)]  # backpointer

    # t = 0
    for i in range(N_STATES):
        if INITIAL_DIST[i] > 0 and EMISSION_MATRIX[i][observations[0]] > 0:
            log_delta[0][i] = math.log(INITIAL_DIST[i]) + math.log(EMISSION_MATRIX[i][observations[0]])

    # t = 1..T-1
    for t in range(1, T):
        for j in range(N_STATES):
            if EMISSION_MATRIX[j][observations[t]] <= 0:
                continue
            best_score = -math.inf
            best_i = 0
            for i in range(N_STATES):
                if TRANSITION_MATRIX[i][j] <= 0:
                    continue
                score = log_delta[t - 1][i] + math.log(TRANSITION_MATRIX[i][j])
                if score > best_score:
                    best_score = score
                    best_i = i
            log_delta[t][j] = best_score + math.log(EMISSION_MATRIX[j][observations[t]])
            psi[t][j] = best_i

    # Backtrack
    best_final_state = max(range(N_STATES), key=lambda i: log_delta[T - 1][i])
    log_prob = log_delta[T - 1][best_final_state]

    state_seq = [0] * T
    state_seq[T - 1] = best_final_state
    for t in range(T - 2, -1, -1):
        state_seq[t] = psi[t + 1][state_seq[t + 1]]

    labels = [STATES[s] for s in state_seq]
    return ViterbiResult(state_sequence=state_seq, state_labels=labels, log_probability=log_prob)


# ===== Top-level analysis =====
@dataclass
class ListingAnalysis:
    listing_id: str
    observations: list[int]
    observation_labels: list[str]
    viterbi_states: list[str]
    posterior: list[list[float]]            # T × 4
    current_state: str
    current_state_prob: float
    current_state_distribution: dict[str, float]
    state_transitions: list[str]            # human-readable e.g. ["W2", "Hot W3", ...]
    weeks_in_current_state: int             # 最近連續幾週同 state


def analyze_listing(listing_id: str, observations: list[int]) -> ListingAnalysis:
    """跑完整 forward-backward + Viterbi。"""
    fwd = forward(observations)
    bwd = backward(observations, fwd.scaling_factors)
    posterior = compute_posterior(fwd.alpha, bwd)
    viterbi_result = viterbi(observations)

    # Current state = last Viterbi state
    current_idx = viterbi_result.state_sequence[-1]
    current_state = STATES[current_idx]
    current_prob = posterior[-1][current_idx]
    current_dist = {STATES[i]: round(posterior[-1][i], 4) for i in range(N_STATES)}

    # State transitions(human-readable)
    transitions: list[str] = []
    prev = None
    for week, state_idx in enumerate(viterbi_result.state_sequence, 1):
        state = STATES[state_idx]
        if state != prev:
            transitions.append(f"W{week} → {state}")
            prev = state

    # Weeks in current state
    weeks_current = 0
    for s in reversed(viterbi_result.state_sequence):
        if s == current_idx:
            weeks_current += 1
        else:
            break

    return ListingAnalysis(
        listing_id=listing_id,
        observations=observations,
        observation_labels=[OBSERVATION_LABELS[o] for o in observations],
        viterbi_states=viterbi_result.state_labels,
        posterior=posterior,
        current_state=current_state,
        current_state_prob=round(current_prob, 4),
        current_state_distribution=current_dist,
        state_transitions=transitions,
        weeks_in_current_state=weeks_current,
    )
