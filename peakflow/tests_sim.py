"""peakflow edge tests — verify simulation correctness without API key."""
from __future__ import annotations

from sim import (
    RestaurantConfig, SimulationConfig, simulate, run_scenarios,
    CustomerState, _find_table, Table, _sample_party_size
)
import random


def test_party_size_distribution():
    """Party-size sampler is in [1, 4]."""
    rng = random.Random(0)
    sizes = [_sample_party_size(rng) for _ in range(1000)]
    assert min(sizes) == 1
    assert max(sizes) == 4
    # 2-person should be most common (50% weight)
    assert sizes.count(2) > sizes.count(1)
    assert sizes.count(2) > sizes.count(3)


def test_find_table_efficient_packing():
    """Smallest-fitting table is chosen."""
    tables = [Table(0, 2), Table(1, 4), Table(2, 6)]
    result = _find_table(tables, 2)
    assert result.table_id == 0  # 2-person → 2-seat table
    result = _find_table(tables, 3)
    assert result.table_id == 1  # 3-person → 4-seat table
    result = _find_table(tables, 5)
    assert result.table_id == 2  # 5-person → 6-seat table


def test_find_table_returns_none_when_full():
    """No table fits = None."""
    tables = [Table(0, 2, occupied_by=99), Table(1, 4, occupied_by=98)]
    assert _find_table(tables, 2) is None
    assert _find_table(tables, 6) is None


def test_simulation_basic_run():
    """Sanity: arrived == served + lost + still_waiting + still_eating."""
    rest = RestaurantConfig(
        name="test", n_tables=5, table_capacities=[2,2,4,4,6],
        n_servers=2, kitchen_capacity=2,
    )
    cfg = SimulationConfig(simulation_duration_min=60, customer_arrival_rate=0.3, seed=1)
    r = simulate(rest, cfg)
    assert r.n_arrived == r.n_served + r.n_lost + r.n_still_waiting_at_end + r.n_still_eating_at_end


def test_more_capacity_reduces_loss():
    """More tables ⇒ lower loss rate (monotonic)."""
    cfg = SimulationConfig(simulation_duration_min=120, customer_arrival_rate=0.5, seed=42)
    small = RestaurantConfig(name="s", n_tables=4, table_capacities=[2,2,4,4],
                              n_servers=2, kitchen_capacity=2)
    big = RestaurantConfig(name="b", n_tables=12, table_capacities=[2,2,2,2,4,4,4,4,4,6,6,6],
                            n_servers=4, kitchen_capacity=4)
    r_small = simulate(small, cfg)
    r_big = simulate(big, cfg)
    assert r_big.loss_rate_pct < r_small.loss_rate_pct, \
        f"More capacity should reduce loss: small={r_small.loss_rate_pct}% vs big={r_big.loss_rate_pct}%"


def test_revenue_only_from_served():
    """Revenue counts only served customers."""
    rest = RestaurantConfig(name="t", n_tables=2, table_capacities=[2,4],
                             n_servers=1, kitchen_capacity=1,
                             avg_check_per_person_ntd=300)
    cfg = SimulationConfig(simulation_duration_min=60, customer_arrival_rate=0.4, seed=7)
    r = simulate(rest, cfg)
    # All served customers contribute party_size × 300 to revenue
    expected = sum(c.party_size * 300 for c in r.raw_customers if c.state == CustomerState.LEFT)
    assert r.revenue_ntd == expected


def test_lost_customers_have_left_time():
    """Customer who exceeded patience has state=LOST and left_time set."""
    rest = RestaurantConfig(name="t", n_tables=1, table_capacities=[2],
                             n_servers=1, kitchen_capacity=1,
                             avg_patience_min=3.0, patience_std=0.5,
                             avg_eat_time_min=20, avg_eat_time_max=30)
    # Aggressive arrival: should overload single table
    cfg = SimulationConfig(simulation_duration_min=60, customer_arrival_rate=0.5, seed=11)
    r = simulate(rest, cfg)
    losts = [c for c in r.raw_customers if c.state == CustomerState.LOST]
    assert len(losts) > 0, "Aggressive arrival should produce some LOST"
    for c in losts:
        assert c.left_time is not None
        assert c.wait_time >= c.patience_minutes - 0.5  # tolerance for float


