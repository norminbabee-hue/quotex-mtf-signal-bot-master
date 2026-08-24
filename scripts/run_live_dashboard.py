from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from quotex_mtf_signal_bot.data.live_candles import LiveCandleManager
from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter, Tick
from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry
from quotex_mtf_signal_bot.live.multi_pair_scanner import MultiPairScanner
from quotex_mtf_signal_bot.telegram.publisher import TelegramConfig, TelegramPublisher

LOG = logging.getLogger("quotex_mtf_signal_bot.dashboard")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "live.json"
ENV_FILE = ROOT / ".env"
STALE_FEED_SECONDS = float(os.getenv("MT5_MAX_TICK_AGE_SECONDS", "30"))
TIMEFRAMES = ("M1", "M5", "M15")


def load_local_env() -> None:
    """Load simple KEY=VALUE settings from the local, git-ignored .env file."""
    if not ENV_FILE.exists():
        return
    try:
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError as exc:
        LOG.warning("Could not read local .env file: %s", exc)


load_local_env()


def iso(value):
    return value.astimezone(timezone.utc).isoformat() if value else None


def feed_status(last_tick: Tick | None, now_utc: datetime) -> str:
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
    scanner: MultiPairScanner,
    latest_signals: dict[str, dict[str, object]],
    last_ticks: dict[str, Tick],
    offset: int,
):
    now = datetime.now(timezone.utc)
    pairs = {}
    for pair in scanner.registry.symbols:
        manager = scanner.managers[pair]
        tick = last_ticks.get(pair)
        status = feed_status(tick, now)
        predictions = {label: signal_payload(latest_signals.get(pair, {}).get(label)) for label in TIMEFRAMES}
        primary = predictions.get("M1") or predictions.get("M5") or predictions.get("M15")
        pairs[pair] = {
            "status": "LIVE" if status == "ONLINE" else "WAITING",
            "marketState": status,
            "lastTick": iso(tick.timestamp_utc) if tick else None,
            "feedAgeSeconds": int((now - tick.timestamp_utc).total_seconds()) if tick else None,
            "brokerSymbol": scanner.broker_symbol(pair),
            "signal": primary,
            "predictions": predictions,
            "candles": {label: candle_payload(manager.builders[label].current, now) for label in TIMEFRAMES},
        }

    snapshot = {
        "status": "LIVE" if any(item["status"] == "LIVE" for item in pairs.values()) else "WAITING",
        "marketState": "ONLINE" if any(item["marketState"] == "ONLINE" for item in pairs.values()) else "MARKET_CLOSED_OR_STALE",
        "serverTime": iso(now),
        "mt5Status": "ONLINE" if any(item["marketState"] == "ONLINE" for item in pairs.values()) else "WAITING",
        "quotexServerOffsetSeconds": offset,
        "pairCount": len(pairs),
        "pairs": pairs,
        # Backward-compatible single-pair fields for the existing dashboard UI.
        "pair": scanner.registry.symbols[0] if scanner.registry.symbols else None,
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
    """Create Telegram publisher from the local .env file when configured."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        LOG.info("Telegram publisher disabled: edit .env and set TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID")
        return None
    return TelegramPublisher(TelegramConfig(bot_token=token, chat_id=chat_id))


def publish_live_signal(publisher: TelegramPublisher | None, signal) -> None:
    if publisher is None or signal is None:
        return
    actionable = float(signal.confidence) > 0
    if actionable:
        publisher.publish(signal)
        LOG.info(
            "TELEGRAM SENT pair=%s direction=%s target=%s",
            signal.symbol,
            signal.next_candle_direction or signal.direction,
            getattr(signal, "target_timeframe", "M1"),
        )
        return
    if os.getenv("TELEGRAM_SEND_PREDICTIONS", "false").strip().lower() in {"1", "true", "yes", "on"}:
        reasons = getattr(signal, "reasons", ())
        rejection_reason = reasons[-1] if reasons else "action gate rejected"
        publisher.publish_prediction(signal, rejection_reason)
        LOG.info(
            "TELEGRAM SENT prediction pair=%s direction=%s target=%s",
            signal.symbol,
            signal.next_candle_direction or signal.direction,
            getattr(signal, "target_timeframe", "M1"),
        )


def main() -> None:
    offset = int(os.getenv("QUOTEX_SERVER_OFFSET_SECONDS", "21600"))
    poll = float(os.getenv("MT5_POLL_SECONDS", "0.25"))
    history_count = max(60, int(os.getenv("MT5_HISTORY_COUNT", "200")))
    path = os.getenv("MT5_PATH") or None
    pair_filter = tuple(
        item.strip().upper()
        for item in os.getenv("MT5_SYMBOLS", "").split(",")
        if item.strip()
    ) or None

    adapter = MT5Adapter(path=path)
    try:
        telegram = telegram_publisher_from_env()
        latest_signals: dict[str, dict[str, object]] = {}
        last_ticks: dict[str, Tick] = {}

        def on_signal(signal) -> None:
            target = getattr(signal, "target_timeframe", "M1")
            latest_signals.setdefault(signal.symbol, {})[target] = signal
            LOG.info(
                "NEW SIGNAL pair=%s direction=%s target=%s prediction_confidence=%.1f%% actionable_confidence=%.1f%%",
                signal.symbol,
                signal.next_candle_direction or signal.direction,
                target,
                float(getattr(signal, "prediction_confidence", signal.confidence)),
                float(signal.confidence),
            )
            try:
                publish_live_signal(telegram, signal)
            except Exception:
                LOG.exception("Telegram publish failed; continuing multi-pair scanner")

        scanner = MultiPairScanner(
            adapter,
            on_signal,
            server_offset_seconds=offset,
            candidates=pair_filter,
        )
        if not scanner.registry.symbols:
            raise RuntimeError("No FX currency pairs were discovered in the connected MT5 terminal")

        LOG.info("Discovered %d FX pairs: %s", len(scanner.registry.symbols), ", ".join(scanner.registry.symbols))
        scanner.warm_up(history_count)

        # Seed each pair with its current tick before entering the live loop.
        for pair in scanner.registry.symbols:
            broker_symbol = scanner.broker_symbol(pair)
            try:
                tick = adapter.latest_tick(broker_symbol)
                last_ticks[pair] = tick
                scanner.managers[pair].on_tick(tick)
            except Exception:
                LOG.exception("Initial tick failed for pair=%s", pair)

        cycle = 0
        last_report = 0.0
        LOG.info("Live multi-pair dashboard started: %d FX pairs, Quotex offset %+d sec", len(scanner.registry.symbols), offset)

        while True:
            try:
                cycle += 1
                for pair in scanner.registry.symbols:
                    broker_symbol = scanner.broker_symbol(pair)
                    try:
                        tick = adapter.latest_tick(broker_symbol)
                    except Exception:
                        LOG.exception("MT5 tick read failed for pair=%s", pair)
                        continue

                    now = datetime.now(timezone.utc)
                    age = (now - tick.timestamp_utc).total_seconds()
                    if age <= STALE_FEED_SECONDS:
                        last_ticks[pair] = tick
                        scanner.on_tick(tick)

                write_snapshot(scanner, latest_signals, last_ticks, offset)
                now_mono = time.monotonic()
                if now_mono - last_report >= 5.0:
                    online = sum(feed_status(last_ticks.get(pair), datetime.now(timezone.utc)) == "ONLINE" for pair in scanner.registry.symbols)
                    LOG.info("LIVE heartbeat cycle=%d pairs=%d online=%d", cycle, len(scanner.registry.symbols), online)
                    last_report = now_mono
                time.sleep(poll)
            except KeyboardInterrupt:
                raise
            except Exception:
                LOG.exception("Live dashboard cycle failed")
                try:
                    write_snapshot(scanner, latest_signals, last_ticks, offset)
                except Exception:
                    LOG.exception("Snapshot write failed")
                time.sleep(max(1.0, poll))
    finally:
        adapter.close()


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    main()
