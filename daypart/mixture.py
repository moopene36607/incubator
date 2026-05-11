"""daypart — 2D Gaussian Mixture EM 演算法(純函式 / no I/O / no LLM).

責任:
  - 從 POS transactions(時間 × 客單價)用 EM 演算法自動找 K 個客群 cluster
  - 每個 cluster 帶 weight + mean(time, spend) + var(time, spend)
  - 對每筆 transaction 計算其所屬 cluster(soft assignment)
  - 對每個 cluster 算 profile(平均時段 + 平均客單價 + 佔比 + 樣本數)

100% stdlib(只用 math + statistics + dataclass)。

EM 演算法(2D diagonal Gaussian Mixture):
  E-step: γ_nk = π_k × N(x_n | μ_k, Σ_k) / Σ_j(π_j × N(x_n | μ_j, Σ_j))
  M-step:
    π_k = Σ_n(γ_nk) / N
    μ_k = Σ_n(γ_nk × x_n) / Σ_n(γ_nk)
    Σ_k = Σ_n(γ_nk × (x_n - μ_k)²) / Σ_n(γ_nk)  (diagonal)
  Iterate until log-likelihood change < tolerance OR max_iter
"""

from __future__ import annotations

import csv
import math
import statistics
from dataclasses import dataclass, field


@dataclass
class Transaction:
    """一筆交易紀錄。"""
    time_minutes: int            # 0-1439(00:00 = 0, 23:59 = 1439)
    spend_ntd: int               # 客單價
    weekday: int = 0             # 0=Mon, 6=Sun(prototype 不用)


def load_csv(path: str) -> list[Transaction]:
    records: list[Transaction] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # time 接受 "HH:MM" 或 minutes
            t = row["time"].strip()
            if ":" in t:
                hh, mm = t.split(":")
                tm = int(hh) * 60 + int(mm)
            else:
                tm = int(t)
            records.append(Transaction(
                time_minutes=tm,
                spend_ntd=int(row["spend_ntd"]),
                weekday=int(row.get("weekday", 0)),
            ))
    return records


# ===== Gaussian Mixture data structures =====
@dataclass
class GaussianCluster:
    weight: float                # π_k(0-1,sum = 1)
    mu_time: float               # 時段中心(分鐘)
    mu_spend: float              # 客單價中心
    var_time: float              # 時段變異數(min²)
    var_spend: float             # 客單價變異數(NT$²)
    n_assigned: int = 0          # 軟分配後該 cluster 的「等效」樣本數
    cluster_id: int = 0


def _gaussian_2d_diag_log(x_time: float, x_spend: float, c: GaussianCluster) -> float:
    """log N(x | μ, Σ_diag) — diagonal covariance 2D Gaussian log-PDF."""
    a = (x_time - c.mu_time) ** 2 / c.var_time
    b = (x_spend - c.mu_spend) ** 2 / c.var_spend
    log_norm = math.log(2 * math.pi) + 0.5 * math.log(c.var_time * c.var_spend)
    return -0.5 * (a + b) - log_norm


def _log_sum_exp(logs: list[float]) -> float:
    """數值穩定的 log(sum(exp(logs)))。"""
    m = max(logs)
    return m + math.log(sum(math.exp(x - m) for x in logs))


# ===== Initialization =====
def _initialize_clusters(records: list[Transaction], k: int) -> list[GaussianCluster]:
    """用 quantile-based 初始化(更 deterministic 比 random)。"""
    times = sorted(r.time_minutes for r in records)
    spends = sorted(r.spend_ntd for r in records)
    mean_spend = statistics.mean(spends)

    # 用 time 的 k 個 quantile 點作初始 μ_time
    clusters = []
    for i in range(k):
        q = (i + 0.5) / k
        idx = min(len(times) - 1, int(q * len(times)))
        clusters.append(GaussianCluster(
            weight=1.0 / k,
            mu_time=float(times[idx]),
            mu_spend=float(mean_spend),
            var_time=10000.0,          # 100 min std
            var_spend=2500.0,           # NT$50 std
            cluster_id=i,
        ))
    return clusters


# ===== EM step =====
def _em_iteration(records: list[Transaction], clusters: list[GaussianCluster]) -> tuple[list[GaussianCluster], float, list[list[float]]]:
    """執行一次 E-step + M-step,回傳新的 clusters + log-likelihood + responsibilities。"""
    k = len(clusters)
    log_likelihood = 0.0
    responsibilities: list[list[float]] = []

    # E-step: 對每筆 transaction 算 γ_nk
    for r in records:
        log_scores = [math.log(c.weight) + _gaussian_2d_diag_log(r.time_minutes, r.spend_ntd, c)
                       for c in clusters]
        log_total = _log_sum_exp(log_scores)
        log_likelihood += log_total
        gamma = [math.exp(ls - log_total) for ls in log_scores]
        responsibilities.append(gamma)

    # M-step: 用 γ_nk 更新 μ / σ² / π
    new_clusters: list[GaussianCluster] = []
    for j in range(k):
        sum_g = sum(resp[j] for resp in responsibilities)
        if sum_g < 1e-9:
            new_clusters.append(clusters[j])
            continue
        mu_t = sum(resp[j] * r.time_minutes for resp, r in zip(responsibilities, records)) / sum_g
        mu_s = sum(resp[j] * r.spend_ntd for resp, r in zip(responsibilities, records)) / sum_g
        var_t = sum(resp[j] * (r.time_minutes - mu_t) ** 2 for resp, r in zip(responsibilities, records)) / sum_g
        var_s = sum(resp[j] * (r.spend_ntd - mu_s) ** 2 for resp, r in zip(responsibilities, records)) / sum_g
        # Floor variance to avoid degenerate clusters
        var_t = max(var_t, 100.0)
        var_s = max(var_s, 25.0)
        weight = sum_g / len(records)
        new_clusters.append(GaussianCluster(
            weight=weight,
            mu_time=mu_t,
            mu_spend=mu_s,
            var_time=var_t,
            var_spend=var_s,
            n_assigned=round(sum_g),
            cluster_id=clusters[j].cluster_id,
        ))
    return new_clusters, log_likelihood, responsibilities


