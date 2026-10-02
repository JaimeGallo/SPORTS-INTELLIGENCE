# EXP-001a: probabilidades calibradas de goles y córners sin leakage

Pregunta: ¿puede JEV producir probabilidades calibradas para goles (partido completo y primer tiempo) y
córners (partido completo) usando datos históricos sin leakage, y compararlas con cuotas históricas?

Configuración: [`config.yaml`](config.yaml). Diseño: [`docs/phase-0-report.md`](../../docs/phase-0-report.md),
sección 4.

## Qué hace

1. **Ingesta** de football-data.co.uk (5 ligas, 2015/16 a 2025/26) a PostgreSQL. Cada fichero crudo se
   guarda por contenido (`data/raw/`) y el conjunto queda registrado como `dataset_version`.
2. **Reglas point-in-time** (ADR-0003): resultados y estadísticas disponibles 3 h después del inicio; cuotas
   pre-partido 24 h antes; cuotas de cierre solo en el inicio (se usan para evaluar, nunca para decidir).
   Las predicciones se hacen 60 min antes del inicio.
3. **Modelos** por objetivo (goles FT, goles 1T, córners FT): baseline de frecuencias de la liga, Poisson
   con fuerzas de ataque/defensa ponderadas por recencia, Dixon-Coles (goles) y Binomial Negativa. Un modelo
   da la distribución completa; todas las líneas salen de ella, así que son coherentes entre sí.
4. **Walk-forward**: se reajusta cada semana con datos anteriores. Nada se baraja.
5. **Calibración** (identidad, Platt, isotónica) ajustada solo con temporadas anteriores.
6. **Selección** de hiperparámetros y calibrador en validación (2017/18 a 2023/24). **Test** intacto:
   2024/25 y 2025/26.
7. **Mercado**: Over/Under 2.5 goles (la única línea con cuotas en estos CSV) contra Pinnacle o la media del
   mercado, sin margen. Simulación paper con stake plano y CLV contra el cierre. Sin dinero real.
8. **Informe** en `results/<backtest_run_id>/report.md` y `summary.json`; predicciones, snapshots de
   features, liquidaciones y apuestas simuladas en PostgreSQL.

## Cómo ejecutarlo

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/jevs
.venv/bin/jevs experiment exp001a                    # descarga los CSV y ejecuta
.venv/bin/jevs experiment exp001a --provider synthetic  # pipeline completo con datos sintéticos
```

Sin acceso de red a `www.football-data.co.uk`, se pueden descargar los ficheros a mano y dejarlos en
`data/raw/cache/football_data_csv/<yyYY>/<DIV>.csv` (por ejemplo `2324/E0.csv`), y ejecutar con
`--no-download`. Divisiones: `E0` Premier League, `SP1` La Liga, `I1` Serie A, `D1` Bundesliga, `F1` Ligue 1.

Usa una base de datos distinta para los datos sintéticos (por ejemplo `jevs_synthetic`). Aunque el loader
filtra por fuente, separarlas evita confusiones.

## Estado

- Pipeline completo verificado con datos sintéticos (proceso generador conocido) y reproducible: dos
  ejecuciones con el mismo dataset, configuración y código producen un `summary.json` idéntico.
- **Pendiente: ejecución con datos reales**, bloqueada porque la política de red del entorno en la nube no
  permite `www.football-data.co.uk`.

## Limitaciones conocidas

- Equipos recién ascendidos empiezan con fuerza media (sin prior de "ascendido"); quedan marcados en las
  features (`home_known` / `away_known`, partidos de historial por equipo).
- Dixon-Coles se estima en dos etapas (fuerzas Poisson y luego rho), una aproximación habitual.
- La dispersión de la Binomial Negativa se estima con medias dentro de muestra (puede subestimarse un poco).
- Solo existe una línea con cuotas (O/U 2.5 goles FT). Los córners y el primer tiempo se comparan con el
  mercado en EXP-001b, con The Odds API.
- Si dos fuentes aportan la misma estadística, la carga se detiene: la reconciliación entre fuentes llega
  con el segundo proveedor.
