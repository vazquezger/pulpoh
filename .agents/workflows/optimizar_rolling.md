---
description: Optimizar una hipótesis usando ventanas móviles continuas (Rolling Walk-Forward)
---

# Flujo de Optimización Continua (Rolling)

Este workflow evalúa una hipótesis bajo un esquema de re-optimización continua. A diferencia del walkforward por años predefinidos, aquí la estrategia "aprende" de los últimos N días y opera los siguientes M días repetidamente. Es ideal para evaluar si la estrategia tiene ventaja combinada con reajuste constante.

1. **Ejecutar Rolling Walk-Forward**:
   // turbo
   Ejecutar la optimización continua sobre la hipótesis objetivo. (Ajustar `--train-days` y `--test-days` según sea necesario).
   `python framework/scripts/optimize_rolling.py <nombre_hipotesis>`

2. **Analizar la Viabilidad del Reajuste Continuo**:
   Revisar el resultado final "*ROLLING WALK-FORWARD RESULT (Continuous)*". Si las métricas (Net Return, Sharpe) son buenas, indica que la estrategia sobrevive y prospera si se re-optimiza periódicamente.

3. **Pruebas de Robustez (Multi-Coin)**:
   Para confirmar que este proceso de re-optimización es válido en otros activos:
   // turbo
   `python framework/scripts/optimize_rolling.py <nombre_hipotesis> --symbol SOLUSDT`
   // turbo
   `python framework/scripts/optimize_rolling.py <nombre_hipotesis> --symbol BNBUSDT`
   // turbo
   `python framework/scripts/optimize_rolling.py <nombre_hipotesis> --symbol ETHUSDT`

4. **Comparación y Decisión Operativa**:
   Comparar este resultado con el workflow estático (`optimizar.md`). Si el *Rolling* rinde mejor y es más estable, se recomienda implementar un esquema de bot en producción que se encargue de re-optimizar parámetros cada semana, en lugar de utilizar parámetros fijos codificados.
