"""Casos tomados de los robots.txt reales de Éxito, Olímpica y D1 (noviembre 2026, resumidos)."""

import pytest

from mercadooptimo.data.scrapers.robots import RobotsPolicy

UA = "MercadoOptimoBot/0.1 (proyecto academico)"

EXITO = """User-agent: *
Content-Signal: search=yes, ai-train=no
Allow: /

User-agent: Applebot-Extended
Allow: /

# Áreas privadas
Disallow: /account/
Disallow: /checkout/
Disallow: /s?
Disallow: /*?*facets=
Disallow: /*?*sort=
Allow: /*?page=
Disallow: /api/
Disallow: /coleccion/
"""

OLIMPICA = """User-agent: *
Disallow: /secret
Disallow: /*?orderFormId=
Allow: /*.css

User-agent: *
Disallow: /*&
Disallow: /*%

User-agent: Googlebot
Disallow: /busca/*
Disallow: /account/*
"""

D1 = """User-agent: *

# comentario tras una línea en blanco
Allow: /*.css$
Disallow: /account/*
Disallow: /busca/*
Disallow: *OrderBy=
Disallow: *map=
"""


def ok(text, url):
    return RobotsPolicy(text, UA).can_fetch(url)


@pytest.mark.parametrize("url,expected", [
    ("https://www.exito.com/arroz-1kg-123/p", True),
    ("https://www.exito.com/mercado/despensa?page=2", True),
    ("https://www.exito.com/api/catalog_system/pub/products/search", False),  # Disallow bajo otro grupo
    ("https://www.exito.com/s?q=arroz", False),
    ("https://www.exito.com/mercado?sort=price", False),
    ("https://www.exito.com/coleccion/ofertas", False),
])
def test_exito(url, expected):
    assert ok(EXITO, url) is expected


@pytest.mark.parametrize("url,expected", [
    ("https://www.olimpica.com/arroz-1kg/p", True),
    ("https://www.olimpica.com/x?a=1&b=2", False),  # comodín /*&
    ("https://www.olimpica.com/x?orderFormId=1", False),
    ("https://www.olimpica.com/busca/arroz", False),  # regla de Googlebot, política conservadora
])
def test_olimpica(url, expected):
    assert ok(OLIMPICA, url) is expected


@pytest.mark.parametrize("url,expected", [
    ("https://domicilios.tiendasd1.com/arroz-1kg/p", True),
    ("https://domicilios.tiendasd1.com/busca/arroz", False),
    ("https://domicilios.tiendasd1.com/x?OrderBy=price", False),  # comodín al inicio
    ("https://domicilios.tiendasd1.com/account/a", False),
])
def test_d1(url, expected):
    assert ok(D1, url) is expected


def test_deny_and_allow_all():
    assert not RobotsPolicy.deny_all(UA).can_fetch("https://t.co/p")
    assert RobotsPolicy.allow_all(UA).can_fetch("https://t.co/p")
