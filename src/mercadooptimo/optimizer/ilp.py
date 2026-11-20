"""Optimizador de la compra (componente principal, informe sección 6.5).

Sea I el conjunto de productos y S el de tiendas, p_is el precio esperado,
d_i la cantidad requerida y B el presupuesto. x_is ∈ Z≥0 es la cantidad del
producto i comprada en la tienda s.

Modelo base:
    min  Σ_i Σ_s p_is x_is
    s.a. Σ_s x_is ≥ d_i         ∀ i
         Σ_i Σ_s p_is x_is ≤ B

Si el modelo base es infactible (el presupuesto no alcanza), se resuelve la
variante con prioridades w_i y binarias z_i (producto cubierto):
    max  Σ_i w_i z_i  (desempate: menor costo)
    s.a. Σ_s x_is ≥ d_i z_i     ∀ i
         Σ_i Σ_s p_is x_is ≤ B

Extensión opcional: `max_stores` limita el número de tiendas visitadas con
binarias y_s (x_is ≤ d_i y_s, Σ_s y_s ≤ K). Sin ella el problema se separa por
producto; con ella deja de ser trivial y justifica el solucionador de
ramificación y acotamiento.

Se resuelve con OR-Tools (SCIP).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import pandas as pd
from ortools.linear_solver import pywraplp


@dataclass
class OptimizationResult:
    status: str  # "optimal" | "partial" (variante de prioridades) | "infeasible"
    plan: pd.DataFrame  # product_id, store, quantity, unit_price, subtotal
    total_cost: float
    budget: float
    uncovered: list[str] = field(default_factory=list)
    solve_seconds: float = 0.0
    model: str = "base"

    @property
    def stores_used(self) -> list[str]:
        return sorted(self.plan["store"].unique()) if not self.plan.empty else []


def _prices_dict(prices: pd.DataFrame) -> dict[tuple[str, str], float]:
    """Acepta formato largo (product_id, store, price) o ancho (índice producto, columnas tienda)."""
    if {"product_id", "store", "price"}.issubset(prices.columns):
        long = prices[["product_id", "store", "price"]]
    else:
        long = prices.rename_axis(index="product_id", columns="store").stack().rename("price").reset_index()
    long = long.dropna(subset=["price"])
    return {(r.product_id, r.store): float(r.price) for r in long.itertuples(index=False)}


def _build_and_solve(p, demands, budget, max_stores, priorities, time_limit):
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if time_limit:
        solver.SetTimeLimit(int(time_limit * 1000))
    products = list(demands)
    stores = sorted({s for (_, s) in p})
    x = {
        (i, s): solver.IntVar(0, demands[i], f"x[{i},{s}]")
        for (i, s) in p
        if i in demands
    }
    cost = solver.Sum(p[k] * v for k, v in x.items())
    solver.Add(cost <= budget)

    z = {}
    for i in products:
        cover = solver.Sum(v for (ii, _), v in x.items() if ii == i)
        if priorities is None:
            solver.Add(cover >= demands[i])
        else:
            z[i] = solver.BoolVar(f"z[{i}]")
            solver.Add(cover >= demands[i] * z[i])

    if max_stores is not None:
        y = {s: solver.BoolVar(f"y[{s}]") for s in stores}
        for (i, s), v in x.items():
            solver.Add(v <= demands[i] * y[s])
        solver.Add(solver.Sum(y.values()) <= max_stores)

    if priorities is None:
        solver.Minimize(cost)
    else:
        # prioridad lexicográfica: el término de costo nunca supera una unidad de prioridad
        eps = 1.0 / (budget + 1.0)
        solver.Maximize(solver.Sum(priorities[i] * z[i] for i in products) - eps * cost)

    status = solver.Solve()
    return solver, status, x, z


def optimize_basket(
    prices: pd.DataFrame,
    demands: dict[str, int],
    budget: float,
    priorities: dict[str, float] | None = None,
    max_stores: int | None = None,
    time_limit: float | None = 30.0,
) -> OptimizationResult:
    """Selecciona cuánto comprar de cada producto y en qué tienda.

    prices: precios esperados (formato largo o ancho, ver `_prices_dict`).
            Un precio ausente (NaN) significa que la tienda no ofrece el producto.
    demands: cantidad entera requerida por producto.
    priorities: pesos w_i para la variante infactible (por defecto 1 para todos).
    """
    p = _prices_dict(prices)
    demands = {i: int(d) for i, d in demands.items() if int(d) > 0}
    unavailable = [i for i in demands if not any(k[0] == i for k in p)]
    if unavailable:
        raise ValueError(f"Productos sin precio en ninguna tienda: {unavailable}")

    t0 = time.perf_counter()
    solver, status, x, _ = _build_and_solve(p, demands, budget, max_stores, None, time_limit)
    model = "base"
    uncovered: list[str] = []
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        w = {i: 1.0 for i in demands} | (priorities or {})
        solver, status, x, z = _build_and_solve(p, demands, budget, max_stores, w, time_limit)
        model = "prioridades"
        if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            uncovered = [i for i, v in z.items() if v.solution_value() < 0.5]
    elapsed = time.perf_counter() - t0

    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        empty = pd.DataFrame(columns=["product_id", "store", "quantity", "unit_price", "subtotal"])
        return OptimizationResult("infeasible", empty, 0.0, budget, list(demands), elapsed, model)

    rows = []
    for (i, s), v in x.items():
        q = int(round(v.solution_value()))
        if q > 0 and i not in uncovered:
            rows.append((i, s, q, p[(i, s)], q * p[(i, s)]))
    plan = pd.DataFrame(rows, columns=["product_id", "store", "quantity", "unit_price", "subtotal"])
    plan = plan.sort_values(["store", "product_id"]).reset_index(drop=True)
    total = float(plan["subtotal"].sum()) if not plan.empty else 0.0
    label = "optimal" if model == "base" else "partial"
    if status == pywraplp.Solver.FEASIBLE:
        label += "_timelimit"
    return OptimizationResult(label, plan, total, budget, uncovered, elapsed, model)


def greedy_basket(prices: pd.DataFrame, demands: dict[str, int], max_stores: int | None = None) -> float:
    """Heurística voraz de referencia para calcular la razón de optimalidad.

    Con `max_stores`, elige iterativamente la tienda que más reduce el costo y
    luego compra cada producto en la más barata de las elegidas. Devuelve el
    costo (inf si alguna demanda no se puede cubrir).
    """
    p = _prices_dict(prices)
    stores = sorted({s for (_, s) in p})

    def cost_with(chosen):
        total = 0.0
        for i, d in demands.items():
            options = [p[(i, s)] for s in chosen if (i, s) in p]
            if not options:
                return math.inf
            total += d * min(options)
        return total

    if max_stores is None or max_stores >= len(stores):
        return cost_with(stores)
    def coverage(chosen):
        return sum(1 for i in demands if any((i, s) in p for s in chosen))

    chosen: list[str] = []
    for _ in range(max_stores):
        # prioriza cubrir más productos; a igual cobertura, menor costo parcial
        def score(s):
            trial = chosen + [s]
            covered = [i for i in demands if any((i, t) in p for t in trial)]
            partial = sum(demands[i] * min(p[(i, t)] for t in trial if (i, t) in p) for i in covered)
            return (-coverage(trial), partial)

        chosen.append(min((s for s in stores if s not in chosen), key=score))
    return cost_with(chosen)
