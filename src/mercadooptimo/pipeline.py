"""Cadena completa: histórico de precios -> precio esperado -> decisión de compra."""

from __future__ import annotations

import pandas as pd

from mercadooptimo.forecasting import get_forecaster
from mercadooptimo.optimizer import OptimizationResult, optimize_basket


MIN_HISTORY = {"arima": 20, "lstm": 42}  # semanas mínimas para usar el modelo; si no, ingenuo


def forecast_next_prices(wide: pd.DataFrame, model: str = "arima", products: list[str] | None = None,
                         model_kwargs: dict | None = None) -> pd.DataFrame:
    """Precio esperado del siguiente periodo para cada (producto, tienda).

    Con poca historia (p. ej. los primeros meses de scraping real) se usa el
    modelo ingenuo para esa serie: un modelo estadístico entrenado con unas
    pocas semanas no es confiable. La columna `model` indica cuál se usó.

    Devuelve formato largo: product_id, store, price, last_price, model.
    """
    rows = []
    for product_id, store in wide.columns:
        if products and product_id not in products:
            continue
        series = wide[(product_id, store)].dropna()
        if len(series) < 3:
            continue
        used = model if len(series) >= MIN_HISTORY.get(model, 3) else "naive"
        kw = (model_kwargs or {}) if used == model else {}
        pred = get_forecaster(used, **kw).fit(series).predict(1)[0]
        rows.append((product_id, store, float(pred), float(series.iloc[-1]), used))
    return pd.DataFrame(rows, columns=["product_id", "store", "price", "last_price", "model"])


def recommend(
    wide: pd.DataFrame,
    demands: dict[str, int],
    budget: float,
    model: str = "arima",
    priorities: dict[str, float] | None = None,
    max_stores: int | None = None,
    reference_store: str | None = None,
    model_kwargs: dict | None = None,
) -> tuple[OptimizationResult, pd.DataFrame, dict]:
    """Recomendación de compra con su ahorro estimado frente a las líneas base.

    Devuelve (resultado, precios_esperados, resumen_ahorro).
    """
    expected = forecast_next_prices(wide, model=model, products=list(demands), model_kwargs=model_kwargs)
    result = optimize_basket(expected, demands, budget, priorities=priorities, max_stores=max_stores)
    summary = estimated_savings(expected, demands, result, reference_store)
    return result, expected, summary


def estimated_savings(expected: pd.DataFrame, demands: dict[str, int], result: OptimizationResult,
                      reference_store: str | None = None) -> dict:
    """Ahorro estimado (con precios esperados) frente a comprar todo en una sola tienda."""
    from mercadooptimo.evaluation.baselines import single_store_cost

    covered = {i: d for i, d in demands.items() if i not in result.uncovered}
    wide_exp = expected.pivot(index="product_id", columns="store", values="price")
    ref_cost, ref_store = single_store_cost(wide_exp, covered, reference_store)
    saving = ref_cost - result.total_cost
    return {
        "costo_optimizado": result.total_cost,
        "costo_referencia": ref_cost,
        "tienda_referencia": ref_store,
        "ahorro": saving,
        "ahorro_pct": 100 * saving / ref_cost if ref_cost else 0.0,
    }
