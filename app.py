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
    .score-section {
        background: #111827; border-radius: 8px; padding: 10px;
        margin: 5px 0; border: 1px solid #1f2937;
    }
    .stChatMessage {direction: rtl;}
    .scan-notify {
        position: fixed; top: 20px; right: 20px; z-index: 9999;
        background: #065f46; color: white; padding: 15px 25px;
        border-radius: 12px; font-weight: bold;
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
# 2. البيانات
# ============================================================
def init_session_state():
    defaults = {
        'messages': [],
        'current_view': 'analysis',
        'scan_running': False,
        'scan_complete': False,
        'scan_results': 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

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
    "DOGE/USD": "DOGE-USD", "DOT/USD": "DOT-USD", "AVAX/USD": "AVAX-USD"
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
TV_INTERVALS = {"15 دقيقة": "15", "1 ساعة": "60", "4 ساعات": "240", "يومي": "D"}

def to_tv_symbol(ticker):
    if ticker.endswith("=X"): return f"FX:{ticker.replace('=X', '')}"
    if ticker.endswith("-USD"): return f"CRYPTO:{ticker.replace('-USD', '')}USD"
    if ticker == "GC=F": return "COMEX:GC1!"
    if ticker == "SI=F": return "COMEX:SI1!"
    if ticker == "CL=F": return "NYMEX:CL1!"
    return f"NASDAQ:{ticker}"

# ============================================================
# 3. AI
# ============================================================
client = None
try:
    token = st.secrets.get("HF_TOKEN", "")
    if token:
        client = InferenceClient(model="Qwen/Qwen2.5-72B-Instruct", token=token)
except Exception:
    client = None

# ============================================================
# 4. دوال التحليل الموحد
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
            raw = stock.history(period="3mo", interval="1h")
            if not raw.empty:
                if raw.index.tz is not None:
                    raw.index = raw.index.tz_localize(None)
                df = raw.resample('4h').agg({
                    'Open': 'first', 'High': 'max',
                    'Low': 'min', 'Close': 'last', 'Volume': 'sum'
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
    c, h, low = df['Close'], df['High'], df['Low']
    vol = df['Volume'] if 'Volume' in df.columns else None

    for w in [5, 10, 20, 50, 100, 200]:
        try: df[f'EMA_{w}'] = ta.trend.ema_indicator(c, window=w)
        except: pass
    for w in [20, 50, 200]:
        try: df[f'SMA_{w}'] = ta.trend.sma_indicator(c, window=w)
        except: pass
    try:
        m = ta.trend.MACD(c)
        df['MACD'] = m.macd(); df['MACD_Signal'] = m.macd_signal()
        df['MACD_Hist'] = m.macd_diff()
    except: pass
    try: df['RSI'] = ta.momentum.rsi(c, window=14)
    except: pass
    try:
        s = ta.momentum.StochasticOscillator(h, low, c)
        df['Stoch_K'] = s.stoch(); df['Stoch_D'] = s.stoch_signal()
    except: pass
    try:
        bb = ta.volatility.BollingerBands(c, window=20)
        df['BB_Upper'] = bb.bollinger_hband(); df['BB_Lower'] = bb.bollinger_lband()
        df['BB_Mid'] = bb.bollinger_mavg()
    except: pass
    try: df['ATR'] = ta.volatility.average_true_range(h, low, c)
    except: pass
    try:
        a = ta.trend.ADXIndicator(h, low, c)
        df['ADX'] = a.adx(); df['DI_plus'] = a.adx_pos(); df['DI_minus'] = a.adx_neg()
    except: pass
    try: df['PSAR'] = ta.trend.PSARIndicator(h, low, c).psar()
    except: pass
    try:
        ich = ta.trend.IchimokuIndicator(h, low)
        df['Ich_A'] = ich.ichimoku_a(); df['Ich_B'] = ich.ichimoku_b()
    except: pass
    try: df['CCI'] = ta.trend.cci(h, low, c, window=20)
    except: pass
    try: df['Williams_R'] = ta.momentum.williams_r(h, low, c)
    except: pass
    if vol is not None:
        try: df['MFI'] = ta.volume.money_flow_index(h, low, c, vol)
        except: pass
        try: df['OBV'] = ta.volume.on_balance_volume(c, vol)
        except: pass
    try: df['ROC'] = ta.momentum.roc(c, window=12)
    except: pass

    return df


def apply_all_filters(df, info):
    """18 فلتر فني - يُستخدم في التوصيات والتحليل معاً"""
    curr = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else curr
    price = safe_val(curr['Close'])
    filters = []
    total = 0

    # 1: Golden/Death Cross
    e50 = safe_val(curr.get('EMA_50'))
    e200 = safe_val(curr.get('EMA_200'))
    if e50 > 0 and e200 > 0:
        if e50 > e200:
            filters.append(("تقاطع ذهبي EMA50/200", 10, "pass", "ترند صاعد قوي"))
            total += 10
        else:
            filters.append(("تقاطع الموت EMA50/200", -10, "fail", "ترند هابط"))
            total -= 10
    else:
        filters.append(("EMA50/200 غير متوفر", 0, "warn", "بيانات غير كافية"))

    # 2: Price vs EMA200
    if e200 > 0:
        if price > e200:
            filters.append(("السعر فوق EMA200", 8, "pass", f"{price:.4f}>{e200:.4f}"))
            total += 8
        else:
            filters.append(("السعر تحت EMA200", -8, "fail", f"{price:.4f}<{e200:.4f}"))
            total -= 8

    # 3: EMA Order
    e5 = safe_val(curr.get('EMA_5'))
    e10 = safe_val(curr.get('EMA_10'))
    e20 = safe_val(curr.get('EMA_20'))
    if all(v > 0 for v in [e5, e10, e20, e50]):
        if e5 > e10 > e20 > e50:
            filters.append(("ترتيب EMAs صعودي مثالي", 7, "pass", "5>10>20>50"))
            total += 7
        elif e5 < e10 < e20 < e50:
            filters.append(("ترتيب EMAs هبوطي مثالي", -7, "fail", "5<10<20<50"))
            total -= 7
        else:
            filters.append(("ترتيب EMAs مختلط", 0, "warn", "لا ترتيب واضح"))

    # 4: ADX
    adx = safe_val(curr.get('ADX'))
    dip = safe_val(curr.get('DI_plus'))
    dim = safe_val(curr.get('DI_minus'))
    if adx > 30:
        if dip > dim:
            filters.append(("ADX ترند صاعد قوي", 8, "pass", f"ADX={adx:.0f}"))
            total += 8
        else:
            filters.append(("ADX ترند هابط قوي", -8, "fail", f"ADX={adx:.0f}"))
            total -= 8
    elif adx > 20:
        if dip > dim:
            filters.append(("ADX صاعد متوسط", 4, "pass", f"ADX={adx:.0f}"))
            total += 4
        else:
            filters.append(("ADX هابط متوسط", -4, "fail", f"ADX={adx:.0f}"))
            total -= 4
    elif adx > 0:
        filters.append(("ADX بدون ترند", 0, "warn", f"ADX={adx:.0f}"))

    # 5: PSAR
    psar = safe_val(curr.get('PSAR'))
    if psar > 0:
        if price > psar:
            filters.append(("PSAR صعودي", 5, "pass", "السعر فوق PSAR"))
            total += 5
        else:
            filters.append(("PSAR هبوطي", -5, "fail", "السعر تحت PSAR"))
            total -= 5

    # 6: Ichimoku
    ia = safe_val(curr.get('Ich_A'))
    ib = safe_val(curr.get('Ich_B'))
    if ia > 0 and ib > 0:
        ct = max(ia, ib)
        cb = min(ia, ib)
        if price > ct:
            filters.append(("فوق سحابة إيشيموكو", 6, "pass", "صعودي"))
            total += 6
        elif price < cb:
            filters.append(("تحت سحابة إيشيموكو", -6, "fail", "هبوطي"))
            total -= 6
        else:
            filters.append(("داخل السحابة", 0, "warn", "حيرة"))

    # 7: RSI
    rsi = safe_val(curr.get('RSI'))
    if rsi > 0:
        if rsi < 25:
            filters.append(("RSI تشبع بيعي شديد", 10, "pass", f"RSI={rsi:.0f}"))
            total += 10
        elif rsi < 35:
            filters.append(("RSI قريب من التشبع البيعي", 5, "pass", f"RSI={rsi:.0f}"))
            total += 5
        elif rsi > 75:
            filters.append(("RSI تشبع شرائي شديد", -10, "fail", f"RSI={rsi:.0f}"))
            total -= 10
        elif rsi > 65:
            filters.append(("RSI قريب من التشبع الشرائي", -5, "fail", f"RSI={rsi:.0f}"))
            total -= 5
        else:
            filters.append(("RSI وسط", 0, "warn", f"RSI={rsi:.0f}"))

    # 8: MACD
    mh = safe_val(curr.get('MACD_Hist'))
    mhp = safe_val(prev.get('MACD_Hist')) if hasattr(prev, 'get') else 0
    if mh > 0 and mhp <= 0:
        filters.append(("MACD تقاطع صعودي جديد", 8, "pass", "تحول إيجابي"))
        total += 8
    elif mh < 0 and mhp >= 0:
        filters.append(("MACD تقاطع هبوطي جديد", -8, "fail", "تحول سلبي"))
        total -= 8
    elif mh > 0:
        filters.append(("MACD إيجابي", 4, "pass", "استمرار"))
        total += 4
    elif mh < 0:
        filters.append(("MACD سلبي", -4, "fail", "استمرار"))
        total -= 4

    # 9: Stochastic
    sk = safe_val(curr.get('Stoch_K'))
    sd = safe_val(curr.get('Stoch_D'))
    if sk > 0:
        if sk < 20 and sk > sd:
            filters.append(("Stoch تشبع بيعي + تقاطع", 7, "pass", f"K={sk:.0f}"))
            total += 7
        elif sk > 80 and sk < sd:
            filters.append(("Stoch تشبع شرائي + تقاطع", -7, "fail", f"K={sk:.0f}"))
            total -= 7
        elif sk < 20:
            filters.append(("Stoch تشبع بيعي", 4, "pass", f"K={sk:.0f}"))
            total += 4
        elif sk > 80:
            filters.append(("Stoch تشبع شرائي", -4, "fail", f"K={sk:.0f}"))
            total -= 4

    # 10: CCI
    cci = safe_val(curr.get('CCI'))
    if cci != 0:
        if cci < -200:
            filters.append(("CCI تشبع بيعي حاد", 6, "pass", f"CCI={cci:.0f}"))
            total += 6
        elif cci > 200:
            filters.append(("CCI تشبع شرائي حاد", -6, "fail", f"CCI={cci:.0f}"))
            total -= 6

    # 11: Williams %R
    wr = safe_val(curr.get('Williams_R'))
    if wr != 0:
        if wr < -80:
            filters.append(("Williams تشبع بيعي", 4, "pass", f"W%R={wr:.0f}"))
            total += 4
        elif wr > -20:
            filters.append(("Williams تشبع شرائي", -4, "fail", f"W%R={wr:.0f}"))
            total -= 4

    # 12: ROC
    roc = safe_val(curr.get('ROC'))
    if roc != 0:
        if roc > 5:
            filters.append(("زخم صعودي ROC", 5, "pass", f"ROC={roc:.1f}%"))
            total += 5
        elif roc < -5:
            filters.append(("زخم هبوطي ROC", -5, "fail", f"ROC={roc:.1f}%"))
            total -= 5

    # 13: Bollinger
    bbu = safe_val(curr.get('BB_Upper'))
    bbl = safe_val(curr.get('BB_Lower'))
    if bbu > 0 and bbl > 0:
        if price <= bbl:
            filters.append(("عند Bollinger السفلي", 6, "pass", "فرصة ارتداد"))
            total += 6
        elif price >= bbu:
            filters.append(("عند Bollinger العلوي", -6, "fail", "فرصة هبوط"))
            total -= 6
        else:
            bbp = (price - bbl) / (bbu - bbl) * 100 if (bbu - bbl) > 0 else 50
            filters.append(("موقع Bollinger", 0, "warn", f"{bbp:.0f}% من النطاق"))

    # 14: ATR
    atr = safe_val(curr.get('ATR'))
    if atr > 0 and price > 0:
        atr_pct = (atr / price) * 100
        if atr_pct > 3:
            filters.append(("تذبذب عالي ATR", -3, "warn", f"{atr_pct:.1f}%"))
            total -= 3
        elif atr_pct < 0.5:
            filters.append(("تذبذب منخفض ATR", -2, "warn", f"{atr_pct:.1f}%"))
            total -= 2
        else:
            filters.append(("تذبذب مناسب ATR", 3, "pass", f"{atr_pct:.1f}%"))
            total += 3

    # 15: MFI
    mfi = safe_val(curr.get('MFI'))
    if mfi > 0:
        if mfi < 20:
            filters.append(("MFI تشبع بيعي", 5, "pass", f"MFI={mfi:.0f}"))
            total += 5
        elif mfi > 80:
            filters.append(("MFI تشبع شرائي", -5, "fail", f"MFI={mfi:.0f}"))
            total -= 5

    # 16: OBV
    if 'OBV' in df.columns and len(df) > 5:
        try:
            obv_now = safe_val(curr.get('OBV'))
            obv_5 = safe_val(df.iloc[-5].get('OBV'))
            p5 = safe_val(df.iloc[-5]['Close'])
            if obv_now > obv_5 and price > p5:
                filters.append(("OBV يؤكد الصعود", 4, "pass", "حجم يدعم"))
                total += 4
            elif obv_now < obv_5 and price < p5:
                filters.append(("OBV يؤكد الهبوط", -4, "fail", "حجم يدعم"))
                total -= 4
            elif obv_now < obv_5 and price > p5:
                filters.append(("تباعد سلبي OBV", -3, "warn", "حذر"))
                total -= 3
        except: pass

    # 17: Engulfing
    if len(df) > 2:
        try:
            co = safe_val(curr.get('Open'))
            cc = safe_val(curr['Close'])
            po = safe_val(prev.get('Open'))
            pc = safe_val(prev['Close'])
            if pc < po and cc > co and cc > po and co < pc:
                filters.append(("ابتلاع صعودي", 7, "pass", "انعكاس قوي"))
                total += 7
            elif pc > po and cc < co and cc < po and co > pc:
                filters.append(("ابتلاع هبوطي", -7, "fail", "انعكاس قوي"))
                total -= 7
        except: pass

    # 18: Support/Resistance
    if len(df) > 20:
        try:
            rh = df['High'].tail(20).max()
            rl = df['Low'].tail(20).min()
            rng = rh - rl
            if rng > 0:
                pos = (price - rl) / rng
                if pos < 0.15:
                    filters.append(("قريب من دعم قوي", 6, "pass", f"{pos*100:.0f}%"))
                    total += 6
                elif pos > 0.85:
                    filters.append(("قريب من مقاومة", -6, "fail", f"{pos*100:.0f}%"))
                    total -= 6
                else:
                    filters.append(("بين الدعم والمقاومة", 0, "warn", f"{pos*100:.0f}%"))
        except: pass

    return total, filters, curr


def get_fundamental_score(info):
    score = 0
    details = []
    if not info or not isinstance(info, dict):
        return 0, [("بيانات أساسية غير متوفرة", 0, "warn", "")]

    pe = info.get('trailingPE') or info.get('forwardPE')
    if pe:
        pe = float(pe)
        if 5 < pe < 20:
            score += 5; details.append(("P/E مناسب", 5, "pass", f"{pe:.1f}"))
        elif pe > 40:
            score -= 3; details.append(("P/E مرتفع", -3, "fail", f"{pe:.1f}"))

    margin = info.get('profitMargins')
    if margin:
        mp = float(margin) * 100
        if mp > 20:
            score += 4; details.append(("هامش ربح ممتاز", 4, "pass", f"{mp:.1f}%"))
        elif mp > 10:
            score += 2; details.append(("هامش ربح جيد", 2, "pass", f"{mp:.1f}%"))
        elif mp < 0:
            score -= 4; details.append(("خاسرة", -4, "fail", f"{mp:.1f}%"))

    growth = info.get('revenueGrowth')
    if growth:
        gp = float(growth) * 100
        if gp > 20:
            score += 4; details.append(("نمو ممتاز", 4, "pass", f"{gp:.1f}%"))
        elif gp > 5:
            score += 2; details.append(("نمو جيد", 2, "pass", f"{gp:.1f}%"))
        elif gp < -5:
            score -= 3; details.append(("انخفاض إيرادات", -3, "fail", f"{gp:.1f}%"))

    de = info.get('debtToEquity')
    if de:
        de = float(de)
        if de < 50:
            score += 3; details.append(("ديون منخفضة", 3, "pass", f"D/E={de:.0f}"))
        elif de > 200:
            score -= 3; details.append(("ديون عالية", -3, "fail", f"D/E={de:.0f}"))

    h52 = info.get('fiftyTwoWeekHigh')
    l52 = info.get('fiftyTwoWeekLow')
    cp = info.get('currentPrice') or info.get('regularMarketPrice')
    if h52 and l52 and cp:
        rng = float(h52) - float(l52)
        if rng > 0:
            pos = (float(cp) - float(l52)) / rng
            if pos < 0.3:
                score += 3; details.append(("قريب من أدنى 52w", 3, "pass", f"{pos*100:.0f}%"))
            elif pos > 0.9:
                score -= 2; details.append(("قريب من أعلى 52w", -2, "warn", f"{pos*100:.0f}%"))

    if not details:
        details.append(("لا بيانات أساسية", 0, "warn", ""))
    return score, details


def get_news_score(ai_client, ticker, name):
    if not ai_client:
        return 0, [("محلل الأخبار غير مفعل", 0, "warn", "يحتاج HF_TOKEN")]
    prompt = f"""حلل الأخبار الحالية لـ {name} ({ticker}).
أجب JSON فقط:
{{"news_sentiment":"إيجابي/سلبي/محايد","score":-10 إلى 10,"key_events":["حدث1"],"impact":"تأثير مختصر"}}"""
    try:
        resp = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "محلل أخبار مالية. JSON فقط. بدون كود."},
                {"role": "user", "content": prompt}
            ], max_tokens=250
        )
        txt = resp.choices[0].message.content.strip()
        if "```" in txt:
            for p in txt.split("```"):
                p = p.strip()
                if p.startswith("json"): p = p[4:].strip()
                if p.startswith("{"): txt = p; break
        data = json.loads(txt)
        ns = int(data.get('score', 0))
        st_txt = "pass" if ns > 0 else ("fail" if ns < 0 else "warn")
        details = [(f"الأخبار: {data.get('news_sentiment', 'محايد')}", ns, st_txt,
                     data.get('impact', ''))]
        for ev in data.get('key_events', [])[:3]:
            details.append((f"📰 {ev}", 0, "warn", ""))
        return ns, details
    except:
        return 0, [("فشل تحليل الأخبار", 0, "warn", "")]


def get_ai_final_decision(ai_client, ticker, name, tech, fund, news,
                           filters, price, hint):
    if not ai_client:
        return None
    top_f = " | ".join([f"{f[0]}({f[1]:+d})" for f in filters[:8]])
    prompt = f"""خبير تداول - قرار نهائي:
الأصل: {name} ({ticker}) | السعر: {price}
فني: {tech} | أساسي: {fund} | أخبار: {news}
الاتجاه: {"صعودي" if hint > 0 else "هبوطي" if hint < 0 else "محايد"}
الفلاتر: {top_f}

أجب JSON فقط:
{{"decision":"شراء قوي/شراء/بيع قوي/بيع/تجنب","confidence":0-100,"reasoning":"تحليل مختصر بالعربية","risk":"منخفض/متوسط/عالي","ai_score":-15 إلى 15}}"""
    try:
        resp = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "خبير تداول. JSON فقط. بدون كود."},
                {"role": "user", "content": prompt}
            ], max_tokens=300
        )
        txt = resp.choices[0].message.content.strip()
        if "```" in txt:
            for p in txt.split("```"):
                p = p.strip()
                if p.startswith("json"): p = p[4:].strip()
                if p.startswith("{"): txt = p; break
        return json.loads(txt)
    except:
        return None


