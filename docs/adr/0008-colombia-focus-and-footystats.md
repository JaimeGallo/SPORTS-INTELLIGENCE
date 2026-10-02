# ADR-0008: Colombia (Liga BetPlay) como foco inicial y FootyStats como fuente candidata

- Estado: **propuesto**, pendiente del spike de verificación (sección 5)
- Fecha: 2026-10-02
- Relacionado: ADR-0002 (proveedores), ADR-0003 (point-in-time), ADR-0007 (proveedor de estadísticas)

## 1. Contexto

Se propone enfocar JEV inicialmente en el fútbol colombiano (Categoría Primera A, Liga BetPlay DIMAYOR) en
lugar de las cinco grandes ligas europeas, y se evaluaron estas fuentes: FootyStats, API-Football,
Sportradar, Opta (Stats Perform) y OpenFoot.

## 2. Hallazgos de la evaluación

| Fuente | Colombia | Córners 1T | Cuotas | Coste aprox. | Observaciones |
| --- | --- | --- | --- | --- | --- |
| FootyStats | Primera A, B, copas, Superliga, femenina | Campo explícito o minuto de cada córner (`corner_timings`) | Campos `odds_*` en el detalle del partido, sin casa ni hora documentadas | £20 a £30/mes | Diseñada para análisis; calidad y licencia por confirmar |
| API-Football | Sí | Parámetro `half` en estadísticas (temporadas por confirmar) | Endpoint de cuotas con casas reales, retención corta | ~19 USD/mes | Buena segunda fuente para reconciliar |
| The Odds API | No hay evidencia de cobertura de Colombia | n/a | Snapshots históricos | desde ~30 USD/mes | Verificar con `/sports` (gratis) |
| Sportradar | Sí | Sí | Según producto | Contrato | Futura fuente premium |
| Opta / Stats Perform | Socio oficial de datos de DIMAYOR (acuerdo de 2021, renovado) | Sí (event-level) | No | Contrato | Futura fuente premium |
| OpenFoot | No confirmada | No confirmado | Plan Developer | Plan gratis y de pago | Prioridad baja |

Precisiones sobre el ecosistema oficial:

- **Genius Sports** tiene la exclusiva de los datos oficiales rápidos (fast-path) y del vídeo de DIMAYOR
  **para apuestas reguladas**. Para cualquier producto live o de apuestas, el socio oficial relevante es
  Genius, no Opta.
- DIMAYOR anunció **Smrt Stats** como nueva plataforma; según la información pública reemplaza a Wyscout
  (scouting y vídeo), no necesariamente a Opta. Quién captura hoy los datos oficiales queda por confirmar.

## 3. Decisión (propuesta)

1. Añadir **COL-PA** (Primera A) como competición configurable, sin quitar las ligas europeas: EXP-001a
   sigue siendo la referencia metodológica con datos gratuitos y muestra grande.
2. Implementar **`FootyStatsProvider`** (hecho, sin verificar contra respuestas reales) como fuente candidata
   principal para Colombia. Todos los nombres de campos están centralizados en `FIELDS` y `ODDS_FIELDS`.
3. **Córners del primer tiempo**: se usa el campo explícito si existe; si no, se derivan de los minutos de
   los córners **solo cuando la lista de minutos cuadra con el total del partido**. La derivación queda
   registrada en `RawMatch.notes`; si no cuadra, el dato queda como faltante.
4. **Cuotas de FootyStats**: como no se documenta la casa ni el momento, se guardan bajo la pseudo-casa
   `footystats_reference` con `is_closing = true` (disponibles solo en el inicio del partido). Sirven para
   **evaluar** el modelo contra una referencia de mercado, **nunca** para decidir una apuesta simulada.
5. **Temporadas de año calendario** (`"2024"`): Apertura y Clausura dentro de la misma temporada. Las fases
   de eliminación (cuadrangulares, finales) se marcarán en una iteración posterior.
6. Cuotas para decisiones paper en Colombia: **empezar a guardar snapshots propios** de una fuente con casa
   y hora conocidas (API-Football odds u otra) en cuanto haya key.

