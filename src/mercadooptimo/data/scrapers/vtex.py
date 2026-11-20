"""Scraper de páginas de producto para tiendas VTEX (Jumbo, Olímpica) vía JSON-LD.

Solo se descargan las URLs de producto listadas en `config/targets.csv` (nunca
buscadores ni categorías, que los robots.txt piden no rastrear). Cada fila indica
cuántas unidades del catálogo trae el empaque (`units_per_pack`), de modo que el
precio guardado es siempre por unidad del catálogo (p. ej. COP por kg de arroz).

Columnas de targets.csv: store, product_id, url, units_per_pack
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import requests

from mercadooptimo.catalog import PRODUCTS_BY_ID
from mercadooptimo.data.scrapers.base import StoreScraper
from mercadooptimo.data.scrapers.jsonld import parse_products

DEFAULT_TARGETS = "config/targets.csv"


def load_targets(path: str | Path = DEFAULT_TARGETS) -> pd.DataFrame:
    df = pd.read_csv(path, comment="#", skipinitialspace=True)
    missing = {"store", "product_id", "url", "units_per_pack"} - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en {path}: {sorted(missing)}")
    unknown = set(df.product_id) - set(PRODUCTS_BY_ID)
    if unknown:
        raise ValueError(f"product_id fuera del catálogo: {sorted(unknown)}")
    if (df.units_per_pack <= 0).any():
        raise ValueError("units_per_pack debe ser > 0")
    return df


class ProductPageScraper(StoreScraper):
    def __init__(self, store: str, targets: pd.DataFrame, **kwargs):
        super().__init__(**kwargs)
        self.store = store
        self.targets = targets[targets.store == store]

    def scrape(self) -> pd.DataFrame:
        today = date.today().isoformat()
        rows = []
        for t in self.targets.itertuples():
            try:
                html = self.fetch_html(t.url)
            except (requests.RequestException, PermissionError) as exc:
                print(f"[{self.store}] {t.product_id}: {exc}")
                continue
            products = parse_products(html)
            info = products[0] if products else None
            if not info or not info.price:
                print(f"[{self.store}] {t.product_id}: sin precio en JSON-LD ({t.url})")
                continue
            if info.in_stock is False:
                print(f"[{self.store}] {t.product_id}: agotado, se omite")
                continue
            if info.currency not in (None, "COP"):
                print(f"[{self.store}] {t.product_id}: moneda inesperada {info.currency}")
                continue
            rows.append((t.product_id, self.store, today, round(info.price / t.units_per_pack, 2), "scraping"))
        return pd.DataFrame(rows, columns=["product_id", "store", "date", "price", "source"])
