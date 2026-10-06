# EXP001A: informe de resultados

> Probabilidad no es certeza. Edge no es garantía de resultado. Simulación sin dinero real.

| Campo | Valor |
| --- | --- |
| backtest_run_id | `bt_y9fb6smbnpxfts6t` |
| dataset_version | `dataset-zjerthrmayqtf7xv` |
| config_hash | `8c0129fca987303e` |
| code_version | `91609fc` |
| provider | `football_data_csv` |
| n_predictions | `430920` |
| n_snapshots | `116280` |
| coherence_violations | `0` |
| ingesta | 7 ficheros, 2660 partidos, 37950 cuotas, 1 incidencias de calidad |

## 1. Integridad (leakage)

- Todas las predicciones usan solo datos con `available_at <= as_of`: **sí**.
- Coherencia entre líneas (P(Over) no crece con la línea): **0 violaciones**.

## 2. Selección en validación

Elegido por log loss medio en las temporadas de validación; el test no interviene en la elección.

| Objetivo | Familia | Modelo | Calibrador | Log loss | Brier | ECE |
| --- | --- | --- | --- | ---: | ---: | ---: |
| corners_FT | league_freq | `jevs-corners-ft-league_freq-xi0.0019-w730-r1-v1` | isotonic | 0.6326 | 0.2209 | 0.0091 |
| corners_FT | negbin | `jevs-corners-ft-negbin-xi0.0039-w730-r1-v1` | platt | 0.6303 | 0.2199 | 0.0066 |
| corners_FT | poisson | `jevs-corners-ft-poisson-xi0.0039-w730-r1-v1` | platt | 0.6303 | 0.2199 | 0.0061 |
| goals_1H | league_freq | `jevs-goals-1h-league_freq-xi0.0039-w730-r1-v1` | isotonic | 0.6248 | 0.2168 | 0.0062 |
| goals_1H | negbin | `jevs-goals-1h-negbin-xi0-w730-r4-v1` | platt | 0.6238 | 0.2163 | 0.0285 |
| goals_1H | poisson | `jevs-goals-1h-poisson-xi0-w730-r4-v1` | platt | 0.6238 | 0.2163 | 0.0285 |
| goals_FT | dixon_coles | `jevs-goals-ft-dixon_coles-xi0.0039-w730-r4-v1` | platt | 0.5249 | 0.1760 | 0.0194 |
| goals_FT | league_freq | `jevs-goals-ft-league_freq-xi0.0019-w730-r1-v1` | identity | 0.5282 | 0.1776 | 0.0062 |
| goals_FT | negbin | `jevs-goals-ft-negbin-xi0.0039-w730-r4-v1` | platt | 0.5249 | 0.1760 | 0.0197 |
| goals_FT | poisson | `jevs-goals-ft-poisson-xi0.0039-w730-r4-v1` | platt | 0.5249 | 0.1760 | 0.0198 |

## 3. Test fuera de muestra

