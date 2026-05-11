"""examready — 多科溫習 MDP / DP with Rollout (pure stdlib).

MDP formulation:
  State  : per-subject familiarity (0-100) + days_to_exam
  Action : tonight's study allocation (subject_id → minutes)
  Trans  : studied subjects gain via boost(minutes);
           non-studied subjects decay via forgetting rate
  Reward : at exam day, weighted predicted score = Σ weight_s × f_s/100 × max_score_s

Optimal-action selection uses N-step forward rollout under a default
future policy (always study the subject with the lowest weight-adjusted
familiarity). For each candidate action tonight we forward-simulate to
exam day and score; the best-scoring candidate wins.

100% stdlib (math + statistics + dataclass + itertools). LLM never
touches scores or familiarity — those are pure functions.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field, replace
from itertools import combinations


# ============== Domain types ==============
@dataclass
class Subject:
    code: str                           # e.g., "MATH_A"
    name: str                           # 顯示名稱
    weight: float                       # 學測 / 會考 權重
    forgetting_rate: float              # per-day exp decay rate (0.01 慢 / 0.05 快)
    boost_a: float                      # max boost per session (學科吸收上限)
    boost_tau: float                    # minutes for 63% of boost saturation


@dataclass
class StudentState:
    familiarity: dict[str, float]       # subject_code → 0-100
    days_since_studied: dict[str, int]  # subject_code → days
    days_to_exam: int


@dataclass
class StudyPlan:
    name: str
    student_state: StudentState
    subjects: list[Subject]
    nightly_available_minutes: int      # 今晚總可用分鐘 (typically 90-180)
    min_block_minutes: int = 30
    max_subjects_per_night: int = 3
    candidate_block_sizes: tuple[int, ...] = (30, 45, 60, 90)


@dataclass
class Action:
    """tonight's allocation: subject_code → minutes."""
    allocation: dict[str, int]

    def total_minutes(self) -> int:
        return sum(self.allocation.values())

    def studied_subjects(self) -> list[str]:
        return [s for s, m in self.allocation.items() if m > 0]


@dataclass
class RolloutResult:
    action: Action
    expected_exam_score: float
    final_familiarity: dict[str, float]
    daily_trajectory: list[dict[str, float]]


# ============== Pure-function dynamics ==============
def boost(subject: Subject, minutes: int) -> float:
    """Familiarity gain from studying `minutes` of a subject. Saturating."""
    if minutes <= 0:
        return 0.0
    return subject.boost_a * (1.0 - math.exp(-minutes / subject.boost_tau))


def decay(familiarity: float, forgetting_rate: float, days: int) -> float:
    """Familiarity loss over `days` without review."""
    return familiarity * math.exp(-forgetting_rate * days)


def apply_action(state: StudentState, subjects: list[Subject], action: Action) -> StudentState:
    """One-day MDP transition: today's action → tomorrow's state.

    Boost uses diminishing returns: f_new = f + (100 - f) / 100 × boost(t).
    This prevents trivial 'study every night → 100' optimistic ceiling.
    """
    new_familiarity: dict[str, float] = {}
    new_days_since: dict[str, int] = {}
    for s in subjects:
        minutes = action.allocation.get(s.code, 0)
        f = state.familiarity[s.code]
        if minutes > 0:
            # Decay for 1 day, then add diminishing-returns boost
            f = decay(f, s.forgetting_rate, 1)
            raw_boost = boost(s, minutes)
            effective_boost = raw_boost * (100.0 - f) / 100.0
            f = min(100.0, f + effective_boost)
            new_days_since[s.code] = 0
        else:
            f = decay(f, s.forgetting_rate, 1)
            new_days_since[s.code] = state.days_since_studied.get(s.code, 0) + 1
        new_familiarity[s.code] = round(f, 2)

    return StudentState(
        familiarity=new_familiarity,
        days_since_studied=new_days_since,
        days_to_exam=max(0, state.days_to_exam - 1),
    )


def predicted_exam_score(state: StudentState, subjects: list[Subject],
                          max_score_per_subject: float = 100.0) -> float:
    """Weighted predicted exam total."""
    total = 0.0
    total_weight = 0.0
    for s in subjects:
        f = state.familiarity[s.code]
        total += s.weight * (f / 100.0) * max_score_per_subject
        total_weight += s.weight
    if total_weight == 0:
        return 0.0
    return round(total / total_weight * len(subjects), 1)


def weighted_familiarity(state: StudentState, subjects: list[Subject]) -> dict[str, float]:
    """Each subject's weight-adjusted gap (lower = needs more attention)."""
    out = {}
    for s in subjects:
        f = state.familiarity[s.code]
        # gap-to-100 weighted by subject weight; higher number = bigger payoff to study
        gap = (100.0 - f) * s.weight
        out[s.code] = round(gap, 2)
    return out


# ============== Default future policy ==============
def default_future_action(state: StudentState, subjects: list[Subject],
                           plan: StudyPlan) -> Action:
    """For rollout: pick top-K subjects by weighted gap, split nightly minutes."""
    gaps = weighted_familiarity(state, subjects)
    # Sort by gap descending; pick top max_subjects
    ranked = sorted(gaps.items(), key=lambda x: -x[1])
    chosen = [code for code, gap in ranked[:plan.max_subjects_per_night] if gap > 0]
    if not chosen:
        return Action(allocation={})
    per_subject = plan.nightly_available_minutes // len(chosen)
    # Floor to min_block
    per_subject = max(plan.min_block_minutes, per_subject - (per_subject % 15))
    allocation = {code: per_subject for code in chosen}
    return Action(allocation=allocation)


