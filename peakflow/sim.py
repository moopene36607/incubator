"""peakflow — 餐廳尖峰時段 agent-based simulation(純函式 / no I/O / no LLM).

模擬 3 類 agents:
  - Customer: 到達、等待、用餐、離開
  - Server: 接客、點餐、上菜、忙碌中
  - Kitchen: 接單、烹飪(共用一個 kitchen 容量)

100% stdlib(只用 random + heapq + dataclass)。

Event-driven simulation:
  - 用 heapq 排序事件依時間發生
  - 處理一個 event 可能觸發後續 events
  - 模擬到 end_time(分鐘)結束
"""

from __future__ import annotations

import heapq
import random
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class CustomerState(Enum):
    ARRIVED = "arrived"
    WAITING = "waiting"
    SEATED = "seated"
    ORDERED = "ordered"
    SERVED = "served"
    EATING = "eating"
    LEFT = "left"
    LOST = "lost"               # left because waited too long


@dataclass
class Customer:
    customer_id: int
    arrival_time: float
    party_size: int
    avg_check_per_person_ntd: int
    patience_minutes: float            # 願意等的最長時間
    state: CustomerState = CustomerState.ARRIVED
    seated_time: float | None = None
    order_taken_time: float | None = None
    order_ready_time: float | None = None
    left_time: float | None = None
    wait_time: float = 0.0
    table_id: int | None = None


@dataclass
class Table:
    table_id: int
    capacity: int                       # 桌子座位數
    occupied_by: int | None = None      # customer_id


@dataclass
class RestaurantConfig:
    name: str
    n_tables: int
    table_capacities: list[int]         # 每桌的座位數(len == n_tables)
    n_servers: int                      # 服務員數
    kitchen_capacity: int               # 同時可處理訂單數
    # 服務時間參數(分鐘)
    server_order_time_min: float = 1.5
    server_order_time_max: float = 3.5
    server_deliver_time_min: float = 0.5
    server_deliver_time_max: float = 1.5
    kitchen_cook_time_min: float = 6.0
    kitchen_cook_time_max: float = 14.0
    avg_eat_time_min: float = 18.0
    avg_eat_time_max: float = 35.0
    avg_check_per_person_ntd: int = 250
    avg_patience_min: float = 8.0
    patience_std: float = 4.0


@dataclass
class SimulationConfig:
    simulation_duration_min: float      # 模擬幾分鐘(e.g., 120 for 11:30-13:30)
    customer_arrival_rate: float        # 平均每分鐘到達多少 party(Poisson lambda)
    seed: int = 42


# ===== Event queue =====
@dataclass
class Event:
    time: float
    event_type: str
    customer_id: int | None = None
    table_id: int | None = None

    def __lt__(self, other: "Event") -> bool:
        return self.time < other.time


# ===== Simulation result =====
@dataclass
class SimulationResult:
    config_name: str
    n_arrived: int
    n_served: int                       # 完成用餐離開
    n_lost: int                         # 等不到桌離開
    n_still_waiting_at_end: int
    n_still_eating_at_end: int
    revenue_ntd: int
    avg_wait_time_min: float
    p50_wait_time_min: float
    p95_wait_time_min: float
    max_wait_time_min: float
    server_utilization_pct: float       # 平均使用率
    kitchen_utilization_pct: float
    table_utilization_pct: float
    loss_rate_pct: float                # 流失率 = n_lost / n_arrived
    raw_customers: list[Customer] = field(default_factory=list)


# ===== Simulation engine =====
def _sample_party_size(rng: random.Random) -> int:
    """1-4 人,加權 1(20%) / 2(50%) / 3(15%) / 4(15%)."""
    r = rng.random()
    if r < 0.20:
        return 1
    if r < 0.70:
        return 2
    if r < 0.85:
        return 3
    return 4


def _find_table(tables: list[Table], party_size: int) -> Table | None:
    """找最小容量但可容納 party_size 的空桌(efficient packing)。"""
    candidates = [t for t in tables if t.occupied_by is None and t.capacity >= party_size]
    if not candidates:
        return None
    # 挑容量最接近的桌(efficient seating)
    candidates.sort(key=lambda t: t.capacity)
    return candidates[0]


