"""
framework/backtester.py

Generic backtesting engine. No look-ahead bias:
- Entry is always at the OPEN of the candle AFTER the signal.
- Exit is determined by the configured ExitModel.
- Supports Bidirectional trading: 1 (Long) and -1 (Short).
"""

from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
from framework.exit_models import ExitResult


@dataclass
class Trade:
    entry_time: datetime
    exit_time: datetime
    symbol: str
    interval: str
    year: int
    direction: int           # 1 = Long, -1 = Short
    entry_price: float       # After slippage
    exit_price: float
    exit_reason: str         # "TP", "SL", "TIME", "END_OF_DATA", "LIQUIDATED"
    bars_held: int
    leverage: int            # 1 = spot, >1 = futures with leverage
    pnl_pct: float           # Net PnL after fees, slippage, and leverage
    pnl_gross_pct: float     # Gross PnL before fees (but after leverage)
    fees_paid_pct: float     # Total fees cost (both sides, post-leverage)


def run_backtest(
    df: pd.DataFrame,
    signals: pd.Series,
    exit_model,
    symbol: str,
    interval: str,
    year: int,
    fees_pct: float = 0.05,      # Futuros taker (0.02% maker, 0.1% spot)
    slippage_pct: float = 0.1,   # Futuros más líquidos — menor slippage
    leverage: int = 1,           # 1 = sin apalancamiento
) -> list[Trade]:
    """
    Simulate trades given entry signals and an exit model.

    Args:
        signals: pd.Series. True/False or 1/0 mapped to Longs. If it contains -1, treats those as Shorts.
        leverage: Multiplies PnL. Also adds liquidation check:
                  if price drops (1/leverage)% from entry, position is liquidated
                  (lose 100% of collateral). Use 1 for spot equivalence.
    """
    trades: list[Trade] = []
    df = df.reset_index(drop=True)
    signals = signals.reset_index(drop=True)

    # Consider true boolean as 1, false as 0. 
    # If the user passed integers 1 (long), -1 (short), 0 (hold), they work straight out of the box.
    if signals.dtype == bool:
        int_signals = signals.astype(int)
    else:
        int_signals = signals.copy()

    signal_indices = int_signals[int_signals != 0].index.tolist()

    for sig_idx in signal_indices:
        direction = int(int_signals.iloc[sig_idx])
        if direction not in [1, -1]:
            continue

        # Entry is at the NEXT candle's open (no look-ahead bias)
        entry_idx = sig_idx + 1
        if entry_idx >= len(df):
            continue  # Signal on last candle — can't enter

        entry_candle = df.iloc[entry_idx]
        raw_entry = entry_candle["open"]
        
        # Apply slippage: you always buy slightly worse off than the open
        if direction == 1:
            entry_price = raw_entry * (1 + slippage_pct / 100)
            liquidation_price = entry_price * (1 - (1 / leverage) + 0.005) if leverage > 1 else 0.0
        else:
            entry_price = raw_entry * (1 - slippage_pct / 100)
            liquidation_price = entry_price * (1 + (1 / leverage) - 0.005) if leverage > 1 else float("inf")
            
        entry_time = entry_candle["timestamp"]

        # Slice from the candle AFTER entry (exit model sees future candles)
        future_df = df.iloc[entry_idx + 1:].reset_index(drop=True)
        if future_df.empty:
            continue

        try:
            result: ExitResult = exit_model.get_exit(entry_price, future_df, entry_candle=entry_candle, direction=direction)
        except TypeError:
            # Fallback for models not updated to accept direction natively
            result: ExitResult = exit_model.get_exit(entry_price, future_df)

        # Check liquidation ONLY up to the exit candle determined by the exit model
        liquidated = False
        if leverage > 1:
            for liq_i in range(result.bars_held + 1):
                liq_row = future_df.iloc[liq_i]
                
                is_liquidated = False
                if direction == 1 and liq_row["low"] <= liquidation_price:
                    # Si es la misma vela de salida, y la salida fue un SL que está por encima del precio de liquidación, 
                    # el SL te salvó ANTES de llegar a la liquidación.
                    if liq_i == result.bars_held and result.reason == "SL" and result.exit_price >= liquidation_price:
                        pass
                    else:
                        is_liquidated = True
                
                elif direction == -1 and liq_row["high"] >= liquidation_price:
                    if liq_i == result.bars_held and result.reason == "SL" and result.exit_price <= liquidation_price:
                        pass
                    else:
                        is_liquidated = True
                        
                if is_liquidated:
                    liq_exit_idx = entry_idx + 1 + liq_i
                    liq_exit_idx = min(liq_exit_idx, len(df) - 1)
                    trades.append(Trade(
                        entry_time=entry_time,
                        exit_time=df.iloc[liq_exit_idx]["timestamp"],
                        symbol=symbol,
                        interval=interval,
                        year=year,
                        direction=direction,
                        entry_price=entry_price,
                        exit_price=liquidation_price,
                        exit_reason="LIQUIDATED",
                        bars_held=liq_i,
                        leverage=leverage,
                        pnl_pct=-100.0,     # Lose all collateral
                        pnl_gross_pct=-100.0,
                        fees_paid_pct=fees_pct * 2,
                    ))
                    liquidated = True
                    break

        if liquidated:
            continue

        exit_idx = entry_idx + 1 + result.bars_held
        exit_idx = min(exit_idx, len(df) - 1)
        exit_time = df.iloc[exit_idx]["timestamp"]

        if direction == 1:
            gross_pnl = (result.exit_price / entry_price - 1) * 100 * leverage
        else:
            gross_pnl = ((entry_price - result.exit_price) / entry_price) * 100 * leverage
            
        total_fees = fees_pct * 2 * leverage   # Fees scale with position size
        net_pnl = gross_pnl - total_fees

        trades.append(Trade(
            entry_time=entry_time,
            exit_time=exit_time,
            symbol=symbol,
            interval=interval,
            year=year,
            direction=direction,
            entry_price=entry_price,
            exit_price=result.exit_price,
            exit_reason=result.reason,
            bars_held=result.bars_held,
            leverage=leverage,
            pnl_pct=net_pnl,
            pnl_gross_pct=gross_pnl,
            fees_paid_pct=total_fees,
        ))

    return trades
