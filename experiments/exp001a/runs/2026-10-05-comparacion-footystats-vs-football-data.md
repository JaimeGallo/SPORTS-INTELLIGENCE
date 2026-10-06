# EXP-001a: referencia con football-data.co.uk frente a FootyStats Premier League

> Probabilidad no es certeza. Edge no es garantía de resultado. Simulación sin dinero real.

Fecha: 2026-10-05. Tres runs, todos con código `91609fc`:

| Run | Qué es | Datos | Test | `backtest_run_id` |
| --- | --- | --- | --- | --- |
| **A** | Referencia con football-data.co.uk ([informe](2026-10-05-football-data-5-ligas-bt_dmxbm5nnf921xyn4.md)) | 5 ligas, 2015/16 a 2025/26, 19.763 partidos | 2024/25 y 2025/26, 3.504 partidos | `bt_dmxbm5nnf921xyn4` |
| **B** | Control: football-data.co.uk con la ventana de FootyStats ([informe](2026-10-05-football-data-epl-control-bt_y9fb6smbnpxfts6t.md), [config](../config.fd-control-epl.yaml)) | Premier League, 2018/19 a 2024/25, 2.660 partidos | 2023/24 y 2024/25, 760 partidos | `bt_y9fb6smbnpxfts6t` |
| **C** | FootyStats Premier League ([informe publicado el 2026-10-02](2026-10-02-footystats-epl-bt_t1p1tw9s712kk8ac.md)), re-ejecutado | Premier League, 2018/19 a 2024/25, 2.660 partidos | 2023/24 y 2024/25, 760 partidos | `bt_1rh8493mbesqmkth` |

B no estaba pedido: lo añadí porque A y C difieren a la vez en fuente, ligas, temporadas, validación y test, así que
compararlos directamente no dice nada sobre la fuente. B cambia **solo** la fuente respecto a C.

## Resumen

1. **La referencia con football-data.co.uk se ejecutó con datos reales.** Sin leakage, 0 violaciones de coherencia, calibración
   dentro del objetivo en las 37 combinaciones agregadas (peor ECE 0,0205) y 17 combinaciones mejores que el baseline (0 peores).
   Reproducible: re-ejecutando desde una base vacía, `summary.json` y `report.md` salen idénticos byte a byte.
2. **La fuente de datos no explica la diferencia entre los dos informes publicados.** En la Premier League, los goles (FT y 1T) son
   idénticos en los 2.660 partidos. Los córners difieren en 102 (3,8%), casi siempre FootyStats con uno menos. Sobre los mismos 380
   partidos de 2024/25, B y C dan el mismo resultado (log loss O/U 2.5 de 0,6805 y 0,6804).
3. **El veredicto de calibración cambia por la ventana de test y el tamaño de muestra, no por la fuente.** El test de C y B incluye
   2023/24, donde el 64,7% de los partidos de la EPL acabó en Over 2.5 (56,6% en 2024/25 y 55,0% en 2025/26). Un calibrador ajustado
   con el pasado no lo anticipa. Con 380 partidos de 2024/25 los tres runs son indistinguibles.
4. **El mercado sigue siendo mejor que los modelos, en los tres runs.** La diferencia de log loss es positiva con IC 95% que excluye
   el cero. La simulación paper (solo posible con football-data.co.uk, que trae cuotas pre-partido) da ROI -5,9% con IC [-10,6%,
   -1,4%] y CLV -4,4%. No hay señal de edge.
5. **La calibración agregada de A esconde sesgos por liga.** 58 de 130 celdas liga×mercado×línea×familia tienen ECE > 0,03 y 18
   quedan fuera del ruido de muestreo (Serie A 10, Premier League 5, Bundesliga 3).
6. **Encontré y corregí un fallo de Dixon-Coles** que abortaba el run con datos reales (sección 6). No cambia ningún número de los
   informes ya publicados.

## 1. Verificaciones previas

- **football-data.co.uk**: `https://www.football-data.co.uk/mmz4281/2526/E0.csv` responde 302 a `https://football-data.co.uk/...`, y
  ese responde 200 (203.438 bytes). Sin `www` directo también 200. Los 55 ficheros (5 ligas × 11 temporadas) se descargaron. El
  README decía que el host sin `www` estaba bloqueado en la red del entorno; hoy no lo está.
- **FOOTYSTATS_API_KEY**: definida en el entorno (no se imprime) y válida: `jevs footystats leagues --country England` lista la
  Premier League 2018/19 a 2024/25, el alcance de la key de prueba. La re-ejecución de C bajó el `dataset_version` otra vez a
  `dataset-42wyw3f7evnhqy3x`, idéntico al del 2026-10-02.
