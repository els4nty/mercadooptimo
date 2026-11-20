import sqlite3

from mercadooptimo.data import db
from mercadooptimo.data.scrapers.base import parse_cop
from mercadooptimo.data.synthetic import generate_prices
from mercadooptimo.evaluation.savings import backtest_savings
from mercadooptimo.pipeline import recommend


def _wide(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.save_prices(conn, generate_prices(weeks=60, seed=1))
    return db.to_wide(db.load_prices(conn))


def test_db_roundtrip_and_wide(tmp_path):
    wide = _wide(tmp_path)
    assert wide.shape[0] == 60
    assert not wide.isna().any().any()


def test_recommend_end_to_end(tmp_path):
    wide = _wide(tmp_path)
    demands = {"arroz": 2, "huevos": 1, "res_molida": 1}
    result, expected, summary = recommend(wide, demands, budget=500_000, model="naive")
    assert result.status == "optimal"
    assert result.plan.quantity.sum() == 4
    assert summary["ahorro"] >= 0


def test_backtest_savings_runs(tmp_path):
    wide = _wide(tmp_path)
    bt = backtest_savings(wide, {"arroz": 1, "leche": 2}, weeks=3, model="naive")
    assert len(bt) == 3
    # el oráculo nunca es peor que el sistema
    assert (bt.costo_oraculo <= bt.costo_sistema + 1e-6).all()


def test_parse_cop():
    assert parse_cop("$ 14.500") == 14500
    assert parse_cop("$14.500,50") == 14500.5
    assert parse_cop("sin precio") is None
