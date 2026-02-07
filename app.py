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

# إعادة تحميل db لضمان قراءة آخر نسخة
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

# تهيئة قاعدة البيانات
try:
    db.init_db()
except Exception as e:
    st.error(f"خطأ في قاعدة البيانات: {e}")

# CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        line-height: 1.6 !important;
    }
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
        display: none !important;
        visibility: hidden !important;
    }
    [data-testid="stToolbar"], footer, header[data-testid="stHeader"] {
        visibility: hidden !important;
    }
    .streamlit-expanderHeader {
        background-color: #111827;
        color: #00ff88;
        font-weight: bold;
        border: 1px solid #374151;
        border-radius: 8px;
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
    .stChatMessage {direction: rtl;}
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

init_session_state()

FOREX_PAIRS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "USD/CHF": "USDCHF=X", "Gold": "GC=F", "Oil": "CL=F", "AUD/USD": "AUDUSD=X"
}
CRYPTO_PAIRS = {
    "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "SOL/USD": "SOL-USD",
    "XRP/USD": "XRP-USD", "BNB/USD": "BNB-USD"
}
STOCKS = {
    "Apple": "AAPL", "Tesla": "TSLA", "NVIDIA": "NVDA", "Google": "GOOGL",
    "Amazon": "AMZN", "Microsoft": "MSFT"
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
    if ticker == "GC=F":
        return "COMEX:GC1!"
    if ticker == "CL=F":
        return "NYMEX:CL1!"
    return f"NASDAQ:{ticker}"

# ============================================================
# 3. الذكاء الاصطناعي
# ============================================================
client = None
try:
    token = st.secrets.get("HF_TOKEN", "")
    if token:
        client = InferenceClient(
            model="Qwen/Qwen2.5-72B-Instruct",
            token=token
        )
except Exception:
    client = None

# ============================================================
# 4. دوال التحليل
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
            df = stock.history(
                period=tf["period"],
                interval=tf["interval"],
                auto_adjust=True
            )
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

    for w in [10, 20, 50, 200]:
        try:
            df[f'EMA_{w}'] = ta.trend.ema_indicator(c, window=w)
        except Exception:
            pass
    try:
        macd_obj = ta.trend.MACD(c)
        df['MACD'] = macd_obj.macd()
        df['MACD_Signal'] = macd_obj.macd_signal()
        df['MACD_Hist'] = macd_obj.macd_diff()
    except Exception:
        pass
    try:
        df['RSI'] = ta.momentum.rsi(c, window=14)
    except Exception:
        pass
    try:
        stoch = ta.momentum.StochasticOscillator(h, low, c)
        df['Stoch_K'] = stoch.stoch()
        df['Stoch_D'] = stoch.stoch_signal()
    except Exception:
        pass
    try:
        bb = ta.volatility.BollingerBands(c, window=20)
        df['BB_Upper'] = bb.bollinger_hband()
        df['BB_Lower'] = bb.bollinger_lband()
    except Exception:
        pass
    try:
        df['ATR'] = ta.volatility.average_true_range(h, low, c)
    except Exception:
        pass
    try:
        adx_obj = ta.trend.ADXIndicator(h, low, c)
        df['ADX'] = adx_obj.adx()
        df['DI_plus'] = adx_obj.adx_pos()
        df['DI_minus'] = adx_obj.adx_neg()
    except Exception:
        pass
    try:
        df['PSAR'] = ta.trend.PSARIndicator(h, low, c).psar()
    except Exception:
        pass
    try:
        ich = ta.trend.IchimokuIndicator(h, low)
        df['Ich_A'] = ich.ichimoku_a()
        df['Ich_B'] = ich.ichimoku_b()
    except Exception:
        pass
    return df


def smart_technical_score(df):
    curr = df.iloc[-1]
    price = safe_val(curr['Close'])
    score = 0
    details = []

    ema50 = safe_val(curr.get('EMA_50'))
    ema200 = safe_val(curr.get('EMA_200'))
    if ema200 > 0:
        if price > ema200:
            score += 10
            details.append(("فوق EMA 200", "+10", "green"))
        else:
            score -= 10
            details.append(("تحت EMA 200", "-10", "red"))
    if ema50 > 0 and ema200 > 0:
        if ema50 > ema200:
            score += 5
            details.append(("الترند صاعد (ذهبي)", "+5", "green"))
        else:
            score -= 5
            details.append(("الترند هابط", "-5", "red"))

    rsi = safe_val(curr.get('RSI'))
    if rsi > 0:
        if rsi < 30:
            score += 8
            details.append((f"RSI تشبع بيعي ({rsi:.0f})", "+8", "green"))
        elif rsi > 70:
            score -= 8
            details.append((f"RSI تشبع شرائي ({rsi:.0f})", "-8", "red"))

    macd_hist = safe_val(curr.get('MACD_Hist'))
    if macd_hist > 0:
        score += 5
        details.append(("MACD إيجابي", "+5", "green"))
    else:
        score -= 5
        details.append(("MACD سلبي", "-5", "red"))

    adx = safe_val(curr.get('ADX'))
    if adx > 25:
        di_plus = safe_val(curr.get('DI_plus'))
        di_minus = safe_val(curr.get('DI_minus'))
        if di_plus > di_minus:
            score += 5
            details.append(("ADX ترند قوي صاعد", "+5", "green"))
        else:
            score -= 5
            details.append(("ADX ترند قوي هابط", "-5", "red"))

    psar = safe_val(curr.get('PSAR'))
    if psar > 0:
        if price > psar:
            score += 3
            details.append(("PSAR صعودي", "+3", "green"))
        else:
            score -= 3
            details.append(("PSAR هبوطي", "-3", "red"))

    icha = safe_val(curr.get('Ich_A'))
    ichb = safe_val(curr.get('Ich_B'))
    if icha > 0 and ichb > 0:
        if price > max(icha, ichb):
            score += 5
            details.append(("فوق سحابة إيشيموكو", "+5", "green"))
        elif price < min(icha, ichb):
            score -= 5
            details.append(("تحت سحابة إيشيموكو", "-5", "red"))

    return score, details, curr


def calc_targets(curr, t_score):
    price = safe_val(curr['Close'])
    atr = safe_val(curr.get('ATR'))
    if atr == 0:
        atr = price * 0.015
    is_buy = t_score > 0
    factor = 1 if is_buy else -1
    sl = price - (2 * atr * factor)
    tp1 = price + (1.5 * atr * factor)
    tp2 = price + (3 * atr * factor)
    tp3 = price + (5 * atr * factor)
    risk = abs(price - sl)
    rr = abs(tp2 - price) / risk if risk > 0 else 0
    return {'sl': sl, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'rr': rr}


def final_signal(t_score, f_score=0):
    combined = (t_score * 0.7) + (f_score * 0.3)
    if combined >= 25:
        return "شراء قوي", "bg-strong-buy", combined
    elif combined >= 10:
        return "شراء", "bg-buy", combined
    elif combined <= -25:
        return "بيع قوي", "bg-strong-sell", combined
    elif combined <= -10:
        return "بيع", "bg-sell", combined
    return "محايد", "bg-neutral", combined


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
# 5. التحقق من وجود دوال db
# ============================================================
st.title("ProTrade Elite 5.0 📊")

# التحقق من أن db يحتوي على الدوال المطلوبة
required_funcs = ['init_db', 'add_signal', 'get_active_signals',
                  'get_closed_signals', 'update_signal_status', 'save_analysis']
missing_funcs = [f for f in required_funcs if not hasattr(db, f)]
if missing_funcs:
    st.error(f"⚠️ ملف db.py لا يحتوي على الدوال: {', '.join(missing_funcs)}")
    st.info("تأكد من حفظ ملف db.py الجديد ورفعه بشكل صحيح")
    st.stop()

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

# ============================================================
# 6. صفحة التوصيات
# ============================================================
if st.session_state.current_view == "signals":
    st.header("📋 مركز التوصيات اليومية")

    btn_col1, btn_col2 = st.columns([1, 4])

    with btn_col1:
        scan_btn = st.button("🔍 مسح السوق الآن", type="primary", use_container_width=True)
        update_btn = st.button("🔄 تحديث الأسعار", use_container_width=True)

    if scan_btn:
        with st.spinner("جاري فحص السوق..."):
            count = 0
            failed = 0
            assets = {}
            assets.update(FOREX_PAIRS)
            assets.update(CRYPTO_PAIRS)
            assets.update(STOCKS)

            progress_bar = st.progress(0)
            total = len(assets)
            idx = 0

            for name, tick in assets.items():
                idx += 1
                progress_bar.progress(idx / total)
                try:
                    scan_df, _ = fetch_data(tick, "4 ساعات")
                    if scan_df is not None and len(scan_df) > 15:
                        scan_df = calculate_indicators(scan_df)
                        ts, td, curr = smart_technical_score(scan_df)
                        # خفض الحد الأدنى للقوة من 20 إلى 10
                        if abs(ts) >= 10:
                            tgts = calc_targets(curr, ts)
                            direction = "buy" if ts > 0 else "sell"
                            price_val = safe_val(curr['Close'])
                            if price_val > 0:
                                added = db.add_signal(
                                    str(tick),
                                    str(name),
                                    str(direction),
                                    float(price_val),
                                    float(tgts['tp1']),
                                    float(tgts['tp2']),
                                    float(tgts['sl']),
                                    float(ts)
                                )
                                if added:
                                    count += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                    continue

            progress_bar.empty()
            if count > 0:
                st.success(f"✅ تم إضافة {count} توصية جديدة")
            else:
                st.warning(f"لم يتم العثور على توصيات جديدة قوية. (فشل جلب بيانات {failed} أصل)")
            time.sleep(1)
            st.rerun()

    if update_btn:
        try:
            active_list = db.get_active_signals()
        except Exception:
            active_list = []

        updated_count = 0
        if active_list and len(active_list) > 0:
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
                                    total_dist = tp - entry
                                    curr_dist = curr_price - entry
                                    progress = (curr_dist / total_dist * 100) if total_dist != 0 else 0
                            else:
                                if curr_price <= tp:
                                    new_status = 'tp_hit'
                                    progress = 100.0
                                elif curr_price >= sl:
                                    new_status = 'sl_hit'
                                    progress = 0.0
                                else:
                                    total_dist = entry - tp
                                    curr_dist = entry - curr_price
                                    progress = (curr_dist / total_dist * 100) if total_dist != 0 else 0

                            progress = max(0.0, min(100.0, progress))
                            if is_buy:
                                pnl = ((curr_price - entry) / entry) * 100
                            else:
                                pnl = ((entry - curr_price) / entry) * 100

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

    # عرض التوصيات
    with btn_col2:
        st.subheader("التوصيات النشطة")
        try:
            signals_list = db.get_active_signals()
        except Exception as err:
            st.error(f"خطأ في قراءة التوصيات: {err}")
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
                    st2 = float(sig_row.get('tp2', 0) or 0)
                    ssl = float(sig_row.get('sl', 0) or 0)
                    sn = sig_row.get('asset_name', '')
                    stk = sig_row.get('ticker', '')

                    st.markdown(f"""
                    <div class="rec-card" style="border-left: 5px solid {color};">
                        <div style="display:flex; justify-content:space-between;">
                            <h3 style="margin:0;">{sn}
                                <span style="font-size:0.8em; color:#888;">{stk}</span>
                            </h3>
                            <h3 style="color:{color}; margin:0;">{dir_txt}</h3>
                        </div>
                        <div style="font-size:14px; margin:8px 0; display:flex; justify-content:space-between;">
                            <span>🏁 {se:.4f}</span>
                            <span>🏷️ {sc:.4f}</span>
                            <span>🎯 {st2:.4f}</span>
                            <span>🛑 {ssl:.4f}</span>
                        </div>
                        <div style="background:#111; height:10px; border-radius:5px; margin-top:5px;">
                            <div style="width:{sp}%; background:{color}; height:100%; border-radius:5px;"></div>
                        </div>
                        <div style="text-align:right; font-size:12px; margin-top:2px; color:#ccc;">
                            التقدم: {sp:.1f}% | الربح: <span style="color:{color}">{spnl:.2f}%</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                except Exception:
                    continue
        else:
            st.info("لا توجد توصيات نشطة. اضغط 'مسح السوق' للبحث عن فرص.")

        st.markdown("---")
        st.subheader("سجل التوصيات المنتهية")
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
                        "الاتجاه": "شراء" if cr.get('direction') == 'buy' else "بيع",
                        "الحالة": "✅ هدف" if cr.get('status') == 'tp_hit' else "❌ وقف",
                        "الربح %": round(float(cr.get('pnl_pct', 0) or 0), 2)
                    })
                except Exception:
                    continue
            if hist_data:
                st.dataframe(pd.DataFrame(hist_data), use_container_width=True, hide_index=True)

# ============================================================
# 7. صفحة التحليل الفني
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
        analyze_btn = st.button("🚀 تحليل الآن", type="primary", use_container_width=True)

    if analyze_btn:
        with st.spinner("جاري التحليل..."):
            df, info = fetch_data(ticker, tf_label)
            if df is not None and len(df) > 15:
                df = calculate_indicators(df)
                ts, td, curr = smart_technical_score(df)
                sig, cls_name, comb = final_signal(ts)
                tgts = calc_targets(curr, ts)

                st.session_state.analysis_result = {
                    'ticker': ticker, 'price': safe_val(curr['Close']),
                    'sig': sig, 'cls': cls_name, 'comb': comb,
                    'ts': ts, 'td': td, 'tgts': tgts, 'tf': tf_label
                }

                ai_res = get_ai_verdict(client, ticker, ts, td, curr)
                st.session_state.ai_result = ai_res

                try:
                    db.save_analysis(ticker, tf_label, sig, cls_name, comb,
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
                icon = "✅" if d[2] == "green" else "❌"
                st.markdown(f"{icon} **{d[0]}** ({d[1]})")

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
# 8. صفحة الدردشة
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

                    resp = client.chat_completion(messages=msgs, max_tokens=600, stream=False)
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
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                except Exception:
                    st.error("⚠️ خطأ في الاتصال. حاول مرة أخرى.")
            else:
                st.error("⚠️ أضف HF_TOKEN في إعدادات التطبيق.")

    if st.session_state.messages:
        if st.button("🗑️ مسح المحادثة"):
            st.session_state.messages = []
            st.rerun()