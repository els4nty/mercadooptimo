# Guion del video de presentación — MercadoÓptimo (≈ 6–7 min)

## Antes de grabar

```bash
pip install -e ".[app,lstm]"
mercadooptimo seed-synthetic        # solo si no existe data/precios.db
streamlit run app/streamlit_app.py
```

Ensayen una vez: la primera ejecución de cada pestaña tarda unos segundos (la LSTM ~20 s).
Después queda en caché y en la grabación responde rápido.

---

## 1. Problema (0:00 – 0:45) — diapositiva o portada del informe
- En Colombia la compra de alimentos pesa mucho en el gasto del hogar y la inflación de alimentos
  hace que los precios de proteínas y canasta básica cambien semana a semana.
- Un comparador de precios del día ordena precios actuales, pero **no anticipa** cómo van a cambiar
  ni resuelve **qué comprar y dónde** con un presupuesto fijo.
- Por eso combinamos dos técnicas de IA: **predicción** (series de tiempo) y **razonamiento**
  (optimización con restricciones).

## 2. Cómo funciona (0:45 – 1:45) — pestaña **4. Cómo funciona**
- Tres capas: datos, bloque de IA y aplicación.
- Datos: scrapers de **Jumbo y Olímpica** que respetan robots.txt; cruce por **código de barras**
  para comparar exactamente el mismo producto (mostrar el expander con los 24 productos reales);
  recolección diaria automática con GitHub Actions.
- Mostrar el modelo matemático: minimizar el costo esperado sujeto a cubrir las cantidades y no pasar
  el presupuesto; si no alcanza, variante con prioridades.
- Aclarar (barra lateral): **la demostración usa precios simulados** mientras el scraping acumula
  historia real; el código es el mismo para datos reales.

## 3. Recomendación (1:45 – 3:15) — pestaña **1. Recomendación**
1. Mostrar la lista (carne molida, pollo, huevos, arroz, papa, leche, tomate) y presupuesto $150.000.
2. **Calcular recomendación** → explicar las 4 métricas: costo esperado, ahorro (~10 % vs. comprar
   todo en una sola tienda), tiendas a visitar y tiempo del optimizador (milisegundos).
3. Mostrar la lista dividida por tienda.
4. Abrir "Precios esperados…" → "esta es la salida del modelo predictivo; en verde la más barata".
5. Activar **Limitar el número de tiendas = 1** → recalcular: el optimizador elige la mejor tienda
   única (más caro, pero un solo desplazamiento). Esto ya no es trivial: necesita programación entera.
6. Bajar el presupuesto a **$60.000** → recalcular: aparece el aviso de presupuesto insuficiente
   y se omiten productos según la prioridad. Subir la prioridad de "Carne de res molida" a 5 y
   recalcular para mostrar que ahora sí se incluye.

## 4. Predicción (3:15 – 5:00) — pestaña **2. Predicción de precios**
1. Producto "Carne de res molida", Tienda A, 24 semanas de prueba, modelos Ingenuo + ARIMA + LSTM.
2. **Entrenar y evaluar** → mientras corre: "cada semana de prueba se predice solo con datos
   anteriores, partición temporal, como en la literatura (Menculini et al.)".
3. Explicar el gráfico: negro = precio real, colores = predicciones de cada modelo.
4. Tabla: RMSE y MAPE; columna "Mejora vs. ingenuo". Leer los números honestamente: los modelos
   mejoran ligeramente al ingenuo; la meta del informe (10 %) se evaluará con datos reales.
5. Cambiar a otro producto (p. ej. "Huevos AA x30") y volver a entrenar para mostrar que funciona
   para cualquier serie.

## 5. Ahorro (5:00 – 6:00) — pestaña **3. Evaluación del ahorro**
1. Explicar las líneas base A, B y el oráculo.
2. **Simular** 12 semanas con ARIMA.
3. Resultados de referencia: **~9,5 % de ahorro vs. A** (meta ≥ 5 %), **> 0 % vs. B** (meta > 0),
   y a menos de 1 % del oráculo.
4. Gráfico: la línea naranja (una sola tienda) siempre por encima; MercadoÓptimo (negro) casi
   pegado al oráculo.

## 6. Cierre (6:00 – 6:45)
- Logrado: cadena completa datos → predicción → optimización → recomendación, con evaluación
  contra líneas base; 62 pruebas automáticas; scraping real de dos cadenas.
- Siguiente: acumular historia real (scraping diario + SIPSA-DANE), ampliar el catálogo de
  proteínas, recalcular las métricas con datos reales y pruebas con usuarios.
