from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter


@dataclass(frozen=True, slots=True)
class SymbolHealth:
    symbol: str
    tick_ok: bool
    m1_bars: int
    m5_bars: int
    m15_bars: int
    bid: str | None
    ask: str | None
    error: str | None = None


def inspect_symbol(adapter: MT5Adapter, symbol: str, bars_count: int = 20) -> SymbolHealth:
    try:
        tick = adapter.latest_tick(symbol)
        m1 = adapter.bars(symbol, "M1", bars_count)
        m5 = adapter.bars(symbol, "M5", bars_count)
        m15 = adapter.bars(symbol, "M15", bars_count)
        return SymbolHealth(symbol, True, len(m1), len(m5), len(m15), str(tick.bid), str(tick.ask))
    except Exception as exc:
        return SymbolHealth(symbol, False, 0, 0, 0, None, None, str(exc))


def write_health_report(adapter: MT5Adapter, symbols: tuple[str, ...], path: str = "data/mt5_health.json") -> list[SymbolHealth]:
    import json
    results = [inspect_symbol(adapter, symbol) for symbol in symbols]
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbols": [asdict(item) for item in results],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return results
