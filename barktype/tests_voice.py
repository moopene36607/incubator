"""Edge-case tests for voice.py -- FFT + autocorrelation + features + kNN.

Validates the real-audio pipeline against synthetic ground-truth signals.

Run: python3 tests_voice.py
"""
from __future__ import annotations

import cmath
import math
import sys

from voice import (
    fft, magnitude_spectrum, autocorrelation, estimate_pitch_hz,
    rms_energy, zero_crossing_rate, spectral_centroid, spectral_rolloff,
    extract_features_from_signal, synthesise_bark,
    BarkFeatures, knn_predict, fit_feature_scales,
    _is_power_of_two, _next_power_of_two,
)


def assert_close(a, b, tol=1e-6, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol {tol})")


# ============================ FFT correctness ====================== #


def test_is_power_of_two():
    assert _is_power_of_two(1)
    assert _is_power_of_two(2)
    assert _is_power_of_two(1024)
    assert not _is_power_of_two(0)
    assert not _is_power_of_two(3)
    assert not _is_power_of_two(1023)


def test_next_power_of_two():
    assert _next_power_of_two(1) == 1
    assert _next_power_of_two(2) == 2
    assert _next_power_of_two(3) == 4
    assert _next_power_of_two(100) == 128


def test_fft_singleton():
    assert fft([complex(5.0)]) == [complex(5.0)]


def test_fft_constant_signal():
    # DC signal -> all energy at bin 0
    x = [complex(1.0)] * 8
    X = fft(x)
    assert_close(abs(X[0]), 8.0, msg="DC bin energy")
    for k in range(1, 8):
        assert abs(X[k]) < 1e-9, f"non-DC bin should be ~0 for constant: {abs(X[k])}"


def test_fft_non_power_of_two_raises():
    try:
        fft([complex(0)] * 3)
    except ValueError:
        return
    raise AssertionError("expected ValueError on length 3")


def test_fft_pure_sine_locates_peak():
    """A 220 Hz sine at 4096 Hz sample rate should peak at bin 220 * N / fs."""
    sample_rate = 4096
    freq = 220.0
    n = 1024
    samples = [math.sin(2 * math.pi * freq * i / sample_rate) for i in range(n)]
    mags = magnitude_spectrum(samples, n_fft=n)
    expected_bin = int(round(freq * n / sample_rate))
    # Find argmax in spectrum (ignoring DC)
    best_bin = 1
    best_mag = mags[1]
    for k in range(2, len(mags) - 1):
        if mags[k] > best_mag:
            best_mag = mags[k]
            best_bin = k
    assert abs(best_bin - expected_bin) <= 1, \
        f"peak at bin {best_bin} not within ±1 of expected {expected_bin}"


def test_magnitude_spectrum_returns_one_sided():
    samples = [1.0, 0.0, -1.0, 0.0] * 16  # length 64
    mags = magnitude_spectrum(samples, n_fft=64)
    assert len(mags) == 64 // 2 + 1


# ============================ pitch detection ====================== #


def test_autocorrelation_at_zero_equals_energy():
    x = [1.0, 2.0, 3.0, 4.0]
    r = autocorrelation(x, max_lag=0)
    expected = 1 + 4 + 9 + 16
    assert_close(r[0], expected)


