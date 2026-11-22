"""Interfaz de MercadoÓptimo.

Pestañas, en el orden de la cadena de IA del informe:
  1. Recomendación   presupuesto + productos -> lista de compra óptima
  2. Predicción      entrenamiento y evaluación de los modelos (ingenuo, ARIMA, LSTM)
  3. Ahorro          backtest del ahorro frente a las líneas base A y B
  4. Cómo funciona   arquitectura, modelo matemático y fuentes de datos

Ejecutar:  streamlit run app/streamlit_app.py
"""

from pathlib import Path

import altair as alt
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
MODEL_HELP = {
    "naive": "Supone que la próxima semana el precio será igual al de esta semana. Es la línea base: "
             "cualquier modelo inteligente debe superarlo.",
    "seasonal_naive": "Repite el precio de la misma semana del año anterior.",
    "arima": "Modelo estadístico de series de tiempo: aprende la tendencia (inflación) y cómo los "
             "cambios recientes influyen en el siguiente precio.",
    "lstm": "Red neuronal recurrente: lee las últimas 12 semanas y aprende patrones para predecir la siguiente.",
}
try:  # la LSTM solo aparece si PyTorch está instalado
    import torch  # noqa: F401

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

STORE_COLORS = ["#16a34a", "#2563eb", "#ea580c", "#9333ea", "#0891b2", "#db2777"]
PALETTE = ["#111827", "#ea580c", "#2563eb", "#16a34a", "#9333ea"]  # la primera serie (real / sistema) en negro
CATEGORY_ICON = {"proteina": "🥩", "canasta": "🧺"}
PRODUCT_ICON = {"res_molida": "🥩", "res_lomo": "🥩", "cerdo_chuleta": "🍖", "pollo_pechuga": "🍗",
                "pollo_entero": "🐔", "tilapia": "🐟", "huevos": "🥚", "arroz": "🍚", "frijol": "🫘",
                "lenteja": "🫘", "papa": "🥔", "platano": "🍌", "leche": "🥛", "aceite": "🫒", "tomate": "🍅",
                "cebolla": "🧅"}

st.set_page_config(page_title="MercadoÓptimo", page_icon="🛒", layout="wide")

