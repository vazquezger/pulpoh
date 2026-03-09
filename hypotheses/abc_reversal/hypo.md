# ABC Reversal Hypothesis

## Concepto
Aproximación algorítmica de la corrección de Elliott (Onda ABC) dentro de una tendencia alcista o bajista macro.
Busca identificar un patrón de tres ondas correctivas (A, B, C) que ocurren en dirección opuesta a la tendencia principal, e intenta capturar el próximo impulso a favor de la tendencia original una vez que la onda C finaliza.

## Patrón Buscado
El patrón ABC se identifica encontrando pivotes relativos (mínimos o máximos locales):
1. **Onda A**: Fuerte movimiento contra la tendencia macro. (ej. Caída desde un máximo relativo `PH0` hasta `PL0` en Longs).
2. **Onda B**: Rebote o consolidación intermedio, sin superar el inicio de A (ej. Sube desde `PL0` a `PH1`, pero `PH1` < `PH0`).
3. **Onda C**: Último empuje contra la tendencia macro, profundo (ej. Cae desde `PH1` a `PL1`, al menos `C_DEPTH_MIN` de lo que recorrió A).
   - *Entrada*: Al cierre de la primera vela siguiente a la confirmación del pivote que cierra la Onda C (ej. `PL1` en Longs o `PH1` en Shorts).

## Filtros
Para confirmar la entrada, se evalúan un conjunto de filtros técnicos:
- **Tendencia Macro (EMA 200)**: Operar a favor de la tendencia mayor (el precio debe estar por encima de EMA200 para operar en Long, o por debajo para Short).
- **Volatilidad / Momento (ATR)**: Busca que la volatilidad esté expandiéndose (`ATR 14 > ATR 50`). Ayuda a evitar entrar en consolidaciones estrechas sin fuerza.
- **RSI**: Filtra posibles entradas si el mercado ya está demasiado sobrecomprado (para vender) o sobrevendido (para comprar), y espera la recuperación o el techo.
  - Para Longs: `RSI <= rsi_max` (en la vela de señal o la anterior).
  - Para Shorts: `RSI >= 100 - rsi_max`.
- **Soporte y Resistencia (SR)**: Opcionalmente (`use_sr_filter: true`), exige que el final de la Onda C ocurra cerca de un nivel histórico de Soporte (para Longs) o Resistencia (para Shorts).
  - Se revisan los últimos `sr_lookback` pivots.
  - El precio de la Onda C debe rebotar a no más de `sr_tolerance_pct` (ej. 1%) de la zona de liquidez de SR previa.

## Configuración y Parámetros (`config.json`)
- `signal_interval` / `execution_interval`: Intervalo de las velas en las que se calculan los indicadores y pivots (por defecto `1h`).
- `trade_direction`: Controla si operar en `long`, `short` o `both`.
- `exit_model`: Normalmente `AsymmetricComboExit`. Las salidas están configuradas con TPs amplios (ej. 12% Long, 6% Short) dado el timeframe de 1h.
- `use_sr_filter` / `sr_lookback` / `sr_tolerance_pct`: Parámetros para activar y afinar el chequeo de soporte/resistencia histórico.
- `rsi_max`: Umbral para RSI (por defecto 50, en un RSI modificado sobre deltas del precio).

### Parámetros internos en el código (`hypothesis.py`)
- `PIVOT_WINDOW = 2`: Cuántas velas a cada lado determinan un pivot válido.
- `C_DEPTH_MIN = 0.30`: La onda C debe recorrer por lo menos el 30% del camino que recorrió la Onda A.
- `EMA_TREND = 200`: Longitud de la media móvil para el filtro macro.

---
*Nota para Agentes*: Utiliza este archivo como punto de referencia para entender rápidamente la lógica de entrada, filtros y parámetros de esta hipótesis.
