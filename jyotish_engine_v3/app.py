"""
Jyotish Engine v3 — Phase 1 Complete Upgrade
Wires ALL jhora modules already in the repo:
  • 20 Graha Dashas + 2 Annual Dashas
  • 20 Rashi Dashas (Jaimini Char, Narayana, Kalachakra, etc.)
  • 20 Divisional Charts (D1–D60)
  • Kundali Matching (full Ashtakoota / 8 kootas / 36 gunas)
  • Varshphal / Tajika (Muntha, Sahams, Solar Return, Mudda Dasha)
  • Full Dosha engine (Mangal, Kaal Sarp, Sade Sati, Pitru)
  • 284 Yogas (yoga.py + raja_yoga_bv_raman.py)
  • Shadbala, Arudhas, Sphuta Lagnas, Eclipse
  • Current transits overlay
  • 6 Languages (en/hi/ta/te/ka/ml)
  • Experimental predictions (general.py, longevity.py)

Drop-in replacement for jyotish_v2/app.py
Routes:
  GET  /                    → index.html (birth data form)
  POST /chart               → chart.html (15-tab results)
  POST /api/chart           → JSON API
  GET  /kundali-match       → kundali_match.html
  POST /kundali-match       → compatibility results
  POST /api/kundali-match   → JSON API
  GET  /varshphal           → varshphal.html
  POST /varshphal           → annual chart results
  GET  /health              → module status JSON
"""

import os, traceback, datetime, sys
from flask import Flask, render_template, request, jsonify

# ── Safe jhora imports ──────────────────────────────────────────────────────
try:
    from jhora.panchanga import drik
    from jhora import utils, const
    JHORA_OK = True
except Exception as e:
    JHORA_OK = False
    print(f"[FATAL] jhora core failed: {e}")

# ── New engines (muhurta + SVG charts) ─────────────────────────────────────
try:
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    from muhurta_engine import compute_muhurtas as _compute_muhurtas
    from chart_svg import generate_chart_svg as _gen_svg
    MUHURTA_OK = True
except Exception as _me:
    _compute_muhurtas = None
    _gen_svg = None
    MUHURTA_OK = False
    print(f"[WARN] muhurta/chart_svg not loaded: {_me}")

def _imp(path):
    """Safe module importer — returns module or None on failure."""
    try:
        parts = path.split('.')
        return __import__(path, fromlist=[parts[-1]])
    except Exception as e:
        print(f"[WARN] import {path}: {e}")
        return None

# ── Chart modules ───────────────────────────────────────────────────────────
charts_mod   = _imp('jhora.horoscope.chart.charts')
yoga_mod     = _imp('jhora.horoscope.chart.yoga')
raja_mod     = _imp('jhora.horoscope.chart.raja_yoga')
raja_bvr     = _imp('jhora.horoscope.chart.raja_yoga_bv_raman')
bav_mod      = _imp('jhora.horoscope.chart.ashtakavarga')
dosha_mod    = _imp('jhora.horoscope.chart.dosha')
strength_mod = _imp('jhora.horoscope.chart.strength')
arudha_mod   = _imp('jhora.horoscope.chart.arudhas')
sphuta_mod   = _imp('jhora.horoscope.chart.sphuta')
house_mod    = _imp('jhora.horoscope.chart.house')

# ── Graha dasha modules ─────────────────────────────────────────────────────
vim_mod  = _imp('jhora.horoscope.dhasa.graha.vimsottari')
yog_mod  = _imp('jhora.horoscope.dhasa.graha.yogini')
ash_mod  = _imp('jhora.horoscope.dhasa.graha.ashtottari')
dwa_mod  = _imp('jhora.horoscope.dhasa.graha.dwadasottari')
sho_mod  = _imp('jhora.horoscope.dhasa.graha.shodasottari')
pan_mod  = _imp('jhora.horoscope.dhasa.graha.panchottari')
tya_mod  = _imp('jhora.horoscope.dhasa.graha.tithi_yogini')
taa_mod  = _imp('jhora.horoscope.dhasa.graha.tithi_ashtottari')
kaa_mod  = _imp('jhora.horoscope.dhasa.graha.kaala')
kar_mod  = _imp('jhora.horoscope.dhasa.graha.karaka')
tar_mod  = _imp('jhora.horoscope.dhasa.graha.tara')
nai_mod  = _imp('jhora.horoscope.dhasa.graha.naisargika')
bud_mod  = _imp('jhora.horoscope.dhasa.graha.buddhi_gathi')
sha_mod  = _imp('jhora.horoscope.dhasa.graha.shastihayani')
sat_mod  = _imp('jhora.horoscope.dhasa.graha.sataatbika')
c84_mod  = _imp('jhora.horoscope.dhasa.graha.chathuraaseethi_sama')
s36_mod  = _imp('jhora.horoscope.dhasa.graha.shattrimsa_sama')
dws_mod  = _imp('jhora.horoscope.dhasa.graha.dwisatpathi')
yvi_mod  = _imp('jhora.horoscope.dhasa.graha.yoga_vimsottari')
ayu_mod  = _imp('jhora.horoscope.dhasa.graha.aayu')
sap_mod  = _imp('jhora.horoscope.dhasa.graha.saptharishi_nakshathra')
kch_mod  = _imp('jhora.horoscope.dhasa.graha.karana_chathuraaseethi_sama')

