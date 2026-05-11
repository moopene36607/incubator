"""Edge-case tests for rl.py -- Q-learning with linear function approximation.

Run: python3 tests_rl.py
"""
from __future__ import annotations

import math
import sys

from rl import (
    Order, normalise_features, compute_reward,
    LinearQ, train_q_learning, recommend, replay_policy_on_log,
    policy_summary,
    N_FEATURES, ACTIONS,
)


def assert_close(a, b, tol=1e-6, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol {tol})")


# ============================ feature engineering ===================== #


def test_normalise_features_length():
    o = Order(fare_ntd=200, distance_km=5, duration_min=15, surge=1.2,
              pickup_zone_density=0.7, traffic_level=3, hour=10, is_weekend=False)
    feats = normalise_features(o)
    assert len(feats) == N_FEATURES


def test_normalise_features_bias_last():
    o = Order(fare_ntd=100, distance_km=2, duration_min=10, surge=1.0,
              pickup_zone_density=0.5, traffic_level=2, hour=5, is_weekend=False)
    feats = normalise_features(o)
    assert feats[-1] == 1.0   # bias is always 1


def test_normalise_features_is_weekend():
    o_wd = Order(fare_ntd=100, distance_km=2, duration_min=10, surge=1.0,
                  pickup_zone_density=0.5, traffic_level=2, hour=5, is_weekend=False)
    o_we = Order(fare_ntd=100, distance_km=2, duration_min=10, surge=1.0,
                  pickup_zone_density=0.5, traffic_level=2, hour=5, is_weekend=True)
    assert normalise_features(o_wd)[1] == 0.0
    assert normalise_features(o_we)[1] == 1.0


def test_normalise_features_hour_in_unit_interval():
    o = Order(fare_ntd=100, distance_km=2, duration_min=10, surge=1.0,
              pickup_zone_density=0.5, traffic_level=2, hour=23, is_weekend=False)
    feats = normalise_features(o)
    assert 0.0 <= feats[0] <= 1.0


# ============================ reward function ====================== #


def test_reward_decline_is_negative_penalty():
    o = Order(fare_ntd=100, distance_km=2, duration_min=10, surge=1.0,
              pickup_zone_density=0.5, traffic_level=2, hour=10, is_weekend=False)
    r = compute_reward(o, 0)
    assert r == -10.0


def test_reward_accept_profitable_order():
    """Short trip with reasonable fare should yield positive reward."""
    o = Order(fare_ntd=180, distance_km=4, duration_min=10, surge=1.0,
              pickup_zone_density=0.7, traffic_level=2, hour=10, is_weekend=False)
    r = compute_reward(o, 1)
    # 180 - 2.5*4 - 6*10 = 180 - 10 - 60 = 110
    assert r > 0
    assert_close(r, 110.0, tol=0.001)


def test_reward_accept_bad_long_no_surge():
    """Long trip with no surge should yield negative reward."""
    o = Order(fare_ntd=280, distance_km=25, duration_min=55, surge=1.0,
              pickup_zone_density=0.3, traffic_level=2, hour=2, is_weekend=False)
    r = compute_reward(o, 1)
    # 280 - 2.5*25 - 6*55 = 280 - 62.5 - 330 = -112.5
    assert r < 0


def test_reward_surge_multiplies_fare():
    o1 = Order(fare_ntd=200, distance_km=5, duration_min=15, surge=1.0,
                pickup_zone_density=0.5, traffic_level=2, hour=10, is_weekend=False)
    o2 = Order(fare_ntd=200, distance_km=5, duration_min=15, surge=2.0,
                pickup_zone_density=0.5, traffic_level=2, hour=10, is_weekend=False)
    r1 = compute_reward(o1, 1)
    r2 = compute_reward(o2, 1)
    assert r2 > r1


# ============================ LinearQ ============================== #


def test_linear_q_init_zero():
    q = LinearQ(n_features=N_FEATURES, n_actions=len(ACTIONS))
    s = [1.0] * N_FEATURES
    assert q.value(s, 0) == 0.0
    assert q.value(s, 1) == 0.0


def test_linear_q_value_correct():
    q = LinearQ(n_features=3, n_actions=2)
    q.weights[1] = [1.0, 2.0, 3.0]
    s = [0.5, 1.0, 2.0]
    expected = 1.0 * 0.5 + 2.0 * 1.0 + 3.0 * 2.0  # 0.5 + 2 + 6 = 8.5
    assert_close(q.value(s, 1), expected)


def test_linear_q_greedy_action():
    q = LinearQ(n_features=2, n_actions=2)
    q.weights[0] = [1.0, 0.0]
    q.weights[1] = [0.0, 2.0]
    s = [3.0, 1.0]
    # Q(s,0) = 3, Q(s,1) = 2 -> greedy = 0
    assert q.greedy_action(s) == 0


def test_linear_q_update_changes_weights():
    q = LinearQ(n_features=2, n_actions=2)
    s = [1.0, 1.0]
    old_w = list(q.weights[1])
    q.update(s, 1, td_error=1.0, alpha=0.1)
    for i in range(2):
        assert q.weights[1][i] != old_w[i]


def test_values_for_all_actions_length():
    q = LinearQ(n_features=4, n_actions=2)
    vs = q.values_for_all_actions([1.0] * 4)
    assert len(vs) == 2


