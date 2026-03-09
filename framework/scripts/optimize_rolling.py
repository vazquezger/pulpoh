import sys
import json
import itertools
from pathlib import Path
import pandas as pd
from datetime import timedelta

# Fix sys path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from framework.downloader import get_ohlcv
from framework.exit_models import build_exit_model
from framework.backtester import run_backtest
from framework.reporter import compute_metrics
from run import discover_hypotheses, load_hypothesis

def dict_to_str(d):
    return " ".join([f"{k.split('.')[-1]}={v}" for k, v in d.items()])

def run_rolling_optimization(hypo_name, symbol, years, train_days, test_days):
    hypos = discover_hypotheses()
    if hypo_name not in hypos:
        print(f"Hypothesis {hypo_name} not found")
        return
        
    folder = hypos[hypo_name]
    hypo = load_hypothesis(folder)
    
    # Grid search config
    param_grid = {
        "exit_params.tp_pct": [3.0, 5.0, 8.0, 12.0],
        "exit_params.sl_pct": [1.5, 3.0, 5.0],
        "macro_filter.vol_multiplier": [1.5, 2.0],
    }
    
    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    
    # Output metrics
    all_rolling_trades = []
    
    # Load all data upfront to simplify sliding windows
    print(f"Loading data for {symbol} {years}...")
    dfs = []
    for year in years:
        df = get_ohlcv(symbol, hypo.signal_interval, year, refresh=False)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True, drop=False)
            dfs.append(df)
            
    if not dfs:
        print("No data found.")
        return
        
    full_df = pd.concat(dfs)
    full_df = full_df.sort_index()
    
    start_date = full_df.index.min()
    end_date = full_df.index.max()
    
    print(f"Data ranges from {start_date} to {end_date}")
    print(f"Rolling Approach: Train on {train_days} days, Trade on next {test_days} days")
    print(f"Grid Size: {len(combos)} configurations")
    
    # Initial window setup
    current_test_start = start_date + timedelta(days=train_days)
    
    # Calculate signals for all combos once over full_df to save massive time
    print(f"Pre-calculating signals for all {len(combos)} combinations...")
    combo_signals = {}
    for i, combo in enumerate(combos):
        params = dict(zip(keys, combo))
        hypo.set_params(params)
        combo_signals[i] = hypo.generate_signals(full_df)
        
    print("Starting rolling walk-forward simulation...")
    
    step = 0
    total_steps = (end_date - current_test_start).days // test_days
    
    while current_test_start < end_date:
        step += 1
        train_start = current_test_start - timedelta(days=train_days)
        test_end = current_test_start + timedelta(days=test_days)
        
        # print(f"[{step}/{total_steps}] Train: {train_start.date()} to {current_test_start.date()} | Test: {current_test_start.date()} to {test_end.date()}")
        
        # Slice train and test data
        train_df = full_df[(full_df.index >= train_start) & (full_df.index < current_test_start)]
        test_df = full_df[(full_df.index >= current_test_start) & (full_df.index < test_end)]
        
        if train_df.empty or test_df.empty:
            current_test_start += timedelta(days=test_days)
            continue
            
        best_score = -float('inf')
        best_combo_idx = None
        best_params = None
        
        # Find best params in train_df
        for i, combo in enumerate(combos):
            params = dict(zip(keys, combo))
            hypo.set_params(params)
            exit_model = build_exit_model(hypo.exit_model_name, hypo.exit_params)
            
            signals = combo_signals[i][train_df.index]
            if signals.sum() == 0:
                continue
                
            trades = run_backtest(
                train_df, signals, exit_model,
                symbol=symbol, interval=hypo.signal_interval, year=train_df.index[0].year,
                fees_pct=hypo.fees_pct, slippage_pct=hypo.slippage_pct, leverage=hypo.leverage,
            )
            
            if not trades:
                continue
                
            metrics = compute_metrics(trades)
            
            # Penalize strategies with less than 2 trades in 30 days
            if len(trades) < 2:
                continue
                
            # Optimize by a mix of Net Return and Sharpe
            score = metrics["total_return_pct"] * (metrics["sharpe_ratio"] if metrics["sharpe_ratio"] > 0 else 0)
            
            if score > best_score:
                best_score = score
                best_combo_idx = i
                best_params = params
                
        # Run best on test window
        if best_combo_idx is not None:
            # print(f"   ✓ Best Params: {dict_to_str(best_params)}")
            hypo.set_params(best_params)
            exit_model = build_exit_model(hypo.exit_model_name, hypo.exit_params)
            
            test_signals = combo_signals[best_combo_idx][test_df.index]
            if test_signals.sum() > 0:
                test_trades = run_backtest(
                    test_df, test_signals, exit_model,
                    symbol=symbol, interval=hypo.signal_interval, year=test_df.index[0].year,
                    fees_pct=hypo.fees_pct, slippage_pct=hypo.slippage_pct, leverage=hypo.leverage,
                )
                
                if test_trades:
                    # Adjust timestamps for aggregated metrics later
                    all_rolling_trades.extend(test_trades)
        else:
            pass # print(f"   ⚠️ No profitable params found in train window, skipping trading week.")
            
        # Move sliding window forward
        current_test_start += timedelta(days=test_days)
        
    print("\n" + "="*50)
    print("ROLLING WALK-FORWARD RESULT (Continuous)")
    print("="*50)
    
    if not all_rolling_trades:
        print("No trades executed across all rolling windows.")
        return
        
    metrics = compute_metrics(all_rolling_trades)
    
    print(f"Total Trades: {metrics['total_trades']}")
    print(f"Win Rate:     {metrics['win_rate']:.2f}%")
    print(f"Net Return:   {metrics['total_return_pct']:+.2f}%")
    print(f"Max DD:       {metrics['max_drawdown_pct']:.2f}%")
    print(f"Sharpe:       {metrics['sharpe_ratio']:.2f}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Rolling Walk-Forward Framework")
    parser.add_argument("hypothesis", help="Hypothesis ID to run")
    parser.add_argument("--symbol", default="SOLUSDT", help="Símbolo a testear")
    parser.add_argument("--train-days", type=int, default=30, help="Días de evaluación hacia atrás")
    parser.add_argument("--test-days", type=int, default=7, help="Días a operar hacia adelante")
    args = parser.parse_args()
    
    run_rolling_optimization(args.hypothesis, args.symbol, [2022, 2023, 2024, 2025], args.train_days, args.test_days)
