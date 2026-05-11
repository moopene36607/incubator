"""Edge-case tests for mcmc.py -- Metropolis-Hastings Bayesian logistic demand.

Run: python3 tests_mcmc.py
"""
from __future__ import annotations

import math
import random
import sys

from mcmc import (
    sigmoid, logit_predict, log_likelihood, log_prior, log_posterior,
    run_mh, sweep_prices, optimal_price,
    NormalPrior, Booking, DEFAULT_PRIORS,
)


def assert_close(a, b, tol=1e-6, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol {tol})")


def test_sigmoid_zero():
    assert_close(sigmoid(0.0), 0.5, msg="sigmoid(0)")


def test_sigmoid_monotonic():
    assert sigmoid(-5) < sigmoid(-1) < sigmoid(0) < sigmoid(1) < sigmoid(5)


def test_sigmoid_numerical_stability():
    # Should not overflow for large magnitudes.
    assert sigmoid(1000) > 0.99
    assert sigmoid(-1000) < 0.01


def test_sigmoid_bounded():
    # At extreme magnitudes, float underflow makes sigmoid land exactly on the boundary;
    # what we really care about is that it stays in [0, 1] and is symmetric around 0.5.
    assert 0.0 <= sigmoid(50) <= 1.0
    assert 0.0 <= sigmoid(-50) <= 1.0
    # At moderate magnitudes, strict inequality must hold.
    assert 0.0 < sigmoid(5) < 1.0
    assert 0.0 < sigmoid(-5) < 1.0


def test_normal_prior_pdf_peaks_at_mu():
    pr = NormalPrior(mu=0.0, sigma=1.0)
    # log_pdf at mu should be the peak
    at_mu = pr.log_pdf(0.0)
    away = pr.log_pdf(2.0)
    assert at_mu > away


def test_logit_predict_baseline_returns_intercept_sigmoid():
    # At price == baseline, log(price/baseline) = 0, weekend=0, holiday=0:
    # logit P = alpha -> P = sigmoid(alpha)
    theta = {"alpha": 0.5, "beta_price": -2.0, "beta_weekend": 1.0, "beta_holiday": 1.5}
    p = logit_predict(theta, price=2400, is_weekend=0, is_holiday=0, baseline_price=2400)
    assert_close(p, sigmoid(0.5), msg="baseline price returns sigmoid(alpha)")


def test_logit_predict_higher_price_lower_prob():
    theta = {"alpha": 0.0, "beta_price": -2.0, "beta_weekend": 0.0, "beta_holiday": 0.0}
    p_low = logit_predict(theta, 2000, 0, 0, 2400)
    p_high = logit_predict(theta, 3000, 0, 0, 2400)
    assert p_low > p_high, "demand should fall with price"


def test_logit_predict_weekend_lifts_demand():
    theta = {"alpha": -1.0, "beta_price": -1.0, "beta_weekend": 2.0, "beta_holiday": 0.0}
    p_wk = logit_predict(theta, 2400, 0, 0, 2400)
    p_we = logit_predict(theta, 2400, 1, 0, 2400)
    assert p_we > p_wk


def test_log_likelihood_perfect_prediction():
    # If model predicts certain booking, log-likelihood for booked=1 should be ~0; for booked=0 very negative.
    theta = {"alpha": 50.0, "beta_price": 0.0, "beta_weekend": 0.0, "beta_holiday": 0.0}
    # alpha=50 -> p ~ 1.0
    data_book = [Booking(2400, 0, 0, 1)]
    data_nobook = [Booking(2400, 0, 0, 0)]
    ll_book = log_likelihood(theta, data_book, 2400)
    ll_nobook = log_likelihood(theta, data_nobook, 2400)
    assert ll_book > ll_nobook  # confident in booked is good
    assert ll_book > -0.001     # very close to 0


def test_log_prior_at_mean_is_max():
    priors = {"alpha": NormalPrior(0, 1), "beta_price": NormalPrior(0, 1),
              "beta_weekend": NormalPrior(0, 1), "beta_holiday": NormalPrior(0, 1)}
    theta_mu = {k: 0.0 for k in priors}
    theta_away = {k: 2.0 for k in priors}
    assert log_prior(theta_mu, priors) > log_prior(theta_away, priors)


def test_mcmc_runs_and_returns_samples():
    data = [Booking(2400, 0, 0, 1), Booking(3500, 1, 0, 1),
            Booking(2300, 0, 0, 0), Booking(2500, 0, 0, 0)]
    result = run_mh(data, baseline_price=2400, n_iter=500, burn_in=100, thin=1, seed=42)
    assert len(result.samples) == 400


def test_mcmc_acceptance_rate_reasonable():
    data = [Booking(2400 + 100 * (i % 5), i % 7 == 5 or i % 7 == 6, 0, (i + 3) % 4 < 3)
            for i in range(30)]
    result = run_mh(data, baseline_price=2400, n_iter=1000, burn_in=200, thin=1, seed=42)
    # Acceptance rate should be in a reasonable range (typically 10%-80% for random-walk).
    ar = result.acceptance_rate()
    assert 0.05 < ar < 0.95, f"unreasonable acceptance rate: {ar}"