## 4. Consecuencias

- La arquitectura no cambia: un adaptador nuevo, una línea en `config/providers.yaml` y la competición en
  `config/default.yaml`. Se añadió `RawMatch.kickoff_utc` (hora exacta del proveedor) y `notes`.
- **Muestra pequeña**: ~400 partidos por año. Las métricas por mercado tendrán intervalos amplios; hay que
  usar todo el histórico disponible y, más adelante, combinar ligas sudamericanas con modelos jerárquicos.
- Variables específicas a incorporar después: altitud del estadio (Bogotá, Pasto, Tunja, Manizales),
  distancia de viaje y fase del torneo.

## 5. Spike de verificación (antes de pagar o confiar en los datos)

Con la key de FootyStats (y red que permita `api.football-data-api.com`):

1. `jevs footystats leagues --country Colombia`: anotar los `season_id` de Primera A y su profundidad
   histórica. Copiarlos en `config/default.yaml` (`footystats_season_ids`).
2. Descargar una temporada y comparar 10 partidos contra una fuente independiente (goles, goles 1T, córners).
3. Confirmar los nombres reales de los campos; corregir `FIELDS` / `ODDS_FIELDS` si difieren y guardar una
   respuesta real sin key en `tests/contract/fixtures/`.
4. Medir por temporada el porcentaje de partidos con córners 1T (explícitos o derivados).
5. Preguntar a FootyStats de qué casa y de qué momento son las cuotas `odds_*`.
6. Revisar los términos de uso (uso comercial, almacenamiento, redistribución).
7. The Odds API: `GET /v4/sports` con la key gratuita para ver si existe Primera A.

Criterio para aceptar el ADR: córners FT y 1T disponibles en al menos 5 temporadas con > 95% de cobertura,
y concordancia con la fuente independiente en los 10 partidos revisados.

## 6. Resultados del spike (2026-10-02, key de prueba)

Red: `api.football-data-api.com` accesible. `www.football-data.co.uk` redirige a `football-data.co.uk`, que la
política de red del entorno bloquea; `api.the-odds-api.com` también está bloqueado (y no hay key). Como fuente
independiente se usó la copia de football-data.co.uk que publica datahub.io
(`datasets/football-datasets`, sin columnas de cuotas).

**Alcance de la key de prueba**: Premier League 2018/19 a 2024/25 y Liga MX 2019/20. Colombia Primera A
existe en el catálogo (14 temporadas, 2013 a 2026; ids en `config/default.yaml`), pero descargarla responde
HTTP 417 "League is not chosen by the user". **Los puntos 1, 2 y 4 no se pueden cerrar para Colombia con
esta key**; lo que sigue se midió en la Premier League.

1. Season ids: listados para Colombia (ver arriba). Profundidad: 2013 a 2026.
2. Concordancia con football-data.co.uk, Premier League, 2.660 partidos:

   | Temporada | Goles FT y 1T iguales | Córners FT iguales | FootyStats menor / mayor | O/U 9.5 córners liquida igual |
   | --- | --- | --- | --- | --- |
   | 2018/19 | 100% | 98,9% | 1 / 3 | 99,5% |
   | 2019/20 | 100% | 99,5% | 2 / 0 | 100% |
   | 2020/21 | 99,7% | 95,8% | 14 / 2 | 99,2% |
   | 2021/22 | 100% | 95,0% | 18 / 1 | 99,5% |
   | 2022/23 | 100% | 96,3% | 12 / 2 | 99,2% |
   | 2023/24 | 100% | 93,9% | 21 / 1 | 99,5% |
   | 2024/25 | 100% | 93,2% | 25 / 1 | 98,9% |

   En la muestra aleatoria de 10 partidos de 2024/25 (semilla 8), goles 10/10 y córners **8/10**. Las
   diferencias son casi siempre de un córner y casi siempre a la baja en FootyStats, y crecen en las
   temporadas recientes: apunta a córners no registrados, no a ruido. **El criterio de concordancia no se
   cumple.** Sin una tercera fuente (oficial) no se puede decir cuál de las dos acierta.
