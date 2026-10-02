# Modelo de datos

Estado: **implementado para EXP-001a** en `packages/storage/schema.py` (migración Alembic `0001`).
Este documento fue la propuesta de la Fase 0; las diferencias con lo implementado se resumen aquí:

- No hay tabla `match_results`: los goles (FT y 1T) son una estadística más en `match_statistics`
  (`stat_key = 'goals'`), con el mismo `available_at` y la misma procedencia que los córners.
- `matches.kickoff_time_known` marca los partidos cuya fuente no da hora (temporadas antiguas de
  football-data.co.uk); para ellos se asume la hora más tardía configurada, que es la opción conservadora.
- `players`, `match_events` y `prediction_distributions` llegan con las fases de alineaciones y live.
- `paper_bets` y `predictions` guardan el `backtest_run_id`; un mismo run reejecutado reemplaza sus filas.

## Principios

1. **IDs canónicos propios** (`ULID` como texto). Los IDs de proveedor viven solo en tablas de mapeo.
2. **Dos tiempos en todo dato que alimenta features**: `event_time` (cuándo ocurrió) y
   `available_at` (cuándo pudimos conocerlo). El Feature Store filtra por `available_at`.
3. **Append-only** para cuotas, eventos, predicciones y estadísticas: las correcciones son filas
   nuevas con `supersedes_id`, nunca un `UPDATE` que borre el pasado.
4. **Procedencia**: cada fila de datos externos guarda `source_id` y `raw_payload_id`.
5. Sin TimescaleDB en el MVP (ADR-0001). Índices por `(match_id, available_at)` bastan para el
   volumen de 6 competiciones.

## Grupos de tablas

### Referencia y procedencia

```sql
CREATE TABLE data_sources (
    source_id        text PRIMARY KEY,          -- 'football_data_csv', 'sportmonks', 'odds_api'
    priority         smallint NOT NULL,         -- menor = más confiable
    license_note     text NOT NULL,
    capabilities     jsonb NOT NULL             -- copia de config/providers.yaml en el momento de la ingesta
);

CREATE TABLE raw_payloads (                     -- respuestas crudas para reproducibilidad
    raw_payload_id   text PRIMARY KEY,
    source_id        text NOT NULL REFERENCES data_sources,
    endpoint         text NOT NULL,
    request_params   jsonb NOT NULL,            -- nunca incluye la key
    fetched_at       timestamptz NOT NULL,
    content_hash     text NOT NULL,
    storage_uri      text NOT NULL              -- fichero comprimido fuera de la BD
);
```

### Entidades canónicas y mapeo

```sql
CREATE TABLE competitions (competition_id text PRIMARY KEY, name text, country text, type text);
CREATE TABLE seasons      (season_id text PRIMARY KEY, competition_id text REFERENCES competitions,
                           label text, start_date date, end_date date);
CREATE TABLE teams        (team_id text PRIMARY KEY, name text, country text);
CREATE TABLE players      (player_id text PRIMARY KEY, name text, birth_date date);

CREATE TABLE matches (
    match_id         text PRIMARY KEY,
    season_id        text NOT NULL REFERENCES seasons,
    home_team_id     text NOT NULL REFERENCES teams,
    away_team_id     text NOT NULL REFERENCES teams,
    kickoff_at       timestamptz NOT NULL,
    matchday         smallint,
    stage            text,
    status           text NOT NULL              -- scheduled | live | finished | postponed | abandoned
);

CREATE TABLE provider_entity_map (              -- un único mapeo para todos los tipos de entidad
    source_id        text NOT NULL REFERENCES data_sources,
    entity_type      text NOT NULL,             -- competition | season | team | player | match | bookmaker
    provider_ref     text NOT NULL,
    canonical_id     text NOT NULL,
    mapped_by        text NOT NULL,             -- rule | manual | fuzzy_reviewed
    created_at       timestamptz NOT NULL,
    PRIMARY KEY (source_id, entity_type, provider_ref)
);
```

### Hechos del partido

```sql
CREATE TABLE match_statistics (                 -- formato largo: extensible sin migraciones
    id               bigserial PRIMARY KEY,
    match_id         text NOT NULL REFERENCES matches,
    team_id          text NOT NULL REFERENCES teams,
    period           text NOT NULL,             -- '1H' | '2H' | 'FT' | 'ET'
    stat_key         text NOT NULL,             -- 'corners', 'shots', 'shots_on_target', ...
    value            numeric NOT NULL,
    source_id        text NOT NULL,
    available_at     timestamptz NOT NULL,
    raw_payload_id   text,
    supersedes_id    bigint
);

CREATE TABLE match_events (                     -- goles, córners, tarjetas... (live y replay)
    event_id         text PRIMARY KEY,
    match_id         text NOT NULL REFERENCES matches,
    source_id        text NOT NULL,
    provider_event_id text NOT NULL,
    event_type       text NOT NULL,
    team_id          text,
    minute           smallint, added_time smallint, period text,
    event_time       timestamptz,
    received_at      timestamptz NOT NULL,
    sequence_number  bigint,
    event_hash       text NOT NULL,
    status           text NOT NULL,             -- active | corrected | retracted | duplicate
    supersedes_id    text,
    UNIQUE (source_id, provider_event_id, event_hash)
);
```

### Mercado

