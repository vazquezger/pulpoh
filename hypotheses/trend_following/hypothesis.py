import pandas as pd
from framework.base_hypothesis import BaseHypothesis

class Hypothesis(BaseHypothesis):
    """
    Trend Following (Donchian Breakout)
    
    1. Calcula el canal de Donchian: el precio 'high' más alto de las últimas N velas (ej. 30 días).
    2. Si el precio 'close' de la vela actual rompe ese techo histórico reciente, se considera que inició una posible macrotendencia alcista.
    3. Triggerea LONG.
    4. La salida es administrada íntegramente por un Trailing Stop (persigue el precio a medida que sube).
    """

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signal = pd.Series(0, index=df.index, dtype=int)
        
        # Load configs
        macro_opts = self.config.get("macro_filter", {})
        donchian_period = macro_opts.get("donchian_period", 30)
        vol_sma_period = macro_opts.get("volume_sma_period", 20)
        vol_multiplier = macro_opts.get("volume_multiplier", 1.2)
        
        df_opt = df.copy()
        
        # 1. Donchian Upper Band (Highest High in the last N periods)
        # Shift(1) is CRITICAL to avoid lookahead bias; we compare today's close against the highest high of the *previous* N days.
        df_opt["highest_high"] = df_opt["high"].rolling(window=donchian_period).max().shift(1)
        
        # 2. Volume moving average to validate the breakout conviction
        df_opt["vol_sma"] = df_opt["volume"].rolling(window=vol_sma_period).mean().shift(1)
        
        df_calc = df_opt.dropna(subset=["highest_high", "vol_sma"])
        
        # 3. Conditions
        # Breakout: Did we close above the established Upper Band?
        cond_breakout = df_calc["close"] > df_calc["highest_high"]
        # Volume: Is the volume pushing this breakout moderately higher than its recent moving average?
        cond_volume = df_calc["volume"] > (df_calc["vol_sma"] * vol_multiplier)
        
        buy_signals = cond_breakout & cond_volume
        
        # Apply Long triggers
        signal.loc[buy_signals[buy_signals].index] = 1

        return signal