# ============== Candidate-action enumeration ==============
def enumerate_candidate_actions(plan: StudyPlan) -> list[Action]:
    """Generate plausible action candidates for tonight.

    To keep search tractable: pick 1..max_subjects subjects × pick block size per subject
    that sum to ≤ nightly_available_minutes.
    """
    actions: list[Action] = []
    codes = [s.code for s in plan.subjects]

    for k in range(1, plan.max_subjects_per_night + 1):
        for combo in combinations(codes, k):
            # For each subset, generate a few allocations
            if k == 1:
                # Single subject: try a few block sizes
                for block in plan.candidate_block_sizes:
                    if block <= plan.nightly_available_minutes:
                        actions.append(Action(allocation={combo[0]: block}))
                # Always include "use full night"
                actions.append(Action(allocation={combo[0]: plan.nightly_available_minutes}))
            elif k == 2:
                # Two subjects: pairs of block sizes
                for b1 in (45, 60, 90):
                    for b2 in (30, 45, 60):
                        if b1 + b2 <= plan.nightly_available_minutes:
                            actions.append(Action(allocation={combo[0]: b1, combo[1]: b2}))
                # Equal split
                half = plan.nightly_available_minutes // 2
                if half >= plan.min_block_minutes:
                    actions.append(Action(allocation={combo[0]: half, combo[1]: half}))
            else:
                # Three subjects: balanced
                third = plan.nightly_available_minutes // 3
                if third >= plan.min_block_minutes:
                    actions.append(Action(allocation={c: third for c in combo}))
                # Heavy on first
                actions.append(Action(allocation={
                    combo[0]: 60, combo[1]: 45, combo[2]: 30,
                }))

    # Deduplicate by tuple of (sorted_alloc_items)
    seen = set()
    unique = []
    for a in actions:
        key = tuple(sorted(a.allocation.items()))
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


# ============== Rollout evaluation ==============
def rollout(state: StudentState, subjects: list[Subject],
             plan: StudyPlan, tonight_action: Action) -> RolloutResult:
    """Simulate forward to exam day under (tonight_action, then default policy)."""
    trajectory = [dict(state.familiarity)]
    cur = state
    # Day 0: tonight
    cur = apply_action(cur, subjects, tonight_action)
    trajectory.append(dict(cur.familiarity))
    # Day 1..days_to_exam-1: default policy
    while cur.days_to_exam > 0:
        default_a = default_future_action(cur, subjects, plan)
        cur = apply_action(cur, subjects, default_a)
        trajectory.append(dict(cur.familiarity))

    score = predicted_exam_score(cur, subjects)
    return RolloutResult(
        action=tonight_action,
        expected_exam_score=score,
        final_familiarity=cur.familiarity,
        daily_trajectory=trajectory,
    )


def find_optimal_tonight(plan: StudyPlan) -> tuple[Action, list[RolloutResult]]:
    """Evaluate every candidate action via rollout; return best + all sorted."""
    candidates = enumerate_candidate_actions(plan)
    if not candidates:
        return Action(allocation={}), []
    results = [rollout(plan.student_state, plan.subjects, plan, a) for a in candidates]
    results.sort(key=lambda r: -r.expected_exam_score)
    return results[0].action, results


def project_seven_day_plan(plan: StudyPlan) -> list[tuple[int, Action, float]]:
    """Project the next 7 days under the optimal-tonight + default-future policy.
    Returns [(day_index, action, predicted_score_after_day)]."""
    out = []
    cur_state = plan.student_state
    for day in range(min(7, plan.student_state.days_to_exam)):
        local_plan = replace(plan, student_state=cur_state)
        best_action, _ = find_optimal_tonight(local_plan)
        cur_state = apply_action(cur_state, plan.subjects, best_action)
        # Score remaining trajectory
        trailing_plan = replace(plan, student_state=cur_state)
        if cur_state.days_to_exam > 0:
            _, all_results = find_optimal_tonight(trailing_plan)
            projected = all_results[0].expected_exam_score if all_results else predicted_exam_score(cur_state, plan.subjects)
        else:
            projected = predicted_exam_score(cur_state, plan.subjects)
        out.append((day + 1, best_action, projected))
    return out


# ============== Helpers ==============
def baseline_score_if_no_study(plan: StudyPlan) -> float:
    """What if student does nothing for the remaining days? (everything just decays)"""
    state = plan.student_state
    new_fam = {}
    for s in plan.subjects:
        f = state.familiarity[s.code]
        f = decay(f, s.forgetting_rate, state.days_to_exam)
        new_fam[s.code] = round(f, 2)
    return predicted_exam_score(
        StudentState(familiarity=new_fam, days_since_studied={}, days_to_exam=0),
        plan.subjects,
    )


def fair_share_baseline(plan: StudyPlan) -> RolloutResult:
    """Baseline: every night study top-K by weight equally (ignoring familiarity)."""
    state = plan.student_state
    # Use a 'fair' action: top-K by weight (not gap)
    sorted_by_weight = sorted(plan.subjects, key=lambda s: -s.weight)
    chosen = sorted_by_weight[:plan.max_subjects_per_night]
    per = plan.nightly_available_minutes // len(chosen)
    fair_action = Action(allocation={s.code: per for s in chosen})

    # Simulate fair policy every day
    trajectory = [dict(state.familiarity)]
    cur = state
    while cur.days_to_exam > 0:
        cur = apply_action(cur, plan.subjects, fair_action)
        trajectory.append(dict(cur.familiarity))
    return RolloutResult(
        action=fair_action,
        expected_exam_score=predicted_exam_score(cur, plan.subjects),
        final_familiarity=cur.familiarity,
        daily_trajectory=trajectory,
    )
