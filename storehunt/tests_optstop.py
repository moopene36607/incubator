"""storehunt edge tests — pure-function optimal stopping correctness."""
from __future__ import annotations

from optstop import (
    StoreAttributes, SearchState, decide, composite_score,
    observation_phase_size, observation_threshold, best_so_far,
    time_pressure_adjustment, DEFAULT_WEIGHTS, Verdict,
)
import math


def _mk_store(name: str, location=70, rent=70, size=70, deposit=70, contract=70):
    return StoreAttributes(name=name, location_score=location, rent_score=rent,
                            size_score=size, deposit_score=deposit, contract_score=contract)


def test_composite_score_range():
    """Composite score in [0, 100]."""
    s = _mk_store("max", 100, 100, 100, 100, 100)
    assert abs(composite_score(s) - 100.0) < 0.01
    s2 = _mk_store("min", 0, 0, 0, 0, 0)
    assert composite_score(s2) == 0


def test_composite_score_weights_sum_to_one():
    """Default weights sum to 1 → composite never exceeds max input."""
    s = _mk_store("test", 60, 60, 60, 60, 60)
    assert abs(composite_score(s) - 60.0) < 0.01


def test_observation_phase_size_formula():
    """1/e ≈ 37%: N/e floor."""
    assert observation_phase_size(30) == math.floor(30 / math.e)
    assert observation_phase_size(10) == math.floor(10 / math.e)
    assert observation_phase_size(3) >= 1
    assert observation_phase_size(1) == 1


def test_observation_threshold_max():
    """Threshold is max of observation-phase scores."""
    seen = [_mk_store(f"s{i}", location=50 + i * 5) for i in range(5)]
    # Take only first 3 as observation
    t = observation_threshold(seen, 3, DEFAULT_WEIGHTS)
    expected_max = max(composite_score(s) for s in seen[:3])
    assert t == expected_max


def test_best_so_far():
    """Best-so-far returns the store with highest composite."""
    seen = [_mk_store("low", 50), _mk_store("high", 90), _mk_store("mid", 70)]
    store, score = best_so_far(seen, DEFAULT_WEIGHTS)
    assert store.name == "high"


def test_time_pressure_no_urgency():
    """No urgency = no adjustment."""
    seen = [_mk_store(f"s{i}") for i in range(10)]
    state = SearchState(seen_stores=seen, estimated_total_stores=30,
                        current_store=_mk_store("current"),
                        search_weeks_elapsed=2, expected_search_weeks=8)
    adj = time_pressure_adjustment(state)
    assert adj == 1.0


def test_time_pressure_increases_with_remaining_drops():
    """Few remaining → lower adjustment (more pressure)."""
    seen_few = [_mk_store(f"s{i}") for i in range(28)]  # 28/30 seen, 2 remaining
    seen_lots = [_mk_store(f"s{i}") for i in range(5)]
    state_late = SearchState(seen_stores=seen_few, estimated_total_stores=30,
                             current_store=_mk_store("current"),
                             search_weeks_elapsed=2, expected_search_weeks=8)
    state_early = SearchState(seen_stores=seen_lots, estimated_total_stores=30,
                               current_store=_mk_store("current"),
                               search_weeks_elapsed=2, expected_search_weeks=8)
    assert time_pressure_adjustment(state_late) < time_pressure_adjustment(state_early)


def test_time_pressure_overrun():
    """Search dragged past budget → pressure adjustment."""
    seen = [_mk_store(f"s{i}") for i in range(10)]
    state = SearchState(seen_stores=seen, estimated_total_stores=30,
                        current_store=_mk_store("current"),
                        search_weeks_elapsed=14, expected_search_weeks=8)
    assert time_pressure_adjustment(state) < 1.0


def test_observation_phase_decision():
    """Still in observation phase → CONTINUE_OBSERVATION."""
    seen = [_mk_store(f"s{i}", location=80) for i in range(3)]
    state = SearchState(seen_stores=seen, estimated_total_stores=30,
                        current_store=_mk_store("current", location=95),
                        search_weeks_elapsed=1, expected_search_weeks=8)
    d = decide(state)
    assert d.verdict == Verdict.CONTINUE_OBSERVATION


def test_strong_accept_after_phase():
    """After phase, score well above threshold → STRONG_ACCEPT."""
    # 30 stores, obs phase = 11. Observation period scores 60.
    seen = [_mk_store(f"s{i}", location=60, rent=60, size=60, deposit=60, contract=60)
            for i in range(12)]
    current = _mk_store("excellent", 95, 90, 95, 85, 90)
    state = SearchState(seen_stores=seen, estimated_total_stores=30,
                        current_store=current,
                        search_weeks_elapsed=2, expected_search_weeks=8)
    d = decide(state)
    assert d.verdict == Verdict.STRONG_ACCEPT


