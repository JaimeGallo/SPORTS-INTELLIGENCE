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

**Fase 0 (auditoría y propuesta), pendiente de aprobación.** Todavía no hay código.

- [Informe de la Fase 0](docs/phase-0-report.md): auditoría, estrategia de datos, primer experimento, decisiones pendientes
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
