"""TDD tests for app.ingest.embedder — cosine + pre-filter threshold.

Pure math, no network calls. embed() (which talks to OpenAI) is exercised by
integration tests that mock the OpenAI client.
"""

import pytest

from app.ingest.embedder import cosine, should_send_to_llm


def test_cosine_identical_vectors_is_one():
    v = [1.0, 0.0, 0.5]
    assert cosine(v, v) == pytest.approx(1.0)


def test_cosine_orthogonal_vectors_is_zero():
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_opposite_vectors_is_minus_one():
    assert cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_zero_vector_returns_zero():
    # avoid division-by-zero blow-up; semantic prefilter should treat empty
    # capability descriptions as "no signal" rather than crashing the worker.
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_cosine_dimension_mismatch_raises():
    with pytest.raises(ValueError):
        cosine([1.0, 0.0], [1.0, 0.0, 0.0])


def test_should_send_below_threshold_returns_false():
    # cosine of orthogonal vectors = 0 < 0.3 threshold
    assert should_send_to_llm([1.0, 0.0], [0.0, 1.0], threshold=0.3) is False


def test_should_send_above_threshold_returns_true():
    # cosine of near-parallel vectors ≈ 0.998 > 0.3 threshold
    assert should_send_to_llm([1.0, 0.0], [0.95, 0.05], threshold=0.3) is True


def test_should_send_at_threshold_boundary_returns_true():
    # exact threshold counts as "send" (>=), so worker never drops a borderline
    # case silently. unit vectors along same axis cosine = 1.
    assert should_send_to_llm([1.0], [1.0], threshold=1.0) is True