def simulate(rest: RestaurantConfig, sim_cfg: SimulationConfig) -> SimulationResult:
    """跑一次完整 simulation,回傳 metrics。"""
    rng = random.Random(sim_cfg.seed)
    tables = [Table(table_id=i, capacity=cap) for i, cap in enumerate(rest.table_capacities)]

    customers: list[Customer] = []
    waiting_queue: list[int] = []           # customer_ids waiting for table
    servers_busy_until: list[float] = [0.0] * rest.n_servers
    kitchen_queue: list[float] = []         # finish times for active orders

    events: list[Event] = []

    # Generate customer arrivals using Poisson process
    t = 0.0
    next_customer_id = 0
    while t < sim_cfg.simulation_duration_min:
        # Inter-arrival time = exponential with mean = 1 / rate
        inter_arrival = rng.expovariate(sim_cfg.customer_arrival_rate)
        t += inter_arrival
        if t >= sim_cfg.simulation_duration_min:
            break
        party_size = _sample_party_size(rng)
        patience = max(2.0, rng.gauss(rest.avg_patience_min, rest.patience_std))
        c = Customer(
            customer_id=next_customer_id,
            arrival_time=t,
            party_size=party_size,
            avg_check_per_person_ntd=rest.avg_check_per_person_ntd,
            patience_minutes=patience,
        )
        customers.append(c)
        heapq.heappush(events, Event(time=t, event_type="arrival", customer_id=c.customer_id))
        next_customer_id += 1

    # Stats trackers for utilization
    server_busy_time = [0.0] * rest.n_servers
    kitchen_busy_minutes = 0.0
    table_busy_minutes = [0.0] * rest.n_tables
    sim_end = sim_cfg.simulation_duration_min

    # Process events
    while events:
        ev = heapq.heappop(events)
        if ev.time > sim_end + 60:   # 60 min grace period after end for current diners
            break

        if ev.event_type == "arrival":
            c = customers[ev.customer_id]
            c.state = CustomerState.WAITING
            # Try to seat immediately
            table = _find_table(tables, c.party_size)
            if table is not None:
                # Seat directly
                table.occupied_by = c.customer_id
                c.table_id = table.table_id
                c.seated_time = ev.time
                c.wait_time = 0.0
                c.state = CustomerState.SEATED
                heapq.heappush(events, Event(time=ev.time, event_type="take_order", customer_id=c.customer_id))
            else:
                waiting_queue.append(c.customer_id)
                # Schedule patience-out check
                heapq.heappush(events, Event(
                    time=ev.time + c.patience_minutes,
                    event_type="patience_out",
                    customer_id=c.customer_id,
                ))

        elif ev.event_type == "patience_out":
            c = customers[ev.customer_id]
            if c.state == CustomerState.WAITING:
                # Still waiting, leave
                c.state = CustomerState.LOST
                c.left_time = ev.time
                c.wait_time = ev.time - c.arrival_time
                if c.customer_id in waiting_queue:
                    waiting_queue.remove(c.customer_id)

        elif ev.event_type == "take_order":
            c = customers[ev.customer_id]
            # Find idle server
            server_idx = -1
            for i, busy_until in enumerate(servers_busy_until):
                if busy_until <= ev.time:
                    server_idx = i
                    break
            if server_idx == -1:
                # No server available, retry later
                next_free = min(servers_busy_until)
                heapq.heappush(events, Event(time=next_free + 0.1, event_type="take_order", customer_id=c.customer_id))
                continue
            # Server takes order
            order_duration = rng.uniform(rest.server_order_time_min, rest.server_order_time_max)
            servers_busy_until[server_idx] = ev.time + order_duration
            server_busy_time[server_idx] += order_duration
            c.order_taken_time = ev.time + order_duration
            c.state = CustomerState.ORDERED
            heapq.heappush(events, Event(time=c.order_taken_time, event_type="send_to_kitchen", customer_id=c.customer_id))

        elif ev.event_type == "send_to_kitchen":
            c = customers[ev.customer_id]
            # Check kitchen capacity
            # Remove completed orders
            kitchen_queue[:] = [t_ for t_ in kitchen_queue if t_ > ev.time]
            if len(kitchen_queue) >= rest.kitchen_capacity:
                # Kitchen full, wait
                next_free = min(kitchen_queue)
                heapq.heappush(events, Event(time=next_free + 0.05, event_type="send_to_kitchen", customer_id=c.customer_id))
                continue
            cook_time = rng.uniform(rest.kitchen_cook_time_min, rest.kitchen_cook_time_max)
            ready_time = ev.time + cook_time
            kitchen_queue.append(ready_time)
            kitchen_busy_minutes += cook_time
            heapq.heappush(events, Event(time=ready_time, event_type="food_ready", customer_id=c.customer_id))

        elif ev.event_type == "food_ready":
            c = customers[ev.customer_id]
            c.order_ready_time = ev.time
            # Need server to deliver
            heapq.heappush(events, Event(time=ev.time, event_type="deliver", customer_id=c.customer_id))

        elif ev.event_type == "deliver":
            c = customers[ev.customer_id]
            server_idx = -1
            for i, busy_until in enumerate(servers_busy_until):
                if busy_until <= ev.time:
                    server_idx = i
                    break
            if server_idx == -1:
                next_free = min(servers_busy_until)
                heapq.heappush(events, Event(time=next_free + 0.05, event_type="deliver", customer_id=c.customer_id))
                continue
            deliver_time = rng.uniform(rest.server_deliver_time_min, rest.server_deliver_time_max)
            servers_busy_until[server_idx] = ev.time + deliver_time
            server_busy_time[server_idx] += deliver_time
            c.state = CustomerState.SERVED
            # Start eating
            eat_duration = rng.uniform(rest.avg_eat_time_min, rest.avg_eat_time_max)
            heapq.heappush(events, Event(time=ev.time + deliver_time + eat_duration, event_type="finish_meal", customer_id=c.customer_id))

        elif ev.event_type == "finish_meal":
            c = customers[ev.customer_id]
            c.state = CustomerState.LEFT
            c.left_time = ev.time
            # Free table
            if c.table_id is not None and c.table_id < len(tables):
                table_busy_minutes[c.table_id] += ev.time - (c.seated_time or ev.time)
                tables[c.table_id].occupied_by = None
                # Try to seat next in waiting queue
                if waiting_queue:
                    # Find first customer in queue that fits
                    for waiting_id in list(waiting_queue):
                        wc = customers[waiting_id]
                        if wc.state != CustomerState.WAITING:
                            waiting_queue.remove(waiting_id)
                            continue
                        table = _find_table(tables, wc.party_size)
                        if table is not None:
                            table.occupied_by = wc.customer_id
                            wc.table_id = table.table_id
                            wc.seated_time = ev.time
                            wc.wait_time = ev.time - wc.arrival_time
                            wc.state = CustomerState.SEATED
                            waiting_queue.remove(waiting_id)
                            heapq.heappush(events, Event(time=ev.time, event_type="take_order", customer_id=wc.customer_id))
                            break

    # Compute metrics
    n_served = sum(1 for c in customers if c.state == CustomerState.LEFT)
    n_lost = sum(1 for c in customers if c.state == CustomerState.LOST)
    n_still_waiting = sum(1 for c in customers if c.state == CustomerState.WAITING)
    n_still_eating = sum(1 for c in customers if c.state in (CustomerState.SEATED, CustomerState.ORDERED, CustomerState.SERVED))

    wait_times = [c.wait_time for c in customers if c.wait_time > 0 or c.state == CustomerState.LOST]
    if wait_times:
        avg_wait = statistics.mean(wait_times)
        p50_wait = statistics.median(wait_times)
        p95_wait = sorted(wait_times)[max(0, int(len(wait_times) * 0.95) - 1)] if len(wait_times) >= 20 else max(wait_times)
        max_wait = max(wait_times)
    else:
        avg_wait = p50_wait = p95_wait = max_wait = 0.0

    revenue = sum(c.party_size * c.avg_check_per_person_ntd for c in customers if c.state == CustomerState.LEFT)

    server_util_pct = (sum(server_busy_time) / (rest.n_servers * sim_end) * 100) if sim_end > 0 else 0
    kitchen_util_pct = (kitchen_busy_minutes / (rest.kitchen_capacity * sim_end) * 100) if sim_end > 0 else 0
    table_util_pct = (sum(table_busy_minutes) / (rest.n_tables * sim_end) * 100) if sim_end > 0 else 0
    loss_rate = (n_lost / len(customers) * 100) if customers else 0

    return SimulationResult(
        config_name=rest.name,
        n_arrived=len(customers),
        n_served=n_served,
        n_lost=n_lost,
        n_still_waiting_at_end=n_still_waiting,
        n_still_eating_at_end=n_still_eating,
        revenue_ntd=revenue,
        avg_wait_time_min=round(avg_wait, 2),
        p50_wait_time_min=round(p50_wait, 2),
        p95_wait_time_min=round(p95_wait, 2),
        max_wait_time_min=round(max_wait, 2),
        server_utilization_pct=round(server_util_pct, 1),
        kitchen_utilization_pct=round(min(100.0, kitchen_util_pct), 1),
        table_utilization_pct=round(table_util_pct, 1),
        loss_rate_pct=round(loss_rate, 1),
        raw_customers=customers,
    )


