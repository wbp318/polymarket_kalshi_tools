# polymarket-kalshi-tools

Market scanner for Polymarket prediction markets, with per-signal trade-context
and direct Kalshi search links so US users can act on the signal via a legal
venue.

Read-only — does not place trades. Posts alerts to a Discord channel of your
choice via a webhook.

## Project tree

<pre>
polymarket_kalshi_tools/
├── <a href=".gitattributes">.gitattributes</a>
├── <a href=".gitignore">.gitignore</a>
├── <a href="CLAUDE.md">CLAUDE.md</a>
├── <a href="CLAUDE_CODE_SKILLS.md">CLAUDE_CODE_SKILLS.md</a>
├── <a href="README.md">README.md</a>
├── <a href="RUNNING.txt">RUNNING.txt</a>
├── <a href="config.example.yaml">config.example.yaml</a>
├── <a href="main.py">main.py</a>
├── <a href="requirements.txt">requirements.txt</a>
├── <a href="smoke_test.py">smoke_test.py</a>
├── core/
│   ├── <a href="core/__init__.py">__init__.py</a>
│   ├── <a href="core/discord_alerter.py">discord_alerter.py</a>
│   ├── <a href="core/polymarket_client.py">polymarket_client.py</a>
│   └── <a href="core/storage.py">storage.py</a>
├── feeds/
│   ├── <a href="feeds/__init__.py">__init__.py</a>
│   └── <a href="feeds/base.py">base.py</a>
└── scanner/
    ├── <a href="scanner/__init__.py">__init__.py</a>
    ├── <a href="scanner/loop.py">loop.py</a>
    ├── <a href="scanner/signals.py">signals.py</a>
    └── <a href="scanner/trade_guidance.py">trade_guidance.py</a>
</pre>

