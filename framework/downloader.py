"""
framework/downloader.py

Downloads OHLCV data from Binance public API.
Cache: framework/data/{SYMBOL}/{YEAR}/{interval}.csv
If the file exists, it is loaded from disk — no re-download needed.
Use --refresh-data flag in run.py to force re-download.
"""

import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

BINANCE_BASE = "https://api.binance.com/api/v3/klines"
DATA_DIR = Path(__file__).parent / "data"

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume",
           "close_time", "quote_volume", "num_trades",
           "taker_buy_base", "taker_buy_quote", "ignore"]


def _year_to_timestamps(year: int):
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    """Fetch all klines for a time range, handling pagination automatically."""
    all_rows = []
    current_start = start_ms

    while current_start < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "endTime": end_ms,
            "limit": 1000,
        }

        for attempt in range(5):
            try:
                resp = requests.get(BINANCE_BASE, params=params, timeout=30)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 60))
                    print(f"  [Rate limit] Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                if attempt == 4:
                    raise RuntimeError(f"Failed to fetch {symbol} {interval}: {e}")
                time.sleep(2 ** attempt)

        if not data:
            break

        all_rows.extend(data)
        last_ts = data[-1][0]

        # If we got less than 1000 rows, we've reached the end
        if len(data) < 1000:
            break

        current_start = last_ts + 1
        time.sleep(0.1)  # Be polite to the API

    if not all_rows:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.DataFrame(all_rows, columns=COLUMNS)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

    numeric_cols = ["open", "high", "low", "close", "volume",
                    "quote_volume", "taker_buy_base", "taker_buy_quote"]
    df[numeric_cols] = df[numeric_cols].astype(float)
    df["num_trades"] = df["num_trades"].astype(int)
    df = df.drop(columns=["ignore"])

    return df.reset_index(drop=True)


def get_ohlcv(
    symbol: str,
    interval: str,
    year: int,
    refresh: bool = False
) -> pd.DataFrame:
    """
    Get OHLCV data for a symbol/interval/year combination.
    Downloads from Binance if not cached; loads from disk otherwise.

    Args:
        symbol: e.g. "BTCUSDT"
        interval: e.g. "1h", "4h", "1d"
        year: e.g. 2024
        refresh: if True, re-downloads even if cache exists

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume, ...
    """
    cache_path = DATA_DIR / symbol / str(year) / f"{interval}.csv"

    if cache_path.exists() and not refresh:
        print(f"  [Cache] Loading {symbol}/{year}/{interval}.csv")
        df = pd.read_csv(cache_path, parse_dates=["timestamp", "close_time"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
        return df

    print(f"  [Download] Fetching {symbol} {interval} for {year}...")
    start_ms, end_ms = _year_to_timestamps(year)
    df = _fetch_klines(symbol, interval, start_ms, end_ms)

    if df.empty:
        print(f"  [Warning] No data returned for {symbol}/{year}/{interval}")
        return df

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    print(f"  [Saved] {cache_path} ({len(df)} rows)")

    return df


def get_ohlcv_multi(
    symbols: list[str],
    intervals: list[str],
    years: list[int],
    refresh: bool = False
) -> dict:
    """
    Download/load all combinations of symbol × interval × year.

    Returns:
        dict keyed by (symbol, interval, year) → DataFrame
    """
    data = {}
    total = len(symbols) * len(intervals) * len(years)
    count = 0

    for symbol in symbols:
        for interval in intervals:
            for year in years:
                count += 1
                print(f"[{count}/{total}] {symbol} {interval} {year}")
                df = get_ohlcv(symbol, interval, year, refresh=refresh)
                data[(symbol, interval, year)] = df

    return data
