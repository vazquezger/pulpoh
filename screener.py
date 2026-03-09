"""
screener.py — Portfolio Screener Automático

Ejecuta el marco de validación cruzada (Walk-Forward) de una hipótesis
sobre un portafolio de activos pre-seleccionados, ordenando los resultados
de mayor a menor Sharpe Ratio.

Uso:
    python3 screener.py abc_reversal
    python3 screener.py abc_reversal --top 5
"""

import sys
import argparse
import pandas as pd
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from run import discover_hypotheses
from walkforward import run_walkforward

# Top 10 activos por capitalización histórica y liquidez (excluyendo stablecoins)
DEFAULT_PORTFOLIO = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOGEUSDT",
    "DOTUSDT",
    "LINKUSDT"
]

def main():
    parser = argparse.ArgumentParser(description="Portfolio Screener for pulpoh")
    parser.add_argument("hypothesis", help="ID de la hipótesis (ej: abc_reversal)")
    parser.add_argument("--top", type=int, default=10, help="Cantidad de monedas a evaluar del Top 10")
    args = parser.parse_args()

    hypo_name = args.hypothesis.lower()
    hypos = discover_hypotheses()

    if hypo_name not in hypos:
        print(f"❌ Hipótesis '{hypo_name}' no encontrada.")
        sys.exit(1)

    symbols_to_test = DEFAULT_PORTFOLIO[:args.top]
    print(f"\n============================================================")
    print(f"  PULPOH SCREENER — Evaluando: {hypo_name}")
    print(f"  Portafolio: {len(symbols_to_test)} activos")
    print(f"============================================================\n")

    results = []

    for idx, symbol in enumerate(symbols_to_test, 1):
        print(f"\n[{idx}/{len(symbols_to_test)}] Analizando {symbol}...")
        
        # Ocultamos temporalmente la salida de walkforward si queremos menos ruido, 
        # pero para el inicio está bien dejarla visible para ver el progreso.
        try:
            wf_metrics = run_walkforward(hypo_name, symbol_override=symbol, sort_by="sharpe")
        except Exception as e:
            print(f"❌ Error al procesar {symbol}: {e}")
            continue

        if wf_metrics is None:
            print(f"⚠️ Sin resultados válidos para {symbol}")
            continue

        results.append({
            "Symbol": symbol,
            "Sharpe Validado": round(wf_metrics["avg_sharpe"], 2),
            "Net Return Validado": round(wf_metrics["avg_net"], 2)
        })

    if not results:
        print("\n❌ El screener finalizó sin resultados válidos para ningún activo.")
        sys.exit(1)

    # Crear DataFrame y ordenar por Sharpe de mayor a menor
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values(by="Sharpe Validado", ascending=False).reset_index(drop=True)

    # Imprimir Tabla Final
    print(f"\n\n============================================================")
    print(f"  RANKING FINAL OOS (Out-Of-Sample) — {hypo_name.upper()}")
    print(f"============================================================\n")
    print(df_results.to_string(index=False))
    print(f"\n============================================================\n")

    # Exportar a CSV en la carpeta de la estrategia
    export_path = hypos[hypo_name] / "results" / "screener_ranking.csv"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    df_results.to_csv(export_path, index=False)
    print(f"✅ Ranking exportado exitosamente a: {export_path}")

if __name__ == "__main__":
    main()
