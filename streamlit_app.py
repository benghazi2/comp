
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import json
from datetime import datetime, timedelta

# إعدادات الصفحة
st.set_page_config(
    page_title="AI Smart Trader Pro",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS مخصص
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .buy-card { border-right: 5px solid #00ff88; background-color: #1a1a2e; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    .sell-card { border-right: 5px solid #ff4b4b; background-color: #1a1a2e; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    .wait-card { border-right: 5px solid #888; background-color: #1a1a2e; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    .strength-bar { height: 20px; border-radius: 10px; }
    .metric-card { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px; border-radius: 15px; }
</style>
""", unsafe_allow_html=True)

# قائمة الأزواج
FOREX_PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "Gold/USD": "XAUUSD=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "USD/CHF": "USDCHF=X",
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
    "NZD/USD": "NZDUSD=X"
}

TIMEFRAMES = {
    "5 دقائق": "5m",
    "15 دقيقة": "15m",
    "ساعة": "1h",
    "4 ساعات": "4h",
    "يومي": "1d"
}

# ============== المؤشرات الفنية ==============

def calculate_rsi(closes, period=14):
    """حساب RSI"""
    if len(closes) < period + 1:
        return 50
    
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ema(data, period):
    """حساب EMA"""
    ema = [data[0]]
    multiplier = 2 / (period + 1)
    for price in data[1:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return np.array(ema)

def calculate_macd(closes):
    """حساب MACD"""
    ema12 = calculate_ema(closes, 12)
    ema26 = calculate_ema(closes, 26)
    macd_line = ema12 - ema26
    signal_line = calculate_ema(macd_line, 9)
    histogram = macd_line - signal_line
    return macd_line[-1], signal_line[-1], histogram[-1]

def calculate_bollinger_bands(closes, period=20):
    """حساب Bollinger Bands"""
    sma = np.mean(closes[-period:])
    std = np.std(closes[-period:])
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    return upper, sma, lower

def calculate_stochastic(df, period=14):
    """حساب Stochastic"""
    recent = df.tail(period)
    low_min = recent['Low'].min()
    high_max = recent['High'].max()
    
    current_close = df['Close'].iloc[-1]
    k = ((current_close - low_min) / (high_max - low_min)) * 100 if high_max != low_min else 50
    
    # حساب %D (متوسط 3 فترات)
    k_values = []
    for i in range(-3, 0):
        if len(df) + i >= period:
            r = df.iloc[i-period:i]
            l = r['Low'].min()
            h = r['High'].max()
            c = df['Close'].iloc[i]
            k_values.append(((c - l) / (h - l)) * 100 if h != l else 50)
    
    d = np.mean(k_values) if k_values else 50
    return k, d

def calculate_atr(df, period=14):
    """حساب ATR"""
    high = df['High']
    low = df['Low']
    close = df['Close'].shift(1)
    
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean().iloc[-1]

def calculate_adx(df, period=14):
    """حساب ADX"""
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    plus_dm = high.diff()
    minus_dm = low.diff()
    
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    tr = calculate_atr(df, period) * period
    
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / tr)
    minus_di = 100 * (abs(minus_dm).rolling(window=period).mean() / tr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean().iloc[-1]
    
    return adx, plus_di.iloc[-1], minus_di.iloc[-1]

# ============== التحليل الشامل ==============

def full_analysis(df):
    """تحليل فني شامل"""
    if len(df) < 50:
        return None
    
    closes = df['Close'].values
    analysis = {
        'indicators': {},
        'score': 0,
        'signal': 'NEUTRAL',
        'buy_signals': 0,
        'sell_signals': 0
    }
    
    # RSI
    rsi = calculate_rsi(closes)
    analysis['indicators']['RSI'] = {
        'value': round(rsi, 2),
        'signal': 'BUY' if rsi < 30 else ('SELL' if rsi > 70 else 'NEUTRAL'),
        'strength': min(100, (30 - rsi) * 3.33) if rsi < 30 else (min(100, (rsi - 70) * 3.33) if rsi > 70 else 0)
    }
    if rsi < 30:
        analysis['buy_signals'] += abs(30 - rsi) * 2
    elif rsi > 70:
        analysis['sell_signals'] += abs(rsi - 70) * 2
    
    # MACD
    macd, signal, hist = calculate_macd(closes)
    analysis['indicators']['MACD'] = {
        'value': round(macd, 5),
        'signal': 'BUY' if hist > 0 else ('SELL' if hist < 0 else 'NEUTRAL'),
        'strength': min(100, abs(hist) * 1000)
    }
    if hist > 0:
        analysis['buy_signals'] += abs(hist) * 1000
    else:
        analysis['sell_signals'] += abs(hist) * 1000
    
    # Bollinger Bands
    upper, middle, lower = calculate_bollinger_bands(closes)
    current_price = closes[-1]
    bb_position = (current_price - lower) / (upper - lower) if upper != lower else 0.5
    analysis['indicators']['Bollinger'] = {
        'value': f"Upper: {upper:.5f}, Lower: {lower:.5f}",
        'signal': 'BUY' if current_price < lower else ('SELL' if current_price > upper else 'NEUTRAL'),
        'strength': min(100, (1 - bb_position) * 100 if bb_position < 0.3 else bb_position * 100 if bb_position > 0.7 else 0)
    }
    if current_price < lower:
        analysis['buy_signals'] += 50
    elif current_price > upper:
        analysis['sell_signals'] += 50
    
    # Stochastic
    k, d = calculate_stochastic(df)
    analysis['indicators']['Stochastic'] = {
        'value': f"K: {k:.1f}, D: {d:.1f}",
        'signal': 'BUY' if k < 20 else ('SELL' if k > 80 else 'NEUTRAL'),
        'strength': min(100, (20 - k) * 5) if k < 20 else (min(100, (k - 80) * 5) if k > 80 else 0)
    }
    if k < 20:
        analysis['buy_signals'] += (20 - k) * 3
    elif k > 80:
        analysis['sell_signals'] += (k - 80) * 3
    
    # EMA Cross
    ema20 = calculate_ema(closes, 20)[-1]
    ema50 = calculate_ema(closes, 50)[-1]
    analysis['indicators']['EMA Cross'] = {
        'value': f"EMA20: {ema20:.5f}, EMA50: {ema50:.5f}",
        'signal': 'BUY' if ema20 > ema50 else ('SELL' if ema20 < ema50 else 'NEUTRAL'),
        'strength': min(100, abs(ema20 - ema50) / closes[-1] * 1000)
    }
    if ema20 > ema50:
        analysis['buy_signals'] += 40
    else:
        analysis['sell_signals'] += 40
    
    # ATR (Volatility)
    try:
        atr = calculate_atr(df)
        atr_percent = (atr / current_price) * 100
        analysis['indicators']['ATR'] = {
            'value': f"{atr:.5f} ({atr_percent:.2f}%)",
            'signal': 'NEUTRAL',
            'strength': 0,
            'volatility': 'HIGH' if atr_percent > 2 else ('LOW' if atr_percent < 0.5 else 'MEDIUM')
        }
    except:
        analysis['indicators']['ATR'] = {'value': 'N/A', 'signal': 'NEUTRAL', 'strength': 0}
    
    # ADX
    try:
        adx, plus_di, minus_di = calculate_adx(df)
        analysis['indicators']['ADX'] = {
            'value': round(adx, 2),
            'signal': 'BUY' if plus_di > minus_di else ('SELL' if minus_di > plus_di else 'NEUTRAL'),
            'strength': min(100, adx * 2)
        }
        if adx > 25:
            if plus_di > minus_di:
                analysis['buy_signals'] += adx
            else:
                analysis['sell_signals'] += adx
    except:
        analysis['indicators']['ADX'] = {'value': 25, 'signal': 'NEUTRAL', 'strength': 0}
    
    # حساب النتيجة النهائية
    total = analysis['buy_signals'] + analysis['sell_signals']
    if total > 0:
        analysis['score'] = int(max(analysis['buy_signals'], analysis['sell_signals']) / total * 100)
    
    if analysis['buy_signals'] > analysis['sell_signals'] * 1.3:
        analysis['signal'] = 'BUY'
    elif analysis['sell_signals'] > analysis['buy_signals'] * 1.3:
        analysis['signal'] = 'SELL'
    
    return analysis

# ============== جلب البيانات ==============

@st.cache_data(ttl=60)
def fetch_market_data(symbol, interval='15m'):
    """جلب بيانات السوق"""
    try:
        period_map = {
            '1m': '1d', '5m': '5d', '15m': '1mo', 
            '30m': '1mo', '1h': '1mo', '4h': '3mo', '1d': '1y'
        }
        period = period_map.get(interval, '1mo')
        
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        
        if df.empty:
            return None
        
        # تسطيح الأعمدة
        df.columns = df.columns.get_level_values(0) if isinstance(df.columns, pd.MultiIndex) else df.columns
        
        return df
    except Exception as e:
        st.error(f"خطأ في جلب البيانات: {e}")
        return None

# ============== الذكاء الاصطناعي ==============

def get_ai_analysis(symbol, price, analysis):
    """الحصول على تحليل AI"""
    # تحليل مبني على المؤشرات (بدون API خارجي)
    signal = analysis['signal']
    score = analysis['score']
    
    if signal == 'BUY':
        entry = price
        sl = price * 0.995  # 0.5% وقف خسارة
        tp1 = price * 1.01  # 1% هدف أول
        tp2 = price * 1.02  # 2% هدف ثاني
        reason = f"إشارة شراء قوية - المؤشرات تشير إلى تشبع بيعي مع زخم صاعد. القوة: {score}%"
    elif signal == 'SELL':
        entry = price
        sl = price * 1.005
        tp1 = price * 0.99
        tp2 = price * 0.98
        reason = f"إشارة بيع قوية - المؤشرات تشير إلى تشبع شرائي مع زخم هابط. القوة: {score}%"
    else:
        entry = price
        sl = price * 0.99
        tp1 = price * 1.005
        tp2 = price * 1.01
        reason = f"السوق في حالة محايدة - يفضل الانتظار لتأكيد الاتجاه. القوة: {score}%"
    
    return {
        'direction': signal,
        'entry': round(entry, 5),
        'sl': round(sl, 5),
        'tp1': round(tp1, 5),
        'tp2': round(tp2, 5),
        'reason': reason,
        'confidence': score
    }

# ============== الواجهة الرئيسية ==============

def main():
    # العنوان
    st.title("💹 AI Smart Trader Pro")
    st.markdown("**محلل الأسواق المالية الذكي - مع الذكاء الاصطناعي**")
    st.markdown("---")
    
    # التبويبات
    tab1, tab2, tab3 = st.tabs(["📡 ماسح السوق", "🎯 التوصيات", "🤖 المحلل الذكي"])
    
    # ========== تبويب ماسح السوق ==========
    with tab1:
        st.header("🔍 الماسح الضوئي للسوق")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            timeframe_label = st.selectbox("الإطار الزمني", list(TIMEFRAMES.keys()), index=1)
            timeframe = TIMEFRAMES[timeframe_label]
        
        if st.button("🚀 بدء فحص جميع الأزواج", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            
            for i, (name, symbol) in enumerate(FOREX_PAIRS.items()):
                status_text.text(f"جاري تحليل {name}...")
                
                df = fetch_market_data(symbol, timeframe)
                if df is not None and len(df) >= 50:
                    analysis = full_analysis(df)
                    if analysis:
                        results.append({
                            'name': name,
                            'symbol': symbol,
                            'price': df['Close'].iloc[-1],
                            'analysis': analysis
                        })
                
                progress_bar.progress((i + 1) / len(FOREX_PAIRS))
            
            status_text.success("✅ اكتمل الفحص!")
            
            # عرض النتائج
            if results:
                st.subheader("📊 نتائج التحليل")
                
                for r in sorted(results, key=lambda x: x['analysis']['score'], reverse=True):
                    signal = r['analysis']['signal']
                    score = r['analysis']['score']
                    
                    # لون البطاقة
                    card_class = 'buy-card' if signal == 'BUY' else ('sell-card' if signal == 'SELL' else 'wait-card')
                    color = '#00ff88' if signal == 'BUY' else ('#ff4b4b' if signal == 'SELL' else '#888')
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="{card_class}">
                            <h3 style="color: {color};">{r['name']} {'🟢 شراء' if signal == 'BUY' else ('🔴 بيع' if signal == 'SELL' else '⚪ محايد')}</h3>
                            <p><b>السعر:</b> {r['price']:.5f}</p>
                            <p><b>القوة:</b> {score}%</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # شريط القوة
                        st.progress(score / 100)
                        
                        # المؤشرات
                        with st.expander("📊 تفاصيل المؤشرات"):
                            for ind_name, ind_data in r['analysis']['indicators'].items():
                                signal_emoji = '🟢' if ind_data['signal'] == 'BUY' else ('🔴' if ind_data['signal'] == 'SELL' else '⚪')
                                st.write(f"**{ind_name}:** {ind_data['value']} {signal_emoji}")
                        
                        st.markdown("---")
    
    # ========== تبويب التوصيات ==========
    with tab2:
        st.header("🎯 التوصيات الحية")
        
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            pair_name = st.selectbox("اختر الزوج", list(FOREX_PAIRS.keys()))
        with col2:
            tf_label = st.selectbox("الإطار الزمني", list(TIMEFRAMES.keys()), index=1, key='tf2')
        with col3:
            st.write("")
            st.write("")
            analyze_btn = st.button("🔍 تحليل", type="primary")
        
        if analyze_btn or 'last_analysis' in st.session_state:
            if analyze_btn:
                symbol = FOREX_PAIRS[pair_name]
                df = fetch_market_data(symbol, TIMEFRAMES[tf_label])
                
                if df is not None and len(df) >= 50:
                    analysis = full_analysis(df)
                    price = df['Close'].iloc[-1]
                    recommendation = get_ai_analysis(symbol, price, analysis)
                    
                    st.session_state['last_analysis'] = {
                        'pair': pair_name,
                        'symbol': symbol,
                        'price': price,
                        'analysis': analysis,
                        'recommendation': recommendation
                    }
            
            if 'last_analysis' in st.session_state:
                data = st.session_state['last_analysis']
                rec = data['recommendation']
                analysis = data['analysis']
                
                # بطاقة التوصية الرئيسية
                signal = rec['direction']
                color = '#00ff88' if signal == 'BUY' else ('#ff4b4b' if signal == 'SELL' else '#888')
                card_class = 'buy-card' if signal == 'BUY' else ('sell-card' if signal == 'SELL' else 'wait-card')
                
                st.markdown(f"""
                <div class="{card_class}" style="padding: 30px; text-align: center;">
                    <h1 style="color: {color}; font-size: 3em;">{'🟢 شراء' if signal == 'BUY' else ('🔴 بيع' if signal == 'SELL' else '⚪ انتظار')}</h1>
                    <h2>{data['pair']}</h2>
                    <p style="font-size: 1.5em;">السعر الحالي: <b>{data['price']:.5f}</b></p>
                </div>
                """, unsafe_allow_html=True)
                
                # مستويات التداول
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("💰 سعر الدخول", f"{rec['entry']:.5f}")
                with col2:
                    st.metric("🛑 وقف الخسارة", f"{rec['sl']:.5f}", delta=f"-{abs(rec['entry'] - rec['sl']) / rec['entry'] * 100:.2f}%")
                with col3:
                    st.metric("🎯 الهدف 1", f"{rec['tp1']:.5f}", delta=f"+{abs(rec['tp1'] - rec['entry']) / rec['entry'] * 100:.2f}%")
                
                # شريط القوة
                st.subheader("📊 قوة الإشارة")
                st.progress(rec['confidence'] / 100)
                st.write(f"**{rec['confidence']}%**")
                
                # السبب
                st.info(f"💡 **التحليل:** {rec['reason']}")
                
                # المؤشرات التفصيلية
                st.subheader("📈 المؤشرات الفنية")
                indicators_df = []
                for name, ind in analysis['indicators'].items():
                    indicators_df.append({
                        'المؤشر': name,
                        'القيمة': ind['value'],
                        'الإشارة': '🟢 شراء' if ind['signal'] == 'BUY' else ('🔴 بيع' if ind['signal'] == 'SELL' else '⚪ محايد')
                    })
                
                st.table(pd.DataFrame(indicators_df))
    
    # ========== تبويب المحلل الذكي ==========
    with tab3:
        st.header("🤖 المحلل الذكي")
        st.markdown("اسألني عن أي زوج أو استراتيجية تداول!")
        
        # اختيار الزوج
        col1, col2 = st.columns([2, 1])
        with col1:
            chat_pair = st.selectbox("اختر زوجاً للحديث عنه", list(FOREX_PAIRS.keys()), key='chat_pair')
        with col2:
            web_search = st.checkbox("🔍 تفعيل بحث الويب", value=True)
        
        # سجل المحادثة
        if 'chat_history' not in st.session_state:
            st.session_state['chat_history'] = []
        
        # عرض الرسائل السابقة
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state['chat_history']:
                with st.chat_message(msg['role']):
                    st.write(msg['content'])
        
        # إدخال المستخدم
        if prompt := st.chat_input("اكتب سؤالك هنا..."):
            # إضافة رسالة المستخدم
            st.session_state['chat_history'].append({'role': 'user', 'content': prompt})
            
            with st.chat_message("user"):
                st.write(prompt)
            
            # الرد
            with st.chat_message("assistant"):
                # جلب بيانات الزوج المحدد
                symbol = FOREX_PAIRS[chat_pair]
                df = fetch_market_data(symbol)
                
                if df is not None:
                    analysis = full_analysis(df)
                    price = df['Close'].iloc[-1]
                    
                    # بناء رد ذكي
                    response = f"""📊 **تحليل {chat_pair}** (السعر: {price:.5f})

"""
                    if analysis:
                        signal_emoji = '🟢' if analysis['signal'] == 'BUY' else ('🔴' if analysis['signal'] == 'SELL' else '⚪')
                        response += f"""**الإشارة العامة:** {signal_emoji} {analysis['signal']}
**قوة الإشارة:** {analysis['score']}%

**المؤشرات:**
"""
                        for name, ind in analysis['indicators'].items():
                            ind_emoji = '🟢' if ind['signal'] == 'BUY' else ('🔴' if ind['signal'] == 'SELL' else '⚪')
                            response += f"- {name}: {ind['value']} {ind_emoji}\n"
                        
                        if 'شراء' in prompt or 'buy' in prompt.lower():
                            response += f"""

💡 **توصية:** {'فرصة شراء محتملة' if analysis['signal'] == 'BUY' else 'يفضل الانتظار لتأكيد الإشارة'}
"""
                        elif 'بيع' in prompt or 'sell' in prompt.lower():
                            response += f"""

💡 **توصية:** {'فرصة بيع محتملة' if analysis['signal'] == 'SELL' else 'يفضل الانتظار لتأكيد الإشارة'}
"""
                    else:
                        response = "عذراً، لا توجد بيانات كافية للتحليل."
                else:
                    response = "عذراً، لم أتمكن من جلب البيانات. يرجى المحاولة مرة أخرى."
                
                st.write(response)
                st.session_state['chat_history'].append({'role': 'assistant', 'content': response})
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #888;">
        <p>© 2024 AI Smart Trader Pro | محلل الأسواق المالية الذكي</p>
        <p>⚠️ تنبيه: هذه التحليلات للأغراض التعليمية فقط ولا تعتبر نصيحة استثمارية</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
