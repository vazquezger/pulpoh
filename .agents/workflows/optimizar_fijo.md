---
description: Optimizar una hipótesis con walkforward (parámetros fijos) y testear en otras criptos (SOL, BNB, ETH)
---

# Flujo de Optimización y Pruebas Multi-Coin

Este workflow estandariza el proceso de ajustar parámetros de una hipótesis mediante walkforward simulation y luego probar su robustez en altcoins volátiles.

1. **Revisar `optimize.json`**:
   Verificar que exista `optimize.json` en la carpeta de la hipótesis objetivo. Si no existe, pedirle al usuario los rangos o generarlo en base al `config.json` actual.

2. **Ejecutar Walk-Forward**:
   // turbo
   Ejecutar el comando de walkforward para la hipótesis: `python walkforward.py <nombre_hipotesis>`

3. **Aplicar Mejores Parámetros**:
   Leer los resultados del walkforward y actualizar los parámetros en el `config.json` local con los que mostraron mejor rendimiento robusto (evitando overfitting).

4. **Pruebas de Robustez (Multi-Coin)**:
   Modificar temporalmente el `config.json` para testear en altcoins de alta volatilidad:
   `"symbols": ["SOLUSDT", "BNBUSDT", "ETHUSDT"]`

5. **Correr Test Multi-Coin**:
   // turbo
   Ejecutar la estrategia en los nuevos símbolos: `python run.py <nombre_hipotesis>`

6. **Analizar y Reportar**:
   Revisar los resultados (`report.md` de la corrida) y presentarle al usuario un resumen de cómo rindió la hipótesis en SOL, BNB y ETH en comparación con la cripto original. Generar un `informe-YYYYMMDD.md` en la carpeta `results/` de la hipótesis.

7. **Restaurar**:
   Devolver el `config.json` a sus símbolos originales (por ej. `["BTCUSDT"]`) para dejar la hipótesis limpia.