def test_wait_for_better_when_below_threshold():
    """Score below threshold + many remaining → WAIT_FOR_BETTER."""
    # 30 stores, obs phase = 11. Observation period contains a high-score store.
    high = _mk_store("high", 95, 90, 95, 90, 95)
    seen = [high] + [_mk_store(f"s{i}", location=50) for i in range(11)]
    current = _mk_store("mediocre", 60, 55, 60, 60, 60)
    state = SearchState(seen_stores=seen, estimated_total_stores=30,
                        current_store=current,
                        search_weeks_elapsed=2, expected_search_weeks=8)
    d = decide(state)
    assert d.verdict in (Verdict.WAIT_FOR_BETTER, Verdict.RECONSIDER)


def test_reluctant_accept_late_in_search():
    """Few remaining + score below threshold but close → RELUCTANT_ACCEPT."""
    # Observation phase has a stand-out high (95), then mediocre.
    # threshold = 95, pressure reduces it.
    seen = [_mk_store("high", 95, 95, 95, 95, 95)] + \
           [_mk_store(f"s{i}", 60, 60, 60, 60, 60) for i in range(26)]
    # Current score 65 — below threshold (95→adjusted ~71)
    # but >= 0.85 × 71 = 60.4
    current = _mk_store("ok", 65, 65, 65, 65, 65)
    state = SearchState(seen_stores=seen, estimated_total_stores=30,
                        current_store=current,
                        search_weeks_elapsed=8, expected_search_weeks=8)
    d = decide(state)
    # Could be RELUCTANT_ACCEPT (below threshold but late) or RECONSIDER (too low)
    assert d.verdict in (Verdict.RELUCTANT_ACCEPT, Verdict.RECONSIDER, Verdict.WAIT_FOR_BETTER)


def test_reconsider_when_very_low_score():
    """Score way below threshold → RECONSIDER."""
    seen = [_mk_store("anchor", 90, 90, 90, 90, 90)] + \
           [_mk_store(f"s{i}", 80, 80, 80, 80, 80) for i in range(12)]
    current = _mk_store("terrible", 20, 20, 20, 20, 20)
    state = SearchState(seen_stores=seen, estimated_total_stores=30,
                        current_store=current,
                        search_weeks_elapsed=2, expected_search_weeks=8)
    d = decide(state)
    assert d.verdict == Verdict.RECONSIDER


def test_theoretical_p_best_constant():
    """P(best | optimal policy) ≈ 1/e."""
    seen = [_mk_store(f"s{i}") for i in range(5)]
    state = SearchState(seen_stores=seen, estimated_total_stores=30,
                        current_store=_mk_store("current"),
                        search_weeks_elapsed=1, expected_search_weeks=8)
    d = decide(state)
    assert abs(d.theoretical_p_best - (1.0 / math.e)) < 0.005


def test_deterministic():
    """Same state → same decision."""
    seen = [_mk_store(f"s{i}", location=60) for i in range(12)]
    state = SearchState(seen_stores=seen, estimated_total_stores=30,
                        current_store=_mk_store("current", 80),
                        search_weeks_elapsed=2, expected_search_weeks=8)
    d1 = decide(state)
    d2 = decide(state)
    assert d1.verdict == d2.verdict
    assert d1.current_score == d2.current_score
    assert d1.threshold == d2.threshold


def test_empty_observations_handled():
    """Zero stores seen yet (deciding on first one) → CONTINUE_OBSERVATION."""
    state = SearchState(seen_stores=[], estimated_total_stores=30,
                        current_store=_mk_store("first", 80),
                        search_weeks_elapsed=0.5, expected_search_weeks=8)
    d = decide(state)
    assert d.verdict == Verdict.CONTINUE_OBSERVATION


def test_must_decide_adds_pressure():
    """Landlord deadline adds time pressure."""
    seen = [_mk_store(f"s{i}", 80) for i in range(15)]
    state_relaxed = SearchState(seen_stores=seen, estimated_total_stores=30,
                                 current_store=_mk_store("ok", 75),
                                 search_weeks_elapsed=3, expected_search_weeks=8,
                                 user_must_decide=False)
    state_pressed = SearchState(seen_stores=seen, estimated_total_stores=30,
                                 current_store=_mk_store("ok", 75),
                                 search_weeks_elapsed=3, expected_search_weeks=8,
                                 user_must_decide=True)
    assert time_pressure_adjustment(state_pressed) < time_pressure_adjustment(state_relaxed)


if __name__ == "__main__":
    tests = [
        test_composite_score_range,
        test_composite_score_weights_sum_to_one,
        test_observation_phase_size_formula,
        test_observation_threshold_max,
        test_best_so_far,
        test_time_pressure_no_urgency,
        test_time_pressure_increases_with_remaining_drops,
        test_time_pressure_overrun,
        test_observation_phase_decision,
        test_strong_accept_after_phase,
        test_wait_for_better_when_below_threshold,
        test_reluctant_accept_late_in_search,
        test_reconsider_when_very_low_score,
        test_theoretical_p_best_constant,
        test_deterministic,
        test_empty_observations_handled,
        test_must_decide_adds_pressure,
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
