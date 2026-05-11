"""Q-learning with linear function approximation -- pure stdlib.

Classic on-policy / off-policy RL with linear value function:

    Q(s, a) = w_a · φ(s)

where φ(s) ∈ R^d is the state-feature vector and w_a is a learned
weight vector for each discrete action a.

TD(0) update on observed (s, a, r, s'):

    δ      = r + γ · max_{a'} Q(s', a') - Q(s, a)
    w_a    ← w_a + α · δ · φ(s)

Training uses simulated shifts: a stream of orders drawn from a logged
sample, ε-greedy policy choosing accept/decline at each step.

Pure stdlib: math + random + statistics + dataclasses.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from statistics import fmean


# ============================ state featurisation ===================== #


@dataclass(frozen=True)
class Order:
    fare_ntd: float
    distance_km: float
    duration_min: float
    surge: float          # 1.0 = no surge
    pickup_zone_density: float   # 0..1
    traffic_level: int    # 1..5
    hour: int             # 0..23
    is_weekend: bool


def normalise_features(order: Order) -> list[float]:
    """8-dim feature vector for an order in [0, 1]-ish range.

    Centring matters less than bounded magnitude for stable linear Q updates.
    """
    return [
        order.hour / 24.0,
        1.0 if order.is_weekend else 0.0,
        min(order.fare_ntd / 600.0, 2.0),       # NT$0..1200
        min(order.distance_km / 30.0, 2.0),     # 0..60 km
        min(order.duration_min / 60.0, 2.0),    # 0..120 min
        (order.surge - 1.0) / 2.0,              # surge 1..3
        order.pickup_zone_density,
        (order.traffic_level - 1) / 4.0,        # 1..5 -> 0..1
        1.0,                                    # bias term
    ]


N_FEATURES = 9  # 8 + bias
ACTIONS = (0, 1)  # 0 = decline, 1 = accept


# ============================ reward model ============================ #


def compute_reward(order: Order, action: int,
                    fuel_cost_per_km: float = 2.5,
                    opportunity_cost_per_min: float = 6.0,
                    decline_penalty: float = 10.0) -> float:
    """Realised reward for taking the action on this order.

    Accept (1):  fare * surge - fuel_cost(distance) - opportunity_cost(duration)
    Decline (0): -decline_penalty (small wait/lost-rating cost)

    These are *defaults* the driver can override (different fuel prices, etc.).
    The point is to give a real signed reward for Q-learning to optimise.
    """
    if action == 1:
        gross = order.fare_ntd * order.surge
        fuel = fuel_cost_per_km * order.distance_km
        opp = opportunity_cost_per_min * order.duration_min
        return gross - fuel - opp
    else:
        return -decline_penalty


# ============================ linear Q model ========================== #


@dataclass
class LinearQ:
    n_features: int
    n_actions: int
    weights: list[list[float]] = field(default_factory=list)

    def __post_init__(self):
        if not self.weights:
            self.weights = [[0.0] * self.n_features for _ in range(self.n_actions)]

    def value(self, state: list[float], action: int) -> float:
        return sum(w * f for w, f in zip(self.weights[action], state))

    def values_for_all_actions(self, state: list[float]) -> list[float]:
        return [self.value(state, a) for a in range(self.n_actions)]

    def greedy_action(self, state: list[float]) -> int:
        qs = self.values_for_all_actions(state)
        best = 0
        best_q = qs[0]
        for a in range(1, self.n_actions):
            if qs[a] > best_q:
                best_q = qs[a]
                best = a
        return best

    def update(self, state: list[float], action: int, td_error: float,
                alpha: float) -> None:
        for i in range(self.n_features):
            self.weights[action][i] += alpha * td_error * state[i]


# ============================ training loop ============================ #


@dataclass
class TrainingDiagnostics:
    episode_returns: list[float]
    final_td_error: float
    n_accepts: int
    n_declines: int


def train_q_learning(
    orders: list[Order],
    n_episodes: int = 200,
    alpha: float = 0.01,
    gamma: float = 0.90,
    epsilon_start: float = 0.5,
    epsilon_end: float = 0.05,
    seed: int = 42,
) -> tuple[LinearQ, TrainingDiagnostics]:
    """Train linear-Q over n_episodes of resampled orders.

    Each episode: shuffle orders, walk through, ε-greedy, TD(0) update.
    ε decays linearly from epsilon_start to epsilon_end.
    """
    if len(orders) < 2:
        raise ValueError("train_q_learning needs at least 2 orders")
    rng = random.Random(seed)
    q = LinearQ(n_features=N_FEATURES, n_actions=len(ACTIONS))

    episode_returns: list[float] = []
    n_accepts = 0
    n_declines = 0
    final_td_error = 0.0

    for ep in range(n_episodes):
        epsilon = epsilon_start - (epsilon_start - epsilon_end) * (ep / max(n_episodes - 1, 1))
        order_indices = list(range(len(orders)))
        rng.shuffle(order_indices)
        episode_return = 0.0

        for i, idx in enumerate(order_indices):
            order = orders[idx]
            s = normalise_features(order)
            # epsilon-greedy
            if rng.random() < epsilon:
                a = rng.choice(ACTIONS)
            else:
                a = q.greedy_action(s)
            r = compute_reward(order, a)
            episode_return += r
            if a == 1:
                n_accepts += 1
            else:
                n_declines += 1

            # Bootstrap from next state (next order in this episode) if available.
            if i + 1 < len(order_indices):
                next_order = orders[order_indices[i + 1]]
                s_next = normalise_features(next_order)
                next_q = max(q.values_for_all_actions(s_next))
            else:
                next_q = 0.0
            td_target = r + gamma * next_q
            td_error = td_target - q.value(s, a)
            final_td_error = td_error
            q.update(s, a, td_error, alpha)

        episode_returns.append(episode_return)

    diag = TrainingDiagnostics(
        episode_returns=episode_returns,
        final_td_error=final_td_error,
        n_accepts=n_accepts,
        n_declines=n_declines,
    )
    return q, diag


# ============================ inference =============================== #


@dataclass
class OrderRecommendation:
    action: int          # 0 = decline, 1 = accept
    q_accept: float
    q_decline: float
    expected_reward_if_accept: float
    margin: float        # q_accept - q_decline; positive => accept stronger
    rationale: str


def recommend(q: LinearQ, order: Order) -> OrderRecommendation:
    """Argmax Q + bookkeeping for the CLI."""
    s = normalise_features(order)
    q_acc = q.value(s, 1)
    q_dec = q.value(s, 0)
    accept = q_acc > q_dec
    margin = q_acc - q_dec
    expected = compute_reward(order, 1)
    if accept:
        if margin > 200:
            rationale = "強烈接單 -- Q 差距大 + 預估淨利夠高"
        elif margin > 50:
            rationale = "建議接單 -- Q 微優"
        else:
            rationale = "勉強接 -- Q 略勝, 但有議價 / 等更好單空間"
    else:
        if margin < -200:
            rationale = "明顯拒接 -- 訂單條件差 (距離 / 時段 / 路況)"
        elif margin < -50:
            rationale = "建議拒接 -- Q 較負"
        else:
            rationale = "看心情 -- Q 接近, 可看現場狀況再決定"
    return OrderRecommendation(
        action=1 if accept else 0,
        q_accept=q_acc,
        q_decline=q_dec,
        expected_reward_if_accept=expected,
        margin=margin,
        rationale=rationale,
    )


def policy_summary(q: LinearQ) -> dict:
    """Return weights and high-level signs per action for diagnostics."""
    out = {}
    feature_names = [
        "hour", "is_weekend", "fare_norm", "distance_norm", "duration_norm",
        "surge_norm", "zone_density", "traffic_norm", "bias",
    ]
    for a in range(len(ACTIONS)):
        per_action = []
        for fname, w in zip(feature_names, q.weights[a]):
            per_action.append((fname, w))
        per_action.sort(key=lambda kv: -abs(kv[1]))
        out[a] = per_action
    return out


# ============================ replay 模擬 ============================ #


def replay_policy_on_log(q: LinearQ, orders: list[Order]) -> dict:
    """Compare learned policy vs naive (accept-all) on a logged set."""
    learned_return = 0.0
    naive_return = 0.0
    learned_n_accept = 0
    for o in orders:
        s = normalise_features(o)
        a = q.greedy_action(s)
        learned_return += compute_reward(o, a)
        if a == 1:
            learned_n_accept += 1
        naive_return += compute_reward(o, 1)
    return {
        "learned_return": learned_return,
        "naive_return": naive_return,
        "delta": learned_return - naive_return,
        "learned_n_accept": learned_n_accept,
        "n_orders": len(orders),
    }
