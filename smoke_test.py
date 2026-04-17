"""One-off smoke test. Does not touch Discord.
Verifies: imports, Polymarket fetch, storage, and signal detection math.
Deletes its own test DB on success.
"""
import logging
import os
import time
from pathlib import Path

from core.polymarket_client import PolymarketClient, MarketSnapshot
from core.storage import Storage, PriorSnapshot
from scanner.signals import (
    detect_new_market,
    detect_price_swing,
    detect_volume_spike,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("smoke")

DB_PATH = "smoke.db"


def test_polymarket_fetch():
    client = PolymarketClient()
    snaps = client.snapshot_markets(tag_slug="mlb", limit=5, now_ts=time.time())
    assert len(snaps) > 0, "no MLB markets returned"
    s = snaps[0]
    log.info("fetched %d markets. First: %s | YES=%s | vol=%s",
             len(snaps), s.question[:70], s.yes_price, s.volume_num)
    assert s.market_id
    assert s.question
    return snaps


def test_storage_roundtrip(snaps):
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    storage = Storage(DB_PATH)
    for s in snaps:
        storage.record_snapshot(s)
    assert len(storage.known_market_ids()) == len({s.market_id for s in snaps})
    prior = storage.latest_prior(snaps[0].market_id, before_ts=time.time() + 1)
    assert prior is not None
    log.info("storage roundtrip ok (wrote %d snapshots)", len(snaps))
    storage.close()


def test_signal_logic():
    now = time.time()
    fake_market = MarketSnapshot(
        market_id="test-1",
        event_id="evt-1",
        event_slug="fake-slug",
        event_title="Fake event",
        question="Will the test pass?",
        outcomes=["Yes", "No"],
        outcome_prices=[0.70, 0.30],
        last_trade_price=0.70,
        volume_num=50000.0,
        liquidity_num=10000.0,
        end_date_iso=None,
        fetched_at=now,
    )
    prior = PriorSnapshot(
        fetched_at=now - 60,
        yes_price=0.55,
        last_trade=0.55,
        volume_num=40000.0,
        liquidity_num=10000.0,
    )
    swing = detect_price_swing(fake_market, prior, min_probability_change=0.05)
    assert swing is not None, "expected price swing 55%→70%"
    log.info("price_swing: %s", swing.summary)

    vol = detect_volume_spike(fake_market, prior, min_dollar_increase=5000, min_ratio=1.1)
    assert vol is not None, "expected $10k volume spike"
    log.info("volume_spike: %s", vol.summary)

    new_sig = detect_new_market(fake_market, known_ids={"other-id"})
    assert new_sig is not None
    log.info("new_market: %s", new_sig.summary)

    no_signal = detect_price_swing(fake_market, prior, min_probability_change=0.50)
    assert no_signal is None


def main():
    log.info("--- test_polymarket_fetch ---")
    snaps = test_polymarket_fetch()
    log.info("--- test_storage_roundtrip ---")
    test_storage_roundtrip(snaps)
    log.info("--- test_signal_logic ---")
    test_signal_logic()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    log.info("ALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
