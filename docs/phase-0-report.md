# Fase 0: informe de auditoría y propuesta

Fecha: 2026-10-02. Estado: **pendiente de aprobación**. No se ha implementado código.

## 1. Auditoría del repositorio

- `JaimeGallo/SPORTS-INTELLIGENCE` solo contenía un `README.md` vacío. No hay código ni deuda técnica.
- `JaimeGallo/Multi-broker` (JEV Trading, commit `875abf9`) está en Fase 2: núcleo común, motor JEV
  con modelos de referencia, calidad de datos, features y riesgo. Todavía no tiene tests ni API.
- **JEV no es una API externa.** Es el nombre del núcleo predictivo de Multi-broker. Su
  `JEV_API_TOKEN` está reservado para proteger la API propia de JEV Trading (Fase 5, sin implementar).
  No hay ninguna key de JEV que integrar aquí (ADR-0005).

Qué se reutiliza y cómo: ver `architecture.md`, sección 7, y ADR-0004.

## 2. Documentos de esta fase

| Documento | Contenido |
| --- | --- |
| [architecture.md](architecture.md) | Capas, stack, estructura de carpetas, interfaces de proveedores y modelos, leakage |
| [data-sources.md](data-sources.md) | Evaluación de proveedores, coste, licencias, recomendación, spike de verificación |
| [data-model.md](data-model.md) | Esquema PostgreSQL propuesto |
| [adr/](adr/) | Decisiones de arquitectura |

## 3. Estrategia de datasets

1. **Histórico base (gratis): football-data.co.uk.** Temporadas 2015/16 a 2025/26 de Premier League,
   La Liga, Serie A, Bundesliga y Ligue 1. Aporta goles FT y 1T, córners FT y cuotas de O/U 2.5
   (incluido cierre de Pinnacle). Champions League no está en esos CSV: entra con el proveedor de pago.
2. **Estadísticas por mitad (pago): Sportmonks o API-Football**, según la decisión pendiente. Aporta
   córners 1T y reconciliación de córners FT contra football-data.co.uk.
3. **Cuotas (pago): The Odds API.** Histórico de mercados adicionales desde 2023-05-03 y, desde el
   día de la aprobación, **recolección propia de snapshots** de los mercados del MVP.
4. **Versionado:** cada ingesta genera un manifiesto (`dataset-vYYYY.MM.DD`) con fuentes, rangos,
   hashes de ficheros crudos y conteos. Un backtest siempre referencia un manifiesto.
5. **Fixture pequeño en el repositorio:** 1 temporada de 1 liga (~380 partidos) en `data/fixtures/`
   para que los tests sean reproducibles sin red.

## 4. Primer experimento reproducible (EXP-001)

**Pregunta:** ¿puede JEV producir probabilidades calibradas para goles y córners de primer tiempo y
partido completo usando datos históricos sin leakage, y compararlas contra cuotas históricas?

Se divide en dos etapas para no bloquear el avance por el dato más caro:

### EXP-001a (coste 0, puede empezar ya)

| | |
| --- | --- |
| Datos | football-data.co.uk, 5 ligas, 2015/16 a 2025/26 |
| Mercados | Goles FT O/U 0.5 a 3.5; goles 1T O/U 0.5 y 1.5; córners FT O/U 7.5 a 11.5 |
| Modelos | Baseline ingenuo (frecuencia de la liga, point-in-time), Poisson con fuerzas de ataque y defensa ponderadas por recencia, Dixon-Coles (goles), Binomial Negativa (córners) |
| Validación | Walk-forward por temporada: entrenar con temporadas < T, calibrar con T, evaluar con T+1. Test final: 2024/25 y 2025/26, sin tocar hasta el final |
| Calibración | Sin calibrar vs Platt vs isotónica, ajustadas solo en la temporada de calibración |
| Métricas | Brier, log loss, ECE, diagrama de fiabilidad, con intervalos bootstrap por partido |
| Mercado | Solo O/U 2.5 goles FT (único con cuotas en el CSV): probabilidad sin margen, edge y ROI simulado plano contra cierre de Pinnacle |
| Pruebas de leakage | `max_available_at <= as_of` en cada feature snapshot; test que inyecta un dato futuro y debe fallar |

### EXP-001b (requiere la key aprobada)

| | |
| --- | --- |
| Datos | Proveedor de estadísticas elegido (córners 1T) + The Odds API (cuotas de córners y 1T desde 2023-05) |
| Mercados | Córners 1T O/U 2.5 a 5.5; comparación contra mercado en córners FT y 1T |
| Resto | Igual que EXP-001a |

### Criterios de éxito

1. El pipeline reproduce el mismo resultado byte a byte con el mismo manifiesto y la misma semilla.
2. Los tests de leakage pasan y el test de leakage inyectado falla como debe.
3. ECE < 0.03 en el test fuera de muestra para los mercados con muestra suficiente.
4. Los modelos igualan o superan al baseline ingenuo en Brier y log loss, con intervalo bootstrap que
   no cruce cero, o se documenta que no lo hacen.
5. Para O/U 2.5 se puede reconstruir cualquier predicción histórica y su comparación con el cierre.

**No es criterio de éxito** tener ROI positivo. Contra el cierre de Pinnacle lo esperable es no
encontrar edge en O/U 2.5 goles; eso también es un resultado válido y útil.

## 5. Plan de fases propuesto (ajustado)

| Fase | Contenido | Depende de |
| --- | --- | --- |
| 0 | Este informe | |
| 0.5 | Spike de proveedores (medio día, gratis) | Keys de trial |
| 1 | Esqueleto: pyproject, common (copiado de JEV Trading), CI con ruff, mypy y pytest | Aprobación |
| 2 | Interfaces de proveedores, mock provider, adapter de football-data.co.uk | 1 |
| 3-4 | Ingesta histórica, normalización, esquema PostgreSQL con Alembic, manifiestos | 2 |
| 5 | Feature Store point-in-time + tests de leakage | 4 |
| 6-7 | Baselines de goles y córners | 5 |
| 8-9 | Backtesting walk-forward + calibración: **EXP-001a completo** | 6-7 |
| 10-11 | Odds Engine + Edge Engine; adapter de cuotas y del proveedor de estadísticas: **EXP-001b** | 8-9, keys |
| 12+ | Paper betting, dashboard, live, replay... como en el prompt | Resultado de EXP-001 |

## 6. Decisiones que necesito de ti

1. **Proveedor de estadísticas:** Sportmonks Growth (~99 EUR/mes, recomendado) o API-Football Pro
   (~19 USD/mes, más barato, más riesgo de calidad). Se puede decidir después del spike de la Fase 0.5.
2. **Plan de The Odds API:** el de ~30 USD/mes alcanza para empezar a recolectar snapshots; el
   histórico consume créditos rápido (10 por región y mercado), así que conviene medirlo en el spike.
3. **Aprobación del EXP-001a** tal como está descrito, que no requiere ningún pago.
4. **Base de datos local:** ¿PostgreSQL con Docker desde la Fase 1, o SQLite para el experimento y
   PostgreSQL a partir de la Fase 4? Recomiendo PostgreSQL desde el inicio para no reescribir consultas.
