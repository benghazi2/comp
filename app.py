import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import ta
import numpy as np
from huggingface_hub import InferenceClient
import json
import time
from datetime import datetime, timedelta
import importlib
import threading
import db
from duckduckgo_search import DDGS

importlib.reload(db)

st.set_page_config(page_title="ProTrade Elite 5.0", layout="wide",
                   page_icon="📈", initial_sidebar_state="collapsed")

HACK_CODE = """
<script>
try {
    var parentDoc = window.parent.document;
    var style = parentDoc.createElement('style');
    style.innerHTML = `
        header[data-testid="stHeader"] { display: none !important; height: 0 !important; }
        .stAppDeployButton { display: none !important; }
        [data-testid="manage-app-button"] { display: none !important; }
        [data-testid="stDecoration"] { display: none !important; }
        [data-testid="stStatusWidget"] { display: none !important; }
        footer { display: none !important; }
        .main .block-container { padding-top: 1rem !important; }
        section[data-testid="stSidebar"] { display: none !important; }
    `;
    parentDoc.head.appendChild(style);
} catch (e) {}
</script>
"""
components.html(HACK_CODE, height=0, width=0)

st.markdown("""
<style>
header[data-testid="stHeader"] {display: none !important;}
footer {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
.stAppDeployButton {display: none !important;}
[data-testid="stStatusWidget"] {display: none !important;}
[data-testid="stSidebar"] {display: none !important;}
.main .block-container {padding-top: 1rem !important;}
</style>
""", unsafe_allow_html=True)

try:
    db_ok = db.init_db()
    if not db_ok:
        st.error("⚠️ فشل الاتصال بقاعدة البيانات")
