"""examready edge tests — pure-function MDP correctness."""
from __future__ import annotations

from mdp import (
    Subject, StudentState, StudyPlan, Action,
    boost, decay, apply_action, predicted_exam_score,
    weighted_familiarity, default_future_action,
    enumerate_candidate_actions, rollout, find_optimal_tonight,
    baseline_score_if_no_study, fair_share_baseline,
)


def _make_subjects():
    return [
        Subject(code="A", name="A", weight=2.0, forgetting_rate=0.03, boost_a=10, boost_tau=60),
        Subject(code="B", name="B", weight=1.0, forgetting_rate=0.02, boost_a=8, boost_tau=45),
        Subject(code="C", name="C", weight=1.5, forgetting_rate=0.025, boost_a=9, boost_tau=50),
    ]


def _make_state(days=30):
    return StudentState(
        familiarity={"A": 40.0, "B": 70.0, "C": 55.0},
        days_since_studied={"A": 5, "B": 1, "C": 3},
        days_to_exam=days,
    )


def test_boost_monotonic():
    """More minutes ⇒ more boost (monotonic, saturating)."""
    s = Subject(code="x", name="x", weight=1, forgetting_rate=0.02, boost_a=10, boost_tau=60)
    assert boost(s, 0) == 0
    assert boost(s, 30) < boost(s, 60)
    assert boost(s, 60) < boost(s, 90)
    assert boost(s, 120) < s.boost_a  # never exceeds boost_a


def test_decay_reduces_familiarity():
    """Decay over time monotonically reduces."""
    assert decay(100, 0.03, 0) == 100
    assert decay(100, 0.03, 1) < 100
    assert decay(100, 0.03, 5) < decay(100, 0.03, 1)
    assert decay(100, 0.03, 30) < decay(100, 0.03, 10)


def test_apply_action_studied_subjects_gain():
    """Studied subject's familiarity grows; unstudied decays."""
    subs = _make_subjects()
    state = _make_state()
    action = Action(allocation={"A": 60})
    new_state = apply_action(state, subs, action)
    # A was studied → went up (with diminishing returns)
    assert new_state.familiarity["A"] > state.familiarity["A"]
    # B not studied → decay
    assert new_state.familiarity["B"] < state.familiarity["B"]
    # days_to_exam decremented
    assert new_state.days_to_exam == state.days_to_exam - 1
    # days_since_studied: A reset, B incremented
    assert new_state.days_since_studied["A"] == 0
    assert new_state.days_since_studied["B"] == 2


def test_predicted_score_in_range():
    """Score is in [0, 500] for 5-subject (or N×100) range."""
    subs = _make_subjects()
    state = _make_state()
    score = predicted_exam_score(state, subs)
    assert 0 <= score <= 100 * len(subs)


def test_perfect_familiarity_gives_max():
    """All 100 familiarity → near max score."""
    subs = _make_subjects()
    state = StudentState(
        familiarity={"A": 100.0, "B": 100.0, "C": 100.0},
        days_since_studied={}, days_to_exam=0,
    )
    score = predicted_exam_score(state, subs)
    # 100 × len(subs) = 300 for 3 subjects (with arithmetic averaging then multiplied by N)
    assert score == 100 * len(subs)


def test_zero_familiarity_zero_score():
    """All 0 familiarity → 0 score."""
    subs = _make_subjects()
    state = StudentState(
        familiarity={"A": 0.0, "B": 0.0, "C": 0.0},
        days_since_studied={}, days_to_exam=0,
    )
    assert predicted_exam_score(state, subs) == 0.0


def test_weighted_gap_higher_for_weak_high_weight():
    """Subject A (weight 2, fam 40) has highest gap = (100-40)*2 = 120."""
    subs = _make_subjects()
    state = _make_state()
    gaps = weighted_familiarity(state, subs)
    assert gaps["A"] > gaps["B"]
    assert gaps["A"] > gaps["C"]
    assert gaps["A"] == 120.0


