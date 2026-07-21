"""
StockTrader: Multi-Agent Stock Analysis System
Usage: python -m src.main
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from src.config import TICKERS
from src.orchestration import run_all_stocks

# Project root = stocktrader/ (parent of src/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    # Explicit path so .env loads even if cwd is not stocktrader/
    # override=True: shell/IDE may set ANTHROPIC_API_KEY empty; .env should still win
    load_dotenv(_PROJECT_ROOT / ".env", override=True)

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print(
            "ERROR: ANTHROPIC_API_KEY is missing or empty.\n"
            "  In stocktrader/.env put: ANTHROPIC_API_KEY=sk-ant-...\n"
            "  Save the file (Cmd+S), then run again. Unsaved editor buffers are not read."
        )
        return

    os.makedirs("outputs", exist_ok=True)

    print("=" * 60)
    print("StockTrader: Momentum vs Value Contrarian vs Volatility Averse")
    print("=" * 60)

    results = asyncio.run(run_all_stocks(TICKERS))

    print("\n" + "=" * 60)
    print("COMPLETE. Results saved to outputs/")
    print("=" * 60)

    for r in results:
        agree_ab = "A/B agree" if r["evaluator"]["agents_agree"] else "A/B split"
        all3 = r["evaluator"].get("agents_all_agree", False)
        all_str = " | all 3 match" if all3 else ""
        print(
            f"  {r['ticker']}: {r['strategy_a']['decision']} / "
            f"{r['strategy_b']['decision']} / {r['strategy_c']['decision']} "
            f"— {agree_ab}{all_str}"
        )


if __name__ == "__main__":
    main()
