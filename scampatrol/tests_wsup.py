"""Edge-case tests for wsup.py -- weak supervision with Dawid-Skene EM.

Run: python3 tests_wsup.py
"""
from __future__ import annotations

import math
import sys

from wsup import (
    ABSTAIN, CLASS_NAMES, N_CLASSES, DEFAULT_LFS,
    lf_invest_keywords, lf_impersonation_authority, lf_phishing_short_link,
    lf_phishing_prize, lf_borrow_urgency, lf_msg_length_link,
    lf_legitimate_long_no_link, lf_invest_percent_number,
    apply_lfs, apply_lfs_batch, majority_vote,
    fit_dawid_skene, predict_one, lf_coverage, lf_estimated_accuracy,
    _init_theta, _init_abstain,
)


def assert_close(a, b, tol=1e-6, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol {tol})")


def test_lf_invest_keywords_fires_on_invest_text():
    assert lf_invest_keywords("加入投資老師群保證獲利 5% 穩賺") == 1


def test_lf_invest_keywords_abstains_on_normal_text():
    assert lf_invest_keywords("明天會議改到下午 3 點") == ABSTAIN


def test_lf_impersonation_authority_fires_on_authority_pattern():
    assert lf_impersonation_authority("警察局通知您配合提供驗證碼凍結帳戶") == 2


def test_lf_impersonation_authority_abstains_on_safe_text():
    assert lf_impersonation_authority("今天小孩在學校吐了") == ABSTAIN


def test_lf_phishing_short_link_fires():
    assert lf_phishing_short_link("點此 https://bit.ly/abc123 立即領取") == 3


def test_lf_phishing_prize_fires():
    assert lf_phishing_prize("恭喜中獎 領取 iPhone") == 3


def test_lf_borrow_urgency_fires():
    assert lf_borrow_urgency("媽我手機壞了急用 30000") == 4


def test_lf_msg_length_link_fires_on_short_link():
    assert lf_msg_length_link("點 https://bit.ly/x") == 3


def test_lf_msg_length_link_abstains_on_long_text():
    long_text = "今天" + "X" * 60 + " 很開心"
    assert lf_msg_length_link(long_text) == ABSTAIN


def test_lf_legitimate_fires_on_long_clean_text():
    text = "明天會議改到下午 3 點, 會議室在 12F 請準時, 議程包含預算討論。"
    assert lf_legitimate_long_no_link(text) == 0


def test_apply_lfs_returns_list_of_lf_count():
    result = apply_lfs("測試訊息")
    assert len(result) == len(DEFAULT_LFS)


def test_majority_vote_picks_dominant_class():
    # Two LFs vote for class 1, one for class 3, rest abstain
    outputs = [1, 1, 3, ABSTAIN, ABSTAIN, ABSTAIN, ABSTAIN, ABSTAIN, ABSTAIN, ABSTAIN]
    cls, votes = majority_vote(outputs)
    assert cls == 1


def test_majority_vote_all_abstain_returns_default():
    outputs = [ABSTAIN] * 10
    cls, votes = majority_vote(outputs)
    assert cls == 0  # default = legitimate


def test_majority_vote_tie_breaks_smaller_index():
    # 1 vote for class 1, 1 vote for class 2 -> tie -> pick smaller (1)
    outputs = [1, 2] + [ABSTAIN] * 8
    cls, _ = majority_vote(outputs)
    assert cls == 1


def test_init_theta_diagonal_dominant():
    theta = _init_theta(n_lfs=2, n_classes=5, diagonal=0.8)
    for j in range(2):
        for c in range(5):
            assert theta[j][c][c] == 0.8
            row_sum = sum(theta[j][c])
            assert_close(row_sum, 1.0, msg=f"row sum LF={j} class={c}")


def test_fit_dawid_skene_empty_raises():
    try:
        fit_dawid_skene([], n_classes=5)
    except ValueError:
        return
    raise AssertionError("expected ValueError on empty input")


def test_fit_dawid_skene_runs_and_returns_model():
    # 6 messages, 3 LFs, 3 classes
    L = [
        [0, 0, ABSTAIN],
        [0, ABSTAIN, 0],
        [1, 1, ABSTAIN],
        [1, 1, 1],
        [2, ABSTAIN, 2],
        [2, 2, 2],
    ]
    model = fit_dawid_skene(L, n_classes=3, n_iter=20)
    assert model.n_classes == 3
    assert model.n_lfs == 3
    assert len(model.pi) == 3
    assert abs(sum(model.pi) - 1.0) < 1e-6


