"""Edge-case tests for som.py -- Self-Organizing Map pure stdlib.

Run: python3 tests_som.py
"""
from __future__ import annotations

import math
import sys

from som import (
    init_som, fit_som, assign_labels, find_bmu, predict,
    quantisation_error, topographic_error,
    fit_minmax_scaler, apply_minmax,
    _vec_dist, _vec_dist_sq, _neighbourhood,
    SOM,
)


def assert_close(a, b, tol=1e-6, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol {tol})")


# ============================ helpers =============================== #


def test_vec_dist_zero_for_same_point():
    assert _vec_dist([1, 2, 3], [1, 2, 3]) == 0.0


def test_vec_dist_pythagorean():
    assert_close(_vec_dist([0, 0], [3, 4]), 5.0)


def test_neighbourhood_self_is_one():
    h = _neighbourhood(2, 3, 2, 3, sigma=1.0)
    assert_close(h, 1.0)


def test_neighbourhood_far_is_near_zero():
    h = _neighbourhood(0, 0, 10, 10, sigma=1.0)
    assert h < 0.01


def test_neighbourhood_sigma_zero_one_hot():
    h_self = _neighbourhood(1, 1, 1, 1, sigma=0.0)
    h_other = _neighbourhood(1, 1, 1, 2, sigma=0.0)
    assert h_self == 1.0
    assert h_other == 0.0


# ============================ init / find BMU ===================== #


def test_init_som_shape():
    som = init_som(4, 5, input_dim=3, seed=0)
    assert som.grid_h == 4
    assert som.grid_w == 5
    assert len(som.weights) == 4
    assert len(som.weights[0]) == 5
    assert len(som.weights[0][0]) == 3


def test_init_som_weights_in_range():
    som = init_som(3, 3, input_dim=4, init_low=0.0, init_high=1.0, seed=0)
    for r in range(3):
        for c in range(3):
            for v in som.weights[r][c]:
                assert 0.0 <= v <= 1.0


def test_find_bmu_returns_closest_cell():
    som = init_som(3, 3, input_dim=2, seed=0)
    # Manually set known weights
    for r in range(3):
        for c in range(3):
            som.weights[r][c] = [float(r), float(c)]
    # Input at (1.0, 2.0) should map to cell [1][2]
    r, c = find_bmu(som, [1.0, 2.0])
    assert (r, c) == (1, 2)


# ============================ fit_som =============================== #


def test_fit_som_empty_raises():
    som = init_som(3, 3, input_dim=2, seed=0)
    try:
        fit_som(som, [])
    except ValueError:
        return
    raise AssertionError("expected ValueError on empty input")


def test_fit_som_reduces_quantisation_error():
    som = init_som(5, 5, input_dim=3, seed=0)
    X = [[0.1, 0.1, 0.1], [0.2, 0.1, 0.1], [0.9, 0.9, 0.9],
         [0.8, 0.9, 0.9], [0.5, 0.5, 0.5]]
    qe_before = quantisation_error(som, X)
    som = fit_som(som, X, epochs=30, seed=0)
    qe_after = quantisation_error(som, X)
    assert qe_after < qe_before, f"QE should decrease: {qe_before} -> {qe_after}"


def test_fit_som_clusters_separable_inputs():
    """Two clusters of inputs should map to different SOM regions."""
    som = init_som(6, 6, input_dim=2, seed=42)
    X_low = [[0.1, 0.1], [0.15, 0.12], [0.1, 0.15]]
    X_high = [[0.9, 0.9], [0.85, 0.88], [0.9, 0.85]]
    X = X_low + X_high
    som = fit_som(som, X, epochs=40, seed=42)
    bmu_low = [find_bmu(som, x) for x in X_low]
    bmu_high = [find_bmu(som, x) for x in X_high]
    # All low inputs should land near each other; same for high.
    avg_low_r = sum(b[0] for b in bmu_low) / 3.0
    avg_low_c = sum(b[1] for b in bmu_low) / 3.0
    avg_high_r = sum(b[0] for b in bmu_high) / 3.0
    avg_high_c = sum(b[1] for b in bmu_high) / 3.0
    dist = math.sqrt((avg_low_r - avg_high_r) ** 2 + (avg_low_c - avg_high_c) ** 2)
    assert dist > 2.0, f"clusters should separate on 6x6 grid; dist={dist}"


