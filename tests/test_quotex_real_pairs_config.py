import json

from quotex_mtf_signal_bot.config.quotex_pairs import (
    DEFAULT_QUOTEX_REAL_PAIRS,
    load_current_quotex_real_pairs,
)


def test_load_current_pairs_normalizes_slash_names(tmp_path):
    path = tmp_path / "pairs.json"
    path.write_text(json.dumps({"pairs": ["EUR/USD", "gbp jpy", "EURUSD"]}), encoding="utf-8")

    assert load_current_quotex_real_pairs(path) == ("EURUSD", "GBPJPY")


def test_invalid_or_empty_watchlist_uses_safe_default(tmp_path):
    path = tmp_path / "pairs.json"
    path.write_text(json.dumps({"pairs": ["BAD", "123"]}), encoding="utf-8")

    assert load_current_quotex_real_pairs(path) == DEFAULT_QUOTEX_REAL_PAIRS
