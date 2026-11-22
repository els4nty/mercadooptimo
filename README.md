# MercadoÓptimo

Proyecto de curso PTIA — Escuela Colombiana de Ingeniería Julio Garavito, Grupo 03.

Sistema que **predice los precios** de proteínas (carnes y pescados) y productos de la
canasta básica y, con esos precios esperados, **optimiza la compra**: dado un presupuesto y
una lista de productos, recomienda qué comprar y en qué establecimiento para minimizar el
costo esperado.

```
precios históricos ──► modelo predictivo ──► precios esperados p_is ──► optimizador ILP ──► lista recomendada + ahorro
 (Jumbo, Olímpica,     (ingenuo, ARIMA, LSTM)                         (OR-Tools / SCIP)
  SIPSA-DANE)
```

## Arquitectura (informe, sección 6.4)

| Capa | Módulo | Contenido |
|---|---|---|
| Datos | `mercadooptimo.data` | SQLite con histórico por producto, tienda y fecha, más un CSV versionado de historial (`db.py`); carga de SIPSA-DANE (`sipsa.py`); scrapers de Jumbo y Olímpica vía JSON-LD y estado VTEX, con política conservadora de robots.txt (`scrapers/`); cruce de productos idénticos por código de barras EAN (`discover.py`); generador sintético para desarrollo (`synthetic.py`) |
| IA: conocimiento | `mercadooptimo.forecasting` | Modelo ingenuo (línea base), ingenuo estacional, ARIMA con selección de orden por AIC y LSTM (PyTorch) sobre retornos logarítmicos con early stopping; evaluación con partición temporal y origen móvil (RMSE, MAPE) |
| IA: razonamiento | `mercadooptimo.optimizer` | Programación lineal entera: modelo base de mínimo costo, variante con prioridades cuando el presupuesto no alcanza, extensión opcional de máximo de tiendas; heurística voraz para la razón de optimalidad |
| Evaluación | `mercadooptimo.evaluation` | Líneas base A (todo en una tienda de referencia) y B (la más barata de la semana anterior), backtest de ahorro con costo realizado y brecha frente al oráculo |
| Aplicación | `app/streamlit_app.py`, `mercadooptimo.cli` | Interfaz web y línea de comandos |

### Modelo del optimizador (sección 6.5)

Modelo base:

$$\min \sum_{i}\sum_{s} p_{is} x_{is} \quad \text{s.a.} \quad \sum_s x_{is} \ge d_i\ \forall i,\quad \sum_i\sum_s p_{is}x_{is} \le B,\quad x_{is}\in\mathbb{Z}_{\ge 0}$$

Si es infactible, variante con prioridades $w_i$ y binarias $z_i$:

$$\max \sum_i w_i z_i \quad \text{s.a.} \quad \sum_s x_{is} \ge d_i z_i\ \forall i,\quad \sum_i\sum_s p_{is}x_{is} \le B$$

## Instalación

Requiere **Python 3.10 a 3.14** (se recomienda **3.12**). Python 3.15 todavía no sirve porque
OR-Tools y PyTorch no publican versiones para él.

### macOS