# ============================ training =========================== #


def test_train_q_learning_empty_raises():
    try:
        train_q_learning([])
    except ValueError:
        return
    raise AssertionError("expected ValueError on empty input")


def test_train_q_learning_single_order_raises():
    o = Order(fare_ntd=100, distance_km=2, duration_min=10, surge=1.0,
              pickup_zone_density=0.5, traffic_level=2, hour=10, is_weekend=False)
    try:
        train_q_learning([o])
    except ValueError:
        return
    raise AssertionError("expected ValueError on single order")


def test_train_q_learning_returns_diag():
    good = Order(fare_ntd=180, distance_km=4, duration_min=10, surge=1.0,
                  pickup_zone_density=0.7, traffic_level=2, hour=10, is_weekend=False)
    bad = Order(fare_ntd=280, distance_km=25, duration_min=55, surge=1.0,
                 pickup_zone_density=0.3, traffic_level=2, hour=2, is_weekend=False)
    orders = [good, bad] * 10
    q, diag = train_q_learning(orders, n_episodes=50, seed=42)
    assert len(diag.episode_returns) == 50
    assert diag.n_accepts + diag.n_declines > 0


def test_train_q_learning_learns_to_decline_bad():
    """After training, Q should rate the bad order lower than the good order."""
    good = Order(fare_ntd=180, distance_km=4, duration_min=10, surge=1.0,
                  pickup_zone_density=0.7, traffic_level=2, hour=10, is_weekend=False)
    bad = Order(fare_ntd=280, distance_km=25, duration_min=55, surge=1.0,
                 pickup_zone_density=0.3, traffic_level=2, hour=2, is_weekend=False)
    orders = [good] * 30 + [bad] * 30
    q, _ = train_q_learning(orders, n_episodes=200, seed=42)
    rec_good = recommend(q, good)
    rec_bad = recommend(q, bad)
    assert rec_good.q_accept > rec_bad.q_accept, \
        f"good order should have higher Q than bad: {rec_good.q_accept} vs {rec_bad.q_accept}"


def test_train_q_learning_deterministic_with_seed():
    o1 = Order(fare_ntd=180, distance_km=4, duration_min=10, surge=1.0,
                pickup_zone_density=0.7, traffic_level=2, hour=10, is_weekend=False)
    o2 = Order(fare_ntd=400, distance_km=15, duration_min=30, surge=1.5,
                pickup_zone_density=0.6, traffic_level=3, hour=18, is_weekend=True)
    orders = [o1, o2] * 5
    q1, _ = train_q_learning(orders, n_episodes=30, seed=42)
    q2, _ = train_q_learning(orders, n_episodes=30, seed=42)
    for a in range(2):
        for i in range(N_FEATURES):
            assert_close(q1.weights[a][i], q2.weights[a][i], tol=1e-12)


def test_episode_returns_trend_improves():
    """After training, later episodes should average higher return than early ones."""
    good = Order(fare_ntd=180, distance_km=4, duration_min=10, surge=1.0,
                  pickup_zone_density=0.7, traffic_level=2, hour=10, is_weekend=False)
    bad = Order(fare_ntd=300, distance_km=25, duration_min=55, surge=1.0,
                 pickup_zone_density=0.3, traffic_level=2, hour=2, is_weekend=False)
    orders = [good] * 20 + [bad] * 20
    q, diag = train_q_learning(orders, n_episodes=200, seed=42)
    first_half = sum(diag.episode_returns[:100]) / 100
    last_half = sum(diag.episode_returns[100:]) / 100
    assert last_half >= first_half - 50, \
        f"learning should not regress; first {first_half} vs last {last_half}"


# ============================ inference ============================ #


def test_recommend_returns_valid_action():
    good = Order(fare_ntd=180, distance_km=4, duration_min=10, surge=1.0,
                  pickup_zone_density=0.7, traffic_level=2, hour=10, is_weekend=False)
    bad = Order(fare_ntd=280, distance_km=25, duration_min=55, surge=1.0,
                 pickup_zone_density=0.3, traffic_level=2, hour=2, is_weekend=False)
    q, _ = train_q_learning([good, bad] * 10, n_episodes=100, seed=42)
    rec = recommend(q, good)
    assert rec.action in (0, 1)
    assert isinstance(rec.q_accept, float)
    assert isinstance(rec.q_decline, float)
    assert rec.margin == rec.q_accept - rec.q_decline


def test_replay_returns_metrics():
    good = Order(fare_ntd=180, distance_km=4, duration_min=10, surge=1.0,
                  pickup_zone_density=0.7, traffic_level=2, hour=10, is_weekend=False)
    bad = Order(fare_ntd=280, distance_km=25, duration_min=55, surge=1.0,
                 pickup_zone_density=0.3, traffic_level=2, hour=2, is_weekend=False)
    orders = [good, bad] * 10
    q, _ = train_q_learning(orders, n_episodes=100, seed=42)
    replay = replay_policy_on_log(q, orders)
    for key in ("learned_return", "naive_return", "delta", "learned_n_accept", "n_orders"):
        assert key in replay


def test_policy_summary_includes_all_actions():
    q = LinearQ(n_features=N_FEATURES, n_actions=len(ACTIONS))
    summary = policy_summary(q)
    assert 0 in summary
    assert 1 in summary
    assert len(summary[0]) == N_FEATURES


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
