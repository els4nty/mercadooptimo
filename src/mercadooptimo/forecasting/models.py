"""Modelos de predicción del precio del siguiente periodo de compra.

* NaiveForecaster: repite el último precio (línea base del informe).
* SeasonalNaiveForecaster: repite el precio de hace `season` semanas.
* ARIMAForecaster: ARIMA de statsmodels sobre log-precio, con selección de
  orden por AIC en una rejilla pequeña.

* LSTMForecaster (módulo `lstm`, requiere PyTorch): red recurrente sobre
  retornos logarítmicos.

Todos comparten la interfaz `fit(series) -> self` / `predict(h) -> np.ndarray`;
los que pueden incorporar datos nuevos sin reentrenar implementan `update`.
"""

from __future__ import annotations

import itertools
import warnings
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class Forecaster(ABC):
    name = "base"

    @abstractmethod
    def fit(self, series: pd.Series) -> "Forecaster": ...

    @abstractmethod
    def predict(self, horizon: int = 1) -> np.ndarray: ...


class NaiveForecaster(Forecaster):
    name = "naive"

    def fit(self, series: pd.Series) -> "NaiveForecaster":
        self._last = float(series.dropna().iloc[-1])
        return self

    def predict(self, horizon: int = 1) -> np.ndarray:
        return np.full(horizon, self._last)


class SeasonalNaiveForecaster(Forecaster):
    name = "seasonal_naive"

    def __init__(self, season: int = 52):
        self.season = season

    def fit(self, series: pd.Series) -> "SeasonalNaiveForecaster":
        self._values = series.dropna().to_numpy(dtype=float)
        return self

    def predict(self, horizon: int = 1) -> np.ndarray:
        v = self._values
        if len(v) < self.season:
            return np.full(horizon, v[-1])
        return np.array([v[len(v) - self.season + (h % self.season)] for h in range(horizon)])


class ARIMAForecaster(Forecaster):
    name = "arima"

    def __init__(self, order: tuple[int, int, int] | None = None, max_p: int = 2, max_q: int = 2):
        self.order = order
        self.max_p = max_p
        self.max_q = max_q

    def fit(self, series: pd.Series) -> "ARIMAForecaster":
        from statsmodels.tsa.arima.model import ARIMA

        y = np.log(series.dropna().to_numpy(dtype=float))
        candidates = (
            [self.order]
            if self.order
            else [(p, 1, q) for p, q in itertools.product(range(self.max_p + 1), range(self.max_q + 1))]
        )
        best, best_aic = None, np.inf
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for order in candidates:
                try:
                    res = ARIMA(y, order=order, trend="t" if order[1] == 1 else "c").fit()
                except Exception:
                    continue
                if res.aic < best_aic:
                    best, best_aic = res, res.aic
        if best is None:  # fallback robusto
            self._fallback = NaiveForecaster().fit(series)
        else:
            self._fallback = None
        self._result = best
        return self

    def predict(self, horizon: int = 1) -> np.ndarray:
        if self._fallback is not None:
            return self._fallback.predict(horizon)
        return np.exp(np.asarray(self._result.forecast(horizon)))

    def update(self, series: pd.Series) -> "ARIMAForecaster":
        """Incorpora observaciones nuevas conservando los parámetros estimados
        (filtro de Kalman), para predecir a un paso sin reentrenar."""
        if self._fallback is not None:
            self._fallback.fit(series)
        else:
            y = np.log(series.dropna().to_numpy(dtype=float))
            self._result = self._result.apply(y)
        return self

    @property
    def selected_order(self):
        return None if self._result is None else self._result.model.order


FORECASTERS = {
    "naive": NaiveForecaster,
    "seasonal_naive": SeasonalNaiveForecaster,
    "arima": ARIMAForecaster,
}


def get_forecaster(name: str, **kwargs) -> Forecaster:
    if name == "lstm":  # import diferido: PyTorch es opcional
        from mercadooptimo.forecasting.lstm import LSTMForecaster

        return LSTMForecaster(**kwargs)
    try:
        return FORECASTERS[name](**kwargs)
    except KeyError:
        raise ValueError(f"Modelo desconocido '{name}'. Opciones: {sorted(FORECASTERS) + ['lstm']}") from None