def calc_targets(curr, score):
    price = safe_val(curr['Close'])
    atr = safe_val(curr.get('ATR'))
    if atr == 0: atr = price * 0.015
    f = 1 if score > 0 else -1
    sl = price - (2 * atr * f)
    tp1 = price + (1.5 * atr * f)
    tp2 = price + (3 * atr * f)
    tp3 = price + (5 * atr * f)
    risk = abs(price - sl)
    rr = abs(tp2 - price) / risk if risk > 0 else 0
    return {'sl': sl, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'rr': rr}


def final_signal(combined):
    if combined >= 40: return "شراء قوي", "bg-strong-buy"
    elif combined >= 20: return "شراء", "bg-buy"
    elif combined <= -40: return "بيع قوي", "bg-strong-sell"
    elif combined <= -20: return "بيع", "bg-sell"
    return "محايد", "bg-neutral"


def build_filters_text(tech_filters, tech_score, fund_details, fund_score,
                        news_details, news_score, ai_score, ai_reasoning,
                        ai_confidence):
    lines = []
    lines.append(f"═══ التحليل الفني ({tech_score:+d}) ═══")
    for f in tech_filters:
        icon = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
        lines.append(f"{icon} {f[0]} ({f[1]:+d}) - {f[3]}")
    lines.append(f"\n═══ الأساسي ({fund_score:+d}) ═══")
    for f in fund_details:
        icon = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
        lines.append(f"{icon} {f[0]} ({f[1]:+d}) - {f[3]}")
    lines.append(f"\n═══ الأخبار ({news_score:+d}) ═══")
    for f in news_details:
        icon = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
        lines.append(f"{icon} {f[0]} ({f[1]:+d}) - {f[3]}")
    lines.append(f"\n═══ قرار AI ({ai_score:+d}) ═══")
    lines.append(f"🤖 {ai_reasoning}")
    lines.append(f"📊 الثقة: {ai_confidence}%")
    return "\n".join(lines)


