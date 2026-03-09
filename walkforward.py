"""
walkforward.py — Framework genérico de Walk-Forward Validation

Metodología:
  Lee `optimize.json` del directorio de la hipótesis.
  P. ej.:
    "walkforward_windows": [{"train": [2022], "validate": 2023}, ...]
    "param_grid": {"PIVOT_WINDOW": [2, 3], "exit_params.tp_pct": [4.0, 5.0]}

Para cada ventana definida:
  1. Ejecuta Backtest con Grid search sobre `param_grid` usando `hypo.set_params()`
  2. Elige los mejores parámetros en la ventana de entrenamiento (train)
  3. Aplica esos parámetros (sin re-optimizar) en el año de validación
  4. Muestra la degradación de métricas para detectar overfitting

Uso:
    python3 walkforward.py abc_reversal
    python3 walkforward.py abc_reversal --symbol BTCUSDT --sort sharpe
"""

import sys
import argparse
import itertools
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from framework.downloader import get_ohlcv
from framework.exit_models import build_exit_model
from framework.backtester import run_backtest
from framework.reporter import compute_metrics
from run import discover_hypotheses, load_hypothesis

def run_years(hypo, symbol, years):
    """Corre backtest sobre una lista de años usando el config actual del hypo y devuelve métricas."""
    all_trades = []
    
    # Cada vez instanciamos el modelo de salida para tomar los posibles nuevos `exit_params`
    exit_model = build_exit_model(hypo.exit_model_name, hypo.exit_params)
    
    # Evitamos recargar datos o re-imprimir usando .generate_signals() directamente
    for year in years:
        hypo._current_symbol = symbol
        hypo._current_year   = year
        hypo._refresh_data   = False

        df = get_ohlcv(symbol, hypo.signal_interval, year, refresh=False)
        if df.empty:
            continue

        signals = hypo.generate_signals(df)
        if signals.sum() == 0:
            continue

        trades = run_backtest(
            df, signals, exit_model,
            symbol=symbol, interval=hypo.signal_interval, year=year,
            fees_pct=hypo.fees_pct, slippage_pct=hypo.slippage_pct, leverage=hypo.leverage,
        )
        all_trades.extend(trades)

    if not all_trades:
        return None
    return compute_metrics(all_trades)

def optimize(hypo, symbol, train_years, param_grid, sort_by="sharpe", min_trades=10):
    """Encuentra los mejores parámetros iterando sobre el grid."""
    best = None
    best_score = -float("inf")
    best_params = None

    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))

    for combo in combos:
        params = dict(zip(keys, combo))
        # Inyecta los parámetros en la hipótesis (actualiza config/instance attrs)
        hypo.set_params(params)
        
        m = run_years(hypo, symbol, train_years)
        
        if m is None or m["total_trades"] < min_trades:
            continue

        score = m["sharpe_ratio"] if sort_by == "sharpe" else m["total_return_pct"]
        if score > best_score:
            best_score = score
            best = m
            best_params = params

    return best_params, best

def dict_to_str(d):
    return " ".join([f"{k.split('.')[-1]}={v}" for k, v in d.items()])

def main():
    parser = argparse.ArgumentParser(description="Walk-Forward Framework")
    parser.add_argument("hypothesis", help="Hypothesis ID to run (e.g. abc_reversal)")
    parser.add_argument("--symbol", help="Símbolo a testear (si no, usa el 1ro de config.json)")
    parser.add_argument("--sort", default="sharpe", choices=["sharpe", "net_return"])
    args = parser.parse_args()

