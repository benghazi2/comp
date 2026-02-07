--- START OF FILE db.py ---
import sqlite3
from datetime import datetime

DB_NAME = "protrade_data.db"

def init_db():
    """إنشاء جدول البيانات إذا لم يكن موجوداً"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
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
    conn.commit()
    conn.close()

def save_analysis(ticker, tf, signal, sig_cls, strength, price, targets, ai_data):
    """حفظ نتيجة التحليل في قاعدة البيانات"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # التعامل مع بيانات الذكاء الاصطناعي في حال كانت غير موجودة
    ai_dec = ai_data.get('decision', 'N/A') if ai_data else 'N/A'
    ai_risk = ai_data.get('risk', 'N/A') if ai_data else 'N/A'
    
    c.execute('''
        INSERT INTO analysis_history (
            timestamp, ticker, timeframe, signal, signal_class, strength, 
            price, sl, tp1, tp2, tp3, rr, ai_decision, ai_risk
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ticker,
        tf,
        signal,
        sig_cls,
        strength,
        price,
        targets['sl'],
        targets['tp1'],
        targets['tp2'],
        targets['tp3'],
        targets['rr'],
        ai_dec,
        ai_risk
    ))
    conn.commit()
    conn.close()

def get_all_history():
    """جلب سجل التحليلات بالكامل مرتباً من الأحدث"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # للوصول للأعمدة بالاسم
    c = conn.cursor()
    c.execute('SELECT * FROM analysis_history ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    return rows