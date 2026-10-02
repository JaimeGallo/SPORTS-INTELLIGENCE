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

## Fuentes

- [FootyStats API](https://footystats.org/api) y [Match Details](https://footystats.org/api/documentations/match-details)
- [FootyStats: Colombia Primera A](https://footystats.org/colombia/categoria-primera-a)
- [DIMAYOR nombra a Stats Perform socio oficial de datos](https://www.prnewswire.co.uk/news-releases/dimayor-names-stats-perform-as-official-data-partner-896423015.html)
- [DIMAYOR renueva con Stats Perform tras el acuerdo con Genius](https://tech.sportbusiness.com/news/dimayor-follows-genius-agreement-with-fresh-stats-perform-deal/)
- [Genius distribuirá los datos de apuestas de DIMAYOR](https://igamingbusiness.com/sports-betting/genius-to-distribute-betting-data-for-colombian-football-leagues/)
- [DIMAYOR, Wyscout y Smrt Stats](https://www.winsports.co/futbol-colombiano/noticias/presidente-de-la-dimayor-aclaro-la-situacion-con-wyscout-374173)
- [The Odds API: fútbol](https://the-odds-api.com/sports-odds-data/football-odds.html)
- [OpenFoot API](https://openfootapi.com/docs)
