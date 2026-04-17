import json
import logging
from dataclasses import dataclass
from typing import Optional

import requests

log = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
MARKET_URL_TEMPLATE = "https://polymarket.com/event/{event_slug}"


@dataclass
class MarketSnapshot:
    market_id: str
    event_id: str
    event_slug: str
    event_title: str
    question: str
    outcomes: list[str]
    outcome_prices: list[float]
    last_trade_price: Optional[float]
    volume_num: float
    liquidity_num: float
    end_date_iso: Optional[str]
    fetched_at: float

    @property
    def url(self) -> str:
        return MARKET_URL_TEMPLATE.format(event_slug=self.event_slug)

    @property
    def yes_price(self) -> Optional[float]:
        for o, p in zip(self.outcomes, self.outcome_prices):
            if o.lower() == "yes":
                return p
        return self.outcome_prices[0] if self.outcome_prices else None


class PolymarketClient:
    def __init__(self, session: Optional[requests.Session] = None, timeout: float = 10.0):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "polymarket-tools/0.1"})
        self.timeout = timeout

    def fetch_active_events(self, tag_slug: str, limit: int = 100) -> list[dict]:
        params = {
            "tag_slug": tag_slug,
            "active": "true",
            "closed": "false",
            "limit": limit,
        }
        resp = self.session.get(f"{GAMMA_BASE}/events", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def snapshot_markets(self, tag_slug: str, limit: int, now_ts: float) -> list[MarketSnapshot]:
        events = self.fetch_active_events(tag_slug=tag_slug, limit=limit)
        snapshots: list[MarketSnapshot] = []
        for ev in events:
            event_id = str(ev.get("id", ""))
            event_slug = ev.get("slug", "")
            event_title = ev.get("title", "")
            for m in ev.get("markets", []) or []:
                if m.get("closed") or not m.get("active", True):
                    continue
                snap = _market_to_snapshot(m, event_id, event_slug, event_title, now_ts)
                if snap is not None:
                    snapshots.append(snap)
        return snapshots


def _parse_json_list(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _to_float(v, default: Optional[float] = 0.0) -> Optional[float]:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _market_to_snapshot(m: dict, event_id: str, event_slug: str, event_title: str, now_ts: float) -> Optional[MarketSnapshot]:
    market_id = str(m.get("id") or m.get("conditionId") or "")
    if not market_id:
        return None
    outcomes_raw = _parse_json_list(m.get("outcomes"))
    prices_raw = _parse_json_list(m.get("outcomePrices"))
    outcomes = [str(o) for o in outcomes_raw]
    prices = [_to_float(p) for p in prices_raw]
    return MarketSnapshot(
        market_id=market_id,
        event_id=event_id,
        event_slug=event_slug,
        event_title=event_title,
        question=str(m.get("question", "")),
        outcomes=outcomes,
        outcome_prices=prices,
        last_trade_price=_to_float(m.get("lastTradePrice"), default=None),
        volume_num=_to_float(m.get("volumeNum")) or 0.0,
        liquidity_num=_to_float(m.get("liquidityNum")) or 0.0,
        end_date_iso=m.get("endDateIso"),
        fetched_at=now_ts,
    )