def test_quantisation_error_zero_with_perfect_weights():
    som = init_som(2, 2, input_dim=2, seed=0)
    som.weights = [[[0.0, 0.0], [1.0, 0.0]], [[0.0, 1.0], [1.0, 1.0]]]
    X = [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    qe = quantisation_error(som, X)
    assert_close(qe, 0.0)


# ============================ assign_labels ========================= #


def test_assign_labels_majority_vote():
    som = init_som(2, 2, input_dim=2, seed=0)
    som.weights = [[[0.0, 0.0], [1.0, 0.0]], [[0.0, 1.0], [1.0, 1.0]]]
    X = [[0.0, 0.0], [0.05, 0.0], [0.0, 0.05]]   # all BMU = [0][0]
    y = ["A", "A", "B"]
    assign_labels(som, X, y)
    assert som.label_grid[0][0] == "A"
    assert som.label_grid[1][1] is None    # no training sample mapped here


def test_assign_labels_empty_cell_returns_none():
    som = init_som(3, 3, input_dim=2, seed=0)
    som.weights = [[[float(r), float(c)] for c in range(3)] for r in range(3)]
    X = [[0.0, 0.0]]
    y = ["X"]
    assign_labels(som, X, y)
    # Only [0][0] has training sample
    assert som.label_grid[0][0] == "X"
    assert som.label_grid[2][2] is None


# ============================ predict =============================== #


def test_predict_returns_bmu_and_label():
    som = init_som(2, 2, input_dim=2, seed=0)
    som.weights = [[[0.0, 0.0], [1.0, 0.0]], [[0.0, 1.0], [1.0, 1.0]]]
    X = [[0.0, 0.0]]
    y = ["test"]
    assign_labels(som, X, y)
    pred = predict(som, [0.05, 0.05])
    assert pred.bmu_row == 0 and pred.bmu_col == 0
    assert pred.bmu_label == "test"
    assert pred.bmu_distance < 0.2


def test_predict_neighbours_sorted_by_distance():
    som = init_som(3, 3, input_dim=2, seed=0)
    som.weights = [[[float(r), float(c)] for c in range(3)] for r in range(3)]
    pred = predict(som, [1.0, 1.0])
    # BMU = [1][1]; neighbours are 8 surrounding cells, sorted ascending distance.
    for i in range(len(pred.nearby_cells) - 1):
        assert pred.nearby_cells[i][3] <= pred.nearby_cells[i + 1][3]


# ============================ scalers =============================== #


def test_minmax_scaler_normal_range():
    X = [[10.0, 100.0], [20.0, 200.0], [30.0, 300.0]]
    mins, maxs = fit_minmax_scaler(X)
    assert mins == [10.0, 100.0]
    assert maxs == [30.0, 300.0]
    scaled = apply_minmax(X, mins, maxs)
    assert_close(scaled[0][0], 0.0)
    assert_close(scaled[1][0], 0.5)
    assert_close(scaled[2][0], 1.0)


def test_minmax_scaler_handles_constant_feature():
    X = [[5.0, 1.0], [5.0, 2.0], [5.0, 3.0]]
    mins, maxs = fit_minmax_scaler(X)
    scaled = apply_minmax(X, mins, maxs)
    # Constant feature should map to 0.5 (centre), not blow up.
    assert scaled[0][0] == 0.5
    assert scaled[1][0] == 0.5
    assert scaled[2][0] == 0.5


def test_minmax_scaler_empty():
    mins, maxs = fit_minmax_scaler([])
    assert mins == []
    assert maxs == []


# ============================ topology =============================== #


def test_topographic_error_zero_for_smooth_map():
    """When SOM perfectly orders inputs along grid, 2nd BMU should be neighbour."""
    som = init_som(1, 5, input_dim=1, seed=0)
    # Weights along a 1D ramp.
    for c in range(5):
        som.weights[0][c] = [float(c) / 4.0]
    X = [[0.0], [0.25], [0.5], [0.75], [1.0]]
    te = topographic_error(som, X)
    assert te == 0.0, f"smooth ramp should have zero topo error; got {te}"


def test_topographic_error_in_unit_interval():
    som = init_som(3, 3, input_dim=2, seed=0)
    X = [[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]]
    te = topographic_error(som, X)
    assert 0.0 <= te <= 1.0


# ============================ end-to-end =============================== #


def test_fit_som_deterministic_with_seed():
    X = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
    s1 = init_som(3, 3, input_dim=2, seed=42)
    s1 = fit_som(s1, X, epochs=20, seed=42)
    s2 = init_som(3, 3, input_dim=2, seed=42)
    s2 = fit_som(s2, X, epochs=20, seed=42)
    for r in range(3):
        for c in range(3):
            for d in range(2):
                assert_close(s1.weights[r][c][d], s2.weights[r][c][d], tol=1e-12)


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
