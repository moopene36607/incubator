"""gpscheck — Dynamic Time Warping for GPS route comparison (pure stdlib).

DTW (Sakoe & Chiba 1978) finds the optimal non-linear alignment between
two time series of possibly different lengths. For GPS traces we use
**haversine great-circle distance** as the per-point distance metric.

Standard DP recurrence:
  C[i][j] = d(a_i, b_j) + min(C[i-1][j], C[i][j-1], C[i-1][j-1])

Normalized DTW similarity score = 100 × exp(-DTW_distance / scale).

Pure stdlib (math + dataclass). No numpy / no scipy. Suitable for
short GPS traces (≤ 200 points each), O(n × m) memory + compute.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ============== Domain types ==============
@dataclass
class GPSPoint:
    """A single GPS sample. `t` is seconds elapsed from trip start (optional)."""
    lat: float
    lon: float
    t: float = 0.0    # seconds from trip start


@dataclass
class Route:
    name: str
    points: list[GPSPoint]


# ============== Distance metric (Haversine) ==============
_EARTH_R_M = 6_371_000.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two lat/lon points."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = rlat2 - rlat1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_R_M * c


def point_dist(p: GPSPoint, q: GPSPoint) -> float:
    return haversine(p.lat, p.lon, q.lat, q.lon)


def route_total_distance(route: Route) -> float:
    """Sum of consecutive haversines (meters)."""
    if len(route.points) < 2:
        return 0.0
    return sum(point_dist(route.points[i], route.points[i + 1])
               for i in range(len(route.points) - 1))


def route_duration_s(route: Route) -> float:
    if len(route.points) < 2:
        return 0.0
    return max(0.0, route.points[-1].t - route.points[0].t)


def route_avg_speed_kmh(route: Route) -> float:
    duration = route_duration_s(route)
    if duration <= 0:
        return 0.0
    dist_m = route_total_distance(route)
    return (dist_m / duration) * 3.6


# ============== DTW core ==============
@dataclass
class DTWResult:
    distance_total_m: float                      # raw DTW cost (sum of haversines along path)
    distance_normalized_m: float                 # per-step average
    path_length: int                             # alignment path length
    similarity_score: float                      # 0-100 (higher = more similar)
    alignment_path: list[tuple[int, int]]        # list of (i, j) indices
    cost_matrix: list[list[float]] = field(default_factory=list)


def dtw_cost_matrix(seq_a: list[GPSPoint], seq_b: list[GPSPoint]) -> list[list[float]]:
    """Compute full DTW cost matrix C where C[i][j] is min-cost alignment up to (a_i, b_j)."""
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return []
    INF = float("inf")
    C = [[INF] * m for _ in range(n)]
    C[0][0] = point_dist(seq_a[0], seq_b[0])
    for i in range(1, n):
        C[i][0] = C[i - 1][0] + point_dist(seq_a[i], seq_b[0])
    for j in range(1, m):
        C[0][j] = C[0][j - 1] + point_dist(seq_a[0], seq_b[j])
    for i in range(1, n):
        for j in range(1, m):
            d = point_dist(seq_a[i], seq_b[j])
            C[i][j] = d + min(C[i - 1][j], C[i][j - 1], C[i - 1][j - 1])
    return C


def dtw_backtrace(C: list[list[float]]) -> list[tuple[int, int]]:
    """Standard backtrace from bottom-right to top-left, choosing argmin neighbor."""
    if not C or not C[0]:
        return []
    n, m = len(C), len(C[0])
    i, j = n - 1, m - 1
    path = [(i, j)]
    while i > 0 or j > 0:
        if i == 0:
            j -= 1
        elif j == 0:
            i -= 1
        else:
            # Argmin of (up, left, diag)
            up = C[i - 1][j]
            left = C[i][j - 1]
            diag = C[i - 1][j - 1]
            best = min(up, left, diag)
            if best == diag:
                i -= 1
                j -= 1
            elif best == up:
                i -= 1
            else:
                j -= 1
        path.append((i, j))
    path.reverse()
    return path


def compute_dtw(actual: Route, planned: Route) -> DTWResult:
    """Full DTW between two GPS routes."""
    C = dtw_cost_matrix(actual.points, planned.points)
    if not C:
        return DTWResult(0.0, 0.0, 0, 0.0, [], C)
    path = dtw_backtrace(C)
    total_cost = C[len(actual.points) - 1][len(planned.points) - 1]
    avg_step_cost = total_cost / len(path) if path else 0.0

    # Similarity score: 100 × exp(-avg_step_cost / scale)
    # Scale: 500m per alignment step → score 37%; 100m → 82%; 50m → 90%
    scale_m = 500.0
    similarity = round(100.0 * math.exp(-avg_step_cost / scale_m), 1)

    return DTWResult(
        distance_total_m=round(total_cost, 1),
        distance_normalized_m=round(avg_step_cost, 1),
        path_length=len(path),
        similarity_score=similarity,
        alignment_path=path,
        cost_matrix=C,
    )


# ============== Deviation analysis ==============
@dataclass
class Deviation:
    actual_idx: int
    planned_idx: int
    distance_m: float
    actual_point: GPSPoint
    planned_point: GPSPoint


def identify_deviations(actual: Route, planned: Route,
                         path: list[tuple[int, int]],
                         threshold_m: float = 200.0) -> list[Deviation]:
    """Points along DTW alignment where distance exceeds threshold."""
    deviations = []
    for ai, pi in path:
        a, p = actual.points[ai], planned.points[pi]
        d = point_dist(a, p)
        if d >= threshold_m:
            deviations.append(Deviation(
                actual_idx=ai, planned_idx=pi, distance_m=round(d, 1),
                actual_point=a, planned_point=p,
            ))
    return deviations


# ============== Verdict classification ==============
from enum import Enum


class Verdict(Enum):
    NORMAL = "NORMAL"                          # similarity ≥ 85
    MINOR_DEVIATION = "MINOR_DEVIATION"        # similarity 70-85
    SIGNIFICANT_DEVIATION = "SIGNIFICANT_DEVIATION"   # 50-70
    MAJOR_DEVIATION = "MAJOR_DEVIATION"        # < 50


def classify_route(result: DTWResult) -> Verdict:
    if result.similarity_score >= 85:
        return Verdict.NORMAL
    elif result.similarity_score >= 70:
        return Verdict.MINOR_DEVIATION
    elif result.similarity_score >= 50:
        return Verdict.SIGNIFICANT_DEVIATION
    else:
        return Verdict.MAJOR_DEVIATION


def extra_distance_estimate(actual: Route, planned: Route) -> float:
    """How much longer is actual route vs planned (meters)."""
    return route_total_distance(actual) - route_total_distance(planned)