def test_fit_dawid_skene_pi_sums_to_one():
    L = [[1, 1, ABSTAIN], [0, 0, 0], [1, ABSTAIN, 1]]
    model = fit_dawid_skene(L, n_classes=3, n_iter=20)
    assert_close(sum(model.pi), 1.0, tol=1e-6, msg="pi sums to 1")


def test_predict_one_returns_probs_sum_to_one():
    L_train = [
        [0, 0, ABSTAIN],
        [1, 1, 1],
        [2, ABSTAIN, 2],
        [0, 0, 0],
        [1, ABSTAIN, 1],
    ]
    model = fit_dawid_skene(L_train, n_classes=3, n_iter=30)
    pred = predict_one(model, [1, 1, ABSTAIN])
    assert_close(sum(pred["probs"]), 1.0, msg="posterior sums to 1")
    assert pred["predicted_class"] in {0, 1, 2}


def test_predict_one_concentrates_on_consistent_signal():
    # All LFs consistently say class 1 -> posterior should heavily favor class 1.
    L_train = [
        [1, 1, 1], [1, 1, 1], [1, 1, 1],
        [0, 0, 0], [0, 0, 0],
        [2, 2, 2], [2, 2, 2],
    ]
    model = fit_dawid_skene(L_train, n_classes=3, n_iter=50)
    pred = predict_one(model, [1, 1, 1])
    assert pred["predicted_class"] == 1
    assert pred["probs"][1] > 0.7


def test_dawid_skene_with_two_agreeing_lfs_recovers_classes():
    """With two LFs that mostly agree on three distinct classes, EM should recover them."""
    # 3 classes, 2 LFs, 15 examples per class. Both LFs roughly agree.
    L_train = []
    for _ in range(13):
        L_train.append([0, 0, ABSTAIN])
    L_train += [[0, 1, ABSTAIN], [1, 0, ABSTAIN]]  # 2 disagreements
    for _ in range(13):
        L_train.append([1, 1, ABSTAIN])
    L_train += [[1, 2, ABSTAIN], [2, 1, ABSTAIN]]
    for _ in range(13):
        L_train.append([2, 2, ABSTAIN])
    L_train += [[2, 0, ABSTAIN], [0, 2, ABSTAIN]]

    model = fit_dawid_skene(L_train, n_classes=3, n_iter=100)
    # Each class should have nontrivial prior (no collapse).
    assert max(model.pi) < 0.85, f"pi collapsed to single class: {model.pi}"
    assert min(model.pi) > 0.05, f"pi underflowed for some class: {model.pi}"
    # When both LFs say class 1, prediction should be class 1.
    pred = predict_one(model, [1, 1, ABSTAIN])
    assert pred["predicted_class"] == 1, f"expected 1; got {pred['predicted_class']} probs={pred['probs']}"


def test_lf_coverage_zero_if_all_abstain():
    L = [[ABSTAIN, ABSTAIN], [ABSTAIN, ABSTAIN]]
    cov = lf_coverage(L)
    assert cov == [0.0, 0.0]


def test_lf_coverage_one_if_always_active():
    L = [[0, 1], [1, 2], [2, 0]]
    cov = lf_coverage(L)
    assert cov == [1.0, 1.0]


def test_lf_estimated_accuracy_in_unit_interval():
    L_train = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [1, 0, ABSTAIN]]
    model = fit_dawid_skene(L_train, n_classes=3, n_iter=20)
    accs = lf_estimated_accuracy(model)
    for a in accs:
        assert 0.0 <= a <= 1.0


def test_dawid_skene_handles_constant_lf_output():
    """LF always emits class 0 -- model should still run and produce valid output."""
    L = [[0, ABSTAIN, ABSTAIN], [0, 1, ABSTAIN], [0, ABSTAIN, 1], [0, 1, 1]]
    model = fit_dawid_skene(L, n_classes=3, n_iter=20)
    pred = predict_one(model, [0, 1, 1])
    assert sum(pred["probs"]) > 0.99


def test_predict_one_handles_all_abstain():
    L_train = [[1, 1], [0, 0], [2, 2], [1, ABSTAIN]]
    model = fit_dawid_skene(L_train, n_classes=3, n_iter=20)
    pred = predict_one(model, [ABSTAIN, ABSTAIN])
    # Should fall back to prior (pi).
    assert_close(sum(pred["probs"]), 1.0)


def test_dawid_skene_deterministic():
    L = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [1, 0, ABSTAIN]]
    m1 = fit_dawid_skene(L, n_classes=3, n_iter=20)
    m2 = fit_dawid_skene(L, n_classes=3, n_iter=20)
    for c in range(3):
        assert_close(m1.pi[c], m2.pi[c], tol=1e-9)


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