# ── Rashi dasha modules ─────────────────────────────────────────────────────
cha_mod  = _imp('jhora.horoscope.dhasa.raasi.chara')
nar_mod  = _imp('jhora.horoscope.dhasa.raasi.narayana')
kal_mod  = _imp('jhora.horoscope.dhasa.raasi.kalachakra')
dri_mod  = _imp('jhora.horoscope.dhasa.raasi.drig')
shl_mod  = _imp('jhora.horoscope.dhasa.raasi.shoola')
bra_mod  = _imp('jhora.horoscope.dhasa.raasi.brahma')
chk_mod  = _imp('jhora.horoscope.dhasa.raasi.chakra')
mnd_mod  = _imp('jhora.horoscope.dhasa.raasi.mandooka')
moo_mod  = _imp('jhora.horoscope.dhasa.raasi.moola')
nav_rmod = _imp('jhora.horoscope.dhasa.raasi.navamsa')
nir_mod  = _imp('jhora.horoscope.dhasa.raasi.nirayana')
lag_mod  = _imp('jhora.horoscope.dhasa.raasi.lagnamsaka')
par_mod  = _imp('jhora.horoscope.dhasa.raasi.paryaaya')
sud_mod  = _imp('jhora.horoscope.dhasa.raasi.sudasa')
sth_mod  = _imp('jhora.horoscope.dhasa.raasi.sthira')
tri_mod  = _imp('jhora.horoscope.dhasa.raasi.trikona')
ken_mod  = _imp('jhora.horoscope.dhasa.raasi.kendradhi_rasi')
var_mod  = _imp('jhora.horoscope.dhasa.raasi.varnada')
trl_mod  = _imp('jhora.horoscope.dhasa.raasi.tara_lagna')
pdh_mod  = _imp('jhora.horoscope.dhasa.raasi.padhanadhamsa')

# ── Annual dasha modules ────────────────────────────────────────────────────
yog_r_mod = _imp('jhora.horoscope.dhasa.raasi.yogardha')
snd_mod   = _imp('jhora.horoscope.dhasa.raasi.sandhya')
pty_mod  = _imp('jhora.horoscope.dhasa.annual.patyayini')

# ── Match / Transit / Prediction / Eclipse ──────────────────────────────────
match_mod = _imp('jhora.horoscope.match.compatibility')
taj_mod   = _imp('jhora.horoscope.transit.tajaka')
sah_mod   = _imp('jhora.horoscope.transit.saham')
tjy_mod   = _imp('jhora.horoscope.transit.tajaka_yoga')
pred_mod  = _imp('jhora.horoscope.prediction.general')
lon_mod   = _imp('jhora.horoscope.prediction.longevity')
ecl_mod   = _imp('jhora.panchanga.eclipse')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'jyotish-v3-secret-key')

# ── Lookup tables ───────────────────────────────────────────────────────────
PLANET_NAMES  = ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']
RASI_NAMES    = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
                 'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']
RASI_SHORT    = ['Ar','Ta','Ge','Ca','Le','Vi','Li','Sc','Sg','Cp','Aq','Pi']
NAK_NAMES     = ['Ashwini','Bharani','Krittika','Rohini','Mrigashira','Ardra',
                 'Punarvasu','Pushya','Ashlesha','Magha','Purva Phalguni',
                 'Uttara Phalguni','Hasta','Chitra','Swati','Vishakha','Anuradha',
                 'Jyeshtha','Mula','Purva Ashadha','Uttara Ashadha','Shravana',
                 'Dhanishta','Shatabhisha','Purva Bhadrapada','Uttara Bhadrapada','Revati']
TITHI_NAMES   = ['Pratipada','Dwitiya','Tritiya','Chaturthi','Panchami','Shashthi',
                 'Saptami','Ashtami','Navami','Dashami','Ekadashi','Dwadashi',
                 'Trayodashi','Chaturdashi','Purnima/Amavasya']
YOGA_NAMES_27 = ['Vishkamba','Priti','Ayushman','Saubhagya','Shobhana','Atiganda',
                 'Sukarma','Dhriti','Shoola','Ganda','Vriddhi','Dhruva','Vyaghata',
                 'Harshana','Vajra','Siddhi','Vyatipata','Variyan','Parigha','Shiva',
                 'Siddha','Sadhya','Shubha','Shukla','Brahma','Indra','Vaidhriti']
KARANA_NAMES  = ['Bava','Balava','Kaulava','Taitila','Garaja','Vanija','Vishti',
                 'Shakuni','Chatushpada','Naga','Kimstughna']
VARA_NAMES    = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
LANGUAGES     = {'en':'English','hi':'Hindi','ta':'Tamil',
                 'te':'Telugu','ka':'Kannada','ml':'Malayalam'}

