# Arquitectura propuesta (Fase 0)

Estado: **propuesta, pendiente de aprobación**.

## 1. Principio rector

> JEV no intenta adivinar el resultado. Estima una distribución de probabilidades usando solo la
> información disponible en cada instante, la calibra y determina cuándo difiere significativamente de
> la valoración implícita del mercado.

Las capas están estrictamente separadas y cada una solo depende de las de arriba:

```text
providers ─► normalization ─► data_quality ─► feature_store ─► models ─► calibration
                                                                              │
                         presentation ◄─ simulation ◄─ risk ◄─ signals ◄─ edge ◄─ odds
```

## 2. Stack

| Pieza | Elección | Motivo |
| --- | --- | --- |
| Lenguaje núcleo | Python 3.12 | Ecosistema estadístico (numpy, scipy, statsmodels, scikit-learn) |
| API | FastAPI + WebSockets | Tipado con Pydantic, async |
| Base de datos | PostgreSQL 16 | Fuente de verdad. TimescaleDB descartado en el MVP (ADR-0001) |
| Migraciones | Alembic | Esquema versionado |
| Cache / colas | Redis (Fase 14+) | No es fuente de verdad. No hace falta para el primer experimento |
| Frontend | React + TypeScript + Vite + Tailwind | Fase 13 |
| Calidad | ruff, mypy, pytest | Mismo estándar que JEV Trading |

Para el primer experimento basta Python + PostgreSQL (o SQLite en tests). Docker, Redis, workers y
frontend llegan en sus fases.

## 3. Estructura de carpetas

```text
SPORTS-INTELLIGENCE/
├── README.md
├── pyproject.toml
├── .env.example
├── config/
│   ├── default.yaml              # parámetros (sin secretos)
│   ├── competitions.yaml         # enabled_competitions
│   ├── providers.yaml            # capability matrix por configuración
│   └── markets.yaml              # catálogo de mercados y líneas
├── packages/
│   ├── common/                   # config, secrets, logging, ids, clock, errors (adaptado de JEV Trading)
│   ├── providers/
│   │   ├── base.py               # DataProvider, OddsProvider, capacidades
│   │   ├── mock.py               # proveedor determinista para tests
│   │   ├── football_data_csv.py  # football-data.co.uk (histórico gratis)
│   │   ├── sportmonks.py         # o api_football.py, según decisión
│   │   ├── odds_api.py
│   │   └── resilience.py         # RateLimiter, Retry, Backoff, CircuitBreaker
│   ├── normalization/            # entidades canónicas + mapeo de IDs de proveedor
│   ├── data_quality/             # DataQualityEngine, DataQualityScore
│   ├── ingestion/                # HistoricalDataEngine (ingest, validate, dedupe, reconcile, snapshot)
│   ├── features/                 # FeatureEngine + FeatureStore point-in-time
│   ├── markets/                  # definición de mercados, líneas y reglas de liquidación
│   ├── models/
│   │   ├── base.py               # MarketModel: devuelve una distribución, no un sí/no
│   │   ├── goals/                # Poisson, Dixon-Coles, Binomial Negativa
│   │   ├── corners/              # Poisson, Binomial Negativa
│   │   └── registry.py           # ModelRegistry
│   ├── calibration/              # Platt, isotónica, beta; ECE, Brier, log loss
│   ├── odds/                     # conversión, margen, probabilidad justa
│   ├── edge/                     # edge, EV, SignalQualityScore, estados de señal
│   ├── backtesting/              # walk-forward, ventanas, métricas, intervalos bootstrap
│   ├── paper/                    # PaperBettingEngine, RiskPolicy, correlación
│   ├── live/                     # MatchState, reconciliación de eventos (Fase 14+)
│   └── replay/                   # MatchReplayEngine (Fase 15)
├── apps/
│   ├── api/                      # FastAPI (Fase 13)
│   ├── worker/                   # jobs de ingesta y cálculo
│   ├── cli/                      # `jevs ingest`, `jevs backtest`, `jevs experiment`
│   └── web/                      # dashboard React (Fase 13)
├── migrations/                   # Alembic
├── experiments/
│   └── exp001_calibrated_goals_corners/   # primer experimento reproducible
├── data/                         # git-ignored, salvo fixtures pequeños
│   └── fixtures/                 # muestras pequeñas versionadas para tests
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/                 # contra respuestas crudas guardadas de cada proveedor
│   └── leakage/                  # pruebas específicas de fuga de información
└── docs/
    ├── architecture.md, data-sources.md, data-model.md, phase-0-report.md
    └── adr/
```

## 4. Interfaces de proveedores (borrador)

