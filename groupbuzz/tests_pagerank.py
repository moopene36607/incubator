"""groupbuzz edge tests — pure-function PageRank correctness."""
from __future__ import annotations

from pagerank import (
    Message, GroupSnapshot, build_influence_graph, pagerank,
    degree_centrality, compute_member_stats, compute_group_health,
    classify_role, MemberStats,
)


def _mk_msg(mid, sender, ts="2026-05-11T10:00", text="x",
             reply=None, mentions=None, reactions=None):
    return Message(msg_id=mid, sender_id=sender, timestamp=ts, text=text,
                    reply_to_msg_id=reply, mentions=mentions or [],
                    reactions=reactions or {})


def test_pagerank_uniform_with_no_edges():
    """No edges → uniform PR = 1/n."""
    snap = GroupSnapshot(group_name="t", members={"U1": "A", "U2": "B", "U3": "C"},
                          messages=[_mk_msg("M1", "U1")])
    graph = build_influence_graph(snap)
    pr = pagerank(graph, list(snap.members.keys()))
    # All scores roughly 1/3 since no edges
    assert all(abs(s - 1/3) < 0.02 for s in pr.scores.values())


def test_pagerank_converges():
    """PageRank should converge for a small graph."""
    snap = GroupSnapshot(group_name="t",
                          members={"U1": "A", "U2": "B"},
                          messages=[
                              _mk_msg("M1", "U1"),
                              _mk_msg("M2", "U2", reply="M1"),
                          ])
    graph = build_influence_graph(snap)
    pr = pagerank(graph, list(snap.members.keys()), max_iter=100)
    assert pr.converged
    # U1 should have higher PR (B replies to A)
    assert pr.scores["U1"] > pr.scores["U2"]


def test_pagerank_scores_sum_close_to_1():
    """Σ PR ≈ 1 (probability distribution)."""
    snap = GroupSnapshot(group_name="t",
                          members={"U1": "A", "U2": "B", "U3": "C", "U4": "D"},
                          messages=[
                              _mk_msg("M1", "U1"),
                              _mk_msg("M2", "U2", reply="M1"),
                              _mk_msg("M3", "U3", reply="M1"),
                              _mk_msg("M4", "U4", reply="M1"),
                          ])
    graph = build_influence_graph(snap)
    pr = pagerank(graph, list(snap.members.keys()))
    total = sum(pr.scores.values())
    assert abs(total - 1.0) < 0.01


def test_build_graph_reply_edge():
    """Reply creates edge from replier → target."""
    snap = GroupSnapshot(group_name="t",
                          members={"U1": "A", "U2": "B"},
                          messages=[
                              _mk_msg("M1", "U1"),
                              _mk_msg("M2", "U2", reply="M1"),
                          ])
    graph = build_influence_graph(snap)
    assert "U2" in graph
    assert "U1" in graph["U2"]
    assert graph["U2"]["U1"] >= 1.0


def test_build_graph_mention_edge():
    """Mention creates edge from mentioner → mentioned."""
    snap = GroupSnapshot(group_name="t",
                          members={"U1": "A", "U2": "B"},
                          messages=[
                              _mk_msg("M1", "U2", mentions=["U1"]),
                          ])
    graph = build_influence_graph(snap)
    assert "U2" in graph
    assert "U1" in graph["U2"]
    assert graph["U2"]["U1"] >= 0.5


def test_build_graph_no_self_edge():
    """Self-mention doesn't create self-edge."""
    snap = GroupSnapshot(group_name="t",
                          members={"U1": "A"},
                          messages=[
                              _mk_msg("M1", "U1", mentions=["U1"]),
                          ])
    graph = build_influence_graph(snap)
    assert "U1" not in graph or "U1" not in graph.get("U1", {})


def test_build_graph_reactions():
    """Reactions create edges from reactor → message sender."""
    snap = GroupSnapshot(group_name="t",
                          members={"U1": "A", "U2": "B", "U3": "C"},
                          messages=[
                              _mk_msg("M1", "U1", reactions={"❤️": ["U2", "U3"]}),
                          ])
    graph = build_influence_graph(snap)
    assert graph["U2"]["U1"] > 0
    assert graph["U3"]["U1"] > 0


def test_degree_centrality_basic():
    """in-weight and out-weight computed correctly."""
    snap = GroupSnapshot(group_name="t",
                          members={"U1": "A", "U2": "B"},
                          messages=[
                              _mk_msg("M1", "U1"),
                              _mk_msg("M2", "U2", reply="M1"),
                          ])
    graph = build_influence_graph(snap)
    in_w, out_w = degree_centrality(graph, list(snap.members.keys()))
    assert in_w["U1"] > 0
    assert out_w["U2"] > 0
    assert in_w["U2"] == 0
    assert out_w["U1"] == 0


