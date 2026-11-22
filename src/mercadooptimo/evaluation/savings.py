"""Backtest del ahorro: simula semanas de compra en el periodo de prueba.

En cada semana t: el sistema solo ve precios hasta t-1, predice los de t,
optimiza, y se evalúa el COSTO REALIZADO con los precios reales de t contra:
  A) comprar todo en la tienda de referencia (precios reales de t);
  B) comprar cada producto en la tienda más barata de t-1 (sin predicción).
También se reporta el costo del oráculo (óptimo con precios reales conocidos).
"""

from __future__ import annotations

import pandas as pd

from mercadooptimo.evaluation.baselines import cheapest_today_plan, plan_cost, single_store_cost
from mercadooptimo.optimizer import optimize_basket
from mercadooptimo.pipeline import forecast_next_prices


def _slice_wide(wide: pd.DataFrame, row: int) -> pd.DataFrame:
    """Precios de la fila `row` como tabla producto x tienda."""
    return wide.iloc[row].unstack("store")


def backtest_savings(
    wide: pd.DataFrame,
    demands: dict[str, int],
    weeks: int = 12,
    model: str = "arima",
    reference_store: str | None = None,
    max_stores: int | None = None,
    model_kwargs: dict | None = None,
    progress=None,
) -> pd.DataFrame:
    products = list(demands)
    no_budget = 1e15  # el ahorro se mide sin restricción presupuestal activa
    records = []
    n = len(wide)
    for k, t in enumerate(range(n - weeks, n)):
        if progress:
            progress(k / weeks)
        history = wide.iloc[:t]
        actual = _slice_wide(wide, t)
        yesterday = _slice_wide(wide, t - 1)
        expected = forecast_next_prices(history, model=model, products=products, model_kwargs=model_kwargs)
        res = optimize_basket(expected, demands, no_budget, max_stores=max_stores)
        oracle = optimize_basket(actual.stack().rename("price").reset_index(), demands, no_budget, max_stores=max_stores)
        cost_sys = plan_cost(res.plan, actual, demands)
        cost_a, ref = single_store_cost(actual, demands, reference_store)
        cost_b = plan_cost(cheapest_today_plan(yesterday, demands), actual, demands)
        records.append(
            {
                "date": wide.index[t],
                "costo_sistema": cost_sys,
                "costo_esperado": res.total_cost,
                "costo_A_tienda_ref": cost_a,
                "tienda_ref": ref,
                "costo_B_mas_barata_ayer": cost_b,
                "costo_oraculo": oracle.total_cost,
                "ahorro_vs_A_%": 100 * (cost_a - cost_sys) / cost_a,
                "ahorro_vs_B_%": 100 * (cost_b - cost_sys) / cost_b,
                "brecha_oraculo_%": 100 * (cost_sys - oracle.total_cost) / oracle.total_cost,
                "segundos_optimizador": res.solve_seconds,
            }
        )
    return pd.DataFrame(records)
