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

st.set_page_config(page_title="ProTrade Elite 5.0", layout="wide",
                   page_icon="📈", initial_sidebar_state="collapsed")

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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        data = {
            "model": "mistral-large-latest", 
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        try:
            resp = requests.post(self.url, headers=headers, json=data, timeout=60)
            if resp.status_code != 200:
                print(f"Mistral Error {resp.status_code}: {resp.text}")
                if resp.status_code == 429 or resp.status_code == 400:
                    data["model"] = "mistral-small-latest"
                    resp = requests.post(self.url, headers=headers, json=data, timeout=60)
            
            resp.raise_for_status()
            return MockResponse(resp.json())
        except Exception as e:
            print(f"Mistral API Exception: {e}")
            raise e

class MockMessage:
    def __init__(self, content): self.content = content
class MockChoice:
    def __init__(self, message): self.message = message
class MockResponse:
    def __init__(self, json_data):
        content = ""
        if 'choices' in json_data and len(json_data['choices']) > 0:
            content = json_data['choices'][0]['message']['content']
        self.choices = [MockChoice(MockMessage(content))]

# ============================================================
# Paper Trading Logic
# ============================================================
def init_paper_trading():
    try:
        ref = firebase_db.reference('paper_trading/balance')
        if ref.get() is None:
            ref.set(1000.0)
            firebase_db.reference('paper_trading/logs').push({
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'message': "تم فتح المحفظة الافتراضية برأس مال 1000$."
            })
    except: pass

def get_paper_portfolio():
    try:
        balance = firebase_db.reference('paper_trading/balance').get() or 0.0
        positions = firebase_db.reference('paper_trading/positions').get() or {}
        logs_data = firebase_db.reference('paper_trading/logs').order_by_key().limit_to_last(20).get() or {}
        logs = []
        for k, v in logs_data.items(): logs.append(v)
        logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return float(balance), positions, logs
    except: return 0.0, {}, []

def log_manager_action(message):
    try:
        firebase_db.reference('paper_trading/logs').push({
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'message': message
        })
    except: pass

def process_single_paper_trade(signal_data, ai_client):
    """
    معالجة إشارة واحدة فورياً:
    1. التحقق من الرصيد.
    2. استشارة AI.
    3. التنفيذ أو التجاهل.
    """
    if not signal_data or not ai_client: return

    # جلب الرصيد الحالي
    try:
        balance = float(firebase_db.reference('paper_trading/balance').get() or 0.0)
    except:
        balance = 0.0
    
    current_equity = balance
    
    # تحضير رسالة للذكاء الاصطناعي
    prompt = f"""
    أنت مدير محفظة ذكي. الرصيد المتاح: {current_equity}$.
    وصلتك إشارة تداول جديدة:
    - الأصل: {signal_data['name']} ({signal_data['ticker']})
    - الاتجاه: {signal_data['signal']}
    - السعر: {signal_data['price']}
    - القوة: {signal_data['total_score']}
    - الهدف: {signal_data['targets']['tp2']}
    - الوقف: {signal_data['targets']['sl']}

    قرر فوراً: هل تدخل هذه الصفقة؟ وكم تستثمر؟
    JSON فقط:
    {{
        "decision": "ENTER" أو "SKIP",
        "invest_amount": 0.0,
        "reason": "سبب مختصر جدا"
    }}
    """
    
    try:
        # استدعاء AI
        resp = ai_client.chat_completion(messages=[{"role":"user", "content": prompt}], max_tokens=300)
        txt = resp.choices[0].message.content.strip()
        if "```" in txt: txt = txt.split("```")[1].replace("json", "").strip()
        
        decision = json.loads(txt)
        
        if decision.get('decision') == 'ENTER':
            amount = float(decision.get('invest_amount', 0))
            if amount > 0 and balance >= amount:
                # تنفيذ الصفقة
                firebase_db.reference('paper_trading/positions').push({
                    'ticker': signal_data['ticker'],
                    'name': signal_data['name'],
                    'type': 'buy' if 'buy' in signal_data['signal'].lower() else 'sell',
                    'entry_price': float(signal_data['price']),
                    'amount': amount,
                    'tp': float(signal_data['targets']['tp2']),
                    'sl': float(signal_data['targets']['sl']),
                    'open_time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'reason': decision.get('reason', ''),
                    'status': 'OPEN'
                })
                # تحديث الرصيد
                new_balance = balance - amount
                firebase_db.reference('paper_trading/balance').set(new_balance)
                
                log_manager_action(f"✅ دخلت صفقة جديدة على {signal_data['name']} بقيمة {amount}$. السبب: {decision.get('reason','')}")
            else:
                log_manager_action(f"⚠️ رفضت الصفقة على {signal_data['name']} بسبب نقص الرصيد أو مبلغ غير صالح.")
        else:
            # تم التجاهل (لا نسجل في اللوج لتجنب الإزعاج، إلا إذا أردت)
            pass
            
    except Exception as e:
        print(f"AI Manager Error: {e}")

def update_paper_positions_status():
    balance, positions, _ = get_paper_portfolio()
    if not positions: return 0
    updates = 0
    for key, pos in positions.items():
        if pos.get('status') != 'OPEN': continue
        ticker = pos['ticker']
        is_buy = pos['type'] == 'buy'
        try:
            df, _ = fetch_data(ticker, "15 دقيقة")
            if df is None: continue
            curr_price = float(df['Close'].iloc[-1]); high = float(df['High'].iloc[-1]); low = float(df['Low'].iloc[-1])
            outcome = None; close_price = 0
            
            if is_buy:
                if low <= pos['sl']: outcome = 'SL'; close_price = pos['sl']
                elif high >= pos['tp']: outcome = 'TP'; close_price = pos['tp']
            else:
                if high >= pos['sl']: outcome = 'SL'; close_price = pos['sl']
                elif low <= pos['tp']: outcome = 'TP'; close_price = pos['tp']
            
            if outcome:
                if is_buy: pnl = ((close_price - pos['entry_price']) / pos['entry_price']) * pos['amount']
                else: pnl = ((pos['entry_price'] - close_price) / pos['entry_price']) * pos['amount']
                new_balance = balance + pos['amount'] + pnl
                firebase_db.reference(f'paper_trading/positions/{key}').update({
                    'status': 'CLOSED', 'close_price': close_price, 'close_time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'outcome': outcome, 'pnl': pnl
                })
                firebase_db.reference('paper_trading/balance').set(new_balance)
                msg = f"🔔 أغلقت صفقة {pos['name']} ({outcome}). الربح/الخسارة: {pnl:.2f}$."
                if outcome == 'TP': msg += " هدف رائع! 🚀"
                else: msg += " تم تفعيل وقف الخسارة."
                log_manager_action(msg)
                balance = new_balance
                updates += 1
        except: pass
    return updates

# ============================================================
# SEARCH APIs
# ============================================================
SERPER_KEY = st.secrets.get("SERPER_API_KEY", "")
TAVILY_KEY = st.secrets.get("TAVILY_API_KEY", "")

def search_serper(query, max_results=8, search_type="search"):
    if not SERPER_KEY: return [], []
    try:
        url = f"https://google.serper.dev/{search_type}"
        headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
        payload = {"q": query, "num": max_results, "gl": "us", "hl": "ar"}
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code != 200: return [], []
        data = resp.json(); results = []; news = []
        for item in data.get("organic", [])[:max_results]:
            results.append({"title": item.get("title", ""), "body": item.get("snippet", ""), "href": item.get("link", ""), "source": "Google (Serper)"})
        kg = data.get("knowledgeGraph", {})
        if kg: results.insert(0, {"title": f"📋 {kg.get('title','')}", "body": kg.get("description", ""), "href": kg.get("website", ""), "source": "Google Knowledge"})
        ab = data.get("answerBox", {})
        if ab: results.insert(0, {"title": "💡 إجابة مباشرة", "body": ab.get("answer", "") or ab.get("snippet", ""), "href": ab.get("link", ""), "source": "Google Answer"})
        for item in data.get("news", [])[:5]:
            news.append({"title": item.get("title", ""), "body": item.get("snippet", ""), "url": item.get("link", ""), "date": item.get("date", ""), "source": item.get("source", "")})
        return results, news
    except: return [], []

def search_serper_news(query, max_results=8):
    if not SERPER_KEY: return []
    try:
        headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
        payload = {"q": query, "num": max_results, "gl": "us", "hl": "ar", "type": "news"}
        resp = requests.post("https://google.serper.dev/news", json=payload, headers=headers, timeout=15)
        if resp.status_code != 200: return []
        data = resp.json(); news = []
        for item in data.get("news", [])[:max_results]:
            news.append({"title": item.get("title", ""), "body": item.get("snippet", ""), "url": item.get("link", ""), "date": item.get("date", ""), "source": item.get("source", "")})
        return news
    except: return []

def search_tavily(query, max_results=6):
    if not TAVILY_KEY: return [], []
    try:
        resp = requests.post("https://api.tavily.com/search", json={"api_key": TAVILY_KEY, "query": query, "search_depth": "advanced", "include_answer": True, "max_results": max_results}, timeout=15)
        if resp.status_code != 200: return [], []
        data = resp.json(); results = []
        if data.get("answer", ""): results.insert(0, {"title": "🧠 تحليل Tavily AI", "body": data.get("answer", ""), "href": "", "source": "Tavily AI"})
        for item in data.get("results", [])[:max_results]:
            results.append({"title": item.get("title", ""), "body": item.get("content", "")[:300], "href": item.get("url", ""), "source": "Tavily"})
        return results, []
    except: return [], []

def search_ddg(query, max_results=6):
    if not HAS_DDG: return []
    try:
        with DDGS() as ddgs: return list(ddgs.text(query, max_results=max_results, region='wt-wt'))
    except: return []

def search_ddg_news(query, max_results=5):
    if not HAS_DDG: return []
    try:
        with DDGS() as ddgs: return list(ddgs.news(query, max_results=max_results, region='wt-wt'))
    except: return []

def get_live_price(query):
    price_map = {
        'ذهب':'GC=F','gold':'GC=F','الذهب':'GC=F','xauusd':'GC=F','xau':'GC=F',
        'فضة':'SI=F','silver':'SI=F','الفضة':'SI=F',
        'نفط':'CL=F','oil':'CL=F','النفط':'CL=F','crude':'CL=F',
        'بيتكوين':'BTC-USD','bitcoin':'BTC-USD','btc':'BTC-USD',
        'ايثريوم':'ETH-USD','ethereum':'ETH-USD','eth':'ETH-USD',
        'سولانا':'SOL-USD','solana':'SOL-USD','sol':'SOL-USD',
        'ريبل':'XRP-USD','xrp':'XRP-USD',
        'دوج':'DOGE-USD','doge':'DOGE-USD','dogecoin':'DOGE-USD',
        'بنب':'BNB-USD','bnb':'BNB-USD',
        'كاردانو':'ADA-USD','ada':'ADA-USD',
        'يورو':'EURUSD=X','eurusd':'EURUSD=X','اليورو':'EURUSD=X',
        'باوند':'GBPUSD=X','gbpusd':'GBPUSD=X','الباوند':'GBPUSD=X','استرليني':'GBPUSD=X',
        'ين':'USDJPY=X','usdjpy':'USDJPY=X','الين':'USDJPY=X',
        'فرنك':'USDCHF=X','usdchf':'USDCHF=X',
        'ابل':'AAPL','apple':'AAPL','تسلا':'TSLA','tesla':'TSLA',
        'نفيديا':'NVDA','nvidia':'NVDA','انفيديا':'NVDA',
        'جوجل':'GOOGL','google':'GOOGL','امازون':'AMZN','amazon':'AMZN',
        'مايكروسوفت':'MSFT','microsoft':'MSFT','ميتا':'META','meta':'META',
        'نتفلكس':'NFLX','netflix':'NFLX','amd':'AMD','انتل':'INTC','intel':'INTC',
        'sp500':'^GSPC','ناسداك':'^IXIC','داو جونز':'^DJI','dow':'^DJI',
        'avax':'AVAX-USD','dot':'DOT-USD','غاز':'NG=F','نحاس':'HG=F',
    }
    name_map = {
        'GC=F':'الذهب (XAU/USD)','SI=F':'الفضة','CL=F':'النفط (WTI)','NG=F':'الغاز','HG=F':'النحاس',
        'BTC-USD':'بيتكوين','ETH-USD':'إيثريوم','SOL-USD':'سولانا','XRP-USD':'ريبل',
        'BNB-USD':'بينانس','ADA-USD':'كاردانو','DOGE-USD':'دوجكوين','AVAX-USD':'أفالانش','DOT-USD':'بولكادوت',
        'EURUSD=X':'يورو/دولار','GBPUSD=X':'باوند/دولار','USDJPY=X':'دولار/ين','USDCHF=X':'دولار/فرنك',
        'AAPL':'آبل','TSLA':'تسلا','NVDA':'إنفيديا','GOOGL':'جوجل','AMZN':'أمازون',
        'MSFT':'مايكروسوفت','META':'ميتا','NFLX':'نتفلكس','AMD':'AMD','INTC':'إنتل',
        '^GSPC':'S&P 500','^IXIC':'ناسداك','^DJI':'داو جونز',
    }
    ql = query.lower().strip()
    matched = set()
    for kw, tick in price_map.items():
        if kw in ql: matched.add(tick)
    if not matched: return []
    results = []
    for tick in matched:
        try:
            hist = yf.Ticker(tick).history(period="5d", interval="1d")
            if hist.empty: continue
            cur=float(hist['Close'].iloc[-1]); prev=float(hist['Close'].iloc[-2]) if len(hist)>1 else cur
            chg=cur-prev; pct=(chg/prev*100) if prev!=0 else 0
            results.append({'ticker':tick,'name':name_map.get(tick,tick),'price':cur,'change':chg,'change_pct':pct,
                'high':float(hist['High'].iloc[-1]),'low':float(hist['Low'].iloc[-1]),
                'open':float(hist['Open'].iloc[-1]),'prev_close':prev,
                'color':'#00ff88' if chg>=0 else '#ff4444',
                'timestamp':datetime.now().strftime('%Y-%m-%d %H:%M UTC')})
        except: continue
    return results

def unified_search(query, max_results=8):
    all_results = []; all_news = []; sources_used = []
    if SERPER_KEY:
        sr, sn = search_serper(query, max_results); all_results.extend(sr)
        if sr: sources_used.append("Google")
        sne = search_serper_news(query, 5); all_news.extend(sne or sn)
        if sne: sources_used.append("Google News")
    if TAVILY_KEY and len(all_results) < 5:
        tr, _ = search_tavily(query, max_results); all_results.extend(tr)
        if tr: sources_used.append("Tavily AI")
    if len(all_results) < 3:
        dr = search_ddg(query, max_results); all_results.extend(dr)
        if dr: sources_used.append("DuckDuckGo")
        if not all_news: all_news.extend(search_ddg_news(query, 5))
    
    unique = []; seen = set()
    for r in all_results:
        if r.get('title') not in seen: seen.add(r.get('title')); unique.append(r)
    unique_n = []; seen_n = set()
    for n in all_news:
        if n.get('title') not in seen_n: seen_n.add(n.get('title')); unique_n.append(n)
    return unique[:max_results], unique_n[:8], sources_used

def build_search_context(query):
    financial_words = ['سعر','price','btc','eth','gold','ذهب','دولار','يورو','سهم','stock','crypto','بيتكوين','نفط','oil','تداول','trading','forex','فوركس','market','سوق','اقتصاد','economy','fed','فائدة','interest','inflation','تضخم','nasdaq','bitcoin','ethereum','solana','usd','eur','gbp','jpy','توقع','forecast','تحليل','analysis','أخبار','news','xrp','bnb','ada','doge','apple','tesla','nvidia','google','amazon','microsoft','meta','netflix','amd','intel','كم','how much','فضة','silver','نحاس','copper','غاز','gas','باوند','ين','فرنك','ريبل','كاردانو','سولانا','ايثريوم','ابل','تسلا','نفيديا','جوجل','امازون','مايكروسوفت','ميتا','نتفلكس','sp500','داو','ناسداك','مؤشر','انفيديا']
    is_financial = any(w in query.lower() for w in financial_words)
    live_prices = get_live_price(query) if is_financial else []
    search_results, news_results, sources_used = unified_search(query, max_results=8)
    parts = [f"[التاريخ والوقت: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC]"]
    if live_prices:
        parts.append("\n=== أسعار لحظية (Yahoo Finance) ===")
        for p in live_prices: parts.append(f"• {p['name']}: {p['price']:.2f} USD | التغير: {p['change']:+.2f} ({p['change_pct']:+.2f}%)")
    if news_results:
        parts.append("\n=== آخر الأخبار ===")
        for i, r in enumerate(news_results[:6], 1): parts.append(f"{i}. [{r.get('date','')}] {r.get('title','')}: {r.get('body','')[:200]}")
    if search_results:
        parts.append("\n=== نتائج البحث ===")
        for i, r in enumerate(search_results[:8], 1): parts.append(f"{i}. [{r.get('source','')}] {r.get('title','')}: {r.get('body','')[:250]}")
    return "\n".join(parts) if len(parts) > 1 else "", search_results, news_results, live_prices, sources_used

def format_live_prices_html(prices):
    if not prices: return ""
    html = ""
    for p in prices:
        arrow = "▲" if p['change']>=0 else "▼"
        html += f"""<div class="live-price-card"><div style="display:flex;justify-content:space-between;align-items:center;"><span style="font-size:18px;font-weight:bold;">{p['name']}</span><div style="text-align:left;"><div style="font-size:22px;font-weight:bold;color:{p['color']};">{p['price']:,.2f} $</div><div style="font-size:14px;color:{p['color']};">{arrow} {p['change']:+,.2f} ({p['change_pct']:+.2f}%)</div></div></div><div style="display:flex;justify-content:space-between;margin-top:8px;font-size:12px;color:#9ca3af;"><span>افتتاح: {p['open']:,.2f}</span><span>أعلى: {p['high']:,.2f}</span><span>أدنى: {p['low']:,.2f}</span><span>سابق: {p['prev_close']:,.2f}</span></div><div style="font-size:10px;color:#6b7280;margin-top:5px;">📊 Yahoo Finance | {p['timestamp']}</div></div>"""
    return html

def format_sources_html(search_results, news_results, sources_used=None):
    if not search_results and not news_results: return ""
    html = '<div style="margin-top:15px;padding-top:10px;border-top:1px solid #333;">'
    if sources_used:
        html += '<p style="color:#64748b;font-size:11px;margin-bottom:5px;">🔍 '
        for s in sources_used: html += f'<span class="search-engine-badge">{s}</span> '
        html += '</p>'
    html += '<p style="color:#94a3b8;font-size:13px;margin-bottom:8px;">📎 المصادر:</p>'
    all_src = []
    for r in (news_results or [])[:3]: all_src.append({'title':r.get('title',''),'url':r.get('url',''),'source':r.get('source',''),'type':'news'})
    for r in (search_results or [])[:4]: all_src.append({'title':r.get('title',''),'url':r.get('href',''),'source':r.get('source',''),'type':'web'})
    for s in all_src[:6]:
        icon="📰" if s.get('type')=='news' else "🔗"; title=s['title'][:70]+"..." if len(s.get('title',''))>70 else s.get('title',''); url=s.get('url','#'); src=f" <span style='color:#475569;font-size:10px;'>({s.get('source','')})</span>" if s.get('source') else ""
        html += f'<div class="web-source">{icon} <a href="{url}" target="_blank">{title}</a>{src}</div>'
    html += '</div>'
    return html

# ============================================================
# Session State & Config
# ============================================================
def init_session_state():
    defaults = {'messages':[],'current_view':'analysis','scan_running':False,
                'scan_complete':False,'scan_results':0,'chart_fullscreen':False,
                'chart_symbol':'FX:EURUSD','chart_interval':'D','paper_trades_checked':False}
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v
init_session_state()
init_paper_trading()

FOREX_PAIRS={"EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","USD/JPY":"USDJPY=X","USD/CHF":"USDCHF=X","AUD/USD":"AUDUSD=X","NZD/USD":"NZDUSD=X","USD/CAD":"USDCAD=X","EUR/GBP":"EURGBP=X","EUR/JPY":"EURJPY=X","GBP/JPY":"GBPJPY=X","Gold":"GC=F","Silver":"SI=F","Oil":"CL=F"}
CRYPTO_PAIRS={"BTC/USD":"BTC-USD","ETH/USD":"ETH-USD","SOL/USD":"SOL-USD","XRP/USD":"XRP-USD","BNB/USD":"BNB-USD","ADA/USD":"ADA-USD","DOGE/USD":"DOGE-USD","DOT/USD":"DOT-USD","AVAX/USD":"AVAX-USD"}
STOCKS={"Apple":"AAPL","Tesla":"TSLA","NVIDIA":"NVDA","Google":"GOOGL","Amazon":"AMZN","Microsoft":"MSFT","Meta":"META","Netflix":"NFLX","AMD":"AMD","Intel":"INTC"}
TIMEFRAMES={"15 دقيقة":{"interval":"15m","period":"5d"},"1 ساعة":{"interval":"1h","period":"1mo"},"4 ساعات":{"interval":"1h","period":"3mo"},"يومي":{"interval":"1d","period":"1y"}}
TV_INTERVALS={"15 دقيقة":"15","1 ساعة":"60","4 ساعات":"240","يومي":"D"}
TRACKING_INTERVALS={"15 دقيقة":{"interval":"5m","period":"5d"},"1 ساعة":{"interval":"15m","period":"1mo"},"4 ساعات":{"interval":"1h","period":"1mo"},"يومي":{"interval":"1h","period":"3mo"}}
TV_SYMBOLS={"فوركس":{"EUR/USD":"FX:EURUSD","GBP/USD":"FX:GBPUSD","USD/JPY":"FX:USDJPY","USD/CHF":"FX:USDCHF","AUD/USD":"FX:AUDUSD","NZD/USD":"FX:NZDUSD","USD/CAD":"FX:USDCAD","EUR/GBP":"FX:EURGBP","EUR/JPY":"FX:EURJPY","GBP/JPY":"FX:GBPJPY"},"سلع":{"الذهب":"COMEX:GC1!","الفضة":"COMEX:SI1!","النفط":"NYMEX:CL1!","الغاز":"NYMEX:NG1!","النحاس":"COMEX:HG1!"},"عملات رقمية":{"BTC/USD":"CRYPTO:BTCUSD","ETH/USD":"CRYPTO:ETHUSD","SOL/USD":"CRYPTO:SOLUSD","XRP/USD":"CRYPTO:XRPUSD","BNB/USD":"CRYPTO:BNBUSD","ADA/USD":"CRYPTO:ADAUSD","DOGE/USD":"CRYPTO:DOGEUSD","AVAX/USD":"CRYPTO:AVAXUSD"},"أسهم أمريكية":{"Apple":"NASDAQ:AAPL","Tesla":"NASDAQ:TSLA","NVIDIA":"NASDAQ:NVDA","Google":"NASDAQ:GOOGL","Amazon":"NASDAQ:AMZN","Microsoft":"NASDAQ:MSFT","Meta":"NASDAQ:META","Netflix":"NASDAQ:NFLX","AMD":"NASDAQ:AMD","Intel":"NASDAQ:INTC"},"مؤشرات":{"S&P 500":"FOREXCOM:SPXUSD","Nasdaq":"NASDAQ:NDX","Dow Jones":"DJ:DJI","DAX":"XETR:DAX","FTSE 100":"FOREXCOM:UKXGBP"}}

def to_tv_symbol(ticker):
    if ticker.endswith("=X"):return f"FX:{ticker.replace('=X','')}"
    if ticker.endswith("-USD"):return f"CRYPTO:{ticker.replace('-USD','')}USD"
    if ticker=="GC=F":return "COMEX:GC1!"
    if ticker=="SI=F":return "COMEX:SI1!"
    if ticker=="CL=F":return "NYMEX:CL1!"
    return f"NASDAQ:{ticker}"

# إعداد عميل ميسترال إذا وجد المفتاح
client = None
mistral_key = st.secrets.get("MISTRAL_API_KEY", "")
if mistral_key:
    client = MistralClient(mistral_key)

# ============================================================
# ANALYSIS FUNCTIONS
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
        if df is not None and len(df)>15:
            if df.index.tz is not None:df.index=df.index.tz_localize(None)
            try:info=stock.info
            except:info={}
            return df,info
    except:pass
    return None,None

def calculate_indicators(df):
    c,h,low=df['Close'],df['High'],df['Low'];vol=df['Volume'] if 'Volume' in df.columns else None
    for w in [5,10,20,50,100,200]:
        try:df[f'EMA_{w}']=ta.trend.ema_indicator(c,window=w)
        except:pass
    for w in [20,50,200]:
        try:df[f'SMA_{w}']=ta.trend.sma_indicator(c,window=w)
        except:pass
    try:m=ta.trend.MACD(c);df['MACD']=m.macd();df['MACD_Signal']=m.macd_signal();df['MACD_Hist']=m.macd_diff()
    except:pass
    try:df['RSI']=ta.momentum.rsi(c,window=14)
    except:pass
    try:s=ta.momentum.StochasticOscillator(h,low,c);df['Stoch_K']=s.stoch();df['Stoch_D']=s.stoch_signal()
    except:pass
    try:bb=ta.volatility.BollingerBands(c,window=20);df['BB_Upper']=bb.bollinger_hband();df['BB_Lower']=bb.bollinger_lband()
    except:pass
    try:df['ATR']=ta.volatility.average_true_range(h,low,c)
    except:pass
    try:a=ta.trend.ADXIndicator(h,low,c);df['ADX']=a.adx();df['DI_plus']=a.adx_pos();df['DI_minus']=a.adx_neg()
    except:pass
    try:df['PSAR']=ta.trend.PSARIndicator(h,low,c).psar()
    except:pass
    try:ich=ta.trend.IchimokuIndicator(h,low);df['Ich_A']=ich.ichimoku_a();df['Ich_B']=ich.ichimoku_b()
    except:pass
    try:df['CCI']=ta.trend.cci(h,low,c,window=20)
    except:pass
    try:df['Williams_R']=ta.momentum.williams_r(h,low,c)
    except:pass
    if vol is not None:
        try:df['MFI']=ta.volume.money_flow_index(h,low,c,vol)
        except:pass
        try:df['OBV']=ta.volume.on_balance_volume(c,vol)
        except:pass
    try:df['ROC']=ta.momentum.roc(c,window=12)
    except:pass
    return df

def apply_all_filters(df,info):
    curr=df.iloc[-1];prev=df.iloc[-2] if len(df)>1 else curr;price=safe_val(curr['Close']);filters=[];total=0
    e50=safe_val(curr.get('EMA_50'));e200=safe_val(curr.get('EMA_200'))
    if e50>0 and e200>0:
        if e50>e200:filters.append(("تقاطع ذهبي",10,"pass","صاعد"));total+=10
        else:filters.append(("تقاطع الموت",-10,"fail","هابط"));total-=10
    if e200>0:
        if price>e200:filters.append(("فوق EMA200",8,"pass",f"{price:.4f}>{e200:.4f}"));total+=8
        else:filters.append(("تحت EMA200",-8,"fail",f"{price:.4f}<{e200:.4f}"));total-=8
    e5=safe_val(curr.get('EMA_5'));e10=safe_val(curr.get('EMA_10'));e20=safe_val(curr.get('EMA_20'))
    if all(v>0 for v in[e5,e10,e20,e50]):
        if e5>e10>e20>e50:filters.append(("EMAs صعودي",7,"pass",""));total+=7
        elif e5<e10<e20<e50:filters.append(("EMAs هبوطي",-7,"fail",""));total-=7
        else:filters.append(("EMAs مختلط",0,"warn",""))
    adx=safe_val(curr.get('ADX'));dip=safe_val(curr.get('DI_plus'));dim=safe_val(curr.get('DI_minus'))
    if adx>30:
        if dip>dim:filters.append(("ADX صاعد قوي",8,"pass",f"{adx:.0f}"));total+=8
        else:filters.append(("ADX هابط قوي",-8,"fail",f"{adx:.0f}"));total-=8
    elif adx>20:
        if dip>dim:filters.append(("ADX صاعد",4,"pass",f"{adx:.0f}"));total+=4
        else:filters.append(("ADX هابط",-4,"fail",f"{adx:.0f}"));total-=4
    psar=safe_val(curr.get('PSAR'))
    if psar>0:
        if price>psar:filters.append(("PSAR صعودي",5,"pass",""));total+=5
        else:filters.append(("PSAR هبوطي",-5,"fail",""));total-=5
    ia=safe_val(curr.get('Ich_A'));ib=safe_val(curr.get('Ich_B'))
    if ia>0 and ib>0:
        if price>max(ia,ib):filters.append(("فوق إيشيموكو",6,"pass",""));total+=6
        elif price<min(ia,ib):filters.append(("تحت إيشيموكو",-6,"fail",""));total-=6
        else:filters.append(("داخل السحابة",0,"warn",""))
    rsi=safe_val(curr.get('RSI'))
    if rsi>0:
        if rsi<25:filters.append(("RSI بيعي شديد",10,"pass",f"{rsi:.0f}"));total+=10
        elif rsi<35:filters.append(("RSI قريب بيعي",5,"pass",f"{rsi:.0f}"));total+=5
        elif rsi>75:filters.append(("RSI شرائي شديد",-10,"fail",f"{rsi:.0f}"));total-=10
        elif rsi>65:filters.append(("RSI قريب شرائي",-5,"fail",f"{rsi:.0f}"));total-=5
        else:filters.append(("RSI وسط",0,"warn",f"{rsi:.0f}"))
    mh=safe_val(curr.get('MACD_Hist'));mhp=safe_val(prev.get('MACD_Hist')) if hasattr(prev,'get') else 0
    if mh>0 and mhp<=0:filters.append(("MACD صعودي",8,"pass",""));total+=8
    elif mh<0 and mhp>=0:filters.append(("MACD هبوطي",-8,"fail",""));total-=8
    elif mh>0:filters.append(("MACD+",4,"pass",""));total+=4
    elif mh<0:filters.append(("MACD-",-4,"fail",""));total-=4
    sk=safe_val(curr.get('Stoch_K'));sd=safe_val(curr.get('Stoch_D'))
    if sk>0:
        if sk<20 and sk>sd:filters.append(("Stoch بيعي+",7,"pass",f"K={sk:.0f}"));total+=7
        elif sk>80 and sk<sd:filters.append(("Stoch شرائي+",-7,"fail",f"K={sk:.0f}"));total-=7
        elif sk<20:filters.append(("Stoch بيعي",4,"pass",f"K={sk:.0f}"));total+=4
        elif sk>80:filters.append(("Stoch شرائي",-4,"fail",f"K={sk:.0f}"));total-=4
    cci=safe_val(curr.get('CCI'))
    if cci!=0:
        if cci<-200:filters.append(("CCI بيعي",6,"pass",f"{cci:.0f}"));total+=6
        elif cci>200:filters.append(("CCI شرائي",-6,"fail",f"{cci:.0f}"));total-=6
    wr=safe_val(curr.get('Williams_R'))
    if wr!=0:
        if wr<-80:filters.append(("Williams بيعي",4,"pass",f"{wr:.0f}"));total+=4
        elif wr>-20:filters.append(("Williams شرائي",-4,"fail",f"{wr:.0f}"));total-=4
    roc=safe_val(curr.get('ROC'))
    if roc!=0:
        if roc>5:filters.append(("زخم+",5,"pass",f"{roc:.1f}%"));total+=5
        elif roc<-5:filters.append(("زخم-",-5,"fail",f"{roc:.1f}%"));total-=5
    bbu=safe_val(curr.get('BB_Upper'));bbl=safe_val(curr.get('BB_Lower'))
    if bbu>0 and bbl>0:
        if price<=bbl:filters.append(("BB سفلي",6,"pass",""));total+=6
        elif price>=bbu:filters.append(("BB علوي",-6,"fail",""));total-=6
    atr=safe_val(curr.get('ATR'))
    if atr>0 and price>0:
        ap=(atr/price)*100
        if ap>3:filters.append(("تذبذب↑",-3,"warn",f"{ap:.1f}%"));total-=3
        elif ap<0.5:filters.append(("تذبذب↓",-2,"warn",f"{ap:.1f}%"));total-=2
        else:filters.append(("تذبذب✓",3,"pass",f"{ap:.1f}%"));total+=3
    mfi=safe_val(curr.get('MFI'))
    if mfi>0:
        if mfi<20:filters.append(("MFI بيعي",5,"pass",f"{mfi:.0f}"));total+=5
        elif mfi>80:filters.append(("MFI شرائي",-5,"fail",f"{mfi:.0f}"));total-=5
    if 'OBV' in df.columns and len(df)>5:
        try:
            on=safe_val(curr.get('OBV'));o5=safe_val(df.iloc[-5].get('OBV'));p5=safe_val(df.iloc[-5]['Close'])
            if on>o5 and price>p5:filters.append(("OBV+",4,"pass",""));total+=4
            elif on<o5 and price<p5:filters.append(("OBV-",-4,"fail",""));total-=4
        except:pass
    if len(df)>2:
        try:
            co=safe_val(curr.get('Open'));cc=safe_val(curr['Close']);po=safe_val(prev.get('Open'));pc=safe_val(prev['Close'])
            if pc<po and cc>co and cc>po and co<pc:filters.append(("ابتلاع↑",7,"pass",""));total+=7
            elif pc>po and cc<co and cc<po and co>pc:filters.append(("ابتلاع↓",-7,"fail",""));total-=7
        except:pass
    if len(df)>20:
        try:
            rh=df['High'].tail(20).max();rl=df['Low'].tail(20).min();rng=rh-rl
            if rng>0:
                pos=(price-rl)/rng
                if pos<0.15:filters.append(("قرب دعم",6,"pass",f"{pos*100:.0f}%"));total+=6
                elif pos>0.85:filters.append(("قرب مقاومة",-6,"fail",f"{pos*100:.0f}%"));total-=6
        except:pass
    return total,filters,curr

def get_fundamental_score(info):
    score=0;details=[]
    if not info or not isinstance(info,dict):return 0,[("لا بيانات",0,"warn","")]
    pe=info.get('trailingPE')or info.get('forwardPE')
    if pe:
        pe=float(pe)
        if 5<pe<20:score+=5;details.append(("P/E✓",5,"pass",f"{pe:.1f}"))
        elif pe>40:score-=3;details.append(("P/E↑",-3,"fail",f"{pe:.1f}"))
    margin=info.get('profitMargins')
    if margin:
        mp=float(margin)*100
        if mp>20:score+=4;details.append(("هامش++",4,"pass",f"{mp:.1f}%"))
        elif mp>10:score+=2;details.append(("هامش+",2,"pass",f"{mp:.1f}%"))
        elif mp<0:score-=4;details.append(("خسارة",-4,"fail",f"{mp:.1f}%"))
    growth=info.get('revenueGrowth')
    if growth:
        gp=float(growth)*100
        if gp>20:score+=4;details.append(("نمو++",4,"pass",f"{gp:.1f}%"))
        elif gp>5:score+=2;details.append(("نمو+",2,"pass",f"{gp:.1f}%"))
        elif gp<-5:score-=3;details.append(("تراجع",-3,"fail",f"{gp:.1f}%"))
    de=info.get('debtToEquity')
    if de:
        de=float(de)
        if de<50:score+=3;details.append(("ديون↓",3,"pass",f"{de:.0f}"))
        elif de>200:score-=3;details.append(("ديون↑",-3,"fail",f"{de:.0f}"))
    if not details:details.append(("لا بيانات",0,"warn",""))
    return score,details

def get_news_score(ai_client,ticker,name):
    _,news_data,_=unified_search(f"{name} {ticker} financial news",max_results=5)
    if not news_data and not ai_client:return 0,[("أخبار غير متاحة",0,"warn","")]
    nc=""
    if news_data:nc="\n".join([f"- [{r.get('date','')}] {r.get('title','')}: {r.get('body','')[:150]}" for r in news_data[:5]])
    if not ai_client:
        pw=['surge','rise','gain','bull','up','high','record','growth','صعود','ارتفاع']
        nw=['drop','fall','crash','bear','down','low','loss','decline','هبوط','انخفاض']
        t=nc.lower();p=sum(1 for w in pw if w in t);n=sum(1 for w in nw if w in t)
        sc=min(max((p-n)*3,-10),10);st_t="pass" if sc>0 else("fail" if sc<0 else "warn")
        d=[("أخبار",sc,st_t,f"+{p}/-{n}")]
        for r in news_data[:2]:d.append((f"📰 {r.get('title','')[:50]}",0,"warn",""))
        return sc,d
    try:
        resp=ai_client.chat_completion(messages=[{"role":"system","content":"محلل أخبار.JSON فقط."},{"role":"user","content":f'حلل أخبار {name}({ticker}):\n{nc}\nJSON:{{"news_sentiment":"إيجابي/سلبي/محايد","score":-10 إلى 10,"key_events":[""],"impact":""}}'}],max_tokens=250)
        txt=resp.choices[0].message.content.strip()
        if "```" in txt:
            for p in txt.split("```"):
                p=p.strip()
                if p.startswith("json"):p=p[4:].strip()
                if p.startswith("{"):txt=p;break
        data=json.loads(txt);ns=int(data.get('score',0));st_t="pass" if ns>0 else("fail" if ns<0 else "warn")
        d=[(f"أخبار:{data.get('news_sentiment','محايد')}",ns,st_t,data.get('impact',''))]
        for ev in data.get('key_events',[])[:3]:d.append((f"📰 {ev}",0,"warn",""))
        return ns,d
    except:return 0,[("فشل الأخبار",0,"warn","")]

def get_ai_final_decision(ai_client,ticker,name,tech,fund,news,filters,price,hint):
    if not ai_client:return None
    mr,_,_=unified_search(f"{name} {ticker} price forecast {datetime.now().strftime('%Y-%m')}",max_results=3)
    mc=""
    if mr:mc="\nحديث:\n"+"\n".join([f"- {r.get('title','')}: {r.get('body','')[:100]}" for r in mr[:3]])
    tf=" | ".join([f"{f[0]}({f[1]:+d})" for f in filters[:8]])
    try:
        resp=ai_client.chat_completion(messages=[{"role":"system","content":"خبير تداول.JSON فقط."},{"role":"user","content":f'قرار:{name}({ticker}) سعر:{price} فني:{tech} أساسي:{fund} أخبار:{news} اتجاه:{"↑" if hint>0 else "↓" if hint<0 else "—"} فلاتر:{tf}{mc}\nJSON:{{"decision":"شراء قوي/شراء/بيع قوي/بيع/تجنب","confidence":0-100,"reasoning":"بالعربية","risk":"منخفض/متوسط/عالي","ai_score":-15 إلى 15}}'}],max_tokens=300)
        txt=resp.choices[0].message.content.strip()
        if "```" in txt:
            for p in txt.split("```"):
                p=p.strip()
                if p.startswith("json"):p=p[4:].strip()
                if p.startswith("{"):txt=p;break
        return json.loads(txt)
    except:return None

def calc_targets(curr,score):
    price=safe_val(curr['Close']);atr=safe_val(curr.get('ATR'))
    if atr==0:atr=price*0.015
    f=1 if score>0 else -1;sl=price-(2*atr*f);tp1=price+(1.5*atr*f);tp2=price+(3*atr*f);tp3=price+(5*atr*f)
    risk=abs(price-sl);rr=abs(tp2-price)/risk if risk>0 else 0
    return{'sl':sl,'tp1':tp1,'tp2':tp2,'tp3':tp3,'rr':rr}

def final_signal(c):
    if c>=40:return"شراء قوي","bg-strong-buy"
    elif c>=20:return"شراء","bg-buy"
    elif c<=-40:return"بيع قوي","bg-strong-sell"
    elif c<=-20:return"بيع","bg-sell"
    return"محايد","bg-neutral"

def build_filters_text(tf,ts,fd,fs,nd,ns,ais,ar,ac):
    l=[f"═ فني({ts:+d}) ═"]
    for f in tf:i="✅" if f[2]=="pass" else("❌" if f[2]=="fail" else "⚠️");l.append(f"{i}{f[0]}({f[1]:+d})-{f[3]}")
    l.append(f"\n═ أساسي({fs:+d}) ═")
    for f in fd:i="✅" if f[2]=="pass" else("❌" if f[2]=="fail" else "⚠️");l.append(f"{i}{f[0]}({f[1]:+d})-{f[3]}")
    l.append(f"\n═ أخبار({ns:+d}) ═")
    for f in nd:i="✅" if f[2]=="pass" else("❌" if f[2]=="fail" else "⚠️");l.append(f"{i}{f[0]}({f[1]:+d})-{f[3]}")
    l.append(f"\n═ AI({ais:+d}) ═");l.append(f"🤖{ar}");l.append(f"📊ثقة:{ac}%")
    return"\n".join(l)

def full_analysis(ticker,name,tf_key,ai_client,require_strong=False):
    df,info=fetch_data(ticker,tf_key)
    if df is None or len(df)<=15:return None
    df=calculate_indicators(df);tech_score,tech_filters,curr=apply_all_filters(df,info)
    fund_score,fund_details=get_fundamental_score(info);news_score,news_details=get_news_score(ai_client,ticker,name)
    pre_total=tech_score+fund_score+news_score
    ai_dec=get_ai_final_decision(ai_client,ticker,name,tech_score,fund_score,news_score,tech_filters,safe_val(curr['Close']),pre_total)
    ai_score=0;ai_reasoning="";ai_confidence=0;ai_risk="متوسط"
    if ai_dec and isinstance(ai_dec,dict):
        ai_score=int(ai_dec.get('ai_score',0));ai_reasoning=ai_dec.get('reasoning','');ai_confidence=int(ai_dec.get('confidence',0));ai_risk=ai_dec.get('risk','متوسط')
        if require_strong:
            if ai_confidence<70 or ai_dec.get('decision','تجنب')=='تجنب':return None
    ft=pre_total+ai_score
    if require_strong and abs(ft)<20:return None
    d="buy" if ft>0 else "sell";tgts=calc_targets(curr,ft);price=safe_val(curr['Close']);sl,sc=final_signal(ft)
    ftxt=build_filters_text(tech_filters,tech_score,fund_details,fund_score,news_details,news_score,ai_score,ai_reasoning,ai_confidence)
    return{'ticker':ticker,'name':name,'price':price,'direction':d,'signal':sl,'signal_class':sc,'total_score':ft,'tech_score':tech_score,'fund_score':fund_score,'news_score':news_score,'ai_score':ai_score,'ai_reasoning':ai_reasoning,'ai_confidence':ai_confidence,'ai_risk':ai_risk,'tech_filters':tech_filters,'fund_details':fund_details,'news_details':news_details,'filters_text':ftxt,'targets':tgts,'timeframe':tf_key,'curr':curr}

def smart_update_signal(sr):
    ticker=sr['ticker'];entry=float(sr.get('entry_price',0)or 0);tp1=float(sr.get('tp1',0)or 0);tp2=float(sr.get('tp2',0)or 0);sl=float(sr.get('sl',0)or 0);is_buy=sr.get('direction','buy')=='buy';ets=sr.get('timestamp','');stf=sr.get('timeframe','4 ساعات');tc=TRACKING_INTERVALS.get(stf,{"interval":"1h","period":"1mo"})
    try:
        hist=yf.Ticker(ticker).history(period=tc["period"],interval=tc["interval"])
        if hist.empty:return None
        if hist.index.tz is not None:hist.index=hist.index.tz_localize(None)
        try:et=pd.to_datetime(ets)
        except:et=hist.index[0]
        candles=hist[hist.index>=et]
        if candles.empty:candles=hist.tail(50)
        cp=float(hist['Close'].iloc[-1]);hs='active';ht='';hp=0;t1h=False
        for idx,c in candles.iterrows():
            ch=float(c['High']);cl=float(c['Low']);ct=str(idx)
            if is_buy:
                if cl<=sl and ch>=tp2:
                    co=float(c['Open']);hs='tp_hit' if abs(co-tp2)<abs(co-sl) else 'sl_hit';hp=tp2 if hs=='tp_hit' else sl;ht=ct;break
                elif cl<=sl:hs='sl_hit';ht=ct;hp=sl;break
                elif ch>=tp2:hs='tp_hit';ht=ct;hp=tp2;break
                if ch>=tp1:t1h=True
            else:
                if ch>=sl and cl<=tp2:
                    co=float(c['Open']);hs='tp_hit' if abs(co-tp2)<abs(co-sl) else 'sl_hit';hp=tp2 if hs=='tp_hit' else sl;ht=ct;break
                elif ch>=sl:hs='sl_hit';ht=ct;hp=sl;break
                elif cl<=tp2:hs='tp_hit';ht=ct;hp=tp2;break
                if cl<=tp1:t1h=True
        if hs=='tp_hit':prog=100.0;pnl=((tp2-entry)/entry*100)if is_buy else((entry-tp2)/entry*100)
        elif hs=='sl_hit':prog=0.0;pnl=((sl-entry)/entry*100)if is_buy else((entry-sl)/entry*100)
        else:
            if is_buy:td=tp2-entry;cd=cp-entry;pnl=((cp-entry)/entry*100)
            else:td=entry-tp2;cd=entry-cp;pnl=((entry-cp)/entry*100)
            prog=(cd/td*100)if td!=0 else 0;prog=max(0,min(100,prog))
            if t1h and prog<50:prog=50
        return{'current_price':cp,'status':hs,'progress':prog,'pnl':pnl,'hit_time':ht,'hit_price':hp}
    except:return None

def background_scan(assets_dict,scan_tf,ai_token):
    # استخدام Mistral Client في الخلفية
    aic = MistralClient(ai_token) if ai_token else None
    
    total=len(assets_dict);found=0;scanned=0;db.set_scan_status(True,0,total,0,0,'بدء...')
    
    for name,tick in assets_dict.items():
        scanned+=1;db.set_scan_status(True,(scanned/total)*100,total,scanned,found,name)
        try:
            r=full_analysis(tick,name,scan_tf,aic,require_strong=True)
            if r and r['price']>0:
                if db.add_signal(str(tick),str(name),r['direction'],float(r['price']),float(r['targets']['tp1']),float(r['targets']['tp2']),float(r['targets']['tp3']),float(r['targets']['sl']),float(abs(r['total_score'])),str(scan_tf),float(r['tech_score']),float(r['fund_score']),float(r['news_score']),float(r['ai_score']),str(r['filters_text']),str(r['ai_reasoning'])):found+=1
                
                # إرسال الإشارة فوراً لمدير المحفظة (Paper Trading) لاتخاذ قرار
                if aic:
                    process_single_paper_trade(r, aic)
                    
        except Exception as e:print(f"Scan err {name}:{e}");continue
        
        # الانتظار لمدة دقيقة (60 ثانية) لتجنب Rate Limit الخاص بـ Mistral
        time.sleep(60)
        
    db.set_scan_status(False,100,total,scanned,found,'اكتمل')

# ============================================================
# MAIN UI
# ============================================================
st.title("ProTrade Elite 5.0 📊")
required=['init_db','add_signal','get_active_signals','get_closed_signals','update_signal_status','save_analysis','set_scan_status','get_scan_status','delete_all_active']
missing=[f for f in required if not hasattr(db,f)]
if missing:st.error(f"⚠️ db.py ناقص:{','.join(missing)}");st.stop()

with st.expander("☰ القائمة",expanded=False):
    n1,n2,n3,n4,n5=st.columns(5)
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

# ============================================================
# VIEW: Signals
# ============================================================
if st.session_state.current_view=="signals":
    st.header("📋 التوصيات الذكية")
    scan_st=db.get_scan_status()
    if scan_st and isinstance(scan_st,dict):
        ir=scan_st.get('is_running',False);sf=int(scan_st.get('found_signals',0)or 0);st_=int(scan_st.get('total_assets',0)or 0);ss=int(scan_st.get('scanned_assets',0)or 0);sp=float(scan_st.get('progress',0)or 0);sc=scan_st.get('current_asset','')
        if ir:
            st.markdown(f'<div class="scan-banner"><span>🔄 {sc} ({ss}/{st_})</span><span>وجد:{sf}</span></div>',unsafe_allow_html=True);st.progress(sp/100);time.sleep(3);st.rerun()
        elif st.session_state.get('scan_running',False):
            st.session_state.scan_running=False;st.session_state.scan_complete=True;st.session_state.scan_results=sf
    if st.session_state.get('scan_complete',False):
        nr=st.session_state.get('scan_results',0)
        if nr>0:st.markdown(f'<div class="scan-done-banner">✅ {nr} إشارة.</div>',unsafe_allow_html=True)
        else:st.markdown('<div class="scan-done-zero">⚠️ لا إشارات</div>',unsafe_allow_html=True)
        st.session_state.scan_complete=False

    with st.expander("⚙️ إعدادات",expanded=True):
        sc1,sc2,sc3=st.columns(3)
        with sc1:scan_types=st.multiselect("أصول",["فوركس","عملات رقمية","أسهم","الكل"],default=["الكل"])
        with sc2:scan_tf=st.selectbox("إطار",list(TIMEFRAMES.keys()),index=2)
        with sc3:specific=st.text_input("محدد",placeholder="EURUSD=X")
    ac1,ac2,ac3,ac4=st.columns(4)
    with ac1:scan_btn=st.button("🔍 مسح",type="primary",use_container_width=True)
    with ac2:update_btn=st.button("🔄 تحديث",use_container_width=True)
    with ac3:clear_btn=st.button("🗑️ حذف",use_container_width=True)
    with ac4:refresh_btn=st.button("♻️",use_container_width=True)
    if refresh_btn:st.rerun()
    if clear_btn:db.delete_all_active();st.success("✅");time.sleep(1);st.rerun()
    if scan_btn:
        cs=db.get_scan_status()
        if cs and cs.get('is_running',False):st.warning("⚠️ يعمل!")
        else:
            assets={}
            if specific.strip():assets[specific.strip()]=specific.strip()
            else:
                if "الكل" in scan_types:assets.update(FOREX_PAIRS);assets.update(CRYPTO_PAIRS);assets.update(STOCKS)
                else:
                    if "فوركس" in scan_types:assets.update(FOREX_PAIRS)
                    if "عملات رقمية" in scan_types:assets.update(CRYPTO_PAIRS)
                    if "أسهم" in scan_types:assets.update(STOCKS)
            if not assets:st.warning("اختر أصول")
            else:
                st.session_state.scan_running=True;threading.Thread(target=background_scan,args=(assets,scan_tf,st.secrets.get("MISTRAL_API_KEY","")),daemon=True).start();st.success(f"🚀 {len(assets)} أصل");time.sleep(2);st.rerun()
    if update_btn:
        active=db.get_active_signals(); paper_updates = update_paper_positions_status()
        if active:
            uc=0;prog=st.progress(0);stat=st.empty()
            for i,sr in enumerate(active):
                prog.progress((i+1)/len(active));stat.text(f"🔄 {sr.get('asset_name','')} ({i+1}/{len(active)})")
                r=smart_update_signal(sr)
                if r:db.update_signal_status(sr['id'],r['current_price'],r['status'],r['progress'],r['pnl'],r.get('hit_time',''),r.get('hit_price',0));uc+=1
            prog.empty();stat.empty(); msg = f"✅ تم تحديث {uc} توصية"
            if paper_updates > 0: msg += f" و {paper_updates} صفقة محفظة"
            st.success(msg);time.sleep(1);st.rerun()
        else:
            if paper_updates > 0: st.success(f"✅ تم تحديث {paper_updates} صفقة محفظة");time.sleep(1);st.rerun()
            else: st.warning("لا توصيات")

    st.subheader("📊 النشطة")
    try:sigs=db.get_active_signals()
    except:sigs=[]
    if sigs and len(sigs)>0:
        st.success(f"📊 {len(sigs)}")
        for sr in sigs:
            try:
                ib=sr.get('direction','buy')=='buy';clr="#00ff88" if ib else "#ff4444";dt="شراء🟢" if ib else "بيع🔴"
                sp=float(sr.get('progress',0)or 0);spnl=float(sr.get('pnl_pct',0)or 0)
                sc=float(sr.get('current_price',0)or sr.get('entry_price',0)or 0);se=float(sr.get('entry_price',0)or 0)
                s1=float(sr.get('tp1',0)or 0);s2=float(sr.get('tp2',0)or 0);s3=float(sr.get('tp3',0)or 0);ssl=float(sr.get('sl',0)or 0)
                sn=sr.get('asset_name','?');stk=sr.get('ticker','');stf=sr.get('timeframe','');sstr=float(sr.get('strength',0)or 0)
                ts=float(sr.get('technical_score',0)or 0);fs=float(sr.get('fundamental_score',0)or 0);ns=float(sr.get('news_score',0)or 0);ais=float(sr.get('ai_score',0)or 0)
                st.markdown(f"""<div class="rec-card" style="border-left:5px solid {clr};"><div style="display:flex;justify-content:space-between;"><h3 style="margin:0;">{sn}<span style="font-size:0.7em;color:#888;">{stk}|{stf}</span></h3><div><h3 style="color:{clr};margin:0;">{dt}</h3><span style="font-size:0.8em;color:#aaa;">قوة:{sstr:.0f}</span></div></div><div style="font-size:13px;margin:10px 0;display:flex;justify-content:space-between;flex-wrap:wrap;"><span>🏁{se:.4f}</span><span>🏷️{sc:.4f}</span><span>🎯1:{s1:.4f}</span><span>🎯2:{s2:.4f}</span><span>🎯3:{s3:.4f}</span><span>🛑{ssl:.4f}</span></div><div style="display:flex;gap:10px;margin:8px 0;font-size:12px;"><span style="color:#00bcd4;">فني:{ts:+.0f}</span><span style="color:#ff9800;">أساسي:{fs:+.0f}</span><span style="color:#e91e63;">أخبار:{ns:+.0f}</span><span style="color:#9c27b0;">AI:{ais:+.0f}</span></div><div style="background:#111;height:10px;border-radius:5px;"><div style="width:{max(0,min(100,sp))}%;background:{clr};height:100%;border-radius:5px;"></div></div><div style="text-align:right;font-size:12px;color:#ccc;">تقدم:{sp:.1f}%|ربح:<span style="color:{clr}">{spnl:.2f}%</span></div></div>""",unsafe_allow_html=True)
                with st.expander(f"📋 {sn}"):
                    fd=sr.get('filters_detail','');ar=sr.get('ai_reasoning','')
                    if fd:st.text(fd)
                    if ar:st.info(f"🤖 {ar}")
            except Exception as e:st.error(f"خطأ:{e}")
    else:st.info("📭 اضغط مسح شامل")
    st.markdown("---");st.subheader("📜 المنتهية")
    try:closed=db.get_closed_signals()
    except:closed=[]
    if closed:
        hd=[]
        for cr in closed:
            try:hd.append({"التاريخ":cr.get('timestamp',''),"الأصل":cr.get('asset_name',''),"الاتجاه":"شراء" if cr.get('direction')=='buy' else "بيع","النتيجة":"✅" if cr.get('status')=='tp_hit' else "❌","الربح%":round(float(cr.get('pnl_pct',0)or 0),2)})
            except:continue
        if hd:st.dataframe(pd.DataFrame(hd),use_container_width=True,hide_index=True)
    else:st.info("لا منتهية")

# ============================================================
# VIEW: Paper Portfolio
# ============================================================
elif st.session_state.current_view=="paper":
    st.header("💼 مدير المحفظة الآلي (Paper Trading)")
    balance, positions, logs = get_paper_portfolio()
    invested = 0; open_positions_count = 0
    for k, p in positions.items():
        if p.get('status') == 'OPEN': invested += p.get('amount', 0); open_positions_count += 1
    equity = balance + invested
    col1, col2, col3 = st.columns(3)
    col1.markdown(f'<div class="portfolio-card"><h3>💵 السيولة المتاحة</h3><h2 style="color:#34d399">{balance:.2f} $</h2></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="portfolio-card"><h3>🔒 المبلغ المستثمر</h3><h2 style="color:#60a5fa">{invested:.2f} $</h2></div>', unsafe_allow_html=True)
    col3.markdown(f'<div class="portfolio-card"><h3>📈 إجمالي القيمة</h3><h2 style="color:#facc15">{equity:.2f} $</h2></div>', unsafe_allow_html=True)
    st.subheader("🤖 يوميات المدير الذكي")
    with st.container(height=300):
        for log in logs: st.markdown(f'<div class="manager-log"><b>[{log.get("timestamp")}]</b>: {log.get("message")}</div>', unsafe_allow_html=True)
    st.subheader(f"📊 الصفقات المفتوحة ({open_positions_count})")
    if open_positions_count > 0:
        for k, p in positions.items():
            if p.get('status') == 'OPEN':
                color = "#34d399" if p['type'] == 'buy' else "#f87171"
                st.markdown(f"""<div class="trade-row" style="border-left: 5px solid {color}"><div><strong>{p['name']} ({p['ticker']})</strong><br><span style="font-size:0.8em; color:#aaa">{p['open_time']}</span></div><div><span style="color:{color}; font-weight:bold">{p['type'].upper()}</span><br>Entry: {p['entry_price']}</div><div>Invest: {p['amount']}$<br>TP: {p['tp']} | SL: {p['sl']}</div></div>""", unsafe_allow_html=True)
                with st.expander(f"📝 سبب الدخول في {p['ticker']}"): st.write(p.get('reason', 'لا يوجد سبب مسجل'))
    else: st.info("لا توجد صفقات مفتوحة حالياً. قم بعمل مسح (Scan) ليقوم المدير بالبحث عن فرص.")
    st.markdown("---"); st.subheader("📜 سجل الصفقات المغلقة")
    closed_trades = []
    for k, p in positions.items():
        if p.get('status') == 'CLOSED': closed_trades.append({"التاريخ": p.get('close_time'), "الرمز": p.get('ticker'), "النوع": p.get('type'), "النتيجة": p.get('outcome'), "الربح/الخسارة": round(p.get('pnl', 0), 2)})
    if closed_trades: st.dataframe(pd.DataFrame(closed_trades), use_container_width=True)
    else: st.caption("لم يتم إغلاق أي صفقة بعد.")

# ============================================================
# VIEW: Analysis
# ============================================================
elif st.session_state.current_view=="analysis":
    st.header("📉 التحليل")
    a1,a2,a3,a4=st.columns(4)
    with a1:ac=st.selectbox("نوع",["فوركس","عملات رقمية","أسهم"])
    with a2:
        if ac=="فوركس":sel=st.selectbox("أصل",list(FOREX_PAIRS.keys()));ticker=FOREX_PAIRS[sel]
        elif ac=="عملات رقمية":sel=st.selectbox("أصل",list(CRYPTO_PAIRS.keys()));ticker=CRYPTO_PAIRS[sel]
        else:sel=st.selectbox("أصل",list(STOCKS.keys()));ticker=STOCKS[sel]
    with a3:tf_l=st.selectbox("إطار",list(TIMEFRAMES.keys()),index=2)
    with a4:abtn=st.button("🚀 تحليل",type="primary",use_container_width=True)
    if abtn:
        with st.spinner("تحليل..."):
            result=full_analysis(ticker,sel,tf_l,client,require_strong=False)
            if result:
                st.session_state.analysis_result=result
                try:db.save_analysis(ticker,tf_l,result['signal'],result['signal_class'],result['total_score'],result['price'],result['targets'],{'final_decision':result['signal'],'risk_level':result['ai_risk']},result['tech_score'],result['fund_score'],result['news_score'],result['ai_score'],result['filters_text'],result['ai_reasoning'])
                except:pass
            else:st.error("فشل")
    if 'analysis_result' in st.session_state:
        r=st.session_state.analysis_result
        st.markdown(f'<div class="main-signal {r["signal_class"]}">{r["signal"]}({r["total_score"]:.1f})<div style="font-size:16px;opacity:0.8;">{r["ticker"]}|{r["price"]:.4f}</div></div>',unsafe_allow_html=True)
        mc1,mc2,mc3,mc4=st.columns(4);mc1.metric("📐فني",f"{r['tech_score']:+d}");mc2.metric("📊أساسي",f"{r['fund_score']:+d}");mc3.metric("📰أخبار",f"{r['news_score']:+d}");mc4.metric("🤖AI",f"{r['ai_score']:+d}")
        m1,m2,m3,m4,m5=st.columns(5);m1.metric("TP1",f"{r['targets']['tp1']:.4f}");m2.metric("TP2",f"{r['targets']['tp2']:.4f}");m3.metric("TP3",f"{r['targets']['tp3']:.4f}");m4.metric("SL",f"{r['targets']['sl']:.4f}",delta_color="inverse");m5.metric("R:R",f"1:{r['targets']['rr']:.1f}")
        tab1,tab2,tab3,tab4,tab5=st.tabs(["📈رسم","📐فلاتر","📊أساسي","📰أخبار","🤖AI"])
        with tab1:
            tv_s=to_tv_symbol(r['ticker']);tv_i=TV_INTERVALS.get(r['timeframe'],'D')
            st.components.v1.html(f'<div style="height:500px;width:100%"><div id="tv"></div><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"width":"100%","height":"500","symbol":"{tv_s}","interval":"{tv_i}","theme":"dark","style":"1","locale":"ar","container_id":"tv"}});</script></div>',height=520)
        with tab2:
            for f in r['tech_filters']:i="✅" if f[2]=="pass" else("❌" if f[2]=="fail" else "⚠️");st.markdown(f"{i}**{f[0]}**({f[1]:+d})—{f[3]}")
        with tab3:
            for f in r['fund_details']:i="✅" if f[2]=="pass" else("❌" if f[2]=="fail" else "⚠️");st.markdown(f"{i}**{f[0]}**({f[1]:+d})—{f[3]}")
        with tab4:
            for f in r['news_details']:i="✅" if f[2]=="pass" else("❌" if f[2]=="fail" else "⚠️");st.markdown(f"{i}**{f[0]}**({f[1]:+d})—{f[3]}")
        with tab5:
            if r['ai_reasoning']:st.info(f"🤖{r['ai_reasoning']}");st.write(f"ثقة:**{r['ai_confidence']}%**");risk=r.get('ai_risk','متوسط');(st.error if risk=="عالي" else st.success if risk=="منخفض" else st.warning)(f"مخاطرة:{risk}")
            else:st.warning("AI غير مفعل")

# ============================================================
# VIEW: Chart
# ============================================================
elif st.session_state.current_view=="chart":
    if not st.session_state.get('chart_fullscreen'):
        st.header("📊 الشارت")
        tc1,tc2,tc3,tc4=st.columns([2,2,1,1])
        with tc1:cc=st.selectbox("فئة",list(TV_SYMBOLS.keys()),key="cc")
        with tc2:sic=TV_SYMBOLS[cc];ca=st.selectbox("أصل",list(sic.keys()),key="ca");sel_sym=sic[ca]
        with tc3:ctf=st.selectbox("إطار",["1","5","15","30","60","240","D","W","M"],index=5,format_func=lambda x:{"1":"1د","5":"5د","15":"15د","30":"30د","60":"1س","240":"4س","D":"يومي","W":"أسبوعي","M":"شهري"}.get(x,x),key="ct")
        with tc4:
            if st.button("🔲",use_container_width=True):st.session_state.chart_fullscreen=True;st.session_state.chart_symbol=sel_sym;st.session_state.chart_interval=ctf;st.rerun()
        c1,c2=st.columns([3,1])
        with c1:cs=st.text_input("رمز",placeholder="BINANCE:BTCUSDT",key="cs")
        with c2:
            if cs.strip():sel_sym=cs.strip();st.success(f"✅{sel_sym}")
        st.components.v1.html(f'<div id="tva" style="height:650px;width:100%;"></div><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"width":"100%","height":650,"symbol":"{sel_sym}","interval":"{ctf}","timezone":"Etc/UTC","theme":"dark","style":"1","locale":"ar","toolbar_bg":"#1a1a2e","enable_publishing":false,"hide_side_toolbar":false,"allow_symbol_change":true,"save_image":true,"studies":["MAExp@tv-basicstudies","RSI@tv-basicstudies","MACD@tv-basicstudies"],"show_popup_button":true,"popup_width":"1000","popup_height":"650","container_id":"tva","withdateranges":true,"details":true,"hotlist":true,"calendar":true,"watchlist":true}});</script>',height=670)
    else:
        if st.button("✕",key="ef"):st.session_state.chart_fullscreen=False;st.rerun()
        sym=st.session_state.get('chart_symbol','FX:EURUSD');intv=st.session_state.get('chart_interval','D')
        st.markdown('<style>.main .block-container{padding:0!important;max-width:100%!important;}</style>',unsafe_allow_html=True)
        st.components.v1.html(f'<div id="tvf" style="height:95vh;width:100%;"></div><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"width":"100%","height":"95%","symbol":"{sym}","interval":"{intv}","timezone":"Etc/UTC","theme":"dark","style":"1","locale":"ar","toolbar_bg":"#1a1a2e","enable_publishing":false,"hide_side_toolbar":false,"allow_symbol_change":true,"save_image":true,"studies":["MAExp@tv-basicstudies","RSI@tv-basicstudies","MACD@tv-basicstudies","BB@tv-basicstudies"],"show_popup_button":true,"popup_width":"1200","popup_height":"800","container_id":"tvf","withdateranges":true,"details":true,"hotlist":true,"calendar":true,"watchlist":true}});</script>',height=900)

# ============================================================
# VIEW: Chat
# ============================================================
elif st.session_state.current_view=="chat":
    st.header("🤖 المستشار المالي الذكي")
    engines = []
    if SERPER_KEY: engines.append("✅ Google (Serper)")
    if TAVILY_KEY: engines.append("✅ Tavily AI")
    if HAS_DDG: engines.append("✅ DuckDuckGo")
    engines.append("✅ Yahoo Finance (أسعار)")
    if client: engines.append("✅ Mistral AI") # التأكيد على وجود ميسترال
    
    st.caption(f"🔍 محركات البحث: {' | '.join(engines)}")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):st.markdown(msg["content"],unsafe_allow_html=True)
    ui=st.chat_input("اسأل عن أي سعر أو موضوع...")
    if ui:
        st.session_state.messages.append({"role":"user","content":ui})
        with st.chat_message("user"):st.markdown(ui)
        with st.chat_message("assistant"):
            with st.spinner("🔍 بحث..."):
                ctx,sr,nr,lp,su=build_search_context(ui)
            ph=format_live_prices_html(lp)
            if ph:st.markdown(ph,unsafe_allow_html=True)
            if client:
                try:
                    sp=f"""أنت مستشار مالي خبير. أجب بالعربية فقط.
الآن: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC
قواعد: 1.عربية فقط 2.ممنوع ``` 3.استخدم البيانات المرفقة 4.دقة في الأرقام 5.حذر من المخاطر 6.لا تقل "لا أستطيع"
{ctx}"""
                    ms=[{"role":"system","content":sp}]
                    for m in st.session_state.messages[-6:]:ms.append({"role":m["role"],"content":m["content"]})
                    resp=client.chat_completion(messages=ms,max_tokens=800,stream=False)
                    rt=resp.choices[0].message.content
                    if "```" in rt:
                        cl=[];ic=False
                        for ln in rt.split('\n'):
                            if '```' in ln:ic=not ic;continue
                            if not ic:cl.append(ln)
                        rt='\n'.join(cl)
                    rt=rt.replace('`','')
                    sh=format_sources_html(sr,nr,su)
                    st.markdown(rt,unsafe_allow_html=True)
                    if sh:st.markdown(sh,unsafe_allow_html=True)
                    st.session_state.messages.append({"role":"assistant","content":ph+"\n\n"+rt+"\n\n"+sh})
                except Exception as e:
                    fb=""
                    if lp: fb+="📊 **أسعار:**\n" + "".join([f"{'📈' if p['change']>=0 else '📉'} **{p['name']}**: {p['price']:,.2f}$ ({p['change_pct']:+.2f}%)\n" for p in lp])
                    if nr: fb+="\n📰 **أخبار:**\n" + "".join([f"- {r.get('title','')}\n" for r in nr[:3]])
                    if fb:st.markdown(fb);st.session_state.messages.append({"role":"assistant","content":ph+fb})
                    else:st.error(f"⚠️{e}")
            else:
                resp=""
                if lp: resp+="📊 **أسعار (Yahoo Finance):**\n\n" + "".join([f"{'📈' if p['change']>=0 else '📉'} **{p['name']}**: **{p['price']:,.2f}**$ | {p['change']:+,.2f} ({p['change_pct']:+.2f}%)\nأعلى:{p['high']:,.2f} أدنى:{p['low']:,.2f} افتتاح:{p['open']:,.2f}\n\n" for p in lp])
                if nr: resp+="📰 **أخبار:**\n" + "".join([f"- **{r.get('title','')}**\n  {r.get('body','')[:200]}\n\n" for r in nr[:5]])
                if sr: resp+="🔗 **معلومات:**\n" + "".join([f"- **{r.get('title','')}**\n  {r.get('body','')[:200]}\n\n" for r in sr[:3]])
                if not resp:resp="⚠️ لم أجد نتائج."
                sh=format_sources_html(sr,nr,su)
                st.markdown(resp,unsafe_allow_html=True)
                if sh:st.markdown(sh,unsafe_allow_html=True)
                st.session_state.messages.append({"role":"assistant","content":ph+"\n\n"+resp+"\n\n"+sh})

    if st.session_state.messages:
        if st.button("🗑️ مسح"):st.session_state.messages=[];st.rerun()