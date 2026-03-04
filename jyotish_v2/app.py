"""
Jyotish Engine — Flask web application
Uses real PyJHora source for all Vedic astrology calculations.
"""
import os, sys, traceback
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, redirect, url_for

# Ensure jhora package is importable
sys.path.insert(0, os.path.dirname(__file__))

app = Flask(__name__)

# ── Lazy-load PyJHora so import errors surface clearly ──────────────────────
_jhora_ready = False
_jhora_error = None

def _init_jhora():
    global _jhora_ready, _jhora_error
    if _jhora_ready:
        return True
    try:
        from jhora import utils, const
        utils.set_language('en')
        _jhora_ready = True
        return True
    except Exception as e:
        _jhora_error = str(e)
        return False

# ── Constants & helpers ──────────────────────────────────────────────────────
SIGN_NAMES = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
              "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
SIGN_SYMBOLS= ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]
PLANET_NAMES = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]
PLANET_SYMBOLS= ["☉","☽","♂","☿","♃","♀","♄","☊","☋"]
DAY_NAMES = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
TITHI_NAMES = [
    "Pratipada","Dvitiya","Tritiya","Chaturthi","Panchami","Shashthi","Saptami",
    "Ashtami","Navami","Dashami","Ekadashi","Dwadashi","Trayodashi","Chaturdashi",
    "Purnima/Amavasya"
]
NAKSHATRA_NAMES = [
    "Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu",
    "Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta",
    "Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha",
    "Uttara Ashadha","Shravana","Dhanishtha","Shatabhisha","Purva Bhadrapada",
    "Uttara Bhadrapada","Revati"
]
YOGA_NAMES = [
    "Vishkambha","Priti","Ayushman","Saubhagya","Shobhana","Atiganda","Sukarma",
    "Dhriti","Shula","Ganda","Vriddhi","Dhruva","Vyaghata","Harshana","Vajra",
    "Siddhi","Vyatipata","Variyan","Parigha","Shiva","Siddha","Sadhya","Shubha",
    "Shukla","Brahma","Indra","Vaidhriti"
]
KARANA_NAMES = [
    "Bava","Balava","Kaulava","Taitila","Garija","Vanija","Vishti",
    "Shakuni","Chatushpada","Naga","Kimsthugna"
]
PLANET_LORDS = {0:"Sun",1:"Moon",2:"Mars",3:"Mercury",4:"Jupiter",5:"Venus",
                6:"Saturn",7:"Rahu",8:"Ketu"}

DIGNITY_TABLE = {
    # (planet_id: {sign_id: dignity_name})
    0: {4:"Own",1:"Exalted",7:"Debilitated",0:"Friendly"},   # Sun
    1: {3:"Own",1:"Exalted",7:"Debilitated"},                  # Moon
    2: {0:"Own",7:"Own",3:"Exalted",9:"Debilitated"},          # Mars
    3: {2:"Own",5:"Own",5:"Exalted",11:"Debilitated"},         # Mercury
    4: {8:"Own",11:"Own",3:"Exalted",9:"Debilitated"},         # Jupiter
    5: {1:"Own",6:"Own",11:"Exalted",5:"Debilitated"},         # Venus
    6: {9:"Own",10:"Own",6:"Exalted",0:"Debilitated"},         # Saturn
}

def get_dignity(planet_id, sign_id):
    if planet_id not in DIGNITY_TABLE:
        return ""
    d = DIGNITY_TABLE[planet_id]
    return d.get(sign_id, "")

def nakshatra_lord(nak_num):
    """Return lord planet name for nakshatra number (1-27)"""
    lords = [7,5,0,1,2,7,4,6,3,   # Rahu Venus Sun Moon Mars...
             7,5,0,1,2,7,4,6,3,
             7,5,0,1,2,7,4,6,3]
    if 1 <= nak_num <= 27:
        return PLANET_NAMES[lords[nak_num-1]]
    return ""

def fmt_dms(deg):
    """Format decimal degrees as D°M'S'' """
    d = int(deg)
    m = int((deg - d) * 60)
    s = int(((deg - d) * 60 - m) * 60)
    return f"{d}°{m:02d}'{s:02d}\""

def dasha_lord_name(lord_id):
    if lord_id == 'L': return 'Lagna'
    try:
        return PLANET_NAMES[int(lord_id)]
    except:
        return str(lord_id)

