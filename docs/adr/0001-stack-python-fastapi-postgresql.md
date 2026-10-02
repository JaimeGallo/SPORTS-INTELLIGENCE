# ADR-0001: Python, FastAPI y PostgreSQL; sin TimescaleDB en el MVP

- Estado: propuesto
- Fecha: 2026-10-02

## Contexto

El núcleo es estadístico (distribuciones de conteo, calibración, backtesting). El prompt sugiere
Python, FastAPI y PostgreSQL, y plantea evaluar TimescaleDB para series temporales.

## Decisión

- Python 3.12 para todo el backend y la investigación, en un único repositorio.
- PostgreSQL 16 como única fuente de verdad; Alembic para migraciones.
- **No** usar TimescaleDB en el MVP. El volumen previsto (6 competiciones, ~2.000 partidos por
  temporada, snapshots de cuotas cada pocos minutos solo en ventanas pre-match) cabe sin problemas en
  tablas normales con índices `(match_id, ..., available_at)`.
- Redis solo a partir de la fase live, como cache, nunca como fuente de verdad.

## Consecuencias

- Mismo lenguaje que JEV Trading: se pueden copiar sus utilidades comunes.
- Si el volumen live crece (sección 78 del prompt), se reevalúa TimescaleDB con métricas reales.