st.markdown(
    """
<style>
.block-container {padding-top: 3.2rem; max-width: 1300px;}
.hero {background: linear-gradient(120deg, #14532d 0%, #16a34a 55%, #4ade80 100%); color: #fff;
       border-radius: 18px; padding: 28px 32px; margin-bottom: 18px; box-shadow: 0 8px 24px rgba(22,163,74,.25);}
.hero h1 {color: #fff; margin: 0; font-size: 2.4rem;}
.hero p {color: #ecfdf5; margin: 6px 0 0 0; font-size: 1.08rem;}
.flow {display: flex; gap: 10px; align-items: stretch; margin: 6px 0 4px 0; flex-wrap: wrap;}
.step {flex: 1; min-width: 150px; background: #fff; border: 1px solid #d1fae5; border-radius: 14px;
       padding: 12px 14px; box-shadow: 0 2px 6px rgba(0,0,0,.04);}
.step b {display: block; color: #14532d; font-size: .98rem;}
.step span {color: #4b5563; font-size: .85rem;}
.step .n {display: inline-block; background: #16a34a; color: #fff; border-radius: 50%; width: 24px; height: 24px;
          text-align: center; line-height: 24px; font-weight: 700; margin-right: 6px; font-size: .85rem;}
.arrow {align-self: center; color: #16a34a; font-size: 1.4rem; font-weight: 700;}
.card {background: #fff; border-radius: 14px; padding: 16px 18px; border: 1px solid #e5e7eb;
       box-shadow: 0 2px 8px rgba(0,0,0,.05); height: 100%;}
.kpi {background: #fff; border-radius: 14px; padding: 14px 18px; border: 1px solid #e5e7eb;
      box-shadow: 0 2px 8px rgba(0,0,0,.05);}
.kpi .label {color: #6b7280; font-size: .85rem; text-transform: uppercase; letter-spacing: .04em;}
.kpi .value {font-size: 1.9rem; font-weight: 800; color: #111827; line-height: 1.25;}
.kpi .sub {font-size: .88rem; color: #6b7280;}
.kpi.good .value {color: #15803d;}
.store-card {background: #fff; border-radius: 14px; border: 1px solid #e5e7eb; overflow: hidden;
             box-shadow: 0 2px 8px rgba(0,0,0,.05); margin-bottom: 12px;}
.store-card .head {color: #fff; padding: 10px 16px; font-weight: 700; font-size: 1.05rem;
                   display: flex; justify-content: space-between;}
.store-card .row {display: flex; justify-content: space-between; padding: 7px 16px; border-top: 1px solid #f3f4f6;
                  font-size: .95rem;}
.store-card .row .q {color: #6b7280; font-size: .85rem;}
.explain {background: #eff6ff; border-left: 5px solid #2563eb; border-radius: 10px; padding: 12px 16px;
          color: #1e3a8a; margin: 6px 0 14px 0; font-size: .96rem;}
.big-saving {background: linear-gradient(120deg, #dcfce7, #f0fdf4); border: 1px solid #86efac; border-radius: 16px;
             padding: 18px 22px; font-size: 1.15rem; color: #14532d; margin-top: 8px;}
.big-saving b {font-size: 1.5rem;}
.arch {display: grid; grid-template-columns: 1fr 40px 1fr 40px 1fr; gap: 6px; align-items: stretch;}
.arch .box {background: #fff; border-radius: 14px; padding: 16px; border-top: 6px solid; min-height: 230px;
            box-shadow: 0 2px 8px rgba(0,0,0,.06);}
.arch .box h4 {margin-top: 0;}
.arch .box ul {padding-left: 18px; margin-bottom: 0;}
.arch .ar {text-align: center; font-size: 2rem; color: #16a34a; font-weight: 800; align-self: center;}
@media (max-width: 900px) {.arch {grid-template-columns: 1fr;} .arch .ar {transform: rotate(90deg);}}
div[data-testid="stTabs"] button p {font-size: 1.02rem; font-weight: 600;}
</style>
""",
    unsafe_allow_html=True,
)


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
STORE_COLOR = {s: STORE_COLORS[k % len(STORE_COLORS)] for k, s in enumerate(STORES)}


def store_label(s: str) -> str:
    return s.replace("tienda_", "Tienda ").title() if s.startswith("tienda_") else s.capitalize()


def pname(pid: str) -> str:
    return PRODUCTS_BY_ID[pid].name if pid in PRODUCTS_BY_ID else pid


def picon(pid: str) -> str:
    p = PRODUCTS_BY_ID.get(pid)
    return PRODUCT_ICON.get(pid) or (CATEGORY_ICON.get(p.category, "🛒") if p else "🛒")


def money(x: float) -> str:
    return f"${x:,.0f}".replace(",", ".")


def kpi(col, label: str, value: str, sub: str = "", good: bool = False) -> None:
    col.markdown(f'<div class="kpi {"good" if good else ""}"><div class="label">{label}</div>'
                 f'<div class="value">{value}</div><div class="sub">{sub}</div></div>', unsafe_allow_html=True)


def explain(text: str) -> None:
    st.markdown(f'<div class="explain">💡 {text}</div>', unsafe_allow_html=True)


