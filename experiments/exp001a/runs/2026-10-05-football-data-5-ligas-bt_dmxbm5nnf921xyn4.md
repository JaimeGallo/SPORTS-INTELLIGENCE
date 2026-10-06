# EXP001A: informe de resultados

> Probabilidad no es certeza. Edge no es garantía de resultado. Simulación sin dinero real.

| Campo | Valor |
| --- | --- |
| backtest_run_id | `bt_dmxbm5nnf921xyn4` |
| dataset_version | `dataset-s5h5r6zcvxdj91c5` |
| config_hash | `dcfc83fa4d94f18d` |
| code_version | `91609fc` |
| provider | `football_data_csv` |
| n_predictions | `3389853` |
| n_snapshots | `914712` |
| coherence_violations | `0` |
| ingesta | 55 ficheros, 19763 partidos, 224796 cuotas, 10 incidencias de calidad |

## 1. Integridad (leakage)

- Todas las predicciones usan solo datos con `available_at <= as_of`: **sí**.
- Coherencia entre líneas (P(Over) no crece con la línea): **0 violaciones**.

## 2. Selección en validación

Elegido por log loss medio en las temporadas de validación; el test no interviene en la elección.

| Objetivo | Familia | Modelo | Calibrador | Log loss | Brier | ECE |
| --- | --- | --- | --- | ---: | ---: | ---: |
| corners_FT | league_freq | `jevs-corners-ft-league_freq-xi0.0039-w730-r1-v1` | identity | 0.6346 | 0.2218 | 0.0037 |
| corners_FT | negbin | `jevs-corners-ft-negbin-xi0.0019-w730-r4-v1` | platt | 0.6297 | 0.2196 | 0.0049 |
| corners_FT | poisson | `jevs-corners-ft-poisson-xi0.0019-w730-r4-v1` | platt | 0.6297 | 0.2196 | 0.0051 |
| goals_1H | league_freq | `jevs-goals-1h-league_freq-xi0-w730-r1-v1` | identity | 0.6231 | 0.2159 | 0.0036 |
| goals_1H | negbin | `jevs-goals-1h-negbin-xi0.0019-w730-r4-v1` | platt | 0.6193 | 0.2143 | 0.0042 |
| goals_1H | poisson | `jevs-goals-1h-poisson-xi0.0019-w730-r4-v1` | platt | 0.6193 | 0.2143 | 0.0040 |
| goals_FT | dixon_coles | `jevs-goals-ft-dixon_coles-xi0.0019-w730-r4-v1` | platt | 0.5147 | 0.1718 | 0.0040 |
| goals_FT | league_freq | `jevs-goals-ft-league_freq-xi0.0039-w730-r1-v1` | identity | 0.5202 | 0.1741 | 0.0019 |
| goals_FT | negbin | `jevs-goals-ft-negbin-xi0.0019-w730-r4-v1` | platt | 0.5147 | 0.1718 | 0.0040 |
| goals_FT | poisson | `jevs-goals-ft-poisson-xi0.0019-w730-r4-v1` | platt | 0.5147 | 0.1718 | 0.0041 |

## 3. Test fuera de muestra

