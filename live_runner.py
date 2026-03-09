import time
import requests
import json
import uuid
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from importlib import import_module

from framework.paper_db import LedgerDB
from framework.exit_models import build_exit_model

BINANCE_URL = "https://api.binance.com/api/v3/klines"

def fetch_live_candles(symbol: str, interval: str, limit: int = 1000) -> pd.DataFrame:
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    retry_delay = 5 # Initial delay in seconds
    max_delay = 300 # Cap delay at 5 minutes
    
    while True:
        try:
            resp = requests.get(BINANCE_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            break # Success, exit retry loop
        except Exception as e:
            print(f"[!] Fetch error {symbol} {interval}: {e}")
            print(f"    Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay) # Exponential backoff with cap

    columns = ["timestamp", "open", "high", "low", "close", "volume", 
               "close_time", "quote_volume", "num_trades", "taker_buy_base", "taker_buy_quote", "ignore"]
    df = pd.DataFrame(data, columns=columns)
    
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    numeric_cols = ["open", "high", "low", "close", "volume"]
    df[numeric_cols] = df[numeric_cols].astype(float)
    return df

class LiveEngine:
    def __init__(self):
        self.db = LedgerDB("settings.json")
        
        with open("settings.json", "r") as f:
            self.settings = json.load(f)["live_engine"]
            
        self.hypotheses = self._load_hypotheses()
        
        self.poll_sec = self.settings.get("poll_interval_seconds", 60)
        
    def _load_hypotheses(self):
        active_strats = self.settings.get("active_strats", [])
        hypo_objs = {}
        for strat in active_strats:
            try:
                module = import_module(f"hypotheses.{strat}.hypothesis")
                hypo_class = getattr(module, "Hypothesis")
                hypo_objs[strat] = hypo_class(Path(f"hypotheses/{strat}"))
                print(f"[+] Loaded strategy logic: {strat}")
            except Exception as e:
                print(f"[!] Could not load {strat}: {e}")
        return hypo_objs

    def run_forever(self):
        print("\n🚀 PULPOH BACKGROUND ENGINE STARTED")
        print("Using Smart Sleep (Cron) to fetch candles only precisely at closing intervals...\n")
        
        while True:
            # Recargar configuración al inicio de cada iteración
            try:
                with open("settings.json", "r") as f:
                    self.settings = json.load(f)["live_engine"]
                self.poll_sec = self.settings.get("poll_interval_seconds", 60)
                self.hypotheses = self._load_hypotheses()
            except Exception as e:
                print(f"[!] Error recargando configuraciones: {e}")

            # Polling engine logic (Silent unless there's an action)
            for strat_name, hypo in self.hypotheses.items():
                symbols = hypo.config.get("symbols", [])
                interval = hypo.config.get("signal_interval")
                exit_params = hypo.config.get("exit_params", {})
                exit_model_name = hypo.config.get("exit_model")
                fees_pct = hypo.config.get("fees_pct", 0.05)
                
                for symbol in symbols:
                    ledger_key = f"{strat_name}_{symbol}"
                    
                    # El DB reconstruye el ledger en vivo. Si desde el CLI alguien agregó un CANCEL, el open_trade de abajo vendrá None.
                    open_trade = self.db.get_open_trade(ledger_key)
                    df = fetch_live_candles(symbol, interval, limit=1000)
                    
                    if df.empty: continue
                    df_closed = df.iloc[:-1].copy().reset_index(drop=True)
                    if df_closed.empty: continue
                    
                    last_closed_candle = df_closed.iloc[-1]
                    
                    if open_trade is None:
                        # Fetch the global shared free capital for sizing
                        global_cap = self.db.get_global_capital(self.settings.get("default_capital", 1000.0))
                        free_capital = global_cap["free_capital"]
                        
                        # Entry logic
                        try:
                            signals = hypo.generate_signals(df_closed)
                            if signals.iloc[-1] == 1 and free_capital > 10: # Only trade if we have at least $10
                                entry_price = last_closed_candle["close"] 
                                usable_capital = free_capital * (1 - (fees_pct/100))
                                size = usable_capital / entry_price
                                trade_id = str(uuid.uuid4())[:8]
                                
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 BUY LONG: {ledger_key} @ {entry_price:.2f} | Size: {size:.4f} | ID: {trade_id}")
                                
                                self.db.record_event(ledger_key, trade_id, "ENTRY", entry_price, size)
                        except Exception as e:
                            print(f"Eval Error on {ledger_key}: {e}")
                    else:
                        # Exit Logic
                        try:
                            entry_time_ts = pd.to_datetime(open_trade["entry_time"], utc=True)
                            entry_price = open_trade["entry_price"]
                            size = open_trade["size"]
                            trade_id = open_trade["trade_id"]
                            
                            df_post_entry = df[df["timestamp"] > entry_time_ts].copy()
                            if not df_post_entry.empty:
                                exit_model = build_exit_model(exit_model_name, exit_params)
                                result = exit_model.get_exit(entry_price, df_post_entry)
                                
                                has_exited = result.reason != "END_OF_DATA" and result.reason != "TIME"
                                if result.reason == "TIME": has_exited = True
                                    
                                if has_exited:
                                    exit_price = result.exit_price
                                    exit_value = exit_price * size
                                    net_val = exit_value * (1 - (fees_pct/100))
                                    orig_val = entry_price * size
                                    pnl_abs = net_val - orig_val
                                    pnl_pct = (pnl_abs / orig_val) * 100
                                    
                                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ SELL CLOSED: {ledger_key} | {trade_id} @ {exit_price:.2f} | PnL: {pnl_pct:.2f}%")
                                    
                                    self.db.record_event(ledger_key, trade_id, "EXIT", exit_price, size, pnl_abs)
                        except Exception as e:
                            print(f"Exit Eval Error on {ledger_key}: {e}")
            # --- SMART SLEEP (CRON SCHEDULER) ---
            # Encontrar la próxima vela a cerrar (el intervalo más corto entre todas las estrategias)
            next_wake_time = None
            now = datetime.now(timezone.utc)
            
            for _, hypo in self.hypotheses.items():
                interval = hypo.config.get("signal_interval", "1h")
                # Lógica simplificada: si opera en 1h, despertar en el minuto 0 de la siguiente hora.
                # Si opera en 1d, despertar a las 00:00 UTC del día siguiente.
                
                if interval.endswith("h"):
                    hours = int(interval[:-1])
                    # Calcula la próxima "X" hora exacta
                    # Ejemplo simple para 1h: próxima hora en el minuto 0.
                    next_hour = now.replace(minute=0, second=5, microsecond=0) + pd.Timedelta(hours=hours)
                    if next_wake_time is None or next_hour < next_wake_time:
                        next_wake_time = next_hour
                elif interval.endswith("d"):
                    days = int(interval[:-1])
                    next_day = now.replace(hour=0, minute=0, second=5, microsecond=0) + pd.Timedelta(days=days)
                    if next_wake_time is None or next_day < next_wake_time:
                        next_wake_time = next_day
            
            if next_wake_time:
                sleep_sec = (next_wake_time - now).total_seconds()
                # Limite de seguridad por si el cálculo da negativo o muy pequeño
                sleep_sec = max(sleep_sec, 60)
                # Convertir a hora local para el log
                local_wake_time = next_wake_time.astimezone()
                wake_time_str = local_wake_time.strftime('%H:%M:%S')
            else:
                sleep_sec = self.poll_sec
                wake_time_str = "Unknown"
                
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 💤 Hiberning for {int(sleep_sec)}s until next tick @ {wake_time_str}...")
            time.sleep(sleep_sec)

if __name__ == "__main__":
    try:
        engine = LiveEngine()
        engine.run_forever()
    except KeyboardInterrupt:
        print("\n[!] Engine shutting down cleanly.")