| Mercado | Línea | Familia | Calibrador | N | Tasa real | P media | Brier | Log loss | ECE | Ruido ECE (p95) |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| corners_ft_total | 7.5 | league_freq | isotonic | 760 | 79.9% | 79.6% | 0.1613 | 0.5039 | 0.0199 | 0.0308 |
| corners_ft_total | 7.5 | negbin | platt | 760 | 79.9% | 80.0% | 0.1585 | 0.4957 | 0.0157 | 0.0320 |
| corners_ft_total | 7.5 | poisson | platt | 760 | 79.9% | 79.7% | 0.1585 | 0.4958 | 0.0076 | 0.0334 |
| corners_ft_total | 8.5 | league_freq | isotonic | 760 | 72.4% | 69.8% | 0.2015 | 0.5932 | 0.0373 ≈ | 0.0374 |
| corners_ft_total | 8.5 | negbin | platt | 760 | 72.4% | 70.6% | 0.1985 | 0.5865 | 0.0203 | 0.0415 |
| corners_ft_total | 8.5 | poisson | platt | 760 | 72.4% | 70.2% | 0.1987 | 0.5868 | 0.0289 | 0.0398 |
| corners_ft_total | 9.5 | league_freq | isotonic | 760 | 60.7% | 56.8% | 0.2403 | 0.6737 | 0.0383 ⚠ | 0.0367 |
| corners_ft_total | 9.5 | negbin | platt | 760 | 60.7% | 57.7% | 0.2378 | 0.6685 | 0.0350 ≈ | 0.0429 |
| corners_ft_total | 9.5 | poisson | platt | 760 | 60.7% | 57.5% | 0.2379 | 0.6688 | 0.0345 ≈ | 0.0419 |
| corners_ft_total | 10.5 | league_freq | isotonic | 760 | 50.4% | 46.9% | 0.2526 | 0.6984 | 0.0347 ≈ | 0.0403 |
| corners_ft_total | 10.5 | negbin | platt | 760 | 50.4% | 45.9% | 0.2494 | 0.6920 | 0.0520 ⚠ | 0.0468 |
| corners_ft_total | 10.5 | poisson | platt | 760 | 50.4% | 45.8% | 0.2496 | 0.6923 | 0.0547 ⚠ | 0.0449 |
| corners_ft_total | 11.5 | league_freq | isotonic | 760 | 36.4% | 36.1% | 0.2328 | 0.6584 | 0.0035 | 0.0359 |
| corners_ft_total | 11.5 | negbin | platt | 760 | 36.4% | 36.1% | 0.2281 | 0.6480 | 0.0212 | 0.0437 |
| corners_ft_total | 11.5 | poisson | platt | 760 | 36.4% | 36.1% | 0.2281 | 0.6481 | 0.0127 | 0.0425 |
| goals_1h_total | 0.5 | league_freq | isotonic | 760 | 75.7% | 80.8% | 0.1909 | 0.5799 | 0.0607 ⚠ | 0.0301 |
| goals_1h_total | 0.5 | negbin | platt | 760 | 75.7% | 73.9% | 0.1818 | 0.5489 | 0.0348 ≈ | 0.0368 |
| goals_1h_total | 0.5 | poisson | platt | 760 | 75.7% | 73.9% | 0.1818 | 0.5489 | 0.0348 ≈ | 0.0368 |
| goals_1h_total | 1.5 | league_freq | isotonic | 760 | 39.2% | 38.7% | 0.2401 | 0.6733 | 0.0372 ≈ | 0.0414 |
| goals_1h_total | 1.5 | negbin | platt | 760 | 39.2% | 38.4% | 0.2393 | 0.6717 | 0.0289 | 0.0421 |
| goals_1h_total | 1.5 | poisson | platt | 760 | 39.2% | 38.4% | 0.2393 | 0.6717 | 0.0289 | 0.0421 |
| goals_ft_total | 0.5 | dixon_coles | platt | 760 | 96.4% | 94.6% | 0.0345 | 0.1558 | 0.0182 | 0.0156 |
| goals_ft_total | 0.5 | league_freq | identity | 760 | 96.4% | 95.8% | 0.0345 | 0.1559 | 0.0063 | 0.0142 |
| goals_ft_total | 0.5 | negbin | platt | 760 | 96.4% | 94.5% | 0.0346 | 0.1564 | 0.0190 | 0.0153 |
| goals_ft_total | 0.5 | poisson | platt | 760 | 96.4% | 94.5% | 0.0346 | 0.1564 | 0.0190 | 0.0153 |
| goals_ft_total | 1.5 | dixon_coles | platt | 760 | 83.7% | 79.4% | 0.1379 | 0.4488 | 0.0428 ⚠ | 0.0326 |
| goals_ft_total | 1.5 | league_freq | identity | 760 | 83.7% | 81.4% | 0.1384 | 0.4510 | 0.0231 | 0.0311 |
| goals_ft_total | 1.5 | negbin | platt | 760 | 83.7% | 79.5% | 0.1377 | 0.4482 | 0.0416 ⚠ | 0.0321 |
| goals_ft_total | 1.5 | poisson | platt | 760 | 83.7% | 79.5% | 0.1377 | 0.4482 | 0.0416 ⚠ | 0.0329 |
| goals_ft_total | 2.5 | dixon_coles | platt | 760 | 60.7% | 57.0% | 0.2397 | 0.6723 | 0.0506 ⚠ | 0.0449 |
| goals_ft_total | 2.5 | league_freq | identity | 760 | 60.7% | 59.0% | 0.2410 | 0.6752 | 0.0468 ⚠ | 0.0389 |
| goals_ft_total | 2.5 | negbin | platt | 760 | 60.7% | 57.0% | 0.2397 | 0.6722 | 0.0506 ⚠ | 0.0449 |
| goals_ft_total | 2.5 | poisson | platt | 760 | 60.7% | 57.0% | 0.2397 | 0.6723 | 0.0506 ⚠ | 0.0449 |
| goals_ft_total | 3.5 | dixon_coles | platt | 760 | 38.9% | 34.7% | 0.2414 | 0.6769 | 0.0576 ⚠ | 0.0449 |
| goals_ft_total | 3.5 | league_freq | identity | 760 | 38.9% | 37.5% | 0.2400 | 0.6732 | 0.0257 | 0.0368 |
| goals_ft_total | 3.5 | negbin | platt | 760 | 38.9% | 34.7% | 0.2414 | 0.6769 | 0.0576 ⚠ | 0.0462 |
| goals_ft_total | 3.5 | poisson | platt | 760 | 38.9% | 34.7% | 0.2414 | 0.6769 | 0.0576 ⚠ | 0.0449 |

