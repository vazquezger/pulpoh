from framework.base_hypothesis import BaseHypothesis
import pandas as pd
import numpy as np


class Hypothesis(BaseHypothesis):
    """
    ABC Reversal — aproximación algorítmica de la corrección de Elliott.

    Patrón buscado (dentro de tendencia alcista macro):
        PH0 ─→ PL0 (onda A: caída desde máximo)
        PL0 ─→ PH1 (onda B: rebote, pero PH1 < PH0)
        PH1 ─→ PL1 (onda C: segunda caída, PL1 cerca o bajo PL0)
        → ENTRADA al cierre de la vela que sube desde PL1

    Filtro macro: BTC sobre EMA200 (evita operar en bear market sostenido).
    Pivots: mínimo local con ventana de PIVOT_WINDOW velas a cada lado.
    """

    PIVOT_WINDOW = 2          # Velas a cada lado para confirmar pivot
    B_RETRACEMENT_MAX = 1.0   # B no puede superar el tope de A (no retrace limit)
    C_DEPTH_MIN = 0.30        # C debe bajar al menos 30% de la onda A
    EMA_TREND = 200           # Filtro macro (1d)
    rsi_max = 50              # Max RSI permitido al confirmarse el rebote C

    def __init__(self, hypothesis_dir):
        super().__init__(hypothesis_dir)
        self.use_sr_filter = self.config.get("use_sr_filter", False)
        self.sr_lookback = self.config.get("sr_lookback", 100)
        self.sr_tolerance_pct = self.config.get("sr_tolerance_pct", 1.0) / 100.0

    # ─── Pivot detection ─────────────────────────────────────────────────────

    def _find_pivots(self, df: pd.DataFrame, window: int):
        """Retorna listas de índices de pivot highs y pivot lows."""
        highs, lows = [], []
        n = len(df)
        for i in range(window, n - window):
            if (df["high"].iloc[i] == df["high"].iloc[i - window: i + window + 1].max()):
                highs.append(i)
            if (df["low"].iloc[i] == df["low"].iloc[i - window: i + window + 1].min()):
                lows.append(i)
        return highs, lows

    def _is_near_sr(self, price: float, pivot_indices: list, current_idx: int, df: pd.DataFrame, is_support: bool) -> bool:
        """Chequea si el precio actual está cerca de un pivot previo (soporte o resistencia)."""
        valid_pivots = [i for i in pivot_indices if current_idx - self.sr_lookback <= i < current_idx]
        if not valid_pivots:
            return False
            
        prices = df["low"].values if is_support else df["high"].values
        for p_idx in valid_pivots:
            p_price = prices[p_idx]
            diff_pct = abs(price - p_price) / p_price
            if diff_pct <= self.sr_tolerance_pct:
                return True
        return False

    # ─── ABC pattern scanner ─────────────────────────────────────────────────

    def _find_abc_long_signals(self, df: pd.DataFrame, ph_idx: list, pl_idx: list) -> pd.Series:
        signal = pd.Series(False, index=df.index)
        for c_i in pl_idx:
            c_val = df["low"].iloc[c_i]
            ph1_candidates = [i for i in ph_idx if i < c_i]
            if not ph1_candidates: continue
            ph1_i = max(ph1_candidates)
            ph1_val = df["high"].iloc[ph1_i]
            a_size_proxy = ph1_val - c_val
            if a_size_proxy <= 0: continue
            pl0_candidates = [i for i in pl_idx if i < ph1_i]
            if not pl0_candidates: continue
            pl0_i = max(pl0_candidates)
            pl0_val = df["low"].iloc[pl0_i]
            ph0_candidates = [i for i in ph_idx if i < pl0_i]
            if not ph0_candidates: continue
            ph0_i = max(ph0_candidates)
            ph0_val = df["high"].iloc[ph0_i]
            a_size = ph0_val - pl0_val
            if a_size <= 0: continue
            if ph1_val >= ph0_val: continue
            c_drop = ph1_val - c_val
            if c_drop < a_size * self.C_DEPTH_MIN: continue
            
            # Filtro de Soporte (C wave bottom near previous Pivot Low)
            if self.use_sr_filter:
                # Filtrar PLs que forman la estructura ABC actual
                structural_pivots = [pl0_i, c_i] 
                historical_pls = [p for p in pl_idx if p not in structural_pivots]
                if not self._is_near_sr(c_val, historical_pls, c_i, df, is_support=True):
                    continue

            signal_idx = c_i + self.PIVOT_WINDOW
            if signal_idx < len(df):
                signal.iloc[signal_idx] = True
        return signal

    def _find_abc_short_signals(self, df: pd.DataFrame, ph_idx: list, pl_idx: list) -> pd.Series:
        signal = pd.Series(False, index=df.index)
        for c_i in ph_idx:
            c_val = df["high"].iloc[c_i]
            pl1_candidates = [i for i in pl_idx if i < c_i]
            if not pl1_candidates: continue
            pl1_i = max(pl1_candidates)
            pl1_val = df["low"].iloc[pl1_i]
            a_size_proxy = c_val - pl1_val
            if a_size_proxy <= 0: continue
            ph0_candidates = [i for i in ph_idx if i < pl1_i]
            if not ph0_candidates: continue
            ph0_i = max(ph0_candidates)
            ph0_val = df["high"].iloc[ph0_i]
            pl0_candidates = [i for i in pl_idx if i < ph0_i]
            if not pl0_candidates: continue
            pl0_i = max(pl0_candidates)
            pl0_val = df["low"].iloc[pl0_i]
            a_size = ph0_val - pl0_val
            if a_size <= 0: continue
            
            # B (PL1) no cae por debajo del inicio de A (PL0)
            if pl1_val <= pl0_val: continue
            
            # C debe subir al menos C_DEPTH_MIN de A
            c_rise = c_val - pl1_val
            if c_rise < a_size * self.C_DEPTH_MIN: continue
            
            # Filtro de Resistencia (C wave top near previous Pivot High)
            if self.use_sr_filter:
                # Filtrar PHs que forman la estructura ABC actual
                structural_pivots = [ph0_i, c_i] 
                historical_phs = [p for p in ph_idx if p not in structural_pivots]
                if not self._is_near_sr(c_val, historical_phs, c_i, df, is_support=False):
                    continue

            signal_idx = c_i + self.PIVOT_WINDOW
            if signal_idx < len(df):
                signal.iloc[signal_idx] = True
        return signal

    # ─── Main ────────────────────────────────────────────────────────────────

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        trade_dir_conf = self.config.get("trade_direction", "both")
        
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        bull_market = df["close"] > df["ema200"]
        bear_market = df["close"] < df["ema200"]

        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14).mean()
        df["atr_ma"] = df["atr"].rolling(window=50).mean()
        expanding = df["atr"] > df["atr_ma"]

        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        
        rsi_long_ok = (df["rsi"] <= self.rsi_max) | (df["rsi"].shift(1) <= self.rsi_max)
        rsi_short_ok = (df["rsi"] >= 100 - self.rsi_max) | (df["rsi"].shift(1) >= 100 - self.rsi_max)

        ph_idx, pl_idx = self._find_pivots(df, self.PIVOT_WINDOW)
        long_signals = self._find_abc_long_signals(df, ph_idx, pl_idx)
        short_signals = self._find_abc_short_signals(df, ph_idx, pl_idx)

        final_signal = pd.Series(0, index=df.index, dtype=int)
        
        if trade_dir_conf in ["long", "both"]:
            long_mask = long_signals & bull_market & expanding & rsi_long_ok
            final_signal[long_mask] = 1
            
        if trade_dir_conf in ["short", "both"]:
            short_mask = short_signals & bear_market & expanding & rsi_short_ok
            final_signal[short_mask] = -1

        return final_signal


