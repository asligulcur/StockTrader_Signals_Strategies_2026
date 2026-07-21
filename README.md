# StockTrader: Multi-Agent Stock Analysis System

Three LLM-powered strategy agents — **Momentum Trader**, **Value Contrarian**, and **Volatility Averse** (course Strategy Menu; **Volatility Averse** implements the **bonus: third strategy agent**) — analyze the same real stock data (via [yfinance](https://github.com/ranaroussi/yfinance)) and produce independent **BUY / HOLD / SELL** recommendations with confidence and justifications. An **Evaluator** agent synthesizes **three-way** agreement and disagreement. The core assignment contrasts two strategies; the third is optional and documented in the report.

## Strategies

- **Momentum Trader** — trend-following: moving averages, volume, short-term momentum.
- **Value Contrarian** — mean-reversion: 52-week positioning, RSI, drawdowns.
- **Volatility Averse** — path risk: std dev of daily returns (30d/90d), ATR (% of price), worst single-day drop (90d), max drawdown; de-emphasizes trend vs. contrarian framing.

## Tech stack

- **Python 3.10+**
- **yfinance** — market data only (OHLCV; ATR and volatility metrics computed in Python)
- **Anthropic API** — **Claude Sonnet** (`claude-sonnet-4-6` by default; override in `src/config.py` if needed)
- **Plain Python** — `asyncio` orchestration; no LangChain / CrewAI / LangGraph

## Setup

```bash
cd stocktrader
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY from https://console.anthropic.com
```

## Run

From the **`stocktrader/`** directory (this folder):

```bash
python -m src.main
```

Outputs are written to `outputs/` — one JSON per ticker (`NVDA`, `TSLA`, `JNJ`, `INTC`, `GME`, `JPM`) plus `summary.json`. Each per-ticker file includes `strategy_a`, `strategy_b`, `strategy_c`, `evaluator` (`agents_agree` = Momentum vs Contrarian; `agents_all_agree` = all three match), and `three_way_pattern` (`unanimous` | `two_one` | `all_three_distinct`).

Pre-generated JSON files may be committed in `outputs/` so graders can review results without an API key; re-run the command to refresh them.

## Stock selection (rationale)

| Ticker | Role |
|--------|------|
| **NVDA** | Strong momentum / uptrend; tests trend vs “near highs” |
| **TSLA** | Volatility; mixed signals |
| **JNJ** | Stable large-cap; possible agreement |
| **INTC** | Legacy tech / recovery name; on a given day the tape may read as downtrend, recovery, or parabolic—check `outputs/INTC.json` for the snapshot you report |
| **GME** | Meme / high retail attention; sharp swings vs. tech-heavy set |
| **JPM** | Large bank; rate & credit cycle exposure vs. semis / consumer |

## Project layout

```
stocktrader/
├── README.md
├── requirements.txt
├── .env.example
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── market_data.py
│   ├── strategies.py
│   ├── evaluator.py
│   ├── orchestration.py
│   └── llm_client.py
├── prompts/
│   ├── strategy_a.txt
│   ├── strategy_b.txt
│   ├── strategy_c.txt
│   └── evaluator.txt
├── outputs/
├── Agent and Multi-Agent System Canvases/
│   └── (HTML canvases — specification, architecture, agents 1–5)
└── report/
    ├── report-3.pdf              # comparative analysis report (PDF); GenAI / AI use documented in Appendix A
    └── System Diagram/
        └── stocktrader_architecture.svg
```

*(If your course asks for a literal `report.pdf` filename, rename or export the PDF to `report/report.pdf`.)*

## Assignment artifacts (documentation)

- **HTML canvases** (spec + architecture + per-agent): [`Agent and Multi-Agent System Canvases/`](Agent%20and%20Multi-Agent%20System%20Canvases/) — includes [`AgentCanvas_5_VolatilityAverse.html`](Agent%20and%20Multi-Agent%20System%20Canvases/AgentCanvas_5_VolatilityAverse.html) (bonus third agent).
- **Comparative analysis PDF:** [`report/report-3.pdf`](report/report-3.pdf) — includes **Appendix A: AI / GenAI use** (tools, prompts, what was revised or rejected, output excerpts), per course requirements.
- **System architecture diagram:** [`report/System Diagram/stocktrader_architecture.svg`](report/System%20Diagram/stocktrader_architecture.svg) (vector; export to PNG if your PDF toolchain needs a raster).
- **Written report (draft, Markdown):** optional source under [`../Report/`](../Report/) (e.g. `report_v2.md`).

## Course

This project implements **CO (Coding) 2 — Building StockTrader** (Agentic Technologies), including optional **bonus: third strategy agent** (Volatility Averse from the Strategy Menu).
