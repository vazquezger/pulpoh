import json
import csv
from pathlib import Path
from datetime import datetime

class LedgerDB:
    def __init__(self, settings_path="settings.json"):
        self.settings_path = Path(settings_path)
        self.live_dir = self._load_live_dir_config()
        
    def _load_live_dir_config(self) -> Path:
        if not self.settings_path.exists():
            return Path("live_data")
        
        with open(self.settings_path, "r") as f:
            data = json.load(f)
            dir_name = data.get("live_engine", {}).get("data_directory", "live_data")
            return Path(dir_name)
            
    def get_ledger_path(self, strategy_name: str) -> Path:
        strat_dir = self.live_dir / strategy_name
        strat_dir.mkdir(parents=True, exist_ok=True)
        return strat_dir / "trades.csv"
        
    def record_event(self, strategy_name: str, trade_id: str, action: str, 
                     price: float, size: float, pnl: float = None, timestamp: str = None):
                         
        filepath = self.get_ledger_path(strategy_name)
        file_exists = filepath.exists()
        
        if timestamp is None:
            # Use local time if not provided
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        pnl_str = f"{pnl:.4f}" if pnl is not None else ""
        
        with open(filepath, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["TradeID", "Timestamp", "Action", "Price", "Size", "PnL"])
                
            writer.writerow([trade_id, timestamp, action.upper(), f"{price:.6f}", f"{size:.6f}", pnl_str])
            
    def get_open_trade(self, strategy_name: str) -> dict:
        """
        Lee el CSV histórico entero para reconstruir el estado.
        Retorna el detalle del trade activo si hay un ENTRY sin un EXIT ni CANCEL.
        Si no hay trades activos, retorna None.
        """
        filepath = self.get_ledger_path(strategy_name)
        if not filepath.exists():
            return None
            
        trades_state = {}
        
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tid = row["TradeID"]
                action = row["Action"].upper()
                
                if tid not in trades_state:
                    trades_state[tid] = {
                        "trade_id": tid,
                        "status": "NONE",
                        "entry_price": 0.0,
                        "size": 0.0,
                        "entry_time": ""
                    }
                
                if action == "ENTRY":
                    trades_state[tid]["status"] = "OPEN"
                    trades_state[tid]["entry_price"] = float(row["Price"])
                    trades_state[tid]["size"] = float(row["Size"])
                    trades_state[tid]["entry_time"] = row["Timestamp"]
                    
                elif action in ["EXIT", "CANCEL"]:
                    trades_state[tid]["status"] = "CLOSED"
                    
        # Buscar si quedó algún trade con status OPEN
        for tid, data in trades_state.items():
            if data["status"] == "OPEN":
                return data
                
        return None

    def get_global_capital(self, starting_capital: float = 1000.0) -> dict:
        """
        Calcula el capital total combinando el PnL de TODAS las estrategias.
        Devuelve capital total y capital libre (restando lo bloqueado en trades abiertos).
        """
        total_pnl = 0.0
        locked_capital = 0.0
        
        if self.live_dir.exists():
            for filepath in self.live_dir.rglob("trades.csv"):
                trades_state = {}
                with open(filepath, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        tid = row["TradeID"]
                        action = row["Action"].upper()
                        
                        if tid not in trades_state:
                            trades_state[tid] = {"status": "NONE", "entry_value": 0.0}
                            
                        if action == "ENTRY":
                            trades_state[tid]["status"] = "OPEN"
                            trades_state[tid]["entry_value"] = float(row["Price"]) * float(row["Size"])
                        elif action == "EXIT":
                            trades_state[tid]["status"] = "CLOSED"
                            if row["PnL"]:
                                try:
                                    total_pnl += float(row["PnL"])
                                except ValueError:
                                    pass
                        elif action == "CANCEL":
                            trades_state[tid]["status"] = "CLOSED"
                            
                # Sum the locked capital of all trades that remain OPEN
                for tid, data in trades_state.items():
                    if data["status"] == "OPEN":
                        locked_capital += data["entry_value"]
                        
        total_capital = starting_capital + total_pnl
        free_capital = total_capital - locked_capital
        
        return {
            "total_capital": total_capital,
            "free_capital": free_capital,
            "locked_capital": locked_capital
        }