def fit_em(records: list[Transaction], k: int = 3, max_iter: int = 100, tol: float = 1e-4) -> tuple[list[GaussianCluster], int, float]:
    """跑 EM 直到收斂或 max_iter。回傳 (clusters, n_iter, final_log_likelihood)。"""
    if not records:
        return [], 0, 0.0
    clusters = _initialize_clusters(records, k)
    prev_ll = -math.inf
    for it in range(1, max_iter + 1):
        new_clusters, ll, _ = _em_iteration(records, clusters)
        if abs(ll - prev_ll) < tol:
            clusters = new_clusters
            return clusters, it, ll
        clusters = new_clusters
        prev_ll = ll
    return clusters, max_iter, prev_ll


def assign_transactions(records: list[Transaction], clusters: list[GaussianCluster]) -> list[int]:
    """為每筆 transaction 分配最可能的 cluster(hard assignment)。"""
    assignments: list[int] = []
    for r in records:
        log_scores = [math.log(c.weight) + _gaussian_2d_diag_log(r.time_minutes, r.spend_ntd, c)
                       for c in clusters]
        assignments.append(log_scores.index(max(log_scores)))
    return assignments


# ===== Cluster profile =====
@dataclass
class ClusterProfile:
    cluster_id: int
    weight: float                        # 該 cluster 占比 %
    n_transactions: int                  # hard assignment 後的樣本數
    mu_time: float
    mu_time_label: str                   # "07:30" format
    mu_spend: float
    std_time_minutes: float
    std_spend: float
    time_range_label: str                # "06:30-09:30 主要時段"
    spend_range_label: str               # "NT$ 60-100"
    total_revenue_contribution_ntd: int  # 該 cluster 對總營收的估貢獻


def _minutes_to_hhmm(minutes: float) -> str:
    h = int(minutes // 60) % 24
    m = int(minutes % 60)
    return f"{h:02d}:{m:02d}"


def profile_clusters(records: list[Transaction], clusters: list[GaussianCluster], assignments: list[int]) -> list[ClusterProfile]:
    """為每個 cluster 算 profile(hard assignment 後的統計)。"""
    profiles: list[ClusterProfile] = []
    for k, c in enumerate(clusters):
        idxs = [i for i, a in enumerate(assignments) if a == k]
        n = len(idxs)
        if n == 0:
            profiles.append(ClusterProfile(
                cluster_id=k, weight=c.weight, n_transactions=0,
                mu_time=c.mu_time, mu_time_label=_minutes_to_hhmm(c.mu_time),
                mu_spend=c.mu_spend, std_time_minutes=math.sqrt(c.var_time),
                std_spend=math.sqrt(c.var_spend),
                time_range_label="(空 cluster)", spend_range_label="(空 cluster)",
                total_revenue_contribution_ntd=0,
            ))
            continue
        cluster_records = [records[i] for i in idxs]
        times = [r.time_minutes for r in cluster_records]
        spends = [r.spend_ntd for r in cluster_records]
        std_t = statistics.stdev(times) if n > 1 else math.sqrt(c.var_time)
        std_s = statistics.stdev(spends) if n > 1 else math.sqrt(c.var_spend)
        t_lo = max(0, c.mu_time - std_t)
        t_hi = min(1439, c.mu_time + std_t)
        s_lo = max(0, c.mu_spend - std_s)
        s_hi = c.mu_spend + std_s
        total_rev = sum(spends)
        profiles.append(ClusterProfile(
            cluster_id=k,
            weight=round(c.weight, 4),
            n_transactions=n,
            mu_time=c.mu_time,
            mu_time_label=_minutes_to_hhmm(c.mu_time),
            mu_spend=round(c.mu_spend, 0),
            std_time_minutes=round(std_t, 1),
            std_spend=round(std_s, 1),
            time_range_label=f"{_minutes_to_hhmm(t_lo)}-{_minutes_to_hhmm(t_hi)}",
            spend_range_label=f"NT$ {int(s_lo)}-{int(s_hi)}",
            total_revenue_contribution_ntd=total_rev,
        ))
    # 按 mu_time 排序(早→晚)
    profiles.sort(key=lambda p: p.mu_time)
    return profiles


# ===== Model selection (BIC) =====
def bayesian_info_criterion(log_likelihood: float, n_records: int, k: int) -> float:
    """BIC = -2 LL + p × log(N),較低代表更好的模型。

    每個 cluster 有 5 個自由參數(μ_t, μ_s, σ²_t, σ²_s, π_k)。
    """
    n_params = k * 5 - 1  # -1 因為 π 受限和為 1
    return -2 * log_likelihood + n_params * math.log(n_records)


def find_best_k(records: list[Transaction], k_range: tuple[int, ...] = (2, 3, 4, 5)) -> dict:
    """跑 k=2..5 找 BIC 最低的 k。"""
    results = []
    for k in k_range:
        clusters, n_iter, ll = fit_em(records, k=k)
        bic = bayesian_info_criterion(ll, len(records), k)
        results.append({
            "k": k,
            "log_likelihood": round(ll, 2),
            "bic": round(bic, 2),
            "n_iter": n_iter,
        })
    best = min(results, key=lambda r: r["bic"])
    return {
        "all_results": results,
        "best_k": best["k"],
        "best_bic": best["bic"],
    }
