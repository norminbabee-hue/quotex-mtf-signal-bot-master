from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from urllib import error, request

from quotex_mtf_signal_bot.signals.model import Signal


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    bot_token: str
    chat_id: str
    timeout_seconds: float = 10.0


class TelegramPublisher:
    """Minimal Telegram Bot API publisher for approved next-candle signals."""

    def __init__(self, config: TelegramConfig) -> None:
        if not config.bot_token or not config.chat_id:
            raise ValueError("Telegram bot_token and chat_id are required")
        self.config = config

    @staticmethod
    def format_signal(signal: Signal) -> str:
        confidence = Decimal(str(signal.confidence)).quantize(Decimal("0.01"))
        direction = signal.next_candle_direction or signal.direction
        direction_label = "UP ↑" if direction == "CALL" else "DOWN ↓" if direction == "PUT" else direction
        target_open = signal.entry_time_utc
        target_close = target_open + timedelta(minutes=1)
        return "\n".join([
            "🔔 NEXT CANDLE SIGNAL",
            f"PAIR: {signal.symbol}",
            f"NEXT M1: {direction_label}",
            "TARGET: NEXT CLOSED M1 CANDLE",
            f"TARGET OPEN UTC: {target_open.isoformat()}",
            f"TARGET CLOSE UTC: {target_close.isoformat()}",
            f"EXPIRY: {signal.expiry}",
            f"CONFIDENCE: {confidence}%",
            f"ENTRY UTC: {signal.entry_time_utc.isoformat()}",
        ])

    def publish(self, signal: Signal) -> None:
        payload = json.dumps({
            "chat_id": self.config.chat_id,
            "text": self.format_signal(signal),
        }).encode("utf-8")
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        req = request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"Telegram API returned HTTP {response.status}")
        except error.URLError as exc:
            raise RuntimeError(f"Telegram publish failed: {exc}") from exc