| Mercado | Línea | Familia | Calibrador | N | Tasa real | P media | Brier | Log loss | ECE | Ruido ECE (p95) |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| corners_ft_total | 7.5 | league_freq | identity | 3503 | 71.2% | 72.1% | 0.2048 | 0.5997 | 0.0100 | 0.0185 |
| corners_ft_total | 7.5 | negbin | platt | 3503 | 71.2% | 72.9% | 0.2027 | 0.5949 | 0.0177 | 0.0187 |
| corners_ft_total | 7.5 | poisson | platt | 3503 | 71.2% | 72.9% | 0.2028 | 0.5952 | 0.0186 | 0.0187 |
| corners_ft_total | 8.5 | league_freq | identity | 3503 | 60.1% | 61.0% | 0.2382 | 0.6692 | 0.0132 | 0.0208 |
| corners_ft_total | 8.5 | negbin | platt | 3503 | 60.1% | 61.9% | 0.2363 | 0.6655 | 0.0202 | 0.0210 |
| corners_ft_total | 8.5 | poisson | platt | 3503 | 60.1% | 61.9% | 0.2364 | 0.6657 | 0.0205 | 0.0212 |
| corners_ft_total | 9.5 | league_freq | identity | 3503 | 49.3% | 49.8% | 0.2478 | 0.6887 | 0.0050 | 0.0221 |
| corners_ft_total | 9.5 | negbin | platt | 3503 | 49.3% | 49.9% | 0.2455 | 0.6841 | 0.0140 | 0.0219 |
| corners_ft_total | 9.5 | poisson | platt | 3503 | 49.3% | 49.8% | 0.2456 | 0.6843 | 0.0135 | 0.0219 |
| corners_ft_total | 10.5 | league_freq | identity | 3503 | 37.8% | 38.8% | 0.2334 | 0.6595 | 0.0111 | 0.0201 |
| corners_ft_total | 10.5 | negbin | platt | 3503 | 37.8% | 38.1% | 0.2318 | 0.6562 | 0.0057 | 0.0218 |
| corners_ft_total | 10.5 | poisson | platt | 3503 | 37.8% | 38.1% | 0.2318 | 0.6562 | 0.0043 | 0.0219 |
| corners_ft_total | 11.5 | league_freq | identity | 3503 | 27.1% | 27.6% | 0.1968 | 0.5822 | 0.0111 | 0.0186 |
| corners_ft_total | 11.5 | negbin | platt | 3503 | 27.1% | 27.6% | 0.1946 | 0.5769 | 0.0122 | 0.0191 |
| corners_ft_total | 11.5 | poisson | platt | 3503 | 27.1% | 27.5% | 0.1945 | 0.5767 | 0.0112 | 0.0194 |
| goals_1h_total | 0.5 | league_freq | identity | 3503 | 71.7% | 72.3% | 0.2023 | 0.5942 | 0.0060 | 0.0168 |
| goals_1h_total | 0.5 | negbin | platt | 3503 | 71.7% | 71.4% | 0.2011 | 0.5912 | 0.0023 | 0.0182 |
| goals_1h_total | 0.5 | poisson | platt | 3503 | 71.7% | 71.4% | 0.2011 | 0.5912 | 0.0025 | 0.0176 |
| goals_1h_total | 1.5 | league_freq | identity | 3503 | 34.3% | 36.1% | 0.2236 | 0.6392 | 0.0179 | 0.0186 |
| goals_1h_total | 1.5 | negbin | platt | 3503 | 34.3% | 35.6% | 0.2226 | 0.6369 | 0.0128 | 0.0202 |
| goals_1h_total | 1.5 | poisson | platt | 3503 | 34.3% | 35.6% | 0.2226 | 0.6369 | 0.0127 | 0.0199 |
| goals_ft_total | 0.5 | dixon_coles | platt | 3504 | 93.9% | 93.5% | 0.0573 | 0.2280 | 0.0035 | 0.0090 |
| goals_ft_total | 0.5 | league_freq | identity | 3504 | 93.9% | 93.9% | 0.0576 | 0.2311 | 0.0014 | 0.0077 |
| goals_ft_total | 0.5 | negbin | platt | 3504 | 93.9% | 93.5% | 0.0573 | 0.2280 | 0.0039 | 0.0088 |
| goals_ft_total | 0.5 | poisson | platt | 3504 | 93.9% | 93.5% | 0.0573 | 0.2280 | 0.0039 | 0.0087 |
| goals_ft_total | 1.5 | dixon_coles | platt | 3504 | 77.2% | 77.3% | 0.1736 | 0.5298 | 0.0041 | 0.0169 |
| goals_ft_total | 1.5 | league_freq | identity | 3504 | 77.2% | 77.7% | 0.1754 | 0.5352 | 0.0119 | 0.0168 |
| goals_ft_total | 1.5 | negbin | platt | 3504 | 77.2% | 77.3% | 0.1737 | 0.5299 | 0.0043 | 0.0168 |
| goals_ft_total | 1.5 | poisson | platt | 3504 | 77.2% | 77.3% | 0.1737 | 0.5299 | 0.0044 | 0.0170 |
| goals_ft_total | 2.5 | dixon_coles | platt | 3504 | 53.2% | 53.6% | 0.2436 | 0.6800 | 0.0102 | 0.0230 |
| goals_ft_total | 2.5 | league_freq | identity | 3504 | 53.2% | 53.7% | 0.2474 | 0.6880 | 0.0122 | 0.0216 |
| goals_ft_total | 2.5 | negbin | platt | 3504 | 53.2% | 53.6% | 0.2436 | 0.6800 | 0.0101 | 0.0230 |
| goals_ft_total | 2.5 | poisson | platt | 3504 | 53.2% | 53.6% | 0.2436 | 0.6800 | 0.0102 | 0.0230 |
| goals_ft_total | 3.5 | dixon_coles | platt | 3504 | 30.8% | 31.2% | 0.2066 | 0.6022 | 0.0061 | 0.0199 |
| goals_ft_total | 3.5 | league_freq | identity | 3504 | 30.8% | 31.7% | 0.2097 | 0.6096 | 0.0092 | 0.0183 |
| goals_ft_total | 3.5 | negbin | platt | 3504 | 30.8% | 31.2% | 0.2066 | 0.6022 | 0.0061 | 0.0199 |
| goals_ft_total | 3.5 | poisson | platt | 3504 | 30.8% | 31.2% | 0.2066 | 0.6022 | 0.0061 | 0.0199 |

