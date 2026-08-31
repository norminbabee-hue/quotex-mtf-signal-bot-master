from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quotex_mtf_signal_bot.config.quotex_pairs import QUOTEX_PAIRS
from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter, Tick
from quotex_mtf_signal_bot.live.multi_pair_scanner import MultiPairScanner
from quotex_mtf_signal_bot.telegram.publisher import TelegramConfig, TelegramPublisher

LOG = logging.getLogger("quotex_mtf_signal_bot.dashboard")
OUT = ROOT / "data" / "live.json"
ENV_FILE = ROOT / ".env"
TIMEFRAMES = ("M1", "M5", "M15")
STALE_FEED_SECONDS = 30.0


def load_local_env() -> None:
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
STALE_FEED_SECONDS = float(os.getenv("MT5_MAX_TICK_AGE_SECONDS", "30"))
PRE_ENTRY_SECONDS = max(30, min(60, int(os.getenv("TELEGRAM_PRE_ENTRY_SECONDS", "45"))))
MAX_ACTIVE_SIGNALS = max(1, int(os.getenv("TELEGRAM_MAX_ACTIVE_SIGNALS", "1")))


def iso(value):
    return value.astimezone(timezone.utc).isoformat() if value else None


def feed_status(last_tick: Tick | None, now_utc: datetime) -> str:
    if last_tick is None:
        return "WAITING_FOR_FEED"
    age = (now_utc - last_tick.timestamp_utc).total_seconds()
    return "MARKET_CLOSED_OR_STALE" if age > STALE_FEED_SECONDS else "ONLINE"


def candle_payload(candle, now_utc: datetime):
    if candle is None:
        return {"state": "WAITING"}
    direction = "UP" if candle.close > candle.open else "DOWN" if candle.close < candle.open else "FLAT"
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
    reasons = list(getattr(signal, "reasons", ()))
    target = getattr(signal, "target_timeframe", "M1")
    return {
        "direction": signal.next_candle_direction or signal.direction,
        "target_timeframe": target,
        "confidence": prediction_confidence,
        "prediction_confidence": prediction_confidence,
        "actionable_confidence": actionable_confidence,
        "actionable": actionable_confidence > 0,
        "status": "ACTIONABLE" if actionable_confidence > 0 else "PREDICTION_ONLY",
        "reasons": reasons,
        "expiry_minutes": {"M1": 1, "M5": 5, "M15": 15}.get(target, 1),
        "source_candle_time": iso(signal.entry_time_utc),
        "note": "Confidence is a model score, not a guaranteed win probability.",
    }


def write_snapshot(scanner: MultiPairScanner, latest_signals: dict[str, dict[str, object]], last_ticks: dict[str, Tick], offset: int, active_signal=None):
    now = datetime.now(timezone.utc)
    pairs = {}
    for pair in scanner.registry.symbols:
        manager = scanner.managers[pair]
        tick = last_ticks.get(pair)
        status = feed_status(tick, now)
        predictions = {label: signal_payload(latest_signals.get(pair, {}).get(label)) for label in TIMEFRAMES}
        pairs[pair] = {
            "status": "LIVE" if status == "ONLINE" else "WAITING",
            "marketState": status,
            "lastTick": iso(tick.timestamp_utc) if tick else None,
            "feedAgeSeconds": int((now - tick.timestamp_utc).total_seconds()) if tick else None,
            "brokerSymbol": scanner.broker_symbol(pair),
            "signal": predictions.get("M1") or predictions.get("M5") or predictions.get("M15"),
            "predictions": predictions,
            "candles": {label: candle_payload(manager.builders[label].current, now) for label in TIMEFRAMES},
        }
    snapshot = {
        "status": "LIVE" if any(item["status"] == "LIVE" for item in pairs.values()) else "WAITING",
        "marketState": "ONLINE" if any(item["marketState"] == "ONLINE" for item in pairs.values()) else "MARKET_CLOSED_OR_STALE",
        "serverTime": iso(now),
        "quotexServerOffsetSeconds": offset,
        "pairCount": len(pairs),
        "pairs": pairs,
        "pair": scanner.registry.symbols[0] if scanner.registry.symbols else None,
        "entryPolicy": {
            "preEntrySeconds": PRE_ENTRY_SECONDS,
            "maxActiveSignals": MAX_ACTIVE_SIGNALS,
            "mode": "ONE_BEST_ACTIONABLE_SIGNAL",
        },
        "activeSignal": signal_payload(active_signal) if active_signal else None,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, indent=2)
    try:
        OUT.write_text(payload, encoding="utf-8")
    except PermissionError:
        time.sleep(0.05)
        try:
            OUT.write_text(payload, encoding="utf-8")
        except PermissionError:
            LOG.warning("live.json remains locked; skipping this snapshot cycle")


def telegram_publisher_from_env() -> TelegramPublisher | None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        LOG.warning("Telegram disabled: TELEGRAM_BOT_TOKEN=%s, TELEGRAM_CHAT_ID=%s", "SET" if token else "MISSING", "SET" if chat_id else "MISSING")
        return None
    publisher = TelegramPublisher(TelegramConfig(bot_token=token, chat_id=chat_id))
    try:
        username = publisher.verify_connection()
    except Exception as exc:
        LOG.error("Telegram configuration found but connection check failed: %s", exc)
        return None
    LOG.info("Telegram connected successfully: @%s | chat_id configured=YES", username)
    return publisher