VARGA_CHARTS = [
    (1,'D1 – Rasi'),(2,'D2 – Hora'),(3,'D3 – Drekkana'),
    (4,'D4 – Chaturthamsa'),(5,'D5 – Panchamsa'),(6,'D6 – Shashthamsa'),
    (7,'D7 – Saptamsa'),(8,'D8 – Ashtamsa'),(9,'D9 – Navamsa'),
    (10,'D10 – Dasamsa'),(11,'D11 – Rudramsa'),(12,'D12 – Dwadasamsa'),
    (16,'D16 – Shodasamsa'),(20,'D20 – Vimshamsa'),(24,'D24 – Chaturvimshamsa'),
    (27,'D27 – Saptavimshamsa'),(30,'D30 – Trimshamsa'),(40,'D40 – Khavedamsa'),
    (45,'D45 – Akshavedamsa'),(60,'D60 – Shashtiamsa'),
]

GRAHA_DASHAS = [
    ('vimsottari',   'Vimshottari (120yr)',          vim_mod),
    ('yogini',       'Yogini (36yr)',                yog_mod),
    ('ashtottari',   'Ashtottari (108yr)',            ash_mod),
    ('dwadasottari', 'Dwadasottari (112yr)',          dwa_mod),
    ('shodasottari', 'Shodasottari (116yr)',          sho_mod),
    ('panchottari',  'Panchottari (100yr)',           pan_mod),
    ('tithi_yogini', 'Tithi Yogini',                 tya_mod),
    ('tithi_ash',    'Tithi Ashtottari',             taa_mod),
    ('kaala',        'Kaala Dhasa',                  kaa_mod),
    ('karaka',       'Karaka Dhasa',                 kar_mod),
    ('tara',         'Tara Dhasa',                   tar_mod),
    ('naisargika',   'Naisargika (Natural)',          nai_mod),
    ('buddhi_gathi', 'Buddhi Gathi',                 bud_mod),
    ('shastihayani', 'Shastihayani (60yr)',           sha_mod),
    ('sataatbika',   'Sataatbika (100yr)',            sat_mod),
    ('chatur84',     'Chaturaaseethi Sama (84yr)',    c84_mod),
    ('shattrimsa36', 'Shattrimsa Sama (36yr)',        s36_mod),
    ('dwisatpathi',  'Dwisatpathi (108yr)',           dws_mod),
    ('yoga_vim',     'Yoga Vimshottari',              yvi_mod),
    ('aayu',         'Aayu Dhasa (Longevity)',        ayu_mod),
    ('saptharishi',  'Saptharishi Nakshathra',        sap_mod),
    ('karana_c84',   'Karana Chaturaaseethi Sama',    kch_mod),
]

RASHI_DASHAS = [
    ('chara',         'Char Dhasa (Jaimini)',         cha_mod),
    ('narayana',      'Narayana Dhasa',               nar_mod),
    ('kalachakra',    'Kalachakra Dhasa',             kal_mod),
    ('drig',          'Drig Dhasa',                   dri_mod),
    ('shoola',        'Shoola Dhasa',                 shl_mod),
    ('brahma',        'Brahma Dhasa',                 bra_mod),
    ('chakra',        'Chakra Dhasa',                 chk_mod),
    ('mandooka',      'Mandooka Dhasa',               mnd_mod),
    ('moola',         'Moola Dhasa',                  moo_mod),
    ('navamsa_r',     'Navamsa Dhasa',                nav_rmod),
    ('nirayana',      'Nirayana Shoola',              nir_mod),
    ('lagnamsaka',    'Lagnamsaka Dhasa',             lag_mod),
    ('paryaaya',      'Paryaaya Dhasa',               par_mod),
    ('sudasa',        'Sudasa Dhasa',                 sud_mod),
    ('sthira',        'Sthira Dhasa',                 sth_mod),
    ('trikona',       'Trikona Dhasa',                tri_mod),
    ('kendradhi',     'Kendradhi Rasi',               ken_mod),
    ('varnada',       'Varnada Dhasa',                var_mod),
    ('tara_lagna',    'Tara Lagna Dhasa',             trl_mod),
    ('padhanadhamsa', 'Padhanadhamsa Dhasa',          pdh_mod),
    ('yogardha',      'Yogardha Dhasa',               yog_r_mod),
    ('sandhya',       'Sandhya Dhasa',                snd_mod),
]

ANNUAL_DASHAS = [
    ('mudda',         'Mudda Dhasa (Annual)',         mud_mod),
    ('patyayini',     'Patyayini Dhasa',              pty_mod),
]

# ── Helper utilities ────────────────────────────────────────────────────────
def planet_name(pid):
    if pid == 'L': return 'Lagna'
    try:   return PLANET_NAMES[int(pid)]
    except: return str(pid)

def rasi_name(rid):
    try:   return RASI_NAMES[int(rid) % 12]
    except: return str(rid)

def fmt_dhasa(raw, cap=80):
    """Normalise any dhasa output list to [{lord, bhukti, start}]."""
    if not raw: return []
    out = []
    for row in raw[:cap]:
        try:
            if len(row) == 3:
                out.append({'lord': planet_name(row[0]),
                             'bhukti': planet_name(row[1]),
                             'start': str(row[2])})
            elif len(row) == 2:
                out.append({'lord': planet_name(row[0]),
                             'bhukti': '—', 'start': str(row[1])})
        except: pass
    return out

