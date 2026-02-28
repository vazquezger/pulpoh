# AGENTS.md — pulpoh

> Pegá este archivo al inicio de cualquier sesión con un LLM (ChatGPT, Claude, Gemini, Cursor, etc.)  
> El asistente entenderá el framework completo y podrá ayudarte a agregar hipótesis, debuggear resultados o modificar parámetros.

---

## ¿Qué es este proyecto?

`pulpoh` es un framework para que un trader profesional testee hipótesis de trading de forma rápida, ordenada y reproducible. Descarga datos históricos de Binance, simula trades y genera reportes estandarizados. Cada hipótesis vive en su propia carpeta aislada; el core del framework **nunca se modifica**.

---

## Arquitectura

```
pulpoh/
├── AGENTS.md                    ← Este archivo (contexto para LLMs)
├── requirements.txt
├── run.py                       ← Entry point principal
│
├── framework/                   ← ⚠️ NO MODIFICAR — core compartido
│   ├── base_hypothesis.py       ← Clase abstracta BaseHypothesis
│   ├── exit_models.py           ← Modelos de salida configurables
│   ├── downloader.py            ← Descarga de Binance con cache CSV
│   ├── backtester.py            ← Motor de simulación sin look-ahead bias
│   ├── reporter.py              ← Métricas + gráficos estandarizados
│   └── data/                   ← Cache de datos descargados
│       └── {SYMBOL}/
│           └── {YEAR}/
│               └── {interval}.csv   ← e.g. BTCUSDT/2024/1h.csv
│
└── hypotheses/                  ← Una carpeta por hipótesis
    └── h001_nombre_descriptivo/
        ├── hypothesis.py        ← ÚNICA clase a implementar (~30 líneas)
        ├── config.json          ← Configuración completa de la hipótesis
        └── results/             ← Auto-generado al correr (gitignoreado)
            ├── report.md
            ├── trades.csv
            ├── trades_chart.html
            ├── equity_curve.png
            └── monthly_returns.png
```

---

## Flujo de datos

```
config.json
    ↓
Downloader → framework/data/{symbol}/{year}/{interval}.csv (cache)
    ↓
hypothesis.generate_signals(df) → Series[bool]  ← LA ÚNICA FUNCIÓN QUE ESCRIBÍS
    ↓
Backtester + ExitModel → List[Trade]
    ↓
Reporter → results/ (report.md, trades.csv, charts)
```

---

## Principios de diseño

1. **Señales = solo entrada.** La hipótesis define *cuándo entrar*. La salida es responsabilidad de un ExitModel configurado en `config.json`.
2. **Sin look-ahead bias.** La entrada es siempre al `open` de la vela *siguiente* a la señal.
3. **Cache de datos.** Si `framework/data/{symbol}/{year}/{interval}.csv` existe, no se vuelve a bajar. Para refrescar, borrar el archivo manualmente.
4. **Reportes idénticos.** Todas las hipótesis generan exactamente el mismo formato de reporte, facilitando la comparación.
5. **El framework no se toca.** Todo cambio de lógica va en `hypothesis.py` o `config.json`.

---

## Exit Models disponibles

| Nombre         | Descripción                             | Parámetros                      |
| -------------- | --------------------------------------- | ------------------------------- |
| `FixedTPSL`    | Take profit y stop loss fijos           | `tp_pct`, `sl_pct`              |
| `TrailingStop` | Stop que sigue el precio                | `trail_pct`                     |
| `TimeBased`    | Sale después de N horas                 | `max_hours`                     |
| `ComboExit`    | TP/SL + tiempo máximo (**recomendado**) | `tp_pct`, `sl_pct`, `max_hours` |

---

## Cómo agregar una nueva hipótesis (4 pasos)

### Paso 1 — Crear la carpeta
```
hypotheses/h002_nombre_descriptivo/
```
Seguir la convención `h{número}_nombre_en_snake_case`.

### Paso 2 — Crear `config.json`
```json
{
  "name": "Nombre descriptivo de la hipótesis",
  "description": "Qué estás testeando y por qué",
  "symbols": ["BTCUSDT"],
  "years": [2023, 2024],
  "signal_interval": "1h",
  "execution_interval": "1h",
  "exit_model": "ComboExit",
  "exit_params": {
    "tp_pct": 2.0,
    "sl_pct": 1.0,
    "max_hours": 48
  }
}
```

