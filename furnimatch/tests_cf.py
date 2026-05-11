"""furnimatch edge tests — pure-function Item-Item CF correctness."""
from __future__ import annotations

from cf import (
    Item, User, Marketplace, QueryProfile, Recommendation,
    cosine_similarity_binary, jaccard_similarity,
    build_item_user_index, build_user_item_index,
    compute_item_similarities, get_similarity,
    recommend_for_profile, style_based_fallback,
    item_popularity, coverage_stats,
)


def _mk_item(item_id, name="X", price=1000, location="台北",
              category="沙發", style="A", condition="GOOD"):
    return Item(item_id=item_id, name=name, price_ntd=price, location=location,
                 category=category, style_tag=style, condition=condition)


def test_cosine_identical_sets():
    """Identical sets → similarity 1.0."""
    assert cosine_similarity_binary({"u1", "u2"}, {"u1", "u2"}) == 1.0


def test_cosine_disjoint_sets():
    """No overlap → 0."""
    assert cosine_similarity_binary({"u1"}, {"u2"}) == 0.0


def test_cosine_empty():
    """Empty sets → 0."""
    assert cosine_similarity_binary(set(), {"u1"}) == 0.0
    assert cosine_similarity_binary(set(), set()) == 0.0


def test_cosine_partial_overlap():
    """3 overlap of |A|=4, |B|=4 → 3 / sqrt(16) = 0.75."""
    a = {"u1", "u2", "u3", "u4"}
    b = {"u1", "u2", "u3", "u5"}
    sim = cosine_similarity_binary(a, b)
    assert abs(sim - 0.75) < 1e-9


def test_jaccard_basic():
    """Jaccard |A ∩ B| / |A ∪ B|."""
    a = {"u1", "u2", "u3"}
    b = {"u2", "u3", "u4"}
    # 2 / 4 = 0.5
    assert abs(jaccard_similarity(a, b) - 0.5) < 1e-9


def test_jaccard_identical():
    """Same set → 1.0."""
    a = {"u1", "u2"}
    assert jaccard_similarity(a, a) == 1.0


def test_build_item_user_index():
    """For each item, set of users who fav'd it."""
    items = [_mk_item("I1"), _mk_item("I2"), _mk_item("I3")]
    users = [
        User("U1", "Alice", ["I1", "I2"]),
        User("U2", "Bob", ["I2", "I3"]),
    ]
    mp = Marketplace(items=items, users=users)
    idx = build_item_user_index(mp)
    assert idx["I1"] == {"U1"}
    assert idx["I2"] == {"U1", "U2"}
    assert idx["I3"] == {"U2"}


def test_build_user_item_index():
    items = [_mk_item("I1")]
    users = [User("U1", "X", ["I1"]), User("U2", "Y", [])]
    mp = Marketplace(items=items, users=users)
    idx = build_user_item_index(mp)
    assert idx["U1"] == {"I1"}
    assert idx["U2"] == set()


def test_compute_similarities_returns_pairs():
    """For 3 items with overlap, returns pairs i < j."""
    items = [_mk_item("I1"), _mk_item("I2"), _mk_item("I3")]
    users = [
        User("U1", "A", ["I1", "I2"]),
        User("U2", "B", ["I2", "I3"]),
        User("U3", "C", ["I1", "I3"]),
    ]
    mp = Marketplace(items=items, users=users)
    sims = compute_item_similarities(mp)
    # All 3 pairs should have nonzero sim
    assert ("I1", "I2") in sims
    assert ("I2", "I3") in sims
    assert ("I1", "I3") in sims


def test_get_similarity_self():
    """sim(x, x) = 1.0."""
    sims = {}
    assert get_similarity(sims, "I1", "I1") == 1.0


def test_get_similarity_symmetric():
    """sim(a, b) == sim(b, a)."""
    sims = {("I1", "I2"): 0.5}
    assert get_similarity(sims, "I1", "I2") == 0.5
    assert get_similarity(sims, "I2", "I1") == 0.5


def test_recommend_excludes_seed_favorites():
    """Recommendation shouldn't include user's own seed favorites."""
    items = [_mk_item(f"I{i}", price=1000, style="A") for i in range(1, 6)]
    users = [User(f"U{i}", "X", ["I1", "I2"]) for i in range(1, 11)]
    mp = Marketplace(items=items, users=users)
    sims = compute_item_similarities(mp)
    profile = QueryProfile(user_name="new", seed_favorites=["I1", "I2"])
    recs = recommend_for_profile(mp, profile, sims, top_n=5)
    for r in recs:
        assert r.item.item_id not in {"I1", "I2"}


