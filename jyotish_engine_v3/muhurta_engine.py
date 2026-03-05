"""
muhurta_engine.py — Auspicious/inauspicious timing from kaalavidya
Pure-Python muhurta functions (no swisseph needed).
"""
import sys, os, types, importlib.util
from datetime import datetime, timezone, timedelta

_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kaalavidya')
_LOADED = False

def _ensure():
    global _LOADED
    if _LOADED: return
    if 'kaalavidya' not in sys.modules:
        pkg = types.ModuleType('kaalavidya')
        pkg.__path__ = [_BASE]; pkg.__package__ = 'kaalavidya'
        sys.modules['kaalavidya'] = pkg
    pkg = sys.modules['kaalavidya']
    def _load(fname):
        name = 'kaalavidya.' + fname[:-3]
        if name in sys.modules: return sys.modules[name]
        spec = importlib.util.spec_from_file_location(name, os.path.join(_BASE, fname))
        m = importlib.util.module_from_spec(spec); m.__package__ = 'kaalavidya'
        sys.modules[name] = m; spec.loader.exec_module(m)
        setattr(pkg, fname[:-3], m); return m
    _load('constants.py'); _load('models.py'); _load('surya.py'); _load('sankalpa.py')
    _LOADED = True

def _fmt(dt):
    return dt.strftime('%I:%M %p') if dt else '—'

def _jd_to_aware(jd, tz_offset):
    """Convert Julian Day number to timezone-aware datetime."""
    swe = sys.modules['kaalavidya.constants'].swe
    r = swe.revjul(float(jd))
    y, mo, d, h_frac = int(r[0]), int(r[1]), int(r[2]), float(r[3])
    h = int(h_frac); rem = (h_frac - h) * 60; mi = int(rem); s = int((rem - mi) * 60)
    dt_utc = datetime(y, mo, d, h, mi, min(s, 59), tzinfo=timezone.utc)
    return dt_utc + timedelta(hours=tz_offset)


def compute_muhurtas(jd_sunrise, jd_sunset, tz_offset=5.5, lang='en',
                     lat=0.0, lon=0.0, city='', state='',
                     tithi_idx=0, nak_idx=0, yoga_idx=0,
                     masa_idx=0, paksha_idx=0, samvatsara_year=2025):
    """
    Compute full muhurta suite from PyJHora JD sunrise/sunset.
    Returns dict ready for Jinja2 template.
    """
    _ensure()
    _consts = sys.modules['kaalavidya.constants']
    _surya  = sys.modules['kaalavidya.surya']
    _sankp  = sys.modules['kaalavidya.sankalpa']

    try:
        sr = _jd_to_aware(jd_sunrise, tz_offset)
        ss = _jd_to_aware(jd_sunset,  tz_offset)
    except Exception as e:
        return {'error': str(e)}

    weekday = sr.weekday()   # 0=Mon … 6=Sun
    result = {
        'sunrise': _fmt(sr), 'sunset': _fmt(ss),
        'weekday': sr.strftime('%A')
    }

    # ── Inauspicious periods ──
    for key, fn in [('rahu_kala',   _surya.compute_rahu_kala),
                    ('yamagandam',  _surya.compute_yamagandam),
                    ('gulika_kala', _surya.compute_gulika_kala)]:
        try:
            p = fn(sr, ss, weekday)
            result[key] = {'start': _fmt(p.starts_at), 'end': _fmt(p.ends_at)}
        except Exception: pass

    try:
        dur = _surya.compute_durmuhurta(sr, ss, weekday)
        result['durmuhurta'] = [{'start': _fmt(d.starts_at), 'end': _fmt(d.ends_at)} for d in dur]
    except Exception: result['durmuhurta'] = []

    # ── Auspicious periods ──
    try:
        bm = _surya.compute_brahma_muhurta(sr, sr - timedelta(hours=12))
        result['brahma_muhurta'] = {'start': _fmt(bm.starts_at), 'end': _fmt(bm.ends_at)}
    except Exception: pass

    try:
        am = _surya.compute_abhijit_muhurta(sr, ss)
        result['abhijit_muhurta'] = {'start': _fmt(am.starts_at), 'end': _fmt(am.ends_at)}
    except Exception: pass

    # ── 15 Dina muhurtas ──
    try:
        dms = _surya.compute_dina_muhurtas(sr, ss, weekday, lang)
        result['dina_muhurtas'] = [
            {'number': m.number, 'name': m.name,
             'start': _fmt(m.starts_at), 'end': _fmt(m.ends_at),
             'is_abhijit': m.is_abhijit, 'is_durmuhurta': m.is_durmuhurta,
             'guna': m.guna}
            for m in dms
        ]
    except Exception: result['dina_muhurtas'] = []

    # ── 15 Ratri muhurtas ──
    try:
        next_sr = sr + timedelta(hours=24)
        rms = _surya.compute_ratri_muhurtas(ss, next_sr, lang)
        result['ratri_muhurtas'] = [
            {'number': m.number, 'name': m.name,
             'start': _fmt(m.starts_at), 'end': _fmt(m.ends_at),
             'is_nishita': m.is_nishita, 'is_brahma': m.is_brahma,
             'guna': m.guna}
            for m in rms
        ]
    except Exception: result['ratri_muhurtas'] = []

    # ── Hora table ──
    try:
        ht = _surya.compute_hora_table(sr, ss, sr + timedelta(hours=24), weekday, lang)
        result['hora_table'] = [
            {'planet': h.planet, 'number': h.number,
             'is_day': h.is_day_hora,
             'start': _fmt(h.starts_at), 'end': _fmt(h.ends_at)}
            for h in ht
        ]
    except Exception: result['hora_table'] = []

    # ── Disha Shoola, Agnivasa, Shivavasa ──
    try: result['disha_shoola'] = _consts.compute_disha_shoola(weekday, lang)
    except Exception: pass
    try: result['agnivasa']    = _consts.compute_agnivasa(tithi_idx, weekday, lang)
    except Exception: pass
    try: result['shivavasa']   = _consts.compute_shivavasa(tithi_idx, lang)
    except Exception: pass

    # ── Sankalpa (India only) ──
    try:
        if _sankp.is_indian_location(lat, lon):
            result['sankalpa'] = _sankp.generate_sankalpa(
                weekday=weekday, tithi_index=tithi_idx, nakshatra_index=nak_idx,
                yoga_index=yoga_idx, masa_index=masa_idx, paksha_index=paksha_idx,
                samvatsara_year=samvatsara_year,
                ritu_index=max(0, masa_idx // 2) % 6,
                ayana_idx=0, city=city, state=state, lat=lat, lon=lon, lang=lang
            )
    except Exception: pass

    return result
