"""Extracción de productos y precios desde bloques JSON-LD (schema.org).

Los portales VTEX de Jumbo y Olímpica publican, en el HTML, un bloque
`<script type="application/ld+json">` con `Product` (página de producto) o
`ItemList` de `Product` (listados). Es más estable que un selector CSS.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_LD_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I)


@dataclass(frozen=True)
class ProductInfo:
    name: str
    sku: str | None
    url: str | None
    price: float | None
    currency: str | None
    in_stock: bool | None
    ean: str | None = None
    brand: str | None = None


def _walk(node):
    """Recorre el JSON-LD y entrega cada objeto con @type == Product."""
    if isinstance(node, list):
        for x in node:
            yield from _walk(x)
    elif isinstance(node, dict):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if "Product" in types:
            yield node
        for key in ("@graph", "itemListElement", "item"):
            if key in node:
                yield from _walk(node[key])


def _price(offers) -> tuple[float | None, str | None, bool | None]:
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        return None, None, None
    price = offers.get("price", offers.get("lowPrice"))
    if price is None and offers.get("offers"):
        return _price(offers["offers"])
    try:
        price = float(price) if price is not None else None
    except (TypeError, ValueError):
        price = None
    avail = offers.get("availability")
    in_stock = None if avail is None else str(avail).rstrip("/").endswith("InStock")
    return price, offers.get("priceCurrency"), in_stock


_EAN_IMG = re.compile(r"/(\d{8,14})(?:-\d+)?\.(?:jpe?g|png|webp)")


def _ean_from_image(image) -> str | None:
    """Algunas imágenes de VTEX se llaman <EAN>.jpg; sirve cuando el JSON-LD no trae gtin."""
    if isinstance(image, list):
        image = image[0] if image else None
    m = _EAN_IMG.search(image or "")
    return m.group(1) if m else None


def parse_products(html: str) -> list[ProductInfo]:
    out: list[ProductInfo] = []
    for block in _LD_RE.findall(html):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for p in _walk(data):
            price, cur, stock = _price(p.get("offers"))
            brand = p.get("brand")
            brand = brand.get("name") if isinstance(brand, dict) else brand
            ean = p.get("gtin13") or p.get("gtin") or _ean_from_image(p.get("image"))
            out.append(ProductInfo(p.get("name", ""), p.get("sku"), p.get("url") or p.get("@id"), price, cur, stock, ean, brand))
    return out