def test_recommend_respects_budget_filter():
    """Items above budget excluded."""
    items = [
        _mk_item("I1", price=500), _mk_item("I2", price=1000),
        _mk_item("I3", price=5000), _mk_item("I4", price=10000),
    ]
    users = [User("U1", "A", ["I1", "I3"]), User("U2", "B", ["I1", "I4"])]
    mp = Marketplace(items=items, users=users)
    sims = compute_item_similarities(mp)
    profile = QueryProfile(user_name="new", seed_favorites=["I2"], budget_max_ntd=3000)
    recs = recommend_for_profile(mp, profile, sims, top_n=5)
    for r in recs:
        assert r.item.price_ntd <= 3000


def test_recommend_respects_location_filter():
    items = [
        _mk_item("I1", location="台北"), _mk_item("I2", location="高雄"),
        _mk_item("I3", location="台北"),
    ]
    users = [User("U1", "X", ["I1", "I2"]), User("U2", "Y", ["I1", "I3"])]
    mp = Marketplace(items=items, users=users)
    sims = compute_item_similarities(mp)
    profile = QueryProfile(user_name="new", seed_favorites=["I1"],
                            location_filter=["台北"])
    recs = recommend_for_profile(mp, profile, sims, top_n=5)
    for r in recs:
        assert r.item.location == "台北"


def test_recommend_sorted_by_score_desc():
    """Recommendations sorted descending by score."""
    items = [_mk_item(f"I{i}", style="A") for i in range(1, 11)]
    users = [User(f"U{i}", "X", [f"I{j}" for j in range(1, 11) if (i + j) % 2 == 0])
             for i in range(1, 21)]
    mp = Marketplace(items=items, users=users)
    sims = compute_item_similarities(mp)
    profile = QueryProfile(user_name="new", seed_favorites=["I1", "I2"])
    recs = recommend_for_profile(mp, profile, sims, top_n=5)
    for i in range(1, len(recs)):
        assert recs[i - 1].score >= recs[i].score


def test_item_popularity():
    """Count of users per item."""
    items = [_mk_item("I1"), _mk_item("I2"), _mk_item("I3")]
    users = [
        User("U1", "A", ["I1", "I2"]),
        User("U2", "B", ["I1"]),
        User("U3", "C", ["I2", "I3"]),
    ]
    mp = Marketplace(items=items, users=users)
    pop = item_popularity(mp)
    assert pop["I1"] == 2
    assert pop["I2"] == 2
    assert pop["I3"] == 1


def test_coverage_stats():
    """Stats include n_items, n_users, density."""
    items = [_mk_item("I1"), _mk_item("I2")]
    users = [User("U1", "X", ["I1", "I2"])]
    mp = Marketplace(items=items, users=users)
    sims = compute_item_similarities(mp)
    stats = coverage_stats(mp, sims)
    assert stats["n_items"] == 2
    assert stats["n_users"] == 1
    assert stats["total_favorites"] == 2


def test_recommend_includes_contributors():
    """Recommendation includes contributing favorites."""
    items = [_mk_item("I1"), _mk_item("I2"), _mk_item("I3")]
    users = [User("U1", "X", ["I1", "I2"]), User("U2", "Y", ["I2", "I3"])]
    mp = Marketplace(items=items, users=users)
    sims = compute_item_similarities(mp)
    profile = QueryProfile(user_name="new", seed_favorites=["I1"])
    recs = recommend_for_profile(mp, profile, sims, top_n=3)
    if recs:
        assert len(recs[0].contributing_favorites) > 0
        # Each contributor is (name, similarity_score)
        for name, score in recs[0].contributing_favorites:
            assert isinstance(name, str)
            assert 0 < score <= 1.0


if __name__ == "__main__":
    tests = [
        test_cosine_identical_sets,
        test_cosine_disjoint_sets,
        test_cosine_empty,
        test_cosine_partial_overlap,
        test_jaccard_basic,
        test_jaccard_identical,
        test_build_item_user_index,
        test_build_user_item_index,
        test_compute_similarities_returns_pairs,
        test_get_similarity_self,
        test_get_similarity_symmetric,
        test_recommend_excludes_seed_favorites,
        test_recommend_respects_budget_filter,
        test_recommend_respects_location_filter,
        test_recommend_sorted_by_score_desc,
        test_item_popularity,
        test_coverage_stats,
        test_recommend_includes_contributors,
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
