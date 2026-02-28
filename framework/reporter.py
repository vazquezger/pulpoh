"""
framework/reporter.py

Standardized reporting for all hypotheses.
Generates one report per (year × symbol) combination, plus a summary.

Output structure:
    hypotheses/{name}/results/
        ├── {year}_{symbol}/
        │   ├── report.md
        │   ├── trades.csv
        │   └── equity_curve.png
        └── summary.md      ← Comparison table of all year×symbol runs
"""

import math
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for saving files
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from framework.backtester import Trade


# ─── Metrics ────────────────────────────────────────────────────────────────

def compute_metrics(trades: list[Trade], df: pd.DataFrame = None) -> dict:
    if not trades:
        return {"total_trades": 0}

    pnls = [t.pnl_pct for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Cumulative returns for drawdown
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    equity = []
    for p in pnls:
        cum += p
        equity.append(cum)
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd

    avg_pnl = np.mean(pnls)
    std_pnl = np.std(pnls)

    # Annualize Sharpe by actual trade frequency (not calendar days)
    # sqrt(252) would assume one trade per day — incorrect for sparse signals
    n_trades = len(trades)
    trades_per_year = n_trades  # all trades are within one year by design
    sharpe = (avg_pnl / std_pnl * math.sqrt(trades_per_year)) if std_pnl > 0 else 0

    # Buy-and-hold benchmark: (last_close / first_open - 1) * 100
    buy_and_hold = 0.0
    if df is not None and not df.empty:
        first_price = df["open"].iloc[0]
        last_price = df["close"].iloc[-1]
        buy_and_hold = (last_price / first_price - 1) * 100

    exit_counts = {}
    for t in trades:
        exit_counts[t.exit_reason] = exit_counts.get(t.exit_reason, 0) + 1

    return {
        "total_trades": n_trades,
        "win_rate": len(wins) / n_trades * 100,
        "profit_factor": profit_factor,
        "total_return_pct": sum(pnls),
        "total_return_gross_pct": sum([t.pnl_gross_pct for t in trades]),
        "total_fees_cost_pct": sum([t.fees_paid_pct for t in trades]),
        "buy_and_hold_pct": buy_and_hold,
        "avg_win_pct": np.mean(wins) if wins else 0,
        "avg_loss_pct": np.mean(losses) if losses else 0,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": sharpe,
        "avg_bars_held": np.mean([t.bars_held for t in trades]),
        "exit_breakdown": exit_counts,
        "equity_curve": equity,
    }


# ─── Charts ─────────────────────────────────────────────────────────────────

def _plot_equity_curve(trades: list[Trade], output_path: Path):
    pnls = [t.pnl_pct for t in trades]
    times = [t.exit_time for t in trades]
    equity = np.cumsum(pnls)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(times, equity, linewidth=1.5, color="#3b82f6")
    ax.axhline(0, color="#ef4444", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.fill_between(times, 0, equity,
                    where=[e >= 0 for e in equity],
                    alpha=0.15, color="#22c55e")
    ax.fill_between(times, 0, equity,
                    where=[e < 0 for e in equity],
                    alpha=0.15, color="#ef4444")
    ax.set_title("Equity Curve (cumulative %)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Cumulative Return (%)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.autofmt_xdate()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)


def _plot_monthly_returns(trades: list[Trade], output_path: Path):
    if not trades:
        return

    df = pd.DataFrame([{
        "month": t.exit_time.strftime("%Y-%m"),
        "pnl": t.pnl_pct,
    } for t in trades])

    monthly = df.groupby("month")["pnl"].sum().reset_index()
    months = monthly["month"]
    returns = monthly["pnl"]
    colors = ["#22c55e" if r >= 0 else "#ef4444" for r in returns]

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(range(len(months)), returns, color=colors, alpha=0.85)
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(months, rotation=45, ha="right", fontsize=8)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Monthly Returns (%)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Return (%)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)


def _plot_trades_html(trades: list[Trade], df: pd.DataFrame, output_path: Path):
    """
    Genera un gráfico interactivo HTML (Plotly CDN) con:
      - Línea de precio de cierre (OHLC resumen)
      - Triángulo ▲ verde en cada entrada
      - Círculo ● en cada salida: verde=TP, rojo=SL/LIQUIDATED, naranja=TIME
      - Tooltip con detalles del trade al pasar el mouse
      - Scroll/zoom horizontal nativo
    """
    if not trades or df is None or df.empty:
        return

    # Precio de cierre como base
    times = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M").tolist()
    closes = df["close"].tolist()

    # Datos de entradas
    entry_x = [t.entry_time.strftime("%Y-%m-%d %H:%M") for t in trades]
    entry_y = [t.entry_price * 0.995 for t in trades]  # ligeramente debajo
    entry_text = [
        f"ENTRY #{i+1}<br>Price: {t.entry_price:.2f}<br>Exit: {t.exit_reason}<br>PnL: {t.pnl_pct:+.2f}%"
        for i, t in enumerate(trades)
    ]

    # Datos de salidas
    exit_x = [t.exit_time.strftime("%Y-%m-%d %H:%M") for t in trades]
    exit_y = [t.exit_price for t in trades]
    exit_colors = []
    exit_text = []
    for i, t in enumerate(trades):
        if t.exit_reason == "TP":
            exit_colors.append("#22c55e")
        elif t.exit_reason in ("SL", "LIQUIDATED"):
            exit_colors.append("#ef4444")
        else:
            exit_colors.append("#f59e0b")
        exit_text.append(
            f"EXIT #{i+1}<br>Reason: {t.exit_reason}<br>Price: {t.exit_price:.2f}<br>PnL: {t.pnl_pct:+.2f}%"
        )

    # Líneas de conexión entry→exit por trade
    lines_x, lines_y = [], []
    for t in trades:
        lines_x += [t.entry_time.strftime("%Y-%m-%d %H:%M"),
                    t.exit_time.strftime("%Y-%m-%d %H:%M"), None]
        lines_y += [t.entry_price, t.exit_price, None]

    symbol = trades[0].symbol
    year = trades[0].year

    # Serializar a JSON
    import json
    price_data = json.dumps({"x": times, "y": closes})
    entry_data = json.dumps({"x": entry_x, "y": entry_y, "text": entry_text})
    exit_data  = json.dumps({"x": exit_x,  "y": exit_y,  "text": exit_text, "colors": exit_colors})
    lines_data = json.dumps({"x": lines_x, "y": lines_y})

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{symbol} {year} — Trades Chart</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    body {{ margin: 0; background: #0f172a; font-family: system-ui, sans-serif; }}
    h1   {{ color: #e2e8f0; font-size: 1rem; padding: 12px 16px 4px; margin: 0; }}
    #chart {{ width: 100%; height: calc(100vh - 44px); }}
  </style>
</head>
<body>
  <h1>{symbol} {year} — {len(trades)} trades &nbsp;|&nbsp; Scroll to zoom · Drag to pan</h1>
  <div id="chart"></div>
  <script>
    const price  = {price_data};
    const entry  = {entry_data};
    const exit_d = {exit_data};
    const lines  = {lines_data};

    const traces = [
      // Precio de cierre
      {{
        x: price.x, y: price.y,
        mode: "lines",
        name: "Close",
        line: {{ color: "#60a5fa", width: 1.5 }},
        hovertemplate: "%{{x}}<br>$%{{y:,.2f}}<extra></extra>"
      }},
      // Líneas entry→exit
      {{
        x: lines.x, y: lines.y,
        mode: "lines",
        name: "Trade",
        line: {{ color: "rgba(148,163,184,0.25)", width: 1, dash: "dot" }},
        hoverinfo: "skip",
        showlegend: false
      }},
      // Entradas
      {{
        x: entry.x, y: entry.y,
        mode: "markers",
        name: "Entry",
        marker: {{ symbol: "triangle-up", size: 12, color: "#22c55e",
                   line: {{ color: "#166534", width: 1 }} }},
        text: entry.text,
        hovertemplate: "%{{text}}<extra></extra>"
      }},
      // Salidas
      {{
        x: exit_d.x, y: exit_d.y,
        mode: "markers",
        name: "Exit",
        marker: {{ symbol: "circle", size: 9,
                   color: exit_d.colors,
                   line: {{ color: "#1e1e2e", width: 1 }} }},
        text: exit_d.text,
        hovertemplate: "%{{text}}<extra></extra>"
      }}
    ];

    const layout = {{
      paper_bgcolor: "#0f172a",
      plot_bgcolor:  "#1e293b",
      font:  {{ color: "#94a3b8" }},
      xaxis: {{ type: "category", tickangle: -45, showgrid: false,
                rangeslider: {{ visible: true, bgcolor: "#1e293b" }} }},
      yaxis: {{ showgrid: true, gridcolor: "#334155",
                tickformat: "$,.0f" }},
      legend: {{ bgcolor: "rgba(0,0,0,0)" }},
      margin: {{ l: 60, r: 20, t: 10, b: 80 }},
      hovermode: "x unified"
    }};

    Plotly.newPlot("chart", traces, layout, {{
      responsive: true,
      displayModeBar: true,
      scrollZoom: true
    }});
  </script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")


# ─── Report per (year × symbol) ─────────────────────────────────────────────

def generate_run_report(
    trades: list[Trade],
    hypo_name: str,
    hypo_description: str,
    results_dir: Path,
    df: pd.DataFrame = None,
) -> dict:
    """
    Generate report files for a single (year × symbol) run.
    Returns the metrics dict for use in the summary.
    """
    if not trades:
        print(f"  [Reporter] No trades for this run — skipping report")
        return {"total_trades": 0}

    m = compute_metrics(trades, df=df)
    symbol = trades[0].symbol
    year = trades[0].year
    interval = trades[0].interval

    run_dir = results_dir / f"{year}_{symbol}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # ── trades.csv ──
    df_trades = pd.DataFrame([{
        "entry_time": t.entry_time,
        "exit_time": t.exit_time,
        "entry_price": round(t.entry_price, 4),
        "exit_price": round(t.exit_price, 4),
        "pnl_pct": round(t.pnl_pct, 4),
        "exit_reason": t.exit_reason,
        "bars_held": t.bars_held,
    } for t in trades])
    df_trades.to_csv(run_dir / "trades.csv", index=False)

    # ── Charts ──
    _plot_equity_curve(trades, run_dir / "equity_curve.png")
    _plot_monthly_returns(trades, run_dir / "monthly_returns.png")
    if df is not None:
        _plot_trades_html(trades, df, run_dir / "trades_chart.html")
        print(f"  [Reporter] Interactive chart → {run_dir}/trades_chart.html")

    # ── report.md ──
    exit_bd = "\n".join(
        f"  - {reason}: {count}" for reason, count in m["exit_breakdown"].items()
    )
    pf_display = f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞"
    bah = m.get("buy_and_hold_pct", 0)
    bah_vs = m['total_return_pct'] - bah
    bah_str = f"{bah:+.2f}% (strategy {'beats' if bah_vs > 0 else 'lags'} by {abs(bah_vs):.2f}%)"
    gross = m.get('total_return_gross_pct', m['total_return_pct'])
    fees_cost = m.get('total_fees_cost_pct', 0)
    leverage = trades[0].leverage if trades else 1
    lev_str = f"{leverage}x (FUTURES)" if leverage > 1 else "1x (Spot)"
    liquidations = sum(1 for t in trades if t.exit_reason == "LIQUIDATED")
    liq_warning = f"\n> ⚠️ **{liquidations} trades ({liquidations/len(trades)*100:.1f}%) ended in LIQUIDATION** — full collateral lost.\n" if liquidations > 0 else ""
    report = f"""# {hypo_name} — {symbol} {year} ({interval})

> {hypo_description}

---

## Results Summary
{liq_warning}
| Metric | Value |
|---|---|
| Total Trades | {m['total_trades']} |
| Leverage | {lev_str} |
| Win Rate | {m['win_rate']:.1f}% |
| Profit Factor | {pf_display} |
| Gross Return | {gross:.2f}% |
| Fees + Slippage Cost | -{fees_cost:.2f}% |
| **Net Return** | **{m['total_return_pct']:.2f}%** |
| Buy & Hold | {bah_str} |
| Avg Win | +{m['avg_win_pct']:.2f}% |
| Avg Loss | {m['avg_loss_pct']:.2f}% |
| Max Drawdown | -{m['max_drawdown_pct']:.2f}% |
| Sharpe Ratio | {m['sharpe_ratio']:.2f} |
| Avg Bars Held | {m['avg_bars_held']:.1f} |

> **Note on Sharpe**: Annualized using actual trade frequency ({m['total_trades']} trades/year),
> not calendar days. Comparable across hypotheses with similar trade counts.

## Exit Breakdown
{exit_bd}

## Files
- [trades.csv](trades.csv) — All simulated trades
- [equity_curve.png](equity_curve.png) — Cumulative return chart
- [monthly_returns.png](monthly_returns.png) — Monthly return bars
- [trades_chart.html](trades_chart.html) — Interactive price chart with all entries/exits

---
*Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}*
"""
    (run_dir / "report.md").write_text(report, encoding="utf-8")

    # Console print
    _print_run_summary(symbol, year, interval, m)

    return m


def _print_run_summary(symbol, year, interval, m):
    pf = f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞"
    bah = m.get("buy_and_hold_pct", 0)
    bah_label = f"{bah:+.2f}% B&H"
    fees_cost = m.get('total_fees_cost_pct', 0)
    gross = m.get('total_return_gross_pct', m['total_return_pct'])
    print(f"""
  ┌─ {symbol} {year} ({interval}) ──────────────────────
  │  Trades:          {m['total_trades']}
  │  Win Rate:        {m['win_rate']:.1f}%
  │  Profit Factor:   {pf}
  │  Gross Return:    {gross:.2f}%
  │  Fees+Slippage:  -{fees_cost:.2f}%
  │  Net Return:     {m['total_return_pct']:.2f}%  (vs {bah_label})
  │  Max Drawdown:    -{m['max_drawdown_pct']:.2f}%
  │  Sharpe:          {m['sharpe_ratio']:.2f}
  └─────────────────────────────────────────────""")


# ─── Summary across all runs ─────────────────────────────────────────────────

def generate_summary(
    all_metrics: dict,   # {(symbol, year): metrics_dict}
    hypo_name: str,
    results_dir: Path,
):
    """
    Generate summary.md comparing all (year × symbol) runs side by side.
    """
    rows = []
    for (symbol, year), m in sorted(all_metrics.items()):
        if m.get("total_trades", 0) == 0:
            continue
        pf = f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞"
        bah = m.get("buy_and_hold_pct", 0)
        rows.append({
            "Run": f"{year} {symbol}",
            "Trades": m["total_trades"],
            "Win%": f"{m['win_rate']:.1f}%",
            "Profit Factor": pf,
            "Return%": f"{m['total_return_pct']:.2f}%",
            "Buy&Hold%": f"{bah:+.2f}%",
            "Max DD%": f"-{m['max_drawdown_pct']:.2f}%",
            "Sharpe": f"{m['sharpe_ratio']:.2f}",
        })

    if not rows:
        return

    # Markdown table
    headers = list(rows[0].keys())
    header_row = "| " + " | ".join(headers) + " |"
    sep_row = "|" + "|".join(["---"] * len(headers)) + "|"
    data_rows = "\n".join(
        "| " + " | ".join(str(row[h]) for h in headers) + " |"
        for row in rows
    )

    summary = f"""# {hypo_name} — Cross-Run Summary

Comparison of all tested year × symbol combinations.

## Performance Table

{header_row}
{sep_row}
{data_rows}

## Interpretation Guide

| Metric | Good | Acceptable | Poor |
|---|---|---|---|
| Win Rate | >55% | 45–55% | <45% |
| Profit Factor | >1.5 | 1.0–1.5 | <1.0 |
| Sharpe Ratio | >1.5 | 0.5–1.5 | <0.5 |
| Max Drawdown | <10% | 10–25% | >25% |

---
*Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}*
"""

    (results_dir / "summary.md").write_text(summary, encoding="utf-8")
    print(f"\n  [Reporter] Summary saved → {results_dir}/summary.md")
