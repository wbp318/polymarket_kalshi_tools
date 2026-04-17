# polymarket-tools

Market scanner for Polymarket. Polls a tag (MLB by default), detects volume
spikes, price swings, and new markets, and posts alerts to Discord.

Read-only. Does not place trades. US users: signals still work; verify and
trade on Kalshi manually.

## First-time setup

```
cd "C:/Users/Tap Parker Farms/Documents/polymarket_tools"

# create a virtualenv
python -m venv venv

# install deps (works in any shell; no activation needed)
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# create your config from the example
copy config.example.yaml config.yaml     # PowerShell / CMD
# or: cp config.example.yaml config.yaml # bash / Git Bash
# then edit config.yaml and paste your Discord webhook URL
```

## Run

Shell-neutral (works in PowerShell, CMD, bash — no activation needed):
```
.\venv\Scripts\python.exe main.py
```

Or with activation:
- PowerShell: `.\venv\Scripts\Activate.ps1` then `python main.py`
- bash / Git Bash: `source venv/Scripts/activate` then `python main.py`

Stop with Ctrl+C. A `scanner.db` (SQLite) is created next to `main.py` and
stores every snapshot + every signal fired — that's the performance log.

## What it alerts on

| Signal | Fires when |
|---|---|
| `new_market` | A market appears under the configured tag that we haven't seen before |
| `volume_spike` | Cumulative volume jumped by at least `min_dollar_increase` between two polls AND ratio ≥ `min_ratio` |
| `price_swing` | YES probability changed by ≥ `min_probability_change` versus the snapshot `lookback_minutes` ago |

Tune thresholds in `config.yaml`. The first poll after starting is silent —
we need a baseline before we can detect changes.

## Architecture (why it's laid out this way)

- `core/polymarket_client.py` — only talks to Polymarket gamma API.
- `core/discord_alerter.py` — only talks to Discord webhooks.
- `core/storage.py` — SQLite; snapshots + signal log.
- `feeds/base.py` — `FeedAdapter` interface for future comparison feeds (Kalshi, Vegas via Optimal MCP, Binance). Drop a new class in `feeds/`, wire it in the scanner, no other code changes.
- `scanner/signals.py` — pure functions per signal type. Easy to add new ones.
- `scanner/loop.py` — the polling loop, dedup, and emission.
- `main.py` — entry point.
