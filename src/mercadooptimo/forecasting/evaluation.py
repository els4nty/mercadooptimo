"""Evaluación de los modelos con partición temporal (sin fuga de información).

`backtest` hace validación con origen móvil: para cada semana t del periodo
de prueba entrena con los datos hasta t-1 y predice t (horizonte 1, que es
el siguiente periodo de compra).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mercadooptimo.forecasting.models import get_forecaster


def rmse(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mape(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    return float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)


def temporal_split(n: int, val_frac: float = 0.15, test_frac: float = 0.15) -> tuple[slice, slice, slice]:
    n_test = max(1, int(round(n * test_frac)))
    n_val = max(1, int(round(n * val_frac)))
    n_train = n - n_val - n_test
    if n_train < 10:
        raise ValueError("Serie demasiado corta para la partición temporal")
    return slice(0, n_train), slice(n_train, n_train + n_val), slice(n_train + n_val, n)


def backtest_series(series: pd.Series, model: str, test_size: int, refit_every: int = 1, **kw) -> pd.DataFrame:
    """Predicciones a un paso sobre las últimas `test_size` observaciones."""
    series = series.dropna()
    n = len(series)
    preds, fitted = [], None  # siempre predicción a un paso con datos hasta t-1
    for k, t in enumerate(range(n - test_size, n)):
        if fitted is None or k % refit_every == 0:
            fitted = get_forecaster(model, **kw).fit(series.iloc[:t])
        elif hasattr(fitted, "update"):  # actualiza el estado sin reestimar parámetros
            fitted.update(series.iloc[:t])
        else:
            fitted.fit(series.iloc[:t])
        preds.append(fitted.predict(1)[0])
    return pd.DataFrame(
        {"date": series.index[n - test_size :], "actual": series.iloc[n - test_size :].to_numpy(), "pred": preds}
    )


def compare_models(
    wide: pd.DataFrame,
    models: list[str] = ("naive", "arima"),
    test_frac: float = 0.15,
    refit_every: int = 4,
) -> pd.DataFrame:
    """RMSE y MAPE por modelo sobre todas las series (producto, tienda)."""
    n = len(wide)
    _, _, test = temporal_split(n, test_frac=test_frac)
    test_size = test.stop - test.start
    records = []
    for col in wide.columns:
        for m in models:
            costly = m in ("arima", "lstm")  # se reentrenan cada `refit_every` semanas y se actualizan entre medio
            bt = backtest_series(wide[col], m, test_size, refit_every=refit_every if costly else 1)
            records.append(
                {
                    "product_id": col[0],
                    "store": col[1],
                    "model": m,
                    "rmse": rmse(bt.actual, bt.pred),
                    "mape": mape(bt.actual, bt.pred),
                }
            )
    return pd.DataFrame(records)


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    summary = results.groupby("model")[["rmse", "mape"]].mean()
    if "naive" in summary.index:
        summary["mejora_mape_vs_naive_%"] = (1 - summary["mape"] / summary.loc["naive", "mape"]) * 100
    return summary
