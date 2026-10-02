# ADR-0004: Reutilizar JEV Trading copiando y adaptando, sin dependencia compartida

- Estado: propuesto
- Fecha: 2026-10-02

## Contexto

`JaimeGallo/Multi-broker` (JEV Trading) tiene utilidades sólidas: secretos solo desde entorno, logs
JSON con secretos ocultos, configuración por capas, IDs deterministas, compuerta de seguridad contra
dinero real y un contrato de modelo puro. Pero está en Fase 2, sin tests, y su dominio (trading
intradía) es distinto.

## Decisión

Copiar a `packages/common/` de este repositorio, con atribución en el encabezado de cada fichero:
`secrets.py`, `logging.py`, `config.py` (prefijo `JEVS__`), `ids.py`, `clock.py`, `errors.py` y una
versión adaptada de `safety.py`. Tomar `packages/jev/base.py`, `registry.py` y
`packages/data_quality/engine.py` como patrón, no como código.

No crear todavía un paquete compartido entre ambos repositorios.

## Consecuencias

- Los dos proyectos evolucionan sin romperse entre sí.
- Si las utilidades comunes se estabilizan en ambos, se puede extraer un paquete `jev-common` más
  adelante.
- Los tests de estas utilidades se escriben aquí, ya que el origen aún no los tiene.
