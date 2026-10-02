# EXP001A: informe de resultados

> Probabilidad no es certeza. Edge no es garantía de resultado. Simulación sin dinero real.

| Campo | Valor |
| --- | --- |
| backtest_run_id | `bt_t1p1tw9s712kk8ac` |
| dataset_version | `dataset-42wyw3f7evnhqy3x` |
| config_hash | `a9db12159ac32b8f` |
| code_version | `bd1bd2d` |
| provider | `footystats` |
| n_predictions | `563880` |
| n_snapshots | `149520` |
| coherence_violations | `0` |
| ingesta | 7 ficheros, 2660 partidos, 65273 cuotas, 101 incidencias de calidad |

## 1. Integridad (leakage)

- Todas las predicciones usan solo datos con `available_at <= as_of`: **sí**.
- Coherencia entre líneas (P(Over) no crece con la línea): **0 violaciones**.

## 2. Selección en validación

Elegido por log loss medio en las temporadas de validación; el test no interviene en la elección.

| Objetivo | Familia | Modelo | Calibrador | Log loss | Brier | ECE |
| --- | --- | --- | --- | ---: | ---: | ---: |
| corners_1H | league_freq | `jevs-corners-1h-league_freq-xi0.0039-w730-r1-v1` | identity | 0.5922 | 0.2033 | 0.0076 |
| corners_1H | negbin | `jevs-corners-1h-negbin-xi0.0019-w730-r4-v1` | platt | 0.5932 | 0.2037 | 0.0164 |
| corners_1H | poisson | `jevs-corners-1h-poisson-xi0-w730-r4-v1` | platt | 0.5933 | 0.2037 | 0.0180 |
| corners_FT | league_freq | `jevs-corners-ft-league_freq-xi0-w730-r1-v1` | identity | 0.6334 | 0.2212 | 0.0098 |
| corners_FT | negbin | `jevs-corners-ft-negbin-xi0.0039-w730-r1-v1` | platt | 0.6309 | 0.2202 | 0.0066 |
| corners_FT | poisson | `jevs-corners-ft-poisson-xi0.0039-w730-r1-v1` | platt | 0.6309 | 0.2202 | 0.0056 |
| goals_1H | league_freq | `jevs-goals-1h-league_freq-xi0.0039-w730-r1-v1` | isotonic | 0.6248 | 0.2168 | 0.0061 |
| goals_1H | negbin | `jevs-goals-1h-negbin-xi0-w730-r4-v1` | platt | 0.6236 | 0.2163 | 0.0302 |
| goals_1H | poisson | `jevs-goals-1h-poisson-xi0-w730-r4-v1` | platt | 0.6236 | 0.2163 | 0.0302 |
| goals_FT | dixon_coles | `jevs-goals-ft-dixon_coles-xi0.0039-w730-r4-v1` | platt | 0.5247 | 0.1759 | 0.0191 |
| goals_FT | league_freq | `jevs-goals-ft-league_freq-xi0.0019-w730-r1-v1` | identity | 0.5282 | 0.1776 | 0.0062 |
| goals_FT | negbin | `jevs-goals-ft-negbin-xi0.0039-w730-r4-v1` | platt | 0.5247 | 0.1759 | 0.0190 |
| goals_FT | poisson | `jevs-goals-ft-poisson-xi0.0039-w730-r4-v1` | platt | 0.5247 | 0.1759 | 0.0194 |

## 3. Test fuera de muestra