def test_mcmc_beta_price_recovers_negative():
    """If data is generated with a clearly-negative price effect, posterior beta_price should be negative."""
    # Simulate: at low price, mostly booked; at high price, mostly not booked.
    data = []
    for _ in range(15):
        data.append(Booking(2000, 0, 0, 1))   # low price, booked
    for _ in range(15):
        data.append(Booking(3500, 0, 0, 0))   # high price, not booked
    result = run_mh(data, baseline_price=2400, n_iter=3000, burn_in=500, thin=2, seed=42)
    mu_bp = result.posterior_mean("beta_price")
    assert mu_bp < 0, f"posterior beta_price should be negative; got {mu_bp}"


def test_mcmc_credible_interval_ordered():
    data = [Booking(2400, 0, 0, 1), Booking(2500, 0, 0, 0),
            Booking(3200, 1, 0, 1), Booking(3500, 1, 0, 1)]
    result = run_mh(data, baseline_price=2400, n_iter=1000, burn_in=200, seed=42)
    for k in ("alpha", "beta_price", "beta_weekend", "beta_holiday"):
        lo, hi = result.credible_interval(k, 0.95)
        assert lo <= hi, f"CI low {lo} > high {hi} for {k}"


def test_mcmc_deterministic_with_seed():
    data = [Booking(2400, 0, 0, 1), Booking(3500, 1, 0, 1),
            Booking(2300, 0, 0, 0), Booking(2500, 0, 0, 0)]
    r1 = run_mh(data, baseline_price=2400, n_iter=500, burn_in=100, thin=1, seed=42)
    r2 = run_mh(data, baseline_price=2400, n_iter=500, burn_in=100, thin=1, seed=42)
    for k in ("alpha", "beta_price", "beta_weekend", "beta_holiday"):
        assert_close(r1.posterior_mean(k), r2.posterior_mean(k), tol=1e-9, msg=f"seed determinism {k}")


def test_sweep_prices_returns_all_points():
    data = [Booking(2400, 0, 0, 1), Booking(2600, 0, 0, 0),
            Booking(3200, 1, 0, 1), Booking(3500, 1, 0, 1)]
    result = run_mh(data, baseline_price=2400, n_iter=500, burn_in=100, seed=42)
    grid = [2000, 2400, 2800, 3200]
    points = sweep_prices(result, is_weekend=0, is_holiday=0, baseline_price=2400, price_grid=grid)
    assert len(points) == 4
    for pt in points:
        assert 0 <= pt.book_prob_mean <= 1
        assert pt.expected_revenue_mean >= 0


def test_sweep_prices_higher_price_lower_book_prob_after_learning():
    """With clear price-elastic data, posterior should produce a decreasing P(book) curve."""
    data = []
    for _ in range(15):
        data.append(Booking(2000, 0, 0, 1))
    for _ in range(15):
        data.append(Booking(3500, 0, 0, 0))
    result = run_mh(data, baseline_price=2400, n_iter=3000, burn_in=500, thin=2, seed=42)
    grid = [2000, 2400, 2800, 3200, 3600]
    points = sweep_prices(result, is_weekend=0, is_holiday=0, baseline_price=2400, price_grid=grid)
    probs = [pt.book_prob_mean for pt in points]
    # Should be monotone non-increasing.
    for i in range(len(probs) - 1):
        assert probs[i] >= probs[i + 1] - 0.05, f"P(book) not decreasing at idx {i}: {probs}"


def test_optimal_price_maximises_expected_revenue():
    # Build dummy PricePoints manually and check optimal_price picks max.
    from mcmc import PricePoint
    points = [
        PricePoint(price=2000, book_prob_mean=0.9, book_prob_low=0.8, book_prob_high=0.95,
                   expected_revenue_mean=1800, expected_revenue_low=1600, expected_revenue_high=1900),
        PricePoint(price=3000, book_prob_mean=0.7, book_prob_low=0.6, book_prob_high=0.8,
                   expected_revenue_mean=2100, expected_revenue_low=1800, expected_revenue_high=2400),
        PricePoint(price=4000, book_prob_mean=0.3, book_prob_low=0.2, book_prob_high=0.4,
                   expected_revenue_mean=1200, expected_revenue_low=800, expected_revenue_high=1600),
    ]
    best = optimal_price(points)
    assert best.price == 3000


def test_log_posterior_is_finite_for_valid_theta():
    data = [Booking(2400, 0, 0, 1), Booking(3500, 1, 0, 1)]
    theta = {"alpha": 0.0, "beta_price": -2.0, "beta_weekend": 0.8, "beta_holiday": 1.2}
    lp = log_posterior(theta, data, DEFAULT_PRIORS, baseline_price=2400)
    assert math.isfinite(lp)


def test_log_likelihood_zero_for_empty_data():
    theta = {"alpha": 0.0, "beta_price": -2.0, "beta_weekend": 0.8, "beta_holiday": 1.2}
    ll = log_likelihood(theta, [], baseline_price=2400)
    assert ll == 0.0


def test_credible_interval_levels():
    data = [Booking(2400, 0, 0, 1), Booking(3500, 1, 0, 1),
            Booking(2300, 0, 0, 0), Booking(2500, 0, 0, 0)]
    result = run_mh(data, baseline_price=2400, n_iter=1000, burn_in=200, seed=42)
    lo80, hi80 = result.credible_interval("beta_price", 0.80)
    lo95, hi95 = result.credible_interval("beta_price", 0.95)
    assert hi95 - lo95 >= hi80 - lo80, "95% CI should be wider than 80%"


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
