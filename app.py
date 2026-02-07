import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import numpy as np
from huggingface_hub import InferenceClient
import json
import time
from datetime import datetime
import importlib
import threading

import db
importlib.reload(db)

# ============================================================
# 1. إعداد الصفحة
# ============================================================
st.set_page_config(
    page_title="ProTrade Elite 5.0",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="collapsed"
)

try:
    db.init_db()
except Exception as e:
    st.error(f"خطأ في قاعدة البيانات: {e}")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        line-height: 1.6 !important;
    }
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
        display: none !important; visibility: hidden !important;
    }
    [data-testid="stToolbar"], footer, header[data-testid="stHeader"] {
        visibility: hidden !important;
    }
    .main-signal {
        padding: 25px; border-radius: 15px; text-align: center;
        font-size: 24px; font-weight: bold; color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2); margin-bottom: 20px;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .bg-strong-buy {background: linear-gradient(135deg, #00b09b, #96c93d);}
    .bg-buy {background: linear-gradient(135deg, #11998e, #38ef7d);}
    .bg-strong-sell {background: linear-gradient(135deg, #cb2d3e, #ef473a);}
    .bg-sell {background: linear-gradient(135deg, #e53935, #ff6f60);}
    .bg-neutral {background: linear-gradient(135deg, #536976, #292E49);}
    .rec-card {
        background: #1f2937; border-radius: 12px; padding: 15px; margin: 10px 0;
        border: 1px solid #374151; color: white;
    }
    .filter-pass { color: #00ff88; }
    .filter-fail { color: #ff4444; }
    .filter-warn { color: #ffaa00; }
    .score-bar {
        height: 8px; border-radius: 4px; margin: 2px 0;
        background: #374151;
    }
    .score-fill {
        height: 100%; border-radius: 4px;
        transition: width 0.5s;
    }
    .detail-card {
        background: #111827; border-radius: 10px; padding: 12px;
        margin: 5px 0; border: 1px solid #1f2937;
    }
    .stChatMessage {direction: rtl;}
    .scan-notify {
        position: fixed; top: 20px; right: 20px; z-index: 9999;
        background: #065f46; color: white; padding: 15px 25px;
        border-radius: 12px; font-weight: bold; font-size: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        animation: slideIn 0.5s ease;
    }
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 2. البيانات والأصول
# ============================================================
def init_session_state():
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'current_view' not in st.session_state:
        st.session_state.current_view = "analysis"
    if 'scan_running' not in st.session_state:
        st.session_state.scan_running = False
    if 'scan_complete' not in st.session_state:
        st.session_state.scan_complete = False
    if 'scan_results' not in st.session_state:
        st.session_state.scan_results = 0
    if 'expanded_signal' not in st.session_state:
        st.session_state.expanded_signal = None

init_session_state()

FOREX_PAIRS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "USD/CHF": "USDCHF=X", "AUD/USD": "AUDUSD=X", "NZD/USD": "NZDUSD=X",
    "USD/CAD": "USDCAD=X", "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X", "Gold": "GC=F", "Silver": "SI=F", "Oil": "CL=F"
}
CRYPTO_PAIRS = {
    "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "SOL/USD": "SOL-USD",
    "XRP/USD": "XRP-USD", "BNB/USD": "BNB-USD", "ADA/USD": "ADA-USD",
    "DOGE/USD": "DOGE-USD", "DOT/USD": "DOT-USD", "AVAX/USD": "AVAX-USD",
    "MATIC/USD": "MATIC-USD"
}
STOCKS = {
    "Apple": "AAPL", "Tesla": "TSLA", "NVIDIA": "NVDA", "Google": "GOOGL",
    "Amazon": "AMZN", "Microsoft": "MSFT", "Meta": "META", "Netflix": "NFLX",
    "AMD": "AMD", "Intel": "INTC"
}
TIMEFRAMES = {
    "15 دقيقة": {"interval": "15m", "period": "5d"},
    "1 ساعة": {"interval": "1h", "period": "1mo"},
    "4 ساعات": {"interval": "1h", "period": "3mo"},
    "يومي": {"interval": "1d", "period": "1y"},
}
TV_INTERVALS = {
    "15 دقيقة": "15", "1 ساعة": "60",
    "4 ساعات": "240", "يومي": "D"
}

def to_tv_symbol(ticker):
    if ticker.endswith("=X"):
        return f"FX:{ticker.replace('=X', '')}"
    if ticker.endswith("-USD"):
        return f"CRYPTO:{ticker.replace('-USD', '')}USD"
    if ticker == "GC=F": return "COMEX:GC1!"
    if ticker == "SI=F": return "COMEX:SI1!"
    if ticker == "CL=F": return "NYMEX:CL1!"
    return f"NASDAQ:{ticker}"

# ============================================================
# 3. الذكاء الاصطناعي
# ============================================================
client = None
try:
    token = st.secrets.get("HF_TOKEN", "")
    if token:
        client = InferenceClient(model="Qwen/Qwen2.5-72B-Instruct", token=token)
except Exception:
    client = None

# ============================================================
# 4. دوال التحليل المتقدم
# ============================================================
def safe_val(value, default=0.0):
    try:
        v = float(value)
        return default if (np.isnan(v) or np.isinf(v)) else v
    except (TypeError, ValueError):
        return default


def fetch_data(ticker, tf_key):
    ticker = ticker.strip().upper()
    tf = TIMEFRAMES[tf_key]
    try:
        stock = yf.Ticker(ticker)
        if tf_key == "4 ساعات":
            raw_df = stock.history(period="3mo", interval="1h")
            if not raw_df.empty:
                if raw_df.index.tz is not None:
                    raw_df.index = raw_df.index.tz_localize(None)
                df = raw_df.resample('4h').agg({
                    'Open': 'first', 'High': 'max',
                    'Low': 'min', 'Close': 'last',
                    'Volume': 'sum'
                }).dropna()
            else:
                return None, None
        else:
            df = stock.history(period=tf["period"], interval=tf["interval"],
                               auto_adjust=True)
        if df is not None and len(df) > 15:
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            try:
                info = stock.info
            except Exception:
                info = {}
            return df, info
    except Exception:
        pass
    return None, None


def calculate_indicators(df):
    c = df['Close']
    h = df['High']
    low = df['Low']
    vol = df['Volume'] if 'Volume' in df.columns else None

    # EMAs
    for w in [5, 10, 20, 50, 100, 200]:
        try:
            df[f'EMA_{w}'] = ta.trend.ema_indicator(c, window=w)
        except Exception:
            pass

    # SMA
    for w in [20, 50, 200]:
        try:
            df[f'SMA_{w}'] = ta.trend.sma_indicator(c, window=w)
        except Exception:
            pass

    # MACD
    try:
        macd_obj = ta.trend.MACD(c)
        df['MACD'] = macd_obj.macd()
        df['MACD_Signal'] = macd_obj.macd_signal()
        df['MACD_Hist'] = macd_obj.macd_diff()
    except Exception:
        pass

    # RSI
    try:
        df['RSI'] = ta.momentum.rsi(c, window=14)
    except Exception:
        pass

    # Stochastic
    try:
        stoch = ta.momentum.StochasticOscillator(h, low, c)
        df['Stoch_K'] = stoch.stoch()
        df['Stoch_D'] = stoch.stoch_signal()
    except Exception:
        pass

    # Bollinger Bands
    try:
        bb = ta.volatility.BollingerBands(c, window=20)
        df['BB_Upper'] = bb.bollinger_hband()
        df['BB_Lower'] = bb.bollinger_lband()
        df['BB_Mid'] = bb.bollinger_mavg()
        df['BB_Width'] = bb.bollinger_wband()
    except Exception:
        pass

    # ATR
    try:
        df['ATR'] = ta.volatility.average_true_range(h, low, c)
    except Exception:
        pass

    # ADX
    try:
        adx_obj = ta.trend.ADXIndicator(h, low, c)
        df['ADX'] = adx_obj.adx()
        df['DI_plus'] = adx_obj.adx_pos()
        df['DI_minus'] = adx_obj.adx_neg()
    except Exception:
        pass

    # PSAR
    try:
        df['PSAR'] = ta.trend.PSARIndicator(h, low, c).psar()
    except Exception:
        pass

    # Ichimoku
    try:
        ich = ta.trend.IchimokuIndicator(h, low)
        df['Ich_A'] = ich.ichimoku_a()
        df['Ich_B'] = ich.ichimoku_b()
    except Exception:
        pass

    # CCI
    try:
        df['CCI'] = ta.trend.cci(h, low, c, window=20)
    except Exception:
        pass

    # Williams %R
    try:
        df['Williams_R'] = ta.momentum.williams_r(h, low, c)
    except Exception:
        pass

    # MFI (Money Flow Index)
    if vol is not None:
        try:
            df['MFI'] = ta.volume.money_flow_index(h, low, c, vol)
        except Exception:
            pass

    # OBV
    if vol is not None:
        try:
            df['OBV'] = ta.volume.on_balance_volume(c, vol)
        except Exception:
            pass

    # VWAP approximation
    if vol is not None:
        try:
            df['VWAP'] = (vol * (h + low + c) / 3).cumsum() / vol.cumsum()
        except Exception:
            pass

    # ROC (Rate of Change)
    try:
        df['ROC'] = ta.momentum.roc(c, window=12)
    except Exception:
        pass

    # Momentum
    try:
        df['Momentum'] = c - c.shift(10)
    except Exception:
        pass

    return df


# ============================================================
# نظام الفلاتر المتقدم (18 فلتر)
# ============================================================

def apply_all_filters(df, info):
    """تطبيق 18 فلتر وإرجاع النتيجة التفصيلية"""
    curr = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else curr
    price = safe_val(curr['Close'])
    filters = []
    total_score = 0

    # ====== مجموعة 1: فلاتر الاتجاه (Trend Filters) ======

    # فلتر 1: EMA 50/200 Cross (Golden/Death)
    ema50 = safe_val(curr.get('EMA_50'))
    ema200 = safe_val(curr.get('EMA_200'))
    if ema50 > 0 and ema200 > 0:
        if ema50 > ema200:
            filters.append(("تقاطع ذهبي EMA50/200", 10, "pass", "الترند صاعد قوي"))
            total_score += 10
        else:
            filters.append(("تقاطع الموت EMA50/200", -10, "fail", "الترند هابط"))
            total_score -= 10
    else:
        filters.append(("EMA50/200 غير متوفر", 0, "warn", "بيانات غير كافية"))

    # فلتر 2: السعر فوق/تحت EMA 200
    if ema200 > 0:
        if price > ema200:
            filters.append(("السعر فوق EMA200", 8, "pass", f"السعر {price:.4f} > EMA200 {ema200:.4f}"))
            total_score += 8
        else:
            filters.append(("السعر تحت EMA200", -8, "fail", f"السعر {price:.4f} < EMA200 {ema200:.4f}"))
            total_score -= 8

    # فلتر 3: ترتيب EMAs (5>10>20>50)
    ema5 = safe_val(curr.get('EMA_5'))
    ema10 = safe_val(curr.get('EMA_10'))
    ema20 = safe_val(curr.get('EMA_20'))
    if all(v > 0 for v in [ema5, ema10, ema20, ema50]):
        if ema5 > ema10 > ema20 > ema50:
            filters.append(("ترتيب EMAs صعودي مثالي", 7, "pass", "5>10>20>50"))
            total_score += 7
        elif ema5 < ema10 < ema20 < ema50:
            filters.append(("ترتيب EMAs هبوطي مثالي", -7, "fail", "5<10<20<50"))
            total_score -= 7
        else:
            filters.append(("ترتيب EMAs مختلط", 0, "warn", "لا ترتيب واضح"))

    # فلتر 4: ADX قوة الاتجاه
    adx = safe_val(curr.get('ADX'))
    di_plus = safe_val(curr.get('DI_plus'))
    di_minus = safe_val(curr.get('DI_minus'))
    if adx > 0:
        if adx > 30 and di_plus > di_minus:
            filters.append(("ADX ترند صاعد قوي جداً", 8, "pass", f"ADX={adx:.0f} DI+>DI-"))
            total_score += 8
        elif adx > 30 and di_minus > di_plus:
            filters.append(("ADX ترند هابط قوي جداً", -8, "fail", f"ADX={adx:.0f} DI->DI+"))
            total_score -= 8
        elif adx > 20:
            if di_plus > di_minus:
                filters.append(("ADX ترند صاعد متوسط", 4, "pass", f"ADX={adx:.0f}"))
                total_score += 4
            else:
                filters.append(("ADX ترند هابط متوسط", -4, "fail", f"ADX={adx:.0f}"))
                total_score -= 4
        else:
            filters.append(("ADX بدون ترند واضح", 0, "warn", f"ADX={adx:.0f} ضعيف"))

    # فلتر 5: PSAR
    psar = safe_val(curr.get('PSAR'))
    if psar > 0:
        if price > psar:
            filters.append(("PSAR صعودي", 5, "pass", f"السعر فوق PSAR"))
            total_score += 5
        else:
            filters.append(("PSAR هبوطي", -5, "fail", f"السعر تحت PSAR"))
            total_score -= 5

    # فلتر 6: Ichimoku Cloud
    icha = safe_val(curr.get('Ich_A'))
    ichb = safe_val(curr.get('Ich_B'))
    if icha > 0 and ichb > 0:
        cloud_top = max(icha, ichb)
        cloud_bot = min(icha, ichb)
        if price > cloud_top:
            filters.append(("فوق سحابة إيشيموكو", 6, "pass", "إشارة صعودية قوية"))
            total_score += 6
        elif price < cloud_bot:
            filters.append(("تحت سحابة إيشيموكو", -6, "fail", "إشارة هبوطية قوية"))
            total_score -= 6
        else:
            filters.append(("داخل سحابة إيشيموكو", 0, "warn", "منطقة حيرة"))

    # ====== مجموعة 2: فلاتر الزخم (Momentum Filters) ======

    # فلتر 7: RSI
    rsi = safe_val(curr.get('RSI'))
    if rsi > 0:
        if rsi < 25:
            filters.append(("RSI تشبع بيعي شديد", 10, "pass", f"RSI={rsi:.0f} فرصة شراء"))
            total_score += 10
        elif rsi < 35:
            filters.append(("RSI قريب من التشبع البيعي", 5, "pass", f"RSI={rsi:.0f}"))
            total_score += 5
        elif rsi > 75:
            filters.append(("RSI تشبع شرائي شديد", -10, "fail", f"RSI={rsi:.0f} فرصة بيع"))
            total_score -= 10
        elif rsi > 65:
            filters.append(("RSI قريب من التشبع الشرائي", -5, "fail", f"RSI={rsi:.0f}"))
            total_score -= 5
        else:
            filters.append(("RSI منطقة متوسطة", 0, "warn", f"RSI={rsi:.0f}"))

    # فلتر 8: MACD
    macd_hist = safe_val(curr.get('MACD_Hist'))
    macd_hist_prev = safe_val(prev.get('MACD_Hist')) if hasattr(prev, 'get') else 0
    if macd_hist > 0 and macd_hist_prev <= 0:
        filters.append(("MACD تقاطع صعودي جديد", 8, "pass", "تحول إيجابي"))
        total_score += 8
    elif macd_hist < 0 and macd_hist_prev >= 0:
        filters.append(("MACD تقاطع هبوطي جديد", -8, "fail", "تحول سلبي"))
        total_score -= 8
    elif macd_hist > 0:
        filters.append(("MACD إيجابي", 4, "pass", "استمرار صعودي"))
        total_score += 4
    else:
        filters.append(("MACD سلبي", -4, "fail", "استمرار هبوطي"))
        total_score -= 4

    # فلتر 9: Stochastic
    stoch_k = safe_val(curr.get('Stoch_K'))
    stoch_d = safe_val(curr.get('Stoch_D'))
    if stoch_k > 0:
        if stoch_k < 20 and stoch_k > stoch_d:
            filters.append(("Stochastic تشبع بيعي + تقاطع صعودي", 7, "pass",
                            f"K={stoch_k:.0f} D={stoch_d:.0f}"))
            total_score += 7
        elif stoch_k > 80 and stoch_k < stoch_d:
            filters.append(("Stochastic تشبع شرائي + تقاطع هبوطي", -7, "fail",
                            f"K={stoch_k:.0f} D={stoch_d:.0f}"))
            total_score -= 7
        elif stoch_k < 20:
            filters.append(("Stochastic تشبع بيعي", 4, "pass", f"K={stoch_k:.0f}"))
            total_score += 4
        elif stoch_k > 80:
            filters.append(("Stochastic تشبع شرائي", -4, "fail", f"K={stoch_k:.0f}"))
            total_score -= 4

    # فلتر 10: CCI
    cci = safe_val(curr.get('CCI'))
    if cci != 0:
        if cci < -200:
            filters.append(("CCI تشبع بيعي حاد", 6, "pass", f"CCI={cci:.0f}"))
            total_score += 6
        elif cci > 200:
            filters.append(("CCI تشبع شرائي حاد", -6, "fail", f"CCI={cci:.0f}"))
            total_score -= 6
        elif cci < -100:
            filters.append(("CCI منطقة بيع", 3, "pass", f"CCI={cci:.0f}"))
            total_score += 3
        elif cci > 100:
            filters.append(("CCI منطقة شراء مفرط", -3, "fail", f"CCI={cci:.0f}"))
            total_score -= 3

    # فلتر 11: Williams %R
    williams = safe_val(curr.get('Williams_R'))
    if williams != 0:
        if williams < -80:
            filters.append(("Williams تشبع بيعي", 4, "pass", f"W%R={williams:.0f}"))
            total_score += 4
        elif williams > -20:
            filters.append(("Williams تشبع شرائي", -4, "fail", f"W%R={williams:.0f}"))
            total_score -= 4

    # فلتر 12: ROC (Rate of Change)
    roc = safe_val(curr.get('ROC'))
    if roc != 0:
        if roc > 5:
            filters.append(("زخم صعودي قوي ROC", 5, "pass", f"ROC={roc:.1f}%"))
            total_score += 5
        elif roc < -5:
            filters.append(("زخم هبوطي قوي ROC", -5, "fail", f"ROC={roc:.1f}%"))
            total_score -= 5

    # ====== مجموعة 3: فلاتر التذبذب (Volatility Filters) ======

    # فلتر 13: Bollinger Bands
    bb_upper = safe_val(curr.get('BB_Upper'))
    bb_lower = safe_val(curr.get('BB_Lower'))
    if bb_upper > 0 and bb_lower > 0:
        if price <= bb_lower:
            filters.append(("السعر عند Bollinger السفلي", 6, "pass", "فرصة ارتداد صعودي"))
            total_score += 6
        elif price >= bb_upper:
            filters.append(("السعر عند Bollinger العلوي", -6, "fail", "فرصة ارتداد هبوطي"))
            total_score -= 6
        else:
            bb_pos = (price - bb_lower) / (bb_upper - bb_lower) * 100 if (bb_upper - bb_lower) > 0 else 50
            filters.append(("موقع Bollinger", 0, "warn", f"في {bb_pos:.0f}% من النطاق"))

    # فلتر 14: ATR Volatility
    atr = safe_val(curr.get('ATR'))
    if atr > 0 and price > 0:
        atr_pct = (atr / price) * 100
        if atr_pct > 3:
            filters.append(("تذبذب عالي جداً ATR", -3, "warn", f"ATR={atr_pct:.1f}% خطر مرتفع"))
            total_score -= 3
        elif atr_pct < 0.5:
            filters.append(("تذبذب منخفض جداً ATR", -2, "warn", f"ATR={atr_pct:.1f}% حركة محدودة"))
            total_score -= 2
        else:
            filters.append(("تذبذب مناسب ATR", 3, "pass", f"ATR={atr_pct:.1f}%"))
            total_score += 3

    # ====== مجموعة 4: فلاتر الحجم (Volume Filters) ======

    # فلتر 15: MFI
    mfi = safe_val(curr.get('MFI'))
    if mfi > 0:
        if mfi < 20:
            filters.append(("MFI تشبع بيعي", 5, "pass", f"MFI={mfi:.0f}"))
            total_score += 5
        elif mfi > 80:
            filters.append(("MFI تشبع شرائي", -5, "fail", f"MFI={mfi:.0f}"))
            total_score -= 5
        else:
            filters.append(("MFI منطقة عادية", 0, "warn", f"MFI={mfi:.0f}"))

    # فلتر 16: OBV Trend
    if 'OBV' in df.columns and len(df) > 5:
        try:
            obv_now = safe_val(curr.get('OBV'))
            obv_5ago = safe_val(df.iloc[-5].get('OBV'))
            if obv_now > obv_5ago and price > safe_val(df.iloc[-5]['Close']):
                filters.append(("OBV يؤكد الصعود", 4, "pass", "حجم يدعم السعر"))
                total_score += 4
            elif obv_now < obv_5ago and price < safe_val(df.iloc[-5]['Close']):
                filters.append(("OBV يؤكد الهبوط", -4, "fail", "حجم يدعم الهبوط"))
                total_score -= 4
            elif obv_now < obv_5ago and price > safe_val(df.iloc[-5]['Close']):
                filters.append(("تباعد سلبي OBV", -3, "warn", "السعر يصعد والحجم يهبط"))
                total_score -= 3
        except Exception:
            pass

    # ====== مجموعة 5: فلاتر النماذج (Pattern Filters) ======

    # فلتر 17: الشموع - Engulfing
    if len(df) > 2:
        try:
            curr_open = safe_val(curr.get('Open'))
            curr_close = safe_val(curr['Close'])
            prev_open = safe_val(prev.get('Open'))
            prev_close = safe_val(prev['Close'])

            if (prev_close < prev_open and curr_close > curr_open and
                    curr_close > prev_open and curr_open < prev_close):
                filters.append(("نموذج ابتلاع صعودي", 7, "pass", "إشارة انعكاس قوية"))
                total_score += 7
            elif (prev_close > prev_open and curr_close < curr_open and
                  curr_close < prev_open and curr_open > prev_close):
                filters.append(("نموذج ابتلاع هبوطي", -7, "fail", "إشارة انعكاس قوية"))
                total_score -= 7
        except Exception:
            pass

    # فلتر 18: دعم ومقاومة ديناميكي
    if len(df) > 20:
        try:
            recent_high = df['High'].tail(20).max()
            recent_low = df['Low'].tail(20).min()
            price_range = recent_high - recent_low
            if price_range > 0:
                position = (price - recent_low) / price_range
                if position < 0.15:
                    filters.append(("قريب من دعم قوي", 6, "pass",
                                    f"في {position*100:.0f}% من النطاق"))
                    total_score += 6
                elif position > 0.85:
                    filters.append(("قريب من مقاومة قوية", -6, "fail",
                                    f"في {position*100:.0f}% من النطاق"))
                    total_score -= 6
                else:
                    filters.append(("بين الدعم والمقاومة", 0, "warn",
                                    f"في {position*100:.0f}% من النطاق"))
        except Exception:
            pass

    return total_score, filters, curr


def get_fundamental_score(info):
    """تحليل أساسي مبسط من بيانات yfinance"""
    score = 0
    details = []

    if not info or not isinstance(info, dict):
        return 0, [("بيانات أساسية غير متوفرة", 0, "warn", "")]

    # P/E Ratio
    pe = info.get('trailingPE') or info.get('forwardPE')
    if pe:
        pe = float(pe)
        if 5 < pe < 20:
            score += 5
            details.append(("P/E مناسب", 5, "pass", f"P/E={pe:.1f}"))
        elif pe > 40:
            score -= 3
            details.append(("P/E مرتفع جداً", -3, "fail", f"P/E={pe:.1f}"))
        elif pe < 5:
            details.append(("P/E منخفض جداً", 0, "warn", f"P/E={pe:.1f} قد يكون خطر"))

    # Profit Margin
    margin = info.get('profitMargins')
    if margin:
        margin_pct = float(margin) * 100
        if margin_pct > 20:
            score += 4
            details.append(("هامش ربح ممتاز", 4, "pass", f"{margin_pct:.1f}%"))
        elif margin_pct > 10:
            score += 2
            details.append(("هامش ربح جيد", 2, "pass", f"{margin_pct:.1f}%"))
        elif margin_pct < 0:
            score -= 4
            details.append(("الشركة خاسرة", -4, "fail", f"{margin_pct:.1f}%"))

    # Revenue Growth
    growth = info.get('revenueGrowth')
    if growth:
        growth_pct = float(growth) * 100
        if growth_pct > 20:
            score += 4
            details.append(("نمو إيرادات ممتاز", 4, "pass", f"{growth_pct:.1f}%"))
        elif growth_pct > 5:
            score += 2
            details.append(("نمو إيرادات جيد", 2, "pass", f"{growth_pct:.1f}%"))
        elif growth_pct < -5:
            score -= 3
            details.append(("انخفاض الإيرادات", -3, "fail", f"{growth_pct:.1f}%"))

    # Debt to Equity
    de = info.get('debtToEquity')
    if de:
        de = float(de)
        if de < 50:
            score += 3
            details.append(("ديون منخفضة", 3, "pass", f"D/E={de:.0f}"))
        elif de > 200:
            score -= 3
            details.append(("ديون مرتفعة جداً", -3, "fail", f"D/E={de:.0f}"))

    # Market Cap
    mcap = info.get('marketCap')
    if mcap:
        mcap_b = mcap / 1e9
        if mcap_b > 100:
            score += 2
            details.append(("شركة عملاقة", 2, "pass", f"${mcap_b:.0f}B"))
        elif mcap_b > 10:
            score += 1
            details.append(("شركة كبيرة", 1, "pass", f"${mcap_b:.0f}B"))

    # 52 Week position
    high52 = info.get('fiftyTwoWeekHigh')
    low52 = info.get('fiftyTwoWeekLow')
    curr_price = info.get('currentPrice') or info.get('regularMarketPrice')
    if high52 and low52 and curr_price:
        pos = (float(curr_price) - float(low52)) / (float(high52) - float(low52)) if (float(high52) - float(low52)) > 0 else 0.5
        if pos < 0.3:
            score += 3
            details.append(("قريب من أدنى 52 أسبوع", 3, "pass", f"في {pos*100:.0f}%"))
        elif pos > 0.9:
            score -= 2
            details.append(("قريب من أعلى 52 أسبوع", -2, "warn", f"في {pos*100:.0f}%"))

    if not details:
        details.append(("لا توجد بيانات أساسية كافية", 0, "warn", ""))

    return score, details


def get_news_score(ai_client, ticker, asset_name):
    """تحليل الأخبار عبر الذكاء الاصطناعي"""
    if not ai_client:
        return 0, [("محلل الأخبار غير مفعل", 0, "warn", "يحتاج HF_TOKEN")]

    prompt = f"""حلل الوضع الإخباري الحالي لـ {asset_name} ({ticker}).
بناءً على معرفتك بالأحداث الاقتصادية والجيوسياسية الأخيرة.

أجب بتنسيق JSON فقط:
{{"news_sentiment": "إيجابي أو سلبي أو محايد", "score": رقم من -10 إلى 10, "key_events": ["حدث1", "حدث2"], "impact": "وصف مختصر للتأثير بالعربية"}}"""

    try:
        resp = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "محلل أخبار مالية. أجب JSON فقط. بدون كود."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250
        )
        txt = resp.choices[0].message.content.strip()
        if "```" in txt:
            parts = txt.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    txt = part
                    break
        data = json.loads(txt)
        n_score = int(data.get('score', 0))
        sentiment = data.get('news_sentiment', 'محايد')
        impact = data.get('impact', '')
        events = data.get('key_events', [])

        details = []
        status = "pass" if n_score > 0 else ("fail" if n_score < 0 else "warn")
        details.append((f"الأخبار: {sentiment}", n_score, status, impact))
        for ev in events[:3]:
            details.append((f"📰 {ev}", 0, "warn", ""))
        return n_score, details
    except Exception:
        return 0, [("فشل تحليل الأخبار", 0, "warn", "")]


def get_ai_final_decision(ai_client, ticker, name, tech_score, fund_score,
                           news_score, filters, price, direction_hint):
    """القرار النهائي من الذكاء الاصطناعي"""
    if not ai_client:
        return None

    top_filters = [f"{f[0]}({f[1]})" for f in filters[:8]]
    filters_txt = " | ".join(top_filters)

    prompt = f"""بصفتك خبير تداول محترف، قم باتخاذ القرار النهائي:

الأصل: {name} ({ticker})
السعر: {price}

النتائج:
- التحليل الفني: {tech_score} نقطة
- التحليل الأساسي: {fund_score} نقطة  
- تحليل الأخبار: {news_score} نقطة
- الاتجاه المبدئي: {"صعودي" if direction_hint > 0 else "هبوطي" if direction_hint < 0 else "محايد"}

أهم الفلاتر: {filters_txt}

المطلوب: قرار نهائي صارم. لا توصي إلا إذا كنت واثقاً 80%+

أجب JSON فقط:
{{"decision": "شراء قوي أو شراء أو بيع قوي أو بيع أو تجنب", "confidence": رقم من 0 لـ 100, "reasoning": "تحليل مختصر بالعربية في 2-3 جمل", "risk": "منخفض أو متوسط أو عالي", "ai_score": رقم من -15 لـ 15}}"""

    try:
        resp = ai_client.chat_completion(
            messages=[
                {"role": "system",
                 "content": "أنت خبير تداول. قراراتك يعتمد عليها. أجب JSON فقط. بدون كود."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300
        )
        txt = resp.choices[0].message.content.strip()
        if "```" in txt:
            parts = txt.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    txt = part
                    break
        return json.loads(txt)
    except Exception:
        return None


def calc_targets(curr, total_score):
    price = safe_val(curr['Close'])
    atr = safe_val(curr.get('ATR'))
    if atr == 0:
        atr = price * 0.015
    is_buy = total_score > 0
    factor = 1 if is_buy else -1
    sl = price - (2 * atr * factor)
    tp1 = price + (1.5 * atr * factor)
    tp2 = price + (3 * atr * factor)
    tp3 = price + (5 * atr * factor)
    risk = abs(price - sl)
    rr = abs(tp2 - price) / risk if risk > 0 else 0
    return {'sl': sl, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'rr': rr}


def final_signal(combined):
    if combined >= 40:
        return "شراء قوي", "bg-strong-buy"
    elif combined >= 20:
        return "شراء", "bg-buy"
    elif combined <= -40:
        return "بيع قوي", "bg-strong-sell"
    elif combined <= -20:
        return "بيع", "bg-sell"
    return "محايد", "bg-neutral"


def get_ai_verdict(ai_client, ticker, ts, td, curr):
    if not ai_client:
        return None
    tech_txt = ", ".join([t[0] for t in td[:5]])
    prompt = f"""حلل {ticker}:
السعر: {safe_val(curr['Close'])}
الفني: {ts} نقاط ({tech_txt})
أجب JSON فقط:
{{"final_decision": "شراء/بيع/محايد", "reasoning": "سبب بالعربية", "risk_level": "منخفض/متوسط/عالي"}}"""
    try:
        resp = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "محلل مالي. أجب JSON فقط. بدون كود."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200
        )
        txt = resp.choices[0].message.content.strip()
        if "```" in txt:
            parts = txt.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    txt = part
                    break
        return json.loads(txt)
    except Exception:
        return None


# ============================================================
# دالة المسح الشامل (تعمل في الخلفية)
# ============================================================
def run_deep_scan(assets_dict, timeframe, ai_client):
    """مسح شامل للأصول المختارة"""
    total = len(assets_dict)
    found = 0
    scanned = 0

    db.set_scan_status(True, 0, total, 0, 0, 'بدء المسح...', '')

    for name, tick in assets_dict.items():
        scanned += 1
        db.set_scan_status(True, (scanned/total)*100, total, scanned, found, name)

        try:
            df, info = fetch_data(tick, timeframe)
            if df is None or len(df) <= 15:
                continue

            df = calculate_indicators(df)

            # 1. التحليل الفني (18 فلتر)
            tech_score, tech_filters, curr = apply_all_filters(df, info)

            # 2. التحليل الأساسي
            fund_score, fund_details = get_fundamental_score(info)

            # 3. تحليل الأخبار
            news_score, news_details = get_news_score(ai_client, tick, name)

            # المجموع المبدئي
            pre_total = tech_score + fund_score + news_score

            # 4. القرار النهائي من AI
            ai_decision = get_ai_final_decision(
                ai_client, tick, name, tech_score, fund_score,
                news_score, tech_filters, safe_val(curr['Close']), pre_total
            )

            ai_score = 0
            ai_reasoning = ""
            ai_confidence = 0
            if ai_decision and isinstance(ai_decision, dict):
                ai_score = int(ai_decision.get('ai_score', 0))
                ai_reasoning = ai_decision.get('reasoning', '')
                ai_confidence = int(ai_decision.get('confidence', 0))
                decision_txt = ai_decision.get('decision', 'تجنب')

                # فقط إذا AI واثق 70%+
                if ai_confidence < 70 or decision_txt == 'تجنب':
                    continue

            final_total = pre_total + ai_score

            # الحد الأدنى للإشارة القوية
            if abs(final_total) < 25:
                continue

            # تحديد الاتجاه
            direction = "buy" if final_total > 0 else "sell"
            tgts = calc_targets(curr, final_total)
            price = safe_val(curr['Close'])

            # تجميع تفاصيل الفلاتر
            all_filters = []
            all_filters.append("═══ التحليل الفني ═══")
            for f in tech_filters:
                icon = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
                all_filters.append(f"{icon} {f[0]} ({f[1]:+d}) - {f[3]}")
            all_filters.append(f"\n═══ التحليل الأساسي ({fund_score:+d}) ═══")
            for f in fund_details:
                icon = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
                all_filters.append(f"{icon} {f[0]} ({f[1]:+d}) - {f[3]}")
            all_filters.append(f"\n═══ الأخبار ({news_score:+d}) ═══")
            for f in news_details:
                icon = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
                all_filters.append(f"{icon} {f[0]} ({f[1]:+d}) - {f[3]}")
            all_filters.append(f"\n═══ قرار AI ({ai_score:+d}) ═══")
            all_filters.append(f"🤖 {ai_reasoning}")
            all_filters.append(f"📊 الثقة: {ai_confidence}%")

            filters_text = "\n".join(all_filters)

            if price > 0:
                added = db.add_signal(
                    str(tick), str(name), str(direction),
                    float(price),
                    float(tgts['tp1']), float(tgts['tp2']), float(tgts['tp3']),
                    float(tgts['sl']), float(abs(final_total)),
                    str(timeframe), float(tech_score), float(fund_score),
                    float(news_score), float(ai_score),
                    str(filters_text), str(ai_reasoning)
                )
                if added:
                    found += 1

        except Exception:
            continue

        # تأخير لتجنب rate limiting
        time.sleep(0.5)

    db.set_scan_status(False, 100, total, scanned, found, 'اكتمل المسح')


# ============================================================
# 5. واجهة التطبيق
# ============================================================
st.title("ProTrade Elite 5.0 📊")

# التحقق من db
required_funcs = ['init_db', 'add_signal', 'get_active_signals',
                  'get_closed_signals', 'update_signal_status',
                  'save_analysis', 'set_scan_status', 'get_scan_status']
missing_funcs = [f for f in required_funcs if not hasattr(db, f)]
if missing_funcs:
    st.error(f"⚠️ db.py ناقص: {', '.join(missing_funcs)}")
    st.stop()

# إشعار انتهاء المسح
scan_status = db.get_scan_status()
if scan_status and not scan_status['is_running'] and scan_status['found_signals'] > 0:
    if st.session_state.get('scan_running', False):
        st.session_state.scan_running = False
        st.session_state.scan_complete = True
        st.session_state.scan_results = scan_status['found_signals']

if st.session_state.get('scan_complete', False):
    st.markdown(f"""
    <div class="scan-notify">
        ✅ اكتمل المسح! تم العثور على {st.session_state.scan_results} إشارة قوية
    </div>
    """, unsafe_allow_html=True)
    st.session_state.scan_complete = False

# القائمة
with st.expander("☰ القائمة الرئيسية", expanded=False):
    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if st.button("📋 التوصيات اليومية", use_container_width=True):
            st.session_state.current_view = "signals"
            st.rerun()
    with nav2:
        if st.button("📉 التحليل الفني", use_container_width=True):
            st.session_state.current_view = "analysis"
            st.rerun()
    with nav3:
        if st.button("🤖 الدردشة الذكية", use_container_width=True):
            st.session_state.current_view = "chat"
            st.rerun()

# شريط حالة المسح (يظهر في كل الصفحات)
if scan_status and scan_status['is_running']:
    st.info(f"🔄 جاري المسح... {scan_status['current_asset']} "
            f"({scan_status['scanned_assets']}/{scan_status['total_assets']}) "
            f"- وجد {scan_status['found_signals']} إشارة")
    st.progress(scan_status['progress'] / 100)

# ============================================================
# 6. صفحة التوصيات المتقدمة
# ============================================================
if st.session_state.current_view == "signals":
    st.header("📋 مركز التوصيات الذكية")

    # إعدادات المسح
    with st.expander("⚙️ إعدادات المسح", expanded=True):
        set_col1, set_col2, set_col3 = st.columns(3)

        with set_col1:
            scan_assets = st.multiselect(
                "اختر نوع الأصول",
                ["فوركس", "عملات رقمية", "أسهم", "الكل"],
                default=["الكل"]
            )

        with set_col2:
            scan_timeframe = st.selectbox(
                "الإطار الزمني للمسح",
                list(TIMEFRAMES.keys()),
                index=2
            )

        with set_col3:
            specific_pair = st.text_input(
                "أو أدخل زوج محدد (اختياري)",
                placeholder="مثل: EURUSD=X أو BTC-USD"
            )

    # أزرار التحكم
    action_col1, action_col2, action_col3, action_col4 = st.columns(4)

    with action_col1:
        scan_btn = st.button("🔍 بدء المسح الشامل", type="primary",
                             use_container_width=True)
    with action_col2:
        update_btn = st.button("🔄 تحديث الأسعار", use_container_width=True)
    with action_col3:
        clear_btn = st.button("🗑️ حذف النشطة", use_container_width=True)
    with action_col4:
        refresh_btn = st.button("♻️ تحديث الصفحة", use_container_width=True)

    if refresh_btn:
        st.rerun()

    if clear_btn:
        db.delete_all_active()
        st.success("تم حذف التوصيات النشطة")
        time.sleep(1)
        st.rerun()

    if scan_btn:
        # بناء قائمة الأصول
        selected_assets = {}

        if specific_pair.strip():
            selected_assets[specific_pair.strip()] = specific_pair.strip()
        else:
            if "الكل" in scan_assets:
                selected_assets.update(FOREX_PAIRS)
                selected_assets.update(CRYPTO_PAIRS)
                selected_assets.update(STOCKS)
            else:
                if "فوركس" in scan_assets:
                    selected_assets.update(FOREX_PAIRS)
                if "عملات رقمية" in scan_assets:
                    selected_assets.update(CRYPTO_PAIRS)
                if "أسهم" in scan_assets:
                    selected_assets.update(STOCKS)

        if not selected_assets:
            st.warning("اختر أصول للمسح أولاً")
        else:
            st.session_state.scan_running = True
            # المسح مباشرة مع عرض التقدم
            total = len(selected_assets)
            found = 0
            scanned = 0
            progress_bar = st.progress(0)
            status_text = st.empty()

            for name, tick in selected_assets.items():
                scanned += 1
                progress_bar.progress(scanned / total)
                status_text.text(f"🔍 يحلل: {name} ({scanned}/{total}) | وجد: {found}")

                try:
                    df, info = fetch_data(tick, scan_timeframe)
                    if df is None or len(df) <= 15:
                        continue

                    df = calculate_indicators(df)
                    tech_score, tech_filters, curr = apply_all_filters(df, info)
                    fund_score, fund_details = get_fundamental_score(info)
                    news_score, news_details = get_news_score(client, tick, name)
                    pre_total = tech_score + fund_score + news_score

                    ai_decision = get_ai_final_decision(
                        client, tick, name, tech_score, fund_score,
                        news_score, tech_filters, safe_val(curr['Close']), pre_total
                    )

                    ai_score = 0
                    ai_reasoning = ""
                    ai_confidence = 0
                    if ai_decision and isinstance(ai_decision, dict):
                        ai_score = int(ai_decision.get('ai_score', 0))
                        ai_reasoning = ai_decision.get('reasoning', '')
                        ai_confidence = int(ai_decision.get('confidence', 0))
                        decision_txt = ai_decision.get('decision', 'تجنب')
                        if ai_confidence < 70 or decision_txt == 'تجنب':
                            continue

                    final_total = pre_total + ai_score
                    if abs(final_total) < 25:
                        continue

                    direction = "buy" if final_total > 0 else "sell"
                    tgts = calc_targets(curr, final_total)
                    price = safe_val(curr['Close'])

                    all_filters_list = []
                    all_filters_list.append("═══ التحليل الفني ═══")
                    for f in tech_filters:
                        icon = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
                        all_filters_list.append(f"{icon} {f[0]} ({f[1]:+d}) - {f[3]}")
                    all_filters_list.append(f"\n═══ الأساسي ({fund_score:+d}) ═══")
                    for f in fund_details:
                        icon = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
                        all_filters_list.append(f"{icon} {f[0]} ({f[1]:+d}) - {f[3]}")
                    all_filters_list.append(f"\n═══ الأخبار ({news_score:+d}) ═══")
                    for f in news_details:
                        icon = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
                        all_filters_list.append(f"{icon} {f[0]} ({f[1]:+d}) - {f[3]}")
                    all_filters_list.append(f"\n═══ AI ({ai_score:+d}) ═══")
                    all_filters_list.append(f"🤖 {ai_reasoning}")
                    all_filters_list.append(f"📊 الثقة: {ai_confidence}%")

                    filters_text = "\n".join(all_filters_list)

                    if price > 0:
                        added = db.add_signal(
                            str(tick), str(name), str(direction),
                            float(price),
                            float(tgts['tp1']), float(tgts['tp2']),
                            float(tgts['tp3']), float(tgts['sl']),
                            float(abs(final_total)),
                            str(scan_timeframe), float(tech_score),
                            float(fund_score), float(news_score),
                            float(ai_score), str(filters_text),
                            str(ai_reasoning)
                        )
                        if added:
                            found += 1

                except Exception:
                    continue

                time.sleep(0.3)

            progress_bar.empty()
            status_text.empty()
            st.session_state.scan_running = False

            if found > 0:
                st.success(f"✅ اكتمل المسح! تم العثور على {found} إشارة قوية من {total} أصل")
            else:
                st.warning(f"لم يتم العثور على إشارات قوية كافية من {total} أصل")
            time.sleep(2)
            st.rerun()

    if update_btn:
        try:
            active_list = db.get_active_signals()
        except Exception:
            active_list = []

        updated_count = 0
        if active_list:
            with st.spinner("جاري تحديث الأسعار..."):
                for sig_row in active_list:
                    try:
                        stock_obj = yf.Ticker(sig_row['ticker'])
                        hist = stock_obj.history(period="1d")
                        if not hist.empty:
                            curr_price = float(hist['Close'].iloc[-1])
                            entry = float(sig_row['entry_price'])
                            tp = float(sig_row['tp2'])
                            sl = float(sig_row['sl'])
                            is_buy = sig_row['direction'] == 'buy'

                            new_status = 'active'
                            progress = 0.0

                            if is_buy:
                                if curr_price >= tp:
                                    new_status = 'tp_hit'
                                    progress = 100.0
                                elif curr_price <= sl:
                                    new_status = 'sl_hit'
                                    progress = 0.0
                                else:
                                    td = tp - entry
                                    cd = curr_price - entry
                                    progress = (cd / td * 100) if td != 0 else 0
                            else:
                                if curr_price <= tp:
                                    new_status = 'tp_hit'
                                    progress = 100.0
                                elif curr_price >= sl:
                                    new_status = 'sl_hit'
                                    progress = 0.0
                                else:
                                    td = entry - tp
                                    cd = entry - curr_price
                                    progress = (cd / td * 100) if td != 0 else 0

                            progress = max(0.0, min(100.0, progress))
                            pnl = ((curr_price - entry) / entry * 100) if is_buy else ((entry - curr_price) / entry * 100)

                            db.update_signal_status(
                                sig_row['id'], curr_price, new_status, progress, pnl
                            )
                            updated_count += 1
                    except Exception:
                        continue
            st.success(f"تم تحديث {updated_count} توصية")
            time.sleep(1)
            st.rerun()
        else:
            st.warning("لا توجد توصيات نشطة للتحديث")

    # عرض التوصيات النشطة
    st.subheader("📊 التوصيات النشطة")
    try:
        signals_list = db.get_active_signals()
    except Exception:
        signals_list = []

    if signals_list and len(signals_list) > 0:
        for sig_row in signals_list:
            try:
                is_buy = sig_row.get('direction', 'buy') == 'buy'
                color = "#00ff88" if is_buy else "#ff4444"
                dir_txt = "شراء 🟢" if is_buy else "بيع 🔴"
                sp = float(sig_row.get('progress', 0) or 0)
                spnl = float(sig_row.get('pnl_pct', 0) or 0)
                sc = float(sig_row.get('current_price', 0) or sig_row.get('entry_price', 0) or 0)
                se = float(sig_row.get('entry_price', 0) or 0)
                stp1 = float(sig_row.get('tp1', 0) or 0)
                stp2 = float(sig_row.get('tp2', 0) or 0)
                stp3 = float(sig_row.get('tp3', 0) or 0)
                ssl = float(sig_row.get('sl', 0) or 0)
                sn = sig_row.get('asset_name', '')
                stk = sig_row.get('ticker', '')
                strength = float(sig_row.get('strength', 0) or 0)
                ts_val = float(sig_row.get('technical_score', 0) or 0)
                fs_val = float(sig_row.get('fundamental_score', 0) or 0)
                ns_val = float(sig_row.get('news_score', 0) or 0)
                ais_val = float(sig_row.get('ai_score', 0) or 0)
                stf = sig_row.get('timeframe', '')

                # بطاقة التوصية
                st.markdown(f"""
                <div class="rec-card" style="border-left: 5px solid {color};">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <h3 style="margin:0;">{sn}
                                <span style="font-size:0.7em; color:#888;">{stk} | {stf}</span>
                            </h3>
                        </div>
                        <div style="text-align:right;">
                            <h3 style="color:{color}; margin:0;">{dir_txt}</h3>
                            <span style="font-size:0.8em; color:#aaa;">القوة: {strength:.0f}</span>
                        </div>
                    </div>
                    <div style="font-size:13px; margin:10px 0; display:flex; justify-content:space-between; flex-wrap:wrap;">
                        <span>🏁 الدخول: {se:.4f}</span>
                        <span>🏷️ الحالي: {sc:.4f}</span>
                        <span>🎯 TP1: {stp1:.4f}</span>
                        <span>🎯 TP2: {stp2:.4f}</span>
                        <span>🎯 TP3: {stp3:.4f}</span>
                        <span>🛑 SL: {ssl:.4f}</span>
                    </div>
                    <div style="display:flex; gap:10px; margin:8px 0; font-size:12px;">
                        <span style="color:#00bcd4;">📐 فني: {ts_val:+.0f}</span>
                        <span style="color:#ff9800;">📊 أساسي: {fs_val:+.0f}</span>
                        <span style="color:#e91e63;">📰 أخبار: {ns_val:+.0f}</span>
                        <span style="color:#9c27b0;">🤖 AI: {ais_val:+.0f}</span>
                    </div>
                    <div style="background:#111; height:10px; border-radius:5px; margin-top:5px;">
                        <div style="width:{sp}%; background:{color}; height:100%; border-radius:5px;"></div>
                    </div>
                    <div style="text-align:right; font-size:12px; margin-top:2px; color:#ccc;">
                        التقدم: {sp:.1f}% | الربح: <span style="color:{color}">{spnl:.2f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # زر عرض التفاصيل
                sig_id = sig_row.get('id', 0)
                with st.expander(f"📋 عرض تفاصيل التحليل - {sn}", expanded=False):
                    filters_detail = sig_row.get('filters_detail', '')
                    ai_reason = sig_row.get('ai_reasoning', '')

                    if filters_detail:
                        st.text(filters_detail)
                    else:
                        st.write("لا توجد تفاصيل")

                    if ai_reason:
                        st.info(f"🤖 تحليل AI: {ai_reason}")

            except Exception:
                continue
    else:
        st.info("لا توجد توصيات نشطة. اضبط الإعدادات واضغط 'بدء المسح الشامل'")

    st.markdown("---")
    st.subheader("📜 سجل التوصيات المنتهية")
    try:
        closed_list = db.get_closed_signals()
    except Exception:
        closed_list = []

    if closed_list and len(closed_list) > 0:
        hist_data = []
        for cr in closed_list:
            try:
                hist_data.append({
                    "التاريخ": cr.get('timestamp', ''),
                    "الأصل": cr.get('asset_name', ''),
                    "الإطار": cr.get('timeframe', ''),
                    "الاتجاه": "شراء" if cr.get('direction') == 'buy' else "بيع",
                    "الحالة": "✅ هدف" if cr.get('status') == 'tp_hit' else "❌ وقف",
                    "القوة": round(float(cr.get('strength', 0) or 0), 0),
                    "الربح %": round(float(cr.get('pnl_pct', 0) or 0), 2)
                })
            except Exception:
                continue
        if hist_data:
            st.dataframe(pd.DataFrame(hist_data), use_container_width=True,
                         hide_index=True)

# ============================================================
# 7. صفحة التحليل الفني (بدون تغيير)
# ============================================================
elif st.session_state.current_view == "analysis":
    st.header("📉 التحليل الفني اليدوي")

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        asset_class = st.selectbox("نوع الأصل", ["فوركس", "عملات رقمية", "أسهم"])
    with s2:
        if asset_class == "فوركس":
            selected = st.selectbox("الأصل", list(FOREX_PAIRS.keys()))
            ticker = FOREX_PAIRS[selected]
        elif asset_class == "عملات رقمية":
            selected = st.selectbox("الأصل", list(CRYPTO_PAIRS.keys()))
            ticker = CRYPTO_PAIRS[selected]
        else:
            selected = st.selectbox("الأصل", list(STOCKS.keys()))
            ticker = STOCKS[selected]
    with s3:
        tf_label = st.selectbox("الإطار الزمني", list(TIMEFRAMES.keys()), index=2)
    with s4:
        analyze_btn = st.button("🚀 تحليل الآن", type="primary",
                                use_container_width=True)

    if analyze_btn:
        with st.spinner("جاري التحليل..."):
            df, info = fetch_data(ticker, tf_label)
            if df is not None and len(df) > 15:
                df = calculate_indicators(df)
                ts, td, curr = apply_all_filters(df, info)
                sig, cls_name = final_signal(ts)
                tgts = calc_targets(curr, ts)

                st.session_state.analysis_result = {
                    'ticker': ticker, 'price': safe_val(curr['Close']),
                    'sig': sig, 'cls': cls_name, 'comb': ts,
                    'ts': ts, 'td': td, 'tgts': tgts, 'tf': tf_label
                }

                ai_res = get_ai_verdict(client, ticker, ts, td, curr)
                st.session_state.ai_result = ai_res

                try:
                    db.save_analysis(ticker, tf_label, sig, cls_name, ts,
                                     safe_val(curr['Close']), tgts, ai_res)
                except Exception:
                    pass
            else:
                st.error("فشل في جلب البيانات")

    if 'analysis_result' in st.session_state:
        res = st.session_state.analysis_result

        st.markdown(f"""
        <div class="main-signal {res['cls']}">
            {res['sig']} <span style="font-size:0.6em">({res['comb']:.1f})</span>
            <div style="font-size:16px; margin-top:5px; opacity:0.8;">
                {res['ticker']} | {res['price']:.4f}
            </div>
        </div>
        """, unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("الهدف الأول", f"{res['tgts']['tp1']:.4f}")
        m2.metric("الهدف الثاني", f"{res['tgts']['tp2']:.4f}")
        m3.metric("وقف الخسارة", f"{res['tgts']['sl']:.4f}", delta_color="inverse")
        m4.metric("العائد للمخاطرة", f"1:{res['tgts']['rr']:.1f}")

        tab1, tab2, tab3 = st.tabs(["الرسم البياني", "التفاصيل الفنية", "تقرير AI"])

        with tab1:
            tv_sym = to_tv_symbol(res['ticker'])
            tv_int = TV_INTERVALS.get(res['tf'], 'D')
            st.components.v1.html(f"""
            <div class="tradingview-widget-container" style="height:500px;width:100%">
              <div id="tv_chart"></div>
              <script src="https://s3.tradingview.com/tv.js"></script>
              <script>
              new TradingView.widget({{
                "width":"100%","height":"500","symbol":"{tv_sym}",
                "interval":"{tv_int}","timezone":"Etc/UTC","theme":"dark",
                "style":"1","locale":"ar","container_id":"tv_chart"
              }});
              </script>
            </div>""", height=520)

        with tab2:
            st.subheader(f"النقاط الفنية: {res['ts']}")
            for d in res['td']:
                icon = "✅" if d[2] == "pass" else ("❌" if d[2] == "fail" else "⚠️")
                st.markdown(f"{icon} **{d[0]}** ({d[1]:+d}) - {d[3]}")

        with tab3:
            ai_r = st.session_state.get('ai_result')
            if ai_r and isinstance(ai_r, dict):
                st.info(f"🎯 القرار: **{ai_r.get('final_decision', 'غير محدد')}**")
                st.write(f"📝 {ai_r.get('reasoning', 'غير متوفر')}")
                risk = ai_r.get('risk_level', 'غير محدد')
                if risk == "عالي":
                    st.error(f"⚠️ المخاطرة: {risk}")
                elif risk == "منخفض":
                    st.success(f"✅ المخاطرة: {risk}")
                else:
                    st.warning(f"⚡ المخاطرة: {risk}")
            else:
                st.warning("AI غير مفعل أو التوكن مفقود")

# ============================================================
# 8. صفحة الدردشة (بدون تغيير)
# ============================================================
elif st.session_state.current_view == "chat":
    st.header("🤖 المستشار المالي الذكي")
    st.caption("اسأل عن الأسواق والتداول")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("اكتب سؤالك...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            if client:
                try:
                    sys_prompt = """أنت مستشار مالي خبير بالعربية.
القواعد:
1. أجب بالعربية فقط دائماً.
2. ممنوع كتابة أي كود برمجي أو استخدام ```.
3. إذا قيل لك hi أو hello رحب بالعربية وعرف نفسك.
4. تخصصك: التحليل الفني والأساسي وإدارة المخاطر.
5. كن مختصراً ومفيداً.
6. حذر من المخاطر."""

                    msgs = [{"role": "system", "content": sys_prompt}]
                    for m in st.session_state.messages[-6:]:
                        msgs.append({"role": m["role"], "content": m["content"]})

                    resp = client.chat_completion(messages=msgs, max_tokens=600,
                                                  stream=False)
                    response_text = resp.choices[0].message.content

                    if "```" in response_text:
                        clean = []
                        in_code = False
                        for line in response_text.split('\n'):
                            if '```' in line:
                                in_code = not in_code
                                continue
                            if not in_code:
                                clean.append(line)
                        response_text = '\n'.join(clean)
                    response_text = response_text.replace('`', '')

                    st.markdown(response_text)
                    st.session_state.messages.append({
                        "role": "assistant", "content": response_text
                    })
                except Exception:
                    st.error("⚠️ خطأ في الاتصال. حاول مرة أخرى.")
            else:
                st.error("⚠️ أضف HF_TOKEN في إعدادات التطبيق.")

    if st.session_state.messages:
        if st.button("🗑️ مسح المحادثة"):
            st.session_state.messages = []
            st.rerun()