⚠ = ECE por encima del objetivo de 0.03 y del ruido de muestreo. ≈ = por encima de 0.03 pero indistinguible del ruido: un modelo perfectamente calibrado con estas mismas probabilidades y este tamaño de muestra mostraría una ECE así al menos el 5% de las veces.

## 4. Modelos frente al baseline ingenuo (test)

Diferencia de log loss por observación (modelo menos baseline; negativo = mejor), intervalo bootstrap 95% remuestreando partidos.

| Mercado | Línea | Familia | N | Δ log loss | IC 95% | Lectura |
| --- | ---: | --- | ---: | ---: | --- | --- |
| corners_ft_total | 7.5 | negbin | 760 | -0.00829 | [-0.01571, -0.00138] | mejor que el baseline |
| corners_ft_total | 7.5 | poisson | 760 | -0.00811 | [-0.01531, -0.00153] | mejor que el baseline |
| corners_ft_total | 8.5 | negbin | 760 | -0.00671 | [-0.01509, 0.00157] | sin diferencia concluyente |
| corners_ft_total | 8.5 | poisson | 760 | -0.00633 | [-0.01436, 0.00141] | sin diferencia concluyente |
| corners_ft_total | 9.5 | negbin | 760 | -0.00520 | [-0.00975, -0.00011] | mejor que el baseline |
| corners_ft_total | 9.5 | poisson | 760 | -0.00489 | [-0.00923, -0.00012] | mejor que el baseline |
| corners_ft_total | 10.5 | negbin | 760 | -0.00641 | [-0.01328, 0.00081] | sin diferencia concluyente |
| corners_ft_total | 10.5 | poisson | 760 | -0.00608 | [-0.01278, 0.00096] | sin diferencia concluyente |
| corners_ft_total | 11.5 | negbin | 760 | -0.01048 | [-0.01750, -0.00331] | mejor que el baseline |
| corners_ft_total | 11.5 | poisson | 760 | -0.01029 | [-0.01699, -0.00342] | mejor que el baseline |
| goals_1h_total | 0.5 | negbin | 760 | -0.03095 | [-0.05116, -0.01219] | mejor que el baseline |
| goals_1h_total | 0.5 | poisson | 760 | -0.03095 | [-0.05116, -0.01219] | mejor que el baseline |
| goals_1h_total | 1.5 | negbin | 760 | -0.00162 | [-0.00846, 0.00516] | sin diferencia concluyente |
| goals_1h_total | 1.5 | poisson | 760 | -0.00162 | [-0.00846, 0.00516] | sin diferencia concluyente |
| goals_ft_total | 0.5 | dixon_coles | 760 | -0.00012 | [-0.00530, 0.00453] | sin diferencia concluyente |
| goals_ft_total | 0.5 | negbin | 760 | 0.00045 | [-0.00466, 0.00500] | sin diferencia concluyente |
| goals_ft_total | 0.5 | poisson | 760 | 0.00044 | [-0.00468, 0.00499] | sin diferencia concluyente |
| goals_ft_total | 1.5 | dixon_coles | 760 | -0.00221 | [-0.00907, 0.00421] | sin diferencia concluyente |
| goals_ft_total | 1.5 | negbin | 760 | -0.00283 | [-0.00979, 0.00364] | sin diferencia concluyente |
| goals_ft_total | 1.5 | poisson | 760 | -0.00285 | [-0.00979, 0.00363] | sin diferencia concluyente |
| goals_ft_total | 2.5 | dixon_coles | 760 | -0.00292 | [-0.01181, 0.00561] | sin diferencia concluyente |
| goals_ft_total | 2.5 | negbin | 760 | -0.00292 | [-0.01181, 0.00561] | sin diferencia concluyente |
| goals_ft_total | 2.5 | poisson | 760 | -0.00292 | [-0.01181, 0.00561] | sin diferencia concluyente |
| goals_ft_total | 3.5 | dixon_coles | 760 | 0.00366 | [-0.00661, 0.01435] | sin diferencia concluyente |
| goals_ft_total | 3.5 | negbin | 760 | 0.00366 | [-0.00661, 0.01436] | sin diferencia concluyente |
| goals_ft_total | 3.5 | poisson | 760 | 0.00366 | [-0.00661, 0.01435] | sin diferencia concluyente |

