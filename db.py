import sqlite3
import os
from datetime import datetime

DB_NAME = "protrade_data.db"
DB_VERSION = 3  # رقم الإصدار - غيّره لإعادة إنشاء الجداول


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # التحقق من إصدار قاعدة البيانات
    c.execute('''CREATE TABLE IF NOT EXISTS db_meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    c.execute("SELECT value FROM db_meta WHERE key='version'")
    row = c.fetchone()
    current_version = int(row[0]) if row else 0

    if current_version < DB_VERSION:
        # حذف الجداول القديمة وإعادة إنشائها
        c.execute("DROP TABLE IF EXISTS signals_tracking")
        c.execute("DROP TABLE IF EXISTS analysis_history")
        c.execute("DROP TABLE IF EXISTS scan_status")
        c.execute("DELETE FROM db_meta")
        c.execute("INSERT INTO db_meta (key, value) VALUES ('version', ?)",
                  (str(DB_VERSION),))
        conn.commit()

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
            ai_risk TEXT,
            technical_score REAL DEFAULT 0,
            fundamental_score REAL DEFAULT 0,
            news_score REAL DEFAULT 0,
            ai_score REAL DEFAULT 0,
            filters_detail TEXT DEFAULT '',
            ai_reasoning TEXT DEFAULT ''
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
            tp3 REAL,
            sl REAL,
            strength REAL,
            status TEXT DEFAULT 'active',
            progress REAL DEFAULT 0,
            pnl_pct REAL DEFAULT 0,
            timeframe TEXT DEFAULT '',
            technical_score REAL DEFAULT 0,
            fundamental_score REAL DEFAULT 0,
            news_score REAL DEFAULT 0,
            ai_score REAL DEFAULT 0,
            filters_detail TEXT DEFAULT '',
            ai_reasoning TEXT DEFAULT ''
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS scan_status (
            id INTEGER PRIMARY KEY,
            is_running INTEGER DEFAULT 0,
            progress REAL DEFAULT 0,
            total_assets INTEGER DEFAULT 0,
            scanned_assets INTEGER DEFAULT 0,
            found_signals INTEGER DEFAULT 0,
            current_asset TEXT DEFAULT '',
            start_time TEXT DEFAULT '',
            end_time TEXT DEFAULT ''
        )
    ''')

    conn.commit()
    conn.close()


def save_analysis(ticker, tf, signal, sig_cls, strength, price, targets,
                  ai_data, tech_score=0, fund_score=0, news_score=0,
                  ai_score=0, filters_detail='', ai_reasoning=''):
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
                price, sl, tp1, tp2, tp3, rr, ai_decision, ai_risk,
                technical_score, fundamental_score, news_score, ai_score,
                filters_detail, ai_reasoning
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ticker, tf, signal, sig_cls, strength, price,
            targets.get('sl', 0), targets.get('tp1', 0),
            targets.get('tp2', 0), targets.get('tp3', 0),
            targets.get('rr', 0), ai_dec, ai_risk,
            float(tech_score), float(fund_score), float(news_score),
            float(ai_score), str(filters_detail), str(ai_reasoning)
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


def add_signal(ticker, name, direction, entry, tp1, tp2, tp3, sl,
               strength, timeframe, technical_score, fundamental_score,
               news_score, ai_score, filters_detail, ai_reasoning):
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
                current_price, tp1, tp2, tp3, sl, strength, status,
                progress, pnl_pct, timeframe, technical_score,
                fundamental_score, news_score, ai_score,
                filters_detail, ai_reasoning
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'active',0.0,0.0,?,?,?,?,?,?,?)
        ''', (
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            str(ticker), str(name), str(direction),
            float(entry), float(entry),
            float(tp1), float(tp2), float(tp3), float(sl),
            float(strength), str(timeframe),
            float(technical_score), float(fundamental_score),
            float(news_score), float(ai_score),
            str(filters_detail), str(ai_reasoning)
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error add_signal: {e}")
        return False


def _row_to_dict(row):
    if not row:
        return None
    keys = [
        'id', 'timestamp', 'ticker', 'asset_name', 'direction',
        'entry_price', 'current_price', 'tp1', 'tp2', 'tp3', 'sl',
        'strength', 'status', 'progress', 'pnl_pct', 'timeframe',
        'technical_score', 'fundamental_score', 'news_score',
        'ai_score', 'filters_detail', 'ai_reasoning'
    ]
    float_keys = {
        'entry_price', 'current_price', 'tp1', 'tp2', 'tp3', 'sl',
        'strength', 'progress', 'pnl_pct', 'technical_score',
        'fundamental_score', 'news_score', 'ai_score'
    }
    d = {}
    for i, k in enumerate(keys):
        if i < len(row):
            val = row[i]
            if k in float_keys:
                try:
                    d[k] = float(val) if val is not None else 0.0
                except (TypeError, ValueError):
                    d[k] = 0.0
            else:
                d[k] = val if val is not None else ''
        else:
            if k in float_keys:
                d[k] = 0.0
            else:
                d[k] = ''
    return d


def get_active_signals():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            "SELECT id, timestamp, ticker, asset_name, direction, "
            "entry_price, current_price, tp1, tp2, tp3, sl, "
            "strength, status, progress, pnl_pct, timeframe, "
            "technical_score, fundamental_score, news_score, "
            "ai_score, filters_detail, ai_reasoning "
            "FROM signals_tracking WHERE status='active' "
            "ORDER BY strength DESC"
        )
        rows = c.fetchall()
        conn.close()
        return [_row_to_dict(r) for r in rows if r]
    except Exception as e:
        print(f"Error get_active_signals: {e}")
        return []


def get_closed_signals():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            "SELECT id, timestamp, ticker, asset_name, direction, "
            "entry_price, current_price, tp1, tp2, tp3, sl, "
            "strength, status, progress, pnl_pct, timeframe, "
            "technical_score, fundamental_score, news_score, "
            "ai_score, filters_detail, ai_reasoning "
            "FROM signals_tracking WHERE status!='active' "
            "ORDER BY timestamp DESC LIMIT 50"
        )
        rows = c.fetchall()
        conn.close()
        return [_row_to_dict(r) for r in rows if r]
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
        ''', (float(current_price), str(status), float(progress),
              float(pnl), int(signal_id)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error update_signal: {e}")


def set_scan_status(is_running, progress=0, total=0, scanned=0,
                    found=0, current=''):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM scan_status")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        end = '' if is_running else now
        c.execute('''
            INSERT INTO scan_status (
                id, is_running, progress, total_assets, scanned_assets,
                found_signals, current_asset, start_time, end_time
            ) VALUES (1,?,?,?,?,?,?,?,?)
        ''', (
            1 if is_running else 0, float(progress), int(total),
            int(scanned), int(found), str(current), now, end
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error set_scan_status: {e}")


def get_scan_status():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM scan_status WHERE id=1")
        row = c.fetchone()
        conn.close()
        if row:
            return {
                'is_running': bool(row[1]),
                'progress': float(row[2]) if row[2] else 0,
                'total_assets': int(row[3]) if row[3] else 0,
                'scanned_assets': int(row[4]) if row[4] else 0,
                'found_signals': int(row[5]) if row[5] else 0,
                'current_asset': row[6] if row[6] else '',
                'start_time': row[7] if row[7] else '',
                'end_time': row[8] if row[8] else '',
            }
        return None
    except Exception:
        return None


def delete_all_active():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM signals_tracking WHERE status='active'")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error delete_all_active: {e}")