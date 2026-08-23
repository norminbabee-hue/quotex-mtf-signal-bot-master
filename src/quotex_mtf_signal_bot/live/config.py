from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LiveConfig:
    symbol: str
    dry_run: bool
    history_count: int
    poll_seconds: float
    log_level: str
    quotex_server_offset_seconds: int

    @classmethod
    def from_env(cls) -> "LiveConfig":
        symbol = os.getenv("MT5_SYMBOL", "EURUSD").strip()
        if not symbol:
            raise ValueError("MT5_SYMBOL cannot be empty")
        history_count = int(os.getenv("MT5_HISTORY_COUNT", "200"))
        if history_count < 60:
            raise ValueError("MT5_HISTORY_COUNT must be at least 60")
        poll_seconds = float(os.getenv("MT5_POLL_SECONDS", "0.25"))
        if poll_seconds <= 0:
            raise ValueError("MT5_POLL_SECONDS must be positive")
        dry_run = os.getenv("DRY_RUN", "true").strip().lower() in {"1", "true", "yes", "on"}
        # This is the target Quotex server-clock offset, not the PC or MT5
        # timezone. It must be configured from the observed Quotex server clock.
        offset = int(os.getenv("QUOTEX_SERVER_OFFSET_SECONDS", "21600"))
        return cls(
            symbol,
            dry_run,
            history_count,
            poll_seconds,
            os.getenv("LOG_LEVEL", "INFO"),
            offset,
        )

    def validate_secrets(self) -> None:
        required = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
        if not self.dry_run:
            missing = [name for name in required if not os.getenv(name)]
            if missing:
                raise ValueError("Missing live secrets: " + ", ".join(missing))
