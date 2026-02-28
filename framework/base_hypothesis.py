"""
framework/base_hypothesis.py

Abstract base class that every hypothesis must inherit from.
The only method you need to implement is generate_signals().

See AGENTS.md for full documentation on how to create a new hypothesis.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import pandas as pd

from framework.downloader import get_ohlcv
from framework.exit_models import build_exit_model
from framework.backtester import run_backtest
from framework.reporter import generate_run_report, generate_summary


class BaseHypothesis(ABC):
    """
    Base class for all trading hypotheses.

    Subclasses must implement:
        generate_signals(df: pd.DataFrame) -> pd.Series[bool]

    Everything else (download, backtest, report) is handled by the framework.
    """

    def __init__(self, hypothesis_dir: Path):
        self.hypothesis_dir = hypothesis_dir
        self.results_dir = hypothesis_dir / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        config_path = hypothesis_dir / "config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"config.json not found in {hypothesis_dir}")

        with open(config_path, encoding="utf-8") as f:
            self.config = json.load(f)

        self.name = self.config.get("name", hypothesis_dir.name)
        self.description = self.config.get("description", "No description provided.")
        self.symbols = self.config.get("symbols", ["BTCUSDT"])
        self.years = self.config.get("years", [2024])
        self.signal_interval = self.config.get("signal_interval", "1h")
        self.exit_model_name = self.config.get("exit_model", "ComboExit")
        self.exit_params = self.config.get("exit_params", {
            "tp_pct": 2.0, "sl_pct": 1.0, "max_hours": 48
        })

        # Set by run() before each generate_signals() call — read-only from hypothesis
        self._current_symbol: str = ""
        self._current_year: int = 0
        self._refresh_data: bool = False
        self.fees_pct: float = self.config.get("fees_pct", 0.05)         # Futuros taker (spot=0.1%)
        self.slippage_pct: float = self.config.get("slippage_pct", 0.1)  # Futuros más líquidos que spot
        self.leverage: int = self.config.get("leverage", 1)               # 1 = sin apalancamiento

    def set_params(self, params: dict):
        """
        Dynamically update parameters (e.g., for optimization grid search).
        Supports flat keys mapping to instance/class variables,
        or nested 'exit_params.key' structure.
        """
        for k, v in params.items():
            if k.startswith("exit_params."):
                sub_k = k.split(".")[1]
                self.exit_params[sub_k] = v
            else:
                setattr(self, k, v)


    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Analyze the OHLCV DataFrame and return entry signals.

        Args:
            df: OHLCV DataFrame for self._current_symbol at self.signal_interval.
                Columns: timestamp, open, high, low, close, volume

        Returns:
            Boolean Series (same length as df).
            True = enter on the NEXT candle's open.

        Available helpers (call from within generate_signals):
            self._current_symbol  → e.g. "BTCUSDT"
            self._current_year    → e.g. 2024
            self.load_data(symbol, interval, year)  → extra DataFrame

        ⚠️ Do NOT use future data. No shift(-1), no lookahead.
        """
        ...

    def load_data(self, symbol: str, interval: str, year: Optional[int] = None) -> pd.DataFrame:
        """
        Load OHLCV data for any symbol/interval/year combination.
        Uses the same cache as the main downloader.

        Call this from within generate_signals() to access:
          - Extra timeframes: self.load_data(self._current_symbol, "4h", self._current_year)
          - Other coins:      self.load_data("ETHUSDT", "1h", self._current_year)

        Args:
            symbol:   e.g. "BTCUSDT", "ETHUSDT"
            interval: e.g. "1h", "4h", "1d"
            year:     defaults to self._current_year if not provided

        Returns:
            DataFrame with OHLCV columns.
        """
        if year is None:
            year = self._current_year
        return get_ohlcv(symbol, interval, year, refresh=self._refresh_data)

    def run(self, refresh_data: bool = False, signals_only: bool = False):
        """
        Orchestrate the full pipeline:
        download → signals → backtest → report (per year×symbol) → summary
        """
        print(f"\n{'='*60}")
        print(f"  {self.name}")
        print(f"  {self.description}")
        print(f"  Symbols: {self.symbols}")
        print(f"  Years:   {self.years}")
        print(f"  TF:      {self.signal_interval}")
        lev_str = f"{self.leverage}x leverage" if self.leverage > 1 else "spot (no leverage)"
        print(f"  Exit:    {self.exit_model_name} {self.exit_params}")
        print(f"  Mode:    {lev_str} | Fees: {self.fees_pct}%/side | Slippage: {self.slippage_pct}%")
        print(f"{'='*60}\n")

        exit_model = build_exit_model(self.exit_model_name, self.exit_params)
        all_metrics = {}
        self._refresh_data = refresh_data

        for symbol in self.symbols:
            for year in self.years:
                print(f"\n▶ {symbol} {year}")

                # Expose context to generate_signals()
                self._current_symbol = symbol
                self._current_year = year

                # 1. Download / load from cache
                df = get_ohlcv(symbol, self.signal_interval, year, refresh=refresh_data)
                if df.empty:
                    print(f"  [Skip] No data available for {symbol}/{year}")
                    continue

                # 2. Generate signals
                signals = self.generate_signals(df)
                n_signals = signals.sum()
                print(f"  [Signals] Found {n_signals} entry signals "
                      f"({n_signals/len(df)*100:.1f}% of candles)")

                if signals_only:
                    continue

                if n_signals == 0:
                    print("  [Skip] No signals — skipping backtest")
                    all_metrics[(symbol, year)] = {"total_trades": 0}
                    continue

                # 3. Backtest
                trades = run_backtest(
                    df, signals, exit_model,
                    symbol=symbol,
                    interval=self.signal_interval,
                    year=year,
                    fees_pct=self.fees_pct,
                    slippage_pct=self.slippage_pct,
                    leverage=self.leverage,
                )
                print(f"  [Backtest] {len(trades)} trades simulated")

                # 4. Report for this run
                metrics = generate_run_report(
                    trades=trades,
                    hypo_name=self.name,
                    hypo_description=self.description,
                    results_dir=self.results_dir,
                    df=df,
                )
                all_metrics[(symbol, year)] = metrics

        # 5. Cross-run summary
        if not signals_only and len(all_metrics) > 0:
            generate_summary(all_metrics, self.name, self.results_dir)

        print(f"\n✅ Done. Results saved to: {self.results_dir}/\n")
