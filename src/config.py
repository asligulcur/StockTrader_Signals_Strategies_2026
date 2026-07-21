"""Configuration: tickers, model, and constants."""

# Third strategy agent — Volatility Averse; see prompts/strategy_c.txt
TICKERS = ["NVDA", "TSLA", "JNJ", "INTC", "GME", "JPM"]

# Stock selection rationale (include as comments):
# NVDA  — strong uptrend / momentum stock. Momentum should love it, Contrarian should be cautious.
# TSLA  — volatile, big swings. Should produce sharp disagreement.
# JNJ   — stable large-cap, low volatility. Likely agreement area (both may say HOLD).
# INTC  — significant decline from highs. Contrarian sees opportunity, Momentum sees danger.
# GME   — meme / retail-driven volatility; tests agents on chaotic price action vs. tech names.
# JPM   — large U.S. bank; rate/credit cycle narrative vs. mostly tech-heavy set.

# Anthropic Claude — Sonnet (Messages API). See https://docs.anthropic.com/en/docs/about-claude/models
ANTHROPIC_MODEL = "claude-sonnet-4-6"
MAX_OUTPUT_TOKENS = 4096
TEMPERATURE = 0.3  # Low temp for consistency
MAX_RETRIES = 3
HISTORY_DAYS = 120  # Fetch 120 days to compute 90-day indicators safely