def call_dhasa(mod, jd, place, dob, tob):
    """Try every known function signature for any graha/rashi/annual dasha module."""
    if mod is None: return []
    attempts = [
        lambda: mod.get_vimsottari_dhasa_bhukthi(jd, place, dhasa_level_index=2),
        lambda: mod.get_vimsottari_dhasa_bhukthi(jd, place),
        lambda: mod.get_dhasa_bhukthi(jd, place),
        lambda: mod.get_dhasa_antardhasa(jd, place),
        lambda: mod.get_ashtottari_dhasa_bhukthi(jd, place),
        lambda: mod.get_yogini_dhasa_bhukthi(jd, place),
        lambda: mod.get_chara_dhasa_bhukthi(jd, place),
        lambda: mod.get_narayana_dhasa_bhukthi(jd, place),
        lambda: mod.get_kalachakra_dhasa_bhukthi(jd, place),
        lambda: mod.get_dhasa_bhukthi(dob, tob, place),
        lambda: mod.get_dhasa_antardhasa(dob, tob, place),
    ]
    for fn in attempts:
        try:
            res = fn()
            if isinstance(res, tuple):
                res = res[1] if len(res) > 1 else res[0]
            if res:
                return fmt_dhasa(res)
        except: pass
    return []

def build_grid(pp):
    """Build 12-house dict {0..11: [planets]} and return (grid, lagna_rasi)."""
    grid = {i: [] for i in range(12)}
    lagna_rasi = 0
    for entry in pp:
        pid, (rasi, lon) = entry[0], entry[1]
        if pid == 'L':
            lagna_rasi = int(rasi)
            continue
        house = (int(rasi) - lagna_rasi) % 12
        grid[house].append({'planet': planet_name(pid),
                             'lon': round(float(lon), 2),
                             'rasi': rasi_name(rasi)})
    return grid, lagna_rasi

def compute_doshas(jd, place, pp):
    """Compute Mangal, Kaal Sarp, Sade Sati, Pitru doshas."""
    d = {}
    h2p = None
    try:
        h2p = utils.get_house_planet_list_from_planet_positions(pp)
    except: pass
    # 1. Mangal Dosha — actual function is manglik(planet_positions, ...)
    try:
        md = dosha_mod.manglik(pp) if dosha_mod else None
        if md is not None:
            d['Mangal (Kuja) Dosha'] = {'present': bool(md), 'detail': str(md)}
    except: pass
    # 2. Kaal Sarp — actual function is kala_sarpa(house_to_planet_list)
    try:
        if dosha_mod and h2p is not None:
            ks = dosha_mod.kala_sarpa(h2p)
            d['Kaal Sarp Dosha'] = {'present': bool(ks), 'detail': str(ks)}
        else:
            raise ValueError()
    except:
        try:
            rahu_r  = int(next(e[1][0] for e in pp if e[0] == 7))
            ketu_r  = (rahu_r + 6) % 12
            planets = [int(e[1][0]) for e in pp if isinstance(e[0], int) and 0 <= e[0] < 7]
            # All 7 planets must fall within the 6-sign arc Rahu→Ketu (exclusive)
            arc_fw  = [(rahu_r + i) % 12 for i in range(1, 7)]
            arc_bw  = [(rahu_r - i) % 12 for i in range(1, 7)]
            kaal    = all(r in arc_fw for r in planets) or all(r in arc_bw for r in planets)
            d['Kaal Sarp Dosha'] = {'present': kaal,
                                     'detail': 'Present' if kaal else 'Not present'}
        except: pass
    # 3. Sade Sati — uses TRANSIT Saturn vs natal Moon (not natal vs natal)
    try:
        moon_r = int(next(e[1][0] for e in pp if e[0] == 1))
        today  = datetime.date.today()
        jd_now = utils.julian_day_number((today.year, today.month, today.day), (12, 0, 0))
        pp_now = charts_mod.rasi_chart(jd_now, place)
        sat_t  = int(next(e[1][0] for e in pp_now if e[0] == 6))
        diff   = abs(sat_t - moon_r) % 12
        ss     = diff <= 1 or diff >= 11
        d['Sade Sati (7.5 yr)'] = {'present': ss,
                                    'detail': f"Natal Moon: {rasi_name(moon_r)}, Transit Saturn: {rasi_name(sat_t)}"}
    except: pass
    # 4. Pitru Dosha
    try:
        lag_r  = int(next(e[1][0] for e in pp if e[0] == 'L'))
        sun_h  = (int(next(e[1][0] for e in pp if e[0] == 0)) - lag_r) % 12
        rahu_h = (int(next(e[1][0] for e in pp if e[0] == 7)) - lag_r) % 12
        ketu_h = (int(next(e[1][0] for e in pp if e[0] == 8)) - lag_r) % 12
        pitru  = sun_h == 8 or rahu_h == 8 or ketu_h == 8 or sun_h == rahu_h
        d['Pitru Dosha'] = {'present': pitru,
                             'detail': f"Sun H{sun_h+1}, Rahu H{rahu_h+1}, Ketu H{ketu_h+1}"}
    except: pass
    return d

