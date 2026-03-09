import pandas as pd
import itertools
from framework.downloader import get_ohlcv
from framework.backtester import run_backtest
from framework.reporter import compute_metrics
from hypotheses.trend_following.hypothesis import Hypothesis
from framework.exit_models import build_exit_model
from pathlib import Path

def optimize_abc():
    hypo = Hypothesis(Path("hypotheses/trend_following"))
    symbol = "ETHUSDT"
    years = [2022, 2023, 2024, 2025]
    interval = "1d"
    
    param_grid = {
        "trail_pct": [5.0, 7.5, 10.0, 15.0, 20.0],
        "donchian_period": [10, 20, 30, 40, 50],
    }
    
    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    
    df_dict = {}
    for y in years:
        df_dict[y] = get_ohlcv(symbol, interval, y)
        
    best_net = -float("inf")
    
    print(f"Testing {len(combos)} combinations for Trend Following ({symbol} {interval})...")
    for combo in combos:
        params = dict(zip(keys, combo))
        
        # Symmetrical exits for both Long and Short
        hypo.exit_params["trail_pct"] = params["trail_pct"]
        if "macro_filter" not in hypo.config:
            hypo.config["macro_filter"] = {}
        hypo.config["macro_filter"]["donchian_period"] = params["donchian_period"]
        
        exit_model = build_exit_model("TrailingStop", hypo.exit_params)
        
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
                
        avg = sum(nets)/len(nets)

        if avg > best_net:
            best_net = avg
            print(f"New Best: {params} | Avg Net: {avg:.2f}% | Nets: {[f'{n:.2f}' for n in nets]}")

if __name__ == "__main__":
    optimize_abc()
