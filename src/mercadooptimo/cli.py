"""Línea de comandos de MercadoÓptimo.

Ejemplos:
    mercadooptimo seed-synthetic --db data/precios.db
    mercadooptimo evaluate-forecast --db data/precios.db
    mercadooptimo recommend --db data/precios.db --budget 120000 \
        --item res_molida=2 --item arroz=3 --item huevos=1
    mercadooptimo evaluate-savings --db data/precios.db --weeks 12
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from mercadooptimo.catalog import ALL_PRODUCTS, PRODUCTS_BY_ID
from mercadooptimo.data import db
from mercadooptimo.data.synthetic import generate_prices

DEFAULT_DB = "data/precios.db"
DEFAULT_BASKET = {"res_molida": 2, "pollo_pechuga": 1, "huevos": 1, "arroz": 2, "frijol": 1, "papa": 2,
                  "leche": 4, "aceite": 1, "tomate": 1, "cebolla": 1}


def _parse_items(items: list[str] | None, available: set[str] | None = None) -> dict[str, int]:
    if not items:
        basket = {k: v for k, v in DEFAULT_BASKET.items() if available is None or k in available}
        if not basket:
            sys.exit("La cesta por defecto no existe en estos datos. Indique productos con --item id=cantidad "
                     "(ids en `mercadooptimo products`).")
        return basket
    out = {}
    for it in items:
        pid, _, qty = it.partition("=")
        if pid not in PRODUCTS_BY_ID:
            sys.exit(f"Producto desconocido: {pid}. Use `mercadooptimo products`.")
        out[pid] = int(qty or 1)
    return out


def _wide(args) -> pd.DataFrame:
    conn = db.connect(args.db)
    df = db.load_prices(conn, source=args.source)
    if df.empty:
        sys.exit(f"No hay precios en {args.db}. Ejecute primero `mercadooptimo seed-synthetic`.")
    return db.to_wide(df)


def cmd_products(args):
    for p in ALL_PRODUCTS:
        print(f"{p.id:22s} {p.name[:44]:44s} {p.unit:8s} {p.category}")


def cmd_seed(args):
    conn = db.connect(args.db)
    n = db.save_prices(conn, generate_prices(weeks=args.weeks, seed=args.seed))
    print(f"{n} precios sintéticos guardados en {args.db}")


def cmd_load_sipsa(args):
    from mercadooptimo.data.sipsa import load_sipsa_file

    conn = db.connect(args.db)
    n = db.save_prices(conn, load_sipsa_file(args.file))
    print(f"{n} precios SIPSA guardados en {args.db}")


def cmd_check_robots(args):
    from mercadooptimo.data.scrapers.robots_check import run

    run(args.out)


def cmd_discover(args):
    from mercadooptimo.data import discover

    jumbo = [discover.read_listing(f, "jumbo") for f in discover.expand(args.jumbo)]
    olimpica = [discover.read_listing(f, "olimpica") for f in discover.expand(args.olimpica)]
    d = discover.build(jumbo, olimpica)
    print("\n".join(d.notes))
    print(f"\n{len(d.catalog)} productos idénticos en ambas tiendas:")
    for r in d.catalog:
        print(f"  {r['ean']}  {r['name'][:52]:52s} {r['unit']:8s} {r['category']}")
    if args.write:
        cat, tgt = discover.write(d, args.out_dir)
        print(f"\nEscrito: {cat} y {tgt}")
    else:
        print("\n(Vista previa. Agregue --write para guardar config/catalog.csv y config/targets.csv)")


def cmd_scrape(args):
    from mercadooptimo.data.scrapers.vtex import ProductPageScraper, load_targets

    targets = load_targets(args.targets)
    stores = args.stores or sorted(targets.store.unique())
    frames = [ProductPageScraper(s, targets, delay=args.delay).scrape() for s in stores]
    df = pd.concat(frames, ignore_index=True)
    print(df.to_string(index=False) if not df.empty else "No se obtuvo ningún precio.")
    if args.dry_run or df.empty:
        return
    n = db.save_prices(db.connect(args.db), df)
    print(f"{n} precios guardados en {args.db}")
    if args.csv:
        added = db.append_csv(df, args.csv)
        print(f"{added} filas nuevas en {args.csv}")


def cmd_import_csv(args):
    n = db.save_prices(db.connect(args.db), db.read_csv(args.file))
    print(f"{n} precios de {args.file} guardados en {args.db}")


def cmd_eval_forecast(args):
    from mercadooptimo.forecasting.evaluation import compare_models, summarize

    wide = _wide(args)
    if args.products:
        wide = wide.loc[:, wide.columns.get_level_values(0).isin(args.products)]
    res = compare_models(wide, models=args.models, test_frac=args.test_frac)
    pd.set_option("display.width", 120)
    print(summarize(res).round(3).to_string())
    if args.out:
        res.to_csv(args.out, index=False)
        print(f"Detalle por serie en {args.out}")


def cmd_recommend(args):
    from mercadooptimo.pipeline import recommend

    wide = _wide(args)
    demands = _parse_items(args.item, set(wide.columns.get_level_values(0)))
    result, _, summary = recommend(wide, demands, args.budget, model=args.model,
                                   max_stores=args.max_stores, reference_store=args.reference_store)
    print(f"Estado: {result.status}  (modelo {result.model}, {result.solve_seconds:.3f} s)")
    plan = result.plan.assign(producto=result.plan.product_id.map(lambda i: PRODUCTS_BY_ID[i].name))
    print(plan[["store", "producto", "quantity", "unit_price", "subtotal"]].round(0).to_string(index=False))
    print(f"\nCosto esperado: ${result.total_cost:,.0f} de ${args.budget:,.0f}")
    if result.uncovered:
        print("No alcanza el presupuesto para:", ", ".join(result.uncovered))
    print(f"Ahorro estimado vs. {summary['tienda_referencia']}: ${summary['ahorro']:,.0f} "
          f"({summary['ahorro_pct']:.1f} %)")


def cmd_eval_savings(args):
    from mercadooptimo.evaluation.savings import backtest_savings

    bt = backtest_savings(_wide(args), _parse_items(args.item), weeks=args.weeks, model=args.model,
                          reference_store=args.reference_store, max_stores=args.max_stores)
    cols = ["ahorro_vs_A_%", "ahorro_vs_B_%", "brecha_oraculo_%", "segundos_optimizador"]
    print(bt[["date"] + cols].round(3).to_string(index=False))
    print("\nPromedio:")
    print(bt[cols].mean().round(3).to_string())
    if args.out:
        bt.to_csv(args.out, index=False)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mercadooptimo")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--source", default=None, help="filtrar por fuente (synthetic, sipsa, scraping)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("products").set_defaults(func=cmd_products)

    s = sub.add_parser("seed-synthetic", help="genera precios sintéticos de desarrollo")
    s.add_argument("--weeks", type=int, default=156)
    s.add_argument("--seed", type=int, default=42)
    s.set_defaults(func=cmd_seed)

    s = sub.add_parser("load-sipsa", help="importa un archivo SIPSA descargado del DANE")
    s.add_argument("file")
    s.set_defaults(func=cmd_load_sipsa)

    s = sub.add_parser("check-robots", help="revisa el robots.txt de las cadenas candidatas")
    s.add_argument("--out", help="guarda el reporte en un archivo .md")
    s.set_defaults(func=cmd_check_robots)

    s = sub.add_parser("discover", help="cruza por EAN los productos de Jumbo y Olímpica a partir de HTML guardados")
    s.add_argument("--jumbo", nargs="+", required=True, help="HTML de categorías de Jumbo (admite comodines)")
    s.add_argument("--olimpica", nargs="+", required=True, help="HTML de listados de Olímpica (admite comodines)")
    s.add_argument("--out-dir", default="config")
    s.add_argument("--write", action="store_true", help="guarda catalog.csv y targets.csv")
    s.set_defaults(func=cmd_discover)

    s = sub.add_parser("scrape", help="descarga precios de las páginas de producto de config/targets.csv")
    s.add_argument("--targets", default="config/targets.csv")
    s.add_argument("--stores", nargs="*", help="jumbo olimpica (por defecto, todas las del archivo)")
    s.add_argument("--delay", type=float, default=3.0, help="segundos entre peticiones")
    s.add_argument("--dry-run", action="store_true", help="muestra los precios sin guardarlos")
    s.add_argument("--csv", help="además, agrega los precios a este CSV de historial (p. ej. data/history/precios.csv)")
    s.set_defaults(func=cmd_scrape)

    s = sub.add_parser("import-csv", help="carga un CSV de historial (product_id,store,date,price,source) a la base")
    s.add_argument("file", nargs="?", default="data/history/precios.csv")
    s.set_defaults(func=cmd_import_csv)

    s = sub.add_parser("evaluate-forecast", help="RMSE/MAPE de los modelos con partición temporal")
    s.add_argument("--models", nargs="+", default=["naive", "seasonal_naive", "arima"],
                   help="naive, seasonal_naive, arima, lstm (lstm requiere PyTorch)")
    s.add_argument("--products", nargs="*")
    s.add_argument("--test-frac", type=float, default=0.15)
    s.add_argument("--out")
    s.set_defaults(func=cmd_eval_forecast)

    for name, func, help_ in [("recommend", cmd_recommend, "recomienda la compra"),
                              ("evaluate-savings", cmd_eval_savings, "backtest del ahorro vs. líneas base")]:
        s = sub.add_parser(name, help=help_)
        s.add_argument("--item", action="append", help="producto=cantidad (repetible)")
        s.add_argument("--model", default="arima")
        s.add_argument("--max-stores", type=int)
        s.add_argument("--reference-store")
        s.set_defaults(func=func)
    sub.choices["recommend"].add_argument("--budget", type=float, required=True)
    sub.choices["evaluate-savings"].add_argument("--weeks", type=int, default=12)
    sub.choices["evaluate-savings"].add_argument("--out")

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