def run_walkforward(hypo_name, symbol_override=None, sort_by="sharpe"):
    hypos = discover_hypotheses()
    key = hypo_name.lower()
    
    if key not in hypos:
        print(f"❌ Hypothesis '{hypo_name}' not found.")
        return None
        
    folder = hypos[key]
    optimize_json_path = folder / "optimize.json"
    
    if not optimize_json_path.exists():
        print(f"❌ '{folder.name}' does not have an optimize.json file.")
        return None
        
    with open(optimize_json_path, "r", encoding="utf-8") as f:
        opt_config = json.load(f)
        
    windows = opt_config.get("walkforward_windows", [])
    param_grid = opt_config.get("param_grid", {})
    
    if not windows or not param_grid:
        print("❌ 'optimize.json' must contain 'walkforward_windows' and 'param_grid'.")
        return None

    print(f"\nLoading: {folder.name}")
    hypo = load_hypothesis(folder)
    
    symbol = symbol_override if symbol_override else hypo.symbols[0]
    
    print(f"\n{'='*65}")
    print(f"  Walk-Forward Validation — {folder.name} ({symbol})")
    print(f"  Optimizando por: {sort_by}")
    print(f"{'='*65}\n")

    wf_results = []
    total_combos = len(list(itertools.product(*param_grid.values())))

    for i, window in enumerate(windows, 1):
        train_years = window["train"]
        val_year    = window["validate"]

        print(f"── Ventana {i}: Train={train_years} │ Validate={val_year} ──────────")
        print(f"   Corriendo grid search ({total_combos} combos)...", flush=True)

        best_params, train_m = optimize(hypo, symbol, train_years, param_grid, sort_by=sort_by)
        if best_params is None:
            print(f"   ❌ Sin resultados para train={train_years}\n")
            continue

        print(f"   ✓ Mejores params: {dict_to_str(best_params)}")
        print(f"   Train  → Net: {train_m['total_return_pct']:+.2f}%  "
              f"Sharpe: {train_m['sharpe_ratio']:.2f}  "
              f"DD: -{train_m['max_drawdown_pct']:.2f}%  "
              f"Trades: {train_m['total_trades']}")

        # Validar con parámetros encontrados:
        hypo.set_params(best_params)
        val_m = run_years(hypo, symbol, [val_year])

        if val_m is None:
            print(f"   Validate → 0 trades\n")
            continue

        sharpe_delta = val_m["sharpe_ratio"] - train_m["sharpe_ratio"]
        verdict = "✅ Robusto" if val_m["sharpe_ratio"] > 1.0 else (
                  "⚠️  Aceptable" if val_m["sharpe_ratio"] > 0 else "❌ Overfitting")

        print(f"   Validate → Net: {val_m['total_return_pct']:+.2f}%  "
              f"Sharpe: {val_m['sharpe_ratio']:.2f}  "
              f"DD: -{val_m['max_drawdown_pct']:.2f}%  "
              f"Trades: {val_m['total_trades']}  │ {verdict}")
        print(f"   Sharpe degradation: {sharpe_delta:+.2f}\n")

        wf_results.append({
            "window": i, "val_year": val_year,
            "params": best_params,
            "train_sharpe": round(train_m["sharpe_ratio"], 2),
            "val_sharpe":   round(val_m["sharpe_ratio"],   2),
            "val_net":      round(val_m["total_return_pct"], 2),
            "val_dd":       round(val_m["max_drawdown_pct"], 2),
            "verdict": verdict,
        })

    if not wf_results:
        return None

    print(f"{'='*65}")
    print(f"  RESUMEN WALK-FORWARD — {symbol}")
    print(f"{'='*65}")
    print(f"  {'Val_Yr':>6} │ {'Train♟':>8} {'Val♟':>7} {'Net%':>8} {'DD%':>8}  Veredicto  │ Params")
    print(f"  {'-'*6} ┼ {'-'*8} {'-'*7} {'-'*8} {'-'*8}  {'-'*10} ┼ {'-'*20}")
    for r in wf_results:
        p_str = dict_to_str(r["params"])
        print(f"  {r['val_year']:>6} │ "
              f"{r['train_sharpe']:>8.2f} {r['val_sharpe']:>7.2f} "
              f"{r['val_net']:>+8.2f}% {r['val_dd']:>7.2f}%  {r['verdict']:<10} │ {p_str}")

    avg_val_sharpe = sum(r["val_sharpe"] for r in wf_results) / len(wf_results)
    avg_val_net    = sum(r["val_net"]    for r in wf_results) / len(wf_results)
    print(f"\n  Promedio validación → Sharpe: {avg_val_sharpe:.2f}  Net: {avg_val_net:+.2f}%/año\n")
    
    return {
        "avg_sharpe": avg_val_sharpe,
        "avg_net": avg_val_net,
        "results": wf_results
    }

def main():
    parser = argparse.ArgumentParser(description="Walk-Forward Framework")
    parser.add_argument("hypothesis", help="Hypothesis ID to run (e.g. abc_reversal)")
    parser.add_argument("--symbol", help="Símbolo a testear (si no, usa el 1ro de config.json)")
    parser.add_argument("--sort", default="sharpe", choices=["sharpe", "net_return"])
    args = parser.parse_args()

    # Descartamos el retorno por consola de main
    res = run_walkforward(args.hypothesis, args.symbol, args.sort)
    if res is None:
        sys.exit(1)

if __name__ == "__main__":
    main()
