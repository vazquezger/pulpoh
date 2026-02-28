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

    # ─── ABC pattern scanner ─────────────────────────────────────────────────

    def _find_abc_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Escanea la serie de pivots buscando el patrón A-B-C.
        Estrategia: busca todos los lows locales (onda C) que estén precedidos
        por la secuencia PH → PL → PH (ondas A y B).
        Retorna una Serie bool del mismo índice que df.
        """
        signal = pd.Series(False, index=df.index)
        ph_idx, pl_idx = self._find_pivots(df, self.PIVOT_WINDOW)

        ph_set = set(ph_idx)
        pl_set = set(pl_idx)

        # Para cada pivot low (candidato a C), buscamos hacia atrás un patrón PH→PL→PH
        for c_i in pl_idx:
            c_val = df["low"].iloc[c_i]

            # Buscar el pivot high más reciente antes de C (= PH1, inicio de onda C)
            ph1_candidates = [i for i in ph_idx if i < c_i]
            if not ph1_candidates:
                continue
            ph1_i = max(ph1_candidates)
            ph1_val = df["high"].iloc[ph1_i]

            # Validar profundidad de C desde PH1
            a_size_proxy = ph1_val - c_val  # mínimo de lo que cayó en la onda C
            if a_size_proxy <= 0:
                continue

            # Buscar pivot low más reciente entre PH1 y algún PH anterior (= PL0, fin de onda A)
            pl0_candidates = [i for i in pl_idx if i < ph1_i]
            if not pl0_candidates:
                continue
            pl0_i = max(pl0_candidates)
            pl0_val = df["low"].iloc[pl0_i]

            # Buscar pivot high antes de PL0 (= PH0, inicio de onda A)
            ph0_candidates = [i for i in ph_idx if i < pl0_i]
            if not ph0_candidates:
                continue
            ph0_i = max(ph0_candidates)
            ph0_val = df["high"].iloc[ph0_i]

            # Calcular tamaño de la onda A
            a_size = ph0_val - pl0_val
            if a_size <= 0:
                continue

            # Regla 1: PH1 debe ser menor que PH0 (B no supera el nivel de inicio de A)
            if ph1_val >= ph0_val:
                continue

            # Regla 2: C debe caer al menos C_DEPTH_MIN de la amplitud de A
            c_drop = ph1_val - c_val
            if c_drop < a_size * self.C_DEPTH_MIN:
                continue

            # Señal: vela SIGUIENTE al pivot C
            signal_idx = c_i + 1
            if signal_idx < len(df):
                signal.iloc[signal_idx] = True

        return signal

    # ─── Main ────────────────────────────────────────────────────────────────

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        df = OHLCV del símbolo en 4h.
        Gate: precio sobre EMA200 (tendencia alcista macro).
        """
        # Gate macro: precio sobre EMA200
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["bull"]   = df["close"] > df["ema200"]

        # Calcular ATR(14) para el AtrComboExit
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14).mean()

        abc_signals = self._find_abc_signals(df)
        return abc_signals & df["bull"]


