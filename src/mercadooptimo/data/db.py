"""Almacenamiento del histórico de precios en SQLite.

Esquema: una fila por (producto, tienda, fecha, fuente) con el precio en COP.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    product_id TEXT NOT NULL,
    store      TEXT NOT NULL,
    date       TEXT NOT NULL,   -- ISO yyyy-mm-dd
    price      REAL NOT NULL,   -- COP
    source     TEXT NOT NULL,   -- 'scraping' | 'sipsa' | 'synthetic' | ...
    PRIMARY KEY (product_id, store, date, source)
);
CREATE INDEX IF NOT EXISTS idx_prices_series ON prices (product_id, store, date);
"""

COLUMNS = ["product_id", "store", "date", "price", "source"]


def connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def save_prices(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Inserta (o reemplaza) precios. `df` debe tener las columnas de COLUMNS."""
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas: {sorted(missing)}")
    rows = df[COLUMNS].copy()
    rows["date"] = pd.to_datetime(rows["date"]).dt.strftime("%Y-%m-%d")
    conn.executemany(
        "INSERT OR REPLACE INTO prices VALUES (?, ?, ?, ?, ?)",
        rows.itertuples(index=False, name=None),
    )
    conn.commit()
    return len(rows)


def load_prices(
    conn: sqlite3.Connection,
    source: str | None = None,
    product_ids: list[str] | None = None,
) -> pd.DataFrame:
    query = "SELECT product_id, store, date, price, source FROM prices WHERE 1=1"
    params: list = []
    if source:
        query += " AND source = ?"
        params.append(source)
    if product_ids:
        query += f" AND product_id IN ({','.join('?' * len(product_ids))})"
        params.extend(product_ids)
    df = pd.read_sql_query(query + " ORDER BY product_id, store, date", conn, params=params)
    df["date"] = pd.to_datetime(df["date"])
    return df


def to_wide(df: pd.DataFrame, freq: str = "W-MON") -> pd.DataFrame:
    """Pivotea a series semanales: índice = fecha, columnas = (product_id, store).

    Si hay varias observaciones en la misma semana se promedian; los huecos se
    rellenan hacia adelante (último precio publicado).
    """
    wide = (
        df.set_index("date")
        .groupby(["product_id", "store"])["price"]
        .resample(freq)
        .mean()
        .unstack(["product_id", "store"])
        .sort_index()
    )
    return wide.ffill()