def full_analysis(ticker, name, tf_key, ai_client, require_strong=False):
    """تحليل شامل موحد - يُستخدم في التوصيات والتحليل اليدوي"""
    df, info = fetch_data(ticker, tf_key)
    if df is None or len(df) <= 15:
        return None

    df = calculate_indicators(df)

    # 1. الفلاتر الفنية (18 فلتر)
    tech_score, tech_filters, curr = apply_all_filters(df, info)

    # 2. الأساسي
    fund_score, fund_details = get_fundamental_score(info)

    # 3. الأخبار
    news_score, news_details = get_news_score(ai_client, ticker, name)

    pre_total = tech_score + fund_score + news_score

    # 4. AI النهائي
    ai_decision = get_ai_final_decision(
        ai_client, ticker, name, tech_score, fund_score,
        news_score, tech_filters, safe_val(curr['Close']), pre_total
    )

    ai_score = 0
    ai_reasoning = ""
    ai_confidence = 0
    ai_risk = "متوسط"
    if ai_decision and isinstance(ai_decision, dict):
        ai_score = int(ai_decision.get('ai_score', 0))
        ai_reasoning = ai_decision.get('reasoning', '')
        ai_confidence = int(ai_decision.get('confidence', 0))
        ai_risk = ai_decision.get('risk', 'متوسط')
        decision_txt = ai_decision.get('decision', 'تجنب')

        if require_strong:
            if ai_confidence < 70 or decision_txt == 'تجنب':
                return None

    final_total = pre_total + ai_score

    if require_strong and abs(final_total) < 20:
        return None

    direction = "buy" if final_total > 0 else "sell"
    tgts = calc_targets(curr, final_total)
    price = safe_val(curr['Close'])
    sig_label, sig_class = final_signal(final_total)

    filters_text = build_filters_text(
        tech_filters, tech_score, fund_details, fund_score,
        news_details, news_score, ai_score, ai_reasoning, ai_confidence
    )

    return {
        'ticker': ticker,
        'name': name,
        'price': price,
        'direction': direction,
        'signal': sig_label,
        'signal_class': sig_class,
        'total_score': final_total,
        'tech_score': tech_score,
        'fund_score': fund_score,
        'news_score': news_score,
        'ai_score': ai_score,
        'ai_reasoning': ai_reasoning,
        'ai_confidence': ai_confidence,
        'ai_risk': ai_risk,
        'tech_filters': tech_filters,
        'fund_details': fund_details,
        'news_details': news_details,
        'filters_text': filters_text,
        'targets': tgts,
        'timeframe': tf_key,
        'curr': curr,
    }


