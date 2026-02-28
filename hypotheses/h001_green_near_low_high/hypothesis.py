"""
hypotheses/h001_green_near_low_high/hypothesis.py

Theory: 1-hour green candles where the open is near the low AND the close is
near the high indicate strong buying pressure throughout the candle.
These are potential entries for a continuation move.

Signal conditions:
  1. Green candle: close > open
  2. Open within `near_threshold` of candle range from the low
  3. Close within `near_threshold` of candle range from the high
"""

import pandas as pd
from framework.base_hypothesis import BaseHypothesis


class Hypothesis(BaseHypothesis):

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        threshold = self.config.get("near_threshold", 0.10)

        candle_range = df["high"] - df["low"]
        # Avoid division by zero on doji candles
        candle_range = candle_range.replace(0, float("nan"))

        is_green = df["close"] > df["open"]
        open_near_low = (df["open"] - df["low"]) / candle_range <= threshold
        close_near_high = (df["high"] - df["close"]) / candle_range <= threshold

        signals = is_green & open_near_low & close_near_high
        return signals.fillna(False)
