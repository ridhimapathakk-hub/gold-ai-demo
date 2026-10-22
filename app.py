
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="Gold AI Demo",
    page_icon="📈",
    layout="wide"
)

INITIAL_BALANCE = 5000.0

# Safety: this prototype cannot place broker orders.
LIVE_TRADING_ENABLED = False
ORDER_EXECUTION_ENABLED = False

st.title("Gold AI — Demo Research Dashboard")
st.caption(
    "Analysis prototype only | No broker connection | "
    "No orders can be placed"
)

st.warning(
    "CSV candle data only. Signals are experimental, "
    "not financial advice. Live trading is disabled."
)

uploaded = st.file_uploader(
    "Upload XAUUSD M15 candle CSV",
    type=["csv"]
)

st.sidebar.header("Risk settings")
risk_pct = st.sidebar.slider(
    "Illustrative risk per setup (%)",
    min_value=0.1,
    max_value=1.0,
    value=0.5,
    step=0.1
)

rr = st.sidebar.selectbox(
    "Target reward/risk",
    [1.5, 2.0, 3.0],
    index=1
)

if uploaded is None:
    st.info(
        "Upload historical XAUUSD M15 candles to begin. "
        "No sample prices or fake P/L are shown as real."
    )
    st.write(
        "Required columns: time, open, high, low, close"
    )
    st.stop()

try:
    df = pd.read_csv(uploaded)
    df.columns = [c.strip().lower() for c in df.columns]

    required = {
        "time", "open", "high", "low", "close"
    }

    if not required.issubset(df.columns):
        st.error("CSV needs time, open, high, low, close.")
        st.stop()

    df["time"] = pd.to_datetime(
        df["time"], errors="coerce", utc=True
    )

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = (
        df.dropna(subset=[
            "time", "open", "high", "low", "close"
        ])
        .sort_values("time")
        .drop_duplicates("time")
        .set_index("time")
    )

    if len(df) < 250:
        st.error(
            "Please upload at least 250 valid M15 candles."
        )
        st.stop()

    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        st.error("Prices must be positive.")
        st.stop()

    if (
        (df["high"] < df["low"]).any()
        or (df["high"] < df["close"]).any()
        or (df["low"] > df["close"]).any()
        or (df["high"] < df["open"]).any()
        or (df["low"] > df["open"]).any()
    ):
        st.error("Invalid OHLC candle values detected.")
        st.stop()

except Exception as exc:
    st.error(f"Could not read CSV: {exc}")
    st.stop()

# M15 indicators
df["ema20"] = df["close"].ewm(
    span=20, adjust=False
).mean()

df["ema50"] = df["close"].ewm(
    span=50, adjust=False
).mean()

prev_close = df["close"].shift(1)

tr = pd.concat([
    df["high"] - df["low"],
    (df["high"] - prev_close).abs(),
    (df["low"] - prev_close).abs()
], axis=1).max(axis=1)

df["atr14"] = tr.rolling(14).mean()

# Resample candles to H1 using uploaded M15 data.
h1 = df[["open", "high", "low", "close"]].resample(
    "1h", label="right", closed="right"
).agg({
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last"
}).dropna()

h1["ema20"] = h1["close"].ewm(
    span=20, adjust=False
).mean()

h1["ema50"] = h1["close"].ewm(
    span=50, adjust=False
).mean()

# Use the last fully completed H1 candle.
completed_h1 = h1.iloc[:-1]

if len(completed_h1) < 50:
    st.error(
        "Not enough completed H1 history for trend analysis."
    )
    st.stop()

last_h1 = completed_h1.iloc[-1]
last = df.iloc[-1]

if pd.isna(last["atr14"]):
    st.error("ATR calculation unavailable.")
    st.stop()

bullish = (
    last_h1["ema20"] > last_h1["ema50"]
    and last_h1["close"] > last_h1["ema50"]
)

bearish = (
    last_h1["ema20"] < last_h1["ema50"]
    and last_h1["close"] < last_h1["ema50"]
)

direction = (
    "BULLISH" if bullish
    else "BEARISH" if bearish
    else "NEUTRAL"
)

# Basic candidate setup, not a validated A+ strategy.
buy_setup = (
    bullish
    and last["ema20"] > last["ema50"]
    and last["close"] > last["ema20"]
    and last["close"] > last["open"]
)

sell_setup = (
    bearish
    and last["ema20"] < last["ema50"]
    and last["close"] < last["ema20"]
    and last["close"] < last["open"]
)

signal = (
    "BUY CANDIDATE" if buy_setup
    else "SELL CANDIDATE" if sell_setup
    else "NO TRADE"
)

entry = float(last["close"])
atr = float(last["atr14"])

if signal == "BUY CANDIDATE":
    sl = entry - 1.5 * atr
    tp = entry + rr * (entry - sl)
elif signal == "SELL CANDIDATE":
    sl = entry + 1.5 * atr
    tp = entry - rr * (sl - entry)
else:
    sl = np.nan
    tp = np.nan

risk_dollars = INITIAL_BALANCE * risk_pct / 100

st.subheader("Market status")

c1, c2, c3 = st.columns(3)
c1.metric("Reference balance", "$5,000.00")
c2.metric("H1 direction", direction)
c3.metric("Latest setup", signal)

st.caption(
    f"Latest uploaded candle: {df.index[-1]} | "
    "Check data freshness and broker timezone."
)

if signal != "NO TRADE":
    st.subheader("Illustrative trade plan")

    c1, c2, c3 = st.columns(3)
    c1.metric("Entry reference", f"{entry:.3f}")
    c2.metric("Stop loss reference", f"{sl:.3f}")
    c3.metric("Take profit reference", f"{tp:.3f}")

    st.write(
        f"Illustrative risk budget: ${risk_dollars:.2f}"
    )

    st.write(
        "Position size is intentionally not calculated: "
        "broker contract size, tick value, account currency, "
        "volume step and execution costs must be verified."
    )
else:
    st.info("No qualifying setup on the latest uploaded candle.")

st.subheader("Recent candles")
st.line_chart(df[["close", "ema20", "ema50"]].tail(150))

st.subheader("Safety status")
st.write("Live trading enabled:", LIVE_TRADING_ENABLED)
st.write("Order execution enabled:", ORDER_EXECUTION_ENABLED)

st.subheader("Data quality")
st.write(f"Valid M15 candles: {len(df)}")
st.write(f"Completed H1 candles: {len(completed_h1)}")
st.write("Broker connection: NOT CONNECTED")
st.write("Execution status: DISABLED")