# ============================================================
# 5. واجهة التطبيق
# ============================================================
st.title("ProTrade Elite 5.0 📊")

required = ['init_db', 'add_signal', 'get_active_signals',
            'get_closed_signals', 'update_signal_status',
            'save_analysis', 'set_scan_status', 'get_scan_status',
            'delete_all_active']
missing = [f for f in required if not hasattr(db, f)]
if missing:
    st.error(f"⚠️ db.py ناقص: {', '.join(missing)}")
    st.stop()

# إشعار
scan_st = db.get_scan_status()
if scan_st and not scan_st['is_running'] and scan_st['found_signals'] > 0:
    if st.session_state.get('scan_running'):
        st.session_state.scan_running = False
        st.session_state.scan_complete = True
        st.session_state.scan_results = scan_st['found_signals']
if st.session_state.get('scan_complete'):
    st.markdown(f'<div class="scan-notify">✅ اكتمل! {st.session_state.scan_results} إشارة</div>', unsafe_allow_html=True)
    st.session_state.scan_complete = False

with st.expander("☰ القائمة الرئيسية", expanded=False):
    n1, n2, n3 = st.columns(3)
    with n1:
        if st.button("📋 التوصيات", use_container_width=True):
            st.session_state.current_view = "signals"; st.rerun()
    with n2:
        if st.button("📉 التحليل", use_container_width=True):
            st.session_state.current_view = "analysis"; st.rerun()
    with n3:
        if st.button("🤖 الدردشة", use_container_width=True):
            st.session_state.current_view = "chat"; st.rerun()

