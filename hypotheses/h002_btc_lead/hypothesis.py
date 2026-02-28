from framework.base_hypothesis import BaseHypothesis
import pandas as pd


class Hypothesis(BaseHypothesis):
    """
    BTC Lead (con filtro macro): cuando la EMA9 de BTC cruza al alza la EMA21 en 4h
    Y el precio de BTC está sobre su EMA200 en 1d (tendencia alcista macro confirmada),
    entramos en ETHUSDT al open de la siguiente vela.

    Filtros:
        1. BTC EMA9 > EMA21 (cruce al alza en 4h) → señal de momentum
        2. BTC close > EMA200 en 1d → confirma que no estamos en bear market

    Sin look-ahead: la señal se detecta en la vela t,
    la entrada se ejecuta al open de la vela t+1 (el backtester lo hace solo).
    """

    EMA_FAST = 9
    EMA_SLOW = 21
    EMA_TREND = 200  # en 1d para filtro macro

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        df = OHLCV de ETHUSDT en 4h.
        """
        # ── Señal 1: BTC EMA9 cruza al alza EMA21 en 4h ──────────────────────
        btc_4h = self.load_data("BTCUSDT", "4h", self._current_year)
        btc_4h["ema_fast"] = btc_4h["close"].ewm(span=self.EMA_FAST, adjust=False).mean()
        btc_4h["ema_slow"] = btc_4h["close"].ewm(span=self.EMA_SLOW, adjust=False).mean()
        btc_4h["above"] = btc_4h["ema_fast"] > btc_4h["ema_slow"]
        btc_4h["cross_up"] = btc_4h["above"] & ~btc_4h["above"].shift(1).fillna(False)

        # ── Filtro macro: BTC sobre EMA200 en 1d ─────────────────────────────
        btc_1d = self.load_data("BTCUSDT", "1d", self._current_year)
        btc_1d["ema200"] = btc_1d["close"].ewm(span=self.EMA_TREND, adjust=False).mean()
        btc_1d["bull"] = btc_1d["close"] > btc_1d["ema200"]

        # Reindexar filtro diario al timeframe de 4h:
        # a cada vela 4h le asignamos el estado bull del día correspondiente
        btc_1d_indexed = btc_1d.set_index("timestamp")["bull"]
        btc_4h["date"] = pd.to_datetime(btc_4h["timestamp"]).dt.normalize()
        btc_4h["bull"] = btc_4h["date"].map(
            lambda d: btc_1d_indexed.asof(d) if d >= btc_1d_indexed.index[0] else False
        )

        # ── Señal final: cruce de EMA + macro alcista ─────────────────────────
        btc_4h["signal"] = btc_4h["cross_up"] & btc_4h["bull"]

        # Alinear con el índice del alt coin
        signal = btc_4h["signal"].reindex(df.index, fill_value=False)

        return signal