- **Re-ejecución de C con el código actual**: el informe solo difiere del publicado en `backtest_run_id` y `code_version`. Todas
  las tablas son idénticas.

## 2. Resultado de la referencia (run A)

Ingesta: 55 ficheros, 19.763 partidos, 224.796 cuotas, 10 incidencias de calidad (7 pares de cuotas inválidas descartados y 3
partidos sin goles del 1T o córners, marcados como `missing_fields`). 3.389.853 predicciones.

| Criterio | Resultado |
| --- | --- |
| Sin leakage | Cumple |
| Coherencia entre líneas | 0 violaciones |
| Calibración agregada (ECE < 0,03 o ruido) | 37 de 37 bajo el objetivo, peor ECE 0,0205 |
| Frente al baseline | 17 mejores, 0 peores, 9 sin diferencia concluyente |
| Frente al mercado O/U 2.5 | Peor que el mercado: ΔLL pre-partido +0,0077 [0,0040, 0,0111], cierre +0,0109 [0,0067, 0,0150] |
| Paper (stake plano) | 2.054 apuestas, ROI -5,9% [-10,6%, -1,4%], acierto 43,3%, edge medio 6,4%, CLV -4,4% |

Lectura:

- Los modelos de equipo ganan al baseline de frecuencias en todas las líneas de goles FT (ΔLL de -0,0031 a -0,0080) y en córners
  FT 7.5, 9.5 (Binomial Negativa) y 11.5. En goles 1T no hay diferencia concluyente.
- Dixon-Coles, Poisson y Binomial Negativa dan el mismo log loss en las líneas de goles 2.5 y 3.5. No es un error: la corrección de
  Dixon-Coles solo mueve masa entre los marcadores 0-0, 0-1, 1-0 y 1-1, es decir, entre totales de 0, 1 y 2, que quedan del mismo
  lado de esas líneas.
- El "edge" de 6,4% que ven los modelos frente a la cuota pre-partido es error del modelo, no señal: con un margen medio de 4,4% de
  las casas, apostar sin criterio rinde unas -4,2%, y el ROI de -5,9% es compatible con eso. El CLV negativo (-4,4%)
  confirma que el precio del modelo es peor que el de cierre.

## 3. Comparación con FootyStats Premier League

### 3.1 Los datos coinciden, salvo algunos córners

Emparejando por fecha local y equipos, los 2.660 partidos de la EPL (2018/19 a 2024/25) de football-data.co.uk están en FootyStats y
viceversa.

| Estadística | Partidos distintos | FootyStats menos | FootyStats más |
| --- | ---: | ---: | ---: |
| Goles FT (local y visitante) | 0 de 2.660 | 0 | 0 |
| Goles 1T (local y visitante) | 0 de 2.660 | 0 | 0 |
| Córners totales | 102 de 2.660 (3,8%) | 94 | 8 |

- La discrepancia de córners crece con el tiempo: 1,1% y 0,5% en 2018/19 y 2019/20, y de 3,7% a 6,8% desde 2020/21. Casi siempre es
  un córner menos en FootyStats (89 de los 102).
- Tres casos son +10 córners en FootyStats (Man City-Cardiff 2019-04-03: 7 frente a 17; Burnley-West Ham 2021-12-12: 4 frente a 14;
  Arsenal-Burnley 2023-11-11: 3 frente a 13). Parecen un dígito de más. No he podido comprobar cuál de las dos fuentes acierta.
- El efecto en los mercados es pequeño: según la línea (7.5 a 11.5), el resultado Over/Under cambia en 0,26% a 0,60% de los partidos.

### 3.2 Control: misma ventana y método, otra fuente (B frente a C)

Comparación pareada por partido de la diferencia de log loss medio (sobre las líneas), con bootstrap por partido. Negativo = B mejor.

| Mercado y familia | N | ΔLL (B menos C) | IC 95% |
| --- | ---: | ---: | --- |
| Goles FT, Poisson | 760 | -0,00002 | [-0,00011, 0,00008] |
| Goles 1T, Poisson | 760 | 0,00000 | [-0,00008, 0,00008] |
| Córners FT, Poisson | 760 | -0,00185 | [-0,00432, 0,00042] |
| Córners FT, Binomial Negativa | 760 | -0,00186 | [-0,00440, 0,00046] |

En goles no hay diferencia alguna porque los datos son idénticos. En córners B es algo mejor, pero el intervalo incluye el cero. Las
cifras de calidad de cada informe también coinciden: en el contraste justo (sin los córners del 1T, que solo tiene FootyStats), C
tiene 15 combinaciones bajo el objetivo, 6 dentro del ruido y 16 fuera, y B tiene 16, 7 y 14.

