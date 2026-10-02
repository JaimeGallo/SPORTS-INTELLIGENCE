# ADR-0006: Sin dinero real ni integración con casas de apuestas

- Estado: propuesto
- Fecha: 2026-10-02

## Decisión

- El sistema produce predicciones, backtests y simulación (paper). No contiene clientes de casas de
  apuestas, automatización de navegadores ni almacenamiento de credenciales de operadores.
- Kelly fraccional existe solo en el simulador y está deshabilitado por defecto.
- No se implementan estrategias de martingala ni de persecución de pérdidas.
- La interfaz usa lenguaje probabilístico: estados `no_edge`, `potential_edge`, `validated_edge` e
  `insufficient_evidence`; nunca "seguro", "fijo" o "apuesta".
- Cualquier integración futura con operadores sería un proyecto separado, con APIs oficiales y
  sujeto a las condiciones del operador y la ley aplicable.
