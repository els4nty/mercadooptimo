import pandas as pd

from mercadooptimo.cli import main
from mercadooptimo.data import db
from mercadooptimo.pipeline import forecast_next_prices


def _rows(date, price):
    return pd.DataFrame([("p1", "jumbo", date, price, "scraping")], columns=db.COLUMNS)


def test_append_csv_deduplicates_and_keeps_latest(tmp_path):
    path = tmp_path / "h" / "precios.csv"
    assert db.append_csv(_rows("2026-11-20", 100.0), path) == 1
    assert db.append_csv(_rows("2026-11-20", 105.0), path) == 0  # mismo día: reemplaza
    assert db.append_csv(_rows("2026-11-21", 110.0), path) == 1
    df = db.read_csv(path)
    assert df.price.tolist() == [105.0, 110.0]


def test_import_csv_command(tmp_path):
    csv, dbp = tmp_path / "precios.csv", tmp_path / "t.db"
    db.append_csv(_rows("2026-11-20", 100.0), csv)
    main(["--db", str(dbp), "import-csv", str(csv)])
    assert len(db.load_prices(db.connect(dbp))) == 1


def test_short_history_uses_naive():
    idx = pd.date_range("2026-01-05", periods=8, freq="W-MON")
    wide = pd.DataFrame({("p1", "s1"): [100, 101, 102, 103, 104, 105, 106, 107.0]}, index=idx)
    out = forecast_next_prices(wide, model="arima")
    assert out.model.iloc[0] == "naive" and out.price.iloc[0] == 107.0
