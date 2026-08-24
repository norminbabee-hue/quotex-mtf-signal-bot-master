from datetime import datetime, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.signals.model import Signal
from quotex_mtf_signal_bot.telegram.publisher import TelegramPublisher


def make_signal(direction: str = "CALL", next_direction: str | None = None, symbol: str = "EURUSD") -> Signal:
    return Signal(
        symbol=symbol,
        direction=direction,
        expiry="1m",
        confidence=Decimal("84.5"),
        entry_time_utc=datetime(2026, 8, 23, 13, 15, tzinfo=timezone.utc),
        next_candle_direction=next_direction,
    )


def test_format_signal_explicitly_targets_next_m1_candle():
    text = TelegramPublisher.format_signal(make_signal("CALL", "CALL"))

    assert "NEXT M1: UP ↑" in text
    assert "PAIR: EUR/USD" in text
    assert "TARGET: NEXT CLOSED M1 CANDLE" in text
    assert "TARGET OPEN UTC: 2026-08-23T13:15:00+00:00" in text
    assert "TARGET CLOSE UTC: 2026-08-23T13:16:00+00:00" in text
    assert "CONFIDENCE: 84.50%" in text


def test_format_signal_maps_put_to_down():
    text = TelegramPublisher.format_signal(make_signal("PUT", "PUT", "USDJPY"))

    assert "PAIR: USD/JPY" in text
    assert "NEXT M1: DOWN ↓" in text
    assert "TARGET OPEN UTC: 2026-08-23T13:15:00+00:00" in text
    assert "TARGET CLOSE UTC: 2026-08-23T13:16:00+00:00" in text


def test_format_signal_falls_back_to_legacy_direction_when_prediction_missing():
    text = TelegramPublisher.format_signal(make_signal("PUT", None))

    assert "NEXT M1: DOWN ↓" in text


def test_format_prediction_is_distinct_from_actionable_signal():
    text = TelegramPublisher.format_prediction(make_signal("PUT", "PUT"), "confidence_below_threshold")

    assert "🔮 NEXT CANDLE PREDICTION" in text
    assert "PAIR: EUR/USD" in text
    assert "TIMEFRAME: M1" in text
    assert "DIRECTION: DOWN ↓" in text
    assert "STATUS: RESEARCH PREDICTION — NOT ACTIONABLE" in text
    assert "ACTION GATE: confidence_below_threshold" in text
