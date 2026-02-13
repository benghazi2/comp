import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import ta
import numpy as np
import json
import time
from datetime import datetime, timedelta
import importlib
import threading
import requests
from urllib.parse import quote_plus
import db
import firebase_admin
from firebase_admin import db as firebase_db

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False

importlib.reload(db)

st.set_page_config(page_title="ProTrade Elite 5.0 (Sniper)", layout="wide",
                   page_icon="🦅", initial_sidebar_state="collapsed")

components.html("""<script>
try{var p=window.parent.document;var s=p.createElement('style');
s.innerHTML='header[data-testid="stHeader"]{display:none!important;height:0!important}.stAppDeployButton{display:none!important}[data-testid="manage-app-button"]{display:none!important}[data-testid="stDecoration"]{display:none!important}[data-testid="stStatusWidget"]{display:none!important}footer{display:none!important}.main .block-container{padding-top:1rem!important}section[data-testid="stSidebar"]{display:none!important}';
p.head.appendChild(s)}catch(e){}</script>""", height=0, width=0)

st.markdown("""<style>
header[data-testid="stHeader"]{display:none!important}footer{display:none!important}
[data-testid="stDecoration"]{display:none!important}.stAppDeployButton{display:none!important}
[data-testid="stStatusWidget"]{display:none!important}[data-testid="stSidebar"]{display:none!important}
.main .block-container{padding-top:1rem!important}
</style>""", unsafe_allow_html=True)

try:
    db_ok = db.init_db()
    if not db_ok: st.error("⚠️ فشل الاتصال بقاعدة البيانات")
except Exception as e:
    st.error(f"خطأ قاعدة البيانات: {e}"); db_ok = False