# ── Core chart builder ───────────────────────────────────────────────────────
def build_chart(year, month, day, hour, minute, second, lat, lon, tz, name):
    from jhora.panchanga import drik
    from jhora.horoscope.chart import charts, yoga as yoga_mod, ashtakavarga, house
    from jhora.horoscope.dhasa.graha import vimsottari
    from jhora import const, utils

    dob = drik.Date(int(year), int(month), int(day))
    tob = (int(hour), int(minute), int(second))
    place = drik.Place(name, float(lat), float(lon), float(tz))
    jd = utils.julian_day_number(dob, tob)

    # ── Rasi chart ────────────────────────────────────────────────────────
    planet_positions = charts.rasi_chart(jd, place)
    h_to_p = utils.get_house_planet_list_from_planet_positions(planet_positions)

    # ── Ascendant ─────────────────────────────────────────────────────────
    asc_sign, asc_long = planet_positions[0][1]
    asc_full_long = asc_sign * 30 + asc_long

    # ── Panchanga ─────────────────────────────────────────────────────────
    try:
        _tithi = drik.tithi(jd, place)
        tithi_num = _tithi[0]
        paksha = "Shukla" if tithi_num <= 15 else "Krishna"
        tithi_idx = (tithi_num - 1) % 15
        tithi_name = f"{paksha} {TITHI_NAMES[tithi_idx]}"
    except:
        tithi_name = "Unknown"

    try:
        _nak = drik.nakshatra(jd, place)
        nak_num, nak_pada = _nak[0], _nak[1]
        nak_name = NAKSHATRA_NAMES[nak_num-1] if 1 <= nak_num <= 27 else "Unknown"
        nak_lord = nakshatra_lord(nak_num)
        nakshatra_str = f"{nak_name} (Pada {nak_pada}, Lord: {nak_lord})"
    except:
        nakshatra_str = "Unknown"
        nak_num = 1

    try:
        _yoga = drik.yogam(jd, place)
        yoga_num = _yoga[0]
        yoga_panchanga = YOGA_NAMES[yoga_num-1] if 1 <= yoga_num <= 27 else "Unknown"
    except:
        yoga_panchanga = "Unknown"

    try:
        _karana = drik.karana(jd, place)
        kar_num = _karana[0]
        karana_name = KARANA_NAMES[(kar_num-1) % 11] if kar_num >= 1 else "Unknown"
    except:
        karana_name = "Unknown"

    try:
        vaara_idx = drik.vaara(jd)
        vaara_name = DAY_NAMES[vaara_idx % 7]
    except:
        vaara_name = "Unknown"

    # ── Retrograde planets ────────────────────────────────────────────────
    try:
        retro_list = drik.planets_in_retrograde(jd, place)
    except:
        retro_list = []

    # ── Planet data ───────────────────────────────────────────────────────
    planets = []
    house_occupants = [[] for _ in range(12)]

    for p, (h, long) in planet_positions:
        if p == const._ascendant_symbol:
            house_occupants[h].append("Lagna")
            continue
        full_long = h * 30 + long
        try:
            nak_info = drik.nakshatra_pada(full_long)
            p_nak_num = nak_info[0]
            p_nak_pada = nak_info[1]
            p_nak_name = NAKSHATRA_NAMES[p_nak_num-1] if 1 <= p_nak_num <= 27 else ""
        except:
            p_nak_name, p_nak_pada = "", ""

        dignity = get_dignity(p, h)
        is_retro = p in retro_list
        planet_entry = {
            'id': p,
            'name': PLANET_NAMES[p],
            'symbol': PLANET_SYMBOLS[p],
            'sign': SIGN_NAMES[h],
            'sign_symbol': SIGN_SYMBOLS[h],
            'sign_num': h,
            'longitude': long,
            'full_longitude': full_long,
            'longitude_str': fmt_dms(long),
            'nakshatra': p_nak_name,
            'pada': p_nak_pada,
            'retrograde': is_retro,
            'dignity': dignity,
            'house': (h - asc_sign) % 12 + 1,
        }
        planets.append(planet_entry)
        house_occupants[h].append(("R " if is_retro else "") + PLANET_NAMES[p])

    planets.sort(key=lambda x: x['id'])

    # ── Houses ─────────────────────────────────────────────────────────────
    HOUSE_PURPOSES = {
        1:"Self & Body", 2:"Wealth & Family", 3:"Siblings & Courage",
        4:"Home & Mother", 5:"Children & Intellect", 6:"Enemies & Debts",
        7:"Partnership", 8:"Longevity & Transformation", 9:"Fortune & Dharma",
        10:"Career & Status", 11:"Gains & Aspirations", 12:"Liberation & Losses"
    }
    HOUSE_QUALITY = {1:"Kendra",2:"Panapara",3:"Apoklima",4:"Kendra",
                     5:"Trikona",6:"Dusthana",7:"Kendra",8:"Dusthana",
                     9:"Trikona",10:"Kendra",11:"Upachaya",12:"Dusthana"}
    houses_data = []
    for i in range(12):
        sign_idx = (asc_sign + i) % 12
        # Find lord of this sign
        sign_lords = [0,1,2,3,4,5,6,2,4,6,6,4]  # sign -> lord index (simplified)
        h_lord_map = {0:0,1:1,2:2,3:1,4:0,5:5,6:5,7:2,8:4,9:6,10:6,11:4}
        lord_id = h_lord_map.get(sign_idx, 0)
        occ = house_occupants[sign_idx]
        houses_data.append({
            'number': i + 1,
            'sign': SIGN_NAMES[sign_idx],
            'sign_symbol': SIGN_SYMBOLS[sign_idx],
            'sign_num': sign_idx,
            'lord': PLANET_NAMES[lord_id],
            'occupants': occ,
            'purpose': HOUSE_PURPOSES.get(i+1, ""),
            'quality': HOUSE_QUALITY.get(i+1, ""),
        })

    # ── Vimshottari Dasha ─────────────────────────────────────────────────
    dasha_data = []
    try:
        vim_bal, raw_dashas = vimsottari.get_vimsottari_dhasa_bhukthi(
            jd, place, dhasa_level_index=2)
        # vim_bal: (lord_id, balance_years)
        # raw_dashas: [[maha_lord, antara_lord, start_str], ...]
        today_jd = utils.julian_day_number(
            drik.Date(date.today().year, date.today().month, date.today().day), (0,0,0))

        # Group by mahadasha
        maha_groups = {}
        for row in raw_dashas:
            ml = row[0]; al = row[1]; start_str = row[2]
            if ml not in maha_groups:
                maha_groups[ml] = {'lord': ml, 'antardashas': [], 'start_jd': None}
            try:
                start_jd_val = float(start_str) if isinstance(start_str, (int,float)) else None
                if start_jd_val and maha_groups[ml]['start_jd'] is None:
                    maha_groups[ml]['start_jd'] = start_jd_val
            except:
                pass
            maha_groups[ml]['antardashas'].append({'lord': al, 'start': start_str})

        for ml, mg in maha_groups.items():
            is_current = False
            if mg['start_jd']:
                is_current = mg['start_jd'] <= today_jd
            dasha_data.append({
                'lord': ml,
                'lord_name': dasha_lord_name(ml),
                'years': vimsottari.vimsottari_dict.get(ml, 0),
                'current': is_current,
                'antardashas': mg['antardashas'][:9],
            })

        # Mark balance
        balance_lord = vim_bal[0] if vim_bal else None
        balance_years = vim_bal[1] if len(vim_bal) > 1 else 0
    except Exception as e:
        balance_lord, balance_years = None, 0

    # ── Yogas ─────────────────────────────────────────────────────────────
    yogas_list = []
    try:
        yoga_results, found_count, _ = yoga_mod.get_yoga_details(jd, place)
        for yoga_key, yoga_val in list(yoga_results.items())[:25]:
            yogas_list.append({
                'name': yoga_key.split('-')[-1] if '-' in yoga_key else yoga_key,
                'chart': yoga_key.split('-')[0] if '-' in yoga_key else 'D1',
                'details': yoga_val if isinstance(yoga_val, str) else str(yoga_val),
            })
    except Exception as e:
        pass

    # ── Ashtakavarga ──────────────────────────────────────────────────────
    bav_data = {}
    sav_data = []
    try:
        bav, sav, _ = ashtakavarga.get_ashtaka_varga(h_to_p)
        planet_labels = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Lagna"]
        for i, scores in enumerate(bav[:7]):
            bav_data[planet_labels[i]] = scores
        sav_data = list(sav)
    except:
        pass

    # ── Divisional Charts ─────────────────────────────────────────────────
    VARGA_NAMES = {2:"Hora",3:"Drekkana",9:"Navamsa",10:"Dasamsa",
                   12:"Dwadasamsa",16:"Shodasamsa",27:"Nakshatramsa",60:"Shashtyamsa"}
    varga_charts = {}
    for dcf, vname in [(9,"Navamsa"),(10,"Dasamsa"),(2,"Hora"),(3,"Drekkana"),(12,"Dwadasamsa")]:
        try:
            vpp = charts.divisional_chart(jd, place, divisional_chart_factor=dcf)
            vasc_sign = vpp[0][1][0]
            vhouse_occ = [[] for _ in range(12)]
            for vp, (vh, vl) in vpp:
                if vp == const._ascendant_symbol:
                    vhouse_occ[vh].append("Lagna")
                else:
                    vhouse_occ[vh].append(PLANET_NAMES[vp])
            varga_charts[dcf] = {
                'name': vname,
                'ascendant': SIGN_NAMES[vasc_sign],
                'houses': [
                    {
                        'number': i+1,
                        'sign': SIGN_NAMES[(vasc_sign+i)%12],
                        'occupants': vhouse_occ[(vasc_sign+i)%12]
                    }
                    for i in range(12)
                ]
            }
        except:
            pass

    return {
        'name': name or "Native",
        'birth': {
            'date': f"{day:02d} {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][month-1]} {year}",
            'time': f"{hour:02d}:{minute:02d}:{second:02d}",
            'lat': f"{abs(lat):.4f}°{'N' if lat>=0 else 'S'}",
            'lon': f"{abs(lon):.4f}°{'E' if lon>=0 else 'W'}",
            'tz': f"UTC{'+' if tz>=0 else ''}{tz}",
        },
        'ascendant': {
            'sign': SIGN_NAMES[asc_sign],
            'sign_symbol': SIGN_SYMBOLS[asc_sign],
            'sign_num': asc_sign,
            'longitude': asc_long,
            'longitude_str': fmt_dms(asc_long),
        },
        'panchanga': {
            'tithi': tithi_name,
            'nakshatra': nakshatra_str,
            'yoga': yoga_panchanga,
            'karana': karana_name,
            'vaara': vaara_name,
        },
        'planets': planets,
        'houses': houses_data,
        'dashas': dasha_data,
        'dasha_balance': {
            'lord': dasha_lord_name(balance_lord) if balance_lord is not None else "",
            'years': round(float(balance_years), 2) if balance_years else 0
        },
        'yogas': yogas_list,
        'ashtakavarga': {
            'bav': bav_data,
            'sav': sav_data,
            'signs': SIGN_NAMES,
        },
        'vargas': varga_charts,
    }