```python
class Capability(StrEnum):
    FIXTURES = "fixtures"
    RESULTS = "results"
    HALFTIME_SCORE = "halftime_score"
    MATCH_STATS = "match_stats"
    MATCH_STATS_BY_HALF = "match_stats_by_half"
    CORNERS = "corners"
    LINEUPS = "lineups"
    LIVE_EVENTS = "live_events"
    ODDS_PREMATCH = "odds_prematch"
    ODDS_LIVE = "odds_live"
    ODDS_HISTORICAL = "odds_historical"


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    capabilities: frozenset[Capability]  # cargadas desde config/providers.yaml, nunca supuestas
    priority: int  # para reconciliación y failover
    license_note: str


class DataProvider(ABC):
    info: ProviderInfo

    async def competitions(self) -> list[RawCompetition]: ...
    async def seasons(self, competition: ProviderRef) -> list[RawSeason]: ...
    async def fixtures(self, season: ProviderRef) -> list[RawMatch]: ...
    async def match_statistics(self, match: ProviderRef) -> RawMatchStatistics: ...
    async def match_events(self, match: ProviderRef) -> list[RawMatchEvent]: ...


class OddsProvider(ABC):
    info: ProviderInfo

    async def odds_snapshot(self, event: ProviderRef, markets: list[MarketKey]) -> RawOddsSnapshot: ...
    async def historical_odds(
        self, event: ProviderRef, markets: list[MarketKey], at: datetime
    ) -> RawOddsSnapshot: ...
```

Reglas:

- Llamar a un método cuya capacidad no está declarada lanza `CapabilityNotSupported`. Nunca se
  devuelven datos vacíos "por defecto" que parezcan reales.
- Los proveedores devuelven objetos `Raw*` con el ID del proveedor y `fetched_at`. La capa de
  normalización los convierte a entidades canónicas. Los proveedores nunca escriben en la base de datos.
- Cada respuesta cruda se guarda (o se puede guardar) con su hash para poder reproducir sin depender
  de la API (sección 34 del prompt).

## 5. Contrato de modelo (borrador)

```python
class MarketModel(ABC):
    model_id: str
    version: str
    feature_version: str

    @abstractmethod
    def predict_distribution(self, features: FeatureSnapshot) -> CountDistribution:
        """Función pura: sin I/O, sin reloj, sin estado oculto. P(k) para k = 0..K."""


# Las probabilidades de mercado salen de la distribución, no de un modelo por línea:
# P(Over 9.5) = 1 - CDF(9)
```

Un único modelo de córners FT produce todas las líneas (7.5 a 11.5) de forma coherente: P(Over 8.5)
nunca puede ser menor que P(Over 9.5). Esto evita incoherencias que aparecerían con un clasificador
por línea, y es la base del `MarketCorrelationEngine`.

## 6. Prevención de leakage

`FeatureStore.get_features(match_id, as_of)` es la única puerta de entrada a los modelos:

- Toda fila en la base de datos lleva `available_at` (cuándo se pudo conocer el dato), además de
  `event_time` (cuándo ocurrió). Ver `data-model.md`.
- Las features se calculan solo con filas `available_at <= as_of` y de partidos con
  `kickoff < as_of`.
- `FeatureSnapshot` registra el `max(available_at)` usado. Un test de leakage falla si supera `as_of`.
- El backtester nunca baraja: walk-forward por fecha.

## 7. Reutilización de JEV Trading (Multi-broker)

Auditado en el commit `875abf9` (Fase 2, sin tests aún). Se **copian y adaptan** (no se importan
como dependencia, ver ADR-0004):

| Módulo de Multi-broker | Uso aquí |
| --- | --- |
| `packages/common/secrets.py` | Igual: secretos solo desde entorno o `.env` |
| `packages/common/logging.py` | Igual: logs JSON con secretos ocultos |
| `packages/common/config.py` | Adaptado: prefijo `JEVS__` en lugar de `JEV__` |
| `packages/common/ids.py` | IDs deterministas de predicción |
| `packages/common/safety.py` | Adaptado a "nunca apuestas reales" |
| `packages/jev/base.py`, `registry.py` | Patrón para `MarketModel` y `ModelRegistry` |
| `packages/data_quality/engine.py` | Patrón para `DataQualityEngine` |

No se reutiliza: datos de mercado, órdenes, brokers, features técnicas (son de trading intradía).

## 8. Modos

`BACKTEST`, `REPLAY`, `PREMATCH`, `LIVE`, `PAPER`. Solo `BACKTEST` entra en el primer experimento.
Ningún modo coloca apuestas reales; el código no tendrá ningún cliente de casas de apuestas (ADR-0006).
