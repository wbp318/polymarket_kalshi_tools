import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    market_id       TEXT NOT NULL,
    fetched_at      REAL NOT NULL,
    yes_price       REAL,
    last_trade      REAL,
    volume_num      REAL,
    liquidity_num   REAL,
    question        TEXT,
    event_slug      TEXT,
    PRIMARY KEY (market_id, fetched_at)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_market_time
    ON snapshots (market_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fired_at        REAL NOT NULL,
    signal_type     TEXT NOT NULL,
    market_id       TEXT NOT NULL,
    dedup_key       TEXT NOT NULL,
    payload_json    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signals_dedup_time
    ON signals (dedup_key, fired_at DESC);
"""


@dataclass
class PriorSnapshot:
    fetched_at: float
    yes_price: Optional[float]
    last_trade: Optional[float]
    volume_num: float
    liquidity_num: float


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.execute("PRAGMA journal_mode=WAL;")

    def close(self) -> None:
        self._conn.close()

    def record_snapshot(self, snap) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO snapshots "
            "(market_id, fetched_at, yes_price, last_trade, volume_num, liquidity_num, question, event_slug) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                snap.market_id,
                snap.fetched_at,
                snap.yes_price,
                snap.last_trade_price,
                snap.volume_num,
                snap.liquidity_num,
                snap.question,
                snap.event_slug,
            ),
        )

    def latest_prior(self, market_id: str, before_ts: float) -> Optional[PriorSnapshot]:
        row = self._conn.execute(
            "SELECT fetched_at, yes_price, last_trade, volume_num, liquidity_num "
            "FROM snapshots WHERE market_id = ? AND fetched_at < ? "
            "ORDER BY fetched_at DESC LIMIT 1",
            (market_id, before_ts),
        ).fetchone()
        if not row:
            return None
        return PriorSnapshot(
            fetched_at=row["fetched_at"],
            yes_price=row["yes_price"],
            last_trade=row["last_trade"],
            volume_num=row["volume_num"] or 0.0,
            liquidity_num=row["liquidity_num"] or 0.0,
        )

    def prior_at_or_before(self, market_id: str, cutoff_ts: float) -> Optional[PriorSnapshot]:
        row = self._conn.execute(
            "SELECT fetched_at, yes_price, last_trade, volume_num, liquidity_num "
            "FROM snapshots WHERE market_id = ? AND fetched_at <= ? "
            "ORDER BY fetched_at DESC LIMIT 1",
            (market_id, cutoff_ts),
        ).fetchone()
        if not row:
            return None
        return PriorSnapshot(
            fetched_at=row["fetched_at"],
            yes_price=row["yes_price"],
            last_trade=row["last_trade"],
            volume_num=row["volume_num"] or 0.0,
            liquidity_num=row["liquidity_num"] or 0.0,
        )

    def known_market_ids(self) -> set[str]:
        rows = self._conn.execute("SELECT DISTINCT market_id FROM snapshots").fetchall()
        return {r["market_id"] for r in rows}

    def recently_fired(self, dedup_key: str, within_seconds: float) -> bool:
        cutoff = time.time() - within_seconds
        row = self._conn.execute(
            "SELECT 1 FROM signals WHERE dedup_key = ? AND fired_at >= ? LIMIT 1",
            (dedup_key, cutoff),
        ).fetchone()
        return row is not None

    def record_signal(self, signal_type: str, market_id: str, dedup_key: str, payload: dict) -> None:
        self._conn.execute(
            "INSERT INTO signals (fired_at, signal_type, market_id, dedup_key, payload_json) "
            "VALUES (?,?,?,?,?)",
            (time.time(), signal_type, market_id, dedup_key, json.dumps(payload)),
        )

    @contextmanager
    def tx(self):
        self._conn.execute("BEGIN")
        try:
            yield self._conn
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
