from datetime import datetime, timedelta, timezone

import pytest

from quotex_mtf_signal_bot.data.clock import BrokerClock


def test_broker_clock_tracks_offset() -> None:
    local = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    broker = local + timedelta(hours=2)

    snapshot = BrokerClock().update(broker, local)

    assert snapshot.offset_seconds == 7200


def test_clock_requires_timezone_aware_values() -> None:
    with pytest.raises(ValueError):
        BrokerClock().update(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc), datetime(2026, 1, 1, 12, 0))
