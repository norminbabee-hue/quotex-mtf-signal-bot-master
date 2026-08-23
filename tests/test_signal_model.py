from datetime import datetime, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.signals.model import Signal, build_signal
from quotex_mtf_signal_bot.signals.scoring import SignalScore


def test_build_signal_keeps_next_candle_prediction_when_action_gate_rejects(monkeypatch):
    monkeypatch.setattr(
        "quotex_mtf_signal_bot.signals.model.score_mtf",
        lambda _analysis: SignalScore(
            direction="NO_SIGNAL",
            score=16,
            confidence=Decimal("0"),
            reasons=("confidence below action threshold",),
            next_candle_direction="PUT",
        ),
    )

    signal = build_signal(
        "EURUSD",
        datetime(2026, 8, 23, 13, 15, tzinfo=timezone.utc),
        analysis=None,
    )

    assert signal is not None
    assert signal.direction == "PUT"
    assert signal.next_candle_direction == "PUT"
    assert signal.expiry == "1m"
    assert signal.confidence == Decimal("0")
