from __future__ import annotations

from datetime import timezone
from typing import Any

from quotex_mtf_signal_bot.analysis.mtf import analyze_mtf
from quotex_mtf_signal_bot.core.models import Candle, Timeframe
from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter, MT5Bar
from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry
from quotex_mtf_signal_bot.signals.expiry import choose_expiry
from quotex_mtf_signal_bot.signals.scoring import score_mtf


TIMEFRAMES = {"M1": Timeframe.M1, "M5": Timeframe.M5, "M15": Timeframe.M15}


def _to_candles(bars: list[MT5Bar]) -> list[Candle]:
    return [
        Candle(
            symbol=bar.symbol,
            timeframe=TIMEFRAMES[bar.timeframe],
            timestamp_utc=bar.timestamp_utc,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
        )
        for bar in bars
    ]


def scan_live_pairs(adapter: MT5Adapter, history_count: int = 120) -> list[dict[str, Any]]:
    """Analyze every FX symbol currently exposed by the connected MT5 feed.

    Only closed historical bars are used for the analysis: the newest MT5 bar
    is the currently-forming bar on normal feeds and is therefore discarded.
    """
    registry = SymbolRegistry.from_mt5(adapter)
    rows: list[dict[str, Any]] = []

    for symbol in registry.symbols:
        try:
            raw: dict[Timeframe, list[MT5Bar]] = {}
            for label, timeframe in TIMEFRAMES.items():
                bars = adapter.bars(symbol, label, history_count)
                if len(bars) < 61:
                    raise RuntimeError(f"only {len(bars)} {label} bars available")
                raw[timeframe] = bars[:-1]

            candles = {timeframe: _to_candles(bars) for timeframe, bars in raw.items()}
            analysis = analyze_mtf(candles)
            score = score_mtf(analysis)
            latest = candles[Timeframe.M1][-1]

            if score.direction == "NO_SIGNAL":
                expiry_value = "—"
            else:
                expiry_value = choose_expiry(analysis).expiry.value

            rows.append(
                {
                    "pair": symbol,
                    "signal": score.direction,
                    "score": score.score,
                    "confidence": f"{score.confidence:.0f}%",
                    "expiry": expiry_value,
                    "closed_at": latest.timestamp_utc.astimezone(timezone.utc).isoformat(),
                    "reason": " | ".join(score.reasons),
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "pair": symbol,
                    "signal": "ERROR",
                    "score": 0,
                    "confidence": "—",
                    "expiry": "—",
                    "closed_at": "—",
                    "reason": str(exc),
                }
            )

    order = {"CALL": 0, "PUT": 1, "NO_SIGNAL": 2, "ERROR": 3}
    rows.sort(key=lambda row: (order.get(row["signal"], 9), -int(row["score"]), row["pair"]))
    return rows


def run_live_dashboard() -> None:
    import streamlit as st

    st.set_page_config(page_title="Quotex MTF — Live Scanner", page_icon="📡", layout="wide")
    st.title("📡 Live MTF Currency Scanner")
    st.caption(
        "Real-time research analysis from the connected MT5 feed. "
        "It scans every broker-discovered FX pair and does not execute trades."
    )

    refresh = st.button("🔄 Refresh all pairs", type="primary", use_container_width=True)
    if "live_rows" not in st.session_state or refresh:
        try:
            adapter = MT5Adapter()
            try:
                with st.spinner("Analyzing every available FX pair…"):
                    st.session_state.live_rows = scan_live_pairs(adapter)
            finally:
                adapter.close()
            st.session_state.live_error = None
        except Exception as exc:
            st.session_state.live_error = str(exc)

    if st.session_state.get("live_error"):
        st.error(st.session_state.live_error)
        st.info("Make sure the MT5 terminal is running and the required symbols are visible in Market Watch.")
        return

    rows = st.session_state.get("live_rows", [])
    if not rows:
        st.info("No FX symbols were discovered from the connected MT5 terminal yet.")
        return

    calls = sum(row["signal"] == "CALL" for row in rows)
    puts = sum(row["signal"] == "PUT" for row in rows)
    neutral = sum(row["signal"] == "NO_SIGNAL" for row in rows)
    errors = sum(row["signal"] == "ERROR" for row in rows)

    metrics = st.columns(5)
    metrics[0].metric("Pairs scanned", len(rows))
    metrics[1].metric("CALL", calls)
    metrics[2].metric("PUT", puts)
    metrics[3].metric("NO SIGNAL", neutral)
    metrics[4].metric("Errors", errors)

    st.divider()
    st.subheader("Current analysis")
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "pair": "Pair",
            "signal": "Signal",
            "score": st.column_config.NumberColumn("Score", format="%d"),
            "confidence": "Confidence",
            "expiry": "Expiry",
            "closed_at": "Latest closed M1",
            "reason": "Why",
        },
    )
    st.caption(
        "Confidence is a model-strength score, not a guaranteed probability of winning. "
        "NO SIGNAL is intentional when M1/M5/M15 confirmation is insufficient."
    )


if __name__ == "__main__":
    run_live_dashboard()
