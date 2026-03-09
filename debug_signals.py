from pathlib import Path
import pandas as pd
from framework.base_hypothesis import BaseHypothesis
from hypotheses.abc_reversal.hypothesis import Hypothesis

def run_debug():
    df = pd.read_csv("framework/data/SOLUSDT/2025/1h.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Filter April 2025 for speed
    df_april = df[(df["timestamp"] >= "2025-04-12") & (df["timestamp"] <= "2025-04-25")].copy().reset_index(drop=True)
    
    # Let's initialize the Hypothesis and run `generate_signals` which adds columns
    hypo = Hypothesis(Path("hypotheses/abc_reversal"))
    
    signals = hypo.generate_signals(df_april)
    df_april["signal"] = signals
    
    # Print the OHLC + signal around April 14 and April 21
    print("--- APRIL 14 ---")
    april_14 = df_april[(df_april["timestamp"] >= "2025-04-14 14:00") & (df_april["timestamp"] <= "2025-04-14 23:00")]
    print(april_14[["timestamp", "open", "high", "low", "close", "rsi", "atr", "signal"]].to_string())

    print("\n--- APRIL 21 ---")
    april_21 = df_april[(df_april["timestamp"] >= "2025-04-21 14:00") & (df_april["timestamp"] <= "2025-04-21 23:00")]
    print(april_21[["timestamp", "open", "high", "low", "close", "rsi", "atr", "signal"]].to_string())

if __name__ == "__main__":
    run_debug()
