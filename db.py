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

    # جدول تتبع التوصيات
    c.execute('''
        CREATE TABLE IF NOT EXISTS signals_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            ticker TEXT,
            asset_name TEXT,
            direction TEXT,
            entry_price REAL,
            current_price REAL,
            tp1 REAL,
            tp2 REAL,
            sl REAL,
            strength REAL,
            status TEXT DEFAULT 'active',
            progress REAL DEFAULT 0,
            pnl_pct REAL DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()


# --- دوال التحليل العادي ---

def save_analysis(ticker, tf, signal, sig_cls, strength, price, targets, ai_data):
    """حفظ تحليل فني في السجل"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        ai_dec = 'N/A'
        ai_risk = 'N/A'
        if ai_data and isinstance(ai_data, dict):
            ai_dec = ai_data.get('final_decision', 'N/A')
            ai_risk = ai_data.get('risk_level', 'N/A')

        c.execute('''
            INSERT INTO analysis_history (
                timestamp, ticker, timeframe, signal, signal_class, strength,
                price, sl, tp1, tp2, tp3, rr, ai_decision, ai_risk
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ticker, tf, signal, sig_cls, strength, price,
            targets.get('sl', 0), targets.get('tp1', 0),
            targets.get('tp2', 0), targets.get('tp3', 0),
            targets.get('rr', 0), ai_dec, ai_risk
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving analysis: {e}")


def get_all_history():
    """جلب كل سجل التحليلات"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            SELECT id, timestamp, ticker, timeframe, signal, signal_class,
                   strength, price, sl, tp1, tp2, tp3, rr, ai_decision, ai_risk
            FROM analysis_history ORDER BY id DESC
        ''')
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


# --- دوال التوصيات ---

def add_signal(ticker, name, direction, entry, tp1, tp2, sl, strength):
    """إضافة توصية جديدة مع التحقق من عدم التكرار"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # التحقق من عدم وجود توصية نشطة لنفس الزوج
        c.execute(
            "SELECT id FROM signals_tracking WHERE ticker = ? AND status = 'active'",
            (ticker,)
        )
        if c.fetchone():
            conn.close()
            return False

        c.execute('''
            INSERT INTO signals_tracking (
                timestamp, ticker, asset_name, direction, entry_price,
                current_price, tp1, tp2, sl, strength, status, progress, pnl_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            ticker, name, direction, entry, entry,
            tp1, tp2, sl, strength, 'active', 0.0, 0.0
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding signal: {e}")
        return False


def get_active_signals():
    """جلب التوصيات النشطة كقائمة من القواميس"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            "SELECT id, timestamp, ticker, asset_name, direction, entry_price, "
            "current_price, tp1, tp2, sl, strength, status, progress, pnl_pct "
            "FROM signals_tracking WHERE status = 'active' ORDER BY strength DESC"
        )
        columns = [
            'id', 'timestamp', 'ticker', 'asset_name', 'direction',
            'entry_price', 'current_price', 'tp1', 'tp2', 'sl',
            'strength', 'status', 'progress', 'pnl_pct'
        ]
        rows = c.fetchall()
        conn.close()

        result = []
        for row in rows:
            d = {}
            for i, col_name in enumerate(columns):
                val = row[i]
                # التأكد أن القيم الرقمية ليست None
                if col_name in ('entry_price', 'current_price', 'tp1', 'tp2',
                                'sl', 'strength', 'progress', 'pnl_pct'):
                    if val is None:
                        val = 0.0
                    else:
                        val = float(val)
                elif val is None:
                    val = ''
                d[col_name] = val
            result.append(d)
        return result

    except Exception as e:
        print(f"Error getting active signals: {e}")
        return []


def get_closed_signals():
    """جلب التوصيات المنتهية كقائمة من القواميس"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            "SELECT id, timestamp, ticker, asset_name, direction, entry_price, "
            "current_price, tp1, tp2, sl, strength, status, progress, pnl_pct "
            "FROM signals_tracking WHERE status != 'active' "
            "ORDER BY timestamp DESC LIMIT 50"
        )
        columns = [
            'id', 'timestamp', 'ticker', 'asset_name', 'direction',
            'entry_price', 'current_price', 'tp1', 'tp2', 'sl',
            'strength', 'status', 'progress', 'pnl_pct'
        ]
        rows = c.fetchall()
        conn.close()

        result = []
        for row in rows:
            d = {}
            for i, col_name in enumerate(columns):
                val = row[i]
                if col_name in ('entry_price', 'current_price', 'tp1', 'tp2',
                                'sl', 'strength', 'progress', 'pnl_pct'):
                    if val is None:
                        val = 0.0
                    else:
                        val = float(val)
                elif val is None:
                    val = ''
                d[col_name] = val
            result.append(d)
        return result

    except Exception as e:
        print(f"Error getting closed signals: {e}")
        return []


def update_signal_status(signal_id, current_price, status, progress, pnl):
    """تحديث حالة التوصية"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            UPDATE signals_tracking
            SET current_price = ?, status = ?, progress = ?, pnl_pct = ?
            WHERE id = ?
        ''', (current_price, status, progress, pnl, signal_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating signal: {e}")