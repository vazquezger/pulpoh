import sys
import json
import itertools
from pathlib import Path

# Fix sys path for imports
sys.path.insert(0, str(Path("/Users/gvazquez/dev/try/pulpoh")))

from framework.downloader import get_ohlcv
from framework.exit_models import build_exit_model
from framework.backtester import run_backtest
from framework.reporter import compute_metrics
from run import load_hypothesis

def dict_to_str(d):
    return " ".join([f"{k.split('.')[-1]}={v}" for k, v in d.items()])

def run_all_years():
    hypo_path = Path("/Users/gvazquez/dev/try/pulpoh/hypotheses/ny_reversal_wicks")
    hypo = load_hypothesis(hypo_path)
    symbol = "SOLUSDT"
    years = [2022, 2023, 2024, 2025]
    
    # 96 periods of 15m = 24 hours calculation window for ATR
    param_grid = {
        "exit_params.tp_pct": [6.0, 8.0, 10.0, 12.0],
        "exit_params.sl_pct": [2.5, 3.5, 5.0],
        "macro_filter.vol_multiplier": [1.5, 2.0],
        "macro_filter.wick_threshold": [0.2, 0.3],
        "macro_filter.atr_threshold": [0.005, 0.01, 0.015] # 0.5%, 1%, 1.5% volatility
    }
    
    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    
    best_avg_net = -float("inf")
    best_params = None
    best_results = None
    
    # Tracking configurations that returned > 10% in ALL years
    golden_configs = []
    
    print(f"Running grid search with ATR filter for {symbol} ({len(combos)} combinations)...")
    
    for combo in combos:
        params = dict(zip(keys, combo))
        hypo.set_params(params)
        
        exit_model = build_exit_model(hypo.exit_model_name, hypo.exit_params)
        
        yearly_nets = []
        for year in years:
            hypo._current_symbol = symbol
            hypo._current_year = year
            hypo._refresh_data = False
            
            df = get_ohlcv(symbol, hypo.signal_interval, year, refresh=False)
            if df.empty:
                yearly_nets.append(0)
                continue
                
            signals = hypo.generate_signals(df)
            if signals.sum() == 0:
                yearly_nets.append(0)
                continue
                
            trades = run_backtest(
                df, signals, exit_model,
                symbol=symbol, interval=hypo.signal_interval, year=year,
                fees_pct=hypo.fees_pct, slippage_pct=hypo.slippage_pct, leverage=hypo.leverage,
            )
            
            if not trades:
                yearly_nets.append(0)
                continue
                
            metrics = compute_metrics(trades)
            yearly_nets.append(metrics["total_return_pct"])
            
        avg_net = sum(yearly_nets) / len(yearly_nets)
        
        if avg_net > best_avg_net:
            best_avg_net = avg_net
            best_params = params
            best_results = yearly_nets
            
        # Check if ALL years are > 10%
        if all(n > 10.0 for n in yearly_nets):
            golden_configs.append((params, yearly_nets, avg_net))
            print(f"🌟 GOLDEN COMBO: {dict_to_str(params)} | Avg: {avg_net:.2f}% | Yearly: {[f'{n:.2f}%' for n in yearly_nets]}")
        elif avg_net > 10.0:
            print(f"Good combo: {dict_to_str(params)} | Avg: {avg_net:.2f}% | Yearly: {[f'{n:.2f}%' for n in yearly_nets]}")

    print("\n" + "="*50)
    print("BEST AVERAGE CONFIGURATION")
    print("="*50)
    print(f"Params: {dict_to_str(best_params)}")
    print(f"Average Net Return: {best_avg_net:.2f}%")
    for y, n in zip(years, best_results):
        print(f"  {y}: {n:+.2f}%")
        
    if golden_configs:
        print("\n🏆 CONFIGURATIONS >10% EVERY YEAR 🏆")
        for p, y_nets, a_net in golden_configs:
            print(f"Avg {a_net:.2f}% | {dict_to_str(p)}")

if __name__ == "__main__":
    run_all_years()
