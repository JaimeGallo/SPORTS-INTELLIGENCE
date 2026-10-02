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
- **Pendiente: ejecución de referencia con football-data.co.uk.** Sigue bloqueada: `www.football-data.co.uk`
  redirige a `football-data.co.uk` (sin `www`), y ese host no está permitido en la red del entorno en la nube.
  No hay una copia pública con las columnas de cuotas en la que se pueda confiar.
- **Primera ejecución con datos reales (2026-10-02): variante FootyStats**,
  [`config.footystats-epl.yaml`](config.footystats-epl.yaml). Informe completo en
  [`runs/2026-10-02-footystats-epl-bt_t1p1tw9s712kk8ac.md`](runs/2026-10-02-footystats-epl-bt_t1p1tw9s712kk8ac.md).
  Premier League 2018/19 a 2024/25 (2.660 partidos; el alcance de la key de prueba), test 2023/24 y 2024/25,
  añade córners del 1T. Reproducible: re-descargando los datos sale el mismo `dataset_version` y dos
  ejecuciones dan un `summary.json` idéntico.

### Lectura de la variante FootyStats (test, 760 partidos)

- **Sin leakage** y 0 violaciones de coherencia entre líneas.
- **Calibración**: 33 de 49 combinaciones mercado-línea-modelo bajo el objetivo o dentro del ruido; 16 fuera.
  Lo más claro: en goles FT los modelos con Platt **subestiman los overs** (O2.5: P media 56,9% frente a
  60,7% real; ECE 0,056). Las temporadas de test tienen más goles que las de calibración y el calibrador,
  ajustado solo con el pasado, no lo recoge. En córners FT 10.5 hay un sesgo parecido.
- **Frente al baseline de frecuencias**: 8 combinaciones mejores (córners FT 7.5, 9.5 y 11.5; goles 1T 0.5),
  ninguna peor, 26 sin diferencia concluyente. En goles FT los modelos de equipo no ganan al baseline.
- **Frente al mercado** (O/U 2.5 de cierre de referencia de FootyStats, solo evaluación): el mercado es
  mejor que todos los modelos (Δ log loss +0,0088, IC 95% [0,0016, 0,0166]). Era lo esperable para una
  primera versión sin información de alineaciones ni xG.
- **Simulación paper**: 0 apuestas, a propósito. FootyStats no indica casa ni hora de sus cuotas, así que no
  hay cuotas pre-partido utilizables (ADR-0008).
- Precaución con los córners: de 2020/21 a 2024/25, FootyStats da menos córners que football-data.co.uk en
  el 3% al 7% de los partidos (casi siempre uno menos) (ADR-0008, sección 6). Las métricas de córners miden
  el modelo frente a los datos de FootyStats, no frente a la realidad.

## Limitaciones conocidas

- Equipos recién ascendidos empiezan con fuerza media (sin prior de "ascendido"); quedan marcados en las
  features (`home_known` / `away_known`, partidos de historial por equipo).
- Dixon-Coles se estima en dos etapas (fuerzas Poisson y luego rho), una aproximación habitual.
- La dispersión de la Binomial Negativa se estima con medias dentro de muestra (puede subestimarse un poco).
- Solo existe una línea con cuotas (O/U 2.5 goles FT). Los córners y el primer tiempo se comparan con el
  mercado en EXP-001b, con The Odds API.
- Si dos fuentes aportan la misma estadística, la carga se detiene: la reconciliación entre fuentes llega
  con el segundo proveedor.