| Mercado | Línea | Familia | Calibrador | N | Tasa real | P media | Brier | Log loss | ECE | Ruido ECE (p95) |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| corners_1h_total | 2.5 | league_freq | identity | 721 | 84.3% | 85.3% | 0.1322 | 0.4343 | 0.0098 | 0.0262 |
| corners_1h_total | 2.5 | negbin | platt | 721 | 84.3% | 85.5% | 0.1319 | 0.4333 | 0.0115 | 0.0259 |
| corners_1h_total | 2.5 | poisson | platt | 721 | 84.3% | 85.6% | 0.1319 | 0.4330 | 0.0123 | 0.0252 |
| corners_1h_total | 3.5 | league_freq | identity | 721 | 69.9% | 70.4% | 0.2106 | 0.6122 | 0.0053 | 0.0384 |
| corners_1h_total | 3.5 | negbin | platt | 721 | 69.9% | 70.6% | 0.2095 | 0.6097 | 0.0340 ≈ | 0.0382 |
| corners_1h_total | 3.5 | poisson | platt | 721 | 69.9% | 70.7% | 0.2095 | 0.6096 | 0.0136 | 0.0372 |
| corners_1h_total | 4.5 | league_freq | identity | 721 | 52.1% | 53.4% | 0.2494 | 0.6919 | 0.0128 | 0.0386 |
| corners_1h_total | 4.5 | negbin | platt | 721 | 52.1% | 53.3% | 0.2475 | 0.6881 | 0.0156 | 0.0423 |
| corners_1h_total | 4.5 | poisson | platt | 721 | 52.1% | 53.4% | 0.2478 | 0.6889 | 0.0138 | 0.0430 |
| corners_1h_total | 5.5 | league_freq | identity | 721 | 33.6% | 34.8% | 0.2231 | 0.6384 | 0.0128 | 0.0386 |
| corners_1h_total | 5.5 | negbin | platt | 721 | 33.6% | 37.0% | 0.2219 | 0.6357 | 0.0347 ≈ | 0.0396 |
| corners_1h_total | 5.5 | poisson | platt | 721 | 33.6% | 36.9% | 0.2226 | 0.6371 | 0.0333 ≈ | 0.0389 |
| corners_ft_total | 7.5 | league_freq | identity | 760 | 79.5% | 79.2% | 0.1638 | 0.5098 | 0.0315 ≈ | 0.0316 |
| corners_ft_total | 7.5 | negbin | platt | 760 | 79.5% | 79.8% | 0.1607 | 0.5009 | 0.0134 | 0.0331 |
| corners_ft_total | 7.5 | poisson | platt | 760 | 79.5% | 79.4% | 0.1608 | 0.5010 | 0.0034 | 0.0353 |
| corners_ft_total | 8.5 | league_freq | identity | 760 | 72.0% | 69.7% | 0.2039 | 0.5984 | 0.0416 ⚠ | 0.0387 |
| corners_ft_total | 8.5 | negbin | platt | 760 | 72.0% | 70.1% | 0.2005 | 0.5906 | 0.0230 | 0.0427 |
| corners_ft_total | 8.5 | poisson | platt | 760 | 72.0% | 69.7% | 0.2006 | 0.5910 | 0.0275 | 0.0417 |
| corners_ft_total | 9.5 | league_freq | identity | 760 | 60.1% | 58.3% | 0.2416 | 0.6764 | 0.0642 ⚠ | 0.0407 |
| corners_ft_total | 9.5 | negbin | platt | 760 | 60.1% | 57.3% | 0.2385 | 0.6700 | 0.0311 ≈ | 0.0455 |
| corners_ft_total | 9.5 | poisson | platt | 760 | 60.1% | 57.2% | 0.2387 | 0.6703 | 0.0325 ≈ | 0.0444 |
| corners_ft_total | 10.5 | league_freq | identity | 760 | 50.0% | 47.5% | 0.2528 | 0.6988 | 0.0647 ⚠ | 0.0419 |
| corners_ft_total | 10.5 | negbin | platt | 760 | 50.0% | 45.6% | 0.2501 | 0.6933 | 0.0567 ⚠ | 0.0493 |
| corners_ft_total | 10.5 | poisson | platt | 760 | 50.0% | 45.5% | 0.2502 | 0.6936 | 0.0590 ⚠ | 0.0477 |
| corners_ft_total | 11.5 | league_freq | identity | 760 | 36.1% | 35.5% | 0.2323 | 0.6575 | 0.0059 | 0.0349 |
| corners_ft_total | 11.5 | negbin | platt | 760 | 36.1% | 35.5% | 0.2267 | 0.6451 | 0.0257 | 0.0444 |
| corners_ft_total | 11.5 | poisson | platt | 760 | 36.1% | 35.5% | 0.2268 | 0.6453 | 0.0236 | 0.0457 |
| goals_1h_total | 0.5 | league_freq | isotonic | 760 | 75.7% | 80.9% | 0.1909 | 0.5798 | 0.0596 ⚠ | 0.0293 |
| goals_1h_total | 0.5 | negbin | platt | 760 | 75.7% | 73.8% | 0.1818 | 0.5489 | 0.0350 ≈ | 0.0370 |
| goals_1h_total | 0.5 | poisson | platt | 760 | 75.7% | 73.8% | 0.1818 | 0.5489 | 0.0350 ≈ | 0.0370 |
| goals_1h_total | 1.5 | league_freq | isotonic | 760 | 39.2% | 38.6% | 0.2402 | 0.6735 | 0.0388 ≈ | 0.0428 |
| goals_1h_total | 1.5 | negbin | platt | 760 | 39.2% | 38.3% | 0.2393 | 0.6717 | 0.0286 | 0.0451 |
| goals_1h_total | 1.5 | poisson | platt | 760 | 39.2% | 38.3% | 0.2393 | 0.6717 | 0.0286 | 0.0451 |
| goals_ft_total | 0.5 | dixon_coles | platt | 760 | 96.4% | 94.6% | 0.0345 | 0.1558 | 0.0182 | 0.0147 |
| goals_ft_total | 0.5 | league_freq | identity | 760 | 96.4% | 95.8% | 0.0345 | 0.1559 | 0.0063 | 0.0142 |
| goals_ft_total | 0.5 | negbin | platt | 760 | 96.4% | 94.5% | 0.0346 | 0.1564 | 0.0190 | 0.0150 |
| goals_ft_total | 0.5 | poisson | platt | 760 | 96.4% | 94.5% | 0.0346 | 0.1564 | 0.0190 | 0.0150 |
| goals_ft_total | 1.5 | dixon_coles | platt | 760 | 83.7% | 79.4% | 0.1379 | 0.4488 | 0.0429 ⚠ | 0.0314 |
| goals_ft_total | 1.5 | league_freq | identity | 760 | 83.7% | 81.4% | 0.1384 | 0.4510 | 0.0231 | 0.0311 |
| goals_ft_total | 1.5 | negbin | platt | 760 | 83.7% | 79.5% | 0.1377 | 0.4482 | 0.0417 ⚠ | 0.0322 |
| goals_ft_total | 1.5 | poisson | platt | 760 | 83.7% | 79.5% | 0.1377 | 0.4482 | 0.0417 ⚠ | 0.0319 |
| goals_ft_total | 2.5 | dixon_coles | platt | 760 | 60.7% | 56.9% | 0.2397 | 0.6723 | 0.0557 ⚠ | 0.0457 |
| goals_ft_total | 2.5 | league_freq | identity | 760 | 60.7% | 59.0% | 0.2410 | 0.6752 | 0.0468 ⚠ | 0.0389 |
| goals_ft_total | 2.5 | negbin | platt | 760 | 60.7% | 56.9% | 0.2397 | 0.6723 | 0.0557 ⚠ | 0.0457 |
| goals_ft_total | 2.5 | poisson | platt | 760 | 60.7% | 56.9% | 0.2397 | 0.6723 | 0.0557 ⚠ | 0.0457 |
| goals_ft_total | 3.5 | dixon_coles | platt | 760 | 38.9% | 34.6% | 0.2414 | 0.6769 | 0.0559 ⚠ | 0.0441 |
| goals_ft_total | 3.5 | league_freq | identity | 760 | 38.9% | 37.5% | 0.2400 | 0.6732 | 0.0257 | 0.0368 |
| goals_ft_total | 3.5 | negbin | platt | 760 | 38.9% | 34.6% | 0.2414 | 0.6769 | 0.0559 ⚠ | 0.0441 |
| goals_ft_total | 3.5 | poisson | platt | 760 | 38.9% | 34.6% | 0.2414 | 0.6769 | 0.0559 ⚠ | 0.0441 |