### 3.3 Los mismos 380 partidos de 2024/25: A, B y C

Goles FT, Over/Under 2.5, Premier League 2024/25 (tasa real 56,6%):

| Run | Familia | P media | Brier | Log loss | ECE |
| --- | --- | ---: | ---: | ---: | ---: |
| A, 5 ligas | Poisson | 57,6% | 0,2430 | 0,6790 | 0,0339 |
| B, control | Poisson | 58,2% | 0,2438 | 0,6805 | 0,0593 |
| C, FootyStats | Poisson | 58,1% | 0,2437 | 0,6804 | 0,0634 |

A frente a B, sobre esos partidos, no hay diferencia concluyente en ningún modelo de equipo (|ΔLL| de 0,0011 como máximo en goles FT,
0,0008 en goles 1T y 0,0008 en córners, y todos los IC incluyen el cero). Entrenar con cinco ligas y más historia no mejora de forma
medible la Premier League, aunque con 380 partidos tampoco se detectaría una mejora pequeña. La única diferencia significativa es la
del baseline de goles 1T, que se explica en 3.5.

### 3.4 Por qué cambia el veredicto de calibración

De las 16 combinaciones "fuera" de C, 10 son goles FT y 3 son córners FT 10.5 (B tiene 14, con el mismo patrón). En goles FT, los
modelos con Platt predicen un 57% de Over 2.5 en C y en B, y la tasa real fue 60,7%. Tres razones, en orden de peso:

1. **La ventana de test.** La Premier League 2023/24 fue un valor atípico: 3,28 goles por partido y 64,7% de partidos con Over 2.5,
   frente a 2,7 a 2,9 goles y 50% a 54% en las cinco temporadas anteriores. El calibrador se ajusta solo con temporadas anteriores y
   no lo anticipa. En A, 2023/24 es validación y el test (2024/25 y 2025/26) tiene en la EPL 2,93 y 2,75 goles por partido y tasas de
   56,6% y 55,0%, cercanas a lo que el modelo esperaba.
2. **El tamaño de muestra.** El ECE se infla en muestras pequeñas. Con 760 partidos la referencia de ruido del ECE (p95) va de 0,03 a
   0,05 en las líneas centrales; con 3.504 va de 0,01 a 0,02. El criterio "ECE < 0,03" es más fácil de cumplir con más partidos.
3. **El calibrador agrupado.** En A el calibrador Platt se ajusta con las cinco ligas y siete temporadas de validación, no con tres
   temporadas de una sola liga.

### 3.5 Una afirmación del informe de FootyStats que no es robusta

El informe de C cita "goles 1T 0.5" entre las combinaciones que ganan al baseline. Ese baseline, con calibrador isotónico elegido
en validación (3 temporadas), sobreestima P(Over 0.5 1T) en 5 puntos en el test: P media 80,9% frente a 75,7% real, ECE 0,0596 (⚠).
B hace lo mismo (80,8%). En A el baseline eligió identidad y la comparación es "sin diferencia concluyente" (ΔLL -0,0030 con IC
[-0,0066, 0,0006]). Esa ventaja era de un baseline mal calibrado, no del modelo.

### 3.6 Mercado

| Run | Referencia de mercado | Δ log loss modelo menos mercado (IC 95%) | Paper |
| --- | --- | --- | --- |
| C | Cierre de FootyStats (casa y hora desconocidas) | +0,0088 [0,0016, 0,0166] | 0 apuestas (sin cuotas pre-partido) |
| B | Pre-partido: Pinnacle o media de mercado | +0,0096 [0,0017, 0,0178] | 434 apuestas, ROI -5,6% [-16,3%, 6,4%], CLV -3,6% |
| B | Cierre | +0,0111 [0,0019, 0,0204] | |
| A | Pre-partido | +0,0077 [0,0040, 0,0111] | 2.054 apuestas, ROI -5,9% [-10,6%, -1,4%], CLV -4,4% |
| A | Cierre | +0,0109 [0,0067, 0,0150] | |

- Las cuotas de cierre de FootyStats son una referencia algo peor que las de football-data.co.uk: sobre los mismos 760 partidos su
  log loss es 0,6635 frente a 0,6612, es decir, subestiman la ventaja del mercado en 0,0023.
- Solo football-data.co.uk permite la simulación paper, porque trae cuotas pre-partido con casa conocida.
- Con 434 apuestas el IC del ROI en B incluye el cero y no concluye nada. El de A (2.054 apuestas) lo excluye por el lado negativo.

