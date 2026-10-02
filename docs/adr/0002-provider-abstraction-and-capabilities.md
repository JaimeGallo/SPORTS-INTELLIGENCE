# ADR-0002: Abstracción de proveedores con capacidades declaradas por configuración

- Estado: propuesto
- Fecha: 2026-10-02

## Contexto

Ningún proveedor cubre todo: football-data.org gratis no trae córners, los CSV de football-data.co.uk
no traen córners por mitad, las cuotas históricas de córners son escasas. Los proveedores usan IDs y
nombres distintos para los mismos equipos y partidos.

## Decisión

- Interfaces `DataProvider` y `OddsProvider`; cada adapter declara sus capacidades en
  `config/providers.yaml`. Pedir una capacidad no declarada lanza un error; nunca se devuelven datos
  vacíos que parezcan reales.
- Los adapters devuelven objetos crudos con el ID del proveedor. Solo la capa de normalización asigna
  IDs canónicos, mediante `provider_entity_map`.
- Toda respuesta cruda se guarda con su hash para reproducir sin depender de la API.
- Cuando dos fuentes discrepan en un dato crítico se registra un `data_quality_event`; no se elige en
  silencio.

## Consecuencias

- Cambiar de proveedor (por ejemplo de API-Football a Sportmonks) no cambia IDs canónicos ni modelos.
- Hay que mantener el mapeo de equipos, con revisión manual de los casos dudosos.
