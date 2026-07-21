"""Evaluator agent: compares three strategy outputs."""

from __future__ import annotations

import os

from src.config import MAX_RETRIES
from src.llm_client import call_llm


def load_prompt(filename: str) -> str:
    prompt_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    path = os.path.join(prompt_dir, filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


def run_evaluator(
    market_data: dict,
    strategy_a_result: dict,
    strategy_b_result: dict,
    strategy_c_result: dict,
    agents_agree_ab: bool,
    agents_all_agree: bool,
) -> dict:
    """
    Compare three strategies. agents_agree_ab = (A decision == B decision).
    agents_all_agree = (A == B == C).
    """
    system = load_prompt("evaluator.txt")
    md = market_data
    ab_str = "AGREE" if agents_agree_ab else "DISAGREE"
    all_str = "YES — all three decisions are identical" if agents_all_agree else "NO — at least one strategy differs from the others"

    sa = strategy_a_result
    sb = strategy_b_result
    sc = strategy_c_result

    user = f"""Compare THREE strategy recommendations for {md['ticker']}.

Momentum vs Contrarian: {ab_str} (pre-computed from decisions).
All three identical: {all_str}.

MARKET DATA SUMMARY FOR {md['ticker']}:
- Current Price: ${md['current_price']}
- 30-day / 90-day Change: {md['pct_change_30d']}% / {md['pct_change_90d']}%
- 20-day MA: ${md['moving_avg_20d']} | 50-day MA: ${md['moving_avg_50d']}
- RSI (14-day): {md['rsi_14']}
- 52-week High: ${md['52_week_high']} ({md['pct_from_52w_high']}% from high)
- 30d volatility (std of daily returns): {md['volatility_30d']} | 90d: {md['volatility_90d']}
- ATR (14): {md['atr_14']} ({md['atr_pct_of_price']}% of price)
- Worst single-day drop (90d): {md['max_single_day_drop_90d']}%

STRATEGY A — {sa.get('name', 'Strategy A')}:
Decision: {sa.get('decision')} (Confidence: {sa.get('confidence')}/10)
Justification: {sa.get('justification', '')}

STRATEGY B — {sb.get('name', 'Strategy B')}:
Decision: {sb.get('decision')} (Confidence: {sb.get('confidence')}/10)
Justification: {sb.get('justification', '')}

STRATEGY C — {sc.get('name', 'Strategy C')}:
Decision: {sc.get('decision')} (Confidence: {sc.get('confidence')}/10)
Justification: {sc.get('justification', '')}

Respond with ONLY a JSON object in this exact format, no other text:
{{
    "analysis": "<5 to 8 sentences>"
}}"""

    raw = call_llm(system, user, max_retries=MAX_RETRIES, response_kind="evaluator")
    analysis = raw.get("analysis", "")
    if not isinstance(analysis, str):
        analysis = str(analysis)
    if not analysis.strip():
        analysis = "Evaluator failed after retries."

    return {
        "agents_agree": agents_agree_ab,
        "agents_all_agree": agents_all_agree,
        "analysis": analysis,
    }