3. Nombres de campos: todos los de `FIELDS` y `ODDS_FIELDS` existen con esos nombres. `team_*_corner_timings`
   **no existe** en `league-matches` (solo `corner_timings_recorded`), así que la derivación por minutos no se
   activa con este endpoint. Hay además `team_*_2h_corners`, `team_*_xg`, ataques y ataques peligrosos.
   Respuesta real sin key guardada en `tests/contract/fixtures/footystats_league_matches_real_epl_2425.json`.
4. Córners 1T:

   | Temporada | Con valor explícito | Coherente (1T + 2T = FT) |
   | --- | --- | --- |
   | 2018/19 | 100% | 99,5% |
   | 2019/20 | 97,1% | 97,1% |
   | 2020/21 | 100% | 99,7% |
   | 2021/22 | 100% | 98,7% |
   | 2022/23 | 100% | 97,9% |
   | 2023/24 | 100% | 94,7% |
   | 2024/25 | 98,2% | 95,0% |
   | Liga MX 2019/20 | 94,2% | 91,6% |

   Hay partidos con splits imposibles (p. ej. Leicester-Bournemouth 2024/25: local 1 córner en el 1T y 0 en
   el total). El adaptador ahora descarta el valor del 1T cuando contradice el total (queda como faltante y
   se anota `*_1h_corners_inconsistent_with_total`). Con ese filtro, 6 de 7 temporadas superan el 95%.
5. Casa y momento de las cuotas `odds_*`: pendiente de preguntar a FootyStats. Cubren O/U goles FT (0.5 a 4.5),
   1T (0.5 a 3.5) y córners FT (7.5 a 11.5) en ~100% de los partidos desde 2019/20. Las O/U 0.5 traen a veces
   1.00, que el motor de calidad rechaza.
6. Términos de uso: la respuesta remite a https://footystats.org/api/documentations/terms-of-use-and-legal;
   revisión legal pendiente.
7. The Odds API: no comprobado (host bloqueado por la red del entorno, sin key).

Otros hallazgos aplicados al código:

- Cada respuesta incluye `metadata.request_remaining`; guardarlo hacía que la misma temporada tuviera un hash
  distinto en cada descarga, duplicaba filas por payload y abortaba el experimento ("multiple versions of a
  statistic"). El adaptador ya no guarda `metadata`.
- HTTP 417 (liga no elegida) da ahora un error claro en lugar de un "HTTP 417" genérico.
- Límite real del plan: 1.800 peticiones por hora (cabecera `request_limit`).

**Estado**: sigue **propuesto**. Siguiente paso: activar Colombia Primera A en la cuenta de FootyStats (o una
key de pago), repetir los puntos 2 y 4 con Colombia y conseguir una tercera fuente para dirimir los córners.

## Fuentes

- [FootyStats API](https://footystats.org/api) y [Match Details](https://footystats.org/api/documentations/match-details)
- [FootyStats: Colombia Primera A](https://footystats.org/colombia/categoria-primera-a)
- [DIMAYOR nombra a Stats Perform socio oficial de datos](https://www.prnewswire.co.uk/news-releases/dimayor-names-stats-perform-as-official-data-partner-896423015.html)
- [DIMAYOR renueva con Stats Perform tras el acuerdo con Genius](https://tech.sportbusiness.com/news/dimayor-follows-genius-agreement-with-fresh-stats-perform-deal/)
- [Genius distribuirá los datos de apuestas de DIMAYOR](https://igamingbusiness.com/sports-betting/genius-to-distribute-betting-data-for-colombian-football-leagues/)
- [DIMAYOR, Wyscout y Smrt Stats](https://www.winsports.co/futbol-colombiano/noticias/presidente-de-la-dimayor-aclaro-la-situacion-con-wyscout-374173)
- [The Odds API: fútbol](https://the-odds-api.com/sports-odds-data/football-odds.html)
- [OpenFoot API](https://openfootapi.com/docs)
