import streamlit as st
import os
import yfinance as yf
import pandas as pd
import ta
from huggingface_hub import InferenceClient

# ======================
# إعداد الصفحة
# ======================
st.set_page_config(
    page_title="AI Trading Assistant",
    page_icon="📈",
    layout="wide"
)

st.title("📈 AI Trading Assistant")
st.caption("تحليل فني + ذكاء اصطناعي (HuggingFace)")

# ======================
# HuggingFace TOKEN
# ======================
HF_TOKEN = st.secrets.get("HF_TOKEN") or os.getenv("HF_TOKEN")

if not HF_TOKEN:
    st.error("❌ HuggingFace Token غير موجود")
    st.stop()

client = InferenceClient(
    model="Qwen/Qwen2.5-72B-Instruct",
    token=HF_TOKEN
)

# ======================
# Sidebar
# ======================
with st.sidebar:
    st.header("⚙️ الإعدادات")
    symbol = st.text_input("الأصل", "EURUSD=X")
    timeframe = st.selectbox("الفريم", ["1d", "1h", "15m"])
    analyze = st.button("🔍 تحليل")

# ======================
# تحميل البيانات
# ======================
def load_data(symbol, interval):
    df = yf.download(symbol, period="3mo", interval=interval)
    if df.empty:
        return None
    df.dropna(inplace=True)
    return df

# ======================
# التحليل الفني
# ======================
def technicals(df):
    df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
    macd = ta.trend.MACD(df["Close"])
    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()
    return df.iloc[-1]

# ======================
# تحليل AI
# ======================
def ai_analysis(symbol, price, rsi, macd):
    prompt = f"""
أنت محلل تداول محترف.

الأصل: {symbol}
السعر الحالي: {price}
RSI: {rsi}
MACD: {macd}

أعطني:
1- القرار (شراء / بيع / انتظار)
2- سبب مختصر
3- مستوى المخاطرة

الرد بالعربية.
"""
    response = client.chat_completion(
        messages=[
            {"role": "system", "content": "أنت خبير تداول."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.2
    )
    return response.choices[0].message.content

# ======================
# التنفيذ
# ======================
if analyze:
    with st.spinner("⏳ جاري التحليل..."):
        df = load_data(symbol, timeframe)

        if df is None:
            st.error("❌ لا يمكن جلب البيانات")
        else:
            last = technicals(df)

            price = float(last["Close"])
            rsi = float(last["RSI"])
            macd = float(last["MACD"])

            c1, c2, c3 = st.columns(3)
            c1.metric("السعر", f"{price:.5f}")
            c2.metric("RSI", f"{rsi:.2f}")
            c3.metric("MACD", f"{macd:.5f}")

            st.divider()
            st.subheader("🤖 تحليل الذكاء الاصطناعي")

            result = ai_analysis(symbol, price, rsi, macd)
            st.success(result)

# ======================
# تنبيه قانوني
# ======================
st.divider()
st.warning("⚠️ هذا التطبيق تعليمي فقط وليس نصيحة استثمارية.")