from __future__ import annotations

import os
from datetime import datetime, timezone

from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter
from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry


def main() -> int:
    requested = os.getenv("MT5_SYMBOL", "EURUSD").strip().upper()
    path = os.getenv("MT5_PATH") or None
    print("=== MT5 MARKET DATA CHECK ===")
    print(f"Requested pair: {requested}")
    try:
        adapter = MT5Adapter(path=path)
    except Exception as exc:
        print(f"MT5 initialization failed: {exc}")
        return 1

    try:
        registry = SymbolRegistry.from_mt5(adapter, candidates=(requested,))
        if requested not in registry.symbols:
            print(f"No MT5 symbol found for {requested}.")
            print("Possible matches:")
            for name in adapter.symbols():
                if requested in name.upper():
                    print(f"  {name}")
            return 2

        broker_symbol = registry.broker_symbol(requested)
        print(f"Selected symbol: {broker_symbol}")
        tick = adapter.latest_tick(broker_symbol)
        age = (datetime.now(timezone.utc) - tick.timestamp_utc).total_seconds()
        print(f"Tick UTC: {tick.timestamp_utc.isoformat()}")
        print(f"Bid: {tick.bid}")
        print(f"Ask: {tick.ask}")
        print(f"Tick age: {age:.2f}s")

        for timeframe in ("M1", "M5", "M15"):
            bars = adapter.bars(broker_symbol, timeframe, 3)
            print(f"{timeframe}: {len(bars)} bars")
            if bars:
                bar = bars[-1]
                print(f"  {bar.timestamp_utc.isoformat()} O={bar.open} H={bar.high} L={bar.low} C={bar.close}")

        print("RESULT: MT5 FEED OK")
        return 0
    finally:
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
