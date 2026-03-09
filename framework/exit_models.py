"""
framework/exit_models.py

Pluggable exit models. Each model receives a DataFrame starting at the
entry candle and returns (exit_price, exit_reason, bars_held).

All models share the same interface:
    model.get_exit(entry_price, df_from_entry, entry_candle, direction) → (exit_price, reason, bars_held)

Available models: FixedTPSL, TrailingStop, TimeBased, ComboExit, AtrComboExit
"""

from dataclasses import dataclass
from typing import Tuple
import pandas as pd


@dataclass
class ExitResult:
    exit_price: float
    reason: str       # "TP", "SL", "TIME", "END_OF_DATA"
    bars_held: int


class FixedTPSL:
    """Exit on fixed take-profit or stop-loss percentages."""

    def __init__(self, tp_pct: float, sl_pct: float):
        self.tp_pct_val = tp_pct / 100
        self.sl_pct_val = sl_pct / 100

    def get_exit(self, entry_price: float, df: pd.DataFrame, entry_candle: pd.Series = None, direction: int = 1) -> ExitResult:
        if direction == 1:
            tp_price = entry_price * (1 + self.tp_pct_val)
            sl_price = entry_price * (1 - self.sl_pct_val)
        else:
            tp_price = entry_price * (1 - self.tp_pct_val)
            sl_price = entry_price * (1 + self.sl_pct_val)

        for i, (_, row) in enumerate(df.iterrows()):
            if direction == 1:
                # Check SL first (worst case within candle)
                if row["low"] <= sl_price: return ExitResult(sl_price, "SL", i)
                if row["high"] >= tp_price: return ExitResult(tp_price, "TP", i)
            else:
                if row["high"] >= sl_price: return ExitResult(sl_price, "SL", i)
                if row["low"] <= tp_price: return ExitResult(tp_price, "TP", i)

        # No exit found — close at last close price
        last = df.iloc[-1]
        return ExitResult(last["close"], "END_OF_DATA", len(df) - 1)


class TrailingStop:
    """Stop-loss that trails the highest price reached."""

    def __init__(self, trail_pct: float):
        self.trail_pct = trail_pct / 100

    def get_exit(self, entry_price: float, df: pd.DataFrame, entry_candle: pd.Series = None, direction: int = 1) -> ExitResult:
        extreme = entry_price

        for i, (_, row) in enumerate(df.iterrows()):
            if direction == 1:
                extreme = max(extreme, row["high"])
                stop = extreme * (1 - self.trail_pct)
                if row["low"] <= stop:
                    return ExitResult(stop, "SL", i)
            else:
                extreme = min(extreme, row["low"])
                stop = extreme * (1 + self.trail_pct)
                if row["high"] >= stop:
                    return ExitResult(stop, "SL", i)

        last = df.iloc[-1]
        return ExitResult(last["close"], "END_OF_DATA", len(df) - 1)


class TimeBased:
    """Exit after a fixed number of bars regardless of P&L."""

    def __init__(self, max_bars: int):
        self.max_bars = max_bars

    def get_exit(self, entry_price: float, df: pd.DataFrame, entry_candle: pd.Series = None, direction: int = 1) -> ExitResult:
        bars = min(self.max_bars, len(df) - 1)
        exit_price = df.iloc[bars]["close"]
        reason = "TIME" if bars == self.max_bars else "END_OF_DATA"
        return ExitResult(exit_price, reason, bars)


class ComboExit:
    """
    TP + SL + max time limit. Most realistic for backtesting.
    Recommended default for all hypotheses.
    """

    def __init__(self, tp_pct: float, sl_pct: float, max_bars: int):
        self.tp_pct_val = tp_pct / 100
        self.sl_pct_val = sl_pct / 100
        self.max_bars = max_bars

    def get_exit(self, entry_price: float, df: pd.DataFrame, entry_candle: pd.Series = None, direction: int = 1) -> ExitResult:
        if direction == 1:
            tp_price = entry_price * (1 + self.tp_pct_val)
            sl_price = entry_price * (1 - self.sl_pct_val)
        else:
            tp_price = entry_price * (1 - self.tp_pct_val)
            sl_price = entry_price * (1 + self.sl_pct_val)

        limit = min(self.max_bars, len(df) - 1)

        for i in range(limit + 1):
            row = df.iloc[i]
            if direction == 1:
                if row["low"] <= sl_price: return ExitResult(sl_price, "SL", i)
                if row["high"] >= tp_price: return ExitResult(tp_price, "TP", i)
            else:
                if row["high"] >= sl_price: return ExitResult(sl_price, "SL", i)
                if row["low"] <= tp_price: return ExitResult(tp_price, "TP", i)

        # Time exit
        exit_price = df.iloc[limit]["close"]
        reason = "TIME" if limit == self.max_bars else "END_OF_DATA"
        return ExitResult(exit_price, reason, limit)


