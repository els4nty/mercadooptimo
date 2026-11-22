import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch")

from mercadooptimo.forecasting import get_forecaster  # noqa: E402
from mercadooptimo.forecasting.lstm import LSTMForecaster  # noqa: E402


def _series(n=120, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return pd.Series(1000 * np.exp(0.002 * t + 0.03 * np.sin(2 * np.pi * t / 26) + rng.normal(0, 0.005, n)))


def test_lstm_predicts_positive_finite_prices_close_to_last():
    s = _series()
    pred = get_forecaster("lstm", epochs=40).fit(s).predict(3)
    assert pred.shape == (3,)
    assert np.all(np.isfinite(pred)) and np.all(pred > 0)
    assert abs(pred[0] / s.iloc[-1] - 1) < 0.1


def test_lstm_is_deterministic_with_seed():
    s = _series()
    a = LSTMForecaster(epochs=30, seed=3).fit(s).predict(1)[0]
    b = LSTMForecaster(epochs=30, seed=3).fit(s).predict(1)[0]
    assert a == pytest.approx(b)


def test_lstm_short_series_falls_back_to_naive():
    s = _series(20)
    assert LSTMForecaster().fit(s).predict(1)[0] == pytest.approx(s.iloc[-1])


def test_lstm_update_uses_new_observations_without_refit():
    s = _series()
    m = LSTMForecaster(epochs=30).fit(s.iloc[:-5])
    before = m.predict(1)[0]
    m.update(s)
    assert m._last_log == pytest.approx(np.log(s.iloc[-1]))
    assert m.predict(1)[0] != pytest.approx(before)
