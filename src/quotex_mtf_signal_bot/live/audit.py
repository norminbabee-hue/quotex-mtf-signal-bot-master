from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from quotex_mtf_signal_bot.signals.model import Signal

LOG = logging.getLogger("quotex_mtf_signal_bot.audit")


@dataclass(frozen=True, slots=True)
class AuditEvent:
    timestamp_utc: str
    event: str
    symbol: str
    details: dict


class SignalAuditLog:
    def __init__(self, path: str | Path = "data/live_audit.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: str, symbol: str, **details: object) -> None:
        item = AuditEvent(datetime.now(timezone.utc).isoformat(), event, symbol, details)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(item), default=str) + "\n")
        LOG.info("%s %s %s", event, symbol, details)

    def signal(self, signal: Signal, *, approved: bool, reason: str) -> None:
        self.record(
            "signal_decision",
            signal.symbol,
            direction=signal.direction,
            expiry=signal.expiry,
            confidence=str(signal.confidence),
            entry_time_utc=signal.entry_time_utc.isoformat(),
            approved=approved,
            reason=reason,
        )
