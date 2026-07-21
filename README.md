# StockTrader — Multi-Agent Signal Disagreement

Three isolated LLM strategy agents — a **Momentum Trader**, a **Value Contrarian**, and a **Volatility Averse** analyst — read the *identical* market-data snapshot for a stock and each return an independent **BUY / HOLD / SELL** call with a confidence score and a numbers-backed justification. A fourth **Evaluator** agent then explains *why* they diverged, without ever picking a winner. Agreement itself is computed in plain Python, not asked of a model. Built on the Anthropic API with `asyncio` fan-out and no agent framework.

## The question

Ensembles of AI advisors are increasingly pointed at judgment calls — should we buy, hold, hedge, escalate — where the tempting design is to average the models into one confident answer. That instinct destroys the most useful thing an ensemble produces: *legible disagreement*. The interesting question is not "can agents analyze a stock?" but **"when several agents look at the same data and disagree, is the disagreement meaningful signal you can trace back to specific inputs — or just noise dressed up as consensus?"**

This project makes disagreement a first-class, auditable output by separating three things:

- **Isolation.** The three strategy agents run in parallel on one shared market-data dict and never see each other's output (`asyncio.gather` in `src/orchestration.py`). So when they disagree, it is genuine divergence, not one agent anchoring on another.
- **Attribution by construction.** Each agent carries an explicit, *ranked* data-priority hierarchy and an explicit **ignore list** in its system prompt (`prompts/strategy_*.txt`). The Momentum Trader weights moving averages and trend and is told to ignore 52-week distance and drawdowns; the Value Contrarian weights distance-from-highs, RSI, and drawdowns and is told to ignore moving-average crossovers. They are, by design, reading different columns of the same table — so any disagreement is attributable to *which* numbers each one was instructed to trust.
- **Code-enforced agreement, LLM-authored explanation.** Whether two decisions match is a Python equality check (`agents_agree`, `agents_all_agree`), recorded independently of any model prose. The Evaluator is constrained to synthesize — explain the divergence, never recommend a winner (`prompts/evaluator.txt`).

The payoff is a structured record where the *fact* of agreement (deterministic) and the *reasoning* about it (generated) are never conflated — and where the sharpest disagreement can be traced to a single indicator.

## Architecture

A parallel fan-out pipeline: deterministic data in, three isolated agents, a neutral evaluator, structured JSON out.

![StockTrader system architecture — parallel fan-out with a convergence barrier: a non-LLM market-data component feeds one shared dict to three isolated strategy agents, whose outputs meet at a programmatic agreement check and a neutral evaluator before being written to per-ticker JSON plus a summary.](report/System%20Diagram/stocktrader_architecture.png)

- **Phase 1 — Data (no LLM).** `src/market_data.py` pulls ~1 year of OHLCV from yfinance and computes every indicator in Python: 20/50-day moving averages, 14-day RSI, 30-day and 90-day volatility (std of daily returns), 14-day ATR and ATR as a percent of price, worst single-day drop over 90 days, max drawdown, 52-week positioning, and volume trend. Zero model calls, so every number the agents reason over is reproducible.
- **Phase 2 — Analysis (parallel, isolated).** The three strategy agents receive the same dict and run concurrently via `asyncio.gather`. All use Claude Sonnet (`claude-sonnet-4-6`) at temperature 0.3. No agent sees another's output.
- **Phase 3 — Evaluation.** Agreement is computed programmatically; the Evaluator produces a three-way synthesis of the divergence.
- **Phase 4 — Output.** One JSON per ticker plus `summary.json`, each tagged with a `three_way_pattern` of `unanimous`, `two_one`, or `all_three_distinct`.

Robustness lives in `src/llm_client.py`: a three-layer JSON extractor (direct parse → fenced-block → brace matching), a retry loop (up to 3 attempts), and typed fallback dicts so a single malformed response degrades one cell rather than crashing the run.

## The three lenses

Each agent is a behavioral design, not a forecaster — the same data, deliberately weighted differently.

| Agent | Core belief | Weights most | Explicitly ignores |
|-------|-------------|--------------|--------------------|
| **Momentum Trader** | "The trend is your friend." | Price vs. 20/50-day MAs, trend strength, volume confirmation, RSI as a momentum gauge | Distance from 52-week high, drawdowns, volatility |
| **Value Contrarian** | "Markets overreact — buy fear, sell greed." | Distance from 52-week extremes, RSI as overbought/oversold, drawdown magnitude | Moving-average crossovers, volume trend, win/loss-day ratio |
| **Volatility Averse** | "Survive first — prefer calm tape." | 30/90-day volatility, ATR as % of price, worst single-day drop, max drawdown | Trend-vs-contrarian framing as a primary driver |

## Quickstart

Requires Python 3.10+ and an Anthropic API key.

```bash
git clone <repo-url> && cd stocktrader
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Provide your key (loaded from .env at the project root):
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

python -m src.main
```

