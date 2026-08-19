from __future__ import annotations

from datetime import datetime, timezone

from quotex_mtf_signal_bot.core.models import ClockSnapshot


class BrokerClock:
    """Tracks broker/server time relative to UTC.

    The broker offset must come from the connected market-data source. We do
    not infer a target binary-options server clock from the local machine.
    """

    def __init__(self) -> None:
        self._offset_seconds: float | None = None

    def update(self, broker_time_utc: datetime, local_utc: datetime | None = None) -> ClockSnapshot:
        if broker_time_utc.tzinfo is None or local_utc is not None and local_utc.tzinfo is None:
            raise ValueError("Clock timestamps must be timezone-aware")

        local = local_utc or datetime.now(timezone.utc)
        broker = broker_time_utc.astimezone(timezone.utc)
        offset = (broker - local).total_seconds()
        self._offset_seconds = offset
        return ClockSnapshot(local, broker, offset)

    @property
    def offset_seconds(self) -> float | None:
        return self._offset_seconds

    def require_offset(self) -> float:
        if self._offset_seconds is None:
            raise RuntimeError("Broker clock has not been synchronized")
        return self._offset_seconds
