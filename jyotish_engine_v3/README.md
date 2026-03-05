# Jyotish Engine — Vedic Astrology Web Application
**Powered by PyJHora (real source embedded)**

---

## What This Is

A complete Vedic (Jyotish) astrology web application that uses the **actual PyJHora library source code** — not a mock, not a bridge, not a stub — embedded directly, so it runs offline after a one-time `pip install`.

---

## Gap Analysis: Previous → This Build

| Gap | Previous Build | This Build |
|-----|---------------|------------|
| PyJHora integration | Hand-rolled bridge mimicking PyJHora's API | **Real PyJHora source embedded** (`jhora/` package) |
| Yoga detection | ~10 manually coded yogas | **Hundreds of yogas** from PyJHora's `yoga.py` + `raja_yoga.py` resource files |
| Divisional charts | 4 charts shown in UI | **5 varga charts** (D2, D3, D9, D10, D12) in tabbed UI |
| Dasha detail | Placeholder/simplified | Real Vimshottari from `vimsottari.py` with Maha+Antardasha |
| Ashtakavarga | Placeholder score | Real BAV + SAV from `ashtakavarga.get_ashtaka_varga()` |
| Panchanga | Basic tithi/nakshatra | Full 5-limb panchanga with proper PyJHora drik functions |
| Optional deps | Hard failures | `pytz`, `geocoder`, `timezonefinder`, `geopy` made gracefully optional |
| Frontend | Functional | Luxurious manuscript-themed UI with tab navigation |

---

## Project Structure

```
jyotish_v2/
├── app.py                      ← Flask application (6 routes)
├── requirements.txt            ← All dependencies
├── README.md                   ← This file
│
├── jhora/                      ← REAL PyJHora source (v from GitHub zip)
│   ├── __init__.py
│   ├── const.py                ← All constants, ayanamsha settings, planet data
│   ├── utils.py                ← Utilities, JD conversion, house lists (patched for optional deps)
│   ├── panchanga/
│   │   ├── drik.py             ← Core panchanga: tithi, nakshatra, yoga, karana, vaara, sunrise
│   │   ├── eclipse.py          ← Solar/lunar eclipse detection
│   │   └── info.py             ← Calendar info
│   └── horoscope/
│       ├── main.py             ← Horoscope class (high-level)
│       ├── chart/
│       │   ├── charts.py       ← Rasi + all divisional charts (D1-D144)
│       │   ├── yoga.py         ← Yoga detection (100s of classical yogas)
│       │   ├── raja_yoga.py    ← Raja yoga algorithms
│       │   ├── ashtakavarga.py ← Binna + Sarva Ashtakavarga
│       │   ├── house.py        ← House lords, relationships, strengths
│       │   ├── arudhas.py      ← Arudha padas
│       │   ├── strength.py     ← Shadbala
│       │   └── dosha.py        ← Mangal dosha etc.
│       └── dhasa/
│           └── graha/
│               ├── vimsottari.py  ← Vimshottari dasha (the standard)
│               └── ...            ← 20+ other dasha systems
│
└── templates/
    ├── index.html              ← Birth data entry (dark celestial theme)
    └── chart.html              ← Chart display (8-tab interface)
```

---

## Installation

### Prerequisites
- Python 3.9+
- A C compiler (for pyswisseph) — usually pre-installed on Linux/macOS
  - **Windows**: Install Microsoft C++ Build Tools
  - **macOS**: `xcode-select --install`
  - **Linux**: `sudo apt install build-essential`

### Steps

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python app.py

# 4. Open in browser
# http://localhost:5050
```

---

## Running

```bash
python app.py
# → http://localhost:5050
```

Enter birth data (date, time, lat/lon/timezone) and click **Cast the Chart**.

---

## API

### `POST /api/chart`
```json
{
  "year": 1992, "month": 2, "day": 15,
  "hour": 5, "minute": 20, "second": 0,
  "latitude": 27.4728, "longitude": 94.912, "timezone": 5.5,
  "name": "Test Person"
}
```

Returns full chart JSON including planets, panchanga, dashas, yogas, ashtakavarga, and varga charts.

### `GET /health`
Returns `{"status": "ok", "jhora": true}` if PyJHora loaded successfully.

---

## PyJHora — How It's Integrated

The `jhora/` directory **is** the PyJHora library source code, copied directly from the official GitHub zip. This means:

1. **No `pip install pyjhora` required** — the source is already here
2. **Full fidelity** — every yoga, every dasha, every calculation is from the real library
3. **Easy updates** — replace `jhora/` with a newer version anytime

### Key API calls used by `app.py`:

```python
from jhora.panchanga import drik
from jhora.horoscope.chart import charts, yoga, ashtakavarga
from jhora.horoscope.dhasa.graha import vimsottari
from jhora import utils

# Julian Day
jd = utils.julian_day_number((year,month,day), (hour,min,sec))

# Place struct
place = drik.Place("City", latitude, longitude, timezone_offset)

# Rasi chart — returns [[planet_id, (sign_0to11, long_in_sign)], ...]
pp = charts.rasi_chart(jd, place)

# Panchanga
tithi   = drik.tithi(jd, place)     # (tithi_num, start_jd, end_jd)
nak     = drik.nakshatra(jd, place) # (nak_num, pada, start_jd, end_jd)
yogam   = drik.yogam(jd, place)     # (yoga_num, start_jd, end_jd)
karana  = drik.karana(jd, place)    # (karana_num, start_jd, end_jd)
vaara   = drik.vaara(jd)            # day index 0=Mon..6=Sun

# Vimshottari Dasha
vim_bal, dasha = vimsottari.get_vimsottari_dhasa_bhukthi(jd, place, dhasa_level_index=2)

# Yogas
yoga_results, count, total = yoga.get_yoga_details(jd, place)

# Ashtakavarga
h_to_p = utils.get_house_planet_list_from_planet_positions(pp)
bav, sav, prastara = ashtakavarga.get_ashtaka_varga(h_to_p)

# Divisional chart
navamsa = charts.divisional_chart(jd, place, divisional_chart_factor=9)
```

---

## Calculation Details

| Parameter | Value |
|-----------|-------|
| Ayanamsha | Lahiri (Chitrapaksha) — standard for Parashari Jyotish |
| House system | Whole sign |
| Ephemeris | Swiss Ephemeris via pyswisseph |
| Dasha | Vimshottari (120-year) from Moon's nakshatra position |
| Yoga detection | PyJHora's built-in yoga.py with JSON resource files |

---

## Extending

**Add more varga charts to UI:**  
In `app.py`, add entries to the `for dcf, vname in [...]` loop.

**Use the full Horoscope class:**  
```python
from jhora.horoscope.main import Horoscope
h = Horoscope(latitude=28.6, longitude=77.2, timezone_offset=5.5,
              date_in=drik.Date(1992,2,15), birth_time="05:20:00")
info = h.get_horoscope_information_for_chart()
```

**Switch to TRUE_PUSHYA ayanamsha:**  
In `jhora/const.py`: `_DEFAULT_AYANAMSA_MODE = 'TRUE_PUSHYA'`

---

## License

PyJHora source in `jhora/` is © Open Astro Technologies, licensed under **GNU AGPL v3**.  
Application code (`app.py`, templates) is provided as-is for educational use.
