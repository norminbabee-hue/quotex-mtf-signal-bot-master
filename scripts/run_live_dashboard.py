from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from quotex_mtf_signal_bot.data.live_candles import LiveCandleManager
from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter
from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry
from quotex_mtf_signal_bot.live.mtf_signal_service import LiveMTFSignalService
from quotex_mtf_signal_bot.telegram.publisher import TelegramConfig, TelegramPublisher

LOG = logging.getLogger("quotex_mtf_signal_bot.dashboard")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "live.json"
STALE_FEED_SECONDS = float(os.getenv("MT5_MAX_TICK_AGE_SECONDS", "30"))
TIMEFRAMES = ("M1", "M5", "M15")


def iso(value):
    return value.astimezone(timezone.utc).isoformat() if value else None


def feed_status(last_tick, now_utc: datetime) -> str:
    if last_tick is None:
        return "WAITING_FOR_FEED"
    age = (now_utc - last_tick.timestamp_utc).total_seconds()
    if age > STALE_FEED_SECONDS:
        return "MARKET_CLOSED_OR_STALE"
    return "ONLINE"


def candle_payload(candle, now_utc: datetime):
    if candle is None:
        return {"state": "WAITING"}
    if candle.close > candle.open:
        direction = "UP"
    elif candle.close < candle.open:
        direction = "DOWN"
    else:
        direction = "FLAT"
    return {
        "state": "LIVE",
        "price": str(candle.close),
        "close": str(candle.close),
        "direction": direction,
        "opened_at": iso(candle.open_time_utc),
        "closed_at": iso(candle.close_time_utc),
        "tick_count": candle.tick_count,
        "seconds_to_close": max(0, int((candle.close_time_utc - now_utc).total_seconds())),
        "age_seconds": max(0, int((now_utc - candle.close_time_utc).total_seconds())),
    }


def signal_payload(signal):
    if signal is None:
        return None
    prediction_confidence = float(getattr(signal, "prediction_confidence", signal.confidence))
    actionable_confidence = float(signal.confidence)
    actionable = actionable_confidence > 0
    reasons = list(getattr(signal, "reasons", ()))
    gate_reason = None if actionable else (reasons[-1] if reasons else "action gate rejected")
    target = getattr(signal, "target_timeframe", "M1")
    return {
        "direction": signal.next_candle_direction or signal.direction,
        "target_timeframe": target,
        "confidence": prediction_confidence,
        "prediction_confidence": prediction_confidence,
        "actionable_confidence": actionable_confidence,
        "actionable": actionable,
        "status": "ACTIONABLE" if actionable else "PREDICTION_ONLY",
        "gate_reason": gate_reason,
        "reasons": reasons,
        "expiry_minutes": {"M1": 1, "M5": 5, "M15": 15}.get(target, 1),
        "source_candle_time": iso(signal.entry_time_utc),
        "note": "Prediction confidence is directional forecast strength, not a calibrated win probability. Actionable is true only when the stricter live action gate passes.",
    }


def write_snapshot(
    pair: str,
    manager: LiveCandleManager,
    latest_signals: dict[str, object],
    last_tick,
    offset: int,
):
    now = datetime.now(timezone.utc)
    status = feed_status(last_tick, now)
    candles = {
        label: candle_payload(manager.builders[label].current, now)
        for label in TIMEFRAMES
    }
    predictions = {
        label: signal_payload(latest_signals.get(label))
        for label in TIMEFRAMES
    }
    primary = predictions.get("M1") or predictions.get("M5") or predictions.get("M15")

    snapshot = {
        "status": "LIVE" if status == "ONLINE" else "WAITING",
        "marketState": status,
        "serverTime": iso(now),
        "mt5Status": status,
        "lastTick": iso(last_tick.timestamp_utc) if last_tick else None,
        "nextCandle": iso(manager.builders["M1"].current.close_time_utc) if manager.builders["M1"].current else None,
        "feedAgeSeconds": int((now - last_tick.timestamp_utc).total_seconds()) if last_tick else None,
        "pair": pair,
        "quotexServerOffsetSeconds": offset,
        "signal": primary,
        "predictions": predictions,
        "candles": candles,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, indent=2)
    try:
        OUT.write_text(payload, encoding="utf-8")
    except PermissionError:
        LOG.warning("live.json is temporarily locked; retrying snapshot write")
        time.sleep(0.05)
        try:
            OUT.write_text(payload, encoding="utf-8")
        except PermissionError:
            LOG.warning("live.json remains locked; skipping this snapshot cycle")


