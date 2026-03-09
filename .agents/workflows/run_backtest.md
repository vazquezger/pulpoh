---
description: Run backtest for a hypothesis
---

To run a backtest for a specific hypothesis (e.g., `abc_reversal`, `ny_reversal_wicks`), run the following command from the root of the project:

```bash
// turbo
python3 run.py <hypothesis_name>
```

## Additional Flags
- `--list`: List all available hypotheses.
- `--signals-only`: Only calculate and show signals, skip the backtesting and reporting phase.
- `--refresh-data`: Force re-download of OHLCV data instead of using the local cache.