if scan_st and scan_st['is_running']:
    st.info(f"🔄 يحلل: {scan_st['current_asset']} ({scan_st['scanned_assets']}/{scan_st['total_assets']}) | وجد: {scan_st['found_signals']}")
    st.progress(scan_st['progress'] / 100)

# ============================================================
# 6. التوصيات
# ============================================================
if st.session_state.current_view == "signals":
    st.header("📋 مركز التوصيات الذكية")

    with st.expander("⚙️ إعدادات المسح", expanded=True):
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            scan_types = st.multiselect("نوع الأصول",
                ["فوركس", "عملات رقمية", "أسهم", "الكل"], default=["الكل"])
        with sc2:
            scan_tf = st.selectbox("الإطار الزمني", list(TIMEFRAMES.keys()), index=2)
        with sc3:
            specific = st.text_input("زوج محدد (اختياري)", placeholder="EURUSD=X")

    ac1, ac2, ac3, ac4 = st.columns(4)
    with ac1: scan_btn = st.button("🔍 مسح شامل", type="primary", use_container_width=True)
    with ac2: update_btn = st.button("🔄 تحديث", use_container_width=True)
    with ac3: clear_btn = st.button("🗑️ حذف النشطة", use_container_width=True)
    with ac4: refresh_btn = st.button("♻️ تحديث الصفحة", use_container_width=True)

    if refresh_btn: st.rerun()
    if clear_btn:
        db.delete_all_active(); st.success("تم الحذف"); time.sleep(1); st.rerun()

    if scan_btn:
        assets = {}
        if specific.strip():
            assets[specific.strip()] = specific.strip()
        else:
            if "الكل" in scan_types:
                assets.update(FOREX_PAIRS); assets.update(CRYPTO_PAIRS); assets.update(STOCKS)
            else:
                if "فوركس" in scan_types: assets.update(FOREX_PAIRS)
                if "عملات رقمية" in scan_types: assets.update(CRYPTO_PAIRS)
                if "أسهم" in scan_types: assets.update(STOCKS)

        if not assets:
            st.warning("اختر أصول أولاً")
        else:
            total = len(assets); found = 0; scanned = 0
            prog = st.progress(0)
            stat = st.empty()

            for name, tick in assets.items():
                scanned += 1
                prog.progress(scanned / total)
                stat.text(f"🔍 {name} ({scanned}/{total}) | وجد: {found}")

                try:
                    result = full_analysis(tick, name, scan_tf, client, require_strong=True)
                    if result and result['price'] > 0:
                        added = db.add_signal(
                            str(tick), str(name), result['direction'],
                            float(result['price']),
                            float(result['targets']['tp1']),
                            float(result['targets']['tp2']),
                            float(result['targets']['tp3']),
                            float(result['targets']['sl']),
                            float(abs(result['total_score'])),
                            str(scan_tf),
                            float(result['tech_score']),
                            float(result['fund_score']),
                            float(result['news_score']),
                            float(result['ai_score']),
                            str(result['filters_text']),
                            str(result['ai_reasoning'])
                        )
                        if added: found += 1
                except: continue
                time.sleep(0.3)

            prog.empty(); stat.empty()
            if found > 0:
                st.success(f"✅ تم العثور على {found} إشارة قوية من {total}")
            else:
                st.warning(f"لم يتم العثور على إشارات قوية من {total} أصل")
            time.sleep(2); st.rerun()

    if update_btn:
        active = db.get_active_signals()
        uc = 0
        if active:
            with st.spinner("تحديث..."):
                for sr in active:
                    try:
                        h = yf.Ticker(sr['ticker']).history(period="1d")
                        if not h.empty:
                            cp = float(h['Close'].iloc[-1])
                            e = float(sr['entry_price'])
                            tp = float(sr['tp2']); sl = float(sr['sl'])
                            ib = sr['direction'] == 'buy'
                            ns = 'active'; pr = 0.0
                            if ib:
                                if cp >= tp: ns='tp_hit'; pr=100
                                elif cp <= sl: ns='sl_hit'; pr=0
                                else:
                                    d = tp-e; pr = ((cp-e)/d*100) if d!=0 else 0
                            else:
                                if cp <= tp: ns='tp_hit'; pr=100
                                elif cp >= sl: ns='sl_hit'; pr=0
                                else:
                                    d = e-tp; pr = ((e-cp)/d*100) if d!=0 else 0
                            pr = max(0, min(100, pr))
                            pnl = ((cp-e)/e*100) if ib else ((e-cp)/e*100)
                            db.update_signal_status(sr['id'], cp, ns, pr, pnl)
                            uc += 1
                    except: continue
            st.success(f"تم تحديث {uc}"); time.sleep(1); st.rerun()
        else:
            st.warning("لا توجد توصيات نشطة")

    # عرض التوصيات
    st.subheader("📊 التوصيات النشطة")
    try: sigs = db.get_active_signals()
    except: sigs = []

    if sigs:
        for sr in sigs:
            try:
                ib = sr.get('direction','buy')=='buy'
                clr = "#00ff88" if ib else "#ff4444"
                dt = "شراء 🟢" if ib else "بيع 🔴"
                sp=float(sr.get('progress',0) or 0)
                spnl=float(sr.get('pnl_pct',0) or 0)
                sc=float(sr.get('current_price',0) or sr.get('entry_price',0) or 0)
                se=float(sr.get('entry_price',0) or 0)
                s1=float(sr.get('tp1',0) or 0)
                s2=float(sr.get('tp2',0) or 0)
                s3=float(sr.get('tp3',0) or 0)
                ssl=float(sr.get('sl',0) or 0)
                sn=sr.get('asset_name','')
                stk=sr.get('ticker','')
                stf=sr.get('timeframe','')
                sstr=float(sr.get('strength',0) or 0)
                ts=float(sr.get('technical_score',0) or 0)
                fs=float(sr.get('fundamental_score',0) or 0)
                ns=float(sr.get('news_score',0) or 0)
                ais=float(sr.get('ai_score',0) or 0)

                st.markdown(f"""
                <div class="rec-card" style="border-left:5px solid {clr};">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <h3 style="margin:0;">{sn} <span style="font-size:0.7em;color:#888;">{stk} | {stf}</span></h3>
                        <div style="text-align:right;">
                            <h3 style="color:{clr};margin:0;">{dt}</h3>
                            <span style="font-size:0.8em;color:#aaa;">القوة: {sstr:.0f}</span>
                        </div>
                    </div>
                    <div style="font-size:13px;margin:10px 0;display:flex;justify-content:space-between;flex-wrap:wrap;">
                        <span>🏁 {se:.4f}</span><span>🏷️ {sc:.4f}</span>
                        <span>🎯1: {s1:.4f}</span><span>🎯2: {s2:.4f}</span>
                        <span>🎯3: {s3:.4f}</span><span>🛑 {ssl:.4f}</span>
                    </div>
                    <div style="display:flex;gap:10px;margin:8px 0;font-size:12px;">
                        <span style="color:#00bcd4;">📐 فني:{ts:+.0f}</span>
                        <span style="color:#ff9800;">📊 أساسي:{fs:+.0f}</span>
                        <span style="color:#e91e63;">📰 أخبار:{ns:+.0f}</span>
                        <span style="color:#9c27b0;">🤖 AI:{ais:+.0f}</span>
                    </div>
                    <div style="background:#111;height:10px;border-radius:5px;margin-top:5px;">
                        <div style="width:{sp}%;background:{clr};height:100%;border-radius:5px;"></div>
                    </div>
                    <div style="text-align:right;font-size:12px;margin-top:2px;color:#ccc;">
                        التقدم:{sp:.1f}% | الربح:<span style="color:{clr}">{spnl:.2f}%</span>
                    </div>
                </div>""", unsafe_allow_html=True)

                with st.expander(f"📋 تفاصيل التحليل - {sn}"):
                    fd = sr.get('filters_detail','')
                    ar = sr.get('ai_reasoning','')
                    if fd: st.text(fd)
                    if ar: st.info(f"🤖 {ar}")
            except: continue
    else:
        st.info("لا توجد توصيات. اضبط الإعدادات واضغط 'مسح شامل'")

    st.markdown("---")
    st.subheader("📜 السجل")
    try: closed = db.get_closed_signals()
    except: closed = []
    if closed:
        hd = []
        for cr in closed:
            try:
                hd.append({
                    "التاريخ": cr.get('timestamp',''),
                    "الأصل": cr.get('asset_name',''),
                    "الإطار": cr.get('timeframe',''),
                    "الاتجاه": "شراء" if cr.get('direction')=='buy' else "بيع",
                    "الحالة": "✅" if cr.get('status')=='tp_hit' else "❌",
                    "القوة": round(float(cr.get('strength',0) or 0)),
                    "الربح%": round(float(cr.get('pnl_pct',0) or 0),2)
                })
            except: continue
        if hd: st.dataframe(pd.DataFrame(hd), use_container_width=True, hide_index=True)