def telegram_publisher_from_env() -> TelegramPublisher | None:
    """Create the Telegram publisher only when both secrets are configured.

    Required environment variables:
      TELEGRAM_BOT_TOKEN
      TELEGRAM_CHAT_ID

    Optional:
      TELEGRAM_SEND_PREDICTIONS=true  -> also send non-actionable predictions.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        LOG.info("Telegram publisher disabled: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not configured")
        return None
    return TelegramPublisher(TelegramConfig(bot_token=token, chat_id=chat_id))


def publish_live_signal(publisher: TelegramPublisher | None, signal) -> None:
    """Publish actionable signals; optionally publish research-only predictions."""
    if publisher is None or signal is None:
        return

    actionable = float(signal.confidence) > 0
    if actionable:
        publisher.publish(signal)
        LOG.info(
            "TELEGRAM SENT actionable signal direction=%s target=%s",
            signal.next_candle_direction or signal.direction,
            getattr(signal, "target_timeframe", "M1"),
        )
        return

    if os.getenv("TELEGRAM_SEND_PREDICTIONS", "false").strip().lower() in {"1", "true", "yes", "on"}:
        reasons = getattr(signal, "reasons", ())
        rejection_reason = reasons[-1] if reasons else "action gate rejected"
        publisher.publish_prediction(signal, rejection_reason)
        LOG.info(
            "TELEGRAM SENT research prediction direction=%s target=%s",
            signal.next_candle_direction or signal.direction,
            getattr(signal, "target_timeframe", "M1"),
        )


def main() -> None:
    pair = os.getenv("MT5_SYMBOL", "EURUSD").strip().upper()
    offset = int(os.getenv("QUOTEX_SERVER_OFFSET_SECONDS", "21600"))
    poll = float(os.getenv("MT5_POLL_SECONDS", "0.25"))
    history_count = max(60, int(os.getenv("MT5_HISTORY_COUNT", "200")))
    path = os.getenv("MT5_PATH") or None

    adapter = MT5Adapter(path=path)
    try:
        registry = SymbolRegistry.from_mt5(adapter, candidates=(pair,))
        if pair not in registry.symbols:
            raise RuntimeError(f"{pair} is not available in the connected MT5 terminal")
        broker_symbol = registry.broker_symbol(pair)
        manager = LiveCandleManager(adapter, broker_symbol, server_offset_seconds=offset)
        service = LiveMTFSignalService(pair)
        telegram = telegram_publisher_from_env()
        service.seed_history(manager.seed_history(history_count))

        last_tick = adapter.latest_tick(broker_symbol)
        manager.on_tick(last_tick)
        latest_signals: dict[str, object] = {}
        cycle = 0
        last_report = 0.0
        LOG.info("Live dashboard started for %s (%s), Quotex offset %+d sec", pair, broker_symbol, offset)

        while True:
            try:
                tick = adapter.latest_tick(broker_symbol)
                now = datetime.now(timezone.utc)
                age = (now - tick.timestamp_utc).total_seconds()
                cycle += 1
                if age <= STALE_FEED_SECONDS:
                    last_tick = tick
                    events = manager.on_tick(tick)
                    for event in events:
                        closed_signals = service.on_closed_candle(event.candle)
                        for closed_signal in closed_signals:
                            target = getattr(closed_signal, "target_timeframe", "M1")
                            latest_signals[target] = closed_signal
                            prediction_confidence = float(getattr(closed_signal, "prediction_confidence", closed_signal.confidence))
                            actionable_confidence = float(closed_signal.confidence)
                            gate_reason = closed_signal.reasons[-1] if getattr(closed_signal, "reasons", ()) else "unknown"
                            if actionable_confidence > 0:
                                LOG.info(
                                    "ACTIONABLE SIGNAL %s target=%s prediction_confidence=%.1f%% actionable_confidence=%.1f%% source=%s",
                                    closed_signal.next_candle_direction or closed_signal.direction,
                                    target,
                                    prediction_confidence,
                                    actionable_confidence,
                                    iso(closed_signal.entry_time_utc),
                                )
                            else:
                                LOG.info(
                                    "NEW PREDICTION %s target=%s prediction_confidence=%.1f%% ACTIONABLE=NO gate=%s source=%s",
                                    closed_signal.next_candle_direction or closed_signal.direction,
                                    target,
                                    prediction_confidence,
                                    gate_reason,
                                    iso(closed_signal.entry_time_utc),
                                )
                            try:
                                publish_live_signal(telegram, closed_signal)
                            except Exception:
                                LOG.exception("Telegram publish failed; continuing live dashboard")
                else:
                    LOG.info("No fresh MT5 tick (%.2fs old); treating feed as closed/stale", age)

                write_snapshot(pair, manager, latest_signals, last_tick, offset)

                now_mono = time.monotonic()
                if now_mono - last_report >= 5.0:
                    status = feed_status(last_tick, now)
                    current = manager.builders["M1"].current
                    LOG.info(
                        "LIVE heartbeat cycle=%d status=%s tick_age=%.2fs bid=%s M1=%s M5=%s M15=%s",
                        cycle,
                        status,
                        age,
                        tick.bid,
                        iso(current.open_time_utc) if current else "WAITING",
                        iso(manager.builders["M5"].current.open_time_utc) if manager.builders["M5"].current else "WAITING",
                        iso(manager.builders["M15"].current.open_time_utc) if manager.builders["M15"].current else "WAITING",
                    )
                    last_report = now_mono
                time.sleep(poll)
            except KeyboardInterrupt:
                raise
            except Exception:
                LOG.exception("Live dashboard cycle failed")
                write_snapshot(pair, manager, latest_signals, last_tick, offset)
                time.sleep(max(1.0, poll))
    finally:
        adapter.close()


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    main()
