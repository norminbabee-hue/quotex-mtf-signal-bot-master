from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from quotex_mtf_signal_bot.live.audit import SignalAuditLog
from quotex_mtf_signal_bot.telegram.dry_run_publisher import DryRunPublisher
from quotex_mtf_signal_bot.signals.model import Signal


def test_dry_run_records_without_network(tmp_path: Path):
    audit = SignalAuditLog(tmp_path / "audit.jsonl")
    publisher = DryRunPublisher(audit=audit)
    signal = Signal(
        symbol="EURUSD",
        direction="CALL",
        expiry="1m",
        confidence=Decimal("82.5"),
        entry_time_utc=datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc),
    )
    publisher.publish(signal)
    text = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "dry_run_publish" in text
    assert "EURUSD" in text
    assert "CALL" in text
