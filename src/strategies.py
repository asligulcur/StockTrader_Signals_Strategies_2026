"""LLM strategy agents: Momentum, Value Contrarian, Volatility Averse."""

from __future__ import annotations

import logging
import os

from src.llm_client import call_llm

logger = logging.getLogger(__name__)


def load_prompt(filename: str) -> str:
    prompt_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    path = os.path.join(prompt_dir, filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


def format_strategy_user_prompt(market_data: dict) -> str:
    d = market_data
    return f"""Analyze the following stock data for {d['ticker']} and provide your recommendation.

MARKET DATA FOR {d['ticker']} (as of {d['fetch_date']}):
- Current Price: ${d['current_price']}
- Price 30 days ago: ${d['price_30d_ago']} (change: {d['pct_change_30d']}%)
- Price 90 days ago: ${d['price_90d_ago']} (change: {d['pct_change_90d']}%)
- 20-day Moving Average: ${d['moving_avg_20d']} (price is {d['price_vs_20d_ma']}% vs MA)
- 50-day Moving Average: ${d['moving_avg_50d']} (price is {d['price_vs_50d_ma']}% vs MA)
- 52-week High: ${d['52_week_high']} (currently {d['pct_from_52w_high']}% from high)
- 52-week Low: ${d['52_week_low']} (currently {d['pct_from_52w_low']}% from low)
- RSI (14-day): {d['rsi_14']}
- 30-day Volatility (std dev of daily returns): {d['volatility_30d']}
- Average Daily Volume (20d): {d['avg_daily_volume_20d']}
- Volume Trend: {d['volume_trend']}
- Positive days in last 30: {d['positive_days_30d']} / Negative days: {d['negative_days_30d']}
- Max drawdown (90d): {d['max_drawdown_90d']}%
- Recent 5-day price change: {d['recent_drawdown_5d']}%
- Worst single-day drop (90d): {d['max_single_day_drop_90d']}%
- Average daily return (30d): {d['avg_daily_return_30d']}%

Respond with ONLY a JSON object in this exact format, no other text:
{{
    "decision": "BUY" or "HOLD" or "SELL",
    "confidence": <integer from 1 to 10>,
    "justification": "<3 to 5 sentences explaining your reasoning. You MUST reference at least 3 specific numbers from the data above.>"
}}"""


def format_volatility_averse_user_prompt(market_data: dict) -> str:
    """User prompt emphasizing ATR and volatility metrics (assignment Strategy Menu: Volatility Averse)."""
    d = market_data
    return f"""Analyze the following stock data for {d['ticker']} as a Volatility Averse investor and provide your recommendation.

MARKET DATA FOR {d['ticker']} (as of {d['fetch_date']}):
- Current Price: ${d['current_price']}
- 30-day Volatility (std dev of daily % returns): {d['volatility_30d']}
- 90-day Volatility (std dev of daily % returns): {d['volatility_90d']}
- Average True Range (14-day ATR): {d['atr_14']} (ATR as % of price: {d['atr_pct_of_price']}%)
- Worst single-day drop (last 90 trading days): {d['max_single_day_drop_90d']}%
- Max drawdown (90d): {d['max_drawdown_90d']}%
- Recent 5-day price change: {d['recent_drawdown_5d']}%
- 30-day price change: {d['pct_change_30d']}% | 90-day: {d['pct_change_90d']}%
- RSI (14-day): {d['rsi_14']} (secondary only)

Context (do not treat as primary drivers — listed for completeness):
- 20-day MA: ${d['moving_avg_20d']} | 50-day MA: ${d['moving_avg_50d']}
- 52-week High/Low: ${d['52_week_high']} / ${d['52_week_low']}

Respond with ONLY a JSON object in this exact format, no other text:
{{
    "decision": "BUY" or "HOLD" or "SELL",
    "confidence": <integer from 1 to 10>,
    "justification": "<3 to 5 sentences. Must cite at least 3 specific numbers, prioritizing volatility, ATR, and worst single-day drop.>"
}}"""


def _normalize_strategy_result(raw: dict, name: str) -> dict:
    decision = raw.get("decision", "HOLD")
    if isinstance(decision, str):
        decision = decision.upper().strip()
    if decision not in ("BUY", "HOLD", "SELL", "ERROR"):
        logger.warning("Invalid decision %r for %s — defaulting to HOLD", decision, name)
    conf = raw.get("confidence", 5)
    try:
        conf = int(conf)
    except (TypeError, ValueError):
        logger.warning("Invalid confidence %r for %s", conf, name)
        conf = 5
    justification = raw.get("justification", "")
    if not isinstance(justification, str):
        justification = str(justification)
    if decision not in ("BUY", "HOLD", "SELL", "ERROR"):
        decision = "HOLD"
    if decision == "ERROR":
        conf = 0
    else:
        if conf < 1 or conf > 10:
            logger.warning("Confidence %s out of 1–10 for %s", conf, name)
        conf = max(1, min(10, conf))
    return {
        "name": name,
        "decision": decision,
        "confidence": conf,
        "justification": justification,
    }


def run_momentum_trader(market_data: dict) -> dict:
    """Returns strategy A output with name Momentum Trader."""
    system = load_prompt("strategy_a.txt")
    user = format_strategy_user_prompt(market_data)
    raw = call_llm(system, user, response_kind="strategy")
    raw = _normalize_strategy_result(raw, "Momentum Trader")
    raw["name"] = "Momentum Trader"
    return raw


def run_value_contrarian(market_data: dict) -> dict:
    """Returns strategy B output with name Value Contrarian."""
    system = load_prompt("strategy_b.txt")
    user = format_strategy_user_prompt(market_data)
    raw = call_llm(system, user, response_kind="strategy")
    raw = _normalize_strategy_result(raw, "Value Contrarian")
    raw["name"] = "Value Contrarian"
    return raw


def run_volatility_averse(market_data: dict) -> dict:
    """Returns strategy C output — Volatility Averse (bonus: third strategy from course menu)."""
    system = load_prompt("strategy_c.txt")
    user = format_volatility_averse_user_prompt(market_data)
    raw = call_llm(system, user, response_kind="strategy")
    raw = _normalize_strategy_result(raw, "Volatility Averse")
    raw["name"] = "Volatility Averse"
    return raw
