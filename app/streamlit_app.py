"""Interfaz de MercadoÓptimo: presupuesto + productos -> lista recomendada.

Ejecutar:  streamlit run app/streamlit_app.py
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from mercadooptimo.catalog import PRODUCTS, PRODUCTS_BY_ID
from mercadooptimo.data import db
from mercadooptimo.data.synthetic import generate_prices
from mercadooptimo.pipeline import recommend

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "precios.db"

st.set_page_config(page_title="MercadoÓptimo", page_icon="🛒", layout="wide")
st.title("🛒 MercadoÓptimo")
st.caption("Recomendación de compra de menor costo esperado dentro de su presupuesto.")


@st.cache_data(show_spinner=False)
def load_wide(path: str) -> pd.DataFrame:
    conn = db.connect(path)
    df = db.load_prices(conn)
    if df.empty:
        db.save_prices(conn, generate_prices())
        df = db.load_prices(conn)
    return db.to_wide(df)


wide = load_wide(str(DB_PATH))
sources = "sintéticos (desarrollo)" if "synthetic" in str(db.load_prices(db.connect(DB_PATH)).source.unique()) else "reales"
st.sidebar.info(f"Datos: precios {sources} · {len(wide)} semanas · última: {wide.index[-1]:%Y-%m-%d}")

with st.sidebar:
    st.header("Parámetros")
    budget = st.number_input("Presupuesto (COP)", min_value=0, value=150_000, step=5_000)
    model = st.selectbox("Modelo de predicción", ["arima", "naive", "seasonal_naive"])
    limit = st.checkbox("Limitar número de tiendas")
    max_stores = st.slider("Máximo de tiendas", 1, 4, 2) if limit else None

st.subheader("1. Productos y cantidades")
default = {"res_molida": 2, "pollo_pechuga": 1, "huevos": 1, "arroz": 2, "papa": 2, "leche": 4}
editor = pd.DataFrame(
    [{"producto": p.name, "unidad": p.unit, "cantidad": default.get(p.id, 0), "prioridad": 1.0, "id": p.id}
     for p in PRODUCTS]
)
edited = st.data_editor(
    editor, hide_index=True, width="stretch", disabled=["producto", "unidad"],
    column_config={"id": None, "cantidad": st.column_config.NumberColumn(min_value=0, step=1),
                   "prioridad": st.column_config.NumberColumn(min_value=0.0, step=0.5,
                                                              help="Se usa si el presupuesto no alcanza")},
)
demands = {r.id: int(r.cantidad) for r in edited.itertuples() if r.cantidad > 0}
priorities = {r.id: float(r.prioridad) for r in edited.itertuples() if r.cantidad > 0}

if st.button("Calcular recomendación", type="primary", disabled=not demands):
    with st.spinner("Prediciendo precios y optimizando…"):
        result, expected, summary = recommend(wide, demands, budget, model=model,
                                              priorities=priorities, max_stores=max_stores)
    st.subheader("2. Lista recomendada")
    if result.status == "infeasible":
        st.error("No se encontró una compra factible con este presupuesto.")
    else:
        if result.uncovered:
            st.warning("El presupuesto no alcanza para todo. Se omitieron: "
                       + ", ".join(PRODUCTS_BY_ID[i].name for i in result.uncovered))
        c1, c2, c3 = st.columns(3)
        c1.metric("Costo esperado", f"${result.total_cost:,.0f}", f"de ${budget:,.0f}", delta_color="off")
        c2.metric("Ahorro estimado", f"${summary['ahorro']:,.0f}", f"{summary['ahorro_pct']:.1f} %")
        c3.metric("Tiendas", len(result.stores_used))
        st.caption(f"Ahorro frente a comprar todo en {summary['tienda_referencia']} (línea base A).")
        for store, grp in result.plan.groupby("store"):
            st.markdown(f"**{store}** — ${grp.subtotal.sum():,.0f}")
            st.dataframe(
                grp.assign(producto=grp.product_id.map(lambda i: PRODUCTS_BY_ID[i].name))[
                    ["producto", "quantity", "unit_price", "subtotal"]
                ].rename(columns={"quantity": "cantidad", "unit_price": "precio esperado"}),
                hide_index=True, width="stretch",
            )
        with st.expander("Precios esperados por tienda"):
            table = expected.pivot(index="product_id", columns="store", values="price").round(0)
            table.index = table.index.map(lambda i: PRODUCTS_BY_ID[i].name)
            st.dataframe(table, width="stretch")

st.subheader("Histórico de precios")
pid = st.selectbox("Producto", [p.id for p in PRODUCTS], format_func=lambda i: PRODUCTS_BY_ID[i].name)
st.line_chart(wide[pid])