The run analyzes six tickers (`NVDA`, `TSLA`, `JNJ`, `INTC`, `GME`, `JPM`) and writes results to `outputs/`. Pre-generated JSON from a prior run is committed there, so the results below can be read without an API key; re-running refreshes them.

Each per-ticker file carries `strategy_a`, `strategy_b`, `strategy_c` (decision, confidence, justification), the `evaluator` synthesis with the two programmatic agreement flags, a `market_data_summary`, and the `three_way_pattern`. `summary.json` rolls up the agreement counts across all six.

## What one run showed

From the committed run (2026-04-12), across the six tickers: Momentum vs. Contrarian **agreed on 2, disagreed on 4**, and **all three agents agreed exactly once** (GME, a unanimous HOLD). The structure of the disagreement is the point:

| Ticker | Momentum | Contrarian | Vol. Averse | Pattern |
|--------|----------|------------|-------------|---------|
| NVDA | BUY | HOLD | SELL | all three distinct |
| TSLA | SELL | BUY | SELL | two-one (the only opposite-action pair) |
| JNJ | HOLD | HOLD | BUY | two-one |
| INTC | HOLD | SELL | SELL | two-one |
| GME | HOLD | HOLD | HOLD | unanimous |
| JPM | HOLD | SELL | HOLD | two-one |

The finding worth surfacing: **RSI is the mechanical fulcrum of nearly every Momentum-vs-Contrarian split.** The same reading is read through opposite lenses — on INTC an RSI of 80.35 is "overbought exhaustion" to the Momentum agent and "peak euphoria to sell" to the Contrarian; on TSLA an RSI of ~42 is "sustained selling pressure" versus "approaching an oversold opportunity." Disagreement isn't random; it traces to one indicator both agents hold but interpret inversely — exactly the attribution the architecture was built to expose. Full justifications and the Evaluator's per-ticker analysis are in `outputs/`, with the extended write-up in `report/report-3.pdf`.

## Key design decisions

- **Agreement is a code check, not a model opinion.** `A == B` is Python; the Evaluator never gets to decide whether the agents agreed, only to explain why they didn't.
- **The evaluator is barred from picking a winner.** Its prompt constrains it to neutral synthesis, so the system surfaces the trade-off rather than laundering one lens into a recommendation.
- **Divergence is engineered, then made legible.** Ranked priority hierarchies plus explicit ignore lists mean each agent's behavior maps to named inputs — the disagreement is attributable by construction, not rationalized after the fact.
- **Determinism where it belongs.** All indicators are computed in Python from raw OHLCV; the model reasons over fixed numbers, so a result is reproducible and every cited figure is checkable.
- **Plain orchestration.** `asyncio` fan-out, no LangChain / CrewAI / LangGraph — the control flow is readable end to end.

## Limitations

- **The Momentum agent's RSI ceiling can override its own strongest signal.** On INTC — a 52-week high, price ~29.5% above its 20-day MA, 20 of 30 positive days, rising volume, +53.8% over 90 days — it still issued HOLD, because RSI at 80.35 sat above the prompt's overbought band. The safety rail is behaving as written, but it makes a momentum agent unable to act on exactly the parabolic move its philosophy should chase. Treating that band as a confidence discount rather than a hard gate is the documented fix.
- **The evaluator occasionally breaks neutrality.** On a couple of tickers it described the Contrarian as "more internally consistent" — normative language its role forbids. Recorded as a limitation rather than edited out of the outputs.
- **Minor persona leakage.** On JPM the Contrarian referenced distance from the 20-day MA, an indicator its ignore list tells it to discount — a prompt-compliance slip, not a crash.
- **Agreement is measured on the discrete decision only** (BUY/HOLD/SELL), not on confidence or reasoning quality; two agents can "agree" for unrelated reasons.
- **This is an analysis harness, not investment advice.** Outputs are LLM-generated over a single snapshot; model non-determinism and the chosen date both shape the results.

## Repository layout

| Path | Role |
|------|------|
| `src/main.py`, `src/orchestration.py` | Entry point and the fan-out pipeline (per-stock analysis + summary) |
| `src/market_data.py` | Deterministic, non-LLM indicator computation from yfinance OHLCV |
| `src/strategies.py`, `src/evaluator.py` | The three strategy agents and the neutral evaluator |
| `src/llm_client.py` | Anthropic Messages API wrapper: retries, three-layer JSON extraction, fallbacks |
| `src/config.py` | Tickers, model id, temperature, retry and history constants |
| `prompts/` | System prompts — philosophy, ranked priorities, ignore lists (`strategy_a/b/c.txt`, `evaluator.txt`) |
| `outputs/` | Committed run: per-ticker JSON + `summary.json` |
| `Agent and Multi-Agent System Canvases/` | Specification, architecture, and per-agent design canvases (HTML) |
| `report/` | Comparative analysis write-up (`report-3.pdf`) and the architecture diagram |

## Author

Asli Gulcur.
