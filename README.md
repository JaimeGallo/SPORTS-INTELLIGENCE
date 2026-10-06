# JEV Sports Intelligence

Plataforma de inteligencia predictiva para fútbol: transforma datos históricos, estadísticas, eventos
y cuotas en **probabilidades calibradas** por mercado, las compara con la probabilidad implícita del
mercado y detecta diferencias estadísticamente interesantes.

> JEV no intenta adivinar el resultado. Estima una distribución de probabilidades usando solo la
> información disponible en cada instante, la calibra y determina cuándo difiere significativamente de
> la valoración implícita del mercado.

**Probabilidad no es certeza. Edge no es garantía de resultado.** El sistema no coloca apuestas reales
(ver [ADR-0006](docs/adr/0006-no-real-money.md)).

## Estado

**EXP-001a implementado** (fases 1 a 12 del plan, solo lo necesario para el experimento): ingesta a
PostgreSQL, calidad de datos, Feature Store point-in-time, modelos de goles y córners, backtest
walk-forward, calibración, Odds Engine, Edge Engine y simulación paper. Verificado con datos sintéticos y
ejecutado con datos reales: referencia con football-data.co.uk (5 ligas, 2015/16 a 2025/26) y variante FootyStats
(Premier League 2018/19 a 2024/25), comparadas en [EXP-001a](experiments/exp001a/README.md). Resultado: sin leakage y
calibración agregada correcta, pero los modelos no superan al mercado (sin señal de edge). Spike de FootyStats y Colombia:
[ADR-0008](docs/adr/0008-colombia-focus-and-footystats.md).

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/jevs
.venv/bin/jevs experiment exp001a
.venv/bin/pytest            # TEST_DATABASE_URL activa también los tests de integración
```

- [EXP-001a](experiments/exp001a/README.md): qué hace, cómo ejecutarlo y limitaciones
- [Informe de la Fase 0](docs/phase-0-report.md): auditoría, estrategia de datos, primer experimento, decisiones
- [Arquitectura](docs/architecture.md)
- [Fuentes de datos](docs/data-sources.md)
- [Modelo de datos](docs/data-model.md)
- [Decisiones de arquitectura (ADR)](docs/adr/)

## MVP

Mercados Over/Under de goles (1T y FT) y córners (1T y FT) para Premier League, La Liga, Serie A,
Bundesliga, Ligue 1 y Champions League (configurables).

## Seguridad

Las keys de proveedores se leen solo de variables de entorno o de un `.env` local ignorado por Git.
Copia `.env.example` a `.env` y rellénalo. Nunca subas keys al repositorio.
