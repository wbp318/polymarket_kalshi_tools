import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

log = logging.getLogger(__name__)

MAX_429_RETRIES = 5
INTER_SEND_DELAY_SECONDS = 0.35  # stay under Discord's 5-req/2-sec per-webhook limit

COLOR_VOLUME_SPIKE = 0xF59E0B
COLOR_PRICE_SWING = 0x3B82F6
COLOR_NEW_MARKET = 0x10B981
COLOR_ERROR = 0xEF4444


@dataclass
class Embed:
    title: str
    description: str
    url: Optional[str] = None
    color: int = 0x6366F1
    fields: Optional[list[tuple[str, str, bool]]] = None
    footer: Optional[str] = None


class DiscordAlerter:
    def __init__(self, webhook_url: str, timeout: float = 10.0):
        if not webhook_url or "PASTE" in webhook_url:
            raise ValueError("Discord webhook URL is not configured. Edit config.yaml.")
        self.webhook_url = webhook_url
        self.timeout = timeout
        self._session = requests.Session()

    def send(self, embed: Embed) -> None:
        payload = {"embeds": [_serialize(embed)]}
        for attempt in range(MAX_429_RETRIES):
            resp = self._session.post(self.webhook_url, json=payload, timeout=self.timeout)
            if resp.status_code == 429:
                retry_after = _retry_after_seconds(resp)
                log.warning("Discord 429 (attempt %d); sleeping %.2fs", attempt + 1, retry_after)
                time.sleep(retry_after)
                continue
            if resp.status_code >= 400:
                log.error("Discord webhook failed: %s %s", resp.status_code, resp.text[:300])
                return
            time.sleep(INTER_SEND_DELAY_SECONDS)
            return
        log.error("Discord webhook gave up after %d 429 retries", MAX_429_RETRIES)


def _retry_after_seconds(resp: requests.Response) -> float:
    try:
        body = resp.json()
        if isinstance(body, dict) and "retry_after" in body:
            return max(0.1, float(body["retry_after"]))
    except (ValueError, KeyError, TypeError):
        pass
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return max(0.1, float(header))
        except ValueError:
            pass
    return 1.0


def _serialize(e: Embed) -> dict:
    payload = {
        "title": e.title[:256],
        "description": e.description[:4000],
        "color": e.color,
    }
    if e.url:
        payload["url"] = e.url
    if e.fields:
        payload["fields"] = [
            {"name": n[:256], "value": v[:1024], "inline": inline}
            for (n, v, inline) in e.fields
        ]
    if e.footer:
        payload["footer"] = {"text": e.footer[:2048]}
    return payload
