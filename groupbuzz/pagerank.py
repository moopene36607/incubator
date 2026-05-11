"""groupbuzz — PageRank-like influence ranking for chat groups (pure stdlib).

Brin & Page (1998) PageRank: stationary distribution of a random walk on a
directed graph (with damping for teleport). Higher PR = more incoming
influence-weighted edges (more people reply to / mention this person).

Edge weighting:
  - Reply (A → B):       weight 1.0
  - Mention (A @ B):     weight 0.7
  - Reaction (A 💛 B):   weight 0.3  (optional, if available)

Edges flow from "noticer" to "noticed" — i.e., person who replies points
to the person they replied to (the influencer gains PageRank).

Pure stdlib (math + collections + dataclass). No numpy / no networkx.
"""

from __future__ import annotations

import math
from collections import defaultdict, Counter
from dataclasses import dataclass, field


# ============== Domain types ==============
@dataclass
class Message:
    """A single chat message."""
    msg_id: str
    sender_id: str
    timestamp: str               # ISO-ish, lexicographic OK
    text: str
    reply_to_msg_id: str | None = None
    mentions: list[str] = field(default_factory=list)        # user_ids
    reactions: dict[str, list[str]] = field(default_factory=dict)  # emoji → [user_ids who reacted]


@dataclass
class GroupSnapshot:
    group_name: str
    members: dict[str, str]      # user_id → display name
    messages: list[Message]


# ============== Build directed graph ==============
def build_influence_graph(snapshot: GroupSnapshot,
                            reply_weight: float = 1.0,
                            mention_weight: float = 0.7,
                            reaction_weight: float = 0.3) -> dict[str, dict[str, float]]:
    """Edge i→j with cumulative weight: i pays attention to j."""
    msg_index = {m.msg_id: m for m in snapshot.messages}
    out_edges: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for m in snapshot.messages:
        sender = m.sender_id
        # Reply edge: sender replies to the original poster
        if m.reply_to_msg_id and m.reply_to_msg_id in msg_index:
            target = msg_index[m.reply_to_msg_id].sender_id
            if target != sender:
                out_edges[sender][target] += reply_weight
        # Mention edges
        for mentioned in m.mentions:
            if mentioned != sender and mentioned in snapshot.members:
                out_edges[sender][mentioned] += mention_weight
        # Reaction edges (others reacting to this sender)
        for emoji, reactors in m.reactions.items():
            for r in reactors:
                if r != sender and r in snapshot.members:
                    out_edges[r][sender] += reaction_weight

    # Convert defaultdict → dict
    return {k: dict(v) for k, v in out_edges.items()}


# ============== Power iteration ==============
@dataclass
class PageRankResult:
    scores: dict[str, float]                # user_id → PageRank
    n_iterations: int
    converged: bool
    damping: float
    n_nodes: int


def pagerank(graph: dict[str, dict[str, float]], all_nodes: list[str],
              damping: float = 0.85, max_iter: int = 100,
              tol: float = 1e-6) -> PageRankResult:
    """Standard PageRank with weighted edges.

    Args:
      graph: i → {j → weight} (edge weights, i 'follows' j)
      all_nodes: list of all node IDs to include (some may have 0 edges)
      damping: teleport probability complement (default 0.85)
    """
    n = len(all_nodes)
    if n == 0:
        return PageRankResult(scores={}, n_iterations=0, converged=True,
                                damping=damping, n_nodes=0)

    # Normalize outgoing weights per node
    out_total: dict[str, float] = {}
    for src, outs in graph.items():
        out_total[src] = sum(outs.values())

    # Initial PR = 1/n
    pr = {node: 1.0 / n for node in all_nodes}

    iter_count = 0
    converged = False
    for it in range(max_iter):
        iter_count = it + 1
        # Dangling nodes: those with 0 outgoing edges — their PR
        # contributes uniformly to all (handled below)
        dangling_pr = sum(pr[n_] for n_ in all_nodes
                           if out_total.get(n_, 0.0) == 0.0)
        new_pr = {node: (1.0 - damping) / n + damping * dangling_pr / n
                   for node in all_nodes}

        for src, outs in graph.items():
            src_pr = pr.get(src, 0.0)
            src_total = out_total[src]
            if src_total <= 0:
                continue
            for dst, w in outs.items():
                if dst in new_pr:
                    new_pr[dst] += damping * src_pr * w / src_total

        # Convergence: max abs diff
        diff = max(abs(new_pr[n_] - pr[n_]) for n_ in all_nodes)
        pr = new_pr
        if diff < tol:
            converged = True
            break

    return PageRankResult(
        scores={k: round(v, 6) for k, v in pr.items()},
        n_iterations=iter_count,
        converged=converged,
        damping=damping,
        n_nodes=n,
    )