## 4. Lo que la calibración agregada de A esconde

Con el test de A desglosado por liga (611 a 760 partidos), los sesgos se compensan entre ligas. Por ejemplo, córners FT 9.5 con
Poisson: Premier League P media 54,1% frente a 58,0% real, Serie A 47,6% frente a 43,2%.

| Liga | Celdas | ECE medio | ECE máx. | ECE > 0,03 | Fuera del ruido |
| --- | ---: | ---: | ---: | ---: | ---: |
| Premier League | 26 | 0,0285 | 0,0557 | 13 | 5 |
| La Liga | 26 | 0,0249 | 0,0373 | 10 | 0 |
| Ligue 1 | 26 | 0,0175 | 0,0328 | 2 | 0 |
| Bundesliga | 26 | 0,0302 | 0,0753 | 12 | 3 |
| Serie A | 26 | 0,0368 | 0,0596 | 21 | 10 |

Total: 130 celdas, 58 con ECE > 0,03 y 18 fuera del ruido. Si todos los modelos estuvieran calibrados se esperarían unas 6 por azar,
pero las celdas no son independientes (Poisson, Binomial Negativa y Dixon-Coles son casi idénticas, y las líneas de un mismo mercado
comparten partidos), así que el exceso es real pero menor de lo que sugiere el recuento. Un modelo calibrado en conjunto no está
necesariamente calibrado en cada liga. Siguiente paso razonable: calibración por liga, o evaluar si compensa.

## 5. Un fallo encontrado y corregido

El primer intento del run A abortó con `rho=-0.245 gives negative probabilities for lambdas 4.309, 0.614`. `fit_dixon_coles_rho`
acota `rho` para que los cuatro factores de bajos marcadores sean positivos con las lambdas de la muestra de entrenamiento (el
límite de -0,245 implica una lambda máxima de unas 4,1), pero un partido futuro muy desequilibrado puede tener una lambda mayor (1 + 4,309 × -0,245 < 0) y la
comprobación estricta de `dixon_coles_total` lanzaba un `ModelError` que tumbaba todo el experimento. Con datos sintéticos nunca
aparecía.

Corrección (commit `91609fc`): al predecir, `rho` se acota al intervalo que mantiene positivos los factores para esa pareja de
lambdas (`dixon_coles_rho_limits`). El `rho` ajustado y el usado se guardan en el snapshot de features (`rho`, `rho_used`). Para
todos los casos que antes funcionaban el resultado es idéntico: el informe de FootyStats re-ejecutado coincide con el publicado, y
en las 17.937 predicciones de la variante de Dixon-Coles seleccionada en A el límite no se activó nunca. El caso que fallaba
(`rho` de -0,245; el mínimo de la variante seleccionada es -0,229) pertenecía a otra variante de la rejilla de hiperparámetros, no
seleccionada, de la que no se guardan snapshots, así que no puedo contar cuántas veces se activó allí. El primer intento fallido no produjo ninguna cifra, por lo que no pudo condicionar decisiones.

## 6. Limitaciones

- Las comparaciones A, B y C se decidieron después de ver los resultados. Ninguna alimenta la selección de modelos (que sigue
  haciéndose solo en validación), pero no son un contraste preregistrado.
- 2024/25 es test en los tres runs. 2023/24 es test en B y C y validación en A.
- Sobre 380 partidos la potencia es baja: "sin diferencia concluyente" no demuestra que dos modelos sean iguales.
- La referencia de ruido del ECE es una simulación que depende del orden de las filas. El script de análisis fija el orden, pero
  las cifras del informe oficial y las del script pueden diferir en el tercer decimal en esa columna.
- Los córners miden el modelo frente a los datos de cada fuente, no frente a la realidad (3,8% de partidos difieren).
- Solo hay una línea con cuotas (O/U 2.5 de goles FT). Córners y primer tiempo se comparan con el mercado en EXP-001b.

## 7. Cómo reproducirlo

```bash
export DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/jevs
.venv/bin/jevs experiment exp001a                                                     # run A
.venv/bin/jevs experiment exp001a --experiment-config experiments/exp001a/config.fd-control-epl.yaml   # run B
DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/jevs_fs FOOTYSTATS_API_KEY=... \
  .venv/bin/jevs experiment exp001a --experiment-config experiments/exp001a/config.footystats-epl.yaml # run C
.venv/bin/python experiments/exp001a/compare_runs.py --five jevs:<run A> --control jevs:<run B> --footystats jevs_fs:<run C>
```

El `backtest_run_id` depende del código, así que otro commit da otro id con las mismas cifras.
