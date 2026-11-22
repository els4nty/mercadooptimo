"""Interfaz de MercadoÓptimo.

Pestañas, en el orden de la cadena de IA del informe:
  1. Recomendación   presupuesto + productos -> lista de compra óptima
  2. Predicción      entrenamiento y evaluación de los modelos (ingenuo, ARIMA, LSTM)
  3. Ahorro          backtest del ahorro frente a las líneas base A y B
  4. Cómo funciona   arquitectura, modelo matemático y fuentes de datos

Ejecutar:  streamlit run app/streamlit_app.py
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from mercadooptimo.catalog import PRODUCTS_BY_ID, REAL_PRODUCTS
from mercadooptimo.data import db
from mercadooptimo.data.synthetic import generate_prices
from mercadooptimo.forecasting.evaluation import backtest_series, mape, rmse
from mercadooptimo.pipeline import recommend

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "precios.db"
FAST_ARIMA = {"order": (1, 1, 1)}  # orden fijo: respuesta en segundos para la recomendación y el backtest

MODEL_LABELS = {"arima": "ARIMA", "naive": "Ingenuo (último precio)", "seasonal_naive": "Ingenuo estacional",
                "lstm": "LSTM (red neuronal)"}
try:  # la LSTM solo aparece si PyTorch está instalado
    import torch  # noqa: F401

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

st.set_page_config(page_title="MercadoÓptimo", page_icon="🛒", layout="wide")


# ---------------------------------------------------------------- datos
@st.cache_data(show_spinner="Cargando histórico de precios…")
def load_data(path: str) -> tuple[pd.DataFrame, list[str]]:
    conn = db.connect(path)
    df = db.load_prices(conn)
    if df.empty:
        db.save_prices(conn, generate_prices())
        df = db.load_prices(conn)
    return db.to_wide(df), sorted(df.source.unique())


wide, sources = load_data(str(DB_PATH))
PRODUCTS = [PRODUCTS_BY_ID[i] for i in dict.fromkeys(wide.columns.get_level_values(0)) if i in PRODUCTS_BY_ID]
STORES = sorted(set(wide.columns.get_level_values(1)))


def store_label(s: str) -> str:
    return s.replace("tienda_", "Tienda ").title() if s.startswith("tienda_") else s.capitalize()


def pname(pid: str) -> str:
    return PRODUCTS_BY_ID[pid].name if pid in PRODUCTS_BY_ID else pid


PALETTE = ["#222222", "#e4572e", "#2e86de", "#17a673", "#a259c4"]  # la primera serie (real / sistema) en negro


def line_chart(df: pd.DataFrame, height: int = 380, y_title: str = "COP") -> None:
    """Gráfico de líneas con el eje Y ajustado a los datos (no desde 0) y leyenda abajo."""
    import altair as alt

    long = df.rename_axis("Fecha").reset_index().melt("Fecha", var_name="Serie", value_name="Valor").dropna()
    order = list(df.columns)
    chart = (
        alt.Chart(long)
        .mark_line(strokeWidth=2.5)
        .encode(
            x=alt.X("Fecha:T", title=None),
            y=alt.Y("Valor:Q", title=y_title, scale=alt.Scale(zero=False)),
            color=alt.Color("Serie:N", sort=order, legend=alt.Legend(orient="bottom", title=None, labelLimit=300),
                            scale=alt.Scale(domain=order, range=PALETTE[: len(order)])),
            tooltip=["Fecha:T", "Serie:N", alt.Tooltip("Valor:Q", format=",.0f")],
        )
        .properties(height=height)
        .interactive(bind_y=False)
    )
    st.altair_chart(chart, width="stretch")


def money(x: float) -> str:
    return f"${x:,.0f}".replace(",", ".")


# ---------------------------------------------------------------- encabezado
st.title("🛒 MercadoÓptimo")
st.markdown("**Predicción de precios + optimización bajo restricciones** para comprar proteínas y canasta "
            "básica al menor costo esperado dentro de un presupuesto.")

with st.sidebar:
    st.header("Datos")
    synthetic = "synthetic" in sources
    st.metric("Semanas de historia", len(wide))
    st.caption(f"{len(PRODUCTS)} productos · {len(STORES)} tiendas · última semana {wide.index[-1]:%d/%m/%Y}")
    if synthetic:
        st.warning("Precios **simulados** (tendencia inflacionaria, estacionalidad, promociones y diferencias "
                   "entre tiendas) mientras el scraping diario de Jumbo y Olímpica acumula historia real.")
    st.header("Parámetros")
    models = ["arima", "naive", "seasonal_naive"] + (["lstm"] if HAS_TORCH else [])
    model = st.selectbox("Modelo de predicción", models, format_func=MODEL_LABELS.get)
    model_kwargs = FAST_ARIMA if model == "arima" else None

tab_rec, tab_pred, tab_save, tab_how = st.tabs(
    ["🛒 1. Recomendación", "📈 2. Predicción de precios", "💰 3. Evaluación del ahorro", "⚙️ 4. Cómo funciona"]
)

# ---------------------------------------------------------------- 1. recomendación
with tab_rec:
    left, right = st.columns([3, 2])
    with left:
        st.subheader("¿Qué necesita comprar?")
        default = {"res_molida": 2, "pollo_pechuga": 1, "huevos": 1, "arroz": 2, "papa": 2, "leche": 4, "tomate": 1}
        editor = pd.DataFrame(
            [{"producto": p.name, "unidad": p.unit, "cantidad": default.get(p.id, 0), "prioridad": 1.0, "id": p.id}
             for p in PRODUCTS]
        )
        edited = st.data_editor(
            editor, hide_index=True, width="stretch", disabled=["producto", "unidad"], height=320,
            column_config={"id": None,
                           "cantidad": st.column_config.NumberColumn(min_value=0, step=1),
                           "prioridad": st.column_config.NumberColumn(
                               min_value=0.0, step=0.5, help="Si el presupuesto no alcanza, se cubren primero "
                                                             "los productos de mayor prioridad")},
        )
    with right:
        st.subheader("Presupuesto y restricciones")
        budget = st.number_input("Presupuesto (COP)", min_value=0, value=150_000, step=5_000)
        limit = st.toggle("Limitar el número de tiendas a visitar")
        max_stores = st.slider("Máximo de tiendas", 1, len(STORES), 1) if limit else None
        st.caption(f"Modelo de predicción: **{MODEL_LABELS[model]}**. El optimizador resuelve un problema de "
                   "programación lineal entera con OR-Tools (SCIP).")
        go = st.button("Calcular recomendación", type="primary", width="stretch")

    demands = {r.id: int(r.cantidad) for r in edited.itertuples() if r.cantidad > 0}
    priorities = {r.id: float(r.prioridad) for r in edited.itertuples() if r.cantidad > 0}

    if go and demands:
        with st.spinner("Prediciendo los precios de la próxima semana y optimizando…"):
            st.session_state.rec = recommend(wide, demands, budget, model=model, priorities=priorities,
                                             max_stores=max_stores, model_kwargs=model_kwargs) + (budget,)
    elif go:
        st.info("Indique al menos un producto con cantidad mayor que cero.")

    if "rec" in st.session_state:
        result, expected, summary, used_budget = st.session_state.rec
        st.divider()
        if result.status == "infeasible":
            st.error("No existe una compra factible con este presupuesto.")
        else:
            if result.uncovered:
                st.warning("El presupuesto no alcanza para toda la lista. Se priorizó lo más importante y se "
                           "omitió: **" + ", ".join(pname(i) for i in result.uncovered) + "**")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Costo esperado", money(result.total_cost), f"{100 * result.total_cost / used_budget:.0f} % "
                      "del presupuesto", delta_color="off")
            c2.metric("Ahorro estimado", money(summary["ahorro"]), f"{summary['ahorro_pct']:.1f} %")
            c3.metric("Tiendas a visitar", len(result.stores_used))
            c4.metric("Tiempo del optimizador", f"{result.solve_seconds * 1000:.0f} ms")
            st.caption(f"Ahorro frente a comprar toda la lista en {store_label(summary['tienda_referencia'])} "
                       "(línea base A), con los precios esperados.")

            cols = st.columns(max(1, len(result.stores_used)))
            for col, (store, grp) in zip(cols, result.plan.groupby("store")):
                with col:
                    st.markdown(f"#### 📍 {store_label(store)}")
                    st.dataframe(
                        pd.DataFrame({"Producto": grp.product_id.map(pname), "Cant.": grp.quantity,
                                      "Precio esperado": grp.unit_price.map(money),
                                      "Subtotal": grp.subtotal.map(money)}),
                        hide_index=True, width="stretch",
                    )
                    st.markdown(f"**Total: {money(grp.subtotal.sum())}**")

            with st.expander("Comparación con comprar todo en una sola tienda"):
                covered = {i: d for i, d in demands.items() if i not in result.uncovered}
                pw = expected.pivot(index="product_id", columns="store", values="price")
                single = pw.reindex(list(covered)).mul(pd.Series(covered), axis=0).sum(skipna=False)
                comp = pd.DataFrame({"Opción": ["MercadoÓptimo"] + [f"Todo en {store_label(s)}" for s in single.index],
                                     "Costo": [result.total_cost] + single.tolist()}).dropna()
                st.bar_chart(comp, x="Opción", y="Costo", horizontal=True, height=260)
            with st.expander("Precios esperados para la próxima semana (salida del modelo predictivo)"):
                table = expected.pivot(index="product_id", columns="store", values="price")
                table = table.rename(index=pname, columns=store_label).round(0)
                st.dataframe(table.style.highlight_min(axis=1, color="#c8e6c9").format("${:,.0f}"), width="stretch")
                st.caption("En verde, la tienda más barata para cada producto.")

# ---------------------------------------------------------------- 2. predicción
with tab_pred:
    st.subheader("Entrenamiento y evaluación de los modelos de predicción")
    st.markdown("Partición **temporal**: cada semana de prueba se predice usando solo los datos anteriores "
                "(sin fuga de información). Se compara contra el modelo **ingenuo** (repetir el último precio), "
                "la línea base del informe.")
    c1, c2, c3 = st.columns([2, 1, 1])
    pid = c1.selectbox("Producto", [p.id for p in PRODUCTS], format_func=pname,
                       index=next((k for k, p in enumerate(PRODUCTS) if p.id == "res_molida"), 0))
    store = c2.selectbox("Tienda", STORES, format_func=store_label)
    test_weeks = c3.slider("Semanas de prueba", 8, 40, 24)
    cand = ["naive", "seasonal_naive", "arima"] + (["lstm"] if HAS_TORCH else [])
    chosen = st.multiselect("Modelos a comparar", cand, default=[m for m in cand if m != "seasonal_naive"],
                            format_func=MODEL_LABELS.get)

    @st.cache_data(show_spinner=False)
    def run_backtest(series: pd.Series, m: str, test_size: int) -> pd.DataFrame:
        return backtest_series(series, m, test_size, refit_every=4 if m in ("arima", "lstm") else 1)

    if st.button("▶ Entrenar y evaluar", type="primary"):
        series = wide[(pid, store)]
        bar = st.progress(0.0, "Entrenando…")
        results = {}
        for k, m in enumerate(chosen):
            bar.progress(k / len(chosen), f"Entrenando {MODEL_LABELS[m]}…")
            results[m] = run_backtest(series, m, test_weeks)
        bar.empty()
        st.session_state.pred = (pid, store, test_weeks, results)

    if "pred" in st.session_state:
        pid_, store_, tw, results = st.session_state.pred
        series = wide[(pid_, store_)]
        metrics = pd.DataFrame(
            [{"Modelo": MODEL_LABELS[m], "RMSE (COP)": rmse(bt.actual, bt.pred), "MAPE (%)": mape(bt.actual, bt.pred)}
             for m, bt in results.items()]
        )
        if "naive" in results:
            base = metrics.loc[metrics.Modelo == MODEL_LABELS["naive"], "MAPE (%)"].iloc[0]
            metrics["Mejora vs. ingenuo (%)"] = (1 - metrics["MAPE (%)"] / base) * 100
        best = metrics.loc[metrics["MAPE (%)"].idxmin(), "Modelo"]

        st.markdown(f"#### {pname(pid_)} — {store_label(store_)}")
        hist = series.iloc[-(tw + 40):].rename("Precio real")
        chart = pd.DataFrame(hist)
        for m, bt in results.items():
            chart[MODEL_LABELS[m]] = pd.Series(bt.pred.to_numpy(), index=pd.DatetimeIndex(bt.date))
        line_chart(chart, height=380, y_title="Precio (COP)")
        st.caption("Las predicciones empiezan donde inicia el periodo de prueba. Pase el mouse para ver valores.")
        st.dataframe(metrics.style.format({"RMSE (COP)": "{:,.0f}", "MAPE (%)": "{:.2f}",
                                           "Mejora vs. ingenuo (%)": "{:+.1f}"})
                     .highlight_min(subset=["MAPE (%)"], color="#c8e6c9"), hide_index=True, width="stretch")
        st.success(f"Mejor modelo en esta serie: **{best}**. Meta del informe: MAPE al menos 10 % menor que el "
                   "modelo ingenuo.")

# ---------------------------------------------------------------- 3. ahorro
with tab_save:
    st.subheader("¿Cuánto se ahorra realmente?")
    st.markdown(
        "Simulación semana a semana: el sistema solo conoce los precios **hasta la semana anterior**, predice, "
        "optimiza y luego se mide el costo **con los precios reales** de esa semana, comparado con:\n"
        "- **Línea base A:** comprar toda la lista en una tienda de referencia.\n"
        "- **Línea base B:** comprar cada producto donde estuvo más barato la semana anterior (sin predicción).\n"
        "- **Oráculo:** la mejor compra posible conociendo los precios reales (cota inferior)."
    )
    c1, c2 = st.columns(2)
    weeks = c1.slider("Semanas a simular", 4, 26, 12)
    save_model = c2.selectbox("Modelo", ["arima", "naive"] + (["lstm"] if HAS_TORCH else []),
                              format_func=MODEL_LABELS.get, key="save_model")
    basket = {i: d for i, d in demands.items()} or {"arroz": 2, "huevos": 1, "leche": 4}
    st.caption("Canasta: la lista de la pestaña 1 — " + ", ".join(f"{d}× {pname(i)}" for i, d in basket.items()))

    def run_savings(basket_items: tuple, weeks: int, m: str) -> pd.DataFrame:
        from mercadooptimo.evaluation.savings import backtest_savings

        bar = st.progress(0.0, "Simulando semanas…")
        out = backtest_savings(wide, dict(basket_items), weeks=weeks, model=m,
                               model_kwargs=FAST_ARIMA if m == "arima" else None,
                               progress=lambda f: bar.progress(f, f"Simulando semana {int(f * weeks) + 1} de {weeks}…"))
        bar.empty()
        return out

    if st.button("▶ Simular", type="primary"):
        st.session_state.save = run_savings(tuple(sorted(basket.items())), weeks, save_model)

    if "save" in st.session_state:
        bt = st.session_state.save
        c1, c2, c3 = st.columns(3)
        c1.metric("Ahorro promedio vs. A", f"{bt['ahorro_vs_A_%'].mean():.1f} %", "meta ≥ 5 %", delta_color="off")
        c2.metric("Ahorro promedio vs. B", f"{bt['ahorro_vs_B_%'].mean():.2f} %", "meta > 0 %", delta_color="off")
        c3.metric("Distancia al oráculo", f"{bt['brecha_oraculo_%'].mean():.2f} %", "menor es mejor",
                  delta_color="off")
        chart = bt.set_index("date")[["costo_sistema", "costo_A_tienda_ref", "costo_B_mas_barata_ayer",
                                      "costo_oraculo"]]
        chart.columns = ["MercadoÓptimo", "A: una sola tienda", "B: más barata la semana anterior", "Oráculo"]
        line_chart(chart, height=360, y_title="Costo de la canasta (COP)")
        total = bt[["costo_A_tienda_ref", "costo_sistema"]].sum()
        st.info(f"En {len(bt)} semanas: {money(total.costo_A_tienda_ref)} comprando todo en una tienda vs. "
                f"{money(total.costo_sistema)} con MercadoÓptimo → **{money(total.costo_A_tienda_ref - total.costo_sistema)}"
                " ahorrados**.")

# ---------------------------------------------------------------- 4. cómo funciona
with tab_how:
    st.subheader("Arquitectura en tres capas")
    a, b, c = st.columns(3)
    a.markdown("##### 🗄️ Datos\n- Scraping de **Jumbo** y **Olímpica** (respeta robots.txt)\n"
               f"- Cruce por **código de barras (EAN)**: {len(REAL_PRODUCTS)} productos idénticos en ambas tiendas\n"
               "- Precios mayoristas **SIPSA-DANE**\n- Histórico en SQLite + CSV, recolección diaria automática")
    b.markdown("##### 🧠 Bloque de IA\n- **Conocimiento:** modelos ingenuo, ARIMA y LSTM estiman el precio "
               "de la próxima semana\n- **Razonamiento:** programación lineal entera elige qué comprar y dónde")
    c.markdown("##### 🖥️ Aplicación\n- Presupuesto, productos y prioridades\n- Lista por tienda y ahorro "
               "estimado\n- Evaluación contra líneas base")
    st.subheader("Modelo del optimizador")
    st.markdown("Sea $p_{is}$ el precio esperado del producto $i$ en la tienda $s$, $d_i$ la cantidad requerida y "
                "$B$ el presupuesto. La variable $x_{is}$ es la cantidad entera a comprar.")
    st.latex(r"\min \sum_{i}\sum_{s} p_{is}\,x_{is} \quad \text{s.a.} \quad \sum_{s} x_{is} \ge d_i \;\; \forall i,"
             r"\qquad \sum_i\sum_s p_{is}\,x_{is} \le B,\qquad x_{is}\in\mathbb{Z}_{\ge 0}")
    st.markdown("Si el presupuesto no alcanza, se maximiza la prioridad cubierta con binarias $z_i$:")
    st.latex(r"\max \sum_i w_i\,z_i \quad \text{s.a.} \quad \sum_s x_{is} \ge d_i\,z_i \;\; \forall i,"
             r"\qquad \sum_i\sum_s p_{is}\,x_{is} \le B")
    st.markdown("Opcionalmente se limita el número de tiendas con binarias $y_s$: "
                "$x_{is} \\le d_i\\,y_s$, $\\sum_s y_s \\le K$.")
    if REAL_PRODUCTS:
        with st.expander(f"Catálogo real cruzado por EAN ({len(REAL_PRODUCTS)} productos)"):
            st.dataframe(pd.DataFrame([{"EAN": p.ean, "Producto": p.name, "Presentación": p.unit,
                                        "Categoría": p.category} for p in REAL_PRODUCTS]),
                         hide_index=True, width="stretch")
