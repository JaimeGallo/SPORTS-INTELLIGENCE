# Fuentes de datos: evaluación (Fase 0)

Fecha de la evaluación: 2026-10-02.

> **Cómo leer este documento.** Las capacidades marcadas **[confirmado]** salen de la documentación
> pública del proveedor o de fuentes secundarias consistentes. Las marcadas **[verificar]** son
> probables pero hay que comprobarlas con una key real antes de comprometer el MVP (ver "Spike de
> proveedores" al final). Los precios cambian: revisarlos en la web del proveedor antes de contratar.
> Durante la Fase 0 el entorno de trabajo no tenía acceso directo a los sitios de los proveedores, así
> que la evidencia viene de búsquedas web (fuentes al final).

## 1. Pregunta clave: ¿football-data.org trae córners gratis?

**No.** El plan gratuito de football-data.org (12 competiciones, 10 peticiones/minuto) incluye
calendario, resultados (con marcador al descanso) y tablas, pero **no estadísticas de partido**.

- Las estadísticas (`corner_kicks`, tiros, posesión, faltas, fueras de juego, etc.) existen en el
  recurso Match de la API v4, pero vienen con el **add-on "Statistics" (~15 EUR/mes)**, que además
  **exige un plan de pago** base. [confirmado]
- Las alineaciones, cambios y goleadores van en planes "Deep Data" (~29 EUR/mes). [confirmado]
- No hay evidencia de que las estadísticas vengan **por mitad**. El marcador al descanso sí existe.
  Por tanto, **córners del primer tiempo: no disponibles**. [verificar, probable no]
- No ofrece cuotas.

Conclusión: football-data.org sirve como fuente secundaria de calendario y resultados, pero **no
resuelve los córners** y, si hay que pagar, hay opciones mejores.

## 2. Matriz de capacidades (corregida)

| Proveedor | Calendario / resultados | Goles 1T | Córners FT | Córners 1T | Estadísticas | Cuotas | Cuotas históricas | Coste aprox. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| football-data.org (gratis) | sí | sí (marcador HT) | **no** | **no** | no | no | no | 0 |
| football-data.org + Statistics | sí | sí | sí | no [verificar] | sí | no | no | ~15 EUR + plan base |
| football-data.co.uk (CSV) | sí | sí (HTHG/HTAG) | sí (HC/AC) | **no** | tiros, faltas, tarjetas | 1X2, O/U 2.5, AH (cierre incl.) | sí, en el propio CSV | 0 |
| API-Football (api-sports) | sí | sí | sí | sí, `half` en `/fixtures/statistics` [verificar temporadas] | sí | sí, incl. córners [verificar] | retención corta [verificar] | 0 / 19 / 29 / 39 USD/mes |
| Sportmonks v3 | sí | sí | sí | sí, `include=periods.statistics` | sí, xG en add-on | add-on Premium Odds ~129 EUR/mes | add-on histórico (pago único desde ~29 EUR) | 29 / 99 / 249 EUR/mes |
| The Odds API | eventos | n/a | n/a | n/a | no | sí, incl. `alternate_totals_corners` | sí, solo planes de pago; mercados adicionales desde 2023-05-03 | 0 (500 créditos) a 249 USD/mes |
| Sportradar | sí | sí | sí | sí (timeline) | sí | según producto | según producto | contrato enterprise |

Notas:

- **football-data.co.uk** es un sitio distinto de football-data.org. Publica CSV gratuitos por liga y
  temporada con resultados, marcador al descanso, estadísticas básicas (incluidos córners del partido
  completo) y cuotas de varias casas (incluidas cuotas de cierre de Pinnacle y medias de mercado para
  1X2, Over/Under 2.5 y hándicap asiático). No tiene córners por mitad ni cuotas de córners.
  Licencia: uso libre pero sin garantías; revisar condiciones antes de redistribuir.
- **The Odds API**: `alternate_totals_corners` y `alternate_spreads_corners` existen como mercados
  adicionales de fútbol, pero la cobertura de mercados adicionales depende de la casa y la región
  (históricamente centrada en casas de EE. UU.). Cada consulta histórica cuesta 10 créditos por región
  y mercado. [verificar cobertura de córners y totales 1T en ligas europeas]
- **Sportradar**: datos de máxima calidad, pero requiere contrato y su licencia restringe el uso. No
  tiene sentido para el MVP salvo que ya exista un acuerdo.

## 3. Recomendación

### Estadísticas (incluidos córners por mitad)

**Primaria recomendada: Sportmonks (plan Growth, ~99 EUR/mes, 30 ligas).**

- Cubre las 6 competiciones del MVP con margen.
- Expone estadísticas por periodo (`periods.statistics`), que es exactamente lo que necesitan los
  modelos de córners 1T.
- API v3 bien documentada, IDs estables, trial de 14 días: podemos validar antes de pagar.
- Tiene add-on de cuotas, aunque no es imprescindible (ver abajo).

**Alternativa económica: API-Football (plan Pro, ~19 USD/mes).**

- Todas las funciones en todos los planes; parámetro `half` para estadísticas por mitad.
- Más barata, pero con reputación más irregular en consistencia de datos de ligas menores. Para las
  6 grandes competiciones suele ser suficiente.
- Riesgo a verificar: desde qué temporada hay estadísticas por mitad (puede limitar el histórico).

Si el presupuesto lo permite, Sportmonks como primaria y API-Football como secundaria de
reconciliación (dos fuentes para detectar conflictos, sección 42 del prompt).

### Histórico base gratuito

**football-data.co.uk** para arrancar ya, a coste cero:

- Goles FT y 1T, córners FT y cuotas de cierre de O/U 2.5 desde hace muchas temporadas.
- Permite ejecutar la primera parte del experimento sin contratar nada.

### Cuotas

**The Odds API (plan de 30 USD/mes o superior)** para cuotas pre-match y snapshots históricos.

- Las cuotas históricas de córners y de primer tiempo son el dato **más escaso del mercado**. Ningún
  proveedor asequible ofrece años de histórico de córners por mitad con cobertura europea fiable.
- Estrategia: (1) usar el histórico de 2023-05 en adelante que exista, (2) empezar a **guardar
  snapshots propios desde ya**, porque cada semana sin recolectar es histórico que se pierde.

### Lo que NO recomiendo

- Pagar el add-on de football-data.org: cuesta casi lo mismo que API-Football y no da córners 1T.
- Scraping de webs de estadísticas o de casas de apuestas: frágil y con problemas de licencia
  (sección 69 del prompt).

## 4. Variables de entorno resultantes

```text
FOOTBALL_DATA_ORG_API_KEY   # opcional, fuente secundaria de calendario
SPORTMONKS_API_TOKEN        # primaria de estadísticas (si se aprueba)
API_FOOTBALL_KEY            # alternativa o secundaria
ODDS_API_KEY                # cuotas
SPORTRADAR_API_KEY          # solo si hay contrato
JEV_SPORTS_API_TOKEN        # token propio de la API de este sistema (no compartir con JEV Trading)
```

No se reutiliza `JEV_API_TOKEN` de Multi-broker: allí protege la API propia de JEV Trading (Fase 5,
aún sin implementar) y no da acceso a ningún dato deportivo. Ver ADR-0005.

## 5. Spike de proveedores (antes de pagar)

Tarea corta, con keys de trial o gratuitas, para pasar de [verificar] a [confirmado]:

1. Sportmonks (trial): descargar 1 partido de Premier League de cada una de las últimas 3 temporadas
   con `include=periods.statistics` y comprobar córners por mitad.
2. API-Football (gratis, 100 peticiones/día): `/fixtures/statistics?fixture=X&half=true` para un
   partido de 2021, 2023 y 2025; anotar desde qué temporada hay datos por mitad.
3. The Odds API (500 créditos gratis): listar mercados de un partido de Premier League en región
   `eu` y `uk` y comprobar si aparecen `alternate_totals_corners` y totales de primer tiempo, y de
   qué casas.
4. Guardar las respuestas crudas en `data/fixtures/providers/` (sin keys) como base de los
   *contract tests*.

Coste: 0. Duración estimada: medio día.

## Fuentes

- [football-data.org Free Tier Limits 2026 (TheStatsAPI)](https://www.thestatsapi.com/blog/football-data-org-free-tier-limits-2026)
- [football-data.org source research (Bruin)](https://getbruin.com/docs/ingestr/soccer-sources/football-data-org.html)
- [football-data API v4: Match](https://docs.football-data.org/general/v4/match.html)
- [Sportmonks: planes y precios](https://www.sportmonks.com/football-api/plans-pricing/)
- [Sportmonks v3: Periods](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/includes/periods)
- [Sportmonks v3: Fixture statistics](https://docs.sportmonks.com/v3/definitions/types/statistics/fixture-statistics)
- [Sportmonks v3: Odds FAQ](https://docs.sportmonks.com/v3/faq/odds)
- [API-Sports](https://api-sports.io/)
- [API-Football en SportsAPI.com](https://sportsapi.com/api-directory/api-football/)
- [The Odds API: mercados](https://the-odds-api.com/sports-odds-data/betting-markets.html)
- [The Odds API: datos históricos](https://the-odds-api.com/historical-odds-data/)
- [The Odds API: documentación v4](https://the-odds-api.com/liveapi/guides/v4/)
- [Comparativa de precios de APIs de cuotas 2026 (OddsPapi)](https://oddspapi.io/blog/odds-api-pricing-2026-comparison/)
- [Sportradar Soccer: Match Stats API](https://docs.sportradar.com/soccer-media/static-endpoints-restful/match-stats-api)

## 6. Colombia (añadido el 2026-10-02)

La evaluación de fuentes para la Liga BetPlay (FootyStats, API-Football, Sportradar, Opta, OpenFoot) y la
decisión propuesta están en [ADR-0008](adr/0008-colombia-focus-and-footystats.md). El adaptador
`packages/providers/footystats.py` está implementado y verificado contra respuestas reales con la key de
prueba (Premier League 2018/19 a 2024/25); los resultados del spike están en la sección 6 del ADR. Colombia
no está incluida en esa key.
