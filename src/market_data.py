"""Fetch yfinance data and compute indicators. No LLM calls."""

from __future__ import annotations

import math
from datetime import datetime

import pandas as pd
import yfinance as yf


def to_native(val):
    """Convert numpy types to native Python for JSON serialization."""
    if hasattr(val, "item"):
        return val.item()
    return val


def _round4(x: float) -> float:
    return round(float(x), 4)


def _compute_rsi_14(closes) -> float:
    """14-period RSI from close series (simple moving average of gains/losses)."""
    if len(closes) < 15:
        return 50.0
    deltas = closes.diff()
    gains = deltas.clip(lower=0.0)
    losses = (-deltas.clip(upper=0.0))
    avg_gain = gains.rolling(window=14, min_periods=14).mean()
    avg_loss = losses.rolling(window=14, min_periods=14).mean()
    g = to_native(avg_gain.iloc[-1])
    l = to_native(avg_loss.iloc[-1])
    if l == 0 and g == 0:
        return 50.0
    if l == 0:
        return 100.0
    rs = g / l
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return _round4(rsi)


def get_market_data(ticker: str) -> dict:
    """Fetch OHLCV and compute all indicators required by strategy agents."""
    t = yf.Ticker(ticker)
    # Enough calendar history for 90+ trading days and 52-week window
    hist = t.history(period="1y", auto_adjust=True)
    if hist is None or len(hist) < 90:
        hist = t.history(period="2y", auto_adjust=True)
    if hist is None or len(hist) < 90:
        raise ValueError(f"Insufficient yfinance history for {ticker}: need at least 90 trading days")

    hist = hist.dropna(how="any")
    if len(hist) < 90:
        raise ValueError(f"Insufficient clean rows for {ticker} after dropna")

    close = hist["Close"]
    vol = hist["Volume"]

    last_idx = -1
    current_price = float(to_native(close.iloc[last_idx]))

    # Trading-day offsets (current = last row)
    price_30d_ago = float(to_native(close.iloc[-31])) if len(close) >= 31 else float(to_native(close.iloc[0]))
    price_90d_ago = float(to_native(close.iloc[-91])) if len(close) >= 91 else float(to_native(close.iloc[0]))

    pct_change_30d = (current_price / price_30d_ago - 1.0) * 100.0 if price_30d_ago else 0.0
    pct_change_90d = (current_price / price_90d_ago - 1.0) * 100.0 if price_90d_ago else 0.0

    ma20 = float(to_native(close.iloc[-20:].mean()))
    ma50 = float(to_native(close.iloc[-50:].mean())) if len(close) >= 50 else float(to_native(close.mean()))

    price_vs_20d_ma = (current_price / ma20 - 1.0) * 100.0 if ma20 else 0.0
    price_vs_50d_ma = (current_price / ma50 - 1.0) * 100.0 if ma50 else 0.0

    avg_daily_volume_20d = int(round(to_native(vol.iloc[-20:].mean())))

    if len(vol) >= 20:
        recent_10 = float(to_native(vol.iloc[-10:].mean()))
        prior_10 = float(to_native(vol.iloc[-20:-10].mean()))
        if prior_10 <= 0:
            volume_trend = "stable"
        else:
            ratio = recent_10 / prior_10
            if ratio > 1.05:
                volume_trend = "increasing"
            elif ratio < 0.95:
                volume_trend = "decreasing"
            else:
                volume_trend = "stable"
    else:
        volume_trend = "stable"

    daily_pct = close.pct_change() * 100.0
    daily_returns_30d = [_round4(float(to_native(x))) for x in daily_pct.iloc[-30:].tolist()]
    pos = sum(1 for x in daily_returns_30d if x > 0)
    neg = sum(1 for x in daily_returns_30d if x < 0)

    # 52-week high/low from last 252 trading days if available
    window_52 = close.iloc[-252:] if len(close) >= 252 else close
    w52_high = float(to_native(window_52.max()))
    w52_low = float(to_native(window_52.min()))
    pct_from_52w_high = (current_price / w52_high - 1.0) * 100.0 if w52_high else 0.0
    pct_from_52w_low = (current_price / w52_low - 1.0) * 100.0 if w52_low else 0.0

    rsi_14 = _compute_rsi_14(close)

    last_90 = close.iloc[-90:]
    cummax = last_90.cummax()
    dd_series = (last_90 / cummax - 1.0) * 100.0
    max_drawdown_90d = float(to_native(dd_series.min()))

    recent_drawdown_5d = 0.0
    if len(close) >= 6:
        p5 = float(to_native(close.iloc[-6]))
        recent_drawdown_5d = (current_price / p5 - 1.0) * 100.0

    last_30_ret = daily_pct.iloc[-30:]
    volatility_30d = float(to_native(last_30_ret.std()))
    if math.isnan(volatility_30d):
        volatility_30d = 0.0

    last_90_ret = daily_pct.iloc[-90:]
    max_single_day_drop_90d = float(to_native(last_90_ret.min()))
    if math.isnan(max_single_day_drop_90d):
        max_single_day_drop_90d = 0.0

    volatility_90d = float(to_native(last_90_ret.std()))
    if math.isnan(volatility_90d):
        volatility_90d = 0.0

    # Average True Range (14) — for the Volatility Averse strategy
    high = hist["High"].astype(float)
    low = hist["Low"].astype(float)
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_window = true_range.iloc[-14:] if len(true_range) >= 14 else true_range
    atr_14 = float(to_native(atr_window.mean()))
    if math.isnan(atr_14):
        atr_14 = 0.0
    atr_pct_of_price = (atr_14 / current_price * 100.0) if current_price else 0.0

    avg_daily_return_30d = float(to_native(last_30_ret.mean()))
    if math.isnan(avg_daily_return_30d):
        avg_daily_return_30d = 0.0

    fetch_ts = hist.index[-1]
    if hasattr(fetch_ts, "date"):
        fetch_date = fetch_ts.date().isoformat()
    else:
        fetch_date = datetime.utcnow().date().isoformat()

    out = {
        "ticker": ticker,
        "fetch_date": fetch_date,
        "current_price": _round4(current_price),
        "price_30d_ago": _round4(price_30d_ago),
        "price_90d_ago": _round4(price_90d_ago),
        "pct_change_30d": _round4(pct_change_30d),
        "pct_change_90d": _round4(pct_change_90d),
        "moving_avg_20d": _round4(ma20),
        "moving_avg_50d": _round4(ma50),
        "price_vs_20d_ma": _round4(price_vs_20d_ma),
        "price_vs_50d_ma": _round4(price_vs_50d_ma),
        "avg_daily_volume_20d": avg_daily_volume_20d,
        "volume_trend": volume_trend,
        "daily_returns_30d": daily_returns_30d,
        "positive_days_30d": int(pos),
        "negative_days_30d": int(neg),
        "52_week_high": _round4(w52_high),
        "52_week_low": _round4(w52_low),
        "pct_from_52w_high": _round4(pct_from_52w_high),
        "pct_from_52w_low": _round4(pct_from_52w_low),
        "rsi_14": _round4(rsi_14),
        "max_drawdown_90d": _round4(max_drawdown_90d),
        "recent_drawdown_5d": _round4(recent_drawdown_5d),
        "volatility_30d": _round4(volatility_30d),
        "volatility_90d": _round4(volatility_90d),
        "atr_14": _round4(atr_14),
        "atr_pct_of_price": _round4(atr_pct_of_price),
        "max_single_day_drop_90d": _round4(max_single_day_drop_90d),
        "avg_daily_return_30d": _round4(avg_daily_return_30d),
    }
    return out
