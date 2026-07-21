"""Pipeline orchestration: per-stock analysis and summary."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date

from src.evaluator import run_evaluator
from src.market_data import get_market_data
from src.strategies import run_momentum_trader, run_value_contrarian, run_volatility_averse


def extract_market_data_summary(market_data: dict) -> dict:
    """Curated subset saved as market_data_summary in output JSON."""
    keys = [
        "current_price",
        "price_30d_ago",
        "pct_change_30d",
        "avg_daily_volume_20d",
        "volatility_30d",
        "volatility_90d",
        "atr_14",
        "atr_pct_of_price",
        "moving_avg_20d",
        "moving_avg_50d",
        "rsi_14",
        "52_week_high",
        "52_week_low",
        "pct_from_52w_high",
        "pct_from_52w_low",
        "volume_trend",
        "pct_change_90d",
        "max_drawdown_90d",
        "recent_drawdown_5d",
        "max_single_day_drop_90d",
    ]
    return {k: market_data[k] for k in keys if k in market_data}


def _outputs_dir() -> str:
    return os.path.join(os.getcwd(), "outputs")


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _three_way_pattern(a: str, b: str, c: str) -> str:
    if a == b == c:
        return "unanimous"
    if a == b or a == c or b == c:
        return "two_one"
    return "all_three_distinct"


async def analyze_single_stock(ticker: str, index: int, total: int) -> dict:
    print(f"\n[{index}/{total}] Analyzing {ticker}...")
    print("  → Fetching market data...", end=" ", flush=True)
    market_data = get_market_data(ticker)
    print("done")

    print(
        "  → Running Momentum, Value Contrarian & Volatility Averse (parallel)...",
        flush=True,
    )
    strategy_a, strategy_b, strategy_c = await asyncio.gather(
        asyncio.to_thread(run_momentum_trader, market_data),
        asyncio.to_thread(run_value_contrarian, market_data),
        asyncio.to_thread(run_volatility_averse, market_data),
    )
    print(
        f"  → Momentum Trader... done ({strategy_a['decision']}, confidence: {strategy_a['confidence']})"
    )
    print(
        f"  → Value Contrarian... done ({strategy_b['decision']}, confidence: {strategy_b['confidence']})"
    )
    print(
        f"  → Volatility Averse... done ({strategy_c['decision']}, confidence: {strategy_c['confidence']})"
    )

    agents_agree_ab = strategy_a["decision"] == strategy_b["decision"]
    agents_all_agree = (
        strategy_a["decision"] == strategy_b["decision"] == strategy_c["decision"]
    )
    agree_ab = "AGREE (A/B)" if agents_agree_ab else "DISAGREE (A/B)"
    all_lbl = "ALL3" if agents_all_agree else "SPLIT"
    print(f"  → Running Evaluator... done ({agree_ab} | {all_lbl})")

    evaluator_result = await asyncio.to_thread(
        run_evaluator,
        market_data,
        strategy_a,
        strategy_b,
        strategy_c,
        agents_agree_ab,
        agents_all_agree,
    )

    out = {
        "ticker": ticker,
        "run_date": date.today().isoformat(),
        "market_data_summary": extract_market_data_summary(market_data),
        "strategy_a": strategy_a,
        "strategy_b": strategy_b,
        "strategy_c": strategy_c,
        "evaluator": evaluator_result,
        "three_way_pattern": _three_way_pattern(
            strategy_a["decision"], strategy_b["decision"], strategy_c["decision"]
        ),
    }

    os.makedirs(_outputs_dir(), exist_ok=True)
    out_path = os.path.join(_outputs_dir(), f"{ticker}.json")
    _write_json(out_path, out)
    print(f"  → Saved to {out_path}")
    return out


async def run_all_stocks(tickers: list[str]) -> list[dict]:
    results: list[dict] = []
    total = len(tickers)
    for i, ticker in enumerate(tickers, start=1):
        if i > 1:
            await asyncio.sleep(2)
        results.append(await analyze_single_stock(ticker, i, total))
    generate_summary(results)
    return results


def generate_summary(results: list[dict]) -> dict:
    """Write outputs/summary.json."""
    rows = []
    agreements_ab = 0
    disagreements_ab = 0
    all_three_agree_count = 0
    for r in results:
        a = r["strategy_a"]["decision"]
        b = r["strategy_b"]["decision"]
        c = r["strategy_c"]["decision"]
        agree_ab = a == b
        all3 = a == b == c
        if agree_ab:
            agreements_ab += 1
        else:
            disagreements_ab += 1
        if all3:
            all_three_agree_count += 1
        rows.append(
            {
                "ticker": r["ticker"],
                "a_decision": a,
                "b_decision": b,
                "c_decision": c,
                "agree_ab": agree_ab,
                "all_three_agree": all3,
                "three_way_pattern": r.get("three_way_pattern", ""),
            }
        )

    summary = {
        "bonus_implementation": "third_strategy_agent",
        "third_strategy": "Volatility Averse",
        "strategies": [
            "Momentum Trader",
            "Value Contrarian",
            "Volatility Averse",
        ],
        "stocks_analyzed": [r["ticker"] for r in results],
        "total_agreements_ab": agreements_ab,
        "total_disagreements_ab": disagreements_ab,
        "total_all_three_agree": all_three_agree_count,
        "results": rows,
    }
    path = os.path.join(_outputs_dir(), "summary.json")
    _write_json(path, summary)
    print(f"\n  → Wrote {path}")
    return summary