# ── Routes ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    ready = _init_jhora()
    return render_template('index.html', error=_jhora_error if not ready else None)

@app.route('/chart', methods=['POST'])
def chart():
    _init_jhora()
    try:
        year   = int(request.form['year'])
        month  = int(request.form['month'])
        day    = int(request.form['day'])
        hour   = int(request.form.get('hour', 0))
        minute = int(request.form.get('minute', 0))
        second = int(request.form.get('second', 0))
        lat    = float(request.form['latitude'])
        lon    = float(request.form['longitude'])
        tz     = float(request.form['timezone'])
        name   = request.form.get('name', '').strip() or "Native"
        data   = build_chart(year, month, day, hour, minute, second, lat, lon, tz, name)
        return render_template('chart.html', chart=data)
    except Exception as e:
        return render_template('index.html',
                               error=f"Calculation error: {e}\n{traceback.format_exc()}")

@app.route('/api/chart', methods=['POST'])
def api_chart():
    _init_jhora()
    try:
        body   = request.get_json(force=True)
        year   = int(body['year']); month = int(body['month']); day = int(body['day'])
        hour   = int(body.get('hour',0)); minute = int(body.get('minute',0)); second = int(body.get('second',0))
        lat    = float(body['latitude']); lon = float(body['longitude']); tz = float(body['timezone'])
        name   = body.get('name','Native')
        data   = build_chart(year, month, day, hour, minute, second, lat, lon, tz, name)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 400

@app.route('/health')
def health():
    ready = _init_jhora()
    return jsonify({'status': 'ok' if ready else 'error', 'jhora': ready, 'error': _jhora_error})

if __name__ == '__main__':
    print("🌙 Jyotish Engine starting on http://localhost:5050")
    print("   Powered by PyJHora (real source)")
    app.run(debug=True, port=5050)
