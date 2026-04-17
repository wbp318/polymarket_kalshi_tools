# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Other docs in this repo

- **`README.md`** — public-facing setup, run, architecture, roadmap. Authoritative for anything user-facing.
- **`RUNNING.txt`** — start/stop walkthrough, threshold tuning, troubleshooting. Written for the human operator, not for Claude.
- **`CLAUDE_CODE_SKILLS.md`** — reference for Claude Code skills available in this environment. Not project-specific.
- **`config.example.yaml`** — authoritative config schema. `config.yaml` (gitignored) is the user's real config and won't be readable from the repo.

Project-specific Claude Code memory lives at `.claude/projects/<encoded-project-path>/memory/` in the user's home directory (outside this repo). It's auto-loaded and contains user preferences, prior feedback, and operational decisions that aren't derivable from the code.

## Commands

Shell assumed is Windows PowerShell. `source venv/Scripts/activate` is **not** a PowerShell command — use the venv's python directly (works in any shell):

```
# install deps
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# run the scanner (polls Polymarket, posts to Discord)
.\venv\Scripts\python.exe main.py

# run the smoke test (verifies fetch + storage + signal detection end-to-end)
.\venv\Scripts\python.exe smoke_test.py
```

`smoke_test.py` is the test suite. It runs all three phases (Polymarket fetch, storage roundtrip, signal-logic math) and prints `ALL SMOKE TESTS PASSED` on success. There is no pytest; individual phases inside the script are three `test_*` functions you can call from a REPL if you need isolated runs.

There is no lint or build step. Config is `config.yaml` (gitignored; copy from `config.example.yaml` and paste the Discord webhook URL).

## Architecture

The scanner is one polling loop with a pluggable-feed shape. Three invariants tie files together across the repo:

**1. `MarketSnapshot` is the unit of data.** Defined in `core/polymarket_client.py`. Every signal detector in `scanner/signals.py` takes a current `MarketSnapshot` and (usually) a `PriorSnapshot` from `core/storage.py`, and returns a `Signal` or `None`. Detectors are pure functions — no I/O, no mutation. Adding a new signal type means: a new pure `detect_*` function, a constant `SIGNAL_*` name, and registration in `Scanner._detect` in `scanner/loop.py`.

**2. `feeds/base.py::FeedAdapter` is for comparison sources, not the market being scanned.** Polymarket is hard-wired as the scan source in `PolymarketClient.snapshot_markets`. `FeedAdapter` is the future slot for Kalshi / Vegas / Binance — each of those will provide a `ReferenceQuote` we compare against a Polymarket snapshot to fire cross-market arb or lag signals. No adapter is wired in yet; `base.py` is an abstract interface waiting to be implemented.

**3. Every `Signal` must have matching entries in three registries** in `scanner/loop.py` and `scanner/trade_guidance.py`: `LABEL_BY_TYPE`, `COLOR_BY_TYPE`, and `GUIDANCE_BY_TYPE`. Missing entries silently degrade the Discord embed (generic fallback copy, default color). When adding a signal type, update all three.

### First-cycle behavior

`Scanner._first_cycle` is set to `True` on startup and `False` after the first completed cycle. While `_first_cycle` is `True`, **snapshots are recorded but no signals of any type are emitted** — the `if self._first_cycle: continue` in `Scanner._cycle` short-circuits before `_detect` runs. This is deliberate; without a prior in-memory state, new-market detection would fire on every market, and the other detectors would see stale-looking baselines.

However, *after* the first cycle completes, detectors that read from disk (`detect_price_swing` via `prior_at_or_before` with a 10-minute lookback) can find baselines in a pre-existing `scanner.db` immediately — historical data survives restarts even though the in-memory first-cycle flag resets. In practice, a restart produces meaningful price-swing alerts on cycle 2 if the DB has old-enough snapshots; volume-spike compares to the most recent prior snapshot (also from disk), so it also activates on cycle 2.

### Gamma API quirks that break if ignored

In `core/polymarket_client.py`:

- `outcomes` and `outcomePrices` come back as **JSON strings**, not arrays. `_parse_json_list` handles both shapes defensively.
- `volume24hr` is `None` on many markets — do **not** use it. Use `volumeNum` (cumulative total) and diff between polls.
- `lastTradePrice` can be `None` on markets with no recent trades.
- Event/market hierarchy: `GET /events` returns events, each containing a `markets` array. The scanner flattens to per-market snapshots; market-level `closed`/`active` filtering happens inside `PolymarketClient.snapshot_markets`, not in the query.

### Dedup

`scanner/signals.py` constructs a `dedup_key` per signal that collapses "same thing happened again." Examples:
- Volume-spike key quantizes by `volume_num / min_dollar_increase` — every threshold-sized increment fires once.
- Price-swing key quantizes by `direction + round(yes_price * 100)` — a market bouncing around within a percent-bucket doesn't re-fire.

`Scanner._cycle` checks `Storage.recently_fired(dedup_key, dedup_window_seconds)` before emitting. The default dedup window is in `config.yaml` (`signals.dedup_window_seconds`).

### Discord rate limiting

`core/discord_alerter.py` enforces a 0.35s inter-send delay and retries up to 5 times on 429 using Discord's server-provided `retry_after`. A failing webhook logs an error and returns — it does **not** raise — so one bad send doesn't kill the cycle.

## Extension points (in expected order of work)

The roadmap in `README.md` is authoritative. Short form:

1. **Kalshi feed** (`feeds/kalshi.py`, implementing `FeedAdapter`). Tap is US-based, so Kalshi is the legal execution venue; Polymarket stays read-only for signal generation. Cross-market arb signals (Polymarket ↔ Kalshi on the same contract) will be the first new signal type that uses a feed.
2. **Vegas/sportsbook feed** for lag-vs-book signals.
3. **Multi-tenant config** — `config.yaml`'s single-user shape needs to split into per-user rows (likely Postgres).
4. **Automated execution** is deliberately last and only lands after the signal log in `scanner.db` proves a real edge.

Other niches (crypto 5-minute rounds, politics, weather, econ data) reuse the same architecture: new `FeedAdapter` + new `detect_*` function + updated `tag_slug` in config.

## Things that are NOT here yet (don't assume)

- No tests beyond `smoke_test.py` — no pytest config, no CI, no unit/integration split.
- No logging to file — scanner logs to stdout only. Redirect in your shell if you need persistence.
- No auth, no multi-tenancy, no web UI. Single-user, single-webhook, single-config.
- No Kalshi API integration. `feeds/base.py` is a stub.
- Trade-guidance copy in `scanner/trade_guidance.py` is static text, not market-aware. An alert for a baseball futures market gets the same guidance as an alert for a live in-game prop — intentional for v0.
