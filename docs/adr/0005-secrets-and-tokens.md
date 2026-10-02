# ADR-0005: Secretos y tokens propios; no se comparte el token de JEV Trading

- Estado: propuesto
- Fecha: 2026-10-02

## Contexto

Se evaluó integrar en este proyecto la "API key de JEV" usada en Multi-broker. En Multi-broker,
`JEV_API_TOKEN` está reservado para autenticar las peticiones que *entran* a la API propia de JEV
Trading (Fase 5, aún sin implementar). No da acceso a ningún servicio ni a datos deportivos.

## Decisión

- No reutilizar `JEV_API_TOKEN`. Este proyecto tendrá su propio `JEV_SPORTS_API_TOKEN` cuando exista
  su API.
- Si en el futuro un sistema necesita consumir al otro, se emite un token de cliente dedicado y de
  solo lectura.
- Las keys de proveedores (`SPORTMONKS_API_TOKEN`, `API_FOOTBALL_KEY`, `ODDS_API_KEY`,
  `FOOTBALL_DATA_ORG_API_KEY`, `SPORTRADAR_API_KEY`) se leen solo del entorno o de un `.env` ignorado
  por Git. Nunca en YAML, base de datos, logs, `raw_payloads.request_params` ni frontend.
- Prefijo de configuración `JEVS__` para no colisionar con `JEV__` de JEV Trading en la misma máquina.

## Consecuencias

- Revocar o rotar un token no afecta al otro sistema; una filtración expone un solo sistema.
