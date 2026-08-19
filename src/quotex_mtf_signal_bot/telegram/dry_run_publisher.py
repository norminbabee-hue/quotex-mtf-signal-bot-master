from __future__ import annotations

import logging

from quotex_mtf_signal_bot.signals.model import Signal
from quotex_mtf_signal_bot.telegram.publisher import TelegramPublisher

LOG = logging.getLogger("quotex_mtf_signal_bot.dry_run")


class DryRunPublisher:
    """Publisher that renders signals locally without sending them to Telegram."""

    def __init__(self, *, audit=None) -> None:
        self.audit = audit

    def publish(self, signal: Signal) -> None:
        message = TelegramPublisher.format_signal(signal)
        LOG.info("DRY RUN - Telegram message would be sent:\n%s", message)
        if self.audit is not None:
            self.audit.record(
                "dry_run_publish",
                signal.symbol,
                direction=signal.direction,
                expiry=signal.expiry,
                confidence=str(signal.confidence),
                entry_time_utc=signal.entry_time_utc.isoformat(),
                message=message,
            )
