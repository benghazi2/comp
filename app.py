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

# ============================================================
# 0. Local Storage Manager - ذاكرة المتصفح
# ============================================================

LOCAL_STORAGE_JS = """
<script>
// Local Storage Manager for Streamlit
const StorageManager = {
    prefix: 'protrade_',
    
    save: function(key, data) {
        try {
            localStorage.setItem(this.prefix + key, JSON.stringify(data));
            return true;
        } catch (e) {
            console.error('Storage save error:', e);
            return false;
        }
    },
    
    load: function(key) {
        try {
            const item = localStorage.getItem(this.prefix + key);
            return item ? JSON.parse(item) : null;
        } catch (e) {
            console.error('Storage load error:', e);
            return null;
        }
    },
    
    remove: function(key) {
        localStorage.removeItem(this.prefix + key);
    },
    
    clear: function() {
        Object.keys(localStorage).forEach(key => {
            if (key.startsWith(this.prefix)) {
                localStorage.removeItem(key);
            }
        });
    }
};

// Auto-save on page unload
window.addEventListener('beforeunload', function() {
    window.parent.postMessage({type: 'save_state'}, '*');
});

// Handle messages from Streamlit
window.addEventListener('message', function(e) {
    if (e.data.type === 'load_state_response') {
        // State loaded from Python
        console.log('State loaded from storage');
    }
});
</script>
"""

def init_local_storage():
    """تهيئة نظام التخزين المحلي"""
    st.components.v1.html(LOCAL_STORAGE_JS, height=0)

def save_to_browser(key, data):
    """حفظ البيانات في المتصفح"""
    try:
        serialized = base64.b64encode(json.dumps(data).encode()).decode()
        js_code = f"""
        <script>
        localStorage.setItem('protrade_{key}', '{serialized}');
        </script>
        """
        st.components.v1.html(js_code, height=0)
        return True
    except Exception as e:
        st.error(f"خطأ في الحفظ: {e}")
        return False

def load_from_browser(key):
    """تحميل البيانات من المتصفح"""
    try:
        js_code = f"""
        <script>
        const data = localStorage.getItem('protrade_{key}');
        const decoded = data ? atob(data) : null;
        window.parent.postMessage({{type: 'storage_data', key: '{key}', data: decoded}}, '*');
        </script>
        """
        st.components.v1.html(js_code, height=0)
        return None  # Will be handled via callback in future versions
    except:
        return None

# ============================================================
# 1. إعداد الصفحة - إصلاح مشكلة التمرير
# ============================================================
st.set_page_config(
    page_title="ProTrade Elite 5.0", 
    layout="wide", 
    page_icon="📈",
    initial_sidebar_state="expanded"
)

