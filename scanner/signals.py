from dataclasses import dataclass
from typing import Optional

from core.polymarket_client import MarketSnapshot
from core.storage import PriorSnapshot


SIGNAL_VOLUME_SPIKE = "volume_spike"
SIGNAL_PRICE_SWING = "price_swing"
SIGNAL_NEW_MARKET = "new_market"


@dataclass
class Signal:
    signal_type: str
    market: MarketSnapshot
    summary: str
    details: dict
    dedup_key: str


def detect_volume_spike(
    curr: MarketSnapshot,
    prior: Optional[PriorSnapshot],
    min_dollar_increase: float,
    min_ratio: float,
) -> Optional[Signal]:
    if prior is None:
        return None
    prior_vol = prior.volume_num or 0.0
    delta = curr.volume_num - prior_vol
    if delta < min_dollar_increase:
        return None
    ratio = curr.volume_num / prior_vol if prior_vol > 0 else float("inf")
    if ratio < min_ratio and prior_vol > 0:
        return None
    dedup = f"vol:{curr.market_id}:{int(curr.volume_num / max(min_dollar_increase, 1))}"
    return Signal(
        signal_type=SIGNAL_VOLUME_SPIKE,
        market=curr,
        summary=f"+${delta:,.0f} volume since last snapshot",
        details={
            "prior_volume": prior_vol,
            "current_volume": curr.volume_num,
            "delta": delta,
            "ratio": ratio,
            "elapsed_seconds": curr.fetched_at - prior.fetched_at,
        },
        dedup_key=dedup,
    )


def detect_price_swing(
    curr: MarketSnapshot,
    baseline: Optional[PriorSnapshot],
    min_probability_change: float,
) -> Optional[Signal]:
    if baseline is None or baseline.yes_price is None or curr.yes_price is None:
        return None
    delta = curr.yes_price - baseline.yes_price
    if abs(delta) < min_probability_change:
        return None
    direction = "up" if delta > 0 else "down"
    bucket = int(round(curr.yes_price * 100))
    dedup = f"swing:{curr.market_id}:{direction}:{bucket}"
    return Signal(
        signal_type=SIGNAL_PRICE_SWING,
        market=curr,
        summary=f"YES {baseline.yes_price:.0%} → {curr.yes_price:.0%} ({delta:+.1%})",
        details={
            "baseline_price": baseline.yes_price,
            "current_price": curr.yes_price,
            "delta": delta,
            "elapsed_seconds": curr.fetched_at - baseline.fetched_at,
        },
        dedup_key=dedup,
    )


def detect_new_market(curr: MarketSnapshot, known_ids: set[str]) -> Optional[Signal]:
    if curr.market_id in known_ids:
        return None
    return Signal(
        signal_type=SIGNAL_NEW_MARKET,
        market=curr,
        summary=f"New market: {curr.question}",
        details={
            "yes_price": curr.yes_price,
            "volume_num": curr.volume_num,
            "liquidity_num": curr.liquidity_num,
            "end_date": curr.end_date_iso,
        },
        dedup_key=f"new:{curr.market_id}",
    )