# ===== Scenario comparison =====
@dataclass
class ScenarioComparison:
    scenarios: list[tuple[str, SimulationResult]]
    baseline_idx: int = 0

    def revenue_delta(self, scenario_idx: int) -> int:
        return self.scenarios[scenario_idx][1].revenue_ntd - self.scenarios[self.baseline_idx][1].revenue_ntd


def run_scenarios(restaurants: list[tuple[str, RestaurantConfig]], sim_cfg: SimulationConfig,
                   n_runs: int = 5) -> ScenarioComparison:
    """為每個 scenario 跑多次 simulation,平均後比較。"""
    scenario_results: list[tuple[str, SimulationResult]] = []
    for name, rest in restaurants:
        results = []
        for run in range(n_runs):
            this_cfg = SimulationConfig(
                simulation_duration_min=sim_cfg.simulation_duration_min,
                customer_arrival_rate=sim_cfg.customer_arrival_rate,
                seed=sim_cfg.seed + run,
            )
            results.append(simulate(rest, this_cfg))
        # Aggregate
        avg = SimulationResult(
            config_name=name,
            n_arrived=int(statistics.mean(r.n_arrived for r in results)),
            n_served=int(statistics.mean(r.n_served for r in results)),
            n_lost=int(statistics.mean(r.n_lost for r in results)),
            n_still_waiting_at_end=int(statistics.mean(r.n_still_waiting_at_end for r in results)),
            n_still_eating_at_end=int(statistics.mean(r.n_still_eating_at_end for r in results)),
            revenue_ntd=int(statistics.mean(r.revenue_ntd for r in results)),
            avg_wait_time_min=round(statistics.mean(r.avg_wait_time_min for r in results), 2),
            p50_wait_time_min=round(statistics.mean(r.p50_wait_time_min for r in results), 2),
            p95_wait_time_min=round(statistics.mean(r.p95_wait_time_min for r in results), 2),
            max_wait_time_min=round(max(r.max_wait_time_min for r in results), 2),
            server_utilization_pct=round(statistics.mean(r.server_utilization_pct for r in results), 1),
            kitchen_utilization_pct=round(statistics.mean(r.kitchen_utilization_pct for r in results), 1),
            table_utilization_pct=round(statistics.mean(r.table_utilization_pct for r in results), 1),
            loss_rate_pct=round(statistics.mean(r.loss_rate_pct for r in results), 1),
        )
        scenario_results.append((name, avg))
    return ScenarioComparison(scenarios=scenario_results, baseline_idx=0)