def test_higher_pagerank_for_more_replies():
    """Member who gets more replies → higher PR."""
    members = {f"U{i}": f"N{i}" for i in range(1, 6)}
    messages = [_mk_msg("M0", "U1")]
    # 4 others reply to U1
    for i in range(2, 6):
        messages.append(_mk_msg(f"M{i}", f"U{i}", reply="M0"))
    snap = GroupSnapshot(group_name="t", members=members, messages=messages)
    graph = build_influence_graph(snap)
    pr = pagerank(graph, list(members.keys()))
    assert pr.scores["U1"] == max(pr.scores.values())


def test_classify_role_core_influencer():
    """High PR + high in_weight → core_influencer."""
    s = MemberStats(user_id="U1", name="A", message_count=10,
                     in_weight=20.0, out_weight=5.0, pagerank=0.5, pagerank_rank=1)
    role = classify_role(s, pagerank_threshold=0.1, median_msg_count=3)
    assert role == "core_influencer"


def test_classify_role_lurker():
    """Zero messages → lurker."""
    s = MemberStats(user_id="U1", name="A", message_count=0,
                     in_weight=0.0, out_weight=0.0, pagerank=0.01, pagerank_rank=50)
    role = classify_role(s, pagerank_threshold=0.1, median_msg_count=3)
    assert role == "lurker"


def test_compute_member_stats_returns_sorted():
    """compute_member_stats returns list sorted by descending PR."""
    snap = GroupSnapshot(group_name="t",
                          members={"U1": "A", "U2": "B", "U3": "C"},
                          messages=[
                              _mk_msg("M1", "U1"),
                              _mk_msg("M2", "U2", reply="M1"),
                              _mk_msg("M3", "U3", reply="M1"),
                          ])
    graph = build_influence_graph(snap)
    pr = pagerank(graph, list(snap.members.keys()))
    stats = compute_member_stats(snap, graph, pr)
    for i in range(1, len(stats)):
        assert stats[i - 1].pagerank >= stats[i].pagerank


def test_compute_group_health_counts_lurkers():
    """Group health correctly counts lurkers."""
    snap = GroupSnapshot(group_name="t",
                          members={"U1": "A", "U2": "B", "U3": "C", "U4": "D"},
                          messages=[
                              _mk_msg("M1", "U1"),
                              _mk_msg("M2", "U1"),
                              _mk_msg("M3", "U2"),
                          ])
    graph = build_influence_graph(snap)
    pr = pagerank(graph, list(snap.members.keys()))
    stats = compute_member_stats(snap, graph, pr)
    health = compute_group_health(snap, stats)
    assert health.n_members == 4
    assert health.n_lurkers == 2    # U3, U4
    assert health.n_messages == 3


def test_pagerank_deterministic():
    """Same input → same PR."""
    snap = GroupSnapshot(group_name="t",
                          members={"U1": "A", "U2": "B", "U3": "C"},
                          messages=[
                              _mk_msg("M1", "U1"),
                              _mk_msg("M2", "U2", reply="M1"),
                              _mk_msg("M3", "U3", reply="M2"),
                          ])
    graph = build_influence_graph(snap)
    pr1 = pagerank(graph, list(snap.members.keys()), max_iter=100)
    pr2 = pagerank(graph, list(snap.members.keys()), max_iter=100)
    assert pr1.scores == pr2.scores


def test_empty_graph():
    """Empty graph handled gracefully."""
    snap = GroupSnapshot(group_name="t", members={}, messages=[])
    graph = build_influence_graph(snap)
    pr = pagerank(graph, [])
    assert pr.scores == {}


def test_dangling_nodes_handled():
    """Nodes with no out-edges shouldn't break PR."""
    members = {"U1": "A", "U2": "B", "U3": "C"}
    messages = [
        _mk_msg("M1", "U1"),
        _mk_msg("M2", "U2", reply="M1"),
        # U3 has 0 messages → dangling
    ]
    snap = GroupSnapshot(group_name="t", members=members, messages=messages)
    graph = build_influence_graph(snap)
    pr = pagerank(graph, list(members.keys()))
    assert pr.converged
    # Sum should still be ~1
    assert abs(sum(pr.scores.values()) - 1.0) < 0.02


if __name__ == "__main__":
    tests = [
        test_pagerank_uniform_with_no_edges,
        test_pagerank_converges,
        test_pagerank_scores_sum_close_to_1,
        test_build_graph_reply_edge,
        test_build_graph_mention_edge,
        test_build_graph_no_self_edge,
        test_build_graph_reactions,
        test_degree_centrality_basic,
        test_higher_pagerank_for_more_replies,
        test_classify_role_core_influencer,
        test_classify_role_lurker,
        test_compute_member_stats_returns_sorted,
        test_compute_group_health_counts_lurkers,
        test_pagerank_deterministic,
        test_empty_graph,
        test_dangling_nodes_handled,
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
