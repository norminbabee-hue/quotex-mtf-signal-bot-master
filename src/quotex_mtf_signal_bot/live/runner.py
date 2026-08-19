from __future__ import annotations

import logging
import time
from decimal import Decimal

from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter, Tick
from quotex_mtf_signal_bot.live.config import LiveConfig
from quotex_mtf_signal_bot.live.live_bot import LiveBot
from quotex_mtf_signal_bot.telegram.dry_run_publisher import DryRunPublisher
from quotex_mtf_signal_bot.telegram.publisher import TelegramConfig, TelegramPublisher

LOG = logging.getLogger("quotex_mtf_signal_bot.live")


def build_from_env() -> tuple[MT5Adapter, LiveBot, LiveConfig]:
    config = LiveConfig.from_env()
    config.validate_secrets()
    adapter = MT5Adapter(
        login=int(__import__("os").environ["MT5_LOGIN"]) if __import__("os").getenv("MT5_LOGIN") else None,
        password=__import__("os").getenv("MT5_PASSWORD"),
        server=__import__("os").getenv("MT5_SERVER"),
        path=__import__("os").getenv("MT5_PATH"),
    )
    if config.dry_run:
        publisher = DryRunPublisher()
        LOG.warning("DRY_RUN enabled: Telegram messages will NOT be sent")
    else:
        import os
        publisher = TelegramPublisher(TelegramConfig(
            bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            chat_id=os.environ["TELEGRAM_CHAT_ID"],
        ))
    return adapter, LiveBot(adapter, config.symbol, publisher), config


def run_forever() -> None:
    adapter, bot, config = build_from_env()
    try:
        bot.warm_up(config.history_count)
        LOG.info("Live bot started for %s", config.symbol)
        last_tick_key: tuple[int, str, Decimal, Decimal] | None = None
        while True:
            try:
                raw = adapter.latest_tick(config.symbol)
                key = (int(raw.timestamp_utc.timestamp()), raw.symbol, raw.bid, raw.ask)
                if key != last_tick_key:
                    bot.on_tick(raw)
                    last_tick_key = key
            except Exception:
                LOG.exception("Live tick cycle failed; retrying")
            time.sleep(config.poll_seconds)
    finally:
        adapter.close()


if __name__ == "__main__":
    logging.basicConfig(level=LiveConfig.from_env().log_level)
    run_forever()