⚠ = ECE por encima del objetivo de 0.03 y del ruido de muestreo. ≈ = por encima de 0.03 pero indistinguible del ruido: un modelo perfectamente calibrado con estas mismas probabilidades y este tamaño de muestra mostraría una ECE así al menos el 5% de las veces.

## 4. Modelos frente al baseline ingenuo (test)

Diferencia de log loss por observación (modelo menos baseline; negativo = mejor), intervalo bootstrap 95% remuestreando partidos.

| Mercado | Línea | Familia | N | Δ log loss | IC 95% | Lectura |
| --- | ---: | --- | ---: | ---: | --- | --- |
| corners_1h_total | 2.5 | negbin | 721 | -0.00104 | [-0.00477, 0.00260] | sin diferencia concluyente |
| corners_1h_total | 2.5 | poisson | 721 | -0.00127 | [-0.00526, 0.00265] | sin diferencia concluyente |
| corners_1h_total | 3.5 | negbin | 721 | -0.00260 | [-0.00661, 0.00160] | sin diferencia concluyente |
| corners_1h_total | 3.5 | poisson | 721 | -0.00268 | [-0.00706, 0.00183] | sin diferencia concluyente |
| corners_1h_total | 4.5 | negbin | 721 | -0.00381 | [-0.00946, 0.00244] | sin diferencia concluyente |
| corners_1h_total | 4.5 | poisson | 721 | -0.00302 | [-0.00859, 0.00311] | sin diferencia concluyente |
| corners_1h_total | 5.5 | negbin | 721 | -0.00274 | [-0.00895, 0.00363] | sin diferencia concluyente |
| corners_1h_total | 5.5 | poisson | 721 | -0.00135 | [-0.00760, 0.00466] | sin diferencia concluyente |
| corners_ft_total | 7.5 | negbin | 760 | -0.00892 | [-0.01532, -0.00186] | mejor que el baseline |
| corners_ft_total | 7.5 | poisson | 760 | -0.00879 | [-0.01503, -0.00222] | mejor que el baseline |
| corners_ft_total | 8.5 | negbin | 760 | -0.00779 | [-0.01610, 0.00115] | sin diferencia concluyente |
| corners_ft_total | 8.5 | poisson | 760 | -0.00743 | [-0.01510, 0.00091] | sin diferencia concluyente |
| corners_ft_total | 9.5 | negbin | 760 | -0.00638 | [-0.01141, -0.00096] | mejor que el baseline |
| corners_ft_total | 9.5 | poisson | 760 | -0.00605 | [-0.01094, -0.00075] | mejor que el baseline |
| corners_ft_total | 10.5 | negbin | 760 | -0.00557 | [-0.01278, 0.00260] | sin diferencia concluyente |
| corners_ft_total | 10.5 | poisson | 760 | -0.00529 | [-0.01224, 0.00245] | sin diferencia concluyente |
| corners_ft_total | 11.5 | negbin | 760 | -0.01240 | [-0.01922, -0.00481] | mejor que el baseline |
| corners_ft_total | 11.5 | poisson | 760 | -0.01219 | [-0.01882, -0.00499] | mejor que el baseline |
| goals_1h_total | 0.5 | negbin | 760 | -0.03091 | [-0.05037, -0.01110] | mejor que el baseline |
| goals_1h_total | 0.5 | poisson | 760 | -0.03091 | [-0.05037, -0.01110] | mejor que el baseline |
| goals_1h_total | 1.5 | negbin | 760 | -0.00178 | [-0.00883, 0.00541] | sin diferencia concluyente |
| goals_1h_total | 1.5 | poisson | 760 | -0.00178 | [-0.00883, 0.00541] | sin diferencia concluyente |
| goals_ft_total | 0.5 | dixon_coles | 760 | -0.00014 | [-0.00498, 0.00472] | sin diferencia concluyente |
| goals_ft_total | 0.5 | negbin | 760 | 0.00043 | [-0.00447, 0.00527] | sin diferencia concluyente |
| goals_ft_total | 0.5 | poisson | 760 | 0.00043 | [-0.00448, 0.00526] | sin diferencia concluyente |
| goals_ft_total | 1.5 | dixon_coles | 760 | -0.00218 | [-0.00877, 0.00410] | sin diferencia concluyente |
| goals_ft_total | 1.5 | negbin | 760 | -0.00279 | [-0.00955, 0.00381] | sin diferencia concluyente |
| goals_ft_total | 1.5 | poisson | 760 | -0.00281 | [-0.00958, 0.00381] | sin diferencia concluyente |
| goals_ft_total | 2.5 | dixon_coles | 760 | -0.00287 | [-0.01165, 0.00579] | sin diferencia concluyente |
| goals_ft_total | 2.5 | negbin | 760 | -0.00287 | [-0.01165, 0.00578] | sin diferencia concluyente |
| goals_ft_total | 2.5 | poisson | 760 | -0.00287 | [-0.01165, 0.00579] | sin diferencia concluyente |
| goals_ft_total | 3.5 | dixon_coles | 760 | 0.00368 | [-0.00592, 0.01354] | sin diferencia concluyente |
| goals_ft_total | 3.5 | negbin | 760 | 0.00368 | [-0.00592, 0.01355] | sin diferencia concluyente |
| goals_ft_total | 3.5 | poisson | 760 | 0.00368 | [-0.00592, 0.01354] | sin diferencia concluyente |

