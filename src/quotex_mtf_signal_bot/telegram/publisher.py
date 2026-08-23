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
    """Minimal Telegram Bot API publisher for next-candle research signals."""

    def __init__(self, config: TelegramConfig) -> None:
        if not config.bot_token or not config.chat_id:
            raise ValueError("Telegram bot_token and chat_id are required")
        self.config = config

    @staticmethod
    def _direction_label(signal: Signal) -> str:
        direction = signal.next_candle_direction or signal.direction
        return "UP ↑" if direction == "CALL" else "DOWN ↓" if direction == "PUT" else direction

    @staticmethod
    def _target_times(signal: Signal) -> tuple[str, str]:
        target_open = signal.entry_time_utc
        target_close = target_open + timedelta(minutes=1)
        return target_open.isoformat(), target_close.isoformat()

    @staticmethod
    def format_signal(signal: Signal) -> str:
        confidence = Decimal(str(signal.confidence)).quantize(Decimal("0.01"))
        target_open, target_close = TelegramPublisher._target_times(signal)
        return "\n".join([
            "🔔 NEXT CANDLE SIGNAL",
            f"PAIR: {signal.symbol}",
            f"NEXT M1: {TelegramPublisher._direction_label(signal)}",
            "TARGET: NEXT CLOSED M1 CANDLE",
            f"TARGET OPEN UTC: {target_open}",
            f"TARGET CLOSE UTC: {target_close}",
            f"EXPIRY: {signal.expiry}",
            f"CONFIDENCE: {confidence}%",
            f"ENTRY UTC: {signal.entry_time_utc.isoformat()}",
        ])

    @staticmethod
    def format_prediction(signal: Signal, rejection_reason: str | None = None) -> str:
        target_open, target_close = TelegramPublisher._target_times(signal)
        lines = [
            "🔮 NEXT M1 PREDICTION",
            f"PAIR: {signal.symbol}",
            f"DIRECTION: {TelegramPublisher._direction_label(signal)}",
            "TARGET: NEXT CLOSED M1 CANDLE",
            f"TARGET OPEN UTC: {target_open}",
            f"TARGET CLOSE UTC: {target_close}",
            "STATUS: RESEARCH PREDICTION — NOT ACTIONABLE",
        ]
        if rejection_reason:
            lines.append(f"ACTION GATE: {rejection_reason}")
        return "\n".join(lines)

    def _send(self, text: str) -> None:
        payload = json.dumps({
            "chat_id": self.config.chat_id,
            "text": text,
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

    def publish(self, signal: Signal) -> None:
        self._send(self.format_signal(signal))

    def publish_prediction(self, signal: Signal, rejection_reason: str | None = None) -> None:
        self._send(self.format_prediction(signal, rejection_reason))