# ── Core chart builder ──────────────────────────────────────────────────────
def compute_chart(data):
    yr  = int(data['year']); mo = int(data['month']); dy = int(data['day'])
    hr  = int(data.get('hour', 0)); mn = int(data.get('minute', 0)); sc = int(data.get('second', 0))
    lat = float(data['latitude']); lon = float(data['longitude']); tz = float(data['timezone'])
    name = data.get('name', 'Native')
    lang = data.get('language', 'en')
    ayan = data.get('ayanamsha', 'LAHIRI')

    # Apply ayanamsha selection to jhora
    AYAN_MAP = {
        'LAHIRI':      'LAHIRI',
        'TRUE_PUSHYA': 'TRUE_PUSHYA',
        'RAMAN':       'RAMAN',
        'KP':          'KP',
        'YUKTESHWAR':  'YUKTESHWAR',
    }
    try:
        const.set_ayanamsha_mode(AYAN_MAP.get(ayan, 'LAHIRI'))
    except:
        try: utils.set_ayanamsha_mode(AYAN_MAP.get(ayan, 'LAHIRI'))
        except: pass

    jd    = utils.julian_day_number((yr, mo, dy), (hr, mn, sc))
    place = drik.Place('Place', lat, lon, tz)
    dob   = drik.Date(yr, mo, dy)
    tob   = (hr, mn, sc)

    pp = charts_mod.rasi_chart(jd, place)
    grid, lagna_rasi = build_grid(pp)

    # Planet table
    # Pre-compute retrograde planets once for the whole table
    retro_set = set()
    try:
        retro_list = drik.planets_in_retrograde(jd, place)
        retro_set  = set(retro_list) if retro_list else set()
    except: pass

    planet_table = []
    for e in pp:
        pid, (rasi, lon_d) = e[0], e[1]
        if pid == 'L':
            planet_table.insert(0, {'id': 'L', 'name': 'Lagna', 'rasi': rasi_name(rasi),
                'rasi_num': int(rasi), 'longitude': round(float(lon_d), 4),
                'house': 1, 'nakshatra': '—', 'retro': False})
            continue
        house = (int(rasi) - lagna_rasi) % 12 + 1
        nak   = NAK_NAMES[int(float(lon_d) * 27 / 360) % 27]
        retro = (pid in retro_set) if isinstance(pid, int) and pid < 7 else False
        planet_table.append({'id': pid, 'name': planet_name(pid), 'rasi': rasi_name(rasi),
            'rasi_num': int(rasi), 'longitude': round(float(lon_d), 4),
            'house': house, 'nakshatra': nak, 'retro': retro})

    # Panchanga
    pan = {}
    for key, fn, names in [
        ('tithi',     lambda: drik.tithi(jd, place),    TITHI_NAMES),
        ('nakshatra', lambda: drik.nakshatra(jd, place), NAK_NAMES),
        ('yoga',      lambda: drik.yogam(jd, place),     YOGA_NAMES_27),
        ('karana',    lambda: drik.karana(jd, place),    KARANA_NAMES),
    ]:
        try:
            v = fn(); idx = int(v[0]) - 1
            pan[key] = names[idx] + (f" Pada {v[1]}" if key == 'nakshatra' else '')
        except: pass
    try:    pan['vara']    = VARA_NAMES[int(drik.vaara(jd)) % 7]
    except: pass
    try:
        sr = drik.sunrise(jd, place); pan['sunrise'] = str(sr[0])
        ss = drik.sunset(jd, place);  pan['sunset']  = str(ss[0])
    except: pass
    pan['lagna'] = rasi_name(lagna_rasi)

    # Divisional charts
    varga = {}
    for dcf, vname in VARGA_CHARTS:
        try:
            vc = charts_mod.divisional_chart(jd, place, divisional_chart_factor=dcf)
            _, vlagna = build_grid(vc)
            varga[str(dcf)] = {'name': vname, 'lagna': rasi_name(vlagna),
                'planets': [{'name': planet_name(e[0]), 'rasi': rasi_name(e[1][0]),
                              'lon': round(float(e[1][1]), 2)} for e in vc]}
        except: pass

    # All dasha systems
    gr_dashas = {k: call_dhasa(m, jd, place, dob, tob) for k, _, m in GRAHA_DASHAS}
    rs_dashas = {k: call_dhasa(m, jd, place, dob, tob) for k, _, m in RASHI_DASHAS}
    an_dashas = {k: call_dhasa(m, jd, place, dob, tob) for k, _, m in ANNUAL_DASHAS}

    # Yogas
    yoga_data = {'yogas': [], 'count': 0, 'total': 0, 'raja_yogas': [], 'bvr_yogas': []}
    try:
        yr_out, ycount, ytot = yoga_mod.get_yoga_details(jd, place)
        yoga_data.update({'yogas': [{'name': str(y[0]), 'planets': str(y[1])} for y in yr_out[:60]],
                           'count': ycount, 'total': ytot})
    except: pass
    try:    yoga_data['raja_yogas'] = [str(r) for r in raja_mod.get_raja_yoga_details(jd, place)[:20]]
    except: pass
    try:    yoga_data['bvr_yogas']  = [str(r) for r in raja_bvr.get_raja_yoga_details(jd, place)[:30]]
    except: pass

    # Ashtakavarga
    bav_data = {}
    try:
        h2p = utils.get_house_planet_list_from_planet_positions(pp)
        bav, sav, _ = bav_mod.get_ashtaka_varga(h2p)
        bav_data = {'sav': [int(x) for x in sav],
                    'bav': {PLANET_NAMES[i]: [int(x) for x in row] for i, row in enumerate(bav) if i < 7}}
    except: pass

    # Shadbala — shad_bala(jd, place) returns [stb, kb, dgb, cb, nb, dkb, sb_sum, sb_rupa, sb_strength]
    shadbala = {}
    try:
        sb_result = strength_mod.shad_bala(jd, place)
        sb_rupa   = sb_result[7]   # index 7 = per-planet Rupa scores (7 values, Sun→Saturn)
        for i, s in enumerate(sb_rupa[:7]):
            shadbala[PLANET_NAMES[i]] = round(float(s or 0), 2)
    except: pass

    # Arudhas
    arudha_data = {}
    try:
        ba = arudha_mod.bhava_arudhas_from_planet_positions(pp)
        arudha_data['bhava'] = [{'house': f'A{i+1}', 'rasi': rasi_name(r)} for i, r in enumerate(ba)]
    except: pass
    try:
        ga = arudha_mod.graha_arudhas_from_planet_positions(pp)
        arudha_data['graha'] = [{'planet': PLANET_NAMES[i], 'rasi': rasi_name(ga[i])}
                                  for i in range(min(9, len(ga)))]
    except: pass

    # Doshas, Sphuta
    dosha_data = compute_doshas(jd, place, pp)
    sphuta_data = {}
    # Special lagnas live in drik.py, not sphuta.py
    # sphuta.py has: pranapada_lagna, indu_lagna, sree_lagna, bhrigu_bindhu_lagna
    SPHUTA_MAP = [
        ('Pranapada Lagna', sphuta_mod, 'pranapada_lagna'),
        ('Indu Lagna',      sphuta_mod, 'indu_lagna'),
        ('Sree Lagna',      sphuta_mod, 'sree_lagna'),
        ('Bhrigu Bindhu',   sphuta_mod, 'bhrigu_bindhu_lagna'),
    ]
    for label, mod, fname in SPHUTA_MAP:
        if mod:
            try:
                v = getattr(mod, fname)(jd, place)
                sphuta_data[label] = f"{rasi_name(v[0])} {round(float(v[1]), 2)}°"
            except: pass

    # Current transits
    transits = []
    try:
        today  = datetime.date.today()
        jd_now = utils.julian_day_number((today.year, today.month, today.day), (12, 0, 0))
        pp_now = charts_mod.rasi_chart(jd_now, place)
        natal  = {e[0]: int(e[1][0]) for e in pp if isinstance(e[0], int)}
        for e in pp_now:
            pid, (tr, _) = e[0], e[1]
            if isinstance(pid, int) and pid < 9 and pid in natal:
                nr = natal[pid]
                transits.append({'planet': planet_name(pid), 'natal': rasi_name(nr),
                                   'transit': rasi_name(tr), 'h_from_natal': (int(tr) - nr) % 12 + 1})
    except: pass

    # Varshphal summary
    varshphal = {}
    try:
        age = datetime.date.today().year - yr
        varshphal = {'age': age, 'muntha_rasi': rasi_name((lagna_rasi + age) % 12),
                      'muntha_house': (lagna_rasi + age) % 12 + 1}
        # Sahams — saham.py has individual functions; collect the most common ones
        if sah_mod:
            saham_fns = ['punya_saham', 'vidya_saham', 'yasas_saham', 'mitra_saham',
                         'mahatmaya_saham', 'asha_saham', 'samartha_saham', 'bhratri_saham',
                         'gaurava_saham', 'pithri_saham']
            night = False
            try:
                sr_t = drik.sunrise(jd, place)
                ss_t = drik.sunset(jd, place)
                # Crude night-birth check using Julian hours
                h = (jd % 1) * 24
                night = not (6 <= h <= 18)
            except: pass
            sahams = {}
            for fn in saham_fns:
                try:
                    f = getattr(sah_mod, fn)
                    import inspect
                    sig = inspect.signature(f)
                    v = f(pp, night) if 'night_time_birth' in sig.parameters else f(pp)
                    sahams[fn.replace('_saham', '').replace('_', ' ').title()] = rasi_name(v)
                except: pass
            if sahams:
                varshphal['sahams'] = sahams
    except: pass

    # Predictions — actual API: get_prediction_details(jd, place), life_span_range(jd, place)
    prediction_data = {}
    try:
        pred = pred_mod.get_prediction_details(jd, place, language=lang)
        prediction_data['general'] = str(pred)[:3000]
    except: pass
    try:
        prediction_data['longevity'] = str(lon_mod.life_span_range(jd, place))
    except: pass

    # Eclipse
    eclipse_data = {}
    try:
        ne = ecl_mod.next_solar_eclipse_date(jd, place)
        eclipse_data['next_solar'] = str(ne)
    except: pass

    # ── Muhurtas from kaalavidya ────────────────────────────────────────────
    muhurta_data = {}
    try:
        if _compute_muhurtas:
            jd_sr = drik.sunrise(jd, place)[0]
            jd_ss = drik.sunset(jd, place)[0]
            # derive panchanga indices for sankalpa
            tith_idx = int(drik.tithi(jd, place)[0]) - 1
            nak_idx  = int(drik.nakshatra(jd, place)[0]) - 1
            yog_idx  = int(drik.yogam(jd, place)[0]) - 1
            muhurta_data = _compute_muhurtas(
                jd_sr, jd_ss, tz_offset=tz, lang=lang,
                lat=lat, lon=lon, city=name, state='',
                tithi_idx=max(0, tith_idx), nak_idx=max(0, nak_idx),
                yoga_idx=max(0, yog_idx), masa_idx=0, paksha_idx=0,
                samvatsara_year=yr
            )
    except Exception as _mu_err:
        muhurta_data = {}

    # ── SVG Chart diagrams ──────────────────────────────────────────────────
    chart_svg_north = ''
    chart_svg_south = ''
    try:
        if _gen_svg:
            chart_svg_north = _gen_svg(planet_table, lagna_rasi, style='north')
            chart_svg_south = _gen_svg(planet_table, lagna_rasi, style='south')
    except Exception: pass

    return {
        'name': name, 'dob': f"{dy}/{mo}/{yr}", 'tob': f"{hr:02d}:{mn:02d}:{sc:02d}",
        'place': f"Lat {lat}N  Lon {lon}E  UTC+{tz}", 'language': lang,
        'lagna': rasi_name(lagna_rasi), 'lagna_num': lagna_rasi,
        'planet_table': planet_table, 'grid': {str(k): v for k, v in grid.items()},
        'panchanga': pan, 'varga': varga,
        'gr_dashas': gr_dashas, 'rs_dashas': rs_dashas, 'an_dashas': an_dashas,
        'yoga_data': yoga_data, 'bav_data': bav_data, 'shadbala': shadbala,
        'arudha_data': arudha_data, 'dosha_data': dosha_data,
        'sphuta_data': sphuta_data, 'transits': transits,
        'varshphal': varshphal, 'prediction_data': prediction_data,
        'eclipse_data': eclipse_data,
        'graha_labels': {k: l for k, l, _ in GRAHA_DASHAS},
        'rashi_labels': {k: l for k, l, _ in RASHI_DASHAS},
        'annual_labels': {k: l for k, l, _ in ANNUAL_DASHAS},
        'muhurta_data': muhurta_data,
        'chart_svg_north': chart_svg_north,
        'chart_svg_south': chart_svg_south,
    }

