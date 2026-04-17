import logging
import signal as pysignal
import time
from typing import Optional

from core.discord_alerter import (
    COLOR_NEW_MARKET,
    COLOR_PRICE_SWING,
    COLOR_VOLUME_SPIKE,
    DiscordAlerter,
    Embed,
)
from core.polymarket_client import MarketSnapshot, PolymarketClient
from core.storage import Storage
from scanner.signals import (
    SIGNAL_NEW_MARKET,
    SIGNAL_PRICE_SWING,
    SIGNAL_VOLUME_SPIKE,
    Signal,
    detect_new_market,
    detect_price_swing,
    detect_volume_spike,
)
from scanner.trade_guidance import DISCLAIMER, guidance_for, kalshi_search_url

log = logging.getLogger(__name__)


COLOR_BY_TYPE = {
    SIGNAL_VOLUME_SPIKE: COLOR_VOLUME_SPIKE,
    SIGNAL_PRICE_SWING: COLOR_PRICE_SWING,
    SIGNAL_NEW_MARKET: COLOR_NEW_MARKET,
}

LABEL_BY_TYPE = {
    SIGNAL_VOLUME_SPIKE: "Volume spike",
    SIGNAL_PRICE_SWING: "Price swing",
    SIGNAL_NEW_MARKET: "New market",
}


class Scanner:
    def __init__(
        self,
        client: PolymarketClient,
        storage: Storage,
        alerter: DiscordAlerter,
        config: dict,
    ):
        self.client = client
        self.storage = storage
        self.alerter = alerter
        self.config = config
        self._stop = False
        self._first_cycle = True

    def request_stop(self, *_args) -> None:
        self._stop = True
        log.info("Stop requested, finishing current cycle...")

    def run(self) -> None:
        pysignal.signal(pysignal.SIGINT, self.request_stop)
        try:
            pysignal.signal(pysignal.SIGTERM, self.request_stop)
        except (AttributeError, ValueError):
            pass

        interval = self.config["scanner"]["poll_interval_seconds"]
        tag_slug = self.config["scanner"]["tag_slug"]
        max_events = self.config["scanner"]["max_events"]

        log.info("Scanner starting: tag=%s interval=%ss max_events=%s", tag_slug, interval, max_events)
        self.alerter.send(
            Embed(
                title="Scanner online",
                description=f"Watching Polymarket tag `{tag_slug}` every {interval}s.",
                color=0x6366F1,
                footer="polymarket-tools v0.1",
            )
        )

        while not self._stop:
            cycle_start = time.time()
            try:
                self._cycle(tag_slug=tag_slug, max_events=max_events)
            except Exception:
                log.exception("Scanner cycle failed")
            self._first_cycle = False
            elapsed = time.time() - cycle_start
            sleep_for = max(0.0, interval - elapsed)
            log.info("Cycle done in %.2fs; sleeping %.2fs", elapsed, sleep_for)
            self._sleep(sleep_for)

        log.info("Scanner stopped.")

    def _sleep(self, seconds: float) -> None:
        end = time.time() + seconds
        while not self._stop and time.time() < end:
            remaining = end - time.time()
            time.sleep(max(0.0, min(0.5, remaining)))

    def _cycle(self, tag_slug: str, max_events: int) -> None:
        now_ts = time.time()
        snapshots = self.client.snapshot_markets(tag_slug=tag_slug, limit=max_events, now_ts=now_ts)
        log.info("Fetched %d markets", len(snapshots))

        known_before = self.storage.known_market_ids() if not self._first_cycle else None

        sig_cfg = self.config["signals"]
        dedup_window = sig_cfg.get("dedup_window_seconds", 600)
        lookback_seconds = sig_cfg["price_swing"]["lookback_minutes"] * 60

        for snap in snapshots:
            prior = self.storage.latest_prior(snap.market_id, before_ts=now_ts)
            baseline_cutoff = now_ts - lookback_seconds
            baseline = self.storage.prior_at_or_before(snap.market_id, cutoff_ts=baseline_cutoff)

            self.storage.record_snapshot(snap)

            if self._first_cycle:
                continue

            signals = self._detect(snap, prior, baseline, known_before or set(), sig_cfg)
            for sig in signals:
                if self.storage.recently_fired(sig.dedup_key, within_seconds=dedup_window):
                    continue
                # Record first so dedup locks in even if the webhook send fails.
                self.storage.record_signal(sig.signal_type, sig.market.market_id, sig.dedup_key, {
                    "summary": sig.summary,
                    "details": sig.details,
                    "question": sig.market.question,
                    "url": sig.market.url,
                })
                self._emit(sig)

    def _detect(self, snap: MarketSnapshot, prior, baseline, known_before: set[str], cfg: dict) -> list[Signal]:
        results: list[Signal] = []

        if cfg["new_market"]["enabled"] and known_before is not None:
            s = detect_new_market(snap, known_before)
            if s:
                results.append(s)

        if cfg["volume_spike"]["enabled"]:
            s = detect_volume_spike(
                snap,
                prior,
                min_dollar_increase=cfg["volume_spike"]["min_dollar_increase"],
                min_ratio=cfg["volume_spike"]["min_ratio"],
            )
            if s:
                results.append(s)

        if cfg["price_swing"]["enabled"]:
            s = detect_price_swing(
                snap,
                baseline,
                min_probability_change=cfg["price_swing"]["min_probability_change"],
            )
            if s:
                results.append(s)

        return results

    def _emit(self, sig: Signal) -> None:
        m = sig.market
        price_str = f"{m.yes_price:.0%}" if m.yes_price is not None else "—"
        vol_str = f"${m.volume_num:,.0f}" if m.volume_num else "—"
        liq_str = f"${m.liquidity_num:,.0f}" if m.liquidity_num else "—"

        kalshi_url = kalshi_search_url(m.question, m.event_title)
        kalshi_value = f"[Search Kalshi for this market]({kalshi_url})\n*{DISCLAIMER}*"

        fields = [
            ("YES price", price_str, True),
            ("Cumulative volume", vol_str, True),
            ("Liquidity", liq_str, True),
        ]
        if m.event_title and m.event_title != m.question:
            fields.append(("Event", m.event_title, False))
        fields.append(("How to trade", guidance_for(sig.signal_type), False))
        fields.append(("Find on Kalshi", kalshi_value, False))

        embed = Embed(
            title=f"[{LABEL_BY_TYPE.get(sig.signal_type, sig.signal_type)}] {m.question[:200]}",
            description=sig.summary,
            url=m.url,
            color=COLOR_BY_TYPE.get(sig.signal_type, 0x6366F1),
            fields=fields,
            footer="Polymarket signal • cross-reference Kalshi before trading",
        )
        self.alerter.send(embed)
        log.info("Signal %s: %s", sig.signal_type, sig.summary)