## 5. Comparación con el mercado

Mercado `goals_ft_total` línea 2.5. Cuotas pre-partido usables en `as_of`: 760 (casas: {'pinnacle': 749, 'market_avg': 11}); margen medio 1.0367. Cuotas de cierre (solo evaluación): 760.

| Modelo | Calibrador | Frente a | N | LL modelo | LL mercado | Δ LL (IC 95%) | |edge| medio |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| dixon_coles | platt | prematch | 760 | 0.6723 | 0.6627 | 0.00959 [0.00166, 0.01776] | 4.4% |
| dixon_coles | platt | closing | 760 | 0.6723 | 0.6612 | 0.01110 [0.00186, 0.02039] | 5.1% |
| league_freq | identity | prematch | 760 | 0.6752 | 0.6627 | 0.01251 [0.00168, 0.02311] | 6.0% |
| league_freq | identity | closing | 760 | 0.6752 | 0.6612 | 0.01402 [0.00219, 0.02633] | 6.6% |
| negbin | platt | prematch | 760 | 0.6722 | 0.6627 | 0.00959 [0.00166, 0.01775] | 4.4% |
| negbin | platt | closing | 760 | 0.6722 | 0.6612 | 0.01110 [0.00186, 0.02038] | 5.1% |
| poisson | platt | prematch | 760 | 0.6723 | 0.6627 | 0.00959 [0.00166, 0.01776] | 4.4% |
| poisson | platt | closing | 760 | 0.6723 | 0.6612 | 0.01110 [0.00186, 0.02039] | 5.1% |

### Simulación paper (stake plano, sin dinero real)

| Modelo | Apuestas | ROI | IC 95% ROI | Acierto | Edge medio | CLV medio | Drawdown máx. |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| dixon_coles | 434 | -5.6% | [-16.3%, 6.4%] | 40.3% | 6.7% | -3.6% | 43.9 |
| league_freq | 542 | -5.8% | [-15.3%, 3.9%] | 41.7% | 7.9% | -4.2% | 48.8 |
| negbin | 433 | -5.4% | [-16.0%, 5.6%] | 40.4% | 6.7% | -3.6% | 43.9 |
| poisson | 434 | -5.6% | [-16.3%, 6.4%] | 40.3% | 6.7% | -3.6% | 43.9 |

Un ROI positivo con un intervalo que incluye el cero no es evidencia de edge. El CLV positivo frente al cierre es una señal más estable que el ROI en muestras pequeñas.

## 6. Criterios de éxito

1. Reproducibilidad: dataset `dataset-zjerthrmayqtf7xv`, configuración `8c0129fca987303e`, código `91609fc`. Verificar re-ejecutando: el `summary.json` debe ser idéntico.
2. Sin leakage: **cumple**.
3. Calibración (ECE < 0.03 en test, o indistinguible del ruido de muestreo): peor ECE 0.0607; 16 combinaciones bajo el objetivo, 7 dentro del ruido, 14 fuera: **no cumple en todos los mercados**.
4. Frente al baseline: 8 combinaciones mejores, 0 peores, 18 sin diferencia concluyente.
5. Reconstrucción: cada predicción está en `predictions` con su `feature_snapshot_id` y su liquidación.
