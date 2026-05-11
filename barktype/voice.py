"""Voice signal analysis -- pure stdlib (math + cmath + statistics).

Pipeline for short audio segments (e.g. a single bark):
  1. Cooley-Tukey radix-2 FFT     -> spectrum
  2. Autocorrelation pitch (lag-search) -> fundamental frequency
  3. Energy / RMS                  -> loudness proxy
  4. Spectral centroid             -> brightness
  5. Zero-crossing rate            -> noise-vs-tone proxy
  6. Spectral rolloff              -> high-frequency energy

These features feed a tiny kNN classifier to label barks among 4 categories.
The full pipeline runs over raw audio samples (real signal arrays); tests
validate FFT + autocorrelation against known synthetic signals.

Pure stdlib: math + cmath + statistics + dataclasses + collections.
"""
from __future__ import annotations

import cmath
import math
from collections import Counter
from dataclasses import dataclass, field
from statistics import fmean, pstdev


# ============================ FFT (Cooley-Tukey) ===================== #


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _next_power_of_two(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


def fft(x: list[complex]) -> list[complex]:
    """Cooley-Tukey radix-2 FFT. Input length must be a power of 2."""
    n = len(x)
    if n == 1:
        return [x[0]]
    if not _is_power_of_two(n):
        raise ValueError(f"FFT length must be power of 2; got {n}")
    even = fft(x[0::2])
    odd = fft(x[1::2])
    half = n // 2
    twiddles = [cmath.exp(-2j * cmath.pi * k / n) for k in range(half)]
    front = [even[k] + twiddles[k] * odd[k] for k in range(half)]
    back = [even[k] - twiddles[k] * odd[k] for k in range(half)]
    return front + back


def magnitude_spectrum(samples: list[float], n_fft: int | None = None) -> list[float]:
    """One-sided magnitude spectrum of real-valued samples.

    Zero-pads to next power of 2 if `n_fft` not given.
    Returns magnitudes for bins 0..N/2 (real-FFT convention).
    """
    n = len(samples)
    if n_fft is None:
        n_fft = _next_power_of_two(n) if n > 1 else 2
    padded = list(samples) + [0.0] * (n_fft - n)
    spec = fft([complex(s) for s in padded])
    return [abs(spec[k]) for k in range(n_fft // 2 + 1)]


# ========================== autocorrelation pitch =================== #


def autocorrelation(samples: list[float], max_lag: int | None = None) -> list[float]:
    """Linear autocorrelation r[k] = sum_i x[i] * x[i+k] for k = 0..max_lag."""
    n = len(samples)
    if max_lag is None:
        max_lag = n - 1
    max_lag = min(max_lag, n - 1)
    out = []
    for k in range(max_lag + 1):
        s = 0.0
        for i in range(n - k):
            s += samples[i] * samples[i + k]
        out.append(s)
    return out


def estimate_pitch_hz(
    samples: list[float], sample_rate: int,
    f_min: float = 80.0, f_max: float = 2000.0,
) -> float:
    """Fundamental frequency via autocorrelation.

    Searches for the peak of r[k] for k corresponding to f in [f_min, f_max].
    Returns 0.0 if signal is too short or no clear peak.
    """
    n = len(samples)
    if n < 32:
        return 0.0
    lag_min = max(1, int(sample_rate / f_max))
    lag_max = min(n - 1, int(sample_rate / f_min))
    if lag_max <= lag_min:
        return 0.0
    r = autocorrelation(samples, max_lag=lag_max)
    r0 = r[0]
    if r0 < 1e-12:
        return 0.0
    # Find best peak in [lag_min, lag_max].
    best_lag = lag_min
    best_val = -1.0
    for k in range(lag_min, lag_max + 1):
        if r[k] > best_val:
            best_val = r[k]
            best_lag = k
    # Pitch is sample_rate / lag. Sanity-check that the peak is "real" (not
    # spurious noise) by requiring r[best_lag] / r[0] > some floor.
    if best_val / r0 < 0.15:
        return 0.0
    return sample_rate / best_lag


# ========================== other features ========================== #


def rms_energy(samples: list[float]) -> float:
    if not samples:
        return 0.0
    s = sum(x * x for x in samples)
    return math.sqrt(s / len(samples))


def zero_crossing_rate(samples: list[float]) -> float:
    if len(samples) < 2:
        return 0.0
    n_zc = 0
    prev = samples[0]
    for cur in samples[1:]:
        if (prev >= 0.0 and cur < 0.0) or (prev < 0.0 and cur >= 0.0):
            n_zc += 1
        prev = cur
    return n_zc / (len(samples) - 1)


def spectral_centroid(magnitudes: list[float], sample_rate: int, n_fft: int) -> float:
    """Frequency-weighted average of magnitudes (brightness proxy)."""
    if not magnitudes:
        return 0.0
    total = sum(magnitudes)
    if total < 1e-12:
        return 0.0
    weighted = 0.0
    for k, m in enumerate(magnitudes):
        freq = k * sample_rate / n_fft
        weighted += freq * m
    return weighted / total


def spectral_rolloff(
    magnitudes: list[float], sample_rate: int, n_fft: int, ratio: float = 0.85,
) -> float:
    """Frequency below which `ratio` of the spectral energy lies."""
    total = sum(magnitudes)
    if total < 1e-12:
        return 0.0
    threshold = ratio * total
    acc = 0.0
    for k, m in enumerate(magnitudes):
        acc += m
        if acc >= threshold:
            return k * sample_rate / n_fft
    return (len(magnitudes) - 1) * sample_rate / n_fft


# ========================== feature extraction =================== #


@dataclass
class BarkFeatures:
    pitch_mean_hz: float
    pitch_std_hz: float
    duration_ms: float
    energy_mean: float
    spectral_centroid_hz: float
    zero_crossing_rate: float
    bark_rate_per_sec: float
    spectral_rolloff_hz: float

    def as_vector(self) -> list[float]:
        return [
            self.pitch_mean_hz, self.pitch_std_hz, self.duration_ms,
            self.energy_mean, self.spectral_centroid_hz,
            self.zero_crossing_rate, self.bark_rate_per_sec,
            self.spectral_rolloff_hz,
        ]

    @staticmethod
    def feature_names() -> list[str]:
        return [
            "pitch_mean_hz", "pitch_std_hz", "duration_ms",
            "energy_mean", "spectral_centroid_hz",
            "zero_crossing_rate", "bark_rate_per_sec",
            "spectral_rolloff_hz",
        ]


def extract_features_from_signal(
    samples: list[float], sample_rate: int,
    frame_size: int = 1024, hop_size: int = 512,
    bark_threshold: float = 0.05,
) -> BarkFeatures:
    """Process raw audio samples into a BarkFeatures vector.

    Frame-by-frame: compute per-frame pitch + energy, then aggregate.
    A "bark event" is a contiguous run of frames whose RMS energy exceeds
    bark_threshold (proxy for loudness).
    """
    n = len(samples)
    duration_s = n / sample_rate if sample_rate > 0 else 0.0
    duration_ms = duration_s * 1000.0

    pitches: list[float] = []
    energies: list[float] = []
    frame_above_threshold: list[bool] = []

    for start in range(0, n - frame_size + 1, hop_size):
        frame = samples[start:start + frame_size]
        e = rms_energy(frame)
        energies.append(e)
        frame_above_threshold.append(e > bark_threshold)
        p = estimate_pitch_hz(frame, sample_rate)
        if p > 0:
            pitches.append(p)

    # FFT on whole-signal magnitude spectrum
    n_fft = _next_power_of_two(min(n, 4096))
    mags = magnitude_spectrum(samples[:n_fft], n_fft=n_fft)
    centroid = spectral_centroid(mags, sample_rate, n_fft)
    rolloff = spectral_rolloff(mags, sample_rate, n_fft)
    zcr = zero_crossing_rate(samples)

    # Count bark events: contiguous runs of above-threshold frames
    bark_events = 0
    prev = False
    for flag in frame_above_threshold:
        if flag and not prev:
            bark_events += 1
        prev = flag
    bark_rate = bark_events / duration_s if duration_s > 0 else 0.0

    return BarkFeatures(
        pitch_mean_hz=fmean(pitches) if pitches else 0.0,
        pitch_std_hz=pstdev(pitches) if len(pitches) >= 2 else 0.0,
        duration_ms=duration_ms,
        energy_mean=fmean(energies) if energies else 0.0,
        spectral_centroid_hz=centroid,
        zero_crossing_rate=zcr,
        bark_rate_per_sec=bark_rate,
        spectral_rolloff_hz=rolloff,
    )


# ========================== kNN classifier =========================== #


def _euclidean_normalised(a: list[float], b: list[float], scales: list[float]) -> float:
    """Distance with per-feature scaling (so 'duration_ms' doesn't drown out 'zcr')."""
    s = 0.0
    for ai, bi, sc in zip(a, b, scales):
        if sc < 1e-12:
            continue
        d = (ai - bi) / sc
        s += d * d
    return math.sqrt(s)


def fit_feature_scales(training_X: list[list[float]]) -> list[float]:
    """Per-feature population stdev, used as scale denominators in distance."""
    if not training_X:
        return []
    p = len(training_X[0])
    out = []
    for j in range(p):
        col = [row[j] for row in training_X]
        sd = pstdev(col) if len(col) >= 2 else 1.0
        out.append(max(sd, 1e-6))
    return out


@dataclass
class KNNPrediction:
    predicted_class: str
    distances: list[tuple[str, float]]      # (label, distance) sorted asc
    vote_counts: dict[str, int]
    confidence: float                        # winner votes / k


def knn_predict(
    training_X: list[list[float]], training_y: list[str],
    query: list[float], scales: list[float], k: int = 3,
) -> KNNPrediction:
    if not training_X:
        return KNNPrediction(predicted_class="unknown", distances=[], vote_counts={}, confidence=0.0)
    distances = []
    for x, y in zip(training_X, training_y):
        d = _euclidean_normalised(x, query, scales)
        distances.append((y, d))
    distances.sort(key=lambda t: t[1])
    top_k = distances[: min(k, len(distances))]
    votes = Counter(label for label, _ in top_k)
    winner, winner_n = votes.most_common(1)[0]
    return KNNPrediction(
        predicted_class=winner,
        distances=distances[: 10],
        vote_counts=dict(votes),
        confidence=winner_n / len(top_k),
    )


# ========================== synthetic bark generator ================ #


def synthesise_bark(
    pitch_hz: float, duration_ms: float, sample_rate: int = 8000,
    energy: float = 1.0, noise: float = 0.05, decay: float = 0.0,
) -> list[float]:
    """Synthesise a bark-like waveform (sine + harmonics + light noise + decay).

    Useful for testing the FFT/pitch pipeline against ground truth.
    """
    import random as _r
    rng = _r.Random(42)
    n = int(sample_rate * duration_ms / 1000.0)
    out: list[float] = []
    for i in range(n):
        t = i / sample_rate
        a = energy
        if decay > 0:
            a *= math.exp(-decay * t)
        # Fundamental + 2nd harmonic to give the bark some body
        v = a * (math.sin(2 * math.pi * pitch_hz * t)
                  + 0.5 * math.sin(2 * math.pi * 2 * pitch_hz * t))
        v += noise * (rng.random() * 2.0 - 1.0)
        out.append(v)
    return out
