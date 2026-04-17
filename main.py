import logging
import sys
from pathlib import Path

import yaml

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from core.discord_alerter import DiscordAlerter
from core.polymarket_client import PolymarketClient
from core.storage import Storage
from scanner.loop import Scanner


def load_config(path: Path) -> dict:
    if not path.exists():
        sys.stderr.write(
            f"ERROR: config file not found at {path}\n"
            f"Copy config.example.yaml to config.yaml and fill in your Discord webhook URL.\n"
        )
        sys.exit(2)
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    project_root = Path(__file__).parent
    config_path = project_root / "config.yaml"
    config = load_config(config_path)

    setup_logging(config.get("logging", {}).get("level", "INFO"))

    storage = Storage(str(project_root / config["storage"]["db_path"]))
    client = PolymarketClient()
    alerter = DiscordAlerter(config["discord"]["webhook_url"])

    scanner = Scanner(client=client, storage=storage, alerter=alerter, config=config)
    try:
        scanner.run()
    finally:
        storage.close()


if __name__ == "__main__":
    main()
