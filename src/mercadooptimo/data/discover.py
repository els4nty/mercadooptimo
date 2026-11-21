"""Descubre los productos idénticos entre Jumbo y Olímpica cruzando por código de barras (EAN).

Entrada: páginas de categoría/listado guardadas desde el navegador (HTML).
Salida: `config/catalog.csv` (un producto por EAN) y `config/targets.csv` (dónde leer el
precio de cada producto en cada tienda).

Solo se aceptan, del lado de Jumbo, páginas de categoría (`/co/supermercado/...`); los
resultados de búsqueda (`/search`, `/busca`) y la portada se descartan, porque el scraper
diario nunca debe depender de ellos. Del lado de Olímpica solo importa de cada listado el
producto y su dirección: el scraper lee después la página del producto.
"""

from __future__ import annotations

import csv
import glob
import html as htmllib
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

from mercadooptimo.data.scrapers.jsonld import ProductInfo, parse_products
from mercadooptimo.data.scrapers.vtex_state import parse_state_products

BASES = {"jumbo": "https://www.jumbocolombia.com", "olimpica": "https://www.olimpica.com"}
_CANONICAL = re.compile(r'<link[^>]*rel="canonical"[^>]*href="([^"]+)"', re.I)
_BLOCKED_PATHS = ("/search", "/busca", "/buscapagina", "/checkout", "/account", "/login", "/cart")
_PROTEIN = ("atún", "atun", "huevo", "pollo", "res ", "cerdo", "pescado", "salchicha", "jamón", "jamon",
            "tilapia", "carne", "chorizo", "mortadela", "salmón", "salmon")
_SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|kgs|g|gr|grs|gramos|lt|l|litros?|ml|und|unds|un)\b", re.I)


@dataclass
class Listing:
    path: str
    store: str
    canonical: str | None
    products: list[ProductInfo]

    @property
    def is_category(self) -> bool:
        if not self.canonical:
            return False
        path = urlparse(self.canonical).path
        return bool(path.strip("/")) and not any(path.startswith(b) for b in _BLOCKED_PATHS)


@dataclass
class Discovery:
    catalog: list[dict] = field(default_factory=list)
    targets: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def clean_url(url: str) -> str:
    url = htmllib.unescape(url)
    if url.startswith("//"):
        url = "https:" + url
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")


def read_listing(path: str | Path, store: str) -> Listing:
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    m = _CANONICAL.search(html)
    products = parse_state_products(html) or parse_products(html)
    return Listing(str(path), store, clean_url(m.group(1)) if m else None, products)


def _unit(name: str) -> str:
    m = _SIZE.search(name)
    if not m:
        return "und"
    qty, unit = m.group(1).replace(",", "."), m.group(2).lower()
    unit = {"kgs": "kg", "gr": "g", "grs": "g", "gramos": "g", "lt": "L", "l": "L", "litro": "L", "litros": "L",
            "unds": "und", "un": "und"}.get(unit, unit)
    return f"{qty.rstrip('0').rstrip('.') if '.' in qty else qty} {unit}"


def _category(name: str) -> str:
    n = name.lower() + " "
    return "proteina" if any(k in n for k in _PROTEIN) else "canasta"


def _tidy(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().rstrip(".")


def _usable(p: ProductInfo) -> bool:
    return bool(p.ean and p.price and p.in_stock is not False and len(p.ean) >= 12)


def build(jumbo: list[Listing], olimpica: list[Listing]) -> Discovery:
    out = Discovery()
    jumbo_by_ean: dict[str, tuple[ProductInfo, str]] = {}
    ok_listings = []
    for lst in jumbo:
        if lst.is_category:
            ok_listings.append(lst)
        else:
            out.notes.append(f"Jumbo: se descarta {Path(lst.path).name} (no es una categoría: {lst.canonical or 'sin canonical'})")
    # Las categorías más específicas primero: listan menos productos y es más difícil que un SKU salga de la página.
    for lst in sorted(ok_listings, key=lambda l: -len(urlparse(l.canonical).path)):
        for p in filter(_usable, lst.products):
            jumbo_by_ean.setdefault(p.ean, (p, lst.canonical))

    olimpica_by_ean: dict[str, ProductInfo] = {}
    for lst in olimpica:
        for p in filter(_usable, lst.products):
            if p.url:
                olimpica_by_ean.setdefault(p.ean, p)

    out.notes.append(f"Jumbo: {len(jumbo_by_ean)} productos con EAN y precio | Olímpica: {len(olimpica_by_ean)}")
    for ean in sorted(set(jumbo_by_ean) & set(olimpica_by_ean), key=lambda e: jumbo_by_ean[e][0].name):
        jp, category_url = jumbo_by_ean[ean]
        op = olimpica_by_ean[ean]
        pid, name = f"ean_{ean}", _tidy(jp.name)
        out.catalog.append(dict(product_id=pid, ean=ean, name=name, unit=_unit(name), category=_category(name)))
        out.targets.append(dict(store="jumbo", product_id=pid, url=category_url, units_per_pack=1, sku=jp.sku))
        out.targets.append(dict(store="olimpica", product_id=pid, url=urljoin(BASES["olimpica"], op.url), units_per_pack=1, sku=""))
    return out


def expand(patterns: list[str]) -> list[str]:
    """Expande comodines (PowerShell no lo hace) y falla con un mensaje claro si falta un archivo."""
    files: list[str] = []
    for pat in patterns:
        found = sorted(glob.glob(pat))
        if not found and not any(ch in pat for ch in "*?["):
            raise SystemExit(f"No existe el archivo: {pat}")
        files += found
    return files


def write(d: Discovery, out_dir: str | Path = "config") -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cat, tgt = out_dir / "catalog.csv", out_dir / "targets.csv"
    with cat.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, ["product_id", "ean", "name", "unit", "category"])
        w.writeheader()
        w.writerows(d.catalog)
    with tgt.open("w", encoding="utf-8", newline="") as fh:
        fh.write("# Generado por `mercadooptimo discover`. Puede editarse a mano.\n"
                 "# Jumbo: url = categoría (sin parámetros) y sku = producto dentro del listado.\n"
                 "# Olímpica: url = página del producto (/nombre/p) y sku vacío.\n"
                 "# Cada producto es un EAN concreto (misma marca y presentación en ambas tiendas): units_per_pack = 1.\n")
        w = csv.DictWriter(fh, ["store", "product_id", "url", "units_per_pack", "sku"])
        w.writeheader()
        w.writerows(d.targets)
    return cat, tgt