class AtrComboExit:
    """
    TP + SL based on ATR (Average True Range), plus max time limit.
    Requires an 'atr' column in the DataFrame evaluated at entry.
    """

    def __init__(self, tp_atr_mult: float, sl_atr_mult: float, max_bars: int):
        self.tp_atr_mult = tp_atr_mult
        self.sl_atr_mult = sl_atr_mult
        self.max_bars = max_bars

    def get_exit(self, entry_price: float, df: pd.DataFrame, entry_candle: pd.Series = None, direction: int = 1) -> ExitResult:
        if entry_candle is None or "atr" not in entry_candle:
            raise ValueError("AtrComboExit requires 'atr' column to be present in df / entry_candle")

        atr = entry_candle["atr"]
        if direction == 1:
            tp_price = entry_price + (atr * self.tp_atr_mult)
            sl_price = entry_price - (atr * self.sl_atr_mult)
        else:
            tp_price = entry_price - (atr * self.tp_atr_mult)
            sl_price = entry_price + (atr * self.sl_atr_mult)
            
        limit = min(self.max_bars, len(df) - 1)

        for i in range(limit + 1):
            row = df.iloc[i]
            if direction == 1:
                if row["low"] <= sl_price: return ExitResult(sl_price, "SL", i)
                if row["high"] >= tp_price: return ExitResult(tp_price, "TP", i)
            else:
                if row["high"] >= sl_price: return ExitResult(sl_price, "SL", i)
                if row["low"] <= tp_price: return ExitResult(tp_price, "TP", i)

        # Time exit
        exit_price = df.iloc[limit]["close"]
        reason = "TIME" if limit == self.max_bars else "END_OF_DATA"
        return ExitResult(exit_price, reason, limit)

class AsymmetricComboExit:
    """
    TP + SL + max time limit, with different parameters for Long and Short trades.
    Allows decoupling risk profiles for bidirectional strategies.
    """

    def __init__(self, tp_pct_long: float, sl_pct_long: float, max_hours_long: int, 
                 tp_pct_short: float, sl_pct_short: float, max_hours_short: int):
        self.tp_pct_long_val = tp_pct_long / 100
        self.sl_pct_long_val = sl_pct_long / 100
        self.max_hours_long = max_hours_long
        
        self.tp_pct_short_val = tp_pct_short / 100
        self.sl_pct_short_val = sl_pct_short / 100
        self.max_hours_short = max_hours_short

    def get_exit(self, entry_price: float, df: pd.DataFrame, entry_candle: pd.Series = None, direction: int = 1) -> ExitResult:
        if direction == 1:
            tp_price = entry_price * (1 + self.tp_pct_long_val)
            sl_price = entry_price * (1 - self.sl_pct_long_val)
            max_bars = self.max_hours_long
            
            limit = min(max_bars, len(df) - 1)
            for i in range(limit + 1):
                row = df.iloc[i]
                if row["low"] <= sl_price: return ExitResult(sl_price, "SL", i)
                if row["high"] >= tp_price: return ExitResult(tp_price, "TP", i)
        else:
            tp_price = entry_price * (1 - self.tp_pct_short_val)
            sl_price = entry_price * (1 + self.sl_pct_short_val)
            max_bars = self.max_hours_short
            
            limit = min(max_bars, len(df) - 1)
            for i in range(limit + 1):
                row = df.iloc[i]
                if row["high"] >= sl_price: return ExitResult(sl_price, "SL", i)
                if row["low"] <= tp_price: return ExitResult(tp_price, "TP", i)

        # Time exit
        exit_price = df.iloc[limit]["close"]
        reason = "TIME" if limit == max_bars else "END_OF_DATA"
        return ExitResult(exit_price, reason, limit)


# Factory — maps config.json "exit_model" string to class instance
def build_exit_model(name: str, params: dict):
    """
    Build an exit model from config.json values.

    Args:
        name: "FixedTPSL" | "TrailingStop" | "TimeBased" | "ComboExit" | "AtrComboExit"
        params: dict of parameters (tp_pct, sl_pct, max_hours, trail_pct, tp_atr_mult, etc.)

    Returns:
        ExitModel instance
    """
    models = {
        "FixedTPSL": lambda p: FixedTPSL(p["tp_pct"], p["sl_pct"]),
        "TrailingStop": lambda p: TrailingStop(p["trail_pct"]),
        "TimeBased": lambda p: TimeBased(p["max_hours"]),
        "ComboExit": lambda p: ComboExit(p["tp_pct"], p["sl_pct"], p["max_hours"]),
        "AtrComboExit": lambda p: AtrComboExit(p["tp_atr_mult"], p["sl_atr_mult"], p["max_hours"]),
        "AsymmetricComboExit": lambda p: AsymmetricComboExit(
            p["tp_pct_long"], p["sl_pct_long"], p["max_hours_long"],
            p["tp_pct_short"], p["sl_pct_short"], p["max_hours_short"]
        ),
    }

    if name not in models:
        raise ValueError(f"Unknown exit model '{name}'. Available: {list(models)}")

    return models[name](params)
