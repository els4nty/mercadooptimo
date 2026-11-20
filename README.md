# MercadoÓptimo

Proyecto de curso PTIA — Escuela Colombiana de Ingeniería Julio Garavito, Grupo 03.

Sistema que **predice los precios** de proteínas (carnes y pescados) y productos de la
canasta básica y, con esos precios esperados, **optimiza la compra**: dado un presupuesto y
una lista de productos, recomienda qué comprar y en qué establecimiento para minimizar el
costo esperado.

```
precios históricos ──► modelo predictivo ──► precios esperados p_is ──► optimizador ILP ──► lista recomendada + ahorro
 (scraping / SIPSA)    (ingenuo, ARIMA, LSTM)                         (OR-Tools / SCIP)
```

## Arquitectura (informe, sección 6.4)

| Capa | Módulo | Contenido |
|---|---|---|
| Datos | `mercadooptimo.data` | SQLite con histórico por producto, tienda y fecha (`db.py`); carga de SIPSA-DANE (`sipsa.py`); scrapers con respeto de robots.txt (`scrapers/`); generador sintético para desarrollo (`synthetic.py`) |
| IA: conocimiento | `mercadooptimo.forecasting` | Modelo ingenuo (línea base), ingenuo estacional y ARIMA con selección de orden por AIC; evaluación con partición temporal y origen móvil (RMSE, MAPE) |
| IA: razonamiento | `mercadooptimo.optimizer` | Programación lineal entera: modelo base de mínimo costo, variante con prioridades cuando el presupuesto no alcanza, extensión opcional de máximo de tiendas; heurística voraz para la razón de optimalidad |
| Evaluación | `mercadooptimo.evaluation` | Líneas base A (todo en una tienda de referencia) y B (la más barata de la semana anterior), backtest de ahorro con costo realizado y brecha frente al oráculo |
| Aplicación | `app/streamlit_app.py`, `mercadooptimo.cli` | Interfaz web y línea de comandos |

### Modelo del optimizador (sección 6.5)

Modelo base:

$$\min \sum_{i}\sum_{s} p_{is} x_{is} \quad \text{s.a.} \quad \sum_s x_{is} \ge d_i\ \forall i,\quad \sum_i\sum_s p_{is}x_{is} \le B,\quad x_{is}\in\mathbb{Z}_{\ge 0}$$

Si es infactible, variante con prioridades $w_i$ y binarias $z_i$:

$$\max \sum_i w_i z_i \quad \text{s.a.} \quad \sum_s x_{is} \ge d_i z_i\ \forall i,\quad \sum_i\sum_s p_{is}x_{is} \le B$$

## Instalación

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[app,dev]"
```

## Uso

```bash
mercadooptimo seed-synthetic                 # datos sintéticos de desarrollo -> data/precios.db
mercadooptimo products                       # catálogo de productos
mercadooptimo recommend --budget 150000 --item res_molida=2 --item arroz=3 --item huevos=1
mercadooptimo recommend --budget 150000 --max-stores 2
mercadooptimo evaluate-forecast              # RMSE/MAPE: ingenuo vs. ingenuo estacional vs. ARIMA
mercadooptimo evaluate-savings --weeks 12    # ahorro vs. líneas base A y B
mercadooptimo load-sipsa data/raw/archivo.xlsx
streamlit run app/streamlit_app.py
pytest
```

## Indicadores (objetivos específicos)

| Objetivo | Indicador | Comando |
|---|---|---|
| Modelo de precios | MAPE ≥ 10 % menor que el ingenuo; comparado con ARIMA | `evaluate-forecast` |
| Optimizador | Factibilidad, tiempo de cómputo, razón de optimalidad | `recommend`, `pytest` |
| Ahorro | ≥ 5 % vs. línea base A y > 0 vs. línea base B | `evaluate-savings` |

## Estado actual

- ✅ Esquema de datos, carga SIPSA configurable, base de scrapers, generador sintético.
- ✅ Modelos ingenuo, ingenuo estacional y ARIMA con backtest temporal.
- ✅ Optimizador ILP (base, prioridades, máximo de tiendas) con OR-Tools/SCIP.
- ✅ Backtest de ahorro contra líneas base y oráculo; CLI e interfaz Streamlit.
- ⏳ Definir las cadenas reales e implementar sus scrapers (revisar términos de uso y robots.txt).
- ⏳ Descargar los anexos SIPSA y ajustar el mapeo de productos (`data/sipsa.py`).
- ⏳ Modelo LSTM (PyTorch/Keras) como otro `Forecaster`.
- ⏳ Pruebas con usuarios del objetivo cualitativo.

> **Importante:** los resultados actuales provienen de datos **sintéticos** (`source='synthetic'`)
> y solo sirven para validar el código. Las métricas del informe deben calcularse con datos reales.

## Referencias principales

1. T. França, R. Campiolo y L. Candido, «A case study for minimal cost shopping in a cluster of online stores», ICEIS 2022.
2. L. Menculini et al., «Comparing Prophet and deep learning to ARIMA in forecasting wholesale food prices», *Forecasting*, 2021.
