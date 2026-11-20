import itertools
import math

import pandas as pd
import pytest

from mercadooptimo.optimizer import optimize_basket
from mercadooptimo.optimizer.ilp import greedy_basket

PRICES = pd.DataFrame(
    {"s1": [10.0, 5.0, 8.0], "s2": [12.0, 4.0, 9.0], "s3": [9.0, 6.0, math.nan]},
    index=["a", "b", "c"],
)


def test_base_model_picks_cheapest_store_per_product():
    res = optimize_basket(PRICES, {"a": 2, "b": 3, "c": 1}, budget=1000)
    assert res.status == "optimal"
    chosen = dict(zip(res.plan.product_id, res.plan.store))
    assert chosen == {"a": "s3", "b": "s2", "c": "s1"}
    assert res.total_cost == pytest.approx(2 * 9 + 3 * 4 + 8)


def test_respects_budget_and_uses_priorities_when_infeasible():
    # costo mínimo total = 38; con 30 no alcanza
    res = optimize_basket(PRICES, {"a": 2, "b": 3, "c": 1}, budget=30, priorities={"a": 5, "b": 1, "c": 1})
    assert res.status == "partial"
    assert res.total_cost <= 30
    assert "a" not in res.uncovered  # el de mayor prioridad se cubre
    assert res.uncovered


def test_max_stores_matches_brute_force():
    demands = {"a": 2, "b": 3, "c": 1}
    res = optimize_basket(PRICES, demands, budget=1000, max_stores=1)
    best = math.inf
    for s in PRICES.columns:
        col = PRICES[s]
        if col.reindex(list(demands)).isna().any():
            continue
        best = min(best, sum(d * col[i] for i, d in demands.items()))
    assert res.total_cost == pytest.approx(best)
    assert len(res.stores_used) == 1


def test_max_stores_two_vs_exhaustive_and_greedy():
    demands = {"a": 1, "b": 1, "c": 1}
    res = optimize_basket(PRICES, demands, budget=1000, max_stores=2)
    best = min(
        sum(d * PRICES.loc[i, list(pair)].min() for i, d in demands.items())
        for pair in itertools.combinations(PRICES.columns, 2)
    )
    assert res.total_cost == pytest.approx(best)
    assert greedy_basket(PRICES, demands, max_stores=2) >= res.total_cost - 1e-9


def test_long_format_input():
    long = PRICES.rename_axis(index="product_id", columns="store").stack().rename("price").reset_index()
    res = optimize_basket(long, {"b": 1}, budget=100)
    assert res.plan.iloc[0].store == "s2"


def test_unknown_product_raises():
    with pytest.raises(ValueError):
        optimize_basket(PRICES, {"z": 1}, budget=100)
