"""Generador de precios SINTÉTICOS para desarrollo y pruebas.

Mientras se completa la recolección real (scraping de cadenas y SIPSA-DANE),
este módulo produce series semanales con tendencia inflacionaria,
estacionalidad anual, choques persistentes (AR(1)) y diferencias de precio
entre tiendas. Los datos se guardan con source='synthetic' para que nunca se
confundan con datos reales en la evaluación final.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mercadooptimo.catalog import PRODUCTS, STORES


def generate_prices(
    weeks: int = 156,
    start: str = "2023-01-02",
    seed: int = 42,
    annual_inflation: float = 0.07,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=weeks, freq="W-MON")
    t = np.arange(weeks)
    weekly_growth = (1 + annual_inflation) ** (1 / 52) - 1
    rows = []
    for product in PRODUCTS:
        volatility = 0.035 if product.category == "proteina" else 0.025
        season_amp = rng.uniform(0.01, 0.06)
        season_phase = rng.uniform(0, 2 * np.pi)
        # choque común del producto (mercado mayorista), AR(1)
        common = np.zeros(weeks)
        for k in range(1, weeks):
            common[k] = 0.85 * common[k - 1] + rng.normal(0, volatility)
        for store in STORES:
            store_offset = rng.normal(0, 0.06)
            idio = np.zeros(weeks)
            for k in range(1, weeks):
                idio[k] = 0.6 * idio[k - 1] + rng.normal(0, volatility / 2)
            # promociones esporádicas
            promo = np.where(rng.random(weeks) < 0.06, -rng.uniform(0.08, 0.2, weeks), 0.0)
            log_price = (
                np.log(product.base_price)
                + store_offset
                + t * weekly_growth
                + season_amp * np.sin(2 * np.pi * t / 52 + season_phase)
                + common
                + idio
                + promo
            )
            prices = np.round(np.exp(log_price) / 10) * 10
            rows.extend(
                (product.id, store, d, float(p), "synthetic") for d, p in zip(dates, prices)
            )
    return pd.DataFrame(rows, columns=["product_id", "store", "date", "price", "source"])
