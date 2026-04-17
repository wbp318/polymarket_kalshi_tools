from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ReferenceQuote:
    source: str
    market_ref: str
    implied_probability: float
    fetched_at: float
    meta: Optional[dict] = None


class FeedAdapter(ABC):
    """Comparison feed for divergence detection.

    Polymarket is the market we scan. Feeds are outside references we can
    compare against — sportsbooks (Vegas), Kalshi, Binance, weather models.
    Each feed returns implied probabilities for a reference market so the
    divergence engine can compare like-for-like.
    """

    name: str

    @abstractmethod
    def quote(self, market_ref: str) -> Optional[ReferenceQuote]: ...
