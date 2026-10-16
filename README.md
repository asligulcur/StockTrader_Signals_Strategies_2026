# StockTrader — Multi-Agent Signal Disagreement

Three isolated LLM strategy agents — a **Momentum Trader**, a **Value Contrarian**, and a **Volatility Averse** analyst — analyze the same market-data snapshot for a stock and each return an independent **BUY / HOLD / SELL** call with a confidence score and a numbers-backed justification. A fourth **Evaluator** agent then explains *why* they diverged, without ever picking a winner. Agreement itself is computed in plain Python, not asked of a model. Built on the Anthropic API with `asyncio` fan-out and no agent framework.

*Built solo for CMU Heinz College's Agentic Technologies (April 2026), with AI coding assistance.*

**Result:** in a six-stock run (April 12, 2026), all three agents agreed on only one stock. They mostly read the numbers the same way and split on what to do about them, because each prompt sets different cut-offs (for example, Momentum avoids buying above RSI 75; the Contrarian sells above 70).

## The question

Ensembles of AI advisors are increasingly pointed at judgment calls — should we buy, hold, hedge, escalate — where the tempting design is to average the models into one confident answer. That instinct destroys the most useful thing an ensemble produces: *legible disagreement*. This project asks: **when several agents look at the same data and disagree, can the disagreement be traced back to specific inputs, or is it just noise?**

This project makes disagreement an auditable output by separating three things:

- **Isolation.** The three strategy agents run in parallel on one shared market-data dict and never see each other's output (`asyncio.gather` in `src/orchestration.py`). So when they disagree, it is genuine divergence, not one agent anchoring on another.
- **Attribution by construction.** Each agent carries an explicit, *ranked* data-priority hierarchy and an explicit **ignore list** in its system prompt (`prompts/strategy_*.txt`). The Momentum Trader weights moving averages and trend and is told to ignore 52-week distance and drawdowns; the Value Contrarian weights distance-from-highs, RSI, and drawdowns and is told to ignore moving-average crossovers. They are, by design, reading different columns of the same table — so any disagreement is attributable to *which* numbers each one was instructed to trust.
- **Code-enforced agreement, LLM-authored explanation.** Whether two decisions match is a Python equality check (`agents_agree`, `agents_all_agree`), recorded independently of any model prose. The Evaluator is constrained to synthesize — explain the divergence, never recommend a winner (`prompts/evaluator.txt`).

The result is a structured record that keeps the *fact* of agreement (deterministic) separate from the *reasoning* about it (generated), and traces each disagreement to the specific rules each agent was given.

## Architecture

A parallel fan-out pipeline: deterministic data in, three isolated agents, a neutral evaluator, structured JSON out.

![StockTrader system architecture — parallel fan-out with a convergence barrier: a non-LLM market-data component feeds one shared dict to three isolated strategy agents, whose outputs meet at a programmatic agreement check and a neutral evaluator before being written to per-ticker JSON plus a summary.](report/System%20Diagram/stocktrader_architecture.png)

- **Phase 1 — Data (no LLM).** `src/market_data.py` pulls ~1 year of OHLCV from yfinance and computes every indicator in Python: 20/50-day moving averages, 14-day RSI (simple-average version, so values can differ slightly from charting sites), 30-day and 90-day volatility (std of daily returns), 14-day ATR and ATR as a percent of price, worst single-day drop over 90 days, max drawdown, 52-week positioning, and volume trend. Zero model calls: every number the agents see is computed, not generated.
- **Phase 2 — Analysis (parallel, isolated).** The three strategy agents receive the same dict and run concurrently via `asyncio.gather`. Momentum and Contrarian see the same figures; the Volatility Averse agent sees a volatility-focused set that adds 90-day volatility and ATR. All use Claude Sonnet (`claude-sonnet-4-6`) at temperature 0.3. No agent sees another's output.
- **Phase 3 — Evaluation.** Agreement is computed programmatically; the Evaluator then explains the pattern: why all three agreed, which two aligned and why, or what anchored each of three different calls.
- **Phase 4 — Output.** One JSON per ticker plus `summary.json`, each tagged with a `three_way_pattern` of `unanimous`, `two_one`, or `all_three_distinct`.

Robustness lives in `src/llm_client.py`: a three-layer JSON extractor (direct parse → fenced-block → brace matching), a retry loop (up to 3 attempts), and typed fallback dicts so a single malformed response degrades one cell rather than crashing the run. (A yfinance data failure still stops the run.)

## The three lenses