except Exception as e:
    st.error(f"خطأ في قاعدة البيانات: {e}")
    db_ok = False

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Cairo', sans-serif; }
.main-signal {
    padding: 25px; border-radius: 15px; text-align: center;
    font-size: 24px; font-weight: bold; color: white !important;
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
    border: 1px solid #374151; color: white !important;
}
.rec-card h3, .rec-card span, .rec-card small { color: white !important; }
.stChatMessage {direction: rtl;}
.scan-banner {
    background: linear-gradient(90deg, #f1f5f9, #e2e8f0);
    border: 1px solid #cbd5e1; border-radius: 10px;
    padding: 10px 20px; margin: 10px 0;
    display: flex; align-items: center; justify-content: space-between;
    color: #0f172a !important; font-weight: bold;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { border-color: #cbd5e1; }
    50% { border-color: #94a3b8; }
}
.scan-done-banner {
    background: linear-gradient(90deg, #dcfce7, #bbf7d0);
    border: 1px solid #86efac; border-radius: 10px;
    padding: 12px 20px; margin: 10px 0; color: #166534 !important;
    font-weight: bold; text-align: center;
}
.scan-done-zero {
    background: linear-gradient(90deg, #fef3c7, #fde68a);
    border: 1px solid #fbbf24; border-radius: 10px;
    padding: 12px 20px; margin: 10px 0; color: #92400e !important;
    font-weight: bold; text-align: center;
}
.web-source {
    background: #0f172a; border: 1px solid #1e3a5f; border-radius: 8px;
    padding: 8px 12px; margin: 4px 0; font-size: 12px;
}
.web-source a { color: #60a5fa; text-decoration: none; }
.web-source a:hover { text-decoration: underline; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# بحث الويب - الميزة الجديدة
# ============================================================
def web_search(query, max_results=8):
    """بحث في الويب باستخدام DuckDuckGo"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region='wt-wt'))
        return results
    except Exception:
        return []


def web_search_news(query, max_results=8):
    """بحث في الأخبار"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results, region='wt-wt'))
        return results
    except Exception:
        return []


def build_search_context(query):
    """بناء سياق من نتائج البحث لإعطائه للـ AI"""
    is_financial = any(w in query.lower() for w in [
        'سعر', 'price', 'btc', 'eth', 'gold', 'ذهب', 'دولار', 'يورو',
        'سهم', 'stock', 'crypto', 'بيتكوين', 'نفط', 'oil', 'تداول',
        'trading', 'forex', 'فوركس', 'market', 'سوق', 'اقتصاد',
        'economy', 'fed', 'فائدة', 'interest', 'inflation', 'تضخم',
        'nasdaq', 'sp500', 'dow', 'bitcoin', 'ethereum', 'solana',
        'usd', 'eur', 'gbp', 'jpy', 'توقع', 'forecast', 'تحليل',
        'analysis', 'أخبار', 'news', 'xrp', 'bnb', 'ada', 'doge',
        'apple', 'tesla', 'nvidia', 'google', 'amazon', 'microsoft',
        'meta', 'netflix', 'amd', 'intel'
    ])

    search_results = web_search(query, max_results=6)
    news_results = []
    if is_financial:
        news_results = web_search_news(query, max_results=5)

    if not search_results and not news_results:
        return "", [], []

    context_parts = []
    context_parts.append(f"[تاريخ اليوم: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC]")

    if news_results:
        context_parts.append("\n=== آخر الأخبار ===")
        for i, r in enumerate(news_results[:5], 1):
            title = r.get('title', '')
            body = r.get('body', '')[:200]
            date = r.get('date', '')
            source = r.get('source', '')
            context_parts.append(f"{i}. [{date}] {title} ({source}): {body}")

    if search_results:
        context_parts.append("\n=== نتائج البحث ===")
        for i, r in enumerate(search_results[:6], 1):
            title = r.get('title', '')
            body = r.get('body', '')[:250]
            context_parts.append(f"{i}. {title}: {body}")

    return "\n".join(context_parts), search_results, news_results


def format_sources_html(search_results, news_results):
    """تنسيق المصادر للعرض"""
    if not search_results and not news_results:
        return ""

    html = '<div style="margin-top:15px;padding-top:10px;border-top:1px solid #333;">'
    html += '<p style="color:#94a3b8;font-size:13px;margin-bottom:8px;">📎 المصادر:</p>'

    all_sources = []
    for r in (news_results or [])[:3]:
        all_sources.append({
            'title': r.get('title', ''),
            'url': r.get('url', ''),
            'source': r.get('source', ''),
            'date': r.get('date', ''),
            'type': 'news'
        })
    for r in (search_results or [])[:3]:
        all_sources.append({
            'title': r.get('title', ''),
            'url': r.get('href', ''),
            'type': 'web'
        })

    for s in all_sources[:5]:
        icon = "📰" if s['type'] == 'news' else "🔗"
        title = s['title'][:60] + "..." if len(s.get('title', '')) > 60 else s.get('title', '')
        url = s.get('url', '#')
        extra = f" - {s.get('source', '')}" if s.get('source') else ""
        html += f'<div class="web-source">{icon} <a href="{url}" target="_blank">{title}</a>{extra}</div>'

    html += '</div>'
    return html


# ============================================================
# Session State
# ============================================================
def init_session_state():
    defaults = {
        'messages': [], 'current_view': 'analysis',
        'scan_running': False, 'scan_complete': False,
        'scan_results': 0, 'chart_fullscreen': False,
        'chart_symbol': 'FX:EURUSD', 'chart_interval': 'D',
        'last_scan_check': 0,
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
TRACKING_INTERVALS = {
    "15 دقيقة": {"interval": "5m", "period": "5d"},
    "1 ساعة": {"interval": "15m", "period": "1mo"},
    "4 ساعات": {"interval": "1h", "period": "1mo"},
    "يومي": {"interval": "1h", "period": "3mo"},
}
TV_SYMBOLS = {
    "فوركس": {
        "EUR/USD": "FX:EURUSD", "GBP/USD": "FX:GBPUSD",
        "USD/JPY": "FX:USDJPY", "USD/CHF": "FX:USDCHF",
        "AUD/USD": "FX:AUDUSD", "NZD/USD": "FX:NZDUSD",
        "USD/CAD": "FX:USDCAD", "EUR/GBP": "FX:EURGBP",
        "EUR/JPY": "FX:EURJPY", "GBP/JPY": "FX:GBPJPY",
    },
    "سلع": {
        "الذهب": "COMEX:GC1!", "الفضة": "COMEX:SI1!",
        "النفط": "NYMEX:CL1!", "الغاز": "NYMEX:NG1!",
        "النحاس": "COMEX:HG1!",
    },
    "عملات رقمية": {
        "BTC/USD": "CRYPTO:BTCUSD", "ETH/USD": "CRYPTO:ETHUSD",
        "SOL/USD": "CRYPTO:SOLUSD", "XRP/USD": "CRYPTO:XRPUSD",
        "BNB/USD": "CRYPTO:BNBUSD", "ADA/USD": "CRYPTO:ADAUSD",
        "DOGE/USD": "CRYPTO:DOGEUSD", "AVAX/USD": "CRYPTO:AVAXUSD",
    },
    "أسهم أمريكية": {
        "Apple": "NASDAQ:AAPL", "Tesla": "NASDAQ:TSLA",
        "NVIDIA": "NASDAQ:NVDA", "Google": "NASDAQ:GOOGL",
        "Amazon": "NASDAQ:AMZN", "Microsoft": "NASDAQ:MSFT",
        "Meta": "NASDAQ:META", "Netflix": "NASDAQ:NFLX",
        "AMD": "NASDAQ:AMD", "Intel": "NASDAQ:INTC",
    },
    "مؤشرات": {
        "S&P 500": "FOREXCOM:SPXUSD", "Nasdaq": "NASDAQ:NDX",
        "Dow Jones": "DJ:DJI", "DAX": "XETR:DAX",
        "FTSE 100": "FOREXCOM:UKXGBP",
    }
}


def to_tv_symbol(ticker):
    if ticker.endswith("=X"): return f"FX:{ticker.replace('=X', '')}"
    if ticker.endswith("-USD"): return f"CRYPTO:{ticker.replace('-USD', '')}USD"
    if ticker == "GC=F": return "COMEX:GC1!"
    if ticker == "SI=F": return "COMEX:SI1!"
    if ticker == "CL=F": return "NYMEX:CL1!"
    return f"NASDAQ:{ticker}"


# ============================================================
# AI Client
# ============================================================
client = None
try:
    token = st.secrets.get("HF_TOKEN", "")
    if token:
        client = InferenceClient(model="Qwen/Qwen2.5-72B-Instruct", token=token)
except Exception:
    client = None

# ============================================================
# دوال التحليل
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
            df = stock.history(period=tf["period"], interval=tf["interval"], auto_adjust=True)
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
        m = ta.trend.MACD(c); df['MACD'] = m.macd(); df['MACD_Signal'] = m.macd_signal(); df['MACD_Hist'] = m.macd_diff()
    except: pass
    try: df['RSI'] = ta.momentum.rsi(c, window=14)
    except: pass
    try:
        s = ta.momentum.StochasticOscillator(h, low, c); df['Stoch_K'] = s.stoch(); df['Stoch_D'] = s.stoch_signal()
    except: pass
    try:
        bb = ta.volatility.BollingerBands(c, window=20); df['BB_Upper'] = bb.bollinger_hband(); df['BB_Lower'] = bb.bollinger_lband()
    except: pass
    try: df['ATR'] = ta.volatility.average_true_range(h, low, c)
    except: pass
    try:
        a = ta.trend.ADXIndicator(h, low, c); df['ADX'] = a.adx(); df['DI_plus'] = a.adx_pos(); df['DI_minus'] = a.adx_neg()
    except: pass
    try: df['PSAR'] = ta.trend.PSARIndicator(h, low, c).psar()
    except: pass
    try:
        ich = ta.trend.IchimokuIndicator(h, low); df['Ich_A'] = ich.ichimoku_a(); df['Ich_B'] = ich.ichimoku_b()
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
    curr = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else curr
    price = safe_val(curr['Close'])
    filters = []
    total = 0

    e50 = safe_val(curr.get('EMA_50')); e200 = safe_val(curr.get('EMA_200'))
    if e50 > 0 and e200 > 0:
        if e50 > e200: filters.append(("تقاطع ذهبي", 10, "pass", "صاعد")); total += 10
        else: filters.append(("تقاطع الموت", -10, "fail", "هابط")); total -= 10

    if e200 > 0:
        if price > e200: filters.append(("فوق EMA200", 8, "pass", f"{price:.4f}>{e200:.4f}")); total += 8
        else: filters.append(("تحت EMA200", -8, "fail", f"{price:.4f}<{e200:.4f}")); total -= 8

    e5 = safe_val(curr.get('EMA_5')); e10 = safe_val(curr.get('EMA_10')); e20 = safe_val(curr.get('EMA_20'))
    if all(v > 0 for v in [e5, e10, e20, e50]):
        if e5 > e10 > e20 > e50: filters.append(("EMAs صعودي", 7, "pass", "")); total += 7
        elif e5 < e10 < e20 < e50: filters.append(("EMAs هبوطي", -7, "fail", "")); total -= 7
        else: filters.append(("EMAs مختلط", 0, "warn", ""))

    adx = safe_val(curr.get('ADX')); dip = safe_val(curr.get('DI_plus')); dim = safe_val(curr.get('DI_minus'))
    if adx > 30:
        if dip > dim: filters.append(("ADX صاعد قوي", 8, "pass", f"{adx:.0f}")); total += 8
        else: filters.append(("ADX هابط قوي", -8, "fail", f"{adx:.0f}")); total -= 8
    elif adx > 20:
        if dip > dim: filters.append(("ADX صاعد", 4, "pass", f"{adx:.0f}")); total += 4
        else: filters.append(("ADX هابط", -4, "fail", f"{adx:.0f}")); total -= 4

    psar = safe_val(curr.get('PSAR'))
    if psar > 0:
        if price > psar: filters.append(("PSAR صعودي", 5, "pass", "")); total += 5
        else: filters.append(("PSAR هبوطي", -5, "fail", "")); total -= 5

    ia = safe_val(curr.get('Ich_A')); ib = safe_val(curr.get('Ich_B'))
    if ia > 0 and ib > 0:
        if price > max(ia, ib): filters.append(("فوق إيشيموكو", 6, "pass", "")); total += 6
        elif price < min(ia, ib): filters.append(("تحت إيشيموكو", -6, "fail", "")); total -= 6
        else: filters.append(("داخل السحابة", 0, "warn", ""))

    rsi = safe_val(curr.get('RSI'))
    if rsi > 0:
        if rsi < 25: filters.append(("RSI بيعي شديد", 10, "pass", f"{rsi:.0f}")); total += 10
        elif rsi < 35: filters.append(("RSI قريب بيعي", 5, "pass", f"{rsi:.0f}")); total += 5
        elif rsi > 75: filters.append(("RSI شرائي شديد", -10, "fail", f"{rsi:.0f}")); total -= 10
        elif rsi > 65: filters.append(("RSI قريب شرائي", -5, "fail", f"{rsi:.0f}")); total -= 5
        else: filters.append(("RSI وسط", 0, "warn", f"{rsi:.0f}"))

    mh = safe_val(curr.get('MACD_Hist')); mhp = safe_val(prev.get('MACD_Hist')) if hasattr(prev, 'get') else 0
    if mh > 0 and mhp <= 0: filters.append(("MACD تقاطع صعودي", 8, "pass", "")); total += 8
    elif mh < 0 and mhp >= 0: filters.append(("MACD تقاطع هبوطي", -8, "fail", "")); total -= 8
    elif mh > 0: filters.append(("MACD إيجابي", 4, "pass", "")); total += 4
    elif mh < 0: filters.append(("MACD سلبي", -4, "fail", "")); total -= 4

    sk = safe_val(curr.get('Stoch_K')); sd = safe_val(curr.get('Stoch_D'))
    if sk > 0:
        if sk < 20 and sk > sd: filters.append(("Stoch بيعي+تقاطع", 7, "pass", f"K={sk:.0f}")); total += 7
        elif sk > 80 and sk < sd: filters.append(("Stoch شرائي+تقاطع", -7, "fail", f"K={sk:.0f}")); total -= 7
        elif sk < 20: filters.append(("Stoch بيعي", 4, "pass", f"K={sk:.0f}")); total += 4
        elif sk > 80: filters.append(("Stoch شرائي", -4, "fail", f"K={sk:.0f}")); total -= 4

    cci = safe_val(curr.get('CCI'))
    if cci != 0:
        if cci < -200: filters.append(("CCI بيعي حاد", 6, "pass", f"{cci:.0f}")); total += 6
        elif cci > 200: filters.append(("CCI شرائي حاد", -6, "fail", f"{cci:.0f}")); total -= 6

    wr = safe_val(curr.get('Williams_R'))
    if wr != 0:
        if wr < -80: filters.append(("Williams بيعي", 4, "pass", f"{wr:.0f}")); total += 4
        elif wr > -20: filters.append(("Williams شرائي", -4, "fail", f"{wr:.0f}")); total -= 4

    roc = safe_val(curr.get('ROC'))
    if roc != 0:
        if roc > 5: filters.append(("زخم صعودي", 5, "pass", f"{roc:.1f}%")); total += 5
        elif roc < -5: filters.append(("زخم هبوطي", -5, "fail", f"{roc:.1f}%")); total -= 5

    bbu = safe_val(curr.get('BB_Upper')); bbl = safe_val(curr.get('BB_Lower'))
    if bbu > 0 and bbl > 0:
        if price <= bbl: filters.append(("Bollinger سفلي", 6, "pass", "ارتداد")); total += 6
        elif price >= bbu: filters.append(("Bollinger علوي", -6, "fail", "هبوط")); total -= 6

    atr = safe_val(curr.get('ATR'))
    if atr > 0 and price > 0:
        ap = (atr / price) * 100
        if ap > 3: filters.append(("تذبذب عالي", -3, "warn", f"{ap:.1f}%")); total -= 3
        elif ap < 0.5: filters.append(("تذبذب منخفض", -2, "warn", f"{ap:.1f}%")); total -= 2
        else: filters.append(("تذبذب مناسب", 3, "pass", f"{ap:.1f}%")); total += 3

    mfi = safe_val(curr.get('MFI'))
    if mfi > 0:
        if mfi < 20: filters.append(("MFI بيعي", 5, "pass", f"{mfi:.0f}")); total += 5
        elif mfi > 80: filters.append(("MFI شرائي", -5, "fail", f"{mfi:.0f}")); total -= 5

    if 'OBV' in df.columns and len(df) > 5:
        try:
            on = safe_val(curr.get('OBV')); o5 = safe_val(df.iloc[-5].get('OBV'))
            p5 = safe_val(df.iloc[-5]['Close'])
            if on > o5 and price > p5: filters.append(("OBV صعود", 4, "pass", "")); total += 4
            elif on < o5 and price < p5: filters.append(("OBV هبوط", -4, "fail", "")); total -= 4
            elif on < o5 and price > p5: filters.append(("تباعد OBV", -3, "warn", "")); total -= 3
        except: pass

    if len(df) > 2:
        try:
            co = safe_val(curr.get('Open')); cc = safe_val(curr['Close'])
            po = safe_val(prev.get('Open')); pc = safe_val(prev['Close'])
            if pc < po and cc > co and cc > po and co < pc: filters.append(("ابتلاع صعودي", 7, "pass", "")); total += 7
            elif pc > po and cc < co and cc < po and co > pc: filters.append(("ابتلاع هبوطي", -7, "fail", "")); total -= 7
        except: pass

    if len(df) > 20:
        try:
            rh = df['High'].tail(20).max(); rl = df['Low'].tail(20).min(); rng = rh - rl
            if rng > 0:
                pos = (price - rl) / rng
                if pos < 0.15: filters.append(("قرب دعم", 6, "pass", f"{pos*100:.0f}%")); total += 6
                elif pos > 0.85: filters.append(("قرب مقاومة", -6, "fail", f"{pos*100:.0f}%")); total -= 6
        except: pass

    return total, filters, curr


def get_fundamental_score(info):
    score = 0; details = []
    if not info or not isinstance(info, dict):
        return 0, [("لا بيانات", 0, "warn", "")]

    pe = info.get('trailingPE') or info.get('forwardPE')
    if pe:
        pe = float(pe)
        if 5 < pe < 20: score += 5; details.append(("P/E مناسب", 5, "pass", f"{pe:.1f}"))
        elif pe > 40: score -= 3; details.append(("P/E مرتفع", -3, "fail", f"{pe:.1f}"))

    margin = info.get('profitMargins')
    if margin:
        mp = float(margin) * 100
        if mp > 20: score += 4; details.append(("هامش ممتاز", 4, "pass", f"{mp:.1f}%"))
        elif mp > 10: score += 2; details.append(("هامش جيد", 2, "pass", f"{mp:.1f}%"))
        elif mp < 0: score -= 4; details.append(("خاسرة", -4, "fail", f"{mp:.1f}%"))

    growth = info.get('revenueGrowth')
    if growth:
        gp = float(growth) * 100
        if gp > 20: score += 4; details.append(("نمو ممتاز", 4, "pass", f"{gp:.1f}%"))
        elif gp > 5: score += 2; details.append(("نمو جيد", 2, "pass", f"{gp:.1f}%"))
        elif gp < -5: score -= 3; details.append(("انخفاض", -3, "fail", f"{gp:.1f}%"))

    de = info.get('debtToEquity')
    if de:
        de = float(de)
        if de < 50: score += 3; details.append(("ديون منخفضة", 3, "pass", f"{de:.0f}"))
        elif de > 200: score -= 3; details.append(("ديون عالية", -3, "fail", f"{de:.0f}"))

    if not details: details.append(("لا بيانات", 0, "warn", ""))
    return score, details


def get_news_score(ai_client, ticker, name):
    """أخبار محسّنة بالبحث الحقيقي"""
    news_data = web_search_news(f"{name} {ticker} financial news", max_results=5)

    if not news_data and not ai_client:
        return 0, [("أخبار غير متاحة", 0, "warn", "")]

    news_context = ""
    if news_data:
        news_context = "\n".join([
            f"- [{r.get('date','')}] {r.get('title','')}: {r.get('body','')[:150]}"
            for r in news_data[:5]
        ])

    if not ai_client:
        pos_words = ['surge', 'rise', 'gain', 'bull', 'up', 'high', 'record', 'growth', 'صعود', 'ارتفاع']
        neg_words = ['drop', 'fall', 'crash', 'bear', 'down', 'low', 'loss', 'decline', 'هبوط', 'انخفاض']
        text = news_context.lower()
        pos = sum(1 for w in pos_words if w in text)
        neg = sum(1 for w in neg_words if w in text)
        sc = min(max((pos - neg) * 3, -10), 10)
        st_t = "pass" if sc > 0 else ("fail" if sc < 0 else "warn")
        details = [("تحليل أخبار", sc, st_t, f"+{pos}/-{neg}")]
        for r in news_data[:2]:
            details.append((f"📰 {r.get('title','')[:50]}", 0, "warn", ""))
        return sc, details

    try:
        resp = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "محلل أخبار. JSON فقط."},
                {"role": "user", "content": f'حلل هذه الأخبار الحقيقية عن {name} ({ticker}):\n{news_context}\nJSON: {{"news_sentiment":"إيجابي/سلبي/محايد","score":-10 إلى 10,"key_events":["حدث"],"impact":"تأثير"}}'}
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
        st_t = "pass" if ns > 0 else ("fail" if ns < 0 else "warn")
        d = [(f"أخبار: {data.get('news_sentiment', 'محايد')}", ns, st_t, data.get('impact', ''))]
        for ev in data.get('key_events', [])[:3]:
            d.append((f"📰 {ev}", 0, "warn", ""))
        return ns, d
    except Exception:
        return 0, [("فشل تحليل الأخبار", 0, "warn", "")]


def get_ai_final_decision(ai_client, ticker, name, tech, fund, news, filters, price, hint):
    if not ai_client:
        return None

    market_data = web_search(f"{name} {ticker} price forecast today {datetime.now().strftime('%Y-%m')}", max_results=3)
    market_context = ""
    if market_data:
        market_context = "\nمعلومات حديثة من الويب:\n" + "\n".join([
            f"- {r.get('title','')}: {r.get('body','')[:100]}" for r in market_data[:3]
        ])

    top_f = " | ".join([f"{f[0]}({f[1]:+d})" for f in filters[:8]])
    try:
        resp = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "خبير تداول. JSON فقط."},
                {"role": "user", "content": f'قرار: {name}({ticker}) سعر:{price} فني:{tech} أساسي:{fund} أخبار:{news} اتجاه:{"صعود" if hint > 0 else "هبوط" if hint < 0 else "محايد"} فلاتر:{top_f}{market_context}\nJSON: {{"decision":"شراء قوي/شراء/بيع قوي/بيع/تجنب","confidence":0-100,"reasoning":"بالعربية","risk":"منخفض/متوسط/عالي","ai_score":-15 إلى 15}}'}
            ], max_tokens=300
        )
        txt = resp.choices[0].message.content.strip()
        if "```" in txt:
            for p in txt.split("```"):
                p = p.strip()
                if p.startswith("json"): p = p[4:].strip()
                if p.startswith("{"): txt = p; break
        return json.loads(txt)
    except Exception:
        return None


def calc_targets(curr, score):
    price = safe_val(curr['Close']); atr = safe_val(curr.get('ATR'))
    if atr == 0: atr = price * 0.015
    f = 1 if score > 0 else -1
    sl = price - (2 * atr * f); tp1 = price + (1.5 * atr * f)
    tp2 = price + (3 * atr * f); tp3 = price + (5 * atr * f)
    risk = abs(price - sl); rr = abs(tp2 - price) / risk if risk > 0 else 0
    return {'sl': sl, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'rr': rr}


def final_signal(combined):
    if combined >= 40: return "شراء قوي", "bg-strong-buy"
    elif combined >= 20: return "شراء", "bg-buy"
    elif combined <= -40: return "بيع قوي", "bg-strong-sell"
    elif combined <= -20: return "بيع", "bg-sell"
    return "محايد", "bg-neutral"


def build_filters_text(tech_filters, tech_score, fund_details, fund_score,
                        news_details, news_score, ai_score, ai_reasoning, ai_confidence):
    lines = [f"═══ فني ({tech_score:+d}) ═══"]
    for f in tech_filters:
        i = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
        lines.append(f"{i} {f[0]} ({f[1]:+d}) - {f[3]}")
    lines.append(f"\n═══ أساسي ({fund_score:+d}) ═══")
    for f in fund_details:
        i = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
        lines.append(f"{i} {f[0]} ({f[1]:+d}) - {f[3]}")
    lines.append(f"\n═══ أخبار ({news_score:+d}) ═══")
    for f in news_details:
        i = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
        lines.append(f"{i} {f[0]} ({f[1]:+d}) - {f[3]}")
    lines.append(f"\n═══ AI ({ai_score:+d}) ═══")
    lines.append(f"🤖 {ai_reasoning}")
    lines.append(f"📊 ثقة: {ai_confidence}%")
    return "\n".join(lines)


def full_analysis(ticker, name, tf_key, ai_client, require_strong=False):
    df, info = fetch_data(ticker, tf_key)
    if df is None or len(df) <= 15:
        return None

    df = calculate_indicators(df)
    tech_score, tech_filters, curr = apply_all_filters(df, info)
    fund_score, fund_details = get_fundamental_score(info)
    news_score, news_details = get_news_score(ai_client, ticker, name)
    pre_total = tech_score + fund_score + news_score

    ai_dec = get_ai_final_decision(
        ai_client, ticker, name, tech_score, fund_score,
        news_score, tech_filters, safe_val(curr['Close']), pre_total
    )

    ai_score = 0; ai_reasoning = ""; ai_confidence = 0; ai_risk = "متوسط"

    if ai_dec and isinstance(ai_dec, dict):
        ai_score = int(ai_dec.get('ai_score', 0))
        ai_reasoning = ai_dec.get('reasoning', '')
        ai_confidence = int(ai_dec.get('confidence', 0))
        ai_risk = ai_dec.get('risk', 'متوسط')
        if require_strong:
            dt = ai_dec.get('decision', 'تجنب')
            if ai_confidence < 70 or dt == 'تجنب':
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
        'ticker': ticker, 'name': name, 'price': price,
        'direction': direction, 'signal': sig_label,
        'signal_class': sig_class, 'total_score': final_total,
        'tech_score': tech_score, 'fund_score': fund_score,
        'news_score': news_score, 'ai_score': ai_score,
        'ai_reasoning': ai_reasoning, 'ai_confidence': ai_confidence,
        'ai_risk': ai_risk, 'tech_filters': tech_filters,
        'fund_details': fund_details, 'news_details': news_details,
        'filters_text': filters_text, 'targets': tgts,
        'timeframe': tf_key, 'curr': curr,
    }


def smart_update_signal(sig_row):
    ticker = sig_row['ticker']
    entry = float(sig_row.get('entry_price', 0) or 0)
    tp1 = float(sig_row.get('tp1', 0) or 0)
    tp2 = float(sig_row.get('tp2', 0) or 0)
    sl = float(sig_row.get('sl', 0) or 0)
    is_buy = sig_row.get('direction', 'buy') == 'buy'
    entry_time_str = sig_row.get('timestamp', '')
    sig_tf = sig_row.get('timeframe', '4 ساعات')
    track_config = TRACKING_INTERVALS.get(sig_tf, {"interval": "1h", "period": "1mo"})

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=track_config["period"], interval=track_config["interval"])
        if hist.empty: return None
        if hist.index.tz is not None: hist.index = hist.index.tz_localize(None)

        try: entry_time = pd.to_datetime(entry_time_str)
        except: entry_time = hist.index[0]

        candles = hist[hist.index >= entry_time]
        if candles.empty: candles = hist.tail(50)

        current_price = float(hist['Close'].iloc[-1])
        hit_status = 'active'; hit_time = ''; hit_price = 0; tp1_hit = False

        for idx, candle in candles.iterrows():
            ch = float(candle['High']); cl = float(candle['Low']); ct = str(idx)
            if is_buy:
                if cl <= sl and ch >= tp2:
                    co = float(candle['Open'])
                    if abs(co - sl) < abs(co - tp2): hit_status = 'sl_hit'; hit_price = sl
                    else: hit_status = 'tp_hit'; hit_price = tp2
                    hit_time = ct; break
                elif cl <= sl: hit_status = 'sl_hit'; hit_time = ct; hit_price = sl; break
                elif ch >= tp2: hit_status = 'tp_hit'; hit_time = ct; hit_price = tp2; break
                if ch >= tp1: tp1_hit = True
            else:
                if ch >= sl and cl <= tp2:
                    co = float(candle['Open'])
                    if abs(co - sl) < abs(co - tp2): hit_status = 'sl_hit'; hit_price = sl
                    else: hit_status = 'tp_hit'; hit_price = tp2
                    hit_time = ct; break
                elif ch >= sl: hit_status = 'sl_hit'; hit_time = ct; hit_price = sl; break
                elif cl <= tp2: hit_status = 'tp_hit'; hit_time = ct; hit_price = tp2; break
                if cl <= tp1: tp1_hit = True

        if hit_status == 'tp_hit':
            progress = 100.0
            pnl = ((tp2 - entry) / entry * 100) if is_buy else ((entry - tp2) / entry * 100)
        elif hit_status == 'sl_hit':
            progress = 0.0
            pnl = ((sl - entry) / entry * 100) if is_buy else ((entry - sl) / entry * 100)
        else:
            if is_buy: td = tp2 - entry; cd = current_price - entry; pnl = ((current_price - entry) / entry * 100)
            else: td = entry - tp2; cd = entry - current_price; pnl = ((entry - current_price) / entry * 100)
            progress = (cd / td * 100) if td != 0 else 0
            progress = max(0, min(100, progress))
            if tp1_hit and progress < 50: progress = 50

        return {'current_price': current_price, 'status': hit_status, 'progress': progress, 'pnl': pnl, 'hit_time': hit_time, 'hit_price': hit_price}
    except Exception:
        return None


def background_scan(assets_dict, scan_tf, ai_token):
    ai_client = None
    if ai_token:
        try: ai_client = InferenceClient(model="Qwen/Qwen2.5-72B-Instruct", token=ai_token)
        except: ai_client = None

    total = len(assets_dict); found = 0; scanned = 0
    db.set_scan_status(True, 0, total, 0, 0, 'بدء...')

    for name, tick in assets_dict.items():
        scanned += 1
        db.set_scan_status(True, (scanned / total) * 100, total, scanned, found, name)
        try:
            result = full_analysis(tick, name, scan_tf, ai_client, require_strong=True)
            if result and result['price'] > 0:
                added = db.add_signal(
                    str(tick), str(name), result['direction'],
                    float(result['price']), float(result['targets']['tp1']),
                    float(result['targets']['tp2']), float(result['targets']['tp3']),
                    float(result['targets']['sl']), float(abs(result['total_score'])),
                    str(scan_tf), float(result['tech_score']), float(result['fund_score']),
                    float(result['news_score']), float(result['ai_score']),
                    str(result['filters_text']), str(result['ai_reasoning'])
                )
                if added: found += 1
        except Exception as e:
            print(f"Error scanning {name}: {e}")
            continue
        time.sleep(0.5)

    db.set_scan_status(False, 100, total, scanned, found, 'اكتمل')


# ============================================================
# الواجهة
# ============================================================
st.title("ProTrade Elite 5.0 📊")

required = ['init_db', 'add_signal', 'get_active_signals', 'get_closed_signals',
            'update_signal_status', 'save_analysis', 'set_scan_status',
            'get_scan_status', 'delete_all_active']
missing = [f for f in required if not hasattr(db, f)]
if missing:
    st.error(f"⚠️ db.py ناقص: {', '.join(missing)}")
    st.stop()

# شريط حالة المسح
scan_st = db.get_scan_status()
if scan_st and isinstance(scan_st, dict):
    is_running = scan_st.get('is_running', False)
    scan_found = int(scan_st.get('found_signals', 0) or 0)
    scan_total = int(scan_st.get('total_assets', 0) or 0)
    scan_scanned = int(scan_st.get('scanned_assets', 0) or 0)
    scan_progress = float(scan_st.get('progress', 0) or 0)
    scan_current = scan_st.get('current_asset', '')

    if is_running:
        st.markdown(f"""
        <div class="scan-banner">
            <span>🔄 جاري المسح: {scan_current} ({scan_scanned}/{scan_total})</span>
            <span>وجد: {scan_found} إشارة</span>
        </div>""", unsafe_allow_html=True)
        st.progress(scan_progress / 100)
        time.sleep(3)
        st.rerun()
    elif st.session_state.get('scan_running', False):
        st.session_state.scan_running = False
        st.session_state.scan_complete = True
        st.session_state.scan_results = scan_found

if st.session_state.get('scan_complete', False):
    n_results = st.session_state.get('scan_results', 0)
    if n_results > 0:
        st.markdown(f'<div class="scan-done-banner">✅ اكتمل المسح! تم العثور على {n_results} إشارة قوية</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="scan-done-zero">⚠️ اكتمل المسح! لم يتم العثور على إشارات قوية حالياً.</div>', unsafe_allow_html=True)
    st.session_state.scan_complete = False

with st.expander("☰ القائمة", expanded=False):
    n1, n2, n3, n4 = st.columns(4)
    with n1:
        if st.button("📋 التوصيات", use_container_width=True): st.session_state.current_view = "signals"; st.rerun()
    with n2:
        if st.button("📉 التحليل", use_container_width=True): st.session_state.current_view = "analysis"; st.rerun()
    with n3:
        if st.button("📊 الشارت", use_container_width=True): st.session_state.current_view = "chart"; st.rerun()
    with n4:
        if st.button("🤖 الدردشة", use_container_width=True): st.session_state.current_view = "chat"; st.rerun()

# ============================================================
# التوصيات
# ============================================================
if st.session_state.current_view == "signals":
    st.header("📋 التوصيات الذكية")

    with st.expander("⚙️ إعدادات المسح", expanded=True):
        sc1, sc2, sc3 = st.columns(3)
        with sc1: scan_types = st.multiselect("الأصول", ["فوركس", "عملات رقمية", "أسهم", "الكل"], default=["الكل"])
        with sc2: scan_tf = st.selectbox("الإطار", list(TIMEFRAMES.keys()), index=2)
        with sc3: specific = st.text_input("زوج محدد", placeholder="EURUSD=X")

    ac1, ac2, ac3, ac4 = st.columns(4)
    with ac1: scan_btn = st.button("🔍 مسح شامل", type="primary", use_container_width=True)
    with ac2: update_btn = st.button("🔄 تحديث ذكي", use_container_width=True)
    with ac3: clear_btn = st.button("🗑️ حذف", use_container_width=True)
    with ac4: refresh_btn = st.button("♻️ تحديث", use_container_width=True)

    if refresh_btn: st.rerun()
    if clear_btn:
        db.delete_all_active(); st.success("✅ تم الحذف"); time.sleep(1); st.rerun()

    if scan_btn:
        current_scan = db.get_scan_status()
        if current_scan and current_scan.get('is_running', False):
            st.warning("⚠️ المسح قيد التشغيل!")
        else:
            assets = {}
            if specific.strip(): assets[specific.strip()] = specific.strip()
            else:
                if "الكل" in scan_types: assets.update(FOREX_PAIRS); assets.update(CRYPTO_PAIRS); assets.update(STOCKS)
                else:
                    if "فوركس" in scan_types: assets.update(FOREX_PAIRS)
                    if "عملات رقمية" in scan_types: assets.update(CRYPTO_PAIRS)
                    if "أسهم" in scan_types: assets.update(STOCKS)
            if not assets: st.warning("اختر أصول أولاً")
            else:
                st.session_state.scan_running = True
                scan_thread = threading.Thread(target=background_scan, args=(assets, scan_tf, st.secrets.get("HF_TOKEN", "")), daemon=True)
                scan_thread.start()
                st.success(f"🚀 بدأ المسح لـ {len(assets)} أصل"); time.sleep(2); st.rerun()

    if update_btn:
        active = db.get_active_signals()
        if active:
            uc = 0; prog = st.progress(0); stat = st.empty()
            for i, sr in enumerate(active):
                prog.progress((i + 1) / len(active)); stat.text(f"🔄 {sr.get('asset_name', '')} ({i + 1}/{len(active)})")
                result = smart_update_signal(sr)
                if result:
                    db.update_signal_status(sr['id'], result['current_price'], result['status'], result['progress'], result['pnl'], result.get('hit_time', ''), result.get('hit_price', 0))
                    uc += 1
            prog.empty(); stat.empty()
            st.success(f"✅ تم التحديث: {uc} توصية"); time.sleep(1); st.rerun()
        else: st.warning("لا توصيات نشطة")

    st.subheader("📊 التوصيات النشطة")
    try: sigs = db.get_active_signals()
    except: sigs = []

    with st.expander("🔧 تشخيص", expanded=False):
        st.write(f"نشطة: {len(sigs) if sigs else 0}")
        scan_info = db.get_scan_status()
        if scan_info:
            st.write(f"حالة المسح: {'يعمل' if scan_info.get('is_running') else 'متوقف'}")
            st.write(f"إشارات: {scan_info.get('found_signals', 0)}")
        if st.button("🔄 إعادة قراءة"): st.rerun()

    if sigs and len(sigs) > 0:
        st.success(f"📊 نشطة: {len(sigs)}")
        for sr in sigs:
            try:
                ib = sr.get('direction', 'buy') == 'buy'
                clr = "#00ff88" if ib else "#ff4444"
                dt = "شراء 🟢" if ib else "بيع 🔴"
                sp = float(sr.get('progress', 0) or 0)
                spnl = float(sr.get('pnl_pct', 0) or 0)
                sc = float(sr.get('current_price', 0) or sr.get('entry_price', 0) or 0)
                se = float(sr.get('entry_price', 0) or 0)
                s1v = float(sr.get('tp1', 0) or 0)
                s2v = float(sr.get('tp2', 0) or 0)
                s3v = float(sr.get('tp3', 0) or 0)
                ssl = float(sr.get('sl', 0) or 0)
                sn = sr.get('asset_name', '?')
                stk = sr.get('ticker', '')
                stf = sr.get('timeframe', '')
                sstr = float(sr.get('strength', 0) or 0)
                ts = float(sr.get('technical_score', 0) or 0)
                fs = float(sr.get('fundamental_score', 0) or 0)
                ns = float(sr.get('news_score', 0) or 0)
                ais = float(sr.get('ai_score', 0) or 0)

                st.markdown(f"""
                <div class="rec-card" style="border-left:5px solid {clr};">
                    <div style="display:flex;justify-content:space-between;">
                        <h3 style="margin:0;">{sn} <span style="font-size:0.7em;color:#888;">{stk} | {stf}</span></h3>
                        <div><h3 style="color:{clr};margin:0;">{dt}</h3><span style="font-size:0.8em;color:#aaa;">قوة: {sstr:.0f}</span></div>
                    </div>
                    <div style="font-size:13px;margin:10px 0;display:flex;justify-content:space-between;flex-wrap:wrap;">
                        <span>🏁 {se:.4f}</span><span>🏷️ {sc:.4f}</span>
                        <span>🎯1: {s1v:.4f}</span><span>🎯2: {s2v:.4f}</span>
                        <span>🎯3: {s3v:.4f}</span><span>🛑 {ssl:.4f}</span>
                    </div>
                    <div style="display:flex;gap:10px;margin:8px 0;font-size:12px;">
                        <span style="color:#00bcd4;">فني: {ts:+.0f}</span>
                        <span style="color:#ff9800;">أساسي: {fs:+.0f}</span>
                        <span style="color:#e91e63;">أخبار: {ns:+.0f}</span>
                        <span style="color:#9c27b0;">AI: {ais:+.0f}</span>
                    </div>
                    <div style="background:#111;height:10px;border-radius:5px;">
                        <div style="width:{max(0, min(100, sp))}%;background:{clr};height:100%;border-radius:5px;"></div>
                    </div>
                    <div style="text-align:right;font-size:12px;color:#ccc;">تقدم: {sp:.1f}% | ربح: <span style="color:{clr}">{spnl:.2f}%</span></div>
                </div>""", unsafe_allow_html=True)

                with st.expander(f"📋 تفاصيل - {sn}"):
                    fd = sr.get('filters_detail', '')
                    ar = sr.get('ai_reasoning', '')
                    if fd: st.text(fd)
                    if ar: st.info(f"🤖 {ar}")
            except Exception as e:
                st.error(f"خطأ: {e}"); continue
    else:
        st.info("📭 لا توصيات نشطة. اضغط '🔍 مسح شامل'")

    st.markdown("---")
    st.subheader("📜 المنتهية")
    try: closed = db.get_closed_signals()
    except: closed = []
    if closed:
        hd = []
        for cr in closed:
            try:
                hd.append({
                    "التاريخ": cr.get('timestamp', ''), "الأصل": cr.get('asset_name', ''),
                    "الاتجاه": "شراء" if cr.get('direction') == 'buy' else "بيع",
                    "النتيجة": "✅" if cr.get('status') == 'tp_hit' else "❌",
                    "سعر الإصابة": f"{float(cr.get('hit_price', 0) or 0):.4f}",
                    "الربح%": round(float(cr.get('pnl_pct', 0) or 0), 2)
                })
            except: continue
        if hd: st.dataframe(pd.DataFrame(hd), use_container_width=True, hide_index=True)
    else:
        st.info("لا توصيات منتهية")

# ============================================================
# التحليل
# ============================================================
elif st.session_state.current_view == "analysis":
    st.header("📉 التحليل المتقدم")

    a1, a2, a3, a4 = st.columns(4)
    with a1: ac = st.selectbox("نوع", ["فوركس", "عملات رقمية", "أسهم"])
    with a2:
        if ac == "فوركس": sel = st.selectbox("الأصل", list(FOREX_PAIRS.keys())); ticker = FOREX_PAIRS[sel]
        elif ac == "عملات رقمية": sel = st.selectbox("الأصل", list(CRYPTO_PAIRS.keys())); ticker = CRYPTO_PAIRS[sel]
        else: sel = st.selectbox("الأصل", list(STOCKS.keys())); ticker = STOCKS[sel]
    with a3: tf_l = st.selectbox("الإطار", list(TIMEFRAMES.keys()), index=2)
    with a4: abtn = st.button("🚀 تحليل شامل", type="primary", use_container_width=True)

    if abtn:
        with st.spinner("جاري التحليل..."):
            result = full_analysis(ticker, sel, tf_l, client, require_strong=False)
            if result:
                st.session_state.analysis_result = result
                try:
                    db.save_analysis(ticker, tf_l, result['signal'], result['signal_class'],
                        result['total_score'], result['price'], result['targets'],
                        {'final_decision': result['signal'], 'risk_level': result['ai_risk']},
                        result['tech_score'], result['fund_score'], result['news_score'],
                        result['ai_score'], result['filters_text'], result['ai_reasoning'])
                except: pass
            else: st.error("فشل التحليل")

    if 'analysis_result' in st.session_state:
        r = st.session_state.analysis_result
        st.markdown(f"""
        <div class="main-signal {r['signal_class']}">
            {r['signal']} ({r['total_score']:.1f})
            <div style="font-size:16px;opacity:0.8;">{r['ticker']} | {r['price']:.4f}</div>
        </div>""", unsafe_allow_html=True)

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

        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 الرسم", "📐 الفلاتر", "📊 أساسي", "📰 أخبار", "🤖 AI"])

        with tab1:
            tv_s = to_tv_symbol(r['ticker']); tv_i = TV_INTERVALS.get(r['timeframe'], 'D')
            st.components.v1.html(f"""
            <div style="height:500px;width:100%"><div id="tv"></div>
            <script src="https://s3.tradingview.com/tv.js"></script>
            <script>new TradingView.widget({{"width":"100%","height":"500","symbol":"{tv_s}","interval":"{tv_i}","theme":"dark","style":"1","locale":"ar","container_id":"tv"}});</script></div>""", height=520)

        with tab2:
            st.subheader(f"الفلاتر ({r['tech_score']:+d})")
            for f in r['tech_filters']:
                i = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
                st.markdown(f"{i} **{f[0]}** ({f[1]:+d}) — {f[3]}")

        with tab3:
            st.subheader(f"أساسي ({r['fund_score']:+d})")
            for f in r['fund_details']:
                i = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
                st.markdown(f"{i} **{f[0]}** ({f[1]:+d}) — {f[3]}")

        with tab4:
            st.subheader(f"أخبار ({r['news_score']:+d})")
            for f in r['news_details']:
                i = "✅" if f[2] == "pass" else ("❌" if f[2] == "fail" else "⚠️")
                st.markdown(f"{i} **{f[0]}** ({f[1]:+d}) — {f[3]}")

        with tab5:
            st.subheader(f"AI ({r['ai_score']:+d})")
            if r['ai_reasoning']:
                st.info(f"🤖 {r['ai_reasoning']}")
                st.write(f"📊 ثقة: **{r['ai_confidence']}%**")
                risk = r.get('ai_risk', 'متوسط')
                if risk == "عالي": st.error(f"⚠️ مخاطرة: {risk}")
                elif risk == "منخفض": st.success(f"✅ مخاطرة: {risk}")
                else: st.warning(f"⚡ مخاطرة: {risk}")
            else: st.warning("AI غير مفعل")

# ============================================================
# الشارت
# ============================================================
elif st.session_state.current_view == "chart":
    if not st.session_state.get('chart_fullscreen'):
        st.header("📊 الشارت المتقدم")
        tc1, tc2, tc3, tc4 = st.columns([2, 2, 1, 1])
        with tc1: chart_category = st.selectbox("الفئة", list(TV_SYMBOLS.keys()), key="chart_cat")
        with tc2:
            symbols_in_cat = TV_SYMBOLS[chart_category]
            chart_asset = st.selectbox("الأصل", list(symbols_in_cat.keys()), key="chart_asset")
            selected_symbol = symbols_in_cat[chart_asset]
        with tc3:
            chart_tf = st.selectbox("الإطار", ["1", "5", "15", "30", "60", "240", "D", "W", "M"], index=5,
                format_func=lambda x: {"1":"1د","5":"5د","15":"15د","30":"30د","60":"1س","240":"4س","D":"يومي","W":"أسبوعي","M":"شهري"}.get(x,x), key="chart_tf")
        with tc4:
            if st.button("🔲 ملء الشاشة", use_container_width=True):
                st.session_state.chart_fullscreen = True; st.session_state.chart_symbol = selected_symbol; st.session_state.chart_interval = chart_tf; st.rerun()

        c1, c2 = st.columns([3, 1])
        with c1:
            custom_symbol = st.text_input("رمز مخصص", placeholder="BINANCE:BTCUSDT", key="custom_sym")
        with c2:
            if custom_symbol.strip(): selected_symbol = custom_symbol.strip(); st.success(f"✅ {selected_symbol}")

        st.components.v1.html(f"""
        <div id="tv_advanced" style="height:650px;width:100%;"></div>
        <script src="https://s3.tradingview.com/tv.js"></script>
        <script>new TradingView.widget({{"width":"100%","height":650,"symbol":"{selected_symbol}","interval":"{chart_tf}","timezone":"Etc/UTC","theme":"dark","style":"1","locale":"ar","toolbar_bg":"#1a1a2e","enable_publishing":false,"hide_side_toolbar":false,"allow_symbol_change":true,"save_image":true,"studies":["MAExp@tv-basicstudies","RSI@tv-basicstudies","MACD@tv-basicstudies"],"show_popup_button":true,"popup_width":"1000","popup_height":"650","container_id":"tv_advanced","withdateranges":true,"details":true,"hotlist":true,"calendar":true,"watchlist":true}});</script>""", height=670)
    else:
        if st.button("✕ خروج", key="exit_fs"): st.session_state.chart_fullscreen = False; st.rerun()
        sym = st.session_state.get('chart_symbol', 'FX:EURUSD'); intv = st.session_state.get('chart_interval', 'D')
        st.markdown('<style>.main .block-container{padding:0!important;max-width:100%!important;}</style>', unsafe_allow_html=True)
        st.components.v1.html(f"""
        <div id="tv_fs" style="height:95vh;width:100%;"></div>
        <script src="https://s3.tradingview.com/tv.js"></script>
        <script>new TradingView.widget({{"width":"100%","height":"95%","symbol":"{sym}","interval":"{intv}","timezone":"Etc/UTC","theme":"dark","style":"1","locale":"ar","toolbar_bg":"#1a1a2e","enable_publishing":false,"hide_side_toolbar":false,"allow_symbol_change":true,"save_image":true,"studies":["MAExp@tv-basicstudies","RSI@tv-basicstudies","MACD@tv-basicstudies","BB@tv-basicstudies"],"show_popup_button":true,"popup_width":"1200","popup_height":"800","container_id":"tv_fs","withdateranges":true,"details":true,"hotlist":true,"calendar":true,"watchlist":true}});</script>""", height=900)

# ============================================================
# الدردشة - مع بحث ويب حقيقي
# ============================================================
elif st.session_state.current_view == "chat":
    st.header("🤖 المستشار المالي الذكي")
    st.caption("🌐 مدعوم ببحث الويب المباشر - معلومات محدثة لحظياً")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    ui = st.chat_input("سؤالك...")

    if ui:
        st.session_state.messages.append({"role": "user", "content": ui})
        with st.chat_message("user"):
            st.markdown(ui)

        with st.chat_message("assistant"):
            if client:
                try:
                    with st.spinner("🔍 جاري البحث في الويب..."):
                        search_context, search_results, news_results = build_search_context(ui)

                    sp = f"""أنت مستشار مالي خبير. أجب بالعربية فقط.
تاريخ اليوم: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC

قواعد صارمة:
1. أجب بالعربية فقط دائماً
2. ممنوع كتابة أي كود أو استخدام ```
3. استخدم المعلومات الحديثة من نتائج البحث أدناه
4. اذكر أن المعلومات من مصادر حديثة
5. كن دقيقاً في الأرقام والتواريخ
6. حذر دائماً من مخاطر التداول
7. إذا لم تجد معلومات كافية، قل ذلك بصراحة

{search_context}"""

                    ms = [{"role": "system", "content": sp}]
                    for m in st.session_state.messages[-6:]:
                        ms.append({"role": m["role"], "content": m["content"]})

                    resp = client.chat_completion(messages=ms, max_tokens=800, stream=False)
                    rt = resp.choices[0].message.content

                    if "```" in rt:
                        cl = []
                        ic = False
                        for ln in rt.split('\n'):
                            if '```' in ln: ic = not ic; continue
                            if not ic: cl.append(ln)
                        rt = '\n'.join(cl)
                    rt = rt.replace('`', '')

                    sources_html = format_sources_html(search_results, news_results)
                    full_response = rt + "\n\n" + sources_html if sources_html else rt

                    st.markdown(full_response, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})

                except Exception as e:
                    st.error(f"⚠️ خطأ: {e}")
            else:
                # حتى بدون AI، نبحث في الويب ونعرض النتائج
                try:
                    with st.spinner("🔍 جاري البحث..."):
                        search_context, search_results, news_results = build_search_context(ui)

                    if search_results or news_results:
                        response = "🔍 **نتائج البحث:**\n\n"
                        if news_results:
                            response += "**📰 آخر الأخبار:**\n"
                            for r in news_results[:5]:
                                response += f"- **{r.get('title', '')}**\n  {r.get('body', '')[:200]}\n\n"
                        if search_results:
                            response += "**🔗 نتائج أخرى:**\n"
                            for r in search_results[:5]:
                                response += f"- **{r.get('title', '')}**\n  {r.get('body', '')[:200]}\n\n"

                        response += "\n⚠️ *أضف HF_TOKEN للحصول على تحليل ذكي للنتائج*"
                        sources_html = format_sources_html(search_results, news_results)
                        full_response = response + "\n\n" + sources_html

                        st.markdown(full_response, unsafe_allow_html=True)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})
                    else:
                        st.error("⚠️ لم يتم العثور على نتائج. أضف HF_TOKEN للدردشة الذكية.")
                except Exception:
                    st.error("⚠️ أضف HF_TOKEN في إعدادات التطبيق.")

    if st.session_state.messages:
        if st.button("🗑️ مسح المحادثة"):
            st.session_state.messages = []; st.rerun()