import json
import requests
import pandas as pd
from pathlib import Path
from importlib import import_module

from framework.paper_db import LedgerDB

class DashboardCLI:
    def __init__(self):
        self.db = LedgerDB("settings.json")
        with open("settings.json", "r") as f:
            self.settings = json.load(f)["live_engine"]
            
        self.hypotheses = self._load_hypotheses()
        
    def _load_hypotheses(self):
        active_strats = self.settings.get("active_strats", [])
        hypo_objs = {}
        for strat in active_strats:
            try:
                module = import_module(f"hypotheses.{strat}.hypothesis")
                hypo_class = getattr(module, "Hypothesis")
                hypo_objs[strat] = hypo_class(Path(f"hypotheses/{strat}"))
            except Exception:
                pass
        return hypo_objs

    def _fetch_current_price(self, symbol: str) -> float:
        try:
            url = "https://api.binance.com/api/v3/ticker/price"
            resp = requests.get(url, params={"symbol": symbol}, timeout=5)
            return float(resp.json()["price"])
        except Exception:
            return 0.0

    def print_status(self):
        print("\n" + "="*50)
        print("📊 LIVE DASHBOARD (PAPER TRADING)")
        print("="*50)
        
        global_cap = self.db.get_global_capital(self.settings.get("default_capital", 1000.0))
        print(f"💰 Global Free Capital: ${global_cap['free_capital']:.2f}")
        print(f"🔒 Locked in Trades:   ${global_cap['locked_capital']:.2f}")
        print(f"💵 Total Equity:       ${global_cap['total_capital']:.2f}")
        print("="*50)
        
        for strat_name, hypo in self.hypotheses.items():
            symbols = hypo.config.get("symbols", [])
            for symbol in symbols:
                ledger_key = f"{strat_name}_{symbol}"
                open_trade = self.db.get_open_trade(ledger_key)
                
                print(f"🟢 {ledger_key}")
                
                if open_trade:
                    print(f"   Status:  [OPEN] TradeID: {open_trade['trade_id']}")
                    print(f"            Entry: ${open_trade['entry_price']:.2f} | Size: {open_trade['size']:.5f}")
                    
                    curr_price = self._fetch_current_price(symbol)
                    if curr_price > 0:
                        pnl = (curr_price - open_trade['entry_price']) * open_trade['size']
                        pnl_pct = (pnl / (open_trade['entry_price'] * open_trade['size'])) * 100
                        print(f"            Unrealized PnL: {pnl_pct:.2f}% (${pnl:.2f})")
                else:
                    print(f"   Status:  [Zzzz] Waiting for signal...")
                print("-" * 50)
        print("")

    def list_strategies(self):
        print("\n=== ESTRATEGIAS ACTIVAS ===")
        for strat_name, hypo in self.hypotheses.items():
            symbols = hypo.config.get("symbols", [])
            print(f"- {strat_name}")
            print(f"  └ Monedas: {', '.join(symbols)}")
            print(f"  └ Intervalo: {hypo.config.get('signal_interval')}\n")

    def cancel_trade(self, trade_id, ledger_key):
        open_trade = self.db.get_open_trade(ledger_key)
        if open_trade and open_trade["trade_id"] == trade_id:
            self.db.record_event(
                strategy_name=ledger_key, 
                trade_id=trade_id, 
                action="CANCEL", 
                price=open_trade["entry_price"], 
                size=open_trade["size"], 
                pnl=0.0
            )
            print(f"✅ Trade {trade_id} cancelled successfully in ledger.")
        else:
            print(f"❌ Trade {trade_id} not found or not OPEN in {ledger_key}.")

    def remove_strategy_or_symbol(self, strat_name, symbol_or_all):
        if strat_name not in self.hypotheses and symbol_or_all != "all":
            print(f"❌ Estrategia {strat_name} no encontrada o inactiva.")
            return

        if symbol_or_all.lower() == "all":
            # Quitar la estrategia de settings.json
            with open("settings.json", "r") as f:
                full_settings = json.load(f)
            
            strats = full_settings.get("live_engine", {}).get("active_strats", [])
            if strat_name in strats:
                strats.remove(strat_name)
                full_settings["live_engine"]["active_strats"] = strats
                
                with open("settings.json", "w") as f:
                    json.dump(full_settings, f, indent=4)
                
                print(f"✅ Estrategia {strat_name} removida completamente de active_strats y settings.json.")
                # Recargar memoria del dashboard
                with open("settings.json", "r") as f:
                    self.settings = json.load(f)["live_engine"]
                self.hypotheses = self._load_hypotheses()
            else:
                print(f"⚠️ {strat_name} no estaba en active_strats.")
        else:
            # Eliminar el symbol de config.json
            symbol = symbol_or_all.upper()
            config_path = Path(f"hypotheses/{strat_name}/config.json")
            if not config_path.exists():
                print(f"❌ No se encontró el archivo de config para {strat_name}.")
                return
            
            with open(config_path, "r") as f:
                strat_cfg = json.load(f)
            
            symbols = strat_cfg.get("symbols", [])
            if symbol in symbols:
                symbols.remove(symbol)
                strat_cfg["symbols"] = symbols
                
                with open(config_path, "w") as f:
                    json.dump(strat_cfg, f, indent=4)
                
                print(f"✅ Moneda {symbol} removida de {strat_name}.")
                # Recargar memoria del dashboard
                self.hypotheses = self._load_hypotheses()
            else:
                print(f"⚠️ {symbol} no estaba en la estrategia {strat_name}.")

    def start_repl(self):
        print("Pulpoh Dashboard Initialized.")
        print("Commands: status | list | cancel <TradeID> <Strategy_Symbol> | exit\n")
        
        while True:
            try:
                cmd_input = input("dashboard> ").strip().split()
                if not cmd_input:
                    continue
                    
                cmd = cmd_input[0].lower()
                if cmd in ["exit", "quit", "q"]:
                    print("Cerrando dashboard...")
                    break
                elif cmd == "status":
                    self.print_status()
                elif cmd == "list":
                    self.list_strategies()
                elif cmd == "cancel":
                    if len(cmd_input) < 3:
                        print("Uso: cancel <TradeID> <Strategy_Symbol> (ej: cancel ab12cd34 abc_reversal_SOLUSDT)")
                    else:
                        self.cancel_trade(trade_id=cmd_input[1], ledger_key=cmd_input[2])
                elif cmd == "remove":
                    if len(cmd_input) < 3:
                        print("Uso: remove <Strategy> <Symbol|all> (ej: remove abc_reversal BNBUSDT o remove trend_following all)")
                    else:
                        self.remove_strategy_or_symbol(strat_name=cmd_input[1], symbol_or_all=cmd_input[2])
                elif cmd == "help":
                    print("\n=== COMANDOS DISPONIBLES ===")
                    print("status  - Muestra el estado de la cuenta virtual, pnl no realizado y posiciones abiertas.")
                    print("list    - Muestra la lista de estrategias cargadas y activas.")
                    print("cancel  - Cancela un trade activo (Uso: cancel <TradeID> <Strategy_Symbol>).")
                    print("remove  - Elimina un par o estrategia (Uso: remove <Strategy> <Symbol|all>).")
                    print("exit    - Cierra el dashboard (no apaga el motor de trading en segundo plano).\n")
                else:
                    print(f"Comando desconocido: {cmd}. Escribe 'help' para ver los comandos disponibles.")
            except KeyboardInterrupt:
                print("\nCerrando dashboard...")
                break

if __name__ == "__main__":
    cli = DashboardCLI()
    cli.start_repl()
