"""Extracción de productos desde el estado de hidratación de VTEX IO (`__STATE__`).

Las páginas de Olímpica sin bloque JSON-LD (categorías y búsquedas) guardan los
productos en un `<template data-varname="__STATE__">` con una caché tipo Apollo:
cada `Product:*` (o `SearchProduct:*`, en Jumbo) apunta a sus variantes (`items`), y estas a su vendedor y su oferta
comercial, donde están el código de barras (`ean`) y el precio.
"""

from __future__ import annotations

import json
import re

from mercadooptimo.data.scrapers.jsonld import ProductInfo

_STATE_RE = re.compile(r'data-varname="__STATE__"[^>]*>\s*<script[^>]*>(.*?)</script>', re.S)


# Olímpica usa `Product:*`; Jumbo usa `SearchProduct:*` en listados y búsquedas.
_PRODUCT_KEY = re.compile(r"(?:Search)?Product:[^.]+")


def _deref(state: dict, node):
    """Resuelve una referencia {"type": "id", "id": ...} al objeto de la caché."""
    if isinstance(node, dict) and node.get("type") == "id":
        return state.get(node["id"], {})
    return node if isinstance(node, dict) else {}


def _items_key(product: dict) -> list:
    for key, value in product.items():
        if key.startswith("items(") and isinstance(value, list):
            return value
    return []


def parse_state_products(html: str) -> list[ProductInfo]:
    m = _STATE_RE.search(html)
    if not m:
        return []
    try:
        state = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    out: list[ProductInfo] = []
    for key, product in state.items():
        if not (_PRODUCT_KEY.fullmatch(key) and isinstance(product, dict) and "productName" in product):
            continue
        for ref in _items_key(product)[:1]:  # la primera variante es la que se muestra
            item = _deref(state, ref)
            sellers = item.get("sellers") or []
            seller = _deref(state, sellers[0]) if sellers else {}
            offer = _deref(state, seller.get("commertialOffer"))
            price = offer.get("Price")
            qty = offer.get("AvailableQuantity")
            out.append(ProductInfo(
                name=product["productName"],
                sku=item.get("itemId") or product.get("productReference"),
                url=product.get("link", "").replace("\\u002F", "/") or None,
                price=float(price) if price else None,
                currency="COP",
                in_stock=None if qty is None else qty > 0,
                ean=item.get("ean") or None,
                brand=product.get("brand"),
            ))
    return out
