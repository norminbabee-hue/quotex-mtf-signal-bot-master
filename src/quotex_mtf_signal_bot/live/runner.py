from __future__ import annotations

import logging
import os
import time
from decimal import Decimal

from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter, Tick
from quotex_mtf_signal_bot.live.live_bot import LiveBot
from quotex_mtf_signal_bot.telegram.publisher import TelegramConfig, TelegramPublisher

LOG = logging.getLogger("quotex_mtf_signal_bot.live")


def build_from_env() -> tuple[MT5Adapter, LiveBot, str]:
    symbol = os.environ["MT5_SYMBOL"]
    adapter = MT5Adapter(
        login=int(os.environ["MT5_LOGIN"]) if os.getenv("MT5_LOGIN") else None,
        password=os.getenv("MT5_PASSWORD"),
        server=os.getenv("MT5_SERVER"),
        path=os.getenv("MT5_PATH"),
    )
    publisher = TelegramPublisher(TelegramConfig(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_CHAT_ID"],
    ))
    return adapter, LiveBot(adapter, symbol, publisher), symbol


def run_forever(poll_seconds: float = 0.25) -> None:
    adapter, bot, symbol = build_from_env()
    try:
        bot.warm_up(int(os.getenv("MT5_HISTORY_COUNT", "200")))
        LOG.info("Live bot started for %s", symbol)
        last_tick_key: tuple[int, str, Decimal, Decimal] | None = None
        while True:
            try:
                raw = adapter.latest_tick(symbol)
                key = (int(raw.timestamp_utc.timestamp()), raw.symbol, raw.bid, raw.ask)
                if key != last_tick_key:
                    bot.on_tick(raw)
                    last_tick_key = key
            except Exception:
                LOG.exception("Live tick cycle failed; retrying")
            time.sleep(poll_seconds)
    finally:
        adapter.close()


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    run_forever()
