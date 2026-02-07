import sqlite3
from datetime import datetime

DB_NAME = "protrade_data.db"


def init_db():
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


def save_analysis(ticker, tf, signal, sig_cls, strength, price, targets, ai_data):
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
        print(f"Error save_analysis: {e}")


def get_all_history():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM analysis_history ORDER BY id DESC')
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def add_signal(ticker, name, direction, entry, tp1, tp2, sl, strength):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            "SELECT id FROM signals_tracking WHERE ticker=? AND status='active'",
            (ticker,)
        )
        if c.fetchone():
            conn.close()
            return False
        c.execute('''
            INSERT INTO signals_tracking (
                timestamp, ticker, asset_name, direction, entry_price,
                current_price, tp1, tp2, sl, strength, status, progress, pnl_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0.0, 0.0)
        ''', (
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            str(ticker), str(name), str(direction),
            float(entry), float(entry),
            float(tp1), float(tp2), float(sl), float(strength)
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error add_signal: {e}")
        return False


def get_active_signals():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            "SELECT id, timestamp, ticker, asset_name, direction, "
            "entry_price, current_price, tp1, tp2, sl, "
            "strength, status, progress, pnl_pct "
            "FROM signals_tracking WHERE status='active' ORDER BY strength DESC"
        )
        rows = c.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                'id': row[0],
                'timestamp': row[1] if row[1] else '',
                'ticker': row[2] if row[2] else '',
                'asset_name': row[3] if row[3] else '',
                'direction': row[4] if row[4] else 'buy',
                'entry_price': float(row[5]) if row[5] else 0.0,
                'current_price': float(row[6]) if row[6] else 0.0,
                'tp1': float(row[7]) if row[7] else 0.0,
                'tp2': float(row[8]) if row[8] else 0.0,
                'sl': float(row[9]) if row[9] else 0.0,
                'strength': float(row[10]) if row[10] else 0.0,
                'status': row[11] if row[11] else 'active',
                'progress': float(row[12]) if row[12] else 0.0,
                'pnl_pct': float(row[13]) if row[13] else 0.0,
            })
        return result
    except Exception as e:
        print(f"Error get_active_signals: {e}")
        return []


def get_closed_signals():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            "SELECT id, timestamp, ticker, asset_name, direction, "
            "entry_price, current_price, tp1, tp2, sl, "
            "strength, status, progress, pnl_pct "
            "FROM signals_tracking WHERE status!='active' "
            "ORDER BY timestamp DESC LIMIT 50"
        )
        rows = c.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                'id': row[0],
                'timestamp': row[1] if row[1] else '',
                'ticker': row[2] if row[2] else '',
                'asset_name': row[3] if row[3] else '',
                'direction': row[4] if row[4] else 'buy',
                'entry_price': float(row[5]) if row[5] else 0.0,
                'current_price': float(row[6]) if row[6] else 0.0,
                'tp1': float(row[7]) if row[7] else 0.0,
                'tp2': float(row[8]) if row[8] else 0.0,
                'sl': float(row[9]) if row[9] else 0.0,
                'strength': float(row[10]) if row[10] else 0.0,
                'status': row[11] if row[11] else 'closed',
                'progress': float(row[12]) if row[12] else 0.0,
                'pnl_pct': float(row[13]) if row[13] else 0.0,
            })
        return result
    except Exception as e:
        print(f"Error get_closed_signals: {e}")
        return []


def update_signal_status(signal_id, current_price, status, progress, pnl):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            UPDATE signals_tracking
            SET current_price=?, status=?, progress=?, pnl_pct=?
            WHERE id=?
        ''', (float(current_price), str(status), float(progress), float(pnl), int(signal_id)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error update_signal: {e}")