# CSS شامل لإصلاح التمرير وجميع المشاكل البصرية
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    * {font-family: 'Cairo', sans-serif !important;}
    
    /* إصلاح مشكلة التمرير الرئيسية */
    html, body {
        height: 100%;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        scroll-behavior: smooth;
    }
    
    .main {
        overflow: auto !important;
        height: 100vh;
    }
    
    .block-container {
        padding-top: 1rem; 
        padding-bottom: 2rem; 
        padding-left: 1rem; 
        padding-right: 1rem;
        max-width: 100%;
        overflow-x: hidden;
    }
    
    /* إخفاء شريط التمرير الأفقي */
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
    
    /* تثبيت الشريط الجانبي */
    [data-testid="stSidebar"] {
        position: fixed !important;
        height: 100vh;
        overflow-y: auto;
        overflow-x: hidden;
    }
    
    [data-testid="stSidebarContent"] {
        padding-bottom: 100px;
    }
    
    /* تحسين التمرير في التبويبات */
    .stTabs [data-baseweb="tab-panel"] {
        overflow-y: auto !important;
        max-height: calc(100vh - 200px);
    }
    
    /* تحسين البطاقات */
    .main-signal {
        padding: 20px; 
        border-radius: 15px; 
        text-align: center;
        font-size: 26px; 
        font-weight: bold; 
        color: white;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3); 
        margin: 8px 0;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    
    .bg-strong-buy {background: linear-gradient(135deg, #00b09b, #96c93d);}
    .bg-buy {background: linear-gradient(135deg, #11998e, #38ef7d);}
    .bg-strong-sell {background: linear-gradient(135deg, #cb2d3e, #ef473a);}
    .bg-sell {background: linear-gradient(135deg, #e53935, #ff6f60);}
    .bg-neutral {background: linear-gradient(135deg, #536976, #292E49);}
    
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 15px; 
        border-radius: 10px; 
        text-align: center;
        border: 1px solid #0f3460; 
        color: white; 
        margin: 5px 0;
        transition: transform 0.2s;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,255,136,0.2);
    }
    
    .metric-card h3 {
        color: #e94560; 
        margin: 0; 
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .metric-card h2 {
        color: #00ff88; 
        margin: 5px 0; 
        font-size: 18px;
        font-weight: bold;
    }
    
    .ai-box {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        color: #00ff88; 
        padding: 20px; 
        border-radius: 15px;
        border: 2px solid #00ff88; 
        margin: 10px 0;
        box-shadow: 0 0 20px rgba(0,255,136,0.1);
    }
    
    .rec-card {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border-radius: 12px; 
        padding: 15px; 
        margin: 10px 0;
        border-left: 5px solid; 
        color: white;
        transition: all 0.3s ease;
    }
    
    .rec-card:hover {
        transform: translateX(5px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    
    .rec-buy {border-color: #00ff88;}
    .rec-sell {border-color: #ff4444;}
    .rec-strong-buy {
        border-color: #00ff88; 
        box-shadow: 0 0 15px rgba(0,255,136,0.3);
        animation: pulse-green 2s infinite;
    }
    .rec-strong-sell {
        border-color: #ff4444; 
        box-shadow: 0 0 15px rgba(255,68,68,0.3);
        animation: pulse-red 2s infinite;
    }
    
    @keyframes pulse-green {
        0%, 100% { box-shadow: 0 0 15px rgba(0,255,136,0.3); }
        50% { box-shadow: 0 0 25px rgba(0,255,136,0.6); }
    }
    
    @keyframes pulse-red {
        0%, 100% { box-shadow: 0 0 15px rgba(255,68,68,0.3); }
        50% { box-shadow: 0 0 25px rgba(255,68,68,0.6); }
    }
    
    .target-hit {
        background: linear-gradient(135deg, #00b09b, #96c93d); 
        padding: 8px; 
        border-radius: 6px; 
        text-align: center; 
        color: white; 
        font-weight: bold; 
        margin: 5px 0;
    }
    
    .target-miss {
        background: linear-gradient(135deg, #cb2d3e, #ef473a); 
        padding: 8px; 
        border-radius: 6px; 
        text-align: center; 
        color: white; 
        font-weight: bold; 
        margin: 5px 0;
    }
    
    .target-progress {
        background: #16213e; 
        padding: 8px; 
        border-radius: 6px; 
        text-align: center; 
        color: #ffeb3b; 
        font-weight: bold; 
        margin: 5px 0;
        border: 1px solid #333;
    }
    
    /* تحسين TradingView */
    .tradingview-widget-container {
        height: 75vh !important;
        min-height: 500px;
    }
    
    .tradingview-widget-container__widget {
        height: 100% !important;
    }
    
    /* تحسين الأزرار */
    .stButton>button {
        transition: all 0.3s !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    
    /* تحسين حقول الإدخال */
    .stTextInput>div>div>input,
    .stSelectbox>div>div>select {
        background-color: #1a1a2e !important;
        color: white !important;
        border: 1px solid #0f3460 !important;
    }
    
    /* تحسين التبويبات */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1a2e;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 600;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #0f3460 !important;
        color: #00ff88 !important;
    }
    
    /* تحسين شريط التقدم */
    .stProgress > div > div {
        background-color: #00ff88 !important;
    }
    
    /* Toast notifications */
    .toast {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: #1a1a2e;
        color: white;
        padding: 15px 20px;
        border-radius: 10px;
        border-left: 4px solid #00ff88;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 9999;
        animation: slideIn 0.3s ease;
    }
    
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    /* تحسين للجوال */
    @media (max-width: 768px) {
        .main-signal {
            font-size: 18px;
            padding: 15px;
        }
        
        .metric-card h2 {
            font-size: 14px;
        }
        
        .tradingview-widget-container {
            height: 50vh !important;
        }
    }
    
    /* إخفاء العناصر غير الضرورية */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* تحسين التحميل */
    .loading-spinner {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 200px;
    }
    
    .spinner {
        width: 50px;
        height: 50px;
        border: 3px solid #0f3460;
        border-top: 3px solid #00ff88;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
</style>
""", unsafe_allow_html=True)

# تهيئة Local Storage
init_local_storage()

# ============================================================
# 2. Session State مع دعم Local Storage
# ============================================================

def init_session_state():
    """تهيئة حالة الجلسة مع التحميل من التخزين المحلي"""
    
    defaults = {
        'messages': [],
        'analysis_history': [],
        'strong_signals': [],
        'saved_signals': [],  # للتوصيات المحفوظة
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
        'auto_refresh': False,
        'dark_mode': True,
        'notifications': True,
    }
    
    # تحميل من التخزين المحلي إذا وجد
    for key, default_value in defaults.items():
        if key not in st.session_state:
            # محاولة التحميل من local storage (سيتم تنفيذها عبر JavaScript)
            st.session_state[key] = default_value
    
    # حفظ تلقائي عند التغيير
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True

init_session_state()

# ============================================================
# 3. دوال حفظ وتحميل البيانات
# ============================================================

def export_data():
    """تصدير جميع البيانات"""
    data = {
        'analysis_history': st.session_state.analysis_history,
        'strong_signals': st.session_state.strong_signals,
        'saved_signals': st.session_state.saved_signals,
        'messages': st.session_state.messages,
        'timestamp': datetime.now().isoformat()
    }
    return base64.b64encode(json.dumps(data).encode()).decode()

def import_data(encoded_data):
    """استيراد البيانات"""
    try:
        data = json.loads(base64.b64decode(encoded_data).decode())
        st.session_state.analysis_history = data.get('analysis_history', [])
        st.session_state.strong_signals = data.get('strong_signals', [])
        st.session_state.saved_signals = data.get('saved_signals', [])
        st.session_state.messages = data.get('messages', [])
        return True
    except Exception as e:
        st.error(f"خطأ في الاستيراد: {e}")
        return False

def save_current_analysis():
    """حفظ التحليل الحالي"""
    if st.session_state.get('ok'):
        analysis = {
            'ticker': st.session_state['ticker'],
            'tf': st.session_state['tf'],
            'sig': st.session_state['sig'],
            'comb': st.session_state['comb'],
            'price': safe_val(st.session_state['curr']['Close']),
            'time': datetime.now().isoformat()
        }
        if analysis not in st.session_state.saved_signals:
            st.session_state.saved_signals.insert(0, analysis)
            st.session_state.saved_signals = st.session_state.saved_signals[:20]
            return True
    return False

# ============================================================
# 4. الأصول
# ============================================================
FOREX_PAIRS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X", "USD/CHF": "USDCHF=X",
    "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X", "EUR/GBP": "EURGBP=X",
    "EUR/JPY": "EURJPY=X", "GBP/JPY": "GBPJPY=X",
    "EUR/CHF": "EURCHF=X", "AUD/JPY": "AUDJPY=X",
    "CAD/JPY": "CADJPY=X", "EUR/AUD": "EURAUD=X",
    "GBP/AUD": "GBPAUD=X",
}
CRYPTO_PAIRS = {
    "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD",
    "SOL/USD": "SOL-USD", "XRP/USD": "XRP-USD",
    "LINK/USD": "LINK-USD", "BNB/USD": "BNB-USD",
    "DOGE/USD": "DOGE-USD", "ADA/USD": "ADA-USD",
    "AVAX/USD": "AVAX-USD", "MATIC/USD": "MATIC-USD",
}
STOCKS = {
    "Apple": "AAPL", "Microsoft": "MSFT",
    "Google": "GOOGL", "Amazon": "AMZN",
    "Tesla": "TSLA", "Meta": "META",
    "NVIDIA": "NVDA", "JPMorgan": "JPM",
    "ExxonMobil": "XOM", "J&J": "JNJ",
}
INDICES_COMMODITIES = {
    "S&P 500": "^GSPC", "Nasdaq": "^IXIC",
    "Dow Jones": "^DJI", "Gold": "GC=F",
    "Silver": "SI=F", "Oil": "CL=F", "Gas": "NG=F",
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
    "شهري": {"interval": "1mo", "period": "5y"},
}
TV_INTERVALS = {
    "1 دقيقة": "1", "5 دقائق": "5", "15 دقيقة": "15",
    "30 دقيقة": "30", "1 ساعة": "60", "4 ساعات": "240",
    "يومي": "D", "أسبوعي": "W", "شهري": "M",
}


def to_tv_symbol(ticker):
    ticker = ticker.upper()
    if ticker.endswith("=X"): return f"FX:{ticker.replace('=X', '')}"
    if ticker.endswith("-USD"): return f"CRYPTO:{ticker.replace('-USD', '')}USD"
    idx = {"^GSPC": "SP:SPX", "^IXIC": "NASDAQ:IXIC", "^DJI": "DJ:DJI"}
    if ticker in idx: return idx[ticker]
    cmd = {"GC=F": "COMEX:GC1!", "SI=F": "COMEX:SI1!", "CL=F": "NYMEX:CL1!", "NG=F": "NYMEX:NG1!"}
    if ticker in cmd: return cmd[ticker]
    return f"NASDAQ:{ticker}"


# ============================================================
# 5. AI
# ============================================================
repo_id = "Qwen/Qwen2.5-72B-Instruct"
try:
    client = InferenceClient(model=repo_id, token=st.secrets.get("HF_TOKEN", "")) if "HF_TOKEN" in st.secrets else None
except: 
    client = None


# ============================================================
# 6. دوال التحليل
# ============================================================

def safe_val(value, default=0.0):
    if value is None: 
        return default
    try:
        v = float(value)
        return default if (np.isnan(v) or np.isinf(v)) else v
    except: 
        return default


def get_current_price(ticker):
    """جلب السعر الحالي فقط - سريع"""
    try:
        stock = yf.Ticker(ticker)
        try:
            p = stock.fast_info.get('lastPrice', None)
            if p and p > 0: 
                return float(p)
        except: 
            pass
        
        try:
            info = stock.info
            p = info.get('regularMarketPrice') or info.get('currentPrice')
            if p and float(p) > 0: 
                return float(p)
        except: 
            pass
        
        hist = stock.history(period="1d")
        if hist is not None and not hist.empty:
            return float(hist['Close'].iloc[-1])
    except: 
        pass
    return None


def fetch_data(ticker, tf_key, max_retries=3):
    ticker = ticker.strip().upper()
    tf = TIMEFRAMES[tf_key]
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            if tf_key == "4 ساعات":
                df = stock.history(period="3mo", interval="1h")
                if df is not None and not df.empty:
                    if df.index.tz is not None: 
                        df.index = df.index.tz_localize(None)
                    df = df.resample('4h').agg({
                        'Open': 'first', 'High': 'max', 'Low': 'min',
                        'Close': 'last', 'Volume': 'sum'
                    }).dropna()
            else:
                df = stock.history(period=tf["period"], interval=tf["interval"], auto_adjust=True)
            
            if df is not None and not df.empty and len(df) > 10:
                if df.index.tz is not None: 
                    df.index = df.index.tz_localize(None)
                if isinstance(df.columns, pd.MultiIndex): 
                    df.columns = df.columns.get_level_values(0)
                try: 
                    info = stock.info
                except: 
                    info = {}
                return df, info
            
            if attempt < max_retries - 1: 
                time.sleep((attempt + 1) * 3)
        except:
            if attempt < max_retries - 1: 
                time.sleep((attempt + 1) * 4)
            else: 
                return None, None
    return None, None


def calculate_indicators(df):
    n = len(df)
    c, h, l = df['Close'], df['High'], df['Low']
    v = df['Volume'] if 'Volume' in df.columns else pd.Series(0, index=df.index)
    has_vol = v.sum() > 0

    for w in [10, 20, 50]:
        if n > w:
            df[f'SMA_{w}'] = ta.trend.sma_indicator(c, window=w)
            df[f'EMA_{w}'] = ta.trend.ema_indicator(c, window=w)
        else: 
            df[f'SMA_{w}'] = df[f'EMA_{w}'] = np.nan
    
    df['EMA_200'] = ta.trend.ema_indicator(c, window=200) if n >= 200 else np.nan

    try:
        macd = ta.trend.MACD(c, window_slow=26, window_fast=12, window_sign=9)
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff()
    except: 
        df['MACD'] = df['MACD_Signal'] = df['MACD_Hist'] = np.nan

    if n > 28:
        try:
            adx = ta.trend.ADXIndicator(h, l, c, window=14)
            df['ADX'] = adx.adx()
            df['DI_plus'] = adx.adx_pos()
            df['DI_minus'] = adx.adx_neg()
        except: 
            df['ADX'] = df['DI_plus'] = df['DI_minus'] = np.nan
    else: 
        df['ADX'] = df['DI_plus'] = df['DI_minus'] = np.nan

    if n > 52:
        try:
            ich = ta.trend.IchimokuIndicator(h, l)
            df['Ich_A'] = ich.ichimoku_a()
            df['Ich_B'] = ich.ichimoku_b()
        except: 
            df['Ich_A'] = df['Ich_B'] = np.nan
    else: 
        df['Ich_A'] = df['Ich_B'] = np.nan

    if n > 14:
        try:
            psar = ta.trend.PSARIndicator(h, l, c)
            df['PSAR'] = psar.psar()
        except: 
            df['PSAR'] = np.nan
    else: 
        df['PSAR'] = np.nan

    try: 
        df['RSI'] = ta.momentum.rsi(c, window=14)
    except: 
        df['RSI'] = np.nan

    try:
        stoch = ta.momentum.StochasticOscillator(h, l, c, window=14, smooth_window=3)
        df['Stoch_K'] = stoch.stoch()
        df['Stoch_D'] = stoch.stoch_signal()
    except: 
        df['Stoch_K'] = df['Stoch_D'] = np.nan

    try: 
        df['Williams_R'] = ta.momentum.williams_r(h, l, c, lbp=14) if n > 14 else np.nan
    except: 
        df['Williams_R'] = np.nan
    
    try: 
        df['CCI'] = ta.trend.cci(h, l, c, window=20) if n > 20 else np.nan
    except: 
        df['CCI'] = np.nan
    
    try: 
        df['ROC'] = ta.momentum.roc(c, window=12) if n > 12 else np.nan
    except: 
        df['ROC'] = np.nan
    
    if n > 34:
        try: 
            df['AO'] = ta.momentum.awesome_oscillator(h, l, window1=5, window2=34)
        except: 
            df['AO'] = np.nan
    else: 
        df['AO'] = np.nan

    try: 
        df['ATR'] = ta.volatility.average_true_range(h, l, c, window=14)
    except: 
        df['ATR'] = np.nan
    
    try:
        bb = ta.volatility.BollingerBands(c, window=20, window_dev=2)
        df['BB_Upper'] = bb.bollinger_hband()
        df['BB_Lower'] = bb.bollinger_lband()
        df['BB_Pct'] = bb.bollinger_pband()
        df['BB_Width'] = bb.bollinger_wband()
    except: 
        df['BB_Upper'] = df['BB_Lower'] = df['BB_Pct'] = df['BB_Width'] = np.nan

    if n > 20:
        try:
            kc = ta.volatility.KeltnerChannel(h, l, c, window=20)
            df['KC_Upper'] = kc.keltner_channel_hband()
            df['KC_Lower'] = kc.keltner_channel_lband()
        except: 
            df['KC_Upper'] = df['KC_Lower'] = np.nan
    else: 
        df['KC_Upper'] = df['KC_Lower'] = np.nan

    if has_vol:
        try: 
            df['OBV'] = ta.volume.on_balance_volume(c, v)
        except: 
            df['OBV'] = np.nan
        try: 
            df['MFI'] = ta.volume.money_flow_index(h, l, c, v, window=14) if n > 14 else np.nan
        except: 
            df['MFI'] = np.nan
        try: 
            df['CMF'] = ta.volume.chaikin_money_flow(h, l, c, v, window=20) if n > 20 else np.nan
        except: 
            df['CMF'] = np.nan
    else: 
        df['OBV'] = df['MFI'] = df['CMF'] = np.nan

    df['Pivot'] = (h.shift(1) + l.shift(1) + c.shift(1)) / 3
    df['R1'] = 2 * df['Pivot'] - l.shift(1)
    df['S1'] = 2 * df['Pivot'] - h.shift(1)
    df['R2'] = df['Pivot'] + (h.shift(1) - l.shift(1))
    df['S2'] = df['Pivot'] - (h.shift(1) - l.shift(1))

    df['Doji'] = abs(c - df['Open']) <= (h - l) * 0.1
    df['Hammer'] = ((h - l) > 3 * abs(c - df['Open'])) & ((c - l) / (h - l + 0.0001) > 0.6)
    df['Engulfing_Bull'] = (df['Open'].shift(1) > c.shift(1)) & (c > df['Open']) & (c > df['Open'].shift(1)) & (df['Open'] < c.shift(1))
    df['Engulfing_Bear'] = (c.shift(1) > df['Open'].shift(1)) & (df['Open'] > c) & (df['Open'] > c.shift(1)) & (c < df['Open'].shift(1))

    return df


# ============================================================
# 7. التسجيل والتحليل
# ============================================================

def smart_technical_score(df):
    curr = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else curr
    price = safe_val(curr['Close'])
    score = 0
    details = []
    signals = {"buy": 0, "sell": 0, "neutral": 0}

    ema50 = safe_val(curr.get('EMA_50'))
    ema200 = safe_val(curr.get('EMA_200'))
    ema20 = safe_val(curr.get('EMA_20'))
    ema10 = safe_val(curr.get('EMA_10'))

    if ema200 > 0:
        if price > ema200: 
            score += 8
            signals["buy"] += 1
            details.append(("فوق EMA 200", "+8", "green"))
        else: 
            score -= 8
            signals["sell"] += 1
            details.append(("تحت EMA 200", "-8", "red"))

    if ema50 > 0 and ema200 > 0:
        pe50 = safe_val(prev.get('EMA_50'))
        pe200 = safe_val(prev.get('EMA_200'))
        if ema50 > ema200:
            score += 5
            signals["buy"] += 1
            details.append(("EMA 50 > 200", "+5", "green"))
            if pe50 > 0 and pe200 > 0 and pe50 <= pe200:
                score += 10
                signals["buy"] += 1
                details.append(("تقاطع ذهبي!", "+10", "green"))
        else:
            score -= 5
            signals["sell"] += 1
            details.append(("EMA 50 < 200", "-5", "red"))
            if pe50 > 0 and pe200 > 0 and pe50 >= pe200:
                score -= 10
                signals["sell"] += 1
                details.append(("تقاطع الموت!", "-10", "red"))
    elif ema50 > 0:
        if price > ema50: 
            score += 4
            signals["buy"] += 1
            details.append(("فوق EMA 50", "+4", "green"))
        else: 
            score -= 4
            signals["sell"] += 1
            details.append(("تحت EMA 50", "-4", "red"))

    if ema10 > 0 and ema20 > 0 and ema50 > 0:
        if ema10 > ema20 > ema50: 
            score += 5
            signals["buy"] += 1
            details.append(("ترتيب مثالي صعودي", "+5", "green"))
        elif ema10 < ema20 < ema50: 
            score -= 5
            signals["sell"] += 1
            details.append(("ترتيب مثالي هبوطي", "-5", "red"))

    adx = safe_val(curr.get('ADX'))
    dip = safe_val(curr.get('DI_plus'))
    dim = safe_val(curr.get('DI_minus'))
    
    if adx > 0:
        if adx > 25:
            if dip > dim: 
                score += 5
                signals["buy"] += 1
                details.append((f"صاعد ADX={adx:.0f}", "+5", "green"))
            else: 
                score -= 5
                signals["sell"] += 1
                details.append((f"هابط ADX={adx:.0f}", "-5", "red"))
        elif adx < 20: 
            signals["neutral"] += 1
            details.append((f"بلا اتجاه ADX={adx:.0f}", "0", "gray"))

    psar = safe_val(curr.get('PSAR'))
    if psar > 0:
        if price > psar: 
            score += 3
            signals["buy"] += 1
            details.append(("PSAR صاعد", "+3", "green"))
        else: 
            score -= 3
            signals["sell"] += 1
            details.append(("PSAR هابط", "-3", "red"))

    rsi = safe_val(curr.get('RSI'))
    if rsi > 0:
        if rsi < 30: 
            score += 8
            signals["buy"] += 1
            details.append((f"RSI تشبع بيعي ({rsi:.1f})", "+8", "green"))
        elif rsi < 40: 
            score += 3
            signals["buy"] += 1
            details.append((f"RSI منخفض ({rsi:.1f})", "+3", "green"))
        elif rsi > 70: 
            score -= 8
            signals["sell"] += 1
            details.append((f"RSI تشبع شرائي ({rsi:.1f})", "-8", "red"))
        elif rsi > 60: 
            score -= 2
            signals["sell"] += 1
            details.append((f"RSI مرتفع ({rsi:.1f})", "-2", "red"))
        else: 
            score += 1
            details.append((f"RSI متوازن ({rsi:.1f})", "+1", "green"))

        if len(df) > 14:
            p14 = safe_val(df['Close'].iloc[-14])
            r14 = safe_val(df['RSI'].iloc[-14])
            if p14 > 0 and r14 > 0:
                if price < p14 and rsi > r14: 
                    score += 6
                    signals["buy"] += 1
                    details.append(("انحراف RSI صعودي", "+6", "green"))
                if price > p14 and rsi < r14: 
                    score -= 6
                    signals["sell"] += 1
                    details.append(("انحراف RSI هبوطي", "-6", "red"))

    macd_v = safe_val(curr.get('MACD'))
    macd_s = safe_val(curr.get('MACD_Signal'))
    macd_h = safe_val(curr.get('MACD_Hist'))
    prev_mh = safe_val(prev.get('MACD_Hist'))
    
    if macd_v > macd_s: 
        score += 5
        signals["buy"] += 1
        details.append(("MACD إيجابي", "+5", "green"))
    elif macd_v != 0 or macd_s != 0: 
        score -= 5
        signals["sell"] += 1
        details.append(("MACD سلبي", "-5", "red"))
    
    if macd_h > 0 and prev_mh <= 0: 
        score += 5
        signals["buy"] += 1
        details.append(("MACD تقاطع صعودي", "+5", "green"))
    elif macd_h < 0 and prev_mh >= 0: 
        score -= 5
        signals["sell"] += 1
        details.append(("MACD تقاطع هبوطي", "-5", "red"))

    stk = safe_val(curr.get('Stoch_K'))
    std = safe_val(curr.get('Stoch_D'))
    
    if stk > 0:
        if stk < 20:
            s = 6 if stk > std else 3
            score += s
            signals["buy"] += 1
            details.append((f"Stoch بيعي ({stk:.0f})", f"+{s}", "green"))
        elif stk > 80:
            s = 6 if stk < std else 3
            score -= s
            signals["sell"] += 1
            details.append((f"Stoch شرائي ({stk:.0f})", f"-{s}", "red"))

    wr = safe_val(curr.get('Williams_R'))
    if wr != 0:
        if wr < -80: 
            score += 3
            signals["buy"] += 1
            details.append(("Williams بيعي", "+3", "green"))
        elif wr > -20: 
            score -= 3
            signals["sell"] += 1
            details.append(("Williams شرائي", "-3", "red"))

    cci = safe_val(curr.get('CCI'))
    if cci != 0:
        if cci < -100: 
            score += 4
            signals["buy"] += 1
            details.append((f"CCI بيعي ({cci:.0f})", "+4", "green"))
        elif cci > 100: 
            score -= 4
            signals["sell"] += 1
            details.append((f"CCI شرائي ({cci:.0f})", "-4", "red"))

    ao = safe_val(curr.get('AO'))
    pao = safe_val(prev.get('AO'))
    
    if ao != 0:
        if ao > 0 and pao <= 0: 
            score += 3
            signals["buy"] += 1
            details.append(("AO إيجابي", "+3", "green"))
        elif ao < 0 and pao >= 0: 
            score -= 3
            signals["sell"] += 1
            details.append(("AO سلبي", "-3", "red"))

    bb_l = safe_val(curr.get('BB_Lower'))
    bb_u = safe_val(curr.get('BB_Upper'))
    
    if bb_l > 0 and bb_u > 0:
        if price <= bb_l: 
            score += 6
            signals["buy"] += 1
            details.append(("بولنجر السفلي", "+6", "green"))
        elif price >= bb_u: 
            score -= 6
            signals["sell"] += 1
            details.append(("بولنجر العلوي", "-6", "red"))

    kc_u = safe_val(curr.get('KC_Upper'))
    kc_l = safe_val(curr.get('KC_Lower'))
    
    if kc_l > 0 and kc_u > 0:
        if price < kc_l: 
            score += 3
            signals["buy"] += 1
            details.append(("تحت Keltner", "+3", "green"))
        elif price > kc_u: 
            score -= 3
            signals["sell"] += 1
            details.append(("فوق Keltner", "-3", "red"))

    mfi = safe_val(curr.get('MFI'))
    if mfi > 0:
        if mfi < 20: 
            score += 5
            signals["buy"] += 1
            details.append((f"MFI بيعي ({mfi:.0f})", "+5", "green"))
        elif mfi > 80: 
            score -= 5
            signals["sell"] += 1
            details.append((f"MFI شرائي ({mfi:.0f})", "-5", "red"))

    cmf = safe_val(curr.get('CMF'))
    if cmf != 0:
        if cmf > 0.05: 
            score += 4
            signals["buy"] += 1
            details.append(("تدفق أموال +", "+4", "green"))
        elif cmf < -0.05: 
            score -= 4
            signals["sell"] += 1
            details.append(("تدفق أموال -", "-4", "red"))

    if 'OBV' in df.columns:
        obv_s = df['OBV'].dropna()
        if len(obv_s) > 10:
            obv_sma = obv_s.rolling(10).mean().iloc[-1]
            if not np.isnan(obv_sma):
                if obv_s.iloc[-1] > obv_sma: 
                    score += 3
                    signals["buy"] += 1
                    details.append(("OBV صاعد", "+3", "green"))
                else: 
                    score -= 3
                    signals["sell"] += 1
                    details.append(("OBV هابط", "-3", "red"))

    ich_a = safe_val(curr.get('Ich_A'))
    ich_b = safe_val(curr.get('Ich_B'))
    
    if ich_a > 0 and ich_b > 0:
        if price > max(ich_a, ich_b): 
            score += 5
            signals["buy"] += 1
            details.append(("فوق إيشيموكو", "+5", "green"))
        elif price < min(ich_a, ich_b): 
            score -= 5
            signals["sell"] += 1
            details.append(("تحت إيشيموكو", "-5", "red"))
        else: 
            signals["neutral"] += 1
            details.append(("داخل السحابة", "0", "gray"))

    pivot = safe_val(curr.get('Pivot'))
    r1 = safe_val(curr.get('R1'))
    s1 = safe_val(curr.get('S1'))
    
    if pivot > 0:
        if price > r1: 
            score += 4
            signals["buy"] += 1
            details.append(("فوق R1", "+4", "green"))
        elif price < s1: 
            score -= 4
            signals["sell"] += 1
            details.append(("تحت S1", "-4", "red"))
        elif price > pivot: 
            score += 2
            details.append(("فوق Pivot", "+2", "green"))
        elif price < pivot: 
            score -= 2
            details.append(("تحت Pivot", "-2", "red"))

    if curr.get('Engulfing_Bull', False): 
        score += 4
        signals["buy"] += 1
        details.append(("ابتلاع صعودي", "+4", "green"))
    
    if curr.get('Engulfing_Bear', False): 
        score -= 4
        signals["sell"] += 1
        details.append(("ابتلاع هبوطي", "-4", "red"))
    
    if curr.get('Hammer', False) and rsi < 40: 
        score += 3
        signals["buy"] += 1
        details.append(("مطرقة", "+3", "green"))
    
    if curr.get('Doji', False): 
        signals["neutral"] += 1
        details.append(("Doji", "0", "gray"))

    total = signals["buy"] + signals["sell"] + signals["neutral"]
    consensus = abs(signals["buy"] - signals["sell"]) / max(total, 1)
    
    return score, details, curr, signals, consensus


def fundamental_score(info):
    score = 0
    details = []
    
    if not info: 
        return 0, [("لا بيانات أساسية", "0", "gray")]

    pe = info.get('trailingPE') or info.get('forwardPE')
    if pe:
        try:
            v = float(pe)
            if 0 < v < 15: 
                score += 10
                details.append((f"P/E ({v:.1f})", "+10", "green"))
            elif v <= 25: 
                score += 5
                details.append((f"P/E ({v:.1f})", "+5", "green"))
            elif v > 25: 
                score -= 5
                details.append((f"P/E ({v:.1f})", "-5", "red"))
            elif v < 0: 
                score -= 8
                details.append((f"P/E سلبي", "-8", "red"))
        except: 
            pass

    margin = info.get('profitMargins')
    if margin:
        try:
            m = float(margin) * 100
            if m > 20: 
                score += 8
                details.append((f"هامش ({m:.1f}%)", "+8", "green"))
            elif m > 10: 
                score += 4
                details.append((f"هامش ({m:.1f}%)", "+4", "green"))
            elif m < 0: 
                score -= 8
                details.append((f"خسارة ({m:.1f}%)", "-8", "red"))
        except: 
            pass

    roe = info.get('returnOnEquity')
    if roe:
        try:
            r = float(roe) * 100
            if r > 20: 
                score += 7
                details.append((f"ROE ({r:.1f}%)", "+7", "green"))
            elif r > 10: 
                score += 3
                details.append((f"ROE ({r:.1f}%)", "+3", "green"))
            elif r < 0: 
                score -= 5
                details.append((f"ROE سلبي", "-5", "red"))
        except: 
            pass

    de = info.get('debtToEquity')
    if de:
        try:
            d = float(de)
            if d < 50: 
                score += 8
                details.append((f"ديون ({d:.0f}%)", "+8", "green"))
            elif d < 100: 
                score += 3
                details.append((f"ديون ({d:.0f}%)", "+3", "green"))
            elif d > 200: 
                score -= 8
                details.append((f"ديون خطيرة ({d:.0f}%)", "-8", "red"))
        except: 
            pass

    fcf = info.get('freeCashflow')
    if fcf:
        try:
            if float(fcf) > 0: 
                score += 6
                details.append(("FCF +", "+6", "green"))
            else: 
                score -= 6
                details.append(("FCF -", "-6", "red"))
        except: 
            pass

    rg = info.get('revenueGrowth')
    if rg:
        try:
            r = float(rg) * 100
            if r > 15: 
                score += 7
                details.append((f"نمو ({r:.1f}%)", "+7", "green"))
            elif r > 0: 
                score += 3
                details.append((f"نمو ({r:.1f}%)", "+3", "green"))
            else: 
                score -= 5
                details.append((f"تراجع ({r:.1f}%)", "-5", "red"))
        except: 
            pass

    rec = info.get('recommendationKey', '')
    if rec:
        r = rec.lower()
        if 'strong_buy' in r: 
            score += 5
            details.append(("شراء قوي", "+5", "green"))
        elif 'buy' in r: 
            score += 3
            details.append(("شراء", "+3", "green"))
        elif 'sell' in r: 
            score -= 5
            details.append(("بيع", "-5", "red"))

    if not details: 
        details.append(("غير متاح", "0", "gray"))
    
    return score, details


def calc_targets(curr, t_score):
    price = safe_val(curr['Close'])
    atr = safe_val(curr.get('ATR'))
    
    if atr == 0: 
        atr = (safe_val(curr['High']) - safe_val(curr['Low'])) * 0.7
    if atr == 0: 
        atr = price * 0.02
    
    bull = t_score > 0
    sl = price - 2*atr if bull else price + 2*atr
    tp1 = price + 1.5*atr if bull else price - 1.5*atr
    tp2 = price + 3*atr if bull else price - 3*atr
    tp3 = price + 5*atr if bull else price - 5*atr
    rr = abs(tp2-price)/abs(price-sl) if abs(price-sl) > 0 else 0
    
    return {'sl':sl, 'tp1':tp1, 'tp2':tp2, 'tp3':tp3, 'atr':atr, 'rr':rr}


def final_signal(t_score, f_score, ai_v):
    t_n = (t_score/50)*100
    f_n = (f_score/50)*100 if f_score != 0 else 0
    ai_s = 0
    
    if ai_v:
        dec = ai_v.get('final_decision','محايد')
        conf = ai_v.get('confidence',50)
        if 'شراء قوي' in dec: 
            ai_s = conf
        elif 'شراء' in dec: 
            ai_s = conf*0.6
        elif 'بيع قوي' in dec: 
            ai_s = -conf
        elif 'بيع' in dec: 
            ai_s = -conf*0.6
    
    combined = t_n*0.4 + f_n*0.3 + ai_s*0.3
    
    if combined >= 40: 
        return "شراء قوي", "bg-strong-buy", combined
    elif combined >= 15: 
        return "شراء", "bg-buy", combined
    elif combined <= -40: 
        return "بيع قوي", "bg-strong-sell", combined
    elif combined <= -15: 
        return "بيع", "bg-sell", combined
    
    return "محايد", "bg-neutral", combined


def get_ai_verdict(client, ticker, ts, fs, td, fd, curr, info):
    if not client: 
        return None
    
    tt = "\n".join([f"- {d[0]} ({d[1]})" for d in td[:15]])
    ft = "\n".join([f"- {d[0]} ({d[1]})" for d in fd[:12]])
    
    prompt = f"""محلل مالي خبير. حلل:
الأصل: {ticker} | السعر: {safe_val(curr.get('Close')):.5f} | القطاع: {info.get('sector','N/A')}
== فني ({ts:+.0f}) ==
{tt}
== أساسي ({fs:+.0f}) ==
{ft}
JSON فقط:
{{"final_decision":"شراء قوي/شراء/محايد/بيع/بيع قوي","confidence":0-100,"reasoning":"تحليل بالعربية","risk_level":"منخفض/متوسط/مرتفع","time_horizon":"قصير/متوسط/طويل","key_factors":["1","2","3"]}}"""
    
    try:
        resp = client.chat_completion(
            messages=[
                {"role":"system","content":"محلل مالي. JSON فقط."},
                {"role":"user","content":prompt}
            ],
            max_tokens=600, 
            temperature=0.2
        )
        txt = resp.choices[0].message.content.strip()
        
        if "```" in txt: 
            txt = txt.split("```json")[-1].split("```")[0] if "```json" in txt else txt.split("```")[1].split("```")[0]
        
        s, e = txt.find('{'), txt.rfind('}')+1
        return json.loads(txt[s:e]) if s>=0 and e>s else None
    except: 
        return None


# ============================================================
# 8. TradingView
# ============================================================

def render_tv_chart(tv_symbol, interval="D"):
    """شارت TradingView محسّن"""
    chart_key = f"tv_chart_{tv_symbol}_{interval}_{int(time.time())}"
    
    chart_html = f"""
    <div style="border-radius:12px;overflow:hidden;border:2px solid #0f3460;width:100%;height:75vh;min-height:500px;background:#0a0a1a;">
        <div class="tradingview-widget-container" style="width:100%;height:100%;">
            <div class="tradingview-widget-container__widget" style="width:100%;height:100%;"></div>
            <script type="text/javascript"
                src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
            {{
                "autosize": true,
                "symbol": "{tv_symbol}",
                "interval": "{interval}",
                "timezone": "Etc/UTC",
                "theme": "dark",
                "style": "1",
                "locale": "ar",
                "enable_publishing": false,
                "backgroundColor": "rgba(10, 10, 26, 1)",
                "gridColor": "rgba(42, 46, 57, 0.5)",
                "hide_top_toolbar": false,
                "hide_legend": false,
                "allow_symbol_change": true,
                "save_image": true,
                "calendar": false,
                "hide_volume": false,
                "support_host": "https://www.tradingview.com",
                "studies": ["STD;Bollinger_Bands","STD;RSI","STD;MACD","STD;Volume"],
                "show_popup_button": true,
                "popup_width": "1200",
                "popup_height": "800",
                "withdateranges": true,
                "details": true,
                "hotlist": true
            }}
            </script>
        </div>
    </div>
    """
    st.components.v1.html(chart_html, height=800, scrolling=False)


def render_tv_tape():
    tape_html = """
    <div class="tradingview-widget-container" style="margin:0;padding:0;width:100%;height:80px;">
        <div class="tradingview-widget-container__widget"></div>
        <script type="text/javascript"
            src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
        {"symbols":[
            {"description":"EUR/USD","proName":"FX:EURUSD"},
            {"description":"GBP/USD","proName":"FX:GBPUSD"},
            {"description":"USD/JPY","proName":"FX:USDJPY"},
            {"description":"BTC","proName":"CRYPTO:BTCUSD"},
            {"description":"ETH","proName":"CRYPTO:ETHUSD"},
            {"description":"Gold","proName":"COMEX:GC1!"},
            {"description":"S&P500","proName":"SP:SPX"},
            {"description":"AAPL","proName":"NASDAQ:AAPL"}
        ],"showSymbolLogo":true,"colorTheme":"dark","isTransparent":true,"displayMode":"adaptive","locale":"ar"}
        </script>
    </div>
    """
    st.components.v1.html(tape_html, height=80)


# ============================================================
# 9. المسح والتحديث
# ============================================================

def background_scan(tf_key="يومي"):
    """مسح شامل مع تحديث فوري"""
    strong_signals = []
    all_assets = {}
    all_assets.update(FOREX_PAIRS)
    all_assets.update(CRYPTO_PAIRS)
    all_assets.update(STOCKS)

    total = len(all_assets)
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, (name, ticker) in enumerate(all_assets.items()):
        progress = (i + 1) / total
        progress_bar.progress(progress)
        status_text.text(f"جاري تحليل {name}... ({i+1}/{total})")

        try:
            df, info = fetch_data(ticker, tf_key, max_retries=1)
            if df is None or len(df) < 15: 
                continue

            df = calculate_indicators(df)
            ts, td, curr, sigs, cons = smart_technical_score(df)
            fs, fd = fundamental_score(info)
            sig, sig_cls, comb = final_signal(ts, fs, None)
            price = safe_val(curr['Close'])
            tgts = calc_targets(curr, ts)

            if abs(comb) >= 8:
                strong_signals.append({
                    'name': name,
                    'ticker': ticker,
                    'signal': sig,
                    'signal_class': sig_cls,
                    'combined_score': comb,
                    'tech_score': ts,
                    'fund_score': fs,
                    'price': price,
                    'entry_price': price,
                    'current_price': price,
                    'sl': tgts['sl'],
                    'tp1': tgts['tp1'],
                    'tp2': tgts['tp2'],
                    'tp3': tgts['tp3'],
                    'rr': tgts['rr'],
                    'consensus': cons,
                    'buy_signals': sigs['buy'],
                    'sell_signals': sigs['sell'],
                    'rsi': safe_val(curr.get('RSI')),
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'timeframe': tf_key,
                    'reasons': [d[0] for d in td[:5]],
                    'direction': 'buy' if comb > 0 else 'sell',
                    'status': 'active',
                    'progress': 0.0,
                    'tp1_hit': False,
                    'pnl_pct': 0.0,
                    'pnl_pips': 0.0,
                })
            time.sleep(0.2)
        except Exception as e:
            continue

    progress_bar.empty()
    status_text.empty()
    
    # حفظ تلقائي في الجلسة
    st.session_state.strong_signals = sorted(strong_signals, key=lambda x: abs(x['combined_score']), reverse=True)
    
    return st.session_state.strong_signals


def update_all_prices():
    """تحديث أسعار جميع التوصيات"""
    if not st.session_state.strong_signals:
        return 0

    progress_bar = st.progress(0)
    updated_count = 0

    for i, sig in enumerate(st.session_state.strong_signals):
        progress_bar.progress((i + 1) / len(st.session_state.strong_signals))
        
        new_price = get_current_price(sig['ticker'])
        if new_price is None:
            continue
            
        updated_count += 1
        sig['current_price'] = new_price
        entry = sig['entry_price']
        tp1, tp2, sl = sig['tp1'], sig['tp2'], sig['sl']
        is_buy = sig['direction'] == 'buy'

        if is_buy:
            total_dist = abs(tp2 - entry)
            move = new_price - entry
            prog = (move / total_dist * 100) if total_dist > 0 else 0

            if new_price >= tp2: 
                sig['status'] = 'tp_hit'
                sig['progress'] = 100.0
            elif new_price <= sl: 
                sig['status'] = 'sl_hit'
                sig['progress'] = 0.0
            else: 
                sig['status'] = 'active'
                sig['progress'] = max(-50, min(100, prog))

            sig['tp1_hit'] = new_price >= tp1
            sig['pnl_pips'] = new_price - entry
            sig['pnl_pct'] = ((new_price - entry) / entry * 100) if entry > 0 else 0
        else:
            total_dist = abs(entry - tp2)
            move = entry - new_price
            prog = (move / total_dist * 100) if total_dist > 0 else 0

            if new_price <= tp2: 
                sig['status'] = 'tp_hit'
                sig['progress'] = 100.0
            elif new_price >= sl: 
                sig['status'] = 'sl_hit'
                sig['progress'] = 0.0
            else: 
                sig['status'] = 'active'
                sig['progress'] = max(-50, min(100, prog))

            sig['tp1_hit'] = new_price <= tp1
            sig['pnl_pips'] = entry - new_price
            sig['pnl_pct'] = ((entry - new_price) / entry * 100) if entry > 0 else 0

        time.sleep(0.1)

    progress_bar.empty()
    st.session_state.last_update = datetime.now().strftime("%H:%M:%S")
    
    return updated_count


def save_analysis(ticker, tf, sig, comb, ts, fs, price, tgts):
    entry = {
        'ticker': ticker,
        'timeframe': tf,
        'signal': sig,
        'combined_score': comb,
        'tech_score': ts,
        'fund_score': fs,
        'price': price,
        'sl': tgts['sl'],
        'tp2': tgts['tp2'],
        'rr': tgts['rr'],
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    st.session_state.analysis_history.insert(0, entry)
    st.session_state.analysis_history = st.session_state.analysis_history[:50]


# ============================================================
# 10. الواجهة الجانبية
# ============================================================

with st.sidebar:
    st.markdown("# 🎯 ProTrade 5.0")
    st.markdown("---")

    # قسم إدارة البيانات
    with st.expander("💾 إدارة البيانات", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 تصدير", use_container_width=True):
                data_str = export_data()
                st.download_button(
                    label="⬇️ تحميل",
                    data=data_str,
                    file_name=f"protrade_backup_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    use_container_width=True
                )
        
        with col2:
            uploaded = st.file_uploader("📤 استيراد", type=['json'], label_visibility="collapsed")
            if uploaded:
                content = uploaded.read().decode()
                if import_data(content):
                    st.success("✅ تم الاستيراد!")
                    st.rerun()
        
        if st.button("🗑️ مسح الكل", use_container_width=True, type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    st.markdown("---")

    # اختيار الأصل
    asset_type = st.selectbox("📂 النوع", ["يدوي", "فوركس", "كريبتو", "أسهم", "مؤشرات"])

    if asset_type == "يدوي": 
        ticker = st.text_input("الرمز", "EURUSD=X").upper()
    elif asset_type == "فوركس":
        pair = st.selectbox("الزوج", list(FOREX_PAIRS.keys()))
        ticker = FOREX_PAIRS[pair]
    elif asset_type == "كريبتو":
        pair = st.selectbox("العملة", list(CRYPTO_PAIRS.keys()))
        ticker = CRYPTO_PAIRS[pair]
    elif asset_type == "أسهم":
        pair = st.selectbox("السهم", list(STOCKS.keys()))
        ticker = STOCKS[pair]
    else:
        pair = st.selectbox("المؤشر/سلعة", list(INDICES_COMMODITIES.keys()))
        ticker = INDICES_COMMODITIES[pair]

    tf_key = st.selectbox("⏰ الفريم", list(TIMEFRAMES.keys()), index=6)
    
    st.markdown("---")

    # أزرار التحليل
    if st.button("🚀 تحليل فوري", type="primary", use_container_width=True):
        with st.spinner("جاري التحليل..."):
            raw_df, info = fetch_data(ticker, tf_key)
            if raw_df is not None and len(raw_df) > 10:
                df_calc = calculate_indicators(raw_df)
                ts, td, curr, sigs, cons = smart_technical_score(df_calc)
                fs, fd = fundamental_score(info)
                tgts = calc_targets(curr, ts)
                ai_v = None
                
                if client: 
                    ai_v = get_ai_verdict(client, ticker, ts, fs, td, fd, curr, info)
                
                sig, sig_cls, comb = final_signal(ts, fs, ai_v)
                save_analysis(ticker, tf_key, sig, comb, ts, fs, safe_val(curr['Close']), tgts)
                
                st.session_state.update({
                    'data': df_calc,
                    'curr': curr,
                    'info': info,
                    'ticker': ticker,
                    'tf': tf_key,
                    'ts': ts,
                    'td': td,
                    'fs': fs,
                    'fd': fd,
                    'tgts': tgts,
                    'ai_v': ai_v,
                    'sig': sig,
                    'sig_cls': sig_cls,
                    'comb': comb,
                    'sigs': sigs,
                    'cons': cons,
                    'ok': True
                })
                
                st.success("✅ تم التحليل!")
                st.balloons()
            else: 
                st.error("❌ فشل في جلب البيانات")

    st.markdown("---")
    
    # قسم المسح
    scan_tf = st.selectbox("🔍 فريم المسح", ["يومي", "4 ساعات", "1 ساعة"], key="stf")
    
    if st.button("🔍 مسح التوصيات", use_container_width=True):
        with st.spinner("جاري المسح..."):
            results = background_scan(scan_tf)
            if results:
                st.success(f"✅ {len(results)} توصية نشطة")
            else:
                st.warning("⚠️ لا توصيات حالياً")

    if st.session_state.strong_signals:
        if st.button("🔄 تحديث الأسعار", use_container_width=True):
            with st.spinner("جاري التحديث..."):
                count = update_all_prices()
                st.success(f"✅ تم تحديث {count} سعر")
                st.rerun()

    if st.session_state.get('last_update'):
        st.caption(f"آخر تحديث: {st.session_state.last_update}")

    st.markdown("---")
    st.caption("v5.0 | ProTrade Elite")


# ============================================================
# 11. العرض الرئيسي
# ============================================================

render_tv_tape()

# عنوان الصفحة
st.markdown("""
<div style="text-align:center; padding:10px 0;">
    <h1 style="color:#00ff88; margin:0; font-size:32px;">📊 ProTrade Elite 5.0</h1>
    <p style="color:#888; margin:5px 0;">منصة التحليل الفني والأساسي المتكاملة</p>
</div>
""", unsafe_allow_html=True)

# التبويبات الرئيسية
main_t1, main_t2, main_t3, main_t4, main_t5 = st.tabs([
    "📈 التحليل", "🏆 التوصيات", "📜 السجل", "🤖 AI", "⚙️ الإعدادات"
])

# ============== التبويب 1: التحليل ==============
with main_t1:
    if st.session_state.get('ok'):
        # استخراج البيانات
        data = st.session_state['data']
        curr = st.session_state['curr']
        info = st.session_state['info']
        tgts = st.session_state['tgts']
        sig = st.session_state['sig']
        sig_cls = st.session_state['sig_cls']
        comb = st.session_state['comb']
        ts = st.session_state['ts']
        fs = st.session_state['fs']
        td = st.session_state['td']
        fd = st.session_state['fd']
        ai_v = st.session_state['ai_v']
        sigs_data = st.session_state['sigs']
        cons = st.session_state['cons']
        tkr = st.session_state['ticker']
        tf = st.session_state['tf']
        price = safe_val(curr['Close'])

        # تحذير البيانات القصيرة
        if len(data) < 200:
            st.warning("⚠️ فترة البيانات قصيرة - النتائج قد تكون غير دقيقة")

        # الإشارة الرئيسية
        st.markdown(f'''
        <div class="main-signal {sig_cls}">
            <div style="font-size:28px; margin-bottom:5px;">{sig}</div>
            <div style="font-size:14px; opacity:0.9;">
                {tkr} | {tf} | القوة: {comb:.1f}/100
            </div>
        </div>
        ''', unsafe_allow_html=True)

        # المقاييس الرئيسية
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f'<div class="metric-card"><h3>السعر الحالي</h3><h2>{price:.5f}</h2></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card"><h3>التحليل الفني</h3><h2>{ts:+.0f}</h2></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-card"><h3>التحليل الأساسي</h3><h2>{fs:+.0f}</h2></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="metric-card"><h3>نسبة المخاطرة</h3><h2>1:{tgts["rr"]:.1f}</h2></div>', unsafe_allow_html=True)

        # الأهداف
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("🛑 وقف الخسارة", f"{tgts['sl']:.5f}")
        t2.metric("🎯 الهدف 1", f"{tgts['tp1']:.5f}")
        t3.metric("🎯 الهدف 2", f"{tgts['tp2']:.5f}")
        t4.metric("🎯 الهدف 3", f"{tgts['tp3']:.5f}")

        # شريط الإجماع
        total_s = sigs_data['buy'] + sigs_data['sell'] + sigs_data['neutral']
        if total_s > 0:
            bp = sigs_data['buy'] / total_s * 100
            sp = sigs_data['sell'] / total_s * 100
            np_ = 100 - bp - sp
            
            st.markdown(f'''
            <div style="margin:15px 0;">
                <div style="display:flex; height:30px; border-radius:15px; overflow:hidden; background:#1a1a2e; border:1px solid #0f3460;">
                    <div style="width:{bp}%; background:linear-gradient(90deg, #00ff88, #00b09b); display:flex; align-items:center; justify-content:center; color:white; font-size:12px; font-weight:bold;">
                        {"شراء " + str(int(bp)) + "%" if bp > 10 else ""}
                    </div>
                    <div style="width:{np_}%; background:#546e7a; display:flex; align-items:center; justify-content:center; color:white; font-size:11px;">
                        {"محايد" if np_ > 15 else ""}
                    </div>
                    <div style="width:{sp}%; background:linear-gradient(90deg, #ff4444, #cb2d3e); display:flex; align-items:center; justify-content:center; color:white; font-size:12px; font-weight:bold;">
                        {"بيع " + str(int(sp)) + "%" if sp > 10 else ""}
                    </div>
                </div>
                <div style="display:flex; justify-content:space-between; margin-top:5px; font-size:11px; color:#888;">
                    <span>إشارات الشراء: {sigs_data['buy']}</span>
                    <span>المحايدة: {sigs_data['neutral']}</span>
                    <span>إشارات البيع: {sigs_data['sell']}</span>
                </div>
            </div>
            ''', unsafe_allow_html=True)

        # التبويبات الفرعية
        ct, tt, ft, at = st.tabs(["📉 الشارت", "🔬 فني", "📋 أساسي", "🤖 AI"])

        with ct:
            tv_sym = to_tv_symbol(tkr)
            tv_int = TV_INTERVALS.get(tf, "D")
            render_tv_chart(tv_sym, tv_int)

        with tt:
            st.subheader(f"التحليل الفني: {ts:+.0f} نقطة")
            st.progress(max(0.0, min(1.0, (ts + 50) / 100)))
            
            if ts > 20: 
                st.success(f"✅ قوي ({ts:+.0f})")
            elif ts > 0: 
                st.info(f"📈 إيجابي ({ts:+.0f})")
            elif ts < -20: 
                st.error(f"❌ سلبي قوي ({ts:+.0f})")
            elif ts < 0: 
                st.warning(f"📉 سلبي ({ts:+.0f})")
            else: 
                st.info(f"➖ محايد ({ts:+.0f})")
            
            st.markdown("### تفاصيل المؤشرات:")
            for d in td:
                icon = "🟢" if d[2] == "green" else "🔴" if d[2] == "red" else "⚪"
                st.markdown(f"{icon} **{d[0]}** — `{d[1]}`")

        with ft:
            st.subheader(f"التحليل الأساسي: {fs:+.0f} نقطة")
            st.progress(max(0.0, min(1.0, (fs + 50) / 100)))
            
            company = info.get('shortName', 'غير معروف')
            sector = info.get('sector', 'غير معروف')
            st.markdown(f"**الشركة:** {company}  |  **القطاع:** {sector}")
            
            st.markdown("### المؤشرات المالية:")
            for d in fd:
                icon = "🟢" if d[2] == "green" else "🔴" if d[2] == "red" else "⚪"
                st.markdown(f"{icon} **{d[0]}** — `{d[1]}`")

        with at:
            st.subheader("🤖 تحليل الذكاء الاصطناعي")
            if ai_v:
                dec = ai_v.get('final_decision', 'محايد')
                conf = ai_v.get('confidence', 50)
                reason = ai_v.get('reasoning', '')
                risk = ai_v.get('risk_level', 'متوسط')
                factors = ai_v.get('key_factors', [])
                
                colors = {'شراء قوي': '#00ff88', 'شراء': '#4caf50', 'محايد': '#ffeb3b', 'بيع': '#ff7777', 'بيع قوي': '#ff4444'}
                color = colors.get(dec, '#aaa')
                
                st.markdown(f'''
                <div class="ai-box">
                    <h2 style="text-align:center; color:{color}; margin:0; font-size:24px;">{dec}</h2>
                    <div style="text-align:center; margin:10px 0;">
                        <span style="background:#0f3460; padding:5px 15px; border-radius:20px; color:white;">
                            الثقة: {conf}%
                        </span>
                    </div>
                    <hr style="border-color:#333; margin:15px 0;">
                    <p style="color:#e0e0e0; line-height:1.6;">{reason}</p>
                    <div style="margin-top:15px;">
                        <span style="color:#888;">مستوى المخاطرة:</span>
                        <span style="color:{color}; font-weight:bold;">{risk}</span>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                
                if factors:
                    st.markdown("### العوامل الرئيسية:")
                    for f in factors:
                        st.markdown(f"🔹 {f}")
            else:
                st.info("ℹ️ أضف مفتاح HF_TOKEN في الإعدادات لتفعيل التحليل الذكي")

        # زر حفظ التحليل
        if st.button("💾 حفظ هذا التحليل", use_container_width=True):
            if save_current_analysis():
                st.success("✅ تم الحفظ في المفضلة!")
            else:
                st.warning("⚠️ لا يوجد تحليل حالي للحفظ")
    else:
        # حالة الترحيب
        st.markdown('''
        <div style="text-align:center; padding:40px 20px;">
            <div style="font-size:64px; margin-bottom:20px;">📊</div>
            <h2 style="color:#00ff88; margin-bottom:10px;">مرحباً بك في ProTrade Elite</h2>
            <p style="color:#888; font-size:16px; margin-bottom:30px;">
                اختر أصلاً من الشريط الجانبي واضغط على "تحليل فوري" للبدء
            </p>
            <div style="display:flex; justify-content:center; gap:20px; flex-wrap:wrap;">
                <div style="background:#1a1a2e; padding:20px; border-radius:10px; min-width:150px;">
                    <div style="font-size:24px; margin-bottom:10px;">💱</div>
                    <div style="color:#00ff88; font-weight:bold;">15 زوج فوركس</div>
                </div>
                <div style="background:#1a1a2e; padding:20px; border-radius:10px; min-width:150px;">
                    <div style="font-size:24px; margin-bottom:10px;">₿</div>
                    <div style="color:#00ff88; font-weight:bold;">10 عملات رقمية</div>
                </div>
                <div style="background:#1a1a2e; padding:20px; border-radius:10px; min-width:150px;">
                    <div style="font-size:24px; margin-bottom:10px;">📈</div>
                    <div style="color:#00ff88; font-weight:bold;">20+ مؤشر فني</div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        # شارت افتراضي
        render_tv_chart("FX:EURUSD", "D")


# ============== التبويب 2: التوصيات ==============
with main_t2:
    st.markdown("## 🏆 مركز التوصيات")
    
    if st.session_state.strong_signals:
        # أزرار التحكم
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            if st.button("🔄 تحديث جميع الأسعار", use_container_width=True, type="primary"):
                with st.spinner("جاري التحديث..."):
                    update_all_prices()
                    st.rerun()
        with c2:
            filter_type = st.selectbox("تصفية", ["الكل", "شراء", "بيع", "نشطة", "محققة"], label_visibility="collapsed")
        with c3:
            sort_by = st.selectbox("ترتيب", ["القوة", "الوقت", "الربح"], label_visibility="collapsed")

        # إحصائيات سريعة
        total_r = len(st.session_state.strong_signals)
        tp_hit = sum(1 for s in st.session_state.strong_signals if s.get('status') == 'tp_hit')
        sl_hit = sum(1 for s in st.session_state.strong_signals if s.get('status') == 'sl_hit')
        active = sum(1 for s in st.session_state.strong_signals if s.get('status') == 'active')
        total_pnl = sum(s.get('pnl_pct', 0) for s in st.session_state.strong_signals)
        
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        sc1.metric("📊 الكل", total_r)
        sc2.metric("✅ أصابت", tp_hit)
        sc3.metric("❌ فشلت", sl_hit)
        sc4.metric("⏳ نشطة", active)
        sc5.metric("💰 الربح", f"{total_pnl:+.2f}%")

        st.markdown("---")
        
        # تصفية التوصيات
        filtered_signals = st.session_state.strong_signals
        
        if filter_type == "شراء":
            filtered_signals = [s for s in filtered_signals if s['direction'] == 'buy']
        elif filter_type == "بيع":
            filtered_signals = [s for s in filtered_signals if s['direction'] == 'sell']
        elif filter_type == "نشطة":
            filtered_signals = [s for s in filtered_signals if s.get('status') == 'active']
        elif filter_type == "محققة":
            filtered_signals = [s for s in filtered_signals if s.get('status') == 'tp_hit']
        
        # الترتيب
        if sort_by == "القوة":
            filtered_signals = sorted(filtered_signals, key=lambda x: abs(x['combined_score']), reverse=True)
        elif sort_by == "الربح":
            filtered_signals = sorted(filtered_signals, key=lambda x: x.get('pnl_pct', 0), reverse=True)

        # عرض التوصيات
        for rec in filtered_signals:
            is_buy = rec.get('direction', 'buy') == 'buy'
            status = rec.get('status', 'active')
            progress = rec.get('progress', 0)
            current_price = rec.get('current_price', rec['price'])
            pnl_pct = rec.get('pnl_pct', 0)
            entry_p = rec['entry_price']

            # تحديد الحالة
            if status == 'tp_hit':
                card_class = "rec-strong-buy"
                status_text = "✅ أصابت الهدف!"
                status_class = "target-hit"
            elif status == 'sl_hit':
                card_class = "rec-strong-sell"
                status_text = "❌ ضربت وقف الخسارة"
                status_class = "target-miss"
            else:
                card_class = "rec-buy" if is_buy else "rec-sell"
                status_text = f"⏳ نشطة - {progress:.1f}%"
                status_class = "target-progress"

            direction_text = "🟢 شراء" if is_buy else "🔴 بيع"
            pnl_color = "#00ff88" if pnl_pct >= 0 else "#ff4444"
            bar_width = max(0, min(100, abs(progress)))
            bar_color = "linear-gradient(90deg, #00ff88, #00b09b)" if progress > 0 else "linear-gradient(90deg, #ff4444, #cb2d3e)"

            st.markdown(f'''
            <div class="rec-card {card_class}">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <div>
                        <h3 style="margin:0; color:{'#00ff88' if is_buy else '#ff4444'}; font-size:18px;">
                            {rec['name']}
                        </h3>
                        <p style="margin:3px 0; color:#888; font-size:12px;">
                            {rec['ticker']} | {rec['timeframe']} | {rec['time']}
                        </p>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:20px; font-weight:bold; color:{'#00ff88' if rec['combined_score'] > 0 else '#ff4444'};">
                            {rec['combined_score']:+.1f}
                        </div>
                        <div style="font-size:11px; color:#888;">درجة القوة</div>
                    </div>
                </div>

                <div class="{status_class}">{status_text}</div>

                <div style="background:#0a0a1a; border-radius:8px; height:25px; margin:10px 0; overflow:hidden; border:1px solid #333;">
                    <div style="width:{bar_width:.0f}%; height:100%; background:{bar_color}; 
                        display:flex; align-items:center; justify-content:center; color:white; 
                        font-size:12px; font-weight:bold; transition:width 0.5s;">
                        {abs(progress):.1f}%
                    </div>
                </div>

                <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; font-size:13px; margin-bottom:8px;">
                    <span>💵 الدخول: <b>{entry_p:.5f}</b></span>
                    <span>💵 الحالي: <b style="color:{pnl_color}">{current_price:.5f}</b></span>
                    <span style="color:{pnl_color}">📈 الربح: <b>{pnl_pct:+.2f}%</b></span>
                </div>

                <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; font-size:12px; color:#888; padding-top:8px; border-top:1px solid #333;">
                    <span>🛑 SL: {rec['sl']:.5f}</span>
                    <span>🎯 TP1: {rec['tp1']:.5f} {'✅' if rec.get('tp1_hit') else ''}</span>
                    <span>🎯 TP2: {rec['tp2']:.5f}</span>
                    <span>⚖️ R:R 1:{rec['rr']:.1f}</span>
                </div>
            </div>
            ''', unsafe_allow_html=True)
            
            # أزرار التحكم لكل توصية
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button(f"تحليل {rec['name']}", key=f"anal_{rec['ticker']}"):
                    st.session_state.ticker = rec['ticker']
                    st.session_state.ok = False
                    st.rerun()
            with col2:
                if st.button("حذف", key=f"del_{rec['ticker']}", type="secondary"):
                    st.session_state.strong_signals.remove(rec)
                    st.rerun()
    else:
        st.info("🔍 لا توجد توصيات حالياً. اضغط على 'مسح التوصيات' في الشريط الجانبي للبدء.")


# ============== التبويب 3: السجل ==============
with main_t3:
    st.markdown("## 📜 سجل التحليلات")
    
    if st.session_state.analysis_history or st.session_state.saved_signals:
        # تبويبات السجل
        hist_tab, saved_tab = st.tabs(["السجل العام", "المحفوظات"])
        
        with hist_tab:
            if st.session_state.analysis_history:
                if st.button("🗑️ مسح السجل", key="clr_hist"):
                    st.session_state.analysis_history = []
                    st.rerun()
                
                for e in st.session_state.analysis_history[:20]:
                    color = "#00ff88" if e['combined_score'] > 0 else "#ff4444"
                    st.markdown(f'''
                    <div style="background:#1a1a2e; padding:12px; border-radius:8px; margin:5px 0; 
                        border-right:4px solid {color};">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <b style="color:white; font-size:14px;">{e['ticker']}</b>
                                <span style="color:{color}; font-weight:bold; margin-right:10px;">{e['signal']}</span>
                            </div>
                            <span style="color:#888; font-size:11px;">{e['time']}</span>
                        </div>
                        <div style="color:#888; font-size:12px; margin-top:5px;">
                            {e['timeframe']} | السعر: {e['price']:.5f} | فني: {e['tech_score']:+.0f} | القوة: {e['combined_score']:.1f}
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
            else:
                st.info("السجل فارغ")
        
        with saved_tab:
            if st.session_state.saved_signals:
                for s in st.session_state.saved_signals:
                    st.markdown(f'''
                    <div style="background:#1a1a2e; padding:12px; border-radius:8px; margin:5px 0; 
                        border-right:4px solid #ffd700;">
                        <b style="color:#ffd700;">⭐ {s['ticker']}</b>
                        <span style="color:#888; margin:0 10px;">|</span>
                        <span style="color:white;">{s['sig']}</span>
                        <div style="color:#888; font-size:11px; margin-top:5px;">{s['time']}</div>
                    </div>
                    ''', unsafe_allow_html=True)
            else:
                st.info("لا توجد تحليلات محفوظة")
    else:
        st.info("📝 السجل فارغ حالياً")


# ============== التبويب 4: AI ==============
with main_t4:
    st.markdown("## 🤖 المستشار الذكي")
    
    # عرض المحادثة
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # إدخال المستخدم
    if prompt := st.chat_input("اسأل المستشار عن التحليل الفني، الأخبار، أو توصية..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            if client:
                # بناء السياق
                ctx = ""
                if st.session_state.get('ok'):
                    curr = st.session_state['curr']
                    ctx = f"الأصل الحالي: {st.session_state.get('ticker','غير محدد')}، السعر: {safe_val(curr['Close']):.5f}، القرار: {st.session_state.get('sig','غير محدد')}"
                
                if st.session_state.strong_signals:
                    top_recs = st.session_state.strong_signals[:3]
                    ctx += " | أقوى التوصيات: " + ", ".join([f"{r['name']}({r['signal']})" for r in top_recs])
                
                messages = [
                    {"role": "system", "content": f"أنت مستشار تداول خبير. تحلل بالعربية. السياق: {ctx}"},
                    *[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
                ]
                
                try:
                    with st.spinner("يفكر..."):
                        stream = client.chat_completion(messages, max_tokens=800, stream=True)
                        
                        def generate():
                            for chunk in stream:
                                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                                    yield chunk.choices[0].delta.content
                        
                        response = st.write_stream(generate())
                        st.session_state.messages.append({"role": "assistant", "content": response})
                        
                        # حفظ تلقائي للمحادثة المهمة
                        if any(keyword in prompt.lower() for keyword in ['توصية', 'شراء', 'بيع', 'تحليل']):
                            save_analysis('CHAT', 'AI', response[:50], 0, 0, 0, 0, {'sl':0,'tp2':0,'rr':0})
                            
                except Exception as e:
                    st.error(f"خطأ في الاتصال: {str(e)}")
            else:
                st.warning("⚠️ أضف مفتاح HF_TOKEN في ملف secrets.toml لتفعيل المستشار الذكي")
                st.info("يمكنك الحصول على مفتاح من: https://huggingface.co/settings/tokens")

    if st.button("🗑️ مسح المحادثة", key="clr_chat"):
        st.session_state.messages = []
        st.rerun()


# ============== التبويب 5: الإعدادات ==============
with main_t5:
    st.markdown("## ⚙️ الإعدادات والمعلومات")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎨 المظهر")
        dark_mode = st.toggle("الوضع الداكن", value=True)
        notifications = st.toggle("التنبيهات الصوتية", value=False)
        
        st.markdown("### 📊 الإعدادات")
        auto_refresh = st.toggle("تحديث تلقائي للأسعار", value=False)
        if auto_refresh:
            refresh_interval = st.slider("فترة التحديث (دقائق)", 1, 60, 5)
    
    with col2:
        st.markdown("### ℹ️ عن المنصة")
        st.markdown('''
        **ProTrade Elite 5.0**
        
        منصة تحليل متكاملة تشمل:
        - 📈 20+ مؤشر فني متقدم
        - 💱 15 زوج فوركس رئيسي
        - ₿ 10 عملات رقمية
        - 📊 10 أسهم أمريكية
        - 🤖 تحليل ذكي بالذكاء الاصطناعي
        - 🎯 نظام أهداف ووقف خسارة
        - 📱 واجهة متجاوبة
        
        **إخلاء المسؤولية:**
        التحليلات المقدمة للأغراض التعليمية فقط.
        التداول يحمل مخاطر عالية وقد تخسر رأس مالك.
        ''')
        
        st.markdown("### 📞 الدعم")
        st.markdown("للاستفسارات والدعم الفني: support@protrade.com")

# Footer
st.markdown("---")
st.caption("⚠️ ProTrade Elite 5.0 - تعليمي فقط. تداول على مسؤوليتك الخاصة.")
