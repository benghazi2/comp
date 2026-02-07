import sqlite3
from datetime import datetime

DB_NAME = "protrade_data.db"

def init_db():
    """إنشاء جداول البيانات"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # جدول سجل التحليلات العادية
    c.execute('''
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            ticker TEXT,
            timeframe TEXT,
            signal TEXT,
            signal_class TEXT,
            strength REAL,
            price REAL,
            sl REAL,
            tp1 REAL,
            tp2 REAL,
            tp3 REAL,
            rr REAL,
            ai_decision TEXT,
            ai_risk TEXT
        )
    ''')

    # جدول تتبع التوصيات (الجديد)
    c.execute('''
        CREATE TABLE IF NOT EXISTS signals_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            ticker TEXT,
            asset_name TEXT,
            direction TEXT, -- buy or sell
            entry_price REAL,
            current_price REAL,
            tp1 REAL,
            tp2 REAL,
            sl REAL,
            strength REAL,
            status TEXT, -- active, tp_hit, sl_hit
            progress REAL, -- 0 to 100%
            pnl_pct REAL
        )
    ''')
    
    conn.commit()
    conn.close()

# --- دوال التحليل العادي ---
def save_analysis(ticker, tf, signal, sig_cls, strength, price, targets, ai_data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    ai_dec = ai_data.get('final_decision', 'N/A') if ai_data else 'N/A'
    ai_risk = ai_data.get('risk_level', 'N/A') if ai_data else 'N/A'
    
    c.execute('''
        INSERT INTO analysis_history (
            timestamp, ticker, timeframe, signal, signal_class, strength, 
            price, sl, tp1, tp2, tp3, rr, ai_decision, ai_risk
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ticker, tf, signal, sig_cls, strength, price,
        targets['sl'], targets['tp1'], targets['tp2'], targets['tp3'], targets['rr'],
        ai_dec, ai_risk
    ))
    conn.commit()
    conn.close()

def get_all_history():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('SELECT id, timestamp, ticker, timeframe, signal, signal_class, strength, price, sl, tp1, tp2, tp3, rr, ai_decision, ai_risk FROM analysis_history ORDER BY id DESC')
        rows = c.fetchall()
        conn.close()
        return rows
    except: return []

# --- دوال التوصيات (الجديدة) ---
def add_signal(ticker, name, direction, entry, tp1, tp2, sl, strength):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # التحقق من عدم وجود توصية نشطة لنفس الزوج
    c.execute("SELECT id FROM signals_tracking WHERE ticker = ? AND status = 'active'", (ticker,))
    if c.fetchone():
        conn.close()
        return False # موجودة مسبقاً

    c.execute('''
        INSERT INTO signals_tracking (
            timestamp, ticker, asset_name, direction, entry_price, current_price,
            tp1, tp2, sl, strength, status, progress, pnl_pct
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        ticker, name, direction, entry, entry,
        tp1, tp2, sl, strength, 'active', 0.0, 0.0
    ))
    conn.commit()
    conn.close()
    return True

def get_active_signals():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM signals_tracking WHERE status = 'active' ORDER BY strength DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_closed_signals():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM signals_tracking WHERE status != 'active' ORDER BY timestamp DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return rows

def update_signal_status(id, current_price, status, progress, pnl):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        UPDATE signals_tracking 
        SET current_price = ?, status = ?, progress = ?, pnl_pct = ?
        WHERE id = ?
    ''', (current_price, status, progress, pnl, id))
    conn.commit()
    conn.close()