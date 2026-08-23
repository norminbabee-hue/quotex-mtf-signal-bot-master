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

LOG = logging.getLogger("quotex_mtf_signal_bot.dashboard")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "live.json"


def iso(value):
    return value.astimezone(timezone.utc).isoformat() if value else None


def candle_payload(candle, now_utc: datetime):
    if candle is None:
        return {"state": "WAITING"}
    if candle.close > candle.open:
        direction = "UP"
    elif candle.close < candle.open:
        direction = "DOWN"
    else:
        direction = "FLAT"
    age = max(0, int((now_utc - candle.close_time_utc).total_seconds()))
    return {
        "state": "LIVE",
        "price": str(candle.close),
        "close": str(candle.close),
        "direction": direction,
        "opened_at": iso(candle.open_time_utc),
        "closed_at": iso(candle.close_time_utc),
        "tick_count": candle.tick_count,
        "seconds_to_close": max(0, int((candle.close_time_utc - now_utc).total_seconds())),
        "age_seconds": age,
    }


def write_snapshot(pair: str, managers, service, signal, last_tick, mt5_status: str, offset: int):
    now = datetime.now(timezone.utc)
    candles = {label: candle_payload(managers[label].current, now) for label in ("M1", "M5", "M15")}
    current = managers["M1"].current
    next_candle = iso(current.close_time_utc) if current else None
    signal_payload = None
    if signal is not None:
        signal_payload = {
            "direction": signal.next_candle_direction or signal.direction,
            "confidence": float(signal.confidence),
            "expiry_minutes": 1,
            "source_candle_time": iso(signal.entry_time_utc),
            "note": "Prediction generated only after a confirmed M1 candle close.",
        }

    snapshot = {
        "status": "LIVE" if mt5_status == "ONLINE" else "OFFLINE",
        "serverTime": iso(now),
        "mt5Status": mt5_status,
        "lastTick": iso(last_tick.timestamp_utc) if last_tick else None,
        "nextCandle": next_candle,
        "feedAgeSeconds": int((now - last_tick.timestamp_utc).total_seconds()) if last_tick else None,
        "pair": pair,
        "quotexServerOffsetSeconds": offset,
        "signal": signal_payload,
        "candles": candles,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    tmp.replace(OUT)


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
        service.seed_history(manager.seed_history(history_count))
        managers = {
            "M1": manager,
            "M5": LiveCandleManager(adapter, broker_symbol, server_offset_seconds=offset),
            "M15": LiveCandleManager(adapter, broker_symbol, server_offset_seconds=offset),
        }
        # Prime all builders from the same tick so their first live candle starts
        # on the same target-market boundary.
        last_tick = adapter.latest_tick(broker_symbol)
        for builder in managers.values():
            builder.on_tick(last_tick)
        signal = None
        LOG.info("Live dashboard started for %s (%s), Quotex offset %+d sec", pair, broker_symbol, offset)

        while True:
            try:
                tick = adapter.latest_tick(broker_symbol)
                last_tick = tick
                for label, builder in managers.items():
                    event = builder.on_tick(tick)
                    if event is not None and label == "M1":
                        signal = service.on_closed_candle(event.candle)
                write_snapshot(pair, managers, service, signal, last_tick, "ONLINE", offset)
                time.sleep(poll)
            except KeyboardInterrupt:
                raise
            except Exception:
                LOG.exception("Live dashboard cycle failed")
                write_snapshot(pair, managers, service, signal, last_tick, "ERROR", offset)
                time.sleep(max(1.0, poll))
    finally:
        adapter.close()


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    main()
