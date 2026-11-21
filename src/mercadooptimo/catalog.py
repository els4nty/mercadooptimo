"""Catálogo acotado del alcance: proteínas (carnes y pescados) y canasta básica.

Los identificadores se usan como llave en la base de datos. Las tiendas son
nombres genéricos hasta que se definan las cadenas reales a recolectar.
"""

import csv
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    unit: str
    category: str  # "proteina" | "canasta"
    base_price: float = 0.0  # precio de referencia en COP, usado solo por el generador sintético
    ean: str | None = None  # código de barras: identifica el mismo producto físico en todas las tiendas


PRODUCTS: list[Product] = [
    Product("res_molida", "Carne de res molida", "500 g", "proteina", 14500),
    Product("res_lomo", "Lomo de res", "500 g", "proteina", 22000),
    Product("cerdo_chuleta", "Chuleta de cerdo", "500 g", "proteina", 12500),
    Product("pollo_pechuga", "Pechuga de pollo", "1 kg", "proteina", 18000),
    Product("pollo_entero", "Pollo entero", "1 kg", "proteina", 11500),
    Product("tilapia", "Filete de tilapia", "500 g", "proteina", 13000),
    Product("huevos", "Huevos AA x30", "30 und", "proteina", 17500),
    Product("arroz", "Arroz blanco", "1 kg", "canasta", 4800),
    Product("frijol", "Fríjol cargamanto", "500 g", "canasta", 6900),
    Product("lenteja", "Lenteja", "500 g", "canasta", 3900),
    Product("papa", "Papa pastusa", "1 kg", "canasta", 3200),
    Product("platano", "Plátano hartón", "1 kg", "canasta", 3600),
    Product("leche", "Leche entera", "1 L", "canasta", 4300),
    Product("aceite", "Aceite vegetal", "1 L", "canasta", 9800),
    Product("tomate", "Tomate chonto", "1 kg", "canasta", 4500),
    Product("cebolla", "Cebolla cabezona", "1 kg", "canasta", 3800),
]

STORES: list[str] = ["tienda_a", "tienda_b", "tienda_c", "tienda_d"]

# Catálogo de productos concretos (marca + presentación), uno por código de barras (EAN).
# Lo genera `mercadooptimo discover` a partir de las páginas de las cadenas y vive en
# config/catalog.csv. Los PRODUCTS genéricos de arriba solo alimentan el generador sintético.
CATALOG_CSV = Path(os.environ.get("MERCADOOPTIMO_CATALOG", Path(__file__).resolve().parents[2] / "config" / "catalog.csv"))


def load_catalog(path: str | Path = CATALOG_CSV) -> list[Product]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return [Product(id=r["product_id"], name=r["name"], unit=r["unit"], category=r["category"], ean=r["ean"] or None)
                for r in csv.DictReader(fh)]


REAL_PRODUCTS: list[Product] = load_catalog()
ALL_PRODUCTS: list[Product] = PRODUCTS + REAL_PRODUCTS
PRODUCTS_BY_ID = {p.id: p for p in ALL_PRODUCTS}