# ============================================================
# 7. التحليل الفني (نفس المنطق الموحد)
# ============================================================
elif st.session_state.current_view == "analysis":
    st.header("📉 التحليل الفني المتقدم")

    a1, a2, a3, a4 = st.columns(4)
    with a1:
        ac = st.selectbox("نوع الأصل", ["فوركس", "عملات رقمية", "أسهم"])
    with a2:
        if ac == "فوركس":
            sel = st.selectbox("الأصل", list(FOREX_PAIRS.keys()))
            ticker = FOREX_PAIRS[sel]
        elif ac == "عملات رقمية":
            sel = st.selectbox("الأصل", list(CRYPTO_PAIRS.keys()))
            ticker = CRYPTO_PAIRS[sel]
        else:
            sel = st.selectbox("الأصل", list(STOCKS.keys()))
            ticker = STOCKS[sel]
    with a3:
        tf_l = st.selectbox("الإطار الزمني", list(TIMEFRAMES.keys()), index=2)
    with a4:
        abtn = st.button("🚀 تحليل شامل", type="primary", use_container_width=True)

    if abtn:
        with st.spinner("جاري التحليل الشامل (فني + أساسي + أخبار + AI)..."):
            result = full_analysis(ticker, sel, tf_l, client, require_strong=False)
            if result:
                st.session_state.analysis_result = result

                try:
                    db.save_analysis(
                        ticker, tf_l, result['signal'], result['signal_class'],
                        result['total_score'], result['price'], result['targets'],
                        {'final_decision': result['signal'], 'risk_level': result['ai_risk']},
                        result['tech_score'], result['fund_score'],
                        result['news_score'], result['ai_score'],
                        result['filters_text'], result['ai_reasoning']
                    )
                except: pass
            else:
                st.error("فشل في جلب البيانات أو تحليلها")

    if 'analysis_result' in st.session_state:
        r = st.session_state.analysis_result

        st.markdown(f"""
        <div class="main-signal {r['signal_class']}">
            {r['signal']} <span style="font-size:0.6em">({r['total_score']:.1f})</span>
            <div style="font-size:16px;margin-top:5px;opacity:0.8;">
                {r['ticker']} | {r['price']:.4f}
            </div>
        </div>""", unsafe_allow_html=True)

        # النقاط التفصيلية
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("📐 فني", f"{r['tech_score']:+d}")
        mc2.metric("📊 أساسي", f"{r['fund_score']:+d}")
        mc3.metric("📰 أخبار", f"{r['news_score']:+d}")
        mc4.metric("🤖 AI", f"{r['ai_score']:+d}")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("TP1", f"{r['targets']['tp1']:.4f}")
        m2.metric("TP2", f"{r['targets']['tp2']:.4f}")
        m3.metric("TP3", f"{r['targets']['tp3']:.4f}")
        m4.metric("SL", f"{r['targets']['sl']:.4f}", delta_color="inverse")
        m5.metric("R:R", f"1:{r['targets']['rr']:.1f}")

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📈 الرسم", "📐 الفلاتر الفنية", "📊 الأساسي",
            "📰 الأخبار", "🤖 قرار AI"
        ])

        with tab1:
            tv_s = to_tv_symbol(r['ticker'])
            tv_i = TV_INTERVALS.get(r['timeframe'], 'D')
            st.components.v1.html(f"""
            <div style="height:500px;width:100%"><div id="tv"></div>
            <script src="https://s3.tradingview.com/tv.js"></script>
            <script>new TradingView.widget({{
                "width":"100%","height":"500","symbol":"{tv_s}",
                "interval":"{tv_i}","theme":"dark","style":"1",
                "locale":"ar","container_id":"tv"
            }});</script></div>""", height=520)

        with tab2:
            st.subheader(f"الفلاتر الفنية ({r['tech_score']:+d})")
            for f in r['tech_filters']:
                icon = "✅" if f[2]=="pass" else ("❌" if f[2]=="fail" else "⚠️")
                st.markdown(f"{icon} **{f[0]}** ({f[1]:+d}) — {f[3]}")

        with tab3:
            st.subheader(f"التحليل الأساسي ({r['fund_score']:+d})")
            for f in r['fund_details']:
                icon = "✅" if f[2]=="pass" else ("❌" if f[2]=="fail" else "⚠️")
                st.markdown(f"{icon} **{f[0]}** ({f[1]:+d}) — {f[3]}")

        with tab4:
            st.subheader(f"تحليل الأخبار ({r['news_score']:+d})")
            for f in r['news_details']:
                icon = "✅" if f[2]=="pass" else ("❌" if f[2]=="fail" else "⚠️")
                st.markdown(f"{icon} **{f[0]}** ({f[1]:+d}) — {f[3]}")

        with tab5:
            st.subheader(f"قرار الذكاء الاصطناعي ({r['ai_score']:+d})")
            if r['ai_reasoning']:
                st.info(f"🤖 **{r['ai_reasoning']}**")
                st.write(f"📊 الثقة: **{r['ai_confidence']}%**")
                risk = r.get('ai_risk', 'متوسط')
                if risk == "عالي": st.error(f"⚠️ المخاطرة: {risk}")
                elif risk == "منخفض": st.success(f"✅ المخاطرة: {risk}")
                else: st.warning(f"⚡ المخاطرة: {risk}")
            else:
                st.warning("AI غير مفعل أو التوكن مفقود")

