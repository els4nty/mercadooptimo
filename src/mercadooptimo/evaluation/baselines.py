"""Líneas base de compra (informe, objetivos específicos).

* Línea base A: comprar toda la lista en una tienda de referencia.
* Línea base B: comprar cada producto en la tienda más barata del día
  (precios actuales, sin predicción).
"""

from __future__ import annotations

import math

import pandas as pd


def single_store_cost(prices_wide: pd.DataFrame, demands: dict[str, int], store: str | None = None) -> tuple[float, str]:
    """Costo de comprar todo en `store`. Si es None, se usa la tienda que
    ofrece todos los productos con el mayor costo mediano entre las tiendas
    completas (tienda "típica"); `prices_wide`: índice producto, columnas tienda."""
    sub = prices_wide.reindex(list(demands))
    qty = pd.Series(demands, dtype=float)
    costs = sub.mul(qty, axis=0).sum(skipna=False)
    if store is not None:
        return float(costs.get(store, math.nan)), store
    complete = costs.dropna().sort_values()
    if complete.empty:
        return math.nan, ""
    median_store = complete.index[len(complete) // 2]
    return float(complete[median_store]), median_store


def cheapest_today_plan(today_wide: pd.DataFrame, demands: dict[str, int]) -> dict[str, str]:
    """Línea base B: tienda más barata HOY para cada producto."""
    return {i: today_wide.loc[i].dropna().idxmin() for i in demands}


def plan_cost(plan: dict[str, str] | pd.DataFrame, prices_wide: pd.DataFrame, demands: dict[str, int]) -> float:
    """Costo realizado de un plan con los precios `prices_wide` (p. ej. los reales)."""
    if isinstance(plan, pd.DataFrame):
        return float(sum(r.quantity * prices_wide.loc[r.product_id, r.store] for r in plan.itertuples()))
    return float(sum(demands[i] * prices_wide.loc[i, s] for i, s in plan.items()))