## 5. Comparación con el mercado

Mercado `goals_ft_total` línea 2.5. Cuotas pre-partido usables en `as_of`: 0 (casas: {}); margen medio n/d. Cuotas de cierre (solo evaluación): 760.

| Modelo | Calibrador | Frente a | N | LL modelo | LL mercado | Δ LL (IC 95%) | |edge| medio |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| dixon_coles | platt | closing | 760 | 0.6723 | 0.6635 | 0.00880 [0.00161, 0.01661] | 4.2% |
| league_freq | identity | closing | 760 | 0.6752 | 0.6635 | 0.01167 [0.00176, 0.02136] | 5.4% |
| negbin | platt | closing | 760 | 0.6723 | 0.6635 | 0.00880 [0.00161, 0.01660] | 4.2% |
| poisson | platt | closing | 760 | 0.6723 | 0.6635 | 0.00880 [0.00161, 0.01661] | 4.2% |

### Simulación paper (stake plano, sin dinero real)

| Modelo | Apuestas | ROI | IC 95% ROI | Acierto | Edge medio | CLV medio | Drawdown máx. |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| dixon_coles | 0 | n/d | n/d | n/d | n/d | n/d | 0.0 |
| league_freq | 0 | n/d | n/d | n/d | n/d | n/d | 0.0 |
| negbin | 0 | n/d | n/d | n/d | n/d | n/d | 0.0 |
| poisson | 0 | n/d | n/d | n/d | n/d | n/d | 0.0 |

Un ROI positivo con un intervalo que incluye el cero no es evidencia de edge. El CLV positivo frente al cierre es una señal más estable que el ROI en muestras pequeñas.

## 6. Criterios de éxito

1. Reproducibilidad: dataset `dataset-42wyw3f7evnhqy3x`, configuración `a9db12159ac32b8f`, código `bd1bd2d`. Verificar re-ejecutando: el `summary.json` debe ser idéntico.
2. Sin leakage: **cumple**.
3. Calibración (ECE < 0.03 en test, o indistinguible del ruido de muestreo): peor ECE 0.0647; 24 combinaciones bajo el objetivo, 9 dentro del ruido, 16 fuera: **no cumple en todos los mercados**.
4. Frente al baseline: 8 combinaciones mejores, 0 peores, 26 sin diferencia concluyente.
5. Reconstrucción: cada predicción está en `predictions` con su `feature_snapshot_id` y su liquidación.