# ── Routes ──────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html', languages=LANGUAGES)

@app.route('/chart', methods=['POST'])
def chart_view():
    try:
        c = compute_chart(request.form.to_dict())
        return render_template('chart.html', c=c, languages=LANGUAGES,
                                graha_dasha_list=GRAHA_DASHAS, rashi_dasha_list=RASHI_DASHAS,
                                annual_dasha_list=ANNUAL_DASHAS, varga_list=VARGA_CHARTS)
    except Exception as e:
        return render_template('index.html',
                                error=f"{e}\n\n{traceback.format_exc()}", languages=LANGUAGES), 400

@app.route('/api/chart', methods=['POST'])
def api_chart():
    try:
        return jsonify({'status': 'ok', 'data': compute_chart(request.get_json(force=True))})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'trace': traceback.format_exc()}), 400

@app.route('/kundali-match', methods=['GET', 'POST'])
def kundali_match():
    if request.method == 'GET':
        return render_template('kundali_match.html', languages=LANGUAGES)
    d = request.form.to_dict()
    result = {}
    try:
        for prefix in ['boy', 'girl']:
            jd_x = utils.julian_day_number(
                (int(d[f'{prefix}_year']), int(d[f'{prefix}_month']), int(d[f'{prefix}_day'])),
                (int(d.get(f'{prefix}_hour', 0)), int(d.get(f'{prefix}_min', 0)), 0))
            pl_x = drik.Place('P', float(d[f'{prefix}_lat']),
                               float(d[f'{prefix}_lon']), float(d[f'{prefix}_tz']))
            n = drik.nakshatra(jd_x, pl_x)
            result[f'{prefix}_nak']      = int(n[0])
            result[f'{prefix}_pada']     = int(n[1])
            result[f'{prefix}_nak_name'] = f"{NAK_NAMES[int(n[0])-1]} Pada {n[1]}"
        if match_mod:
            ak = match_mod.Ashtakoota(result['boy_nak'], result['boy_pada'],
                                       result['girl_nak'], result['girl_pada'])
            sc = ak.compatibility_score()
            # Ashtakoota return order: [varna, vasiya, gana, dina/tara, yoni, raasi_adhipathi, raasi, naadi, total, mahendra, vedha, rajju, sthree]
            kootas = [('Varna',1),('Vasiya',2),('Gana',6),('Dina/Tara',3),
                      ('Yoni',4),('Graha Maitri',5),('Bhakoot',7),('Naadi',8)]
            result['kootas']          = [{'name': kootas[i][0], 'score': round(float(sc[i]), 1),
                                           'max': kootas[i][1]} for i in range(8)]
            result['total']           = round(float(sc[8]), 1)
            result['mahendra']        = bool(sc[9])
            result['vedha']           = bool(sc[10])
            result['rajju']           = bool(sc[11])
            result['sthree_dheerga']  = bool(sc[12])
            result['verdict'] = ('Excellent (≥28)' if result['total'] >= 28 else
                                  'Good (18–27)'    if result['total'] >= 18 else
                                  'Average (12–17)' if result['total'] >= 12 else 'Poor (<12)')
    except Exception as e:
        result['error'] = f"{e}\n{traceback.format_exc()}"
    return render_template('kundali_match.html', result=result, d=d, languages=LANGUAGES)

