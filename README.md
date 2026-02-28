# pulpoh 📊

Un laboratorio para testear ideas de trading. Bajás datos reales de Binance, describís tu hipótesis en código, y el sistema te dice si la idea gana o pierde plata históricamente.

---

## La idea en una línea

> *"Si cada vez que pasa X compro Y coin, ¿cuánto hubiera ganado en 2022 y 2024?"*

Eso es lo que hace este sistema. Vos definís el "X", el resto lo hace solo.

---

## Cómo está organizado

```
pulpoh/
│
├── framework/        ← El motor. No lo tocás.
│   └── data/         ← Los datos descargados de Binance (se guardan acá)
│
└── hypotheses/       ← Tus ideas van acá, una carpeta por hipótesis
    └── green_near_low_high/
        ├── hypothesis.py   ← La lógica de la idea (~20 líneas)
        ├── config.json     ← Qué coins, qué años, cómo salir
        └── results/        ← Los resultados se generan acá
```

---

## Para correr una hipótesis

```bash
python run.py green_near_low_high
```

Eso hace todo: baja los datos si no los tiene, detecta señales, simula los trades, y guarda los resultados en `hypotheses/green_near_low_high/results/`.

```bash
python run.py --list              # Ver todas las hipótesis disponibles
python run.py green_near_low_high --signals-only # Solo muestra las señales, no simula trades
python run.py green_near_low_high --refresh-data # Fuerza re-descarga de datos
```

---

## 🏃‍♂️ Walk-Forward Validation (Validación robusta)

Para evitar overfitting, el framework incluye un motor de *Walk-Forward Validation*. Optimiza parámetros en datos pasados y los prueba "a ciegas" en el futuro.

1. Creá un archivo `optimize.json` en tu hipótesis (ej: `hypotheses/abc_reversal/optimize.json`):
```json
{
    "walkforward_windows": [
        {"train": [2022], "validate": 2023},
        {"train": [2022, 2023], "validate": 2024}
    ],
    "param_grid": {
        "PIVOT_WINDOW": [2, 3],
        "exit_params.tp_pct": [4.0, 6.0],
        "exit_params.sl_pct": [0.5, 1.0]
    }
}
```
2. Corré el validador:
```bash
python walkforward.py abc_reversal
```
Esto te dirá si tu estrategia realmente funciona o si solo memorizó el pasado.

---

## Qué genera cada corrida

Por cada combinación de **coin × año** que configurés, se crea una carpeta:

```
results/
├── 2022_BTCUSDT/
│   ├── report.md          ← Resumen con todas las métricas
│   ├── trades.csv         ← Cada trade simulado en detalle
│   ├── equity_curve.png   ← Gráfico de cómo creció (o bajó) el capital
│   └── monthly_returns.png
└── summary.md             ← Tabla comparativa de todos los años/coins juntos
```

---

## Agregar una nueva hipótesis (4 pasos)

### 1. Crear la carpeta
```
hypotheses/mi_idea/
```

### 2. Crear `config.json` — qué testear y cómo salir
```json
{
  "name": "Mi Hipótesis",
  "description": "Qué estoy testeando",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "years": [2022, 2023, 2024],
  "signal_interval": "1h",
  "exit_model": "ComboExit",
  "exit_params": { "tp_pct": 2.0, "sl_pct": 1.0, "max_hours": 48 }
}
```

### 3. Crear `hypothesis.py` — la lógica de entrada
```python
from framework.base_hypothesis import BaseHypothesis
import pandas as pd

class Hypothesis(BaseHypothesis):
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # df tiene columnas: open, high, low, close, volume, timestamp
        # Retorná True en las filas donde querés entrar
        # El trade se ejecuta al open de la SIGUIENTE vela
        return df['close'] > df['open']  # ejemplo: cualquier vela verde
```

### 4. Correr
```bash
python run.py mi_idea
```

---

## Modelos de salida disponibles

| Opción         | Qué hace                                                   |
| -------------- | ---------------------------------------------------------- |
| `FixedTPSL`    | Sale al llegar al target de ganancia o límite de pérdida   |
| `TrailingStop` | El stop sigue el precio hacia arriba, bloqueando ganancias |
| `TimeBased`    | Sale después de N horas sin importar el P&L                |
| `ComboExit`    | TP + SL + tiempo máximo — **el más realista, recomendado** |

---

## Los datos

- Vienen de **Binance** (API pública, sin cuenta necesaria)
- Se guardan en `framework/data/{COIN}/{AÑO}/{timeframe}.csv`
- La primera vez se bajan solos, las siguientes se leen del disco
- Timeframes disponibles: `1m`, `5m`, `15m`, `1h`, `4h`, `1d`

---

## Cómo interpretar el reporte

| Métrica           | Qué significa                  | Bueno | Preocupante |
| ----------------- | ------------------------------ | ----- | ----------- |
| **Win Rate**      | % de trades que ganaron        | > 50% | < 40%       |
| **Profit Factor** | Ganancia total / Pérdida total | > 1.5 | < 1.0       |
| **Max Drawdown**  | Peor racha de pérdidas         | < 10% | > 25%       |
| **Sharpe Ratio**  | Retorno ajustado por riesgo    | > 1.5 | < 0.5       |

---

## Instalación

```bash
pip install -r requirements.txt
```

Requiere Python 3.10+.

---

## Nota importante

Los resultados son simulaciones sobre datos históricos. El pasado no garantiza resultados futuros. Este sistema es una herramienta de investigación, no un sistema de trading automático.
