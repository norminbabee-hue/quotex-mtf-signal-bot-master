from __future__ import annotations

from datetime import timezone
from typing import Any

from quotex_mtf_signal_bot.analysis.mtf import analyze_mtf
from quotex_mtf_signal_bot.core.models import Candle, Timeframe
from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter, MT5Bar
from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry
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

    The displayed prediction is explicitly for the NEXT M1 candle. Only closed
    M1/M5/M15 bars are used to calculate it; the forming MT5 bar is discarded.
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

            if score.next_candle_direction == "CALL":
                next_candle = "UP ↑"
            elif score.next_candle_direction == "PUT":
                next_candle = "DOWN ↓"
            else:
                next_candle = "NO SIGNAL"

            # The horizon is about the prediction target, not whether the
            # stricter actionability gate accepted the setup.
            expiry_value = "1m" if score.next_candle_direction else "—"

            rows.append(
                {
                    "pair": symbol,
                    "signal": score.direction,
                    "next_candle": next_candle,
                    "score": score.score,
                    "confidence": f"{score.confidence:.0f}%" if score.confidence else "—",
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
                    "next_candle": "ERROR",
                    "score": 0,
                    "confidence": "—",
                    "expiry": "—",
                    "closed_at": "—",
                    "reason": str(exc),
                }
            )

    # Sort actionable predictions first, then visible next-candle predictions,
    # then pairs with no directional edge. This makes the scanner useful even
    # when the actionability filter rejects most setups.
    def sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
        signal = row["signal"]
        next_candle = row["next_candle"]
        if signal == "CALL":
            bucket = 0
        elif signal == "PUT":
            bucket = 1
        elif next_candle == "UP ↑":
            bucket = 2
        elif next_candle == "DOWN ↓":
            bucket = 3
        elif signal == "ERROR":
            bucket = 5
        else:
            bucket = 4
        return bucket, -int(row["score"]), row["pair"]

    rows.sort(key=sort_key)
    return rows


def run_live_dashboard() -> None:
    import streamlit as st

    st.set_page_config(page_title="Quotex MTF — Live Scanner", page_icon="📡", layout="wide")
    st.title("📡 Live MTF Currency Scanner")
    st.caption(
        "Real-time research analysis from the connected MT5 feed. "
        "It scans every broker-discovered FX pair and predicts the next M1 candle."
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

    calls = sum(row["next_candle"] == "UP ↑" for row in rows)
    puts = sum(row["next_candle"] == "DOWN ↓" for row in rows)
    actionable_calls = sum(row["signal"] == "CALL" for row in rows)
    actionable_puts = sum(row["signal"] == "PUT" for row in rows)
    neutral = sum(row["next_candle"] == "NO SIGNAL" for row in rows)
    errors = sum(row["signal"] == "ERROR" for row in rows)

    metrics = st.columns(6)
    metrics[0].metric("Pairs scanned", len(rows))
    metrics[1].metric("NEXT UP", calls)
    metrics[2].metric("NEXT DOWN", puts)
    metrics[3].metric("Actionable UP", actionable_calls)
    metrics[4].metric("Actionable DOWN", actionable_puts)
    metrics[5].metric("Errors", errors)

    st.divider()
    st.subheader("Next candle prediction")
    st.caption(
        "Prediction target: the next closed M1 candle. UP ↑ = CALL, DOWN ↓ = PUT. "
        "A row can show UP/DOWN prediction while remaining NO_SIGNAL when the stricter actionability gates reject it."
    )
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "pair": "Pair",
            "signal": "Action status",
            "next_candle": "NEXT M1",
            "score": st.column_config.NumberColumn("Score", format="%d"),
            "confidence": "Confidence",
            "expiry": "Horizon",
            "closed_at": "Latest closed M1",
            "reason": "Why",
        },
    )
    st.caption(
        "Confidence is a model-strength score, not a guaranteed probability of winning. "
        "NEXT M1 shows the model's directional prediction separately from the stricter trade/action filter."
    )


if __name__ == "__main__":
    run_live_dashboard()
