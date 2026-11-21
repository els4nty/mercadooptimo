from pathlib import Path

import pytest

from mercadooptimo.catalog import load_catalog
from mercadooptimo.data import discover
from mercadooptimo.data.scrapers.vtex import load_targets

FIX = Path(__file__).parent / "fixtures"
CAT = '<link rel="canonical" href="https://www.jumbocolombia.com/co/supermercado/despensa/pastas?gclid=abc&amp;x=1"/>'
SEARCH = '<link rel="canonical" href="https://www.jumbocolombia.com/search?query=arroz&amp;type=term"/>'


@pytest.fixture()
def files(tmp_path):
    jumbo = (FIX / "jumbo_estado.html").read_text(encoding="utf-8")
    olimpica = (FIX / "olimpica_estado.html").read_text(encoding="utf-8")
    paths = {}
    for name, body in {"j_cat": CAT + jumbo, "j_search": SEARCH + jumbo, "j_home": jumbo, "o": olimpica}.items():
        paths[name] = tmp_path / f"{name}.html"
        paths[name].write_text(body, encoding="utf-8")
    return paths


def test_cruce_por_ean_y_urls_limpias(files):
    d = discover.build([discover.read_listing(files["j_cat"], "jumbo")], [discover.read_listing(files["o"], "olimpica")])
    assert [r["ean"] for r in d.catalog] == ["7702085019023"]
    row = d.catalog[0]
    assert row["product_id"] == "ean_7702085019023" and row["unit"] == "1000 g" and row["category"] == "canasta"
    jumbo, olimpica = d.targets
    assert jumbo["url"] == "https://www.jumbocolombia.com/co/supermercado/despensa/pastas"  # sin gclid ni parámetros
    assert jumbo["sku"] and jumbo["units_per_pack"] == 1
    assert olimpica["url"].startswith("https://www.olimpica.com/") and olimpica["url"].endswith("/p") and olimpica["sku"] == ""


@pytest.mark.parametrize("key", ["j_search", "j_home"])
def test_descarta_busquedas_y_portada_de_jumbo(files, key):
    d = discover.build([discover.read_listing(files[key], "jumbo")], [discover.read_listing(files["o"], "olimpica")])
    assert d.catalog == [] and any("se descarta" in n for n in d.notes)


def test_write_y_lectura_de_vuelta(files, tmp_path, monkeypatch):
    d = discover.build([discover.read_listing(files["j_cat"], "jumbo")], [discover.read_listing(files["o"], "olimpica")])
    cat, tgt = discover.write(d, tmp_path / "cfg")
    products = load_catalog(cat)
    assert products[0].id == "ean_7702085019023" and products[0].ean == "7702085019023"
    import mercadooptimo.data.scrapers.vtex as vtex

    monkeypatch.setitem(vtex.PRODUCTS_BY_ID, products[0].id, products[0])
    assert len(load_targets(tgt)) == 2


def test_expand_avisa_si_falta_un_archivo():
    with pytest.raises(SystemExit):
        discover.expand(["no_existe.html"])
    assert discover.expand(["tests/fixtures/zzz*.html"]) == []


def test_config_real_es_consistente():
    products = {p.id for p in load_catalog("config/catalog.csv")}
    targets = load_targets("config/targets.csv")
    assert products and set(targets.product_id) <= products
    assert targets.groupby("product_id").store.nunique().eq(2).all()  # cada producto está en las dos tiendas
