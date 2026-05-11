"""phonefix edge tests — pure-function weighted edit distance correctness."""
from __future__ import annotations

from editdist import (
    substitution_cost, tokenize_syllable, tokenize_phrase,
    weighted_edit_distance, analyze_pronunciation,
    detect_systematic_pattern, PHONEME_CLASSES, PHONEME_TO_CLASS,
    COMMON_SUBSTITUTION_PAIRS,
)


def test_same_phoneme_zero_cost():
    cost, _ = substitution_cost("ㄓ", "ㄓ")
    assert cost == 0.0


def test_common_pair_low_cost():
    """翹舌→平舌 is common, should be low cost."""
    cost, reason = substitution_cost("ㄓ", "ㄗ")
    assert cost == 0.3
    assert "翹舌" in reason or "平舌" in reason


def test_same_class_medium_cost():
    """Same class but different phoneme = 0.5 (if not in COMMON_SUBSTITUTION_PAIRS)."""
    # ㄇ is 唇音 same class as ㄅ, but not in common pairs
    cost, _ = substitution_cost("ㄇ", "ㄅ")
    # Either commonpair or sameclass
    assert cost <= 0.5


def test_unrelated_high_cost():
    """Vowel vs consonant should be 1.0."""
    cost, _ = substitution_cost("ㄚ", "ㄓ")
    assert cost == 1.0


def test_tokenize_syllable_with_tone():
    """Tone marker becomes a token."""
    toks = tokenize_syllable("ㄓㄤˊ")
    assert "ㄓ" in toks
    assert "ㄤ" in toks
    assert "_tone2" in toks


def test_tokenize_syllable_default_tone():
    """No tone mark → tone 1."""
    toks = tokenize_syllable("ㄓㄤ")
    assert "_tone1" in toks


def test_tokenize_phrase_splits_syllables():
    """Spaces split syllables."""
    result = tokenize_phrase("ㄓㄤ ㄕㄥ ㄈㄢˋ")
    assert len(result) == 3


def test_edit_distance_identical():
    """Same sequence → cost 0."""
    a = ["ㄓ", "ㄤ", "_tone1"]
    align = weighted_edit_distance(a, a)
    assert align.total_cost == 0.0
    assert align.n_substitutions == 0
    assert align.n_deletions == 0
    assert align.n_insertions == 0


def test_edit_distance_one_sub():
    """One ㄓ→ㄗ substitution → 0.3 cost."""
    target = ["ㄓ", "ㄤ", "_tone1"]
    actual = ["ㄗ", "ㄤ", "_tone1"]
    align = weighted_edit_distance(target, actual)
    assert align.n_substitutions == 1
    assert align.total_cost == 0.3


def test_edit_distance_deletion():
    """Missing phoneme in actual = deletion."""
    target = ["ㄓ", "ㄤ", "_tone1"]
    actual = ["ㄓ", "ㄤ"]
    align = weighted_edit_distance(target, actual)
    assert align.n_deletions == 1


def test_edit_distance_insertion():
    """Extra phoneme in actual = insertion."""
    target = ["ㄓ", "ㄤ"]
    actual = ["ㄓ", "ㄤ", "ㄚ"]
    align = weighted_edit_distance(target, actual)
    assert align.n_insertions == 1


def test_analyze_perfect():
    """Identical phrase → 100% accuracy."""
    target = "ㄓㄤ ㄕㄥ"
    actual = "ㄓㄤ ㄕㄥ"
    report = analyze_pronunciation(target, actual)
    assert report.total_edit_cost == 0
    assert report.accuracy_pct == 100.0
    assert report.error_patterns == {}


def test_analyze_systematic_qiao_to_ping():
    """3 翹舌→平舌 errors → systematic pattern detected."""
    target = "ㄓㄤ ㄕㄥ ㄔˇ"
    actual = "ㄗㄤ ㄙㄥ ㄘˇ"
    report = analyze_pronunciation(target, actual)
    # Should have 3 substitutions, all 翹舌→平舌
    pattern = detect_systematic_pattern(report)
    assert pattern is not None
    assert "系統性" in pattern
    assert "翹舌" in pattern or "平舌" in pattern


def test_analyze_error_pattern_count():
    """Error pattern counter is correct."""
    target = "ㄓㄤ ㄕㄥ"
    actual = "ㄗㄤ ㄙㄥ"
    report = analyze_pronunciation(target, actual)
    # ㄓ→ㄗ + ㄕ→ㄙ both '翹舌→平舌 (最常見構音錯誤)' (low-cost pair)
    pattern_total = sum(report.error_patterns.values())
    assert pattern_total >= 2


def test_analyze_accuracy_inverse_to_errors():
    """More errors → lower accuracy."""
    target = "ㄓㄤ ㄕㄥ"
    less_err = analyze_pronunciation(target, "ㄓㄤ ㄙㄥ")    # 1 sub
    more_err = analyze_pronunciation(target, "ㄗㄤ ㄙㄥ")    # 2 sub
    assert less_err.accuracy_pct > more_err.accuracy_pct


def test_detect_systematic_pattern_none_for_perfect():
    """No errors → no systematic pattern."""
    report = analyze_pronunciation("ㄓㄤ", "ㄓㄤ")
    assert detect_systematic_pattern(report) is None


def test_phoneme_classes_complete():
    """All consonants assigned to a class."""
    consonants = "ㄅㄆㄇㄈㄉㄊㄋㄌㄓㄔㄕㄖㄗㄘㄙㄐㄑㄒㄍㄎㄏ"
    for c in consonants:
        assert c in PHONEME_TO_CLASS


def test_deterministic():
    """Same input → same output."""
    target = "ㄓㄤ ㄕㄥ"
    actual = "ㄗㄤ ㄙㄥ"
    r1 = analyze_pronunciation(target, actual)
    r2 = analyze_pronunciation(target, actual)
    assert r1.total_edit_cost == r2.total_edit_cost
    assert r1.accuracy_pct == r2.accuracy_pct
    assert r1.error_patterns == r2.error_patterns


if __name__ == "__main__":
    tests = [
        test_same_phoneme_zero_cost,
        test_common_pair_low_cost,
        test_same_class_medium_cost,
        test_unrelated_high_cost,
        test_tokenize_syllable_with_tone,
        test_tokenize_syllable_default_tone,
        test_tokenize_phrase_splits_syllables,
        test_edit_distance_identical,
        test_edit_distance_one_sub,
        test_edit_distance_deletion,
        test_edit_distance_insertion,
        test_analyze_perfect,
        test_analyze_systematic_qiao_to_ping,
        test_analyze_error_pattern_count,
        test_analyze_accuracy_inverse_to_errors,
        test_detect_systematic_pattern_none_for_perfect,
        test_phoneme_classes_complete,
        test_deterministic,
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