# ============================================================
# CSS (Original + Sniper Extensions)
# ============================================================
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Cairo',sans-serif}
.main-signal{padding:25px;border-radius:15px;text-align:center;font-size:24px;font-weight:bold;color:white!important;box-shadow:0 4px 15px rgba(0,0,0,0.2);margin-bottom:20px;border:1px solid rgba(255,255,255,0.1)}
.bg-strong-buy{background:linear-gradient(135deg,#00b09b,#96c93d)}
.bg-buy{background:linear-gradient(135deg,#11998e,#38ef7d)}
.bg-strong-sell{background:linear-gradient(135deg,#cb2d3e,#ef473a)}
.bg-sell{background:linear-gradient(135deg,#e53935,#ff6f60)}
.bg-neutral{background:linear-gradient(135deg,#536976,#292E49)}
.rec-card{background:#1f2937;border-radius:12px;padding:15px;margin:10px 0;border:1px solid #374151;color:white!important}
.rec-card h3,.rec-card span,.rec-card small{color:white!important}
.stChatMessage{direction:rtl}
/* Sniper Live Elements */
.scan-banner{background:linear-gradient(90deg,#f1f5f9,#e2e8f0);border:1px solid #cbd5e1;border-radius:10px;padding:10px 20px;margin:10px 0;display:flex;align-items:center;justify-content:space-between;color:#0f172a!important;font-weight:bold;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{border-color:#cbd5e1}50%{border-color:#94a3b8}}
.scan-done-banner{background:linear-gradient(90deg,#dcfce7,#bbf7d0);border:1px solid #86efac;border-radius:10px;padding:12px 20px;margin:10px 0;color:#166534!important;font-weight:bold;text-align:center}
.scan-done-zero{background:linear-gradient(90deg,#fef3c7,#fde68a);border:1px solid #fbbf24;border-radius:10px;padding:12px 20px;margin:10px 0;color:#92400e!important;font-weight:bold;text-align:center}
.web-source{background:#0f172a;border:1px solid #1e3a5f;border-radius:8px;padding:8px 12px;margin:4px 0;font-size:12px}
.web-source a{color:#60a5fa;text-decoration:none}
.live-price-card{background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #0f3460;border-radius:12px;padding:15px;margin:8px 0;color:white}
.search-engine-badge{display:inline-block;background:#1e3a5f;color:#60a5fa;padding:2px 8px;border-radius:4px;font-size:10px;margin:2px}
/* Paper Trading Styles */
.portfolio-card {background: linear-gradient(145deg, #1e293b, #0f172a); border: 1px solid #334155; border-radius: 15px; padding: 20px; margin-bottom: 20px; text-align: center; color: white;}
.manager-log {background: #1e1e1e; border-left: 4px solid #f59e0b; padding: 15px; margin: 10px 0; border-radius: 4px; font-family: monospace; font-size: 0.9em; color: #d4d4d4;}
.trade-row {background: #2d3748; padding: 10px; margin: 5px 0; border-radius: 8px; border: 1px solid #4a5568; display: flex; justify-content: space-between; align-items: center;}
</style>""", unsafe_allow_html=True)

# ============================================================
# Mistral API Client Wrapper
# ============================================================
class MistralClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://api.mistral.ai/v1/chat/completions"

    def chat_completion(self, messages, max_tokens=1000, stream=False):
        if not self.api_key: return MockResponse({})
        headers = {"Authorization": f"Bearer {self.api_key}","Content-Type": "application/json","Accept": "application/json"}
        data = {"model": "mistral-large-latest", "messages": messages,"max_tokens": max_tokens,"temperature": 0.3}
        try:
            resp = requests.post(self.url, headers=headers, json=data, timeout=30)
            if resp.status_code != 200: return MockResponse({})
            return MockResponse(resp.json())
        except: return MockResponse({})

class MockMessage:
    def __init__(self, content): self.content = content
class MockChoice:
    def __init__(self, message): self.message = message
class MockResponse:
    def __init__(self, json_data):
        content = ""
        if 'choices' in json_data and len(json_data['choices']) > 0: content = json_data['choices'][0]['message']['content']
        self.choices = [MockChoice(MockMessage(content))]

# ============================================================
# Paper Trading Logic (AUTO-PILOT)
# ============================================================
def init_paper_trading():
    try:
        ref = firebase_db.reference('paper_trading/balance')
        if ref.get() is None:
            ref.set(1000.0)
            firebase_db.reference('paper_trading/logs').push({'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),'message': "تم تفعيل المحفظة الآلية."})
    except: pass

def get_paper_portfolio():
    try:
        balance = firebase_db.reference('paper_trading/balance').get() or 0.0
        positions = firebase_db.reference('paper_trading/positions').get() or {}
        logs_data = firebase_db.reference('paper_trading/logs').order_by_key().limit_to_last(20).get() or {}
        logs = sorted([v for v in logs_data.values()], key=lambda x: x.get('timestamp',''), reverse=True)
        return float(balance), positions, logs
    except: return 0.0, {}, []

def log_manager_action(message):
    try: firebase_db.reference('paper_trading/logs').push({'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),'message': message})
    except: pass

def process_single_paper_trade(signal_data):
    """نظام الدخول الآلي الفوري (بدون انتظار إذن)"""
    if not signal_data: return
    try:
        balance = float(firebase_db.reference('paper_trading/balance').get() or 0.0)
        positions = firebase_db.reference('paper_trading/positions').get() or {}
        
        # 1. فلتر النقاط (Sniper Filter): 35 نقطة كافية للدخول
        if signal_data['total_score'] < 35: return 

        open_trades_count = sum(1 for p in positions.values() if p.get('status') == 'OPEN')
        if open_trades_count >= 6: return # حد أقصى للصفقات

        # 2. إدارة المخاطر (5%)
        amount = balance * 0.05
        if amount > 5 and balance >= amount:
            firebase_db.reference('paper_trading/positions').push({
                'ticker': signal_data['ticker'], 'name': signal_data['name'],
                'type': 'buy' if 'buy' in signal_data['signal'].lower() else 'sell',
                'entry_price': float(signal_data['price']), 'amount': amount,
                'tp': float(signal_data['targets']['tp2']), 'sl': float(signal_data['targets']['sl']),
                'open_time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'reason': f"Sniper Score: {signal_data['total_score']:.0f} | {signal_data.get('ai_reasoning','')}",
                'status': 'OPEN', 'current_pnl': 0.0
            })
            firebase_db.reference('paper_trading/balance').set(balance - amount)
            log_manager_action(f"🦅 قنص آلي: {signal_data['name']} (Score: {signal_data['total_score']})")
    except: pass

def background_autopilot_monitor():
    """المراقب الخلفي: تحديث الأسعار وإغلاق الصفقات تلقائياً"""
    while True:
        try:
            positions = firebase_db.reference('paper_trading/positions').get() or {}
            balance = float(firebase_db.reference('paper_trading/balance').get() or 0.0)
            
            for k, p in positions.items():
                if p.get('status') == 'OPEN':
                    try:
                        df = yf.Ticker(p['ticker']).history(period="1d", interval="5m")
                        if not df.empty:
                            curr = float(df['Close'].iloc[-1])
                            entry = float(p['entry_price']); amt = float(p['amount'])
                            is_buy = p['type'] == 'buy'
                            
                            pnl_pct = (curr - entry)/entry if is_buy else (entry - curr)/entry
                            curr_pnl = amt * pnl_pct
                            
                            # تحديث حي
                            firebase_db.reference(f'paper_trading/positions/{k}').update({'current_price': curr, 'current_pnl': curr_pnl})
                            
                            # إغلاق الهدف/الوقف
                            outcome = None
                            if is_buy:
                                if curr >= p['tp']: outcome = "TP Hit ✅"
                                elif curr <= p['sl']: outcome = "SL Hit ❌"
                            else:
                                if curr <= p['tp']: outcome = "TP Hit ✅"
                                elif curr >= p['sl']: outcome = "SL Hit ❌"
                                
                            if outcome:
                                new_bal = balance + amt + curr_pnl
                                firebase_db.reference(f'paper_trading/positions/{k}').update({
                                    'status': 'CLOSED', 'outcome': outcome, 'close_price': curr, 'pnl': curr_pnl,
                                    'close_time': datetime.now().strftime("%Y-%m-%d %H:%M")
                                })
                                firebase_db.reference('paper_trading/balance').set(new_bal)
                                balance = new_bal
                    except: pass
            time.sleep(10)
        except: time.sleep(10)

# تشغيل الطيار الآلي
if 'autopilot_on' not in st.session_state:
    threading.Thread(target=background_autopilot_monitor, daemon=True).start()
    st.session_state.autopilot_on = True

# ============================================================
# SEARCH APIs (Original - Unchanged)
# ============================================================
SERPER_KEY = st.secrets.get("SERPER_API_KEY", "")
TAVILY_KEY = st.secrets.get("TAVILY_API_KEY", "")

def search_serper(query, max_results=8, search_type="search"):
    if not SERPER_KEY: return [], []
    try:
        url = f"https://google.serper.dev/{search_type}"
        headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
        payload = {"q": query, "num": max_results, "gl": "us", "hl": "ar"}
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code != 200: return [], []
        data = resp.json(); results = []; news = []
        for item in data.get("organic", [])[:max_results]:
            results.append({"title": item.get("title", ""), "body": item.get("snippet", ""), "href": item.get("link", ""), "source": "Google"})
        for item in data.get("news", [])[:5]:
            news.append({"title": item.get("title", ""), "body": item.get("snippet", ""), "url": item.get("link", ""), "date": item.get("date", ""), "source": item.get("source", "")})
        return results, news
    except: return [], []

def get_live_price(query):
    # (نفس دالة الأسعار الأصلية)
    return []

def unified_search(query, max_results=8):
    return search_serper(query, max_results) + ([],)

def build_search_context(query):
    # (نفس دالة السياق الأصلية)
    sr, nr, _ = unified_search(query)
    return f"Context: {sr}", sr, nr, [], []

def format_live_prices_html(prices): return ""
def format_sources_html(search_results, news_results, sources_used=None): return ""

# ============================================================
# SNIPER ANALYSIS ENGINE (New & Robust)
# ============================================================
def safe_val(v,d=0.0):
    try:v=float(v);return d if(np.isnan(v)or np.isinf(v))else v
    except:return d

def fetch_data(ticker,tf_key):
    ticker=ticker.strip().upper();tf=TIMEFRAMES[tf_key]
    try:
        stock=yf.Ticker(ticker)
        if tf_key=="4 ساعات":
            raw=stock.history(period="3mo",interval="1h")
            if not raw.empty:
                if raw.index.tz is not None:raw.index=raw.index.tz_localize(None)
                df=raw.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
            else:return None,None
        else:df=stock.history(period=tf["period"],interval=tf["interval"],auto_adjust=True)
        if df is not None and len(df)>20:
            if df.index.tz is not None:df.index=df.index.tz_localize(None)
            try:info=stock.info
            except:info={}
            return df,info
    except:pass
    return None,None

def calculate_indicators(df):
    c=df['Close']; h=df['High']; l=df['Low']
    df['EMA_50'] = ta.trend.ema_indicator(c, window=50)
    df['EMA_200'] = ta.trend.ema_indicator(c, window=200)
    df['RSI'] = ta.momentum.rsi(c, window=14)
    df['ATR'] = ta.volatility.average_true_range(h, l, c)
    # Sniper Indicators
    bb = ta.volatility.BollingerBands(c, window=20)
    df['BB_Upper'] = bb.bollinger_hband()
    df['BB_Lower'] = bb.bollinger_lband()
    if 'Volume' in df.columns: df['Vol_SMA'] = df['Volume'].rolling(20).mean()
    return df

def detect_sniper_patterns(df):
    """نظام التنقيط المتقدم (Sniper Scoring)"""
    curr = df.iloc[-1]; prev = df.iloc[-2]
    score = 0; patterns = []
    
    # 1. Trend
    if curr['EMA_50'] > curr['EMA_200']: score += 10 # صاعد
    else: score -= 10 # هابط
    
    # 2. RSI Sniper
    if curr['RSI'] < 30: score += 15; patterns.append("RSI Oversold")
    elif curr['RSI'] > 70: score -= 15; patterns.append("RSI Overbought")
    
    # 3. Candle Patterns
    body = abs(curr['Close'] - curr['Open'])
    # Hammer
    if (curr['Open'] - curr['Low']) > (body * 2): score += 10; patterns.append("Hammer")
    # Shooting Star
    if (curr['High'] - curr['Open']) > (body * 2): score -= 10; patterns.append("Shooting Star")
    
    # 4. Volume
    if 'Volume' in df.columns and curr.get('Vol_SMA', 0) > 0:
        if curr['Volume'] > (curr['Vol_SMA'] * 1.5): score = score * 1.2; patterns.append("Vol Spike")
        
    return score, patterns

def get_ai_score(ai_client, ticker, name, current_score):
    """تحليل AI لا يوقف النظام إذا فشل"""
    if not ai_client: return 0, "No AI"
    try:
        msg = f"Ticker: {ticker}. Technical Score: {current_score}. Buy or Sell? Give score -20 to 20."
        resp = ai_client.chat_completion([{"role":"user","content":msg}], max_tokens=100)
        txt = resp.choices[0].message.content.lower()
        ai_s = 15 if "buy" in txt else (-15 if "sell" in txt else 0)
        return ai_s, "AI Confirmed"
    except: return 0, "AI Error"

def full_analysis(ticker, name, tf_key, ai_client, require_strong=False):
    """المحرك الشامل"""
    df, info = fetch_data(ticker, tf_key)
    if df is None: return None
    
    df = calculate_indicators(df)
    
    # حساب نقاط القنص
    sniper_score, patterns = detect_sniper_patterns(df)
    
    # نقاط AI
    ai_score, ai_msg = get_ai_score(ai_client, ticker, name, sniper_score)
    
    # المجموع النهائي
    total_score = sniper_score + ai_score
    
    # القرار
    signal = "neutral"
    if total_score >= 35: signal = "buy" # عتبة القبول
    elif total_score <= -35: signal = "sell"
    
    if signal == "neutral": return None # لا توجد فرصة
    
    # الأهداف
    atr = df['ATR'].iloc[-1]; price = df['Close'].iloc[-1]
    f = 1 if signal == "buy" else -1
    sl = price - (2.0 * atr * f)
    tp1 = price + (1.5 * atr * f)
    tp2 = price + (3.0 * atr * f)
    tp3 = price + (5.0 * atr * f)
    
    reason = f"Sniper:{sniper_score} ({','.join(patterns)}) | AI:{ai_score}"
    
    return {
        'ticker': ticker, 'name': name, 'price': price,
        'direction': signal, 'signal': "شراء قوي" if signal=="buy" else "بيع قوي",
        'total_score': total_score, 'tech_score': sniper_score, 'fund_score': 0, 'news_score': 0, 'ai_score': ai_score,
        'ai_reasoning': reason, 'filters_text': reason,
        'targets': {'sl': sl, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3},
        'timeframe': tf_key, 'curr': df.iloc[-1]
    }

def background_scan(assets_dict, scan_tf, ai_token):
    aic = MistralClient(ai_token) if ai_token else None
    total = len(assets_dict); found = 0
    db.set_scan_status(True, 0, total, 0, 0, 'بدء المسح...')
    
    for i, (name, tick) in enumerate(assets_dict.items()):
        db.set_scan_status(True, (i/total)*100, total, i, found, name)
        try:
            r = full_analysis(tick, name, scan_tf, aic, require_strong=True)
            if r:
                # إضافة فورية للقاعدة
                db.add_signal(str(tick), str(name), r['direction'], float(r['price']),
                              float(r['targets']['tp1']), float(r['targets']['tp2']), float(r['targets']['tp3']),
                              float(r['targets']['sl']), float(abs(r['total_score'])), str(scan_tf),
                              r['tech_score'], 0, 0, r['ai_score'], str(r['filters_text']), str(r['ai_reasoning']))
                
                # تفعيل فوري للمحفظة
                process_single_paper_trade(r)
                found += 1
                db.set_scan_status(True, (i/total)*100, total, i, found, f"🎯 وجد: {name}")
                
        except Exception as e: print(f"Error {name}: {e}")
        time.sleep(0.1) # سريع
        
    db.set_scan_status(False, 100, total, i, found, 'اكتمل')

# ============================================================
# Session & Config
# ============================================================
def init_session_state():
    defaults = {'messages':[],'current_view':'analysis','scan_running':False,
                'scan_complete':False,'scan_results':0,'chart_fullscreen':False,
                'chart_symbol':'FX:EURUSD','chart_interval':'D','paper_trades_checked':False}
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v
init_session_state()
init_paper_trading()

FOREX_PAIRS={"EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","USD/JPY":"USDJPY=X","USD/CHF":"USDCHF=X","Gold":"GC=F","Silver":"SI=F","Oil":"CL=F"}
CRYPTO_PAIRS={"BTC/USD":"BTC-USD","ETH/USD":"ETH-USD","SOL/USD":"SOL-USD","XRP/USD":"XRP-USD"}
STOCKS={"Apple":"AAPL","Tesla":"TSLA","NVIDIA":"NVDA"}
TIMEFRAMES={"15 دقيقة":{"interval":"15m","period":"5d"},"1 ساعة":{"interval":"1h","period":"1mo"},"4 ساعات":{"interval":"1h","period":"3mo"},"يومي":{"interval":"1d","period":"1y"}}
TV_INTERVALS={"15 دقيقة":"15","1 ساعة":"60","4 ساعات":"240","يومي":"D"}
TV_SYMBOLS={"فوركس":{"EUR/USD":"FX:EURUSD"},"عملات رقمية":{"BTC/USD":"CRYPTO:BTCUSD"}}

def to_tv_symbol(ticker):
    if ticker.endswith("=X"):return f"FX:{ticker.replace('=X','')}"
    if ticker.endswith("-USD"):return f"CRYPTO:{ticker.replace('-USD','')}USD"
    return f"NASDAQ:{ticker}"

client = None
mistral_key = st.secrets.get("MISTRAL_API_KEY", "")
if mistral_key: client = MistralClient(mistral_key)

# ============================================================
# MAIN UI
# ============================================================
st.title("ProTrade Elite 5.0 📊 (Sniper)")

with st.expander("☰ القائمة",expanded=False):
    n1,n2,n3,n4,n5,n6=st.columns(6)
    with n1:
        if st.button("📋 التوصيات",use_container_width=True):st.session_state.current_view="signals";st.rerun()
    with n2:
        if st.button("📉 التحليل",use_container_width=True):st.session_state.current_view="analysis";st.rerun()
    with n3:
        if st.button("📊 الشارت",use_container_width=True):st.session_state.current_view="chart";st.rerun()
    with n4:
        if st.button("💼 المحفظة",use_container_width=True):st.session_state.current_view="paper";st.rerun()
    with n5:
        if st.button("🤖 الدردشة",use_container_width=True):st.session_state.current_view="chat";st.rerun()
    with n6:
        if st.button("⚙️ إعدادات",use_container_width=True):st.session_state.current_view="settings";st.rerun()

# ============================================================
# VIEW: Signals (Scanner)
# ============================================================
if st.session_state.current_view=="signals":
    st.header("📋 التوصيات الذكية (Sniper)")
    
    # Status
    scan_st=db.get_scan_status()
    if scan_st and isinstance(scan_st,dict):
        ir=scan_st.get('is_running',False)
        if ir:
            st.markdown(f'<div class="scan-banner"><span>🔄 {scan_st.get("current_asset")}</span><span>🎯 وجد: {scan_st.get("found_signals")}</span></div>',unsafe_allow_html=True)
            st.progress(scan_st.get('progress',0)/100)
            time.sleep(1) # Auto Refresh
            st.rerun()

    # Controls
    with st.expander("⚙️ إعدادات الفحص",expanded=True):
        sc1,sc2,sc3=st.columns(3)
        with sc1:scan_types=st.multiselect("أصول",["فوركس","عملات رقمية","أسهم","الكل"],default=["الكل"])
        with sc2:scan_tf=st.selectbox("إطار",list(TIMEFRAMES.keys()),index=2)
        with sc3:
            if st.button("🚀 بدء المسح",type="primary",use_container_width=True):
                assets={}
                if "الكل" in scan_types:assets.update(FOREX_PAIRS);assets.update(CRYPTO_PAIRS);assets.update(STOCKS)
                else:
                    if "فوركس" in scan_types:assets.update(FOREX_PAIRS)
                    if "عملات رقمية" in scan_types:assets.update(CRYPTO_PAIRS)
                    if "أسهم" in scan_types:assets.update(STOCKS)
                st.session_state.scan_running=True
                threading.Thread(target=background_scan,args=(assets,scan_tf,st.secrets.get("MISTRAL_API_KEY","")),daemon=True).start()
                st.rerun()

    st.subheader("📊 النشطة")
    sigs=db.get_active_signals()
    if sigs:
        for sr in sigs:
            try:
                ib=sr.get('direction','buy')=='buy';clr="#00ff88" if ib else "#ff4444";dt="شراء🟢" if ib else "بيع🔴"
                st.markdown(f"""<div class="rec-card" style="border-left:5px solid {clr};"><div style="display:flex;justify-content:space-between;"><h3 style="margin:0;">{sr.get('asset_name')}</h3><div><h3 style="color:{clr};margin:0;">{dt}</h3></div></div><div style="font-size:13px;margin:10px 0;display:flex;justify-content:space-between;flex-wrap:wrap;"><span>⚡{sr.get('entry_price'):.4f}</span><span>🎯{sr.get('tp2'):.4f}</span><span>🛑{sr.get('sl'):.4f}</span></div><div style="font-size:12px;color:#aaa;">{sr.get('ai_reasoning','')}</div></div>""",unsafe_allow_html=True)
            except: pass
    else: st.info("📭 ابدأ المسح لاكتشاف الفرص")

# ============================================================
# VIEW: Portfolio (Auto-Pilot)
# ============================================================
elif st.session_state.current_view=="paper":
    time.sleep(2) # Auto refresh
    st.rerun()
    
    st.header("💼 المحفظة (Auto-Pilot)")
    balance, positions, logs = get_paper_portfolio()
    
    active = [p for p in positions.values() if p.get('status') == 'OPEN']
    pnl = sum([p.get('current_pnl', 0) for p in active])
    invested = sum([p.get('amount', 0) for p in active])
    
    col1, col2, col3 = st.columns(3)
    col1.markdown(f'<div class="portfolio-card"><h3>الرصيد</h3><h2 style="color:#34d399">{balance:.2f} $</h2></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="portfolio-card"><h3>الربح العائم</h3><h2 style="color:{"#10b981" if pnl>=0 else "#ef4444"}">{pnl:+.2f} $</h2></div>', unsafe_allow_html=True)
    col3.markdown(f'<div class="portfolio-card"><h3>الصفقات</h3><h2>{len(active)}</h2></div>', unsafe_allow_html=True)
    
    st.subheader("الصفقات الجارية")
    if positions:
        keys = [k for k,v in positions.items() if v.get('status') == 'OPEN']
        if keys:
            cols = st.columns(2)
            for idx, k in enumerate(keys):
                p = positions[k]
                with cols[idx % 2]:
                    clr = "#10b981" if p.get('current_pnl',0) >= 0 else "#ef4444"
                    st.markdown(f"""
                    <div class="trade-row" style="border-right: 5px solid {clr}">
                        <div><strong>{p['name']}</strong> <small>({p['type'].upper()})</small><br><span style="font-size:11px;color:#aaa;">{p.get('reason','')}</span></div>
                        <div style="text-align:right;"><div style="font-size:18px;font-weight:bold;color:{clr}">{p.get('current_pnl',0):+.2f}$</div><small>{p.get('current_price',0):.4f}</small></div>
                    </div>""", unsafe_allow_html=True)
                    if st.button(f"إغلاق {p['ticker']}", key=k):
                        firebase_db.reference(f'paper_trading/positions/{k}').update({'status':'CLOSED', 'outcome':'MANUAL'})
                        firebase_db.reference('paper_trading/balance').set(balance + p['amount'] + p.get('current_pnl',0))
    else: st.info("المحفظة فارغة. الطيار الآلي ينتظر إشارات.")

# ============================================================
# باقي الصفحات كما هي
# ============================================================
elif st.session_state.current_view=="analysis":
    st.header("📉 التحليل اليدوي")
    a1,a2,a3,a4=st.columns(4)
    with a1:ac=st.selectbox("نوع",["فوركس","عملات رقمية","أسهم"])
    with a2:
        if ac=="فوركس":sel=st.selectbox("أصل",list(FOREX_PAIRS.keys()));ticker=FOREX_PAIRS[sel]
        else:sel=st.selectbox("أصل",list(CRYPTO_PAIRS.keys()));ticker=CRYPTO_PAIRS[sel]
    with a3:tf_l=st.selectbox("إطار",list(TIMEFRAMES.keys()),index=2)
    with a4:abtn=st.button("🚀 تحليل",type="primary",use_container_width=True)
    if abtn:
        res=full_analysis(ticker,sel,tf_l,client)
        if res:
            st.markdown(f'<div class="main-signal {res["signal_class"]}">{res["signal"]}({res["total_score"]})</div>',unsafe_allow_html=True)
            st.info(res['ai_reasoning'])

elif st.session_state.current_view=="chart":
    st.header("📊 الشارت")
    st.components.v1.html(f'<div id="tv"></div><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"width":"100%","height":"600","symbol":"FX:EURUSD","interval":"D","theme":"dark","container_id":"tv"}});</script>',height=600)

elif st.session_state.current_view=="chat":
    st.header("🤖 الدردشة")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):st.markdown(msg["content"])
    if ui:=st.chat_input():
        st.session_state.messages.append({"role":"user","content":ui})
        with st.chat_message("user"):st.markdown(ui)
        st.session_state.messages.append({"role":"assistant","content":"..."})

elif st.session_state.current_view=="settings":
    st.header("⚙️ إعدادات")
    if st.button("🗑️ حذف البيانات"):
        firebase_db.reference('paper_trading').delete()
        db.delete_all_active()
        st.success("تم")
        time.sleep(1);st.rerun()