Runtime artifacts (gitignored, not in repo): *config.yaml* (your settings + webhook URL), *scanner.db* (SQLite snapshot + signal log), *venv/* (Python environment), *notes.local.txt* (personal operator runbook).

## First-time setup

```
git clone https://github.com/wbp318/polymarket_kalshi_tools.git
cd polymarket_kalshi_tools

# create a virtualenv
python -m venv venv

# install deps (works in any shell; no activation needed)
.\venv\Scripts\python.exe -m pip install -r requirements.txt
# macOS / Linux:
# ./venv/bin/python -m pip install -r requirements.txt

# create your config from the example
copy config.example.yaml config.yaml     # PowerShell / CMD
# or: cp config.example.yaml config.yaml # bash / Git Bash / macOS / Linux

# then edit config.yaml and paste your Discord webhook URL in place of
# PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE
```

## Run

Shell-neutral (works in PowerShell, CMD, bash — no activation needed):
```
.\venv\Scripts\python.exe main.py
```

Or with activation:
- PowerShell: `.\venv\Scripts\Activate.ps1` then `python main.py`
- bash / Git Bash: `source venv/Scripts/activate` then `python main.py`

Stop with `Ctrl+C`. A *scanner.db* (SQLite, WAL mode) is created next to [main.py](main.py) and stores every snapshot + every signal fired — that's the performance log you pay for once it becomes a product.

See [RUNNING.txt](RUNNING.txt) for a detailed start/stop/troubleshooting walkthrough.

## What it alerts on

| Signal | Fires when |
|---|---|
| `new_market` | A market appears under the configured tag that we haven't seen before |
| `volume_spike` | Cumulative volume jumped by at least `min_dollar_increase` between two polls AND ratio ≥ `min_ratio` |
| `price_swing` | YES probability changed by ≥ `min_probability_change` versus the snapshot `lookback_minutes` ago |

Tune thresholds in *config.yaml* (see [config.example.yaml](config.example.yaml) for the schema). The first poll after starting is silent — we need a baseline before we can detect changes.

## What each Discord alert contains

Every fired signal posts a Discord embed with:

- **Market link** — deep-links to the Polymarket page
- **YES price / cumulative volume / liquidity** — current snapshot
- **Event** — the parent event title, if different from the market question
- **How to trade** — signal-type-specific playbook (copy lives in [scanner/trade_guidance.py](scanner/trade_guidance.py))
- **Find on Kalshi** — a search link built from the market's event title / question, so US users can cross-reference the same event on a legal venue
- **Disclaimer** — signals are starting points; verify on Kalshi/Polymarket before trading

The Discord alerter respects Discord's 5-requests-per-2-seconds per-webhook limit with a 0.35s inter-send delay, and retries up to 5 times on 429 responses using the server-provided `retry_after`. A single failing send does not kill the polling loop.

## Architecture (why it's laid out this way)

The scanned market is **Polymarket** (read-only, via the public gamma API). Kalshi is the intended US-legal **execution venue**: signals are generated from Polymarket, then each alert carries a link to the equivalent Kalshi market so a US user can act on the same event. That two-venue split runs through the whole architecture.

### Where Kalshi lives today

- [scanner/trade_guidance.py](scanner/trade_guidance.py) — builds a Kalshi search URL from each market's event title / question. This is what powers the **Find on Kalshi** field on every Discord alert. No Kalshi API call, no price comparison — just a deep-linked search.
- [feeds/base.py](feeds/base.py) — the `FeedAdapter` abstract interface. Kalshi's real integration will land as feeds/kalshi.py implementing this interface, which unlocks cross-market arb signals (Polymarket vs. Kalshi pricing on the same contract). Not wired in yet; see Roadmap.

### Module map

- [core/polymarket_client.py](core/polymarket_client.py) — only talks to Polymarket gamma API. Returns `MarketSnapshot` dataclasses.
- [core/discord_alerter.py](core/discord_alerter.py) — only talks to Discord webhooks. Handles rate limits and retries.
- [core/storage.py](core/storage.py) — SQLite; snapshot table + signal log with dedup by key + time window.
- [feeds/base.py](feeds/base.py) — `FeedAdapter` interface for future comparison feeds (Kalshi, Vegas via an odds API, Binance). Drop a new class in feeds/, wire it into the scanner, no other code changes needed.
- [scanner/signals.py](scanner/signals.py) — pure functions per signal type (`detect_volume_spike`, `detect_price_swing`, `detect_new_market`). Easy to add new ones.
- [scanner/trade_guidance.py](scanner/trade_guidance.py) — per-signal-type alert copy + Kalshi search URL builder (see "Where Kalshi lives today" above).
- [scanner/loop.py](scanner/loop.py) — the polling loop, dedup logic, and embed emission.
- [main.py](main.py) — entry point: loads config, wires components, runs the scanner.
- [smoke_test.py](smoke_test.py) — offline verification of Polymarket fetch, storage roundtrip, and signal detection math. Run with `.\venv\Scripts\python.exe smoke_test.py` before your first real run to confirm the stack works end-to-end on your machine.

## Roadmap

- [x] **Phase 1 — Polymarket MLB scanner → Discord alerts with trade context.** This repo today.
- [ ] **Phase 2 — Kalshi feed.** Cross-market arb signals when Polymarket and Kalshi price the same contract differently.
- [ ] **Phase 3 — Vegas / sportsbook feed.** Lag-vs-book signals when sportsbook odds move before the prediction markets catch up.
- [ ] **Phase 4 — Web dashboard + multi-tenant config.** Per-user Discord channels, subscription billing, SaaS product shape.
- [ ] **Phase 5 — Automated execution (Kalshi API).** Only after Phase 1's signal log proves a real edge.

Other niches (crypto 5-minute rounds, politics, weather, economic data) are deliberately deferred to keep the sport-first MVP focused. Each is a new `FeedAdapter` + divergence rule when the time comes.

## Discord channel topic

If you're running this for a Discord audience, paste this into your channel topic (under 1024-char limit):

```
Real-time +EV signals for MLB prediction markets. A Python scanner polls Polymarket every 30s across 572 active MLB markets (futures + game/prop markets) and posts automated alerts here when something meaningful moves.

Signal types:
• Price swing — YES probability shifts >10% over 10 min
• Volume spike — $100k+ fresh volume on a single market
• New market (currently disabled)

Each alert includes a "How to trade" playbook for that signal type and a Kalshi search link so US users can act on the same event via Kalshi.

Source: https://github.com/wbp318/polymarket_kalshi_tools

Clone and run your own:
  git clone https://github.com/wbp318/polymarket_kalshi_tools.git
  cd polymarket_kalshi_tools
  python -m venv venv
  ./venv/Scripts/python.exe -m pip install -r requirements.txt
  (copy config.example.yaml to config.yaml, paste your Discord webhook URL)
  ./venv/Scripts/python.exe main.py

Not advice. Signals are starting points — verify on Kalshi or Polymarket before trading.
```

## Security / webhook handling

- *config.yaml* is gitignored — your webhook URL never gets committed.
- Only share your webhook URL with people you'd trust to post as your bot in that channel.
- To rotate a leaked webhook: Discord → channel → Edit Channel → Integrations → Webhooks → delete the old webhook, create a new one, paste the new URL into *config.yaml*, restart the scanner.
- Scanner error logs can contain the full webhook URL when HTTP errors occur — don't paste raw logs into public places without stripping URLs.