⚠ = ECE por encima del objetivo de 0.03 y del ruido de muestreo. ≈ = por encima de 0.03 pero indistinguible del ruido: un modelo perfectamente calibrado con estas mismas probabilidades y este tamaño de muestra mostraría una ECE así al menos el 5% de las veces.

## 4. Modelos frente al baseline ingenuo (test)

Diferencia de log loss por observación (modelo menos baseline; negativo = mejor), intervalo bootstrap 95% remuestreando partidos.

| Mercado | Línea | Familia | N | Δ log loss | IC 95% | Lectura |
| --- | ---: | --- | ---: | ---: | --- | --- |
| corners_ft_total | 7.5 | negbin | 3503 | -0.00478 | [-0.00911, -0.00065] | mejor que el baseline |
| corners_ft_total | 7.5 | poisson | 3503 | -0.00454 | [-0.00898, -0.00019] | mejor que el baseline |
| corners_ft_total | 8.5 | negbin | 3503 | -0.00364 | [-0.00834, 0.00098] | sin diferencia concluyente |
| corners_ft_total | 8.5 | poisson | 3503 | -0.00347 | [-0.00821, 0.00122] | sin diferencia concluyente |
| corners_ft_total | 9.5 | negbin | 3503 | -0.00455 | [-0.00898, -0.00009] | mejor que el baseline |
| corners_ft_total | 9.5 | poisson | 3503 | -0.00444 | [-0.00890, 0.00010] | sin diferencia concluyente |
| corners_ft_total | 10.5 | negbin | 3503 | -0.00332 | [-0.00805, 0.00151] | sin diferencia concluyente |
| corners_ft_total | 10.5 | poisson | 3503 | -0.00331 | [-0.00799, 0.00152] | sin diferencia concluyente |
| corners_ft_total | 11.5 | negbin | 3503 | -0.00532 | [-0.00940, -0.00125] | mejor que el baseline |
| corners_ft_total | 11.5 | poisson | 3503 | -0.00556 | [-0.00959, -0.00149] | mejor que el baseline |
| goals_1h_total | 0.5 | negbin | 3503 | -0.00299 | [-0.00658, 0.00055] | sin diferencia concluyente |
| goals_1h_total | 0.5 | poisson | 3503 | -0.00299 | [-0.00658, 0.00054] | sin diferencia concluyente |
| goals_1h_total | 1.5 | negbin | 3503 | -0.00228 | [-0.00598, 0.00127] | sin diferencia concluyente |
| goals_1h_total | 1.5 | poisson | 3503 | -0.00229 | [-0.00599, 0.00127] | sin diferencia concluyente |
| goals_ft_total | 0.5 | dixon_coles | 3504 | -0.00312 | [-0.00589, -0.00042] | mejor que el baseline |
| goals_ft_total | 0.5 | negbin | 3504 | -0.00317 | [-0.00611, -0.00033] | mejor que el baseline |
| goals_ft_total | 0.5 | poisson | 3504 | -0.00315 | [-0.00611, -0.00030] | mejor que el baseline |
| goals_ft_total | 1.5 | dixon_coles | 3504 | -0.00539 | [-0.00934, -0.00134] | mejor que el baseline |
| goals_ft_total | 1.5 | negbin | 3504 | -0.00527 | [-0.00928, -0.00115] | mejor que el baseline |
| goals_ft_total | 1.5 | poisson | 3504 | -0.00530 | [-0.00930, -0.00117] | mejor que el baseline |
| goals_ft_total | 2.5 | dixon_coles | 3504 | -0.00799 | [-0.01285, -0.00301] | mejor que el baseline |
| goals_ft_total | 2.5 | negbin | 3504 | -0.00798 | [-0.01283, -0.00300] | mejor que el baseline |
| goals_ft_total | 2.5 | poisson | 3504 | -0.00799 | [-0.01285, -0.00301] | mejor que el baseline |
| goals_ft_total | 3.5 | dixon_coles | 3504 | -0.00738 | [-0.01272, -0.00242] | mejor que el baseline |
| goals_ft_total | 3.5 | negbin | 3504 | -0.00739 | [-0.01272, -0.00243] | mejor que el baseline |
| goals_ft_total | 3.5 | poisson | 3504 | -0.00738 | [-0.01272, -0.00242] | mejor que el baseline |

