# Top Candidates Repository

Este documento centraliza las estrategias ("hipótesis") que ya pasaron una rigurosa auditoría matemática ("Lookahead-Free"), fueron sometidas a un "Walk-Forward" u optimización profunda de 4 años, y demuestran retornos netos positivos sostenibles frente al mercado de forma real.

---

## 🟢 1. ABC Reversal
* **Archivo:** `pulpoh/hypotheses/abc_reversal`
* **Tipo:** Spot (Solo Long)
* **Mecánica:** Detecta caídas en 3 ondas (Corrección ABC Elliott Wave), verifica filtro de Soporte/Resistencia, y compra el piso estadístico.
* **Reporte Oficial de Rendimiento:** Revisar el artifact `spot_analysis_report.md` originado durante el testing masivo de Marzo 2026.

### Seteos Recomendados por Moneda
El motor determinó que los niveles de Take Profit deben ajustarse según la volatilidad específica del activo. Operan nativamente en gráficos de **1 Hora**:

| Moneda      | TP %    | SL %   | Retorno Promedio Anualizado (2022-2026) | Notas del Motor                                                                              |
| :---------- | :------ | :----- | :-------------------------------------- | :------------------------------------------------------------------------------------------- |
| **SOLUSDT** | `9.0%`  | `2.0%` | **+20.0%** (Sostenido)                  | **★ LA MEJOR ESTADÍSTICAMENTE.** Armonía perfecta de volatilidad para este patrón.           |
| **BTCUSDT** | `8.0%`  | `1.5%` | **+7.7%** (Defensivo)                   | Extremadamente seguro contra desplomes (Bear Markets), pero menores retornos en Bulls.       |
| **BNBUSDT** | `10.0%` | `2.0%` | Altamente Variable                      | Salva tu cuenta en Bulls masivos (llega a +100%), pero puede drawdown fuerte en osos (-40%). |
| ~ETHUSDT~   | `9.0%`  | `1.5%` | Negativo                                | *Incompatible* estadísticamente con este setup en 1H Spot.                                   |

---

## 📈 2. Trend Following (Surfista de Tendencias))
* **Archivo:** `pulpoh/hypotheses/trend_following`
* **Tipo:** Spot Direccional Macro (Solo Long)
* **Mecánica:** Opera en velas Diarias (1D). Dispara una orden de compra cuando el precio rompe el punto máximo de los últimos 10 días (Ruptura Donchian) con validación de volumen. No tiene "Take Profit" fijo. Se mantiene invertido utilizando un Stop Loss Dinámico (Trailing Stop) amplio que persigue al precio hasta que la macrotendencia se quiebra.

### Seteos Recomendados por Moneda
Esta estrategia sacrifica meses de rentabilidad negativa o plana a cambio de agarrar el 100% de los grandes "Bull Runs" parabólicos ("win rate" bajo pero "risk-reward" monstruoso):

| Moneda      | Trailing Stop % | Donchian Period | Retorno Promedio Anualizado (2022-2026) | Notas del Motor                                                                                                                              |
| :---------- | :-------------- | :-------------- | :-------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------- |
| **BTCUSDT** | `15.0%`         | `10 Días`       | **+76.7%** (Explosivo)                  | **★ LA MAYOR POTENCIA MACRO.** Perdió capital en el mercado bajista de 2022, pero generó casi un +400% de ganancia durante el Rally de 2024. |
| **ETHUSDT** | `15.0%`         | `10 Días`       | **+57.4%** (Sostenido)                  | Excelente desempeño absorbiendo los rallies alcistas de Ethereum con un margen de maniobra idéntico al de Bitcoin.                           |

---
*Para agregar nuevas candidates, asegurar que fueron puestas a prueba sin Lookahead Bias por al menos 4 años.*
