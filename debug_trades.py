import pandas as pd
from pathlib import Path
from framework.backtester import run_backtest
from hypotheses.abc_reversal.hypothesis import Hypothesis
from framework.exit_models import build_exit_model

def debug_trades():
    hypo = Hypothesis(Path("hypotheses/abc_reversal"))
    symbol = "SOLUSDT"
    
    exit_model = build_exit_model("AsymmetricComboExit", hypo.exit_params)
    
    for year in [2025, 2026]:
        try:
            from framework.downloader import get_ohlcv
            df = get_ohlcv(symbol, "1h", year)
            
            signals = hypo.generate_signals(df)
            trades = run_backtest(df, signals, exit_model, symbol, "1h", year, 0.1, 0.1, 1)
            
            print(f"=== Trades in {year} ===")
            for i, t in enumerate(trades):
                print(f"Trade {i+1}: Entry {t.entry_time} @ {t.entry_price:.2f} | "
                      f"Exit {t.exit_time} @ {t.exit_price:.2f} | "
                      f"Net: {t.pnl_pct:.2f}% | Reason: {t.exit_reason}")
        except Exception as e:
            print(f"Error loading {year}:", e)

if __name__ == "__main__":
    debug_trades()
