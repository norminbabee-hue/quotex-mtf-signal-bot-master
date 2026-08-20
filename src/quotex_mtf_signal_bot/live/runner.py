from __future__ import annotations

import logging
import os
import time

from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter
from quotex_mtf_signal_bot.live.config import LiveConfig
from quotex_mtf_signal_bot.live.audit import SignalAuditLog
from quotex_mtf_signal_bot.live.multi_pair_bot import MultiPairBot
from quotex_mtf_signal_bot.telegram.dry_run_publisher import DryRunPublisher
from quotex_mtf_signal_bot.telegram.publisher import TelegramConfig, TelegramPublisher

LOG = logging.getLogger("quotex_mtf_signal_bot.live")


def build_from_env() -> tuple[MT5Adapter, MultiPairBot, LiveConfig]:
    config = LiveConfig.from_env()
    config.validate_secrets()
    adapter = MT5Adapter(
        login=int(os.environ["MT5_LOGIN"]) if os.getenv("MT5_LOGIN") else None,
        password=os.getenv("MT5_PASSWORD"),
        server=os.getenv("MT5_SERVER"),
        path=os.getenv("MT5_PATH"),
    )
    audit = SignalAuditLog()
    publisher = DryRunPublisher(audit=audit) if config.dry_run else TelegramPublisher(
        TelegramConfig(bot_token=os.environ["TELEGRAM_BOT_TOKEN"], chat_id=os.environ["TELEGRAM_CHAT_ID"])
    )
    if config.dry_run:
        LOG.warning("DRY_RUN enabled: Telegram messages will NOT be sent")
    bot = MultiPairBot(adapter, publisher, audit=audit)
    return adapter, bot, config


def run_forever() -> None:
    adapter, bot, config = build_from_env()
    try:
        symbols = bot.refresh_symbols()
        LOG.info("Monitoring %d major FX symbols: %s", len(symbols), ", ".join(symbols))
        bot.warm_up(config.history_count)
        while True:
            for symbol in bot.symbols:
                try:
                    bot.on_tick(adapter.latest_tick(symbol))
                except Exception:
                    LOG.exception("Tick cycle failed for %s; continuing", symbol)
            time.sleep(config.poll_seconds)
    finally:
        adapter.close()


if __name__ == "__main__":
    logging.basicConfig(level=LiveConfig.from_env().log_level)
    run_forever()