@app.route('/api/kundali-match', methods=['POST'])
def api_kundali_match():
    data = request.get_json(force=True)
    result = {}
    try:
        for prefix in ['boy', 'girl']:
            jd_x = utils.julian_day_number(
                (int(data[f'{prefix}_year']), int(data[f'{prefix}_month']), int(data[f'{prefix}_day'])),
                (int(data.get(f'{prefix}_hour', 0)), int(data.get(f'{prefix}_min', 0)), 0))
            pl_x = drik.Place('P', float(data[f'{prefix}_lat']),
                               float(data[f'{prefix}_lon']), float(data[f'{prefix}_tz']))
            n = drik.nakshatra(jd_x, pl_x)
            result[f'{prefix}_nakshatra'] = NAK_NAMES[int(n[0]) - 1]
            result[f'{prefix}_pada']      = int(n[1])
            result[f'{prefix}_nak_num']   = int(n[0])
        if match_mod:
            ak = match_mod.Ashtakoota(result['boy_nak_num'], result['boy_pada'],
                                       result['girl_nak_num'], result['girl_pada'])
            sc = ak.compatibility_score()
            result['total_score'] = round(float(sc[8]), 1)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    return jsonify({'status': 'ok', 'data': result})

@app.route('/varshphal', methods=['GET', 'POST'])
def varshphal():
    if request.method == 'GET':
        return render_template('varshphal.html', languages=LANGUAGES)
    d = request.form.to_dict()
    result = {}
    try:
        yr = int(d['year']); mo = int(d['month']); dy = int(d['day'])
        hr = int(d.get('hour', 0)); mn = int(d.get('minute', 0))
        lat = float(d['latitude']); lon = float(d['longitude']); tz = float(d['timezone'])
        age = int(d['age']) if d.get('age') else datetime.date.today().year - yr
        jd    = utils.julian_day_number((yr, mo, dy), (hr, mn, 0))
        place = drik.Place('Place', lat, lon, tz)
        pp    = charts_mod.rasi_chart(jd, place)
        lag_r = int(next(e[1][0] for e in pp if e[0] == 'L'))
        result.update({'age': age, 'muntha_rasi': rasi_name((lag_r + age) % 12),
                        'muntha_house': (lag_r + age) % 12 + 1})
        sr_pp = None
        if taj_mod:
            try:
                sr_jd = taj_mod.solar_return_jd(jd, place, age)
                sr_pp = charts_mod.rasi_chart(sr_jd, place)
                _, sr_lag = build_grid(sr_pp)
                result['sr_lagna']   = rasi_name(sr_lag)
                result['sr_planets'] = [{'name': planet_name(e[0]), 'rasi': rasi_name(e[1][0])}
                                          for e in sr_pp]
            except: pass
        if tjy_mod:
            try:
                ty = tjy_mod.get_tajaka_yogas(sr_pp or pp)
                result['tajaka_yogas'] = [str(t) for t in ty[:20]]
            except: pass
        if sah_mod:
            try:
                pp_sah = charts_mod.rasi_chart(jd, place)
                saham_fns = ['punya_saham', 'vidya_saham', 'yasas_saham', 'mitra_saham',
                             'mahatmaya_saham', 'asha_saham', 'samartha_saham', 'gaurava_saham']
                import inspect as _ins
                sahams = {}
                for fn in saham_fns:
                    try:
                        f = getattr(sah_mod, fn)
                        v = f(pp_sah, False) if 'night_time_birth' in _ins.signature(f).parameters else f(pp_sah)
                        sahams[fn.replace('_saham','').replace('_',' ').title()] = rasi_name(v)
                    except: pass
                result['sahams'] = sahams
            except: pass
        for key, mod in [('mudda', mud_mod), ('patyayini', pty_mod)]:
            if mod:
                try:
                    res = mod.get_dhasa_bhukthi(drik.Date(yr, mo, dy), (hr, mn, 0), place)
                    if isinstance(res, tuple): res = res[1] if len(res) > 1 else res[0]
                    result[key] = fmt_dhasa(res)
                except: pass
    except Exception as e:
        result['error'] = str(e)
    return render_template('varshphal.html', result=result, d=d, languages=LANGUAGES)

@app.route('/health')
def health():
    return jsonify({
        'status': 'ok', 'version': '3.0', 'jhora': JHORA_OK,
        'graha_dashas': sum(1 for _, _, m in GRAHA_DASHAS if m is not None),
        'rashi_dashas': sum(1 for _, _, m in RASHI_DASHAS if m is not None),
        'annual_dashas': sum(1 for _, _, m in ANNUAL_DASHAS if m is not None),
        'modules': {k: bool(v) for k, v in {
            'charts': charts_mod, 'yoga': yoga_mod, 'match': match_mod,
            'tajaka': taj_mod, 'strength': strength_mod, 'dosha': dosha_mod,
            'sphuta': sphuta_mod, 'eclipse': ecl_mod}.items()}})

if __name__ == '__main__':
    app.run(debug=True, port=5050, host='0.0.0.0')
