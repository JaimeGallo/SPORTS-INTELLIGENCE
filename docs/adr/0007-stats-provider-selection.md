# ADR-0007: Selección del proveedor de estadísticas

- Estado: **pendiente de decisión** (tras el spike de la Fase 0.5)
- Fecha: 2026-10-02

## Contexto

Los mercados de córners de primer tiempo necesitan estadísticas por mitad. football-data.org no las
ofrece en su plan gratuito (las estadísticas son un add-on de pago y no hay evidencia de que vengan
por mitad). Los CSV de football-data.co.uk solo traen córners del partido completo.

## Opciones

| Opción | Coste aprox. | A favor | En contra |
| --- | --- | --- | --- |
| Sportmonks Growth | ~99 EUR/mes | `periods.statistics`, IDs estables, 30 ligas, trial de 14 días | Más caro; cuotas en add-on aparte |
| API-Football Pro | ~19 USD/mes | Barato, todas las funciones, parámetro `half` | Calidad más irregular; temporadas con datos por mitad por verificar |
| Sportradar | contrato | Máxima calidad, timeline y live | Coste y licencia restrictiva |
| football-data.org + Statistics | ~15 EUR + plan base | Ya conocido | Sin córners por mitad: no resuelve el problema |

## Propuesta

Sportmonks como primaria y API-Football como secundaria de reconciliación si el presupuesto lo
permite. Si solo se paga uno, decidir con los resultados del spike (cobertura por mitad en las
temporadas 2021/22 a 2025/26 de las 6 competiciones).
