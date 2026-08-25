from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib import error, request

from quotex_mtf_signal_bot.signals.model import Signal


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    bot_token: str
    chat_id: str
    timeout_seconds: float = 10.0


class TelegramPublisher:
    """Telegram publisher for pre-entry next-candle actionable signals."""

    def __init__(self, config: TelegramConfig) -> None:
        if not config.bot_token or not config.chat_id:
            raise ValueError("Telegram bot_token and chat_id are required")
        self.config = config

    @staticmethod
    def _pair_label(symbol: str) -> str:
        compact = symbol.replace("/", "").upper()
        if len(compact) == 6 and compact.isalpha():
            return f"{compact[:3]}/{compact[3:]}"
        return symbol

    @staticmethod
    def _direction_label(signal: Signal) -> str:
        direction = signal.next_candle_direction or signal.direction
        return "UP ↑" if direction == "CALL" else "DOWN ↓" if direction == "PUT" else direction

    @staticmethod
    def _target_times(signal: Signal) -> tuple[str, str]:
        target_open = signal.entry_time_utc.astimezone(timezone.utc)
        minutes = {"M1": 1, "M5": 5, "M15": 15}.get(signal.target_timeframe, 1)
        target_close = target_open + timedelta(minutes=minutes)
        return target_open.isoformat(), target_close.isoformat()

    @staticmethod
    def format_signal(signal: Signal) -> str:
        confidence = Decimal(str(signal.confidence)).quantize(Decimal("0.01"))
        target_open, target_close = TelegramPublisher._target_times(signal)
        target = signal.target_timeframe
        now = datetime.now(timezone.utc)
        entry_seconds = max(0, int((signal.entry_time_utc.astimezone(timezone.utc) - now).total_seconds()))
        offset = int(os.getenv("QUOTEX_SERVER_OFFSET_SECONDS", "21600"))
        quotex_entry = signal.entry_time_utc.astimezone(timezone(timedelta(seconds=offset)))
        return "\n".join([
            "🔔 ACTIONABLE NEXT CANDLE SIGNAL",
            f"PAIR: {TelegramPublisher._pair_label(signal.symbol)}",
            f"TIMEFRAME: {target}",
            f"NEXT {target}: {TelegramPublisher._direction_label(signal)}",
            "STATUS: ✅ ACTIONABLE",
            f"ENTRY IN: {entry_seconds} SEC",
            f"ENTRY QUOTEX TIME: {quotex_entry.strftime('%Y-%m-%d %H:%M:%S')}",
            f"TARGET OPEN UTC: {target_open}",
            f"TARGET CLOSE UTC: {target_close}",
            f"EXPIRY: {signal.expiry}",
            f"CONFIDENCE: {confidence}%",
            "⚠️ Enter only at the stated target candle open; ignore this signal if the entry time has passed.",
        ])

    @staticmethod
    def format_prediction(signal: Signal, rejection_reason: str | None = None) -> str:
        target_open, target_close = TelegramPublisher._target_times(signal)
        target = signal.target_timeframe
        lines = [
            "🔮 NEXT CANDLE PREDICTION",
            f"PAIR: {TelegramPublisher._pair_label(signal.symbol)}",
            f"TIMEFRAME: {target}",
            f"DIRECTION: {TelegramPublisher._direction_label(signal)}",
            f"TARGET: NEXT CLOSED {target} CANDLE",
            f"TARGET OPEN UTC: {target_open}",
            f"TARGET CLOSE UTC: {target_close}",
            "STATUS: RESEARCH PREDICTION — NOT ACTIONABLE",
        ]
        if rejection_reason:
            lines.append(f"ACTION GATE: {rejection_reason}")
        return "\n".join(lines)

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.config.bot_token}/{method}"

    def verify_connection(self) -> str:
        req = request.Request(self._url("getMe"), method="GET")
        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"Telegram API returned HTTP {response.status}")
                body = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(f"Telegram connection failed: {exc}") from exc
        if not body.get("ok"):
            raise RuntimeError(f"Telegram API rejected bot token: {body.get('description', 'unknown error')}")
        return str(body.get("result", {}).get("username", "unknown"))

    def _send(self, text: str) -> None:
        payload = json.dumps({"chat_id": self.config.chat_id, "text": text}).encode("utf-8")
        req = request.Request(self._url("sendMessage"), data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"Telegram API returned HTTP {response.status}")
                body = json.loads(response.read().decode("utf-8"))
                if not body.get("ok"):
                    raise RuntimeError(f"Telegram API rejected message: {body.get('description', 'unknown error')}")
        except error.URLError as exc:
            raise RuntimeError(f"Telegram publish failed: {exc}") from exc

    def publish(self, signal: Signal) -> None:
        self._send(self.format_signal(signal))

    def publish_prediction(self, signal: Signal, rejection_reason: str | None = None) -> None:
        self._send(self.format_prediction(signal, rejection_reason))
