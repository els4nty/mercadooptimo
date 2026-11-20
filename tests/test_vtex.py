from pathlib import Path

import pandas as pd
import pytest

from mercadooptimo.data.scrapers.jsonld import parse_products
from mercadooptimo.data.scrapers.vtex import ProductPageScraper, load_targets

FIX = Path(__file__).parent / "fixtures"


def read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_jumbo_listado():
    prods = parse_products(read("jumbo_listado.html"))
    assert len(prods) == 3
    first = prods[0]
    assert first.name == "Arroz Diana blanco x5kg"
    assert first.price == 16890 and first.currency == "COP" and first.in_stock is True


def test_olimpica_listado_aggregate_offer():
    first = parse_products(read("olimpica_listado.html"))[0]
    assert first.name == "Arroz Sabrosón 5 Kg"
    assert first.price == 20990 and first.currency == "COP"


@pytest.mark.parametrize("name,price", [("jumbo_producto.html", 16890), ("olimpica_producto.html", 20990)])
def test_pagina_de_producto(name, price):
    prods = parse_products(read(name))
    assert len(prods) == 1 and prods[0].price == price


def test_sin_json_ld():
    assert parse_products("<html><body>nada</body></html>") == []


class Resp:
    def __init__(self, status, body=""):
        self.status_code, self.text, self.content = status, body, body.encode()
        self.ok = 200 <= status < 400

    def raise_for_status(self):
        if not self.ok:
            raise AssertionError(self.status_code)


class Session:
    def __init__(self, pages):
        self.headers, self.pages = {}, pages

    def get(self, url, timeout=None):
        if url.endswith("/robots.txt"):
            return Resp(200, "User-agent: *\nDisallow: /busca*\n")
        return Resp(200, self.pages[url]) if url in self.pages else Resp(404)


def test_scrape_convierte_a_precio_por_unidad_del_catalogo():
    url = "https://www.jumbocolombia.com/arroz-diana-x-5-kg/p"
    targets = pd.DataFrame([{"store": "jumbo", "product_id": "arroz", "url": url, "units_per_pack": 5}])
    df = ProductPageScraper("jumbo", targets, session=Session({url: read("jumbo_producto.html")}), delay=0).scrape()
    assert df.iloc[0].to_dict()["price"] == pytest.approx(16890 / 5)
    assert df.iloc[0].store == "jumbo" and df.iloc[0].source == "scraping"


def test_scrape_no_descarga_rutas_bloqueadas():
    url = "https://www.jumbocolombia.com/busca/arroz"
    targets = pd.DataFrame([{"store": "jumbo", "product_id": "arroz", "url": url, "units_per_pack": 1}])
    df = ProductPageScraper("jumbo", targets, session=Session({url: "x"}), delay=0).scrape()
    assert df.empty


def test_load_targets_valida_catalogo(tmp_path):
    f = tmp_path / "t.csv"
    f.write_text("store,product_id,url,units_per_pack\njumbo,producto_raro,https://x/p,1\n")
    with pytest.raises(ValueError):
        load_targets(f)
    assert len(load_targets("config/targets.csv")) >= 2