def test_default_future_picks_top_gaps():
    """Default policy picks subjects with highest weighted gap."""
    subs = _make_subjects()
    state = _make_state()
    plan = StudyPlan(name="t", student_state=state, subjects=subs,
                     nightly_available_minutes=180, max_subjects_per_night=3)
    action = default_future_action(state, subs, plan)
    studied = set(action.allocation.keys())
    # A (gap 120) and C (gap 67.5) must be in top 3
    assert "A" in studied
    assert "C" in studied


def test_candidate_actions_nonempty():
    """Enumeration produces multiple candidates."""
    subs = _make_subjects()
    state = _make_state()
    plan = StudyPlan(name="t", student_state=state, subjects=subs,
                     nightly_available_minutes=180, max_subjects_per_night=3)
    actions = enumerate_candidate_actions(plan)
    assert len(actions) > 10


def test_optimal_beats_no_study():
    """Optimal rollout score > no-study baseline."""
    subs = _make_subjects()
    state = _make_state(days=21)
    plan = StudyPlan(name="t", student_state=state, subjects=subs,
                     nightly_available_minutes=180, max_subjects_per_night=3)
    best_action, results = find_optimal_tonight(plan)
    no_study = baseline_score_if_no_study(plan)
    assert results[0].expected_exam_score > no_study * 1.2


def test_optimal_beats_or_ties_fair_share():
    """Optimal is at least as good as fair-share equal split."""
    subs = _make_subjects()
    state = _make_state(days=20)
    plan = StudyPlan(name="t", student_state=state, subjects=subs,
                     nightly_available_minutes=180, max_subjects_per_night=3)
    _, results = find_optimal_tonight(plan)
    fair = fair_share_baseline(plan)
    assert results[0].expected_exam_score >= fair.expected_exam_score - 0.5


def test_diminishing_returns_near_100():
    """Boost effect near f=100 is tiny (no overflow > 100)."""
    s = Subject(code="x", name="x", weight=1, forgetting_rate=0.02, boost_a=10, boost_tau=60)
    state = StudentState(
        familiarity={"x": 95.0}, days_since_studied={"x": 0}, days_to_exam=10,
    )
    action = Action(allocation={"x": 120})
    new_state = apply_action(state, [s], action)
    assert new_state.familiarity["x"] <= 100.0
    # Should still grow but by small amount
    assert new_state.familiarity["x"] > state.familiarity["x"] * 0.95  # at least keeps most


def test_action_total_minutes():
    """Action.total_minutes sums allocation."""
    a = Action(allocation={"A": 60, "B": 30, "C": 45})
    assert a.total_minutes() == 135
    assert set(a.studied_subjects()) == {"A", "B", "C"}


def test_deterministic_optimum():
    """Same plan → same optimum (no randomness in MDP)."""
    subs = _make_subjects()
    state = _make_state()
    plan = StudyPlan(name="t", student_state=state, subjects=subs,
                     nightly_available_minutes=180, max_subjects_per_night=3)
    a1, r1 = find_optimal_tonight(plan)
    a2, r2 = find_optimal_tonight(plan)
    assert a1.allocation == a2.allocation
    assert r1[0].expected_exam_score == r2[0].expected_exam_score


if __name__ == "__main__":
    tests = [
        test_boost_monotonic,
        test_decay_reduces_familiarity,
        test_apply_action_studied_subjects_gain,
        test_predicted_score_in_range,
        test_perfect_familiarity_gives_max,
        test_zero_familiarity_zero_score,
        test_weighted_gap_higher_for_weak_high_weight,
        test_default_future_picks_top_gaps,
        test_candidate_actions_nonempty,
        test_optimal_beats_no_study,
        test_optimal_beats_or_ties_fair_share,
        test_diminishing_returns_near_100,
        test_action_total_minutes,
        test_deterministic_optimum,
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
