# ADR-0003: Datos point-in-time para evitar leakage

- Estado: propuesto
- Fecha: 2026-10-02

## Contexto

El mayor riesgo de un sistema de predicción con backtesting es usar sin querer información que no
existía en el momento de la predicción (estadísticas del propio partido, cuotas posteriores,
correcciones de datos).

## Decisión

- Toda fila que alimenta features tiene `event_time` y `available_at`. Para datos históricos
  importados en bloque, `available_at` se estima de forma conservadora (por ejemplo, fin del partido
  más un margen configurable), nunca como la fecha de importación ni como el inicio del partido.
- Los datos externos son append-only; una corrección es una fila nueva que referencia a la anterior.
- Los modelos solo reciben datos a través de `FeatureStore.get_features(match_id, as_of)`.
- `feature_snapshots.max_available_at <= as_of` se valida en código y con una restricción `CHECK`.
- El backtesting es walk-forward por fecha; nunca se barajan partidos.
- Existe una batería de tests en `tests/leakage/` que inyecta datos futuros y debe detectarlos.

## Consecuencias

- Las tablas de "forma" o "promedios" no se guardan como estado mutable; se derivan y se congelan en
  cada snapshot. Cuesta algo más de cálculo, pero hace cada predicción reproducible.