def test_autocorrelation_zero_for_orthogonal_lag():
    # Sine wave: autocorrelation at lag = period should equal energy
    n = 100
    period = 10
    x = [math.sin(2 * math.pi * i / period) for i in range(n)]
    r = autocorrelation(x, max_lag=period * 2)
    # r[period] should be high relative to r[period//2]
    assert r[period] > r[period // 2], "autocorrelation peaks at period"


def test_pitch_detection_known_sine():
    """Synthesised 440 Hz tone at 8 kHz should be detected as ~440 Hz."""
    sr = 8000
    freq = 440.0
    n = 4000  # 0.5 s
    samples = [math.sin(2 * math.pi * freq * i / sr) for i in range(n)]
    detected = estimate_pitch_hz(samples, sr, f_min=200.0, f_max=1000.0)
    assert abs(detected - freq) < 5.0, \
        f"pitch detected as {detected:.1f} Hz, expected ~{freq} Hz"


def test_pitch_detection_known_low_pitch():
    """Synthesised 220 Hz tone at 8 kHz."""
    sr = 8000
    freq = 220.0
    n = 4000
    samples = [math.sin(2 * math.pi * freq * i / sr) for i in range(n)]
    detected = estimate_pitch_hz(samples, sr, f_min=80.0, f_max=600.0)
    assert abs(detected - freq) < 5.0


def test_pitch_detection_empty_signal():
    assert estimate_pitch_hz([], 8000) == 0.0


def test_pitch_detection_too_short_signal():
    short = [0.1] * 10
    assert estimate_pitch_hz(short, 8000) == 0.0


# ============================ feature extractors =================== #


def test_rms_energy_zero_signal():
    assert rms_energy([0.0, 0.0, 0.0]) == 0.0


def test_rms_energy_unit_sine():
    n = 1000
    samples = [math.sin(2 * math.pi * i / 100) for i in range(n)]
    e = rms_energy(samples)
    # RMS of a unit-amplitude sine = 1/sqrt(2)
    assert abs(e - 1.0 / math.sqrt(2)) < 0.05


def test_zero_crossing_rate_alternating():
    # Each pair of adjacent samples crosses zero
    x = [1.0, -1.0, 1.0, -1.0, 1.0]
    zcr = zero_crossing_rate(x)
    assert_close(zcr, 1.0)


def test_zero_crossing_rate_constant():
    x = [0.5, 0.5, 0.5, 0.5]
    assert zero_crossing_rate(x) == 0.0


def test_spectral_centroid_zero_for_silence():
    mags = [0.0] * 16
    assert spectral_centroid(mags, 8000, 32) == 0.0


def test_spectral_centroid_pure_freq():
    """Spectrum with energy only at bin k should give centroid = k * sr / N."""
    mags = [0.0] * 16
    mags[5] = 1.0
    centroid = spectral_centroid(mags, sample_rate=8000, n_fft=32)
    assert_close(centroid, 5.0 * 8000 / 32, msg="single-bin centroid")


# ============================ end-to-end feature extraction ========= #


def test_extract_features_synthetic_bark():
    """Run the full feature pipeline on a synthetic 500 Hz bark."""
    samples = synthesise_bark(pitch_hz=500.0, duration_ms=300, sample_rate=8000, noise=0.02)
    feats = extract_features_from_signal(samples, 8000, frame_size=512, hop_size=256)
    assert 400 < feats.pitch_mean_hz < 600, \
        f"pitch mean {feats.pitch_mean_hz} not near 500 Hz"
    assert abs(feats.duration_ms - 300) < 30
    assert feats.energy_mean > 0


def test_extract_features_returns_all_fields():
    samples = synthesise_bark(pitch_hz=400.0, duration_ms=500, sample_rate=8000)
    feats = extract_features_from_signal(samples, 8000)
    v = feats.as_vector()
    assert len(v) == 8
    names = BarkFeatures.feature_names()
    assert len(names) == 8


# ============================ kNN classifier ====================== #


def test_knn_predict_separable_classes():
    # 2 classes with clearly separated features
    training_X = [[1.0, 1.0], [1.1, 0.9], [0.9, 1.1],
                  [5.0, 5.0], [5.1, 4.9], [4.9, 5.1]]
    training_y = ["A", "A", "A", "B", "B", "B"]
    scales = fit_feature_scales(training_X)
    pred = knn_predict(training_X, training_y, [1.0, 1.0], scales, k=3)
    assert pred.predicted_class == "A"
    pred = knn_predict(training_X, training_y, [5.0, 5.0], scales, k=3)
    assert pred.predicted_class == "B"


def test_knn_predict_empty_training():
    pred = knn_predict([], [], [1.0, 2.0], [], k=3)
    assert pred.predicted_class == "unknown"


def test_knn_predict_returns_confidence():
    training_X = [[1.0], [1.1], [1.2], [10.0]]
    training_y = ["A", "A", "A", "B"]
    scales = fit_feature_scales(training_X)
    pred = knn_predict(training_X, training_y, [1.05], scales, k=3)
    assert 0.0 <= pred.confidence <= 1.0


def test_knn_predict_distances_sorted():
    training_X = [[1.0], [3.0], [5.0]]
    training_y = ["A", "B", "C"]
    scales = fit_feature_scales(training_X)
    pred = knn_predict(training_X, training_y, [1.5], scales, k=3)
    for i in range(len(pred.distances) - 1):
        assert pred.distances[i][1] <= pred.distances[i + 1][1]


def test_fit_feature_scales_constant_feature():
    X = [[1.0, 5.0], [1.0, 6.0], [1.0, 7.0]]
    scales = fit_feature_scales(X)
    assert scales[0] >= 1e-6   # constant feature gets safeguarded scale
    assert scales[1] > 0


# ============================ synthesise =========================== #


def test_synthesise_bark_length():
    samples = synthesise_bark(pitch_hz=300.0, duration_ms=500, sample_rate=8000)
    assert len(samples) == 4000  # 0.5 s * 8000 Hz


def test_synthesise_bark_deterministic():
    s1 = synthesise_bark(pitch_hz=300.0, duration_ms=100, sample_rate=8000)
    s2 = synthesise_bark(pitch_hz=300.0, duration_ms=100, sample_rate=8000)
    for a, b in zip(s1, s2):
        assert a == b


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
