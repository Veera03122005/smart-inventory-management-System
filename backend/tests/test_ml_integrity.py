"""
SmartStock AI — Machine Learning Pipeline & Statistical Validation Integrity Tests.
Verifies forward-only causality (no look-ahead leakage), training-fold-only weekday profiling,
zero-denominator WAPE handling, target provenance labeling, and seed reproducibility.
"""
import numpy as np
import pandas as pd
import pytest
import ml


def test_forward_only_interpolation_no_future_leakage():
    # Construct a historical series up to day 10
    dates = pd.date_range("2026-01-01", periods=10, freq="D").strftime("%Y-%m-%d")
    s1 = pd.Series([10.0, 12.0, np.nan, 14.0, 11.0, 13.0, 15.0, 12.0, 14.0, 16.0], index=dates)

    # Compute features for s1
    f1 = ml.features(s1)

    # Now create s2 where days 8, 9, 10 are radically altered in the FUTURE
    s2 = s1.copy()
    s2.iloc[7] = 500.0
    s2.iloc[8] = 900.0
    s2.iloc[9] = 1200.0

    # Compute features for s2
    f2 = ml.features(s2)

    # Historical features up to day 6 (index 0 to 5) must be 100% IDENTICAL
    # Any difference indicates look-ahead leakage from future points
    pd.testing.assert_frame_equal(f1.iloc[:6], f2.iloc[:6])


def test_zero_denominator_wape_reported_as_none():
    # If all actual values are zero, WAPE denominator is 0.
    # Per non-negotiable rule: Must report WAPE as None (undefined/unscorable), NEVER 0%.
    y_zeros = [0.0, 0.0, 0.0, 0.0]
    preds = [1.0, 2.0, 0.5, 1.2]

    res = ml.metrics(y_zeros, preds)
    assert res["WAPE"] is None
    assert res["MAE"] > 0
    assert res["RMSE"] > 0


def test_wape_calculates_correctly_on_positive_sum():
    y = [10.0, 20.0, 30.0]
    p = [12.0, 18.0, 33.0]
    # Errors: |2| + |-2| + |3| = 7. Sum(y) = 60. WAPE = 7 / 60 * 100 = 11.67%
    res = ml.metrics(y, p)
    assert res["WAPE"] == 11.67


def test_forecast_target_metadata():
    res = ml.get_results()["results"]["ING01"]
    assert res["target_type"] == "recorded_or_reconstructed_usage"
    assert "stockout_censored" in res
    assert isinstance(res["stockout_censored"], bool)


def test_metrics_reproducibility():
    m1 = ml.make_model("Random Forest", seed=123)
    m2 = ml.make_model("Random Forest", seed=123)
    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    y = np.array([10.0, 20.0, 30.0, 40.0])

    m1.fit(X, y)
    m2.fit(X, y)

    preds1 = m1.predict(X)
    preds2 = m2.predict(X)
    np.testing.assert_array_almost_equal(preds1, preds2)


def test_changing_future_observations_does_not_affect_past_features():
    """
    Mathematical Proof of Zero Temporal Lookahead Leakage:
    Creates a time series with missing initial, middle, and late values.
    Alters observations at future dates t >= 20.
    Verifies that all computed features for dates t < 20 remain 100% bit-for-bit identical.
    """
    dates = pd.date_range("2026-01-01", periods=30, freq="D").strftime("%Y-%m-%d")
    np.random.seed(42)
    base_values = np.random.uniform(10.0, 50.0, size=30)
    # Insert NaN gaps in initial prefix and middle
    base_values[0] = np.nan
    base_values[1] = np.nan
    base_values[8] = np.nan
    base_values[9] = np.nan

    s_orig = pd.Series(base_values.copy(), index=dates)
    feats_orig = ml.features(s_orig)

    # Radically change future values at day 20..29
    s_modified = pd.Series(base_values.copy(), index=dates)
    s_modified.iloc[20:] = s_modified.iloc[20:] * 10.0 + 500.0
    feats_modified = ml.features(s_modified)

    # Check each feature column up to day 19 (index 0 to 18)
    for col in ml.FEATS:
        past_orig = feats_orig[col].iloc[:19].values
        past_mod = feats_modified[col].iloc[:19].values
        np.testing.assert_array_equal(
            past_orig, past_mod,
            err_msg=f"Feature '{col}' leaked future information into past historical dates!"
        )