def publish_ranked_signal(publisher: TelegramPublisher | None, signal, now_utc: datetime) -> None:
    if publisher is None or signal is None:
        return
    publisher.publish(signal)
    entry = signal.entry_time_utc.astimezone(timezone.utc)
    lead = max(0, int((entry - now_utc).total_seconds()))
    LOG.info("TELEGRAM ACTIONABLE SENT pair=%s direction=%s target=%s confidence=%.1f%% entry_in=%ss entry=%s", signal.symbol, signal.next_candle_direction or signal.direction, signal.target_timeframe, float(signal.confidence), lead, entry.isoformat())


def candidate_rank(signal):
    timeframe_priority = {"M1": 3, "M5": 2, "M15": 1}
    return (float(signal.confidence), float(getattr(signal, "prediction_confidence", 0)), int(getattr(signal, "score", 0)), timeframe_priority.get(getattr(signal, "target_timeframe", "M1"), 0))


def main() -> None:
    offset = int(os.getenv("QUOTEX_SERVER_OFFSET_SECONDS", "21600"))
    poll = float(os.getenv("MT5_POLL_SECONDS", "0.25"))
    history_count = max(60, int(os.getenv("MT5_HISTORY_COUNT", "200")))
    path = os.getenv("MT5_PATH") or None
    configured_symbols = tuple(item.strip().upper() for item in os.getenv("MT5_SYMBOLS", "").split(",") if item.strip())
    pair_filter = configured_symbols or QUOTEX_PAIRS

    adapter = MT5Adapter(path=path)
    try:
        telegram = telegram_publisher_from_env()
        latest_signals: dict[str, dict[str, object]] = {}
        last_ticks: dict[str, Tick] = {}
        published_targets: set[tuple[str, str]] = set()
        active_signal = None

        def on_signal(signal) -> None:
            target = getattr(signal, "target_timeframe", "M1")
            latest_signals.setdefault(signal.symbol, {})[target] = signal
            LOG.info("CLOSED-CANDLE RESULT pair=%s direction=%s target=%s prediction=%.1f%% actionable=%.1f%% (not sent late)", signal.symbol, signal.next_candle_direction or signal.direction, target, float(getattr(signal, "prediction_confidence", signal.confidence)), float(signal.confidence))

        scanner = MultiPairScanner(adapter, on_signal, server_offset_seconds=offset, candidates=pair_filter)
        if not scanner.registry.symbols:
            raise RuntimeError("None of the configured Quotex pairs are available in the connected MT5 terminal")
        LOG.info("Quotex whitelist: %d pairs requested; %d matched in MT5: %s", len(pair_filter), len(scanner.registry.symbols), ", ".join(scanner.registry.symbols))
        scanner.warm_up(history_count)

        for pair in scanner.registry.symbols:
            try:
                tick = adapter.latest_tick(scanner.broker_symbol(pair))
                last_ticks[pair] = tick
                scanner.managers[pair].on_tick(tick)
            except Exception:
                LOG.exception("Initial tick failed for pair=%s", pair)

        cycle = 0
        last_report = 0.0
        LOG.info("Live Quotex multi-pair dashboard started: %d matched pairs, Quotex offset %+d sec", len(scanner.registry.symbols), offset)

        while True:
            try:
                cycle += 1
                now = datetime.now(timezone.utc)
                for pair in scanner.registry.symbols:
                    try:
                        tick = adapter.latest_tick(scanner.broker_symbol(pair))
                    except Exception:
                        LOG.exception("MT5 tick read failed for pair=%s", pair)
                        continue
                    if (now - tick.timestamp_utc).total_seconds() <= STALE_FEED_SECONDS:
                        last_ticks[pair] = tick
                        scanner.on_tick(tick)

                if active_signal is None or now >= active_signal.entry_time_utc + timedelta(minutes={"M1": 1, "M5": 5, "M15": 15}.get(active_signal.target_timeframe, 1)):
                    active_signal = None

                if active_signal is None:
                    candidates = scanner.preview_candidates(now, PRE_ENTRY_SECONDS)
                    if candidates:
                        candidates.sort(key=candidate_rank, reverse=True)
                        best = candidates[0]
                        target_key = (best.target_timeframe, best.entry_time_utc.isoformat())
                        if target_key not in published_targets:
                            publish_ranked_signal(telegram, best, now)
                            published_targets.add(target_key)
                            active_signal = best
                            LOG.info("ACTIONABLE PICK pair=%s target=%s direction=%s confidence=%.1f%% candidates=%d", best.symbol, best.target_timeframe, best.next_candle_direction or best.direction, float(best.confidence), len(candidates))

                if len(published_targets) > 100:
                    published_targets = set(list(published_targets)[-30:])

                write_snapshot(scanner, latest_signals, last_ticks, offset, active_signal)
                now_mono = time.monotonic()
                if now_mono - last_report >= 5.0:
                    online = sum(feed_status(last_ticks.get(pair), datetime.now(timezone.utc)) == "ONLINE" for pair in scanner.registry.symbols)
                    LOG.info("LIVE heartbeat cycle=%d quotex_pairs=%d online=%d active_signal=%s", cycle, len(scanner.registry.symbols), online, f"{active_signal.symbol}/{active_signal.target_timeframe}" if active_signal else "NONE")
                    last_report = now_mono
                time.sleep(poll)
            except KeyboardInterrupt:
                raise
            except Exception:
                LOG.exception("Live dashboard cycle failed")
                time.sleep(max(1.0, poll))
    finally:
        adapter.close()


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    main()