## 5. Comparación con el mercado

Mercado `goals_ft_total` línea 2.5. Cuotas pre-partido usables en `as_of`: 3504 (casas: {'pinnacle': 2625, 'market_avg': 879}); margen medio 1.0437. Cuotas de cierre (solo evaluación): 3504.

| Modelo | Calibrador | Frente a | N | LL modelo | LL mercado | Δ LL (IC 95%) | |edge| medio |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| dixon_coles | platt | prematch | 3504 | 0.6800 | 0.6723 | 0.00766 [0.00397, 0.01111] | 4.3% |
| dixon_coles | platt | closing | 3504 | 0.6800 | 0.6691 | 0.01088 [0.00668, 0.01499] | 5.0% |
| league_freq | identity | prematch | 3504 | 0.6880 | 0.6723 | 0.01565 [0.01022, 0.02090] | 6.4% |
| league_freq | identity | closing | 3504 | 0.6880 | 0.6691 | 0.01887 [0.01282, 0.02432] | 7.0% |
| negbin | platt | prematch | 3504 | 0.6800 | 0.6723 | 0.00768 [0.00398, 0.01112] | 4.3% |
| negbin | platt | closing | 3504 | 0.6800 | 0.6691 | 0.01090 [0.00669, 0.01501] | 5.0% |
| poisson | platt | prematch | 3504 | 0.6800 | 0.6723 | 0.00766 [0.00397, 0.01111] | 4.3% |
| poisson | platt | closing | 3504 | 0.6800 | 0.6691 | 0.01088 [0.00668, 0.01499] | 5.0% |

### Simulación paper (stake plano, sin dinero real)

| Modelo | Apuestas | ROI | IC 95% ROI | Acierto | Edge medio | CLV medio | Drawdown máx. |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| dixon_coles | 2054 | -5.9% | [-10.6%, -1.4%] | 43.3% | 6.4% | -4.4% | 134.0 |
| league_freq | 2446 | -6.4% | [-10.9%, -2.0%] | 41.1% | 8.6% | -4.6% | 189.2 |
| negbin | 2055 | -6.0% | [-10.3%, -1.4%] | 43.2% | 6.4% | -4.4% | 136.0 |
| poisson | 2054 | -5.9% | [-10.6%, -1.4%] | 43.3% | 6.4% | -4.4% | 134.0 |

Un ROI positivo con un intervalo que incluye el cero no es evidencia de edge. El CLV positivo frente al cierre es una señal más estable que el ROI en muestras pequeñas.

## 6. Criterios de éxito

1. Reproducibilidad: dataset `dataset-s5h5r6zcvxdj91c5`, configuración `dcfc83fa4d94f18d`, código `91609fc`. Verificar re-ejecutando: el `summary.json` debe ser idéntico.
2. Sin leakage: **cumple**.
3. Calibración (ECE < 0.03 en test, o indistinguible del ruido de muestreo): peor ECE 0.0205; 37 combinaciones bajo el objetivo, 0 dentro del ruido, 0 fuera: **cumple**.
4. Frente al baseline: 17 combinaciones mejores, 0 peores, 9 sin diferencia concluyente.
5. Reconstrucción: cada predicción está en `predictions` con su `feature_snapshot_id` y su liquidación.
