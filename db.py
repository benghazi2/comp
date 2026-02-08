import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime

def init_db():
    if not firebase_admin._apps:
        try:
            key_dict = dict(st.secrets["firebase"])
            db_url = key_dict.pop('database_url', None)

            if not db_url:
                print("ERROR: database_url missing")
                return False

            # إصلاح private_key - مشكلة شائعة جداً
            if 'private_key' in key_dict:
                key_dict['private_key'] = key_dict['private_key'].replace('\\n', '\n')

            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred, {'databaseURL': db_url})
            print("Firebase connected OK")
            return True
        except Exception as e:
            print(f"Firebase init error: {e}")
            return False
    return True


def _ref(path):
    return db.reference(path)


def save_analysis(ticker, tf, signal, sig_cls, strength, price, targets,
                  ai_data, tech_score=0, fund_score=0, news_score=0,
                  ai_score=0, filters_detail='', ai_reasoning=''):
    try:
        ai_dec = 'N/A'
        ai_risk = 'N/A'
        if isinstance(ai_data, dict):
            ai_dec = ai_data.get('final_decision', 'N/A')
            ai_risk = ai_data.get('risk_level', 'N/A')

        _ref('analysis_history').push({
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'ticker': str(ticker), 'timeframe': str(tf),
            'signal': str(signal), 'signal_class': str(sig_cls),
            'strength': float(strength), 'price': float(price),
            'sl': float(targets.get('sl', 0)),
            'tp1': float(targets.get('tp1', 0)),
            'tp2': float(targets.get('tp2', 0)),
            'tp3': float(targets.get('tp3', 0)),
            'rr': float(targets.get('rr', 0)),
            'ai_decision': str(ai_dec), 'ai_risk': str(ai_risk),
            'technical_score': float(tech_score),
            'fundamental_score': float(fund_score),
            'news_score': float(news_score),
            'ai_score': float(ai_score),
            'filters_detail': str(filters_detail),
            'ai_reasoning': str(ai_reasoning)
        })
    except Exception as e:
        print(f"Error save_analysis: {e}")


def get_all_history():
    try:
        snapshot = _ref('analysis_history').order_by_key().limit_to_last(50).get()
        if not snapshot:
            return []
        rows = []
        for key, val in snapshot.items():
            val['id'] = key
            rows.append(val)
        return sorted(rows, key=lambda x: x.get('timestamp', ''), reverse=True)
    except:
        return []


def add_signal(ticker, name, direction, entry, tp1, tp2, tp3, sl,
               strength, timeframe, technical_score, fundamental_score,
               news_score, ai_score, filters_detail, ai_reasoning):
    try:
        ref = _ref('signals_tracking')
        actives = ref.order_by_child('status').equal_to('active').get()
        if actives:
            for _, val in actives.items():
                if val.get('ticker') == str(ticker):
                    return False

        ref.push({
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'ticker': str(ticker), 'asset_name': str(name),
            'direction': str(direction),
            'entry_price': float(entry), 'current_price': float(entry),
            'tp1': float(tp1), 'tp2': float(tp2), 'tp3': float(tp3),
            'sl': float(sl), 'strength': float(strength),
            'status': 'active', 'progress': 0.0, 'pnl_pct': 0.0,
            'timeframe': str(timeframe),
            'technical_score': float(technical_score),
            'fundamental_score': float(fundamental_score),
            'news_score': float(news_score),
            'ai_score': float(ai_score),
            'filters_detail': str(filters_detail),
            'ai_reasoning': str(ai_reasoning),
            'hit_time': '', 'hit_price': 0
        })
        return True
    except Exception as e:
        print(f"Error add_signal: {e}")
        return False


def get_active_signals():
    try:
        snapshot = _ref('signals_tracking').order_by_child('status').equal_to('active').get()
        if not snapshot:
            return []
        rows = []
        for key, val in snapshot.items():
            val['id'] = key
            rows.append(val)
        return sorted(rows, key=lambda x: x.get('strength', 0), reverse=True)
    except Exception as e:
        print(f"Error get_active_signals: {e}")
        return []


def get_closed_signals():
    try:
        snapshot = _ref('signals_tracking').order_by_key().limit_to_last(100).get()
        if not snapshot:
            return []
        rows = []
        for key, val in snapshot.items():
            if val.get('status') != 'active':
                val['id'] = key
                rows.append(val)
        return sorted(rows, key=lambda x: x.get('timestamp', ''), reverse=True)
    except:
        return []


def update_signal_status(signal_id, current_price, status, progress, pnl,
                         hit_time='', hit_price=0):
    try:
        _ref(f'signals_tracking/{signal_id}').update({
            'current_price': float(current_price),
            'status': str(status), 'progress': float(progress),
            'pnl_pct': float(pnl), 'hit_time': str(hit_time),
            'hit_price': float(hit_price)
        })
    except Exception as e:
        print(f"Error update_signal: {e}")


def delete_all_active():
    try:
        snapshot = _ref('signals_tracking').order_by_child('status').equal_to('active').get()
        if snapshot:
            for key in snapshot:
                _ref(f'signals_tracking/{key}').delete()
    except Exception as e:
        print(f"Error delete_all_active: {e}")


def set_scan_status(is_running, progress=0, total=0, scanned=0,
                    found=0, current=''):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _ref('scan_status').set({
            'is_running': bool(is_running),
            'progress': float(progress),
            'total_assets': int(total),
            'scanned_assets': int(scanned),
            'found_signals': int(found),
            'current_asset': str(current),
            'start_time': now,
            'end_time': '' if is_running else now,
            'last_update': now
        })
    except Exception as e:
        print(f"Error set_scan_status: {e}")


def get_scan_status():
    try:
        return _ref('scan_status').get()
    except:
        return None