def line_chart(df: pd.DataFrame, height: int = 380, y_title: str = "COP") -> None:
    """Gráfico de líneas con el eje Y ajustado a los datos (no desde 0) y leyenda abajo."""
    long = df.rename_axis("Fecha").reset_index().melt("Fecha", var_name="Serie", value_name="Valor").dropna()
    order = list(df.columns)
    chart = (
        alt.Chart(long)
        .mark_line(strokeWidth=2.6)
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


# ---------------------------------------------------------------- encabezado
st.markdown(
    '<div class="hero"><h1>🛒 MercadoÓptimo</h1>'
    "<p>Le decimos <b>qué comprar y en qué tienda</b> para gastar lo menos posible: la IA <b>predice</b> los "
    "precios de la próxima semana y <b>optimiza</b> su lista de mercado dentro de su presupuesto.</p></div>",
    unsafe_allow_html=True,
)
st.markdown(
    """<div class="flow">
<div class="step"><span class="n">1</span><b>Datos</b><span>Precios históricos de cada producto en cada tienda</span></div>
<div class="arrow">➜</div>
<div class="step"><span class="n">2</span><b>Predicción 🧠</b><span>ARIMA / LSTM estiman el precio de la próxima semana</span></div>
<div class="arrow">➜</div>
<div class="step"><span class="n">3</span><b>Optimización ⚙️</b><span>Programación entera elige qué comprar y dónde</span></div>
<div class="arrow">➜</div>
<div class="step"><span class="n">4</span><b>Resultado 💰</b><span>Lista por tienda + ahorro estimado</span></div>
</div>""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 📊 Datos")
    st.metric("Semanas de historia", len(wide))
    st.caption(f"{len(PRODUCTS)} productos · {len(STORES)} tiendas · última semana {wide.index[-1]:%d/%m/%Y}")
    if "synthetic" in sources:
        st.warning("**Precios simulados** (inflación, estacionalidad, promociones y diferencias entre tiendas) "
                   "mientras el scraping diario de Jumbo y Olímpica acumula historia real.")
    st.markdown("### 🧠 Modelo de predicción")
    models = ["arima", "naive", "seasonal_naive"] + (["lstm"] if HAS_TORCH else [])
    model = st.selectbox("Modelo", models, format_func=MODEL_LABELS.get, label_visibility="collapsed")
    st.caption(MODEL_HELP[model])
    model_kwargs = FAST_ARIMA if model == "arima" else None

tab_rec, tab_pred, tab_save, tab_how = st.tabs(
    ["🛒 1. Mi recomendación", "📈 2. Predicción de precios", "💰 3. ¿Cuánto ahorro?", "⚙️ 4. Cómo funciona"]
)

# ---------------------------------------------------------------- 1. recomendación
with tab_rec:
    explain("Escriba cuántas unidades necesita de cada producto y su presupuesto. El sistema predice el precio "
            "de cada producto en cada tienda para la próxima semana y busca la combinación más barata.")
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("#### 📝 Mi lista de mercado")
        default = {"res_molida": 2, "pollo_pechuga": 1, "huevos": 1, "arroz": 2, "papa": 2, "leche": 4, "tomate": 1}
        editor = pd.DataFrame(
            [{"producto": f"{picon(p.id)}  {p.name}", "unidad": p.unit, "cantidad": default.get(p.id, 0),
              "prioridad": 1.0, "id": p.id} for p in PRODUCTS]
        )
        edited = st.data_editor(
            editor, hide_index=True, width="stretch", disabled=["producto", "unidad"], height=350,
            column_config={"id": None,
                           "producto": st.column_config.TextColumn("Producto", width="medium"),
                           "unidad": st.column_config.TextColumn("Presentación", width="small"),
                           "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0, step=1),
                           "prioridad": st.column_config.NumberColumn(
                               "Prioridad", min_value=0.0, step=0.5,
                               help="Si el presupuesto no alcanza, se compran primero los de mayor prioridad")},
        )
    with right:
        st.markdown("#### 💵 Presupuesto y restricciones")
        budget = st.number_input("Presupuesto para la semana (COP)", min_value=0, value=150_000, step=5_000)
        limit = st.toggle("🚗 Quiero visitar pocas tiendas")
        max_stores = st.slider("Máximo de tiendas", 1, len(STORES), 1) if limit else None
        st.caption(f"Predicción con **{MODEL_LABELS[model]}** · optimización con programación lineal entera "
                   "(OR-Tools / SCIP).")
        go = st.button("✨ Calcular mi compra óptima", type="primary", width="stretch")

    demands = {r.id: int(r.cantidad) for r in edited.itertuples() if r.cantidad > 0}
    priorities = {r.id: float(r.prioridad) for r in edited.itertuples() if r.cantidad > 0}

    if go and demands:
        with st.status("Calculando…", expanded=True) as status:
            st.write(f"🧠 Prediciendo el precio de la próxima semana con {MODEL_LABELS[model]}…")
            st.write("⚙️ Resolviendo el problema de optimización…")
            st.session_state.rec = recommend(wide, demands, budget, model=model, priorities=priorities,
                                             max_stores=max_stores, model_kwargs=model_kwargs) + (budget,)
            status.update(label="¡Listo! Esta es su compra óptima", state="complete", expanded=False)
    elif go:
        st.info("Indique al menos un producto con cantidad mayor que cero.")

    if "rec" in st.session_state:
        result, expected, summary, used_budget = st.session_state.rec
        st.divider()
        if result.status == "infeasible":
            st.error("No existe una compra factible con este presupuesto.")
        else:
            if result.uncovered:
                st.warning("⚠️ El presupuesto no alcanza para toda la lista. Se priorizó lo más importante y se "
                           "dejó por fuera: **" + ", ".join(pname(i) for i in result.uncovered) + "**")
            st.markdown("### ✅ Su compra óptima")
            c1, c2, c3, c4 = st.columns(4)
            kpi(c1, "Costo esperado", money(result.total_cost),
                f"{100 * result.total_cost / used_budget:.0f} % de su presupuesto")
            kpi(c2, "Ahorro estimado", money(summary["ahorro"]),
                f"{summary['ahorro_pct']:.1f} % vs. comprar todo en {store_label(summary['tienda_referencia'])}",
                good=True)
            kpi(c3, "Tiendas a visitar", str(len(result.stores_used)), ", ".join(map(store_label, result.stores_used)))
            kpi(c4, "Tiempo de cálculo", f"{result.solve_seconds * 1000:.0f} ms", "optimizador exacto")
            st.progress(min(1.0, result.total_cost / used_budget),
                        text=f"Uso del presupuesto: {money(result.total_cost)} de {money(used_budget)}")

            st.markdown("#### 🗺️ Qué comprar en cada tienda")
            cols = st.columns(max(1, len(result.stores_used)))
            for col, (store, grp) in zip(cols, result.plan.groupby("store")):
                rows = "".join(
                    f'<div class="row"><span>{picon(r.product_id)} {pname(r.product_id)} '
                    f'<span class="q">× {r.quantity}</span></span><span>{money(r.subtotal)}</span></div>'
                    for r in grp.itertuples()
                )
                col.markdown(
                    f'<div class="store-card"><div class="head" style="background:{STORE_COLOR[store]}">'
                    f"<span>📍 {store_label(store)}</span><span>{money(grp.subtotal.sum())}</span></div>{rows}</div>",
                    unsafe_allow_html=True,
                )

            g1, g2 = st.columns([1, 1], gap="large")
            with g1:
                st.markdown("#### 📊 ¿Y si compro todo en una sola tienda?")
                covered = {i: d for i, d in demands.items() if i not in result.uncovered}
                pw = expected.pivot(index="product_id", columns="store", values="price")
                single = pw.reindex(list(covered)).mul(pd.Series(covered), axis=0).sum(skipna=False).dropna()
                comp = pd.DataFrame({"Opción": ["⭐ MercadoÓptimo"] + [f"Todo en {store_label(s)}" for s in single.index],
                                     "Costo": [result.total_cost] + single.tolist()})
                comp["tipo"] = ["optimo"] + ["tienda"] * len(single)
                bars = alt.Chart(comp).mark_bar(cornerRadiusEnd=6).encode(
                    x=alt.X("Costo:Q", title="Costo de la lista (COP)", scale=alt.Scale(zero=False)),
                    y=alt.Y("Opción:N", sort="x", title=None),
                    color=alt.Color("tipo:N", scale=alt.Scale(domain=["optimo", "tienda"],
                                                             range=["#16a34a", "#cbd5e1"]), legend=None),
                    tooltip=["Opción", alt.Tooltip("Costo:Q", format=",.0f")],
                )
                labels = bars.mark_text(align="left", dx=4, fontWeight="bold").encode(
                    text=alt.Text("Costo:Q", format="$,.0f"), color=alt.value("#111827"))
                st.altair_chart((bars + labels).properties(height=60 + 38 * len(comp)), width="stretch")
            with g2:
                st.markdown("#### 🔮 Precios esperados la próxima semana")
                table = expected.pivot(index="product_id", columns="store", values="price").reindex(list(demands))
                table.index = [f"{picon(i)} {pname(i)}" for i in table.index]
                table = table.rename(columns=store_label)
                st.dataframe(table.style.highlight_min(axis=1, color="#bbf7d0").format("${:,.0f}"), width="stretch")
                st.caption("Salida del modelo predictivo. En verde, la tienda más barata para cada producto.")

# ---------------------------------------------------------------- 2. predicción
with tab_pred:
    st.markdown("### 📈 Entrenamiento y evaluación de los modelos")
    explain("Para saber si un modelo predice bien, lo ponemos a prueba con el pasado: en cada semana del periodo "
            "de prueba el modelo <b>solo ve los precios anteriores</b> y debe adivinar el de esa semana. Luego "
            "comparamos su predicción con el precio que realmente ocurrió.")
    c1, c2, c3 = st.columns([2, 1, 1])
    pid = c1.selectbox("Producto", [p.id for p in PRODUCTS], format_func=lambda i: f"{picon(i)} {pname(i)}",
                       index=next((k for k, p in enumerate(PRODUCTS) if p.id == "res_molida"), 0))
    store = c2.selectbox("Tienda", STORES, format_func=store_label)
    test_weeks = c3.slider("Semanas de prueba", 8, 40, 24)
    cand = ["naive", "seasonal_naive", "arima"] + (["lstm"] if HAS_TORCH else [])
    chosen = st.multiselect("Modelos a comparar", cand, default=[m for m in cand if m != "seasonal_naive"],
                            format_func=MODEL_LABELS.get)
    with st.expander("¿Qué hace cada modelo?"):
        for m in cand:
            st.markdown(f"- **{MODEL_LABELS[m]}:** {MODEL_HELP[m]}")

    @st.cache_data(show_spinner=False)
    def run_backtest(series: pd.Series, m: str, test_size: int) -> pd.DataFrame:
        return backtest_series(series, m, test_size, refit_every=4 if m in ("arima", "lstm") else 1)

    if st.button("▶ Entrenar y evaluar", type="primary") and chosen:
        series = wide[(pid, store)]
        bar = st.progress(0.0, "Entrenando…")
        results = {}
        for k, m in enumerate(chosen):
            bar.progress(k / len(chosen), f"🧠 Entrenando {MODEL_LABELS[m]}…")
            results[m] = run_backtest(series, m, test_weeks)
        bar.empty()
        st.session_state.pred = (pid, store, test_weeks, results)

    if "pred" in st.session_state:
        pid_, store_, tw, results = st.session_state.pred
        series = wide[(pid_, store_)]
        metrics = pd.DataFrame(
            [{"m": m, "Modelo": MODEL_LABELS[m], "RMSE (COP)": rmse(bt.actual, bt.pred),
              "MAPE (%)": mape(bt.actual, bt.pred)} for m, bt in results.items()]
        )
        base = metrics.loc[metrics.m == "naive", "MAPE (%)"]
        if not base.empty:
            metrics["Mejora vs. ingenuo (%)"] = (1 - metrics["MAPE (%)"] / base.iloc[0]) * 100
        best = metrics.loc[metrics["MAPE (%)"].idxmin()]

        st.markdown(f"#### {picon(pid_)} {pname(pid_)} — {store_label(store_)}")
        cols = st.columns(len(metrics))
        for col, (_, r) in zip(cols, metrics.iterrows()):
            err = r["MAPE (%)"]
            sub = f"se equivoca en promedio {err:.1f} %"
            if "Mejora vs. ingenuo (%)" in metrics and r["m"] != "naive":
                sub += f" · {r['Mejora vs. ingenuo (%)']:+.1f} % vs. ingenuo"
            is_best = r["m"] == best["m"]
            kpi(col, ("🏆 " if is_best else "") + r["Modelo"], f"{err:.2f} %", sub, good=is_best)

        hist = series.iloc[-(tw + 40):].rename("Precio real")
        chart = pd.DataFrame(hist)
        for m, bt in results.items():
            chart[MODEL_LABELS[m]] = pd.Series(bt.pred.to_numpy(), index=pd.DatetimeIndex(bt.date))
        line_chart(chart, height=380, y_title="Precio (COP)")
        st.caption("Las predicciones empiezan donde inicia el periodo de prueba. Pase el mouse para ver valores; "
                   "con la rueda puede hacer zoom.")

        with st.expander("📐 Tabla de métricas y cómo leerlas"):
            st.dataframe(metrics.drop(columns="m").style.format(
                {"RMSE (COP)": "{:,.0f}", "MAPE (%)": "{:.2f}", "Mejora vs. ingenuo (%)": "{:+.1f}"})
                .highlight_min(subset=["MAPE (%)"], color="#bbf7d0"), hide_index=True, width="stretch")
            st.markdown("- **MAPE:** error porcentual promedio. Un MAPE de 3 % significa que, en promedio, la "
                        "predicción se aleja 3 % del precio real.\n"
                        "- **RMSE:** error típico en pesos; penaliza más los errores grandes.\n"
                        "- **Meta del informe:** MAPE al menos 10 % menor que el del modelo ingenuo.")

# ---------------------------------------------------------------- 3. ahorro
with tab_save:
    st.markdown("### 💰 ¿Cuánto se ahorra realmente?")
    explain("Simulamos varias semanas de compras. Cada semana el sistema solo conoce los precios hasta la semana "
            "anterior, predice, optimiza y luego medimos cuánto habría pagado <b>con los precios reales</b>. "
            "Lo comparamos con tres formas de comprar:")
    a, b, c = st.columns(3)
    a.markdown('<div class="card"><b>🏪 Línea base A</b><br>Comprar toda la lista en una sola tienda de '
               "referencia, como hace la mayoría.</div>", unsafe_allow_html=True)
    b.markdown('<div class="card"><b>📅 Línea base B</b><br>Comprar cada producto donde estuvo más barato la '
               "semana pasada, sin predecir.</div>", unsafe_allow_html=True)
    c.markdown('<div class="card"><b>🔮 Oráculo</b><br>La mejor compra posible si conociéramos el futuro. '
               "Nadie puede superarla: es la cota inferior.</div>", unsafe_allow_html=True)
    st.write("")
    c1, c2 = st.columns(2)
    weeks = c1.slider("Semanas a simular", 4, 26, 12)
    save_model = c2.selectbox("Modelo", ["arima", "naive"] + (["lstm"] if HAS_TORCH else []),
                              format_func=MODEL_LABELS.get, key="save_model")
    basket = dict(demands) or {"arroz": 2, "huevos": 1, "leche": 4}
    st.caption("🧺 Canasta (la lista de la pestaña 1): " + ", ".join(f"{d}× {pname(i)}" for i, d in basket.items()))

    def run_savings(basket_items: tuple, weeks: int, m: str) -> pd.DataFrame:
        from mercadooptimo.evaluation.savings import backtest_savings

        bar = st.progress(0.0, "Simulando semanas…")
        out = backtest_savings(wide, dict(basket_items), weeks=weeks, model=m,
                               model_kwargs=FAST_ARIMA if m == "arima" else None,
                               progress=lambda f: bar.progress(f, f"🛒 Simulando semana {int(f * weeks) + 1} de {weeks}…"))
        bar.empty()
        return out

    if st.button("▶ Simular semanas de compra", type="primary"):
        st.session_state.save = run_savings(tuple(sorted(basket.items())), weeks, save_model)

    if "save" in st.session_state:
        bt = st.session_state.save
        total = bt[["costo_A_tienda_ref", "costo_sistema"]].sum()
        st.markdown(
            f'<div class="big-saving">En <b>{len(bt)} semanas</b> habría pagado {money(total.costo_A_tienda_ref)} '
            f"comprando todo en una tienda, y <b>{money(total.costo_sistema)}</b> con MercadoÓptimo: "
            f"<b>{money(total.costo_A_tienda_ref - total.costo_sistema)} ahorrados</b> 🎉</div>",
            unsafe_allow_html=True,
        )
        st.write("")
        c1, c2, c3 = st.columns(3)
        sa, sb, gap = bt["ahorro_vs_A_%"].mean(), bt["ahorro_vs_B_%"].mean(), bt["brecha_oraculo_%"].mean()
        kpi(c1, "Ahorro vs. A", f"{sa:.1f} %", "meta del informe ≥ 5 % " + ("✅" if sa >= 5 else "❌"), good=sa >= 5)
        kpi(c2, "Ahorro vs. B", f"{sb:.2f} %", "meta del informe > 0 % " + ("✅" if sb > 0 else "❌"), good=sb > 0)
        kpi(c3, "Distancia al oráculo", f"{gap:.2f} %", "qué tan cerca estamos de lo perfecto")
        st.write("")
        chart = bt.set_index("date")[["costo_sistema", "costo_A_tienda_ref", "costo_B_mas_barata_ayer",
                                      "costo_oraculo"]]
        chart.columns = ["⭐ MercadoÓptimo", "A: una sola tienda", "B: más barata la semana pasada", "Oráculo"]
        line_chart(chart, height=360, y_title="Costo de la canasta (COP)")

# ---------------------------------------------------------------- 4. cómo funciona
with tab_how:
    st.markdown("### ⚙️ Arquitectura en tres capas")
    st.markdown(
        f"""<div class="arch">
<div class="box" style="border-color:#2563eb"><h4>🗄️ Capa de datos</h4><ul>
<li>Scraping de <b>Jumbo</b> y <b>Olímpica</b>, respetando robots.txt</li>
<li>Cruce por <b>código de barras (EAN)</b>: {len(REAL_PRODUCTS)} productos idénticos en ambas tiendas</li>
<li>Precios mayoristas <b>SIPSA-DANE</b></li>
<li>Histórico en SQLite + CSV, recolección diaria automática (GitHub Actions)</li></ul></div>
<div class="ar">➜</div>
<div class="box" style="border-color:#16a34a"><h4>🧠 Bloque de IA</h4><ul>
<li><b>Conocimiento:</b> modelos ingenuo, ARIMA y LSTM aprenden de los precios históricos y estiman el precio de la próxima semana</li>
<li><b>Razonamiento:</b> programación lineal entera evalúa las combinaciones producto-tienda y elige la más barata que cumple el presupuesto</li></ul></div>
<div class="ar">➜</div>
<div class="box" style="border-color:#ea580c"><h4>🖥️ Aplicación</h4><ul>
<li>El usuario ingresa presupuesto, productos y prioridades</li>
<li>Recibe la lista por tienda y el ahorro estimado</li>
<li>Evaluación contra líneas base</li></ul></div>
</div>""",
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown("### 🧮 El modelo matemático del optimizador")
    explain("El optimizador es el corazón del sistema: convierte los precios esperados en una decisión de compra.")
    m1, m2 = st.columns(2, gap="large")
    with m1:
        st.markdown("**Modelo base: minimizar el costo**")
        st.latex(r"\min \sum_{i}\sum_{s} p_{is}\,x_{is}")
        st.latex(r"\text{s.a.}\;\; \sum_{s} x_{is} \ge d_i \;\;\forall i, \qquad \sum_i\sum_s p_{is}\,x_{is} \le B")
        st.markdown("- $p_{is}$: precio esperado del producto $i$ en la tienda $s$ (lo da el modelo predictivo)\n"
                    "- $d_i$: cantidad que necesita · $B$: presupuesto\n"
                    "- $x_{is}$: cuántas unidades comprar (número entero)")
    with m2:
        st.markdown("**Si el presupuesto no alcanza: maximizar la prioridad cubierta**")
        st.latex(r"\max \sum_i w_i\,z_i")
        st.latex(r"\text{s.a.}\;\; \sum_s x_{is} \ge d_i\,z_i \;\;\forall i, \qquad \sum_i\sum_s p_{is}\,x_{is} \le B")
        st.markdown("- $w_i$: prioridad del producto · $z_i \\in \\{0,1\\}$: ¿se compra?\n"
                    "- **Extra:** limitar a $K$ tiendas con binarias $y_s$: $x_{is} \\le d_i\\,y_s$, "
                    "$\\sum_s y_s \\le K$")
    if REAL_PRODUCTS:
        with st.expander(f"🏷️ Catálogo real cruzado por código de barras ({len(REAL_PRODUCTS)} productos)"):
            st.dataframe(pd.DataFrame([{"EAN": p.ean, "Producto": p.name, "Presentación": p.unit,
                                        "Categoría": p.category} for p in REAL_PRODUCTS]),
                         hide_index=True, width="stretch")