En Mac el comando es `python3` (no `python`). Si tu versión no está entre 3.10 y 3.14, instala
Python 3.12 desde [python.org](https://www.python.org/downloads/release/python-31210/)
(*macOS 64-bit universal2 installer*) o con Homebrew:

```bash
brew install python@3.12
```

Luego, dentro de la carpeta del proyecto:

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # la terminal debe mostrar (.venv)
pip install -e ".[app,dev]"
pip install -e ".[lstm]"           # opcional: PyTorch para el modelo LSTM
streamlit run app/streamlit_app.py
```

Cada vez que abras una terminal nueva, activa el entorno antes de ejecutar:

```bash
cd mercadooptimo
source .venv/bin/activate
streamlit run app/streamlit_app.py
```

Si ya habías creado `.venv` con otra versión de Python, bórralo primero con
`deactivate; rm -rf .venv`.

### Windows

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[app,dev]"
pip install -e ".[lstm]"
streamlit run app/streamlit_app.py
```

### Linux

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[app,dev]"
pip install -e ".[lstm]"
```

## Uso

```bash
mercadooptimo seed-synthetic                 # datos sintéticos de desarrollo -> data/precios.db
mercadooptimo products                       # catálogo de productos
mercadooptimo recommend --budget 150000 --item res_molida=2 --item arroz=3 --item huevos=1
mercadooptimo recommend --budget 150000 --max-stores 2
mercadooptimo evaluate-forecast --models naive arima lstm   # RMSE/MAPE con partición temporal
mercadooptimo evaluate-savings --weeks 12    # ahorro vs. líneas base A y B
mercadooptimo load-sipsa data/raw/archivo.xlsx

# Datos reales de las cadenas
mercadooptimo check-robots --out robots_report.md            # revisa robots.txt de las cadenas
mercadooptimo discover --jumbo html/jumbo_*.html --olimpica html/olimpica_*.html --write
mercadooptimo scrape --dry-run                               # prueba sin guardar
mercadooptimo scrape --csv data/history/precios.csv          # guarda en la base y en el historial
mercadooptimo import-csv                                     # carga el historial a la base local
streamlit run app/streamlit_app.py
pytest
```

## Indicadores (objetivos específicos)

| Objetivo | Indicador | Comando |
|---|---|---|
| Modelo de precios | MAPE ≥ 10 % menor que el ingenuo; comparado con ARIMA | `evaluate-forecast` |
| Optimizador | Factibilidad, tiempo de cómputo, razón de optimalidad | `recommend`, `pytest` |
| Ahorro | ≥ 5 % vs. línea base A y > 0 vs. línea base B | `evaluate-savings` |

## Interfaz

`streamlit run app/streamlit_app.py` abre la app en el navegador con cuatro pestañas:

| Pestaña | Qué muestra |
|---|---|
| 🛒 Mi recomendación | Lista de mercado, presupuesto, prioridades y límite de tiendas → tarjetas por tienda, ahorro estimado y comparación con comprar todo en una sola tienda |
| 📈 Predicción de precios | Entrena y compara ingenuo, ARIMA y LSTM sobre una serie, con gráfico real vs. predicción y métricas explicadas |
| 💰 ¿Cuánto ahorro? | Simulación semana a semana contra las líneas base A, B y el oráculo |
| ⚙️ Cómo funciona | Diagrama de arquitectura, modelo matemático y catálogo real por código de barras |

Capturas en `docs/capturas/` y guion del video en `docs/guion_video.md`.

## Recolección automática

El workflow `.github/workflows/scrape.yml` corre todos los días a las 6:17 a. m. (hora de
Colombia): descarga los precios de `config/targets.csv` y agrega las filas nuevas a
`data/history/precios.csv` con un commit. También se puede lanzar a mano desde la
pestaña **Actions** → *Recolección diaria de precios* → *Run workflow*. El workflow
`tests.yml` corre las pruebas en cada push y pull request.

Mientras una serie tenga poca historia (menos de 20 semanas para ARIMA y 42 para la
LSTM), la recomendación usa el modelo ingenuo para esa serie.

## Estado actual

- ✅ Esquema de datos, carga SIPSA configurable, generador sintético.
- ✅ Scrapers de Jumbo y Olímpica, revisión de robots.txt y catálogo de 24 productos idénticos por EAN.
- ✅ Historial en CSV y recolección diaria automática con GitHub Actions.
- ✅ Modelos ingenuo, ingenuo estacional, ARIMA y LSTM con backtest temporal.
- ✅ Optimizador ILP (base, prioridades, máximo de tiendas) con OR-Tools/SCIP.
- ✅ Backtest de ahorro contra líneas base y oráculo; CLI e interfaz Streamlit.
- ⏳ Ampliar el catálogo real con proteínas (carnes, pollo, pescado), hoy casi todo es despensa.
- ⏳ Descargar los anexos SIPSA y ajustar el mapeo de productos (`data/sipsa.py`) para tener historia larga.
- ⏳ Recalcular las métricas con datos reales cuando haya historia suficiente.
- ⏳ Pruebas con usuarios del objetivo cualitativo.

> **Importante:** los resultados actuales provienen de datos **sintéticos** (`source='synthetic'`)
> y solo sirven para validar el código. Las métricas del informe deben calcularse con datos reales.

## Referencias principales

1. T. França, R. Campiolo y L. Candido, «A case study for minimal cost shopping in a cluster of online stores», ICEIS 2022.
2. L. Menculini et al., «Comparing Prophet and deep learning to ARIMA in forecasting wholesale food prices», *Forecasting*, 2021.
