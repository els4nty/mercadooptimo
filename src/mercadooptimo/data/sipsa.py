"""Carga de precios mayoristas del SIPSA (DANE).

El SIPSA publica boletines diarios, semanales y mensuales (en Excel) con series
desde 2013, incluidos los grupos Carnes y Pescados. Este módulo NO descarga
los archivos: se descargan manualmente desde el portal del DANE a `data/raw/`
y aquí se normalizan al esquema de la base de datos.

Como el formato de los anexos puede cambiar entre años, el mapeo de columnas
y de productos es configurable. Verificar la cobertura de cada producto en los
archivos antes de entrenar (ver informe, sección 6.3).
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd

# Mapeo nombre SIPSA (normalizado) -> product_id del catálogo. Ajustar según
# los nombres exactos que aparezcan en los anexos descargados.
DEFAULT_PRODUCT_MAP = {
    "carne de res molida": "res_molida",
    "lomo de res": "res_lomo",
    "chuleta de cerdo": "cerdo_chuleta",
    "pechuga de pollo": "pollo_pechuga",
    "pollo entero": "pollo_entero",
    "filete de tilapia": "tilapia",
    "arroz de primera": "arroz",
    "frijol cargamanto": "frijol",
    "lenteja": "lenteja",
    "papa pastusa": "papa",
    "platano harton": "platano",
    "tomate chonto": "tomate",
    "cebolla cabezona": "cebolla",
}

DEFAULT_COLUMNS = {"fecha": "date", "producto": "product", "mercado": "store", "precio": "price"}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def normalize_sipsa(
    raw: pd.DataFrame,
    columns: dict[str, str] | None = None,
    product_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Convierte una tabla SIPSA ya leída a las columnas del esquema `prices`.

    `columns` mapea nombres de columna del archivo (normalizados) a
    date/product/store/price. Los productos sin mapeo se descartan.
    """
    columns = columns or DEFAULT_COLUMNS
    product_map = product_map or DEFAULT_PRODUCT_MAP
    df = raw.rename(columns={c: _norm(c) for c in raw.columns})
    df = df.rename(columns=columns)
    missing = {"date", "product", "store", "price"} - set(df.columns)
    if missing:
        raise ValueError(f"No se encontraron columnas {sorted(missing)}; ajuste `columns`.")
    df["product_id"] = df["product"].map(lambda x: product_map.get(_norm(x)))
    df = df.dropna(subset=["product_id", "price"])
    out = pd.DataFrame(
        {
            "product_id": df["product_id"],
            "store": "sipsa_" + df["store"].map(_norm).str.replace(" ", "_"),
            "date": pd.to_datetime(df["date"], dayfirst=True, errors="coerce"),
            "price": pd.to_numeric(df["price"], errors="coerce"),
            "source": "sipsa",
        }
    )
    return out.dropna(subset=["date", "price"])


def load_sipsa_file(path: str | Path, sheet_name=0, header: int = 0, **kwargs) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".xls", ".xlsx"}:
        raw = pd.read_excel(path, sheet_name=sheet_name, header=header)
    else:
        raw = pd.read_csv(path, header=header)
    return normalize_sipsa(raw, **kwargs)