Each agent is a behavioral design, not a forecaster — the same data, deliberately weighted differently.

| Agent | Core belief | Weights most | Explicitly ignores |
|-------|-------------|--------------|--------------------|
| **Momentum Trader** | "The trend is your friend." | Price vs. 20/50-day MAs, trend strength, volume confirmation, RSI as a momentum gauge | Distance from 52-week high, drawdowns, volatility |
| **Value Contrarian** | "Markets overreact — buy fear, sell greed." | Distance from 52-week extremes, RSI as overbought/oversold, drawdown magnitude | Moving-average crossovers, volume trend, win/loss-day ratio |
| **Volatility Averse** | "Survive first, profit second." | 30/90-day volatility, ATR as % of price, worst single-day drop, max drawdown | Moving averages, 52-week distance, RSI on its own |

## Quickstart

Requires Python 3.10+ and an Anthropic API key.

```bash
git clone https://github.com/asligulcur/StockTrader_Signals_Strategies_2026.git && cd StockTrader_Signals_Strategies_2026
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

![Decision matrix — six stocks (rows) by three strategy agents (columns), each cell colored by BUY/HOLD/SELL with the agent's confidence beneath, and a right-hand column labeling each row's agreement pattern (three-way split, 2–1, or unanimous). Momentum vs Contrarian agree on 2 and split on 4; all three agree only on GME.](report/decision_matrix.png)

| Ticker | Momentum | Contrarian | Vol. Averse | Pattern |
|--------|----------|------------|-------------|---------|
| NVDA | BUY | HOLD | SELL | all three distinct |
| TSLA | SELL | BUY | SELL | two-one (the only BUY vs SELL split between Momentum and Contrarian) |
| JNJ | HOLD | HOLD | BUY | two-one |
| INTC | HOLD | SELL | SELL | two-one |
| GME | HOLD | HOLD | HOLD | unanimous |
| JPM | HOLD | SELL | HOLD | two-one |

*RSI (Relative Strength Index) is a 0–100 score of how strongly a stock's price has moved up or down over the last 14 days. Traders commonly read above 70 as "overbought" (it may be due to fall back) and below 30 as "oversold." Each agent's prompt sets its own cut-offs: Momentum avoids buying above 75; the Contrarian sells above 70 and prefers to buy below 35.*

The finding worth surfacing: **the agents mostly agreed on what the numbers said; they disagreed on what to do about them.** On INTC (RSI 80.35) both called the stock overbought: the Momentum agent saw "overbought exhaustion, well above my 75 threshold" and held, while the Contrarian saw RSI "deeply overbought, well above my 70 threshold" and sold. JPM (RSI 73.69) split the same way, because 73.69 falls between those two thresholds. On TSLA the split came from a different input: the Contrarian bought because the stock was 28.77% below its 52-week high. NVDA is the one case where the same reading was interpreted differently: RSI 68.17 was "right in the sweet spot" for Momentum and "approaching overbought territory" for the Contrarian. The disagreement traces to the thresholds and priorities written into each agent's prompt, exactly the attribution the architecture was built to expose. Full justifications and the Evaluator's per-ticker analysis are in `outputs/`, with the extended write-up in `report/report.pdf`.

## Key design decisions

- **Indicators in code, judgment in the model.** All indicators are computed in Python from raw OHLCV, and 20 of them are saved with each result (`market_data_summary`), so most figures an agent cites can be checked.
- **Plain orchestration.** `asyncio` fan-out, no LangChain / CrewAI / LangGraph — the control flow is readable end to end.

## Limitations

- **The Momentum agent's RSI ceiling can override its own strongest signal.** On INTC — a 52-week high, price ~29.5% above its 20-day MA, 20 of 30 positive days, rising volume, +53.8% over 90 days — it still issued HOLD, because RSI at 80.35 sat above the prompt's overbought band. The safety rail is behaving as written, but it makes a momentum agent unable to act on exactly the parabolic move its philosophy should chase. Treating that band as a confidence discount rather than a hard gate is the documented fix.
- **The evaluator can drift from neutral, or past the data.** On INTC and JPM, an earlier version of the evaluator called the Contrarian "more internally consistent." I added an explicit ban to its prompt (`prompts/evaluator.txt`). The committed run still has one slip: on INTC it says "both MAs rising," but the agents are never given moving-average slope.
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
| `report/` | Comparative analysis write-up (`report.pdf`) and the architecture diagram |

Author: [Asli Gulcur](https://asligulcur.github.io/).