# ============================================================
# 8. الدردشة
# ============================================================
elif st.session_state.current_view == "chat":
    st.header("🤖 المستشار المالي الذكي")
    st.caption("اسأل عن الأسواق والتداول")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    ui = st.chat_input("اكتب سؤالك...")
    if ui:
        st.session_state.messages.append({"role": "user", "content": ui})
        with st.chat_message("user"): st.markdown(ui)

        with st.chat_message("assistant"):
            if client:
                try:
                    sp = """أنت مستشار مالي خبير بالعربية.
1. أجب بالعربية فقط. 2. ممنوع أي كود أو ```.
3. إذا قيل hi رحب بالعربية. 4. تخصصك التحليل والتداول.
5. كن مختصراً. 6. حذر من المخاطر."""
                    ms = [{"role":"system","content":sp}]
                    for m in st.session_state.messages[-6:]:
                        ms.append({"role":m["role"],"content":m["content"]})
                    resp = client.chat_completion(messages=ms, max_tokens=600, stream=False)
                    rt = resp.choices[0].message.content
                    if "```" in rt:
                        cl = []
                        ic = False
                        for ln in rt.split('\n'):
                            if '```' in ln: ic = not ic; continue
                            if not ic: cl.append(ln)
                        rt = '\n'.join(cl)
                    rt = rt.replace('`','')
                    st.markdown(rt)
                    st.session_state.messages.append({"role":"assistant","content":rt})
                except: st.error("⚠️ خطأ. حاول مرة أخرى.")
            else: st.error("⚠️ أضف HF_TOKEN")

    if st.session_state.messages:
        if st.button("🗑️ مسح المحادثة"):
            st.session_state.messages = []; st.rerun()