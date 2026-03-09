# Trend Following (Momentum) 

## Concepto
Estrategia base de **Seguimiento de Tendencia** (Trend Following). 
A diferencia de los enfoques de Reversión a la Media (Mean-Reversion) que buscan tomar ganancias rápidas en rebotes, el Trend Following busca **posicionarse a favor de una gran marea del mercado** y aguantar la posición durante semanas o meses utilizando **Trailing Stops**.

## El Problema que Resuelve
Las estrategias de Mean-Reversion (como ABC Reversal) tienen "Take Profits" fijos (ej: 9%). Si el activo entra en un rally histórico (ej: sube un 300% en dos meses), el bot sale de la posición muy temprano y se pierde la ganancia macroeconómica. 
El Trend Following sacrifica la alta tasa de aciertos (Win Rate) a cambio de poder **capitalizar los grandes "Bull Runs"**.

## Posible Implementación Futura
1. **Timeframe:** Semanal (1W) o Diario (1D).
2. **Setup:** Ruptura (Breakout) de un canal de Donchian de 20 o 50 días.
3. **Gestión de Riesgo:** Take Profit infinito (no se toma ganancia fija). El Stop Loss se va moviendo (Trailing) utilizando el mínimo de los últimos N días, o un múltiple del ATR.
4. **Win Rate Esperado:** Bajo (30% - 40%). Cientos de pequeñas pérdidas (-2%), intercaladas con unas pocas ganancias masivas (+60%, +150%).
