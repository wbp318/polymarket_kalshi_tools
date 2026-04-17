"""Per-signal-type trade-context copy + Kalshi search-link builder.

Every Discord alert embeds a 'How to trade' field and a 'Find on Kalshi'
field so readers don't have to translate a raw Polymarket signal into an
actionable Kalshi trade on their own.
"""
from urllib.parse import quote_plus

KALSHI_SEARCH_BASE = "https://kalshi.com/markets?search="


PRICE_SWING_GUIDANCE = (
    "**What this is:** Someone moved this market meaningfully vs. 10 min ago.\n"
    "**Check:** any injury / lineup / weather / trade news in the last 15 min?\n"
    "**Play:** If the move looks real, ride it on Kalshi (same side). "
    "If it looks like a knee-jerk, fade it (opposite side). "
    "Size small — moves often retrace within the next cycle."
)

VOLUME_SPIKE_GUIDANCE = (
    "**What this is:** Fresh money landed on this market, not necessarily moving price yet.\n"
    "**Check:** did Kalshi's equivalent market tighten too? If not, you may be ahead of the crowd.\n"
    "**Play:** Take the side the new volume implies (check YES price vs. 30s ago). "
    "Compare Kalshi pricing — if it's stale vs. Polymarket, that's the arb."
)

NEW_MARKET_GUIDANCE = (
    "**What this is:** Polymarket just listed a new contract in this tag.\n"
    "**Check:** does Kalshi have an equivalent? New markets often have wide spreads on both.\n"
    "**Play:** If Kalshi doesn't list it yet, just monitor. "
    "If both list it at different prices, that's a cross-market arb — verify liquidity first."
)

GUIDANCE_BY_TYPE = {
    "price_swing": PRICE_SWING_GUIDANCE,
    "volume_spike": VOLUME_SPIKE_GUIDANCE,
    "new_market": NEW_MARKET_GUIDANCE,
}

DISCLAIMER = "Not advice — a starting point. Verify the Kalshi market exists and has liquidity before trading."


def kalshi_search_url(question: str, event_title: str = "") -> str:
    candidate = event_title.strip() if event_title else ""
    if not candidate or len(candidate) > 70:
        candidate = question.strip()
    if len(candidate) > 100:
        candidate = candidate[:100]
    return KALSHI_SEARCH_BASE + quote_plus(candidate)


def guidance_for(signal_type: str) -> str:
    return GUIDANCE_BY_TYPE.get(signal_type, "Signal detected — compare against Kalshi and verify before acting.")