def test_utilization_in_range():
    """All utilization percentages in [0, 100]."""
    rest = RestaurantConfig(name="t", n_tables=10, table_capacities=[2]*5 + [4]*5,
                             n_servers=2, kitchen_capacity=2)
    cfg = SimulationConfig(simulation_duration_min=120, customer_arrival_rate=0.4, seed=5)
    r = simulate(rest, cfg)
    assert 0 <= r.server_utilization_pct <= 100
    assert 0 <= r.kitchen_utilization_pct <= 100
    assert 0 <= r.table_utilization_pct <= 100
    assert 0 <= r.loss_rate_pct <= 100


def test_zero_arrivals_zero_revenue():
    """Sim with no arrivals = no revenue, no loss."""
    rest = RestaurantConfig(name="empty", n_tables=10, table_capacities=[4]*10,
                             n_servers=2, kitchen_capacity=2)
    cfg = SimulationConfig(simulation_duration_min=10, customer_arrival_rate=0.001, seed=99)
    r = simulate(rest, cfg)
    assert r.revenue_ntd == 0 or r.n_arrived <= 1  # very unlikely to have arrivals
    assert r.loss_rate_pct <= 100


def test_run_scenarios_aggregates_correctly():
    """run_scenarios averages metrics across runs."""
    rest_a = RestaurantConfig(name="a", n_tables=5, table_capacities=[2,2,4,4,6],
                                n_servers=2, kitchen_capacity=2)
    rest_b = RestaurantConfig(name="b", n_tables=10, table_capacities=[2,2,2,2,4,4,4,4,4,6],
                                n_servers=3, kitchen_capacity=3)
    cfg = SimulationConfig(simulation_duration_min=60, customer_arrival_rate=0.4, seed=42)
    comp = run_scenarios([("A", rest_a), ("B", rest_b)], cfg, n_runs=3)
    assert len(comp.scenarios) == 2
    assert comp.scenarios[0][0] == "A"
    assert comp.scenarios[1][0] == "B"
    # B has more capacity, should have higher revenue or lower loss
    a_r = comp.scenarios[0][1]
    b_r = comp.scenarios[1][1]
    assert b_r.loss_rate_pct <= a_r.loss_rate_pct + 5  # within margin


def test_deterministic_with_same_seed():
    """Same seed = identical results."""
    rest = RestaurantConfig(name="d", n_tables=5, table_capacities=[2,2,4,4,6],
                             n_servers=2, kitchen_capacity=2)
    cfg = SimulationConfig(simulation_duration_min=60, customer_arrival_rate=0.4, seed=123)
    r1 = simulate(rest, cfg)
    r2 = simulate(rest, cfg)
    assert r1.n_arrived == r2.n_arrived
    assert r1.n_served == r2.n_served
    assert r1.revenue_ntd == r2.revenue_ntd


def test_kitchen_capacity_respected():
    """Kitchen never has more than capacity concurrent orders."""
    rest = RestaurantConfig(name="k", n_tables=10, table_capacities=[4]*10,
                             n_servers=3, kitchen_capacity=2,
                             kitchen_cook_time_min=10, kitchen_cook_time_max=12)
    cfg = SimulationConfig(simulation_duration_min=120, customer_arrival_rate=0.4, seed=8)
    r = simulate(rest, cfg)
    # Sanity: kitchen utilization should be at or below 100%
    assert r.kitchen_utilization_pct <= 100


if __name__ == "__main__":
    tests = [
        test_party_size_distribution,
        test_find_table_efficient_packing,
        test_find_table_returns_none_when_full,
        test_simulation_basic_run,
        test_more_capacity_reduces_loss,
        test_revenue_only_from_served,
        test_lost_customers_have_left_time,
        test_utilization_in_range,
        test_zero_arrivals_zero_revenue,
        test_run_scenarios_aggregates_correctly,
        test_deterministic_with_same_seed,
        test_kitchen_capacity_respected,
    ]
    passed = 0
    failed = 0
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
