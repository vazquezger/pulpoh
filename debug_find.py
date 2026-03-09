import pandas as pd
from framework.downloader import get_ohlcv
from framework.backtester import run_backtest
from framework.reporter import compute_metrics
from hypotheses.ny_reversal_wicks.hypothesis import Hypothesis
from framework.exit_models import build_exit_model
from pathlib import Path

def debug():
    hypo = Hypothesis(Path("hypotheses/ny_reversal_wicks"))
    symbol = "ETHUSDT"
    years = [2022, 2023, 2024, 2025]
    interval = "15m"
    
    # baseline config that got +6.46% in run.py
    hypo.exit_params["tp_pct"] = 3.0
    hypo.exit_params["sl_pct"] = 1.5
    exit_model = build_exit_model("ComboExit", hypo.exit_params)
    
    df_dict = {}
    for y in years:
        df_dict[y] = get_ohlcv(symbol, interval, y)
        
    for _ in range(3): # simulate loop twice to see if memory persists
        hypo.exit_params["tp_pct"] = 3.0
        hypo.exit_params["sl_pct"] = 1.5
        exit_model = build_exit_model("ComboExit", hypo.exit_params)
        
        nets = []
        for y in years:
            df = df_dict[y].copy()
            hypo.signal_interval = interval
            hypo._current_symbol = symbol
            hypo._current_year = y
            signals = hypo.generate_signals(df)
            trades = run_backtest(df, signals, exit_model, symbol, interval, y, hypo.fees_pct, hypo.slippage_pct, hypo.leverage)
            
            m = compute_metrics(trades) if trades else {"total_return_pct": 0}
            nets.append(m["total_return_pct"])
            print(f"Year {y}: {m['total_return_pct']:.2f}% | Trades: {len(trades)}")
            
        print(f"Avg Net: {sum(nets)/len(nets):.2f}%")

if __name__ == "__main__":
    debug()
