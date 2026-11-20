import numpy as np
import pandas as pd
import pytest

from mercadooptimo.forecasting import ARIMAForecaster, NaiveForecaster, SeasonalNaiveForecaster
from mercadooptimo.forecasting.evaluation import backtest_series, mape, rmse, temporal_split


def test_metrics():
    assert rmse([1, 2], [1, 4]) == pytest.approx(np.sqrt(2))
    assert mape([100, 200], [110, 180]) == pytest.approx(10.0)


def test_temporal_split_is_ordered_and_disjoint():
    tr, va, te = temporal_split(100)
    assert tr.stop == va.start and va.stop == te.start and te.stop == 100


def test_naive_and_seasonal():
    s = pd.Series(np.arange(1, 61, dtype=float))
    assert NaiveForecaster().fit(s).predict(2).tolist() == [60.0, 60.0]
    assert SeasonalNaiveForecaster(52).fit(s).predict(1)[0] == 9.0


def test_arima_beats_naive_on_trending_series():
    t = np.arange(120)
    rng = np.random.default_rng(0)
    s = pd.Series(1000 * np.exp(0.01 * t + rng.normal(0, 0.002, 120)))
    bt_arima = backtest_series(s, "arima", test_size=10, refit_every=5)
    bt_naive = backtest_series(s, "naive", test_size=10)
    assert mape(bt_arima.actual, bt_arima.pred) < mape(bt_naive.actual, bt_naive.pred)
    assert ARIMAForecaster(order=(1, 1, 0)).fit(s).predict(1)[0] > s.iloc[-1]