# ============== Additional centrality metrics ==============
@dataclass
class MemberStats:
    user_id: str
    name: str
    message_count: int
    in_weight: float        # Σ incoming edge weights (who points to me)
    out_weight: float       # Σ outgoing
    pagerank: float
    pagerank_rank: int      # 1 = top
    role: str = ""          # 'core_influencer' / 'connector' / 'silent' etc.


def degree_centrality(graph: dict[str, dict[str, float]],
                       all_nodes: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    """Returns (in_weight, out_weight) per node."""
    in_w: dict[str, float] = {n: 0.0 for n in all_nodes}
    out_w: dict[str, float] = {n: 0.0 for n in all_nodes}
    for src, outs in graph.items():
        if src in out_w:
            out_w[src] = sum(outs.values())
        for dst, w in outs.items():
            if dst in in_w:
                in_w[dst] += w
    return in_w, out_w


def classify_role(stats: MemberStats, pagerank_threshold: float,
                    median_msg_count: float) -> str:
    """Heuristic role classification."""
    if stats.pagerank >= pagerank_threshold and stats.in_weight > stats.out_weight * 1.5:
        return "core_influencer"      # 高 PR + 多人 reply / mention
    if stats.message_count >= median_msg_count and stats.out_weight > stats.in_weight * 1.5:
        return "connector"            # 主動 reply 多, 帶動氣氛
    if stats.pagerank >= pagerank_threshold and stats.message_count >= median_msg_count:
        return "active_contributor"
    if stats.message_count == 0:
        return "lurker"
    if stats.message_count <= 2 and stats.in_weight == 0:
        return "silent"
    return "regular"


def compute_member_stats(snapshot: GroupSnapshot,
                          graph: dict[str, dict[str, float]],
                          pr_result: PageRankResult) -> list[MemberStats]:
    msg_counts: Counter = Counter()
    for m in snapshot.messages:
        msg_counts[m.sender_id] += 1

    in_w, out_w = degree_centrality(graph, list(snapshot.members.keys()))

    # Ranked PR
    pr_sorted = sorted(pr_result.scores.items(), key=lambda kv: -kv[1])
    pr_rank = {uid: rank + 1 for rank, (uid, _) in enumerate(pr_sorted)}

    median_msg = sorted(msg_counts.values())[len(msg_counts) // 2] if msg_counts else 0
    top_pr_threshold = pr_sorted[max(0, len(pr_sorted) // 5)][1] if pr_sorted else 0  # top 20%

    stats_list = []
    for uid, name in snapshot.members.items():
        s = MemberStats(
            user_id=uid, name=name,
            message_count=msg_counts.get(uid, 0),
            in_weight=round(in_w.get(uid, 0.0), 3),
            out_weight=round(out_w.get(uid, 0.0), 3),
            pagerank=pr_result.scores.get(uid, 0.0),
            pagerank_rank=pr_rank.get(uid, len(snapshot.members)),
        )
        s.role = classify_role(s, top_pr_threshold, median_msg)
        stats_list.append(s)

    stats_list.sort(key=lambda s: -s.pagerank)
    return stats_list


# ============== Group-level analytics ==============
@dataclass
class GroupHealth:
    n_members: int
    n_active_members: int     # message_count > 0
    n_silent_members: int     # message_count <= 2
    n_messages: int
    pagerank_concentration: float    # top 5 PR sum / total
    activity_skew: float             # top 20% senders' messages / total
    n_lurkers: int


def compute_group_health(snapshot: GroupSnapshot,
                           stats: list[MemberStats]) -> GroupHealth:
    n = len(snapshot.members)
    active = sum(1 for s in stats if s.message_count > 0)
    silent = sum(1 for s in stats if s.message_count <= 2)
    lurkers = sum(1 for s in stats if s.message_count == 0)

    total_pr = sum(s.pagerank for s in stats) or 1.0
    top5_pr = sum(s.pagerank for s in stats[:5])
    pr_concentration = top5_pr / total_pr

    by_msg = sorted(stats, key=lambda s: -s.message_count)
    top20_pct_count = max(1, n // 5)
    total_msg = sum(s.message_count for s in stats) or 1
    top20_msg_count = sum(s.message_count for s in by_msg[:top20_pct_count])
    activity_skew = top20_msg_count / total_msg

    return GroupHealth(
        n_members=n,
        n_active_members=active,
        n_silent_members=silent,
        n_messages=len(snapshot.messages),
        pagerank_concentration=round(pr_concentration, 3),
        activity_skew=round(activity_skew, 3),
        n_lurkers=lurkers,
    )