```sql
CREATE TABLE bookmakers (bookmaker_id text PRIMARY KEY, name text, is_sharp boolean DEFAULT false);

CREATE TABLE markets (                          -- catálogo, sembrado desde config/markets.yaml
    market_key       text PRIMARY KEY,          -- 'goals_ft_total', 'corners_1h_total'
    stat_key         text NOT NULL,             -- 'goals' | 'corners'
    period           text NOT NULL,             -- '1H' | 'FT'
    kind             text NOT NULL,             -- 'total' (MVP); luego 'btts', '1x2', 'handicap'...
    settlement_rule  text NOT NULL
);

CREATE TABLE odds_snapshots (                   -- append-only
    id               bigserial PRIMARY KEY,
    match_id         text NOT NULL REFERENCES matches,
    bookmaker_id     text NOT NULL REFERENCES bookmakers,
    market_key       text NOT NULL REFERENCES markets,
    line             numeric(5,2) NOT NULL,     -- 9.5
    selection        text NOT NULL,             -- 'over' | 'under'
    decimal_odds     numeric(8,3) NOT NULL CHECK (decimal_odds > 1.0),
    is_closing       boolean NOT NULL DEFAULT false,
    quoted_at        timestamptz NOT NULL,      -- según el proveedor
    available_at     timestamptz NOT NULL,      -- cuándo la recibimos nosotros
    source_id        text NOT NULL,
    raw_payload_id   text
);
CREATE INDEX ON odds_snapshots (match_id, market_key, line, available_at);
```

### Modelos, predicciones y evaluación

```sql
CREATE TABLE dataset_versions (dataset_version text PRIMARY KEY, created_at timestamptz,
                               manifest jsonb NOT NULL, content_hash text NOT NULL);

CREATE TABLE model_versions (
    model_version    text PRIMARY KEY,          -- 'jev-corners-ft-poisson-0.1.0'
    market_family    text NOT NULL,
    algorithm        text NOT NULL,
    hyperparameters  jsonb NOT NULL,
    feature_version  text NOT NULL,
    dataset_version  text REFERENCES dataset_versions,
    training_period  tstzrange NOT NULL,
    calibrator       jsonb,
    metrics          jsonb,
    status           text NOT NULL,             -- development | candidate | validated | production | retired
    created_at       timestamptz NOT NULL
);

CREATE TABLE predictions (                      -- append-only, una fila por (partido, mercado, línea, instante)
    prediction_id    text PRIMARY KEY,
    match_id         text NOT NULL REFERENCES matches,
    mode             text NOT NULL,             -- backtest | replay | prematch | live
    as_of            timestamptz NOT NULL,      -- información usada: available_at <= as_of
    market_key       text NOT NULL REFERENCES markets,
    line             numeric(5,2) NOT NULL,
    probability_raw  numeric(6,5) NOT NULL,
    probability      numeric(6,5) NOT NULL,     -- calibrada
    uncertainty      numeric(6,5),
    fair_odds        numeric(8,3),
    market_odds      numeric(8,3),
    market_probability_raw numeric(6,5),
    market_probability     numeric(6,5),        -- sin margen
    edge             numeric(6,5),
    expected_value   numeric(8,5),
    signal_state     text,                      -- no_edge | potential_edge | validated_edge | insufficient_evidence
    data_quality     numeric(4,3),
    model_version    text NOT NULL REFERENCES model_versions,
    feature_snapshot_id text NOT NULL,
    backtest_run_id  text,
    created_at       timestamptz NOT NULL
);

CREATE TABLE prediction_distributions (         -- P(k) completo para auditar y derivar líneas
    prediction_group_id text PRIMARY KEY,
    probabilities    real[] NOT NULL
);

CREATE TABLE feature_snapshots (
    feature_snapshot_id text PRIMARY KEY,
    match_id         text NOT NULL, as_of timestamptz NOT NULL,
    feature_version  text NOT NULL,
    features         jsonb NOT NULL,
    max_available_at timestamptz NOT NULL CHECK (max_available_at <= as_of)   -- guarda contra leakage
);

CREATE TABLE settlements (prediction_id text PRIMARY KEY REFERENCES predictions,
                          outcome text NOT NULL,      -- hit | miss | push | void
                          settled_at timestamptz NOT NULL);

CREATE TABLE backtest_runs (backtest_run_id text PRIMARY KEY, config jsonb NOT NULL,
                            dataset_version text NOT NULL, code_version text NOT NULL,
                            started_at timestamptz, finished_at timestamptz, metrics jsonb);

CREATE TABLE paper_bets (paper_bet_id text PRIMARY KEY, prediction_id text REFERENCES predictions,
                         stake numeric NOT NULL, decimal_odds numeric NOT NULL,
                         placed_at timestamptz NOT NULL, outcome text, pnl numeric);

CREATE TABLE data_quality_events (id bigserial PRIMARY KEY, match_id text, source_id text,
                                  kind text NOT NULL, details jsonb, detected_at timestamptz NOT NULL);
```

## Tablas del prompt que no se crean como tablas

- `team_statistics`, `team_form`, `head_to_head`, `prediction_features`: son **features derivadas**
  y se recalculan de forma point-in-time desde `match_statistics`; guardarlas como
  tablas mutables invita al leakage. Su resultado queda congelado en `feature_snapshots`.
- `market_lines`: la línea es una columna de `odds_snapshots` y `predictions`.
- `prediction_results`, `backtest_predictions`: cubiertas por `settlements` y por
  `predictions.backtest_run_id`.
