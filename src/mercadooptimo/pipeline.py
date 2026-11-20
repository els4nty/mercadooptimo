"""Cadena completa: histórico de precios -> precio esperado -> decisión de compra."""

from __future__ import annotations

import pandas as pd

from mercadooptimo.forecasting import get_forecaster
from mercadooptimo.optimizer import OptimizationResult, optimize_basket


def forecast_next_prices(wide: pd.DataFrame, model: str = "arima", products: list[str] | None = None) -> pd.DataFrame:
    """Precio esperado del siguiente periodo para cada (producto, tienda).

    Devuelve formato largo: product_id, store, price, last_price.
    """
    rows = []
    for product_id, store in wide.columns:
        if products and product_id not in products:
            continue
        series = wide[(product_id, store)].dropna()
        if len(series) < 3:
            continue
        pred = get_forecaster(model).fit(series).predict(1)[0]
        rows.append((product_id, store, float(pred), float(series.iloc[-1])))
    return pd.DataFrame(rows, columns=["product_id", "store", "price", "last_price"])


def recommend(
    wide: pd.DataFrame,
    demands: dict[str, int],
    budget: float,
    model: str = "arima",
    priorities: dict[str, float] | None = None,
    max_stores: int | None = None,
    reference_store: str | None = None,
) -> tuple[OptimizationResult, pd.DataFrame, dict]:
    """Recomendación de compra con su ahorro estimado frente a las líneas base.

    Devuelve (resultado, precios_esperados, resumen_ahorro).
    """
    expected = forecast_next_prices(wide, model=model, products=list(demands))
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
