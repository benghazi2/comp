--- START OF FILE app.py ---

import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import numpy as np
from huggingface_hub import InferenceClient
import json
import time
from datetime import datetime
import base64
import db  # استيراد ملف قاعدة البيانات

# ============================================================
# 1. إعداد الصفحة وتنسيق CSS (تم الإصلاح)
# ============================================================
st.set_page_config(
    page_title="ProTrade Elite 5.0", 
    layout="wide", 
    page_icon="📈",
    initial_sidebar_state="expanded"
)

# تهيئة قاعدة البيانات عند بدء التشغيل
try:
    db.init_db()
except Exception as e:
    st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")

# CSS احترافي - إصلاح الشريط الجانبي وإخفاء الشعارات
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    /* تعيين الخط العام وضبط تباعد الأسطر لمنع التداخل */
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        line-height: 1.6 !important; 
    }
    
    /* إخفاء القائمة العلوية وأزرار Github و Deploy وشعار Streamlit */
    [data-testid="stToolbar"] {
        visibility: hidden !important;
        display: none !important;
    }
    
    header[data-testid="stHeader"] {
        background: transparent !important;
        z-index: 1;
    }
    
    /* إخفاء الزخرفة العلونية */
    [data-testid="stDecoration"] {
        visibility: hidden !important;
        display: none !important;
    }

    /* إخفاء الفوتر */
    footer {
        visibility: hidden !important;
        display: none !important;
    }

    /* ============================================================ */
    /* إصلاح الشريط الجانبي (Sidebar Fixes) */
    /* ============================================================ */
    
    /* التأكد من ظهور قسم الشريط الجانبي */
    section[data-testid="stSidebar"] {
        background-color: #0e1117 !important;
        border-right: 1px solid #1f2937;
        width: 300px !important; /* عرض ثابت لضمان الظهور */
        display: block !important;
        visibility: visible !important;
    }
    
    /* تحسين زر إغلاق/فتح الشريط الجانبي ليكون ظاهراً دائماً */
    [data-testid="stSidebarCollapsedControl"] {
        display: block !important;
        visibility: visible !important;
        color: #00ff88 !important;
        background-color: rgba(14, 17, 23, 0.8);
        border-radius: 50%;
        padding: 4px;
        z-index: 1000000; /* طبقة عالية جداً ليظهر فوق أي شيء */
    }

    /* تنسيق شريط التمرير */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #1a1a2e;
    }
    ::-webkit-scrollbar-thumb {
        background: #0f3460;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #e94560;
    }
    
    /* البطاقات والتنسيقات */
    .main-signal {
        padding: 25px; 
        border-radius: 15px; 
        text-align: center;
        font-size: 24px; 
        font-weight: bold; 
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2); 
        margin-bottom: 20px;
        border: 1px solid rgba(255,255,255,0.1);
    }
    
    .bg-strong-buy {background: linear-gradient(135deg, #00b09b, #96c93d);}
    .bg-buy {background: linear-gradient(135deg, #11998e, #38ef7d);}
    .bg-strong-sell {background: linear-gradient(135deg, #cb2d3e, #ef473a);}
    .bg-sell {background: linear-gradient(135deg, #e53935, #ff6f60);}
    .bg-neutral {background: linear-gradient(135deg, #536976, #292E49);}
    
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 20px; 
        border-radius: 12px; 
        text-align: center;
        border: 1px solid #2d3748; 
        color: white; 
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .metric-card h3 {
        color: #a0aec0; 
        margin: 0; 
        font-size: 14px;
        font-weight: 600;
    }
    
    .metric-card h2 {
        color: #00ff88; 
        margin: 10px 0 0 0; 
        font-size: 22px;
        font-weight: 700;
    }
    
    .rec-card {
        background: #111827;
        border-radius: 12px; 
        padding: 20px; 
        margin: 15px 0;
        border: 1px solid #374151;
        border-left: 5px solid; 
        color: white;
    }
    
    .rec-buy {border-color: #00ff88;}
    .rec-sell {border-color: #ff4444;}
    .rec-strong-buy {border-color: #00ff88; box-shadow: 0 0 15px rgba(0,255,136,0.1);}
    .rec-strong-sell {border-color: #ff4444; box-shadow: 0 0 15px rgba(255,68,68,0.1);}
    
    /* تحسينات للجوال */
    @media (max-width: 768px) {
        .main-signal {font-size: 18px; padding: 15px;}
        .metric-card h2 {font-size: 18px;}
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 2. إدارة البيانات (Local Storage / Session)
# ============================================================

def init_session_state():
    defaults = {
        'messages': [],
        'analysis_history': [],
        'strong_signals': [],
        'saved_signals': [],
        'ok': False,
        'data': None,
        'curr': None,
        'info': None,
        'ticker': None,
        'tf': None,
        'ts': 0,
        'td': [],
        'fs': 0,
        'fd': [],
        'tgts': {},
        'ai_v': None,
        'sig': '',
        'sig_cls': '',
        'comb': 0,
        'sigs': {},
        'cons': 0,
        'last_update': None,
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

def export_data_to_json():
    """تجهيز البيانات للتصدير كملف JSON"""
    data = {
        'analysis_history': st.session_state.analysis_history,
        'strong_signals': st.session_state.strong_signals,
        'saved_signals': st.session_state.saved_signals,
        'messages': st.session_state.messages,
        'timestamp': datetime.now().isoformat()
    }
    return json.dumps(data, ensure_ascii=False, indent=2)

def import_data_from_json(json_content):
    """استيراد البيانات من ملف JSON"""
    try:
        data = json.loads(json_content)
        st.session_state.analysis_history = data.get('analysis_history', [])
        st.session_state.strong_signals = data.get('strong_signals', [])
        st.session_state.saved_signals = data.get('saved_signals', [])
        st.session_state.messages = data.get('messages', [])
        return True
    except Exception as e:
        st.error(f"خطأ في الاستيراد: {e}")
        return False

# ============================================================
# 3. بيانات الأصول (Assets)
# ============================================================
FOREX_PAIRS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "USD/CHF": "USDCHF=X", "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X", "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X", "Gold": "GC=F", "Silver": "SI=F", "Oil": "CL=F"
}
CRYPTO_PAIRS = {
    "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "SOL/USD": "SOL-USD",
    "XRP/USD": "XRP-USD", "BNB/USD": "BNB-USD", "DOGE/USD": "DOGE-USD",
    "ADA/USD": "ADA-USD", "MATIC/USD": "MATIC-USD"
}
STOCKS = {
    "Apple": "AAPL", "Microsoft": "MSFT", "Google": "GOOGL",
    "Amazon": "AMZN", "Tesla": "TSLA", "Meta": "META",
    "NVIDIA": "NVDA", "S&P 500": "^GSPC", "Nasdaq": "^IXIC"
}
TIMEFRAMES = {
    "1 دقيقة": {"interval": "1m", "period": "1d"},
    "5 دقائق": {"interval": "5m", "period": "5d"},
    "15 دقيقة": {"interval": "15m", "period": "5d"},
    "30 دقيقة": {"interval": "30m", "period": "1mo"},
    "1 ساعة": {"interval": "1h", "period": "1mo"},
    "4 ساعات": {"interval": "1h", "period": "3mo"},
    "يومي": {"interval": "1d", "period": "1y"},
    "أسبوعي": {"interval": "1wk", "period": "2y"},
}
TV_INTERVALS = {
    "1 دقيقة": "1", "5 دقائق": "5", "15 دقيقة": "15",
    "30 دقيقة": "30", "1 ساعة": "60", "4 ساعات": "240",
    "يومي": "D", "أسبوعي": "W"
}

def to_tv_symbol(ticker):
    ticker = ticker.upper()
    if ticker.endswith("=X"): return f"FX:{ticker.replace('=X', '')}"
    if ticker.endswith("-USD"): return f"CRYPTO:{ticker.replace('-USD', '')}USD"
    if ticker == "GC=F": return "COMEX:GC1!"
    if ticker == "CL=F": return "NYMEX:CL1!"
    if ticker == "SI=F": return "COMEX:SI1!"
    if ticker == "^GSPC": return "SP:SPX"
    if ticker == "^IXIC": return "NASDAQ:IXIC"
    return f"NASDAQ:{ticker}"

# ============================================================
# 4. الذكاء الاصطناعي (AI)
# ============================================================
try:
    # يفضل وضع التوكن في .streamlit/secrets.toml
    token = st.secrets.get("HF_TOKEN", "")
    client = InferenceClient(model="Qwen/Qwen2.5-72B-Instruct", token=token) if token else None
except: 
    client = None

# ============================================================
# 5. دوال التحليل والمؤشرات
# ============================================================

def safe_val(value, default=0.0):
    if value is None: return default
    try:
        v = float(value)
        return default if (np.isnan(v) or np.isinf(v)) else v
    except: return default

def get_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        # محاولة سريعة
        try:
            p = stock.fast_info.get('lastPrice', None)
            if p and p > 0: return float(p)
        except: pass
        
        # محاولة عبر info
        try:
            info = stock.info
            p = info.get('regularMarketPrice') or info.get('currentPrice')
            if p and float(p) > 0: return float(p)
        except: pass
        
        # محاولة أخيرة عبر التاريخ
        hist = stock.history(period="1d")
        if not hist.empty: return float(hist['Close'].iloc[-1])
    except: pass
    return None

def fetch_data(ticker, tf_key, max_retries=2):
    ticker = ticker.strip().upper()
    tf = TIMEFRAMES[tf_key]
    
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            if tf_key == "4 ساعات":
                df = stock.history(period="3mo", interval="1h")
                if not df.empty:
                    if df.index.tz is not None: df.index = df.index.tz_localize(None)
                    df = df.resample('4h').agg({
                        'Open': 'first', 'High': 'max', 'Low': 'min',
                        'Close': 'last', 'Volume': 'sum'
                    }).dropna()
            else:
                df = stock.history(period=tf["period"], interval=tf["interval"], auto_adjust=True)
            
            if df is not None and not df.empty and len(df) > 10:
                if df.index.tz is not None: df.index = df.index.tz_localize(None)
                try: info = stock.info
                except: info = {}
                return df, info
            
            time.sleep(1)
        except:
            time.sleep(1)
    return None, None

def calculate_indicators(df):
    n = len(df)
    c = df['Close']
    h = df['High']
    l = df['Low']
    
    # المتوسطات
    for w in [10, 20, 50, 200]:
        if n > w:
            df[f'EMA_{w}'] = ta.trend.ema_indicator(c, window=w)
        else:
            df[f'EMA_{w}'] = np.nan

    # MACD
    try:
        macd = ta.trend.MACD(c)
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff()
    except: pass

    # RSI
    try: df['RSI'] = ta.momentum.rsi(c, window=14)
    except: df['RSI'] = np.nan

    # Bollinger Bands
    try:
        bb = ta.volatility.BollingerBands(c, window=20, window_dev=2)
        df['BB_Upper'] = bb.bollinger_hband()
        df['BB_Lower'] = bb.bollinger_lband()
    except: pass
    
    # ATR
    try: df['ATR'] = ta.volatility.average_true_range(h, l, c, window=14)
    except: df['ATR'] = np.nan

    # ADX
    if n > 14:
        try:
            adx = ta.trend.ADXIndicator(h, l, c, window=14)
            df['ADX'] = adx.adx()
            df['DI_plus'] = adx.adx_pos()
            df['DI_minus'] = adx.adx_neg()
        except: pass

    # Pivot Points
    df['Pivot'] = (h.shift(1) + l.shift(1) + c.shift(1)) / 3
    df['R1'] = 2 * df['Pivot'] - l.shift(1)
    df['S1'] = 2 * df['Pivot'] - h.shift(1)

    return df

def smart_technical_score(df):
    curr = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else curr
    price = safe_val(curr['Close'])
    score = 0
    details = []
    signals = {"buy": 0, "sell": 0, "neutral": 0}

    # تحليل المتوسطات
    ema50 = safe_val(curr.get('EMA_50'))
    ema200 = safe_val(curr.get('EMA_200'))
    
    if ema200 > 0:
        if price > ema200:
            score += 10
            signals['buy'] += 1
            details.append(("فوق EMA 200", "+10", "green"))
        else:
            score -= 10
            signals['sell'] += 1
            details.append(("تحت EMA 200", "-10", "red"))
            
    if ema50 > 0 and ema200 > 0:
        if ema50 > ema200:
            score += 5
            details.append(("الترند العام صاعد (تقاطع ذهبي)", "+5", "green"))
        else:
            score -= 5
            details.append(("الترند العام هابط", "-5", "red"))

    # RSI
    rsi = safe_val(curr.get('RSI'))
    if rsi > 0:
        if rsi < 30:
            score += 8
            signals['buy'] += 1
            details.append((f"RSI تشبع بيعي ({rsi:.1f})", "+8", "green"))
        elif rsi > 70:
            score -= 8
            signals['sell'] += 1
            details.append((f"RSI تشبع شرائي ({rsi:.1f})", "-8", "red"))
        else:
            signals['neutral'] += 1

    # MACD
    macdh = safe_val(curr.get('MACD_Hist'))
    prev_macdh = safe_val(prev.get('MACD_Hist'))
    if macdh > 0 and prev_macdh <= 0:
        score += 8
        signals['buy'] += 1
        details.append(("تقاطع MACD إيجابي", "+8", "green"))
    elif macdh < 0 and prev_macdh >= 0:
        score -= 8
        signals['sell'] += 1
        details.append(("تقاطع MACD سلبي", "-8", "red"))

    # Bollinger Bands
    bb_l = safe_val(curr.get('BB_Lower'))
    bb_u = safe_val(curr.get('BB_Upper'))
    if bb_l > 0:
        if price <= bb_l:
            score += 6
            signals['buy'] += 1
            details.append(("ارتداد من بولنجر السفلي", "+6", "green"))
        elif price >= bb_u:
            score -= 6
            signals['sell'] += 1
            details.append(("ارتداد من بولنجر العلوي", "-6", "red"))

    # ADX
    adx = safe_val(curr.get('ADX'))
    di_p = safe_val(curr.get('DI_plus'))
    di_m = safe_val(curr.get('DI_minus'))
    if adx > 25:
        if di_p > di_m:
            score += 5
            details.append(("اتجاه قوي صاعد", "+5", "green"))
        else:
            score -= 5
            details.append(("اتجاه قوي هابط", "-5", "red"))

    return score, details, curr, signals, 0

def fundamental_score(info):
    score = 0
    details = []
    if not info: return 0, [("لا توجد بيانات", "0", "gray")]
    
    # PE Ratio
    pe = info.get('trailingPE')
    if pe:
        if 0 < pe < 20: 
            score += 10
            details.append((f"مكرر ربحية جيد ({pe:.1f})", "+10", "green"))
        elif pe > 40:
            score -= 5
            details.append((f"مكرر ربحية مرتفع ({pe:.1f})", "-5", "red"))
            
    # Margins
    margin = info.get('profitMargins')
    if margin:
        m = margin * 100
        if m > 20:
            score += 5
            details.append((f"هامش ربح مرتفع ({m:.1f}%)", "+5", "green"))
    
    # Recommendation
    rec = info.get('recommendationKey', '').lower()
    if 'buy' in rec:
        score += 5
        details.append(("توصية المحللين: شراء", "+5", "green"))
    elif 'sell' in rec:
        score -= 5
        details.append(("توصية المحللين: بيع", "-5", "red"))
        
    if not details: details.append(("بيانات محايدة", "0", "gray"))
    return score, details

def calc_targets(curr, t_score):
    price = safe_val(curr['Close'])
    atr = safe_val(curr.get('ATR'))
    if atr == 0: atr = price * 0.015
    
    is_buy = t_score > 0
    factor = 1 if is_buy else -1
    
    sl = price - (2 * atr * factor)
    tp1 = price + (1.5 * atr * factor)
    tp2 = price + (3 * atr * factor)
    tp3 = price + (5 * atr * factor)
    
    rr = abs(tp2 - price) / abs(price - sl) if abs(price - sl) > 0 else 0
    return {'sl': sl, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'rr': rr}

def final_signal(t_score, f_score):
    # وزن الفني 70% والأساسي 30%
    combined = (t_score * 0.7) + (f_score * 0.3)
    
    if combined >= 25: return "شراء قوي", "bg-strong-buy", combined
    elif combined >= 10: return "شراء", "bg-buy", combined
    elif combined <= -25: return "بيع قوي", "bg-strong-sell", combined
    elif combined <= -10: return "بيع", "bg-sell", combined
    return "محايد", "bg-neutral", combined

def get_ai_verdict(client, ticker, ts, fs, td, fd, curr):
    if not client: return None
    
    tech_txt = ", ".join([t[0] for t in td[:5]])
    prompt = f"""
    أنت خبير مالي. حلل باختصار شديد:
    الأصل: {ticker}
    السعر: {safe_val(curr['Close'])}
    التحليل الفني: {ts} ({tech_txt})
    التحليل الأساسي: {fs}
    
    المطلوب رد بتنسيق JSON فقط:
    {{"decision": "شراء/بيع/محايد", "reason": "سبب مختصر بالعربية", "risk": "منخفض/عالي"}}
    """
    try:
        resp = client.chat_completion(
            messages=[{"role":"user", "content":prompt}], 
            max_tokens=200
        )
        txt = resp.choices[0].message.content
        if "```" in txt: txt = txt.split("```json")[-1].split("```")[0]
        return json.loads(txt)
    except: return None

# ============================================================
# 6. الشريط الجانبي (Sidebar)
# ============================================================

with st.sidebar:
    st.markdown("## 📊 ProTrade Elite")
    
    # 1. قسم إدارة الذاكرة وقاعدة البيانات
    with st.expander("💾 إدارة البيانات", expanded=False):
        st.info(f"يتم حفظ التحليلات في: {db.DB_NAME}")
        
        # خيار الحفظ المحلي كملف JSON (كما كان سابقاً)
        json_data = export_data_to_json()
        st.download_button(
            label="📥 نسخة احتياطية (JSON)",
            data=json_data,
            file_name=f"protrade_backup_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True
        )
        
        uploaded_file = st.file_uploader("📤 استرجاع JSON", type=['json'])
        if uploaded_file:
            if import_data_from_json(uploaded_file.read().decode()):
                st.success("✅ تم الاسترجاع!")
                time.sleep(1)
                st.rerun()

    st.divider()

    # 2. إعدادات التحليل
    asset_class = st.selectbox("نوع الأصل", ["فوركس", "عملات رقمية", "أسهم أمريكية"], index=0)
    
    if asset_class == "فوركس":
        pair = st.selectbox("اختر الزوج", list(FOREX_PAIRS.keys()))
        ticker = FOREX_PAIRS[pair]
    elif asset_class == "عملات رقمية":
        pair = st.selectbox("اختر العملة", list(CRYPTO_PAIRS.keys()))
        ticker = CRYPTO_PAIRS[pair]
    else:
        pair = st.selectbox("اختر السهم", list(STOCKS.keys()))
        ticker = STOCKS[pair]
        
    tf_label = st.selectbox("الإطار الزمني", list(TIMEFRAMES.keys()), index=6)
    
    if st.button("🚀 تحليل الآن", type="primary", use_container_width=True):
        with st.spinner("جاري جلب البيانات وتحليل السوق..."):
            df, info = fetch_data(ticker, tf_label)
            if df is not None:
                df = calculate_indicators(df)
                ts, td, curr, sigs, _ = smart_technical_score(df)
                fs, fd = fundamental_score(info)
                sig, cls, comb = final_signal(ts, fs)
                tgts = calc_targets(curr, ts)
                
                ai_res = get_ai_verdict(client, ticker, ts, fs, td, fd, curr)
                
                # حفظ النتيجة في قاعدة البيانات
                try:
                    db.save_analysis(ticker, tf_label, sig, cls, comb, safe_val(curr['Close']), tgts, ai_res)
                except Exception as e:
                    st.warning(f"لم يتم الحفظ في قاعدة البيانات: {e}")

                # تحديث الحالة (Session State) للعرض الحالي
                st.session_state.update({
                    'ok': True, 'ticker': ticker, 'tf': tf_label,
                    'data': df, 'curr': curr, 'info': info,
                    'ts': ts, 'td': td, 'fs': fs, 'fd': fd,
                    'sig': sig, 'sig_cls': cls, 'comb': comb,
                    'tgts': tgts, 'ai_v': ai_res, 'sigs': sigs
                })
                st.rerun()
            else:
                st.error("فشل في جلب البيانات، حاول مجدداً.")

    st.divider()
    st.info("نظام ProTrade v5.0 - التحليل الاحترافي")

# ============================================================
# 7. الواجهة الرئيسية
# ============================================================

# شريط الأسعار المتحرك (TradingView Widget)
st.components.v1.html("""
<div class="tradingview-widget-container">
  <div class="tradingview-widget-container__widget"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
  {
  "symbols": [{"proName": "FX:EURUSD", "title": "EUR/USD"}, {"proName": "BITSTAMP:BTCUSD", "title": "BTC/USD"}, {"proName": "NASDAQ:AAPL", "title": "Apple"}],
  "showSymbolLogo": true, "colorTheme": "dark", "isTransparent": true, "displayMode": "adaptive", "locale": "ar"
  }
  </script>
</div>
""", height=50)

st.title("ProTrade Elite 5.0 📊")

if st.session_state.get('ok'):
    # جلب البيانات من الحالة
    curr = st.session_state['curr']
    sig = st.session_state['sig']
    cls = st.session_state['sig_cls']
    comb = st.session_state['comb']
    tkr = st.session_state['ticker']
    tgts = st.session_state['tgts']
    price = safe_val(curr['Close'])
    
    # 1. بطاقة الإشارة الرئيسية
    st.markdown(f"""
    <div class="main-signal {cls}">
        <div>{sig}</div>
        <div style="font-size:16px; margin-top:5px; opacity:0.9;">
            {tkr} | السعر: {price:.4f} | القوة: {abs(comb):.1f}/50
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. الأرقام والأهداف
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("الهدف الأول", f"{tgts['tp1']:.4f}")
    col2.metric("الهدف الثاني", f"{tgts['tp2']:.4f}")
    col3.metric("وقف الخسارة", f"{tgts['sl']:.4f}", delta_color="inverse")
    col4.metric("العائد للمخاطرة", f"1:{tgts['rr']:.1f}")
    
    # 3. التبويبات التفصيلية
    tab1, tab2, tab3 = st.tabs(["📉 الشارت", "📝 تفاصيل التحليل", "🤖 رأي الذكاء الاصطناعي"])
    
    with tab1:
        # شارت TradingView
        tv_sym = to_tv_symbol(tkr)
        tv_int = TV_INTERVALS.get(st.session_state['tf'], "D")
        st.components.v1.html(f"""
        <div class="tradingview-widget-container" style="height:500px;width:100%">
          <div id="tradingview_chart"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget({{
            "width": "100%", "height": "500", "symbol": "{tv_sym}",
            "interval": "{tv_int}", "timezone": "Etc/UTC", "theme": "dark",
            "style": "1", "locale": "ar", "toolbar_bg": "#f1f3f6",
            "enable_publishing": false, "allow_symbol_change": true, "container_id": "tradingview_chart"
          }});
          </script>
        </div>
        """, height=500)
        
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("التحليل الفني")
            for d in st.session_state['td']:
                icon = "✅" if d[2] == "green" else "❌" if d[2] == "red" else "➖"
                st.markdown(f"{icon} **{d[0]}**")
        with c2:
            st.subheader("التحليل الأساسي")
            for d in st.session_state['fd']:
                icon = "✅" if d[2] == "green" else "❌" if d[2] == "red" else "➖"
                st.markdown(f"{icon} **{d[0]}**")
                
    with tab3:
        ai_res = st.session_state.get('ai_v')
        if ai_res:
            st.markdown(f"### القرار: {ai_res.get('decision')}")
            st.info(f"💡 السبب: {ai_res.get('reason')}")
            st.warning(f"⚠️ مستوى المخاطرة: {ai_res.get('risk')}")
        else:
            st.write("الذكاء الاصطناعي غير مفعل أو لم يتم ضبط المفتاح.")

    # 4. عرض سجل التحليلات من قاعدة البيانات
    st.divider()
    st.subheader("🗄️ سجل التحليلات (من قاعدة البيانات)")
    
    try:
        history_data = db.get_all_history()
        if history_data:
            # تحويل البيانات إلى DataFrame لتسهيل العرض
            # الجدول في db.py: id, timestamp, ticker, timeframe, signal, signal_class, strength, price, sl, tp1, tp2, tp3, rr, ai_decision, ai_risk
            cols = ['ID', 'Date', 'Ticker', 'TF', 'Signal', 'Class', 'Score', 'Price', 'SL', 'TP1', 'TP2', 'TP3', 'RR', 'AI_Dec', 'AI_Risk']
            hist_df = pd.DataFrame(history_data, columns=cols)
            
            # عرض البيانات باختصار
            st.dataframe(
                hist_df[['Date', 'Ticker', 'Signal', 'Price', 'TP1', 'SL', 'RR']], 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.caption("لا توجد تحليلات محفوظة في قاعدة البيانات بعد.")
    except Exception as e:
        st.error(f"حدث خطأ أثناء جلب البيانات: {e}")

else:
    # شاشة الترحيب عند عدم وجود تحليل
    st.markdown("""
    <div style="text-align:center; padding:50px; color:#888;">
        <h2>👋 مرحباً بك في ProTrade Elite</h2>
        <p>اختر الأصل من القائمة الجانبية واضغط "تحليل الآن" للبدء</p>
    </div>
    """, unsafe_allow_html=True)