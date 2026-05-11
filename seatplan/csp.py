"""seatplan — 婚禮座位編排 CSP / Simulated Annealing(純函式 / no I/O / no LLM).

責任:
  - 接受賓客清單 + 桌子設定 + 多種 constraints
  - 用 greedy initial + simulated annealing 找出 cost 最低的座位編排
  - 計算 final assignment 的 constraint violations + group cohesion

100% stdlib(只用 random + math + dataclass)。

Cost function(較低越好):
  - **HARD violations**(嚴重):
      avoid_pair_with 兩人卻同桌:+100
      must_pair_with 兩人卻不同桌:+50
      VIP 沒在 VIP 桌:+30
  - **SOFT objectives**(柔性):
      group cohesion bonus:同 group 兩人同桌 -1
      group monopoly penalty:同一桌某 group 佔 > 80%:+10
      capacity overflow:某桌人數 > 容量:+200 each
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from itertools import combinations


@dataclass
class Guest:
    guest_id: str
    name: str
    group: str                           # "家族-新郎" / "家族-新娘" / "同事-新郎" / ...
    must_pair_with: list[str] = field(default_factory=list)
    avoid_pair_with: list[str] = field(default_factory=list)
    is_vip: bool = False
    age_group: str = "adult"             # adult / child / senior
    notes: str = ""


@dataclass
class Table:
    table_id: str
    capacity: int
    is_vip: bool = False
    name: str = ""                       # 例「新郎主桌」
    preferred_groups: list[str] = field(default_factory=list)  # 該桌偏好的 group(用於 cost 偏好,非硬限制)


@dataclass
class CostBreakdown:
    avoid_violations: int                # 不能同桌卻同桌的對數
    must_pair_violations: int            # 必同桌卻分開的對數
    vip_misplaced: int                   # VIP 沒在 VIP 桌的人數
    capacity_overflow: int               # 超出桌容量的人次
    group_cohesion_bonus: int            # 同 group 同桌對數(負分)
    group_monopoly_penalty: int          # 單 group 壟斷桌數(>80%)
    preferred_group_mismatch: int        # 賓客 group 不符桌子 preferred_groups
    total_cost: float


def _compute_cost(assignments: dict[str, str], guests: dict[str, Guest],
                  tables: dict[str, Table]) -> CostBreakdown:
    """assignments: guest_id -> table_id 的對應。"""
    # 各桌的 guest list
    by_table: dict[str, list[str]] = {t: [] for t in tables}
    for gid, tid in assignments.items():
        if tid in by_table:
            by_table[tid].append(gid)

    # 計算各種 violation
    avoid_count = 0
    must_count = 0
    vip_misplaced = 0
    overflow = 0
    cohesion = 0
    monopoly = 0
    preferred_mismatch = 0

    # 1. avoid_pair_with violation
    # 2. group cohesion bonus
    for tid, gids in by_table.items():
        table = tables[tid]
        for i, gid_a in enumerate(gids):
            ga = guests[gid_a]
            for gid_b in gids[i + 1:]:
                gb = guests[gid_b]
                if gid_b in ga.avoid_pair_with or gid_a in gb.avoid_pair_with:
                    avoid_count += 1
                if ga.group == gb.group:
                    cohesion += 1

        # capacity overflow
        cap = table.capacity
        if len(gids) > cap:
            overflow += len(gids) - cap

        # group monopoly (>80%)
        if gids:
            group_counts: dict[str, int] = {}
            for gid in gids:
                g = guests[gid].group
                group_counts[g] = group_counts.get(g, 0) + 1
            max_share = max(group_counts.values()) / len(gids)
            if max_share > 0.80 and len(gids) >= 5:
                monopoly += 1

        # VIP misplaced
        for gid in gids:
            if guests[gid].is_vip and not table.is_vip:
                vip_misplaced += 1

        # preferred_groups mismatch(若該桌指定 preferred,賓客 group 應落在 preferred 內)
        if table.preferred_groups:
            for gid in gids:
                if guests[gid].group not in table.preferred_groups:
                    preferred_mismatch += 1

    # 3. must_pair_with violation
    seen_pairs: set[tuple[str, str]] = set()
    for gid, g in guests.items():
        for partner_id in g.must_pair_with:
            pair = tuple(sorted([gid, partner_id]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            if assignments.get(gid) != assignments.get(partner_id):
                must_count += 1

    total = (
        avoid_count * 100
        + must_count * 50
        + vip_misplaced * 30
        + overflow * 200
        + monopoly * 10
        + preferred_mismatch * 3
        - cohesion * 1
    )
    return CostBreakdown(
        avoid_violations=avoid_count,
        must_pair_violations=must_count,
        vip_misplaced=vip_misplaced,
        capacity_overflow=overflow,
        group_cohesion_bonus=cohesion,
        group_monopoly_penalty=monopoly,
        preferred_group_mismatch=preferred_mismatch,
        total_cost=total,
    )


# ===== Greedy initial assignment =====
def _greedy_initial(guests: list[Guest], tables: list[Table], seed: int = 42) -> dict[str, str]:
    """貪婪初始化:VIP 先進 VIP 桌,同 group 盡量同桌(直到該桌滿)。"""
    rng = random.Random(seed)
    assignments: dict[str, str] = {}
    table_counts: dict[str, int] = {t.table_id: 0 for t in tables}
    table_map = {t.table_id: t for t in tables}

    # 1. VIPs first to VIP tables
    vip_tables = [t for t in tables if t.is_vip]
    non_vip_tables = [t for t in tables if not t.is_vip]
    vips = [g for g in guests if g.is_vip]
    non_vips = [g for g in guests if not g.is_vip]

    for g in vips:
        # 找第一個還有容量的 VIP table
        for t in vip_tables:
            if table_counts[t.table_id] < t.capacity:
                assignments[g.guest_id] = t.table_id
                table_counts[t.table_id] += 1
                break
        else:
            # No VIP table space, fall back to regular
            for t in non_vip_tables:
                if table_counts[t.table_id] < t.capacity:
                    assignments[g.guest_id] = t.table_id
                    table_counts[t.table_id] += 1
                    break

    # 2. Non-VIPs grouped by group, distribute
    by_group: dict[str, list[Guest]] = {}
    for g in non_vips:
        by_group.setdefault(g.group, []).append(g)

    # 從大 group 開始分配
    sorted_groups = sorted(by_group.items(), key=lambda x: -len(x[1]))
    for group_name, gs in sorted_groups:
        rng.shuffle(gs)
        for g in gs:
            preferred_table = None

            # 優先 1: 該桌的 preferred_groups 含 guest 的 group
            for t in non_vip_tables:
                if table_counts[t.table_id] < t.capacity and group_name in t.preferred_groups:
                    preferred_table = t
                    break

            # 優先 2: 該 group 已有人在但未滿的桌子(group cohesion)
            if preferred_table is None:
                for t in non_vip_tables:
                    if table_counts[t.table_id] < t.capacity:
                        has_same_group = any(
                            assignments.get(g2.guest_id) == t.table_id and g2.group == group_name
                            for g2 in non_vips
                        )
                        if has_same_group:
                            preferred_table = t
                            break

            # 優先 3: 任何未滿的非 VIP 桌
            if preferred_table is None:
                for t in non_vip_tables:
                    if table_counts[t.table_id] < t.capacity:
                        preferred_table = t
                        break
            if preferred_table is not None:
                assignments[g.guest_id] = preferred_table.table_id
                table_counts[preferred_table.table_id] += 1
            else:
                # All non-VIP tables full — fall back to any with space (including VIP)
                for t in tables:
                    if table_counts[t.table_id] < t.capacity:
                        assignments[g.guest_id] = t.table_id
                        table_counts[t.table_id] += 1
                        break

    return assignments


# ===== Simulated annealing =====
@dataclass
class OptimizationLog:
    iterations_run: int
    initial_cost: float
    final_cost: float
    improvement_steps: list[tuple[int, float]]   # (iteration, cost)


def _swap_two(assignments: dict[str, str], rng: random.Random) -> dict[str, str] | None:
    """隨機選兩個 guest 互換 table。"""
    gids = list(assignments.keys())
    if len(gids) < 2:
        return None
    a, b = rng.sample(gids, 2)
    if assignments[a] == assignments[b]:
        return None
    new_assignments = dict(assignments)
    new_assignments[a], new_assignments[b] = assignments[b], assignments[a]
    return new_assignments


def simulated_annealing(
    guests: list[Guest],
    tables: list[Table],
    max_iter: int = 5000,
    initial_temp: float = 20.0,
    cooling_rate: float = 0.9995,
    seed: int = 42,
) -> tuple[dict[str, str], OptimizationLog]:
    """跑 simulated annealing 改善初始 assignment。"""
    rng = random.Random(seed)
    guests_map = {g.guest_id: g for g in guests}
    tables_map = {t.table_id: t for t in tables}

    current = _greedy_initial(guests, tables, seed=seed)
    current_cost = _compute_cost(current, guests_map, tables_map).total_cost
    initial_cost = current_cost
    best = dict(current)
    best_cost = current_cost

    log_steps: list[tuple[int, float]] = [(0, current_cost)]
    temp = initial_temp

    for it in range(1, max_iter + 1):
        candidate = _swap_two(current, rng)
        if candidate is None:
            continue
        candidate_cost = _compute_cost(candidate, guests_map, tables_map).total_cost
        delta = candidate_cost - current_cost
        # Accept if better, or with probability exp(-delta/temp) if worse
        if delta < 0 or rng.random() < math.exp(-delta / max(temp, 1e-3)):
            current = candidate
            current_cost = candidate_cost
            if current_cost < best_cost:
                best = dict(current)
                best_cost = current_cost
                log_steps.append((it, best_cost))
        temp *= cooling_rate

    return best, OptimizationLog(
        iterations_run=max_iter,
        initial_cost=initial_cost,
        final_cost=best_cost,
        improvement_steps=log_steps,
    )


# ===== High-level solve =====
@dataclass
class TablePlan:
    table_id: str
    table_name: str
    capacity: int
    is_vip: bool
    assigned_guests: list[Guest]
    n_seated: int
    groups_at_table: dict[str, int]


@dataclass
class SeatPlanResult:
    table_plans: list[TablePlan]
    cost_breakdown: CostBreakdown
    optimization_log: OptimizationLog
    n_total_guests: int
    n_total_tables: int
    total_capacity: int


def solve(guests: list[Guest], tables: list[Table], max_iter: int = 5000) -> SeatPlanResult:
    """端到端 solve:greedy initial + simulated annealing。"""
    assignments, log = simulated_annealing(guests, tables, max_iter=max_iter)
    guests_map = {g.guest_id: g for g in guests}
    tables_map = {t.table_id: t for t in tables}
    cost = _compute_cost(assignments, guests_map, tables_map)

    # 組裝 TablePlan
    table_plans: list[TablePlan] = []
    for t in tables:
        seated = [guests_map[gid] for gid, tid in assignments.items() if tid == t.table_id]
        group_counts: dict[str, int] = {}
        for g in seated:
            group_counts[g.group] = group_counts.get(g.group, 0) + 1
        table_plans.append(TablePlan(
            table_id=t.table_id,
            table_name=t.name or t.table_id,
            capacity=t.capacity,
            is_vip=t.is_vip,
            assigned_guests=seated,
            n_seated=len(seated),
            groups_at_table=group_counts,
        ))

    return SeatPlanResult(
        table_plans=table_plans,
        cost_breakdown=cost,
        optimization_log=log,
        n_total_guests=len(guests),
        n_total_tables=len(tables),
        total_capacity=sum(t.capacity for t in tables),
    )
