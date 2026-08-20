from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter


@dataclass(frozen=True, slots=True)
class MT5Health:
    connected: bool
    symbol: str
    bid: Decimal | None
    ask: Decimal | None
    m1_bars: int
    m5_bars: int
    m15_bars: int


def check_mt5(adapter: MT5Adapter, symbol: str, history_count: int = 20) -> MT5Health:
    tick = adapter.latest_tick(symbol)
    m1 = adapter.bars(symbol, "M1", history_count)
    m5 = adapter.bars(symbol, "M5", history_count)
    m15 = adapter.bars(symbol, "M15", history_count)
    return MT5Health(
        connected=True,
        symbol=symbol,
        bid=tick.bid,
        ask=tick.ask,
        m1_bars=len(m1),
        m5_bars=len(m5),
        m15_bars=len(m15),
    )