### Paso 3 — Crear `hypothesis.py`
```python
from framework.base_hypothesis import BaseHypothesis
import pandas as pd

class Hypothesis(BaseHypothesis):
    """
    Describir la teoría acá.
    """

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        df = OHLCV del symbol principal en signal_interval.

        Helpers disponibles:
            self._current_symbol        → e.g. "BTCUSDT"
            self._current_year          → e.g. 2024
            self.load_data(sym, tf)     → DataFrame extra (cualquier coin/TF)
        """
        # Ejemplo: cualquier vela verde
        return df['close'] > df['open']
```

### Paso 4 — Correr
```bash
python run.py h002
```

---

## Patrones avanzados

### Multi-timeframe: señal en 4h, refinar con 1h
```python
def generate_signals(self, df: pd.DataFrame) -> pd.Series:
    # df = 1h (signal_interval en config.json)
    # Cargar 4h del mismo coin y año
    df_4h = self.load_data(self._current_symbol, "4h")

    # Calcular tendencia en 4h (EMA200)
    df_4h["ema200"] = df_4h["close"].ewm(span=200).mean()
    uptrend_4h = df_4h["close"].iloc[-1] > df_4h["ema200"].iloc[-1]

    # Señal en 1h solo si 4h está en uptrend
    green_1h = df["close"] > df["open"]
    return green_1h & uptrend_4h
```

### Inter-coin: ETH como trigger, operar en BTC
```python
# En config.json: symbols = ["BTCUSDT"]
def generate_signals(self, df: pd.DataFrame) -> pd.Series:
    # df = BTCUSDT 1h
    # Cargar ETH del mismo año
    df_eth = self.load_data("ETHUSDT", "1h")

    # ETH señal: vela verde fuerte
    eth_strong_green = (
        (df_eth["close"] - df_eth["open"]) / df_eth["open"] > 0.02
    ).reindex(df.index, fill_value=False)

    # Operar BTC cuando ETH da señal
    return eth_strong_green
```

> **Nota sobre alineación de índices**: cuando mezclás dos DataFrames, usá `.reindex()` o merge por timestamp para alinear correctamente.

## Comandos principales

```bash
# Correr una hipótesis
python run.py h001

# Correr y ver solo las señales sin simular trades
python run.py h001 --signals-only

# Listar todas las hipótesis disponibles
python run.py --list

# Forzar re-descarga de datos (ignora cache)
python run.py h001 --refresh-data

# Correr validación walk-forward (requiere optimize.json en la carpeta de la hipótesis)
python walkforward.py h001
```

---

## Intervalos soportados (Binance)

`1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`, `3d`, `1w`

---

## Métricas del reporte

| Métrica            | Descripción                                    |
| ------------------ | ---------------------------------------------- |
| Total trades       | Cantidad de operaciones simuladas              |
| Win rate           | % de trades rentables                          |
| Profit factor      | Ganancia bruta / Pérdida bruta (>1.5 es bueno) |
| Max drawdown       | Pérdida máxima desde un pico                   |
| Avg win / Avg loss | Tamaño promedio de ganancias vs pérdidas       |
| Total return %     | Retorno total del período                      |
| Sharpe ratio       | Retorno ajustado por riesgo                    |

---

## Reglas para el LLM asistente

- **NUNCA modificar** archivos dentro de `framework/` salvo que el usuario lo pida explícitamente y entienda las implicaciones
- **SIEMPRE** implementar `generate_signals()` sin usar datos futuros (no `shift(-1)`, no `lookahead`)
- Cuando se pide agregar una hipótesis, seguir exactamente los 4 pasos de arriba
- Los parámetros de la hipótesis van en `config.json`, no hardcodeados en `hypothesis.py`
- Si hay dudas sobre qué exit model usar, recomendar `ComboExit` por defecto
- Para acceder a datos de múltiples timeframes, agregar múltiples entradas en `config.json` bajo `"extra_intervals"`
- **NUEVO:** Después de obtener el resultado de un test/script, **SIEMPRE pregunta al usuario** si quiere ver los resultados. Si dice que sí, **abrí automáticamente el archivo `trades_chart.html` en el navegador** utilizando los comandos del sistema operativo (ej: `open "ruta/al/trades_chart.html"` en macOS, o `start ""` en Windows).

---

## Stack tecnológico

- **Python 3.10+**
- `pandas` — manipulación de datos
- `requests` — API de Binance (pública, sin autenticación)
- `matplotlib` — gráficos
- `numpy` — cálculos numéricos
