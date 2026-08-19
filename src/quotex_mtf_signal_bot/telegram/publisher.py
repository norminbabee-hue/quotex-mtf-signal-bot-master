from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from urllib import error, request

from quotex_mtf_signal_bot.signals.model import Signal


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    bot_token: str
    chat_id: str
    timeout_seconds: float = 10.0


class TelegramPublisher:
    """Minimal Telegram Bot API publisher for approved signals."""

    def __init__(self, config: TelegramConfig) -> None:
        if not config.bot_token or not config.chat_id:
            raise ValueError("Telegram bot_token and chat_id are required")
        self.config = config

    @staticmethod
    def format_signal(signal: Signal) -> str:
        confidence = Decimal(str(signal.confidence)).quantize(Decimal("0.01"))
        return "\n".join([
            "🔔 BINARY SIGNAL",
            f"PAIR: {signal.symbol}",
            f"DIRECTION: {signal.direction}",
            f"EXPIRY: {signal.expiry}",
            f"CONFIDENCE: {confidence}%",
            f"ENTRY: {signal.entry_time_utc.isoformat()}",
        ])

    def publish(self, signal: Signal) -> None:
        payload = json.dumps({
            "chat_id": self.config.chat_id,
            "text": self.format_signal(signal),
        }).encode("utf-8")
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        req = request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"Telegram API returned HTTP {response.status}")
        except error.URLError as exc:
            raise RuntimeError(f"Telegram publish failed: {exc}") from exc
