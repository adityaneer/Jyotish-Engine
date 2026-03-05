"""
Kaalavidya — Chart (Kundali) Module

Computes the Vedic rashi chart (kundali) at any moment — typically
at Vedic sunrise for the daily Panchanga chart.

The chart shows:
  - Lagna (ascendant) — which rashi is rising on the eastern horizon
  - Navagraha positions — which rashi each of the 9 planets occupies
  - House mapping — lagna rashi = 1st bhava, then clockwise

Navagraha (Nine Planets):
  Sun (Surya), Moon (Chandra), Mars (Mangala), Mercury (Budha),
  Jupiter (Guru), Venus (Shukra), Saturn (Shani), Rahu, Ketu

This module outputs data structures suitable for rendering both
South Indian (fixed-rashi) and North Indian (fixed-house) charts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# swisseph stubbed
class _swe_stub:
    SUN=0;MOON=1;MARS=4;MERCURY=2;JUPITER=5;VENUS=3;SATURN=6;MEAN_NODE=11
    SIDM_LAHIRI=1;FLG_SIDEREAL=64;FLG_SWIEPH=2;FLG_SPEED=256
    FLG_HELCTR=8;FLG_TOPOCTR=32768
    def set_sid_mode(self,*a,**k): pass
    def calc_ut(self,*a,**k): return ([0,0,0,1,0,0],)
    def julday(self,y,m,d,h=0):
        a=(14-m)//12;y2=y+4800-a;m2=m+12*a-3
        return d+(153*m2+2)//5+365*y2+y2//4-y2//100+y2//400-32045+h/24.0-0.5
    def revjul(self,jd):
        jd2=int(jd+0.5);z=jd2;a=int((z-1867216.25)/36524.25)
        a=z+1+a-a//4;b=a+1524;c=int((b-122.1)/365.25);d2=int(365.25*c)
        e=int((b-d2)/30.6001);day=b-d2-int(30.6001*e);month=e-1 if e<14 else e-13
        year=c-4716 if month>2 else c-4715;hour=(jd+0.5-int(jd+0.5))*24
        return year,month,day,hour
    def houses_ex(self,*a,**k): return ([0]*13,[0]*10)
    def rise_trans(self,*a,**k): return None,None
swe = _swe_stub()

from kaalavidya.constants import (
    AYANAMSHA_LAHIRI, TOTAL_RASHIS, TOTAL_NAKSHATRAS,
    NAKSHATRA_SPAN,
    name, RASHI, GRAHA, GRAHA_ABBREV, GRAHA_KEY_INDEX, NAKSHATRA,
)
from kaalavidya.chandra import datetime_to_jd
from kaalavidya.lagna import ascendant_longitude


# ──────────────────────────────────────────────────────────────────
#  Data Structures
# ──────────────────────────────────────────────────────────────────

# Swiss Ephemeris planet IDs for the Navagraha
# Ketu has no separate ID — it's 180° from Rahu (mean node)
_NAVAGRAHA = [
    ("sun",     swe.SUN,       0),
    ("moon",    swe.MOON,      1),
    ("mars",    swe.MARS,      2),
    ("mercury", swe.MERCURY,   3),
    ("jupiter", swe.JUPITER,   4),
    ("venus",   swe.VENUS,     5),
    ("saturn",  swe.SATURN,    6),
    ("rahu",    swe.MEAN_NODE, 7),
    # Ketu is computed from Rahu, index 8
]

_GRAHA_SYMBOL = {
    "sun": "☉", "moon": "☽", "mars": "♂", "mercury": "☿",
    "jupiter": "♃", "venus": "♀", "saturn": "♄",
    "rahu": "☊", "ketu": "☋",
}


def _graha_abbrev(key: str, lang: str = "en") -> str:
    """Get localized abbreviation for a graha key."""
    idx = GRAHA_KEY_INDEX.get(key, 0)
    return name(GRAHA_ABBREV, idx, lang)


@dataclass
class GrahaPosition:
    """Position of a graha (planet) at a given moment."""
    key: str                   # "sun", "moon", etc.
    index: int                 # 0–8 (Navagraha order)
    name: str                  # localized display name
    abbrev: str                # "Su", "Mo", etc.
    symbol: str                # "☉", "☽", etc.
    longitude: float           # sidereal longitude (0–360)
    rashi_index: int           # 0–11
    rashi_name: str            # localized rashi name
    degree_in_rashi: float     # degree within the rashi (0–30)
    nakshatra_index: int       # 0–26
    nakshatra_name: str        # localized nakshatra name
    nakshatra_pada: int        # 1–4
    is_retrograde: bool = False
    is_combust: bool = False


@dataclass
class SunriseChart:
    """
    Complete rashi chart computed at a specific moment (usually sunrise).

    Contains:
      - Lagna (ascendant) with exact degree
      - All 9 graha positions
      - House-to-graha mapping for rendering
      - Rashi-to-graha mapping for South Indian chart
    """
    # Lagna
    lagna_index: int           # rashi index of the ascendant (0–11)
    lagna_name: str            # localized rashi name
    lagna_degree: float        # exact degree within the lagna rashi
    lagna_longitude: float     # full sidereal longitude (0–360)
    lagna_nakshatra_index: int = 0
    lagna_nakshatra_name: str = ""
    lagna_nakshatra_pada: int = 1

    # Navagraha positions
    grahas: list[GrahaPosition] = field(default_factory=list)

    # Chart mappings (computed from above)
    # rashi_grahas[rashi_index] = list of graha abbreviations in that rashi
    rashi_grahas: dict = field(default_factory=dict)
    # house_grahas[house_number] = list of graha abbreviations in that house
    house_grahas: dict = field(default_factory=dict)

    def summary(self) -> str:
        """Text representation of the sunrise chart."""
        lines = []
        lines.append(f"── Sunrise Rashi Chart ──")
        lines.append(f"  Lagna: {self.lagna_name} ({self.lagna_degree:.1f}°)")
        lines.append("")

        for g in self.grahas:
            flags = []
            if g.is_retrograde:
                flags.append("R")
            if g.is_combust:
                flags.append("C")
            flag_str = f" ({','.join(flags)})" if flags else ""
            lines.append(
                f"  {g.symbol} {g.name:<16s} {g.rashi_name:<12s} "
                f"{g.degree_in_rashi:5.1f}°  "
                f"{g.nakshatra_name} (Pada {g.nakshatra_pada}){flag_str}"
            )

        lines.append("")
        lines.append("  Houses:")
        for house_num in range(1, 13):
            rashi_idx = (self.lagna_index + house_num - 1) % 12
            grahas_here = self.house_grahas.get(house_num, [])
            grahas_str = ", ".join(grahas_here) if grahas_here else "—"
            lines.append(f"    {house_num:>2}. {grahas_str}")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────
#  Combustion (Maudhya / Asta) limits
#
#  A planet is combust (asta) when it is within a threshold angular
#  distance from the Sun.  Limits from Surya Siddhanta / Brihat
#  Parashara Hora Shastra.
#
#  Key: graha key → (normal_limit°, retrograde_limit°)
#  Sun, Rahu, Ketu cannot be combust (Sun is the cause; Rahu/Ketu
#  are shadow grahas).
# ──────────────────────────────────────────────────────────────────

_COMBUSTION_LIMITS = {
    "moon":    (12.0, 12.0),
    "mars":    (17.0, 17.0),
    "mercury": (14.0, 12.0),  # tighter when retrograde
    "jupiter": (11.0, 11.0),
    "venus":   (10.0,  8.0),  # tighter when retrograde
    "saturn":  (15.0, 15.0),
}


def _angular_distance(lon1: float, lon2: float) -> float:
    """
    Shortest angular distance between two longitudes on a 360° circle.
    Always returns a value in [0, 180].
    """
    diff = abs(lon1 - lon2) % 360
    return diff if diff <= 180 else 360 - diff


def _check_combustion(graha: GrahaPosition, sun_longitude: float) -> bool:
    """
    Determine if a graha is combust (asta) — too close to the Sun.

    Returns True if the angular distance from the Sun is within the
    combustion threshold for that planet.
    """
    limits = _COMBUSTION_LIMITS.get(graha.key)
    if limits is None:
        return False  # Sun, Rahu, Ketu — never combust
    normal_limit, retro_limit = limits
    limit = retro_limit if graha.is_retrograde else normal_limit
    return _angular_distance(graha.longitude, sun_longitude) <= limit


# ──────────────────────────────────────────────────────────────────
#  Computation
# ──────────────────────────────────────────────────────────────────

def _graha_longitude(jd: float, planet_id: int) -> tuple:
    """
    Get sidereal longitude and speed of a planet.

    Returns (longitude_degrees, speed_degrees_per_day).
    Speed < 0 means retrograde motion.
    """
    swe.set_sid_mode(AYANAMSHA_LAHIRI)
    flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH | swe.FLG_SPEED
    result = swe.calc_ut(jd, planet_id, flags)
    longitude = result[0][0] % 360
    speed = result[0][3]
    return longitude, speed


def _nakshatra_info(longitude: float) -> tuple:
    """Nakshatra index (0–26) and pada (1–4) from sidereal longitude."""
    nak_idx = int(longitude / NAKSHATRA_SPAN) % TOTAL_NAKSHATRAS
    offset = longitude % NAKSHATRA_SPAN
    pada = min(int(offset / (NAKSHATRA_SPAN / 4)) + 1, 4)
    return nak_idx, pada


# ──────────────────────────────────────────────────────────────────
#  Orrery Data (Heliocentric + Geocentric planetary positions)
#
#  Heliocentric: TROPICAL longitudes — physical positions in space.
#  Geocentric:   SIDEREAL (Lahiri) longitudes — matches Indian
#                rashi ring (Mesha = 0° sidereal, not 0° tropical).
#
#  This ensures planets appear in their correct sidereal rashis
#  on the geocentric orrery, consistent with Vedic astrology.
# ──────────────────────────────────────────────────────────────────

# Approximate semi-major axes in AU (for visual orbit sizing)
_ORBIT_AU = {
    "mercury": 0.387,
    "venus":   0.723,
    "earth":   1.000,
    "mars":    1.524,
    "jupiter": 5.203,
    "saturn":  9.537,
}

# Display properties — Navagraha traditional colours
# Surya: bright gold-red, Chandra: silver-white, Mangala: blood-red,
# Budha: emerald-green, Guru: bright yellow-gold, Shukra: pearl-white,
# Shani: deep indigo-blue, Rahu: smoky dark-blue, Ketu: smoky grey
_BODY_PROPS = {
    "sun":     {"symbol": "☉", "label": "Sūrya",   "color": "#f59e0b"},
    "moon":    {"symbol": "☽", "label": "Chandra",  "color": "#e2e8f0"},
    "mercury": {"symbol": "☿", "label": "Budha",    "color": "#34d399"},
    "venus":   {"symbol": "♀", "label": "Shukra",   "color": "#f0f0f0"},
    "earth":   {"symbol": "🜨", "label": "Pṛthvī",   "color": "#06b6d4"},
    "mars":    {"symbol": "♂", "label": "Maṅgala",  "color": "#ef4444"},
    "jupiter": {"symbol": "♃", "label": "Guru",     "color": "#facc15"},
    "saturn":  {"symbol": "♄", "label": "Shani",    "color": "#6366f1"},
    "rahu":    {"symbol": "☊", "label": "Rāhu",     "color": "#475569"},
    "ketu":    {"symbol": "☋", "label": "Ketu",     "color": "#94a3b8"},
}


def compute_orrery_data(jd: float, lang: str = "en") -> dict:
    """
    Compute planetary positions for orrery visualisation.

    Returns a dict with:
      heliocentric: list of {key, symbol, label, color, longitude, distance_au}
                    (Sun at center, planets + Earth positioned around it)
                    Uses TROPICAL longitudes (physical positions in space).
      geocentric:   list of {key, symbol, label, color, longitude, distance_au}
                    (Earth at center, Sun/Moon/planets positioned around it)
                    Uses SIDEREAL (Lahiri) longitudes to match Indian rashi ring.
    """
    # -- Sidereal geocentric positions (Lahiri ayanamsha) --
    # Geocentric view shows planets relative to Indian rashis (sidereal),
    # so we use sidereal longitudes to ensure correct rashi placement.
    swe.set_sid_mode(AYANAMSHA_LAHIRI)
    geo_flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    geo_data = {}
    for key, planet_id, _ in _NAVAGRAHA:
        result = swe.calc_ut(jd, planet_id, geo_flags)
        geo_data[key] = {
            "longitude": result[0][0] % 360,
            "distance_au": result[0][2],
            "speed": result[0][3],
        }

    # Ketu = Rahu + 180°
    rahu_lon = geo_data["rahu"]["longitude"]
    geo_data["ketu"] = {
        "longitude": (rahu_lon + 180) % 360,
        "distance_au": geo_data["rahu"]["distance_au"],
        "speed": geo_data["rahu"]["speed"],
    }

    # -- Heliocentric positions (sidereal — to match Indian rashi ring) --
    # Both views share the same sidereal rashi ring, so heliocentric
    # planets also use Lahiri-corrected sidereal longitudes.
    helio_flags = swe.FLG_SWIEPH | swe.FLG_HELCTR | swe.FLG_SIDEREAL
    helio_data = {}
    for key in ("mercury", "venus", "mars", "jupiter", "saturn"):
        planet_id = dict((k, pid) for k, pid, _ in _NAVAGRAHA)[key]
        result = swe.calc_ut(jd, planet_id, helio_flags)
        helio_data[key] = {
            "longitude": result[0][0] % 360,
            "distance_au": result[0][2],
        }

    # Earth's heliocentric position = Sun's sidereal geocentric longitude + 180°
    sun_sid = swe.calc_ut(jd, swe.SUN, geo_flags)
    helio_data["earth"] = {
        "longitude": (sun_sid[0][0] + 180) % 360,
        "distance_au": sun_sid[0][2],
    }

    # -- Build output lists with localized labels --
    def _label(key):
        """Get localized label; Earth has no GRAHA index so use _BODY_PROPS."""
        idx = GRAHA_KEY_INDEX.get(key)
        if idx is not None:
            return name(GRAHA, idx, lang)
        return _BODY_PROPS[key]["label"]  # fallback (e.g. Earth/Prithvi)

    helio_list = []
    for key in ("mercury", "venus", "earth", "mars", "jupiter", "saturn"):
        props = _BODY_PROPS[key]
        helio_list.append({
            "key": key,
            "symbol": props["symbol"],
            "label": _label(key),
            "color": props["color"],
            "longitude": round(helio_data[key]["longitude"], 4),
            "distance_au": round(helio_data[key]["distance_au"], 4),
            "orbit_au": _ORBIT_AU[key],
        })

    # For combustion check we need Sun's sidereal longitude
    sun_sid_lon = geo_data["sun"]["longitude"]

    geo_list = []
    for key in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "rahu", "ketu"):
        props = _BODY_PROPS[key]
        gd = geo_data[key]
        is_retro = gd["speed"] < 0
        # Check combustion for planets that can be combust
        limits = _COMBUSTION_LIMITS.get(key)
        is_combust = False
        if limits:
            limit = limits[1] if is_retro else limits[0]
            is_combust = _angular_distance(gd["longitude"], sun_sid_lon) <= limit
        geo_list.append({
            "key": key,
            "symbol": props["symbol"],
            "label": _label(key),
            "color": props["color"],
            "longitude": round(gd["longitude"], 4),
            "distance_au": round(gd["distance_au"], 4),
            "is_retrograde": is_retro,
            "is_combust": is_combust,
        })

    # -- Localized rashi names for the orrery ring --
    rashi_names = [name(RASHI, i, lang) for i in range(TOTAL_RASHIS)]

    return {
        "heliocentric": helio_list,
        "geocentric": geo_list,
        "rashi_names": rashi_names,
    }


def compute_sunrise_chart(
    sunrise_dt: datetime,
    latitude: float,
    longitude: float,
    lang: str = "en",
) -> SunriseChart:
    """
    Compute the complete Vedic rashi chart at the moment of sunrise.

    This gives a snapshot of the sky at sunrise: which rashi is rising
    (lagna), and where each of the 9 grahas are positioned.

    Args:
        sunrise_dt: Vedic sunrise datetime (timezone-aware).
        latitude: Observer's latitude (°N).
        longitude: Observer's longitude (°E).
        lang: Language code for names.

    Returns:
        SunriseChart with lagna, graha positions, and house mappings.
    """
    jd = datetime_to_jd(sunrise_dt)

    # ── Lagna (Ascendant) ──
    lagna_long = ascendant_longitude(jd, latitude, longitude)
    lagna_idx = int(lagna_long / 30) % TOTAL_RASHIS
    lagna_deg = round(lagna_long % 30, 2)
    lagna_nak_idx, lagna_nak_pada = _nakshatra_info(lagna_long)

    # ── Navagraha positions ──
    grahas = []

    for key, planet_id, graha_idx in _NAVAGRAHA:
        planet_long, speed = _graha_longitude(jd, planet_id)
        rashi_idx = int(planet_long / 30) % TOTAL_RASHIS
        deg_in_rashi = round(planet_long % 30, 2)
        nak_idx, pada = _nakshatra_info(planet_long)

        grahas.append(GrahaPosition(
            key=key,
            index=graha_idx,
            name=name(GRAHA, graha_idx, lang),
            abbrev=_graha_abbrev(key, lang),
            symbol=_GRAHA_SYMBOL[key],
            longitude=round(planet_long, 4),
            rashi_index=rashi_idx,
            rashi_name=name(RASHI, rashi_idx, lang),
            degree_in_rashi=deg_in_rashi,
            nakshatra_index=nak_idx,
            nakshatra_name=name(NAKSHATRA, nak_idx, lang),
            nakshatra_pada=pada,
            is_retrograde=(speed < 0),
        ))

    # ── Ketu ── (180° opposite Rahu)
    rahu = grahas[7]  # Rahu is index 7 in _NAVAGRAHA
    ketu_long = (rahu.longitude + 180) % 360
    ketu_rashi = int(ketu_long / 30) % TOTAL_RASHIS
    ketu_deg = round(ketu_long % 30, 2)
    ketu_nak, ketu_pada = _nakshatra_info(ketu_long)

    grahas.append(GrahaPosition(
        key="ketu",
        index=8,
        name=name(GRAHA, 8, lang),
        abbrev=_graha_abbrev("ketu", lang),
        symbol=_GRAHA_SYMBOL["ketu"],
        longitude=round(ketu_long, 4),
        rashi_index=ketu_rashi,
        rashi_name=name(RASHI, ketu_rashi, lang),
        degree_in_rashi=ketu_deg,
        nakshatra_index=ketu_nak,
        nakshatra_name=name(NAKSHATRA, ketu_nak, lang),
        nakshatra_pada=ketu_pada,
        is_retrograde=True,  # Rahu/Ketu always retrograde
    ))
    # Mark Rahu as retrograde too
    grahas[7].is_retrograde = True

    # ── Combustion check ──
    # Sun is always at index 0 in our list
    sun_longitude = grahas[0].longitude
    for g in grahas:
        g.is_combust = _check_combustion(g, sun_longitude)

    # ── Build rashi→graha mapping ──
    # rashi_grahas[rashi_index] = ["Su", "Me", ...] — for South Indian chart
    rashi_grahas = {}
    for i in range(TOTAL_RASHIS):
        rashi_grahas[i] = []
    for g in grahas:
        rashi_grahas[g.rashi_index].append(g.abbrev)

    # ── Build house→graha mapping ──
    # house 1 = lagna rashi, house 2 = lagna+1, etc.
    house_grahas = {}
    for house_num in range(1, 13):
        rashi_idx = (lagna_idx + house_num - 1) % 12
        house_grahas[house_num] = rashi_grahas[rashi_idx].copy()

    return SunriseChart(
        lagna_index=lagna_idx,
        lagna_name=name(RASHI, lagna_idx, lang),
        lagna_degree=lagna_deg,
        lagna_longitude=round(lagna_long, 4),
        lagna_nakshatra_index=lagna_nak_idx,
        lagna_nakshatra_name=name(NAKSHATRA, lagna_nak_idx, lang),
        lagna_nakshatra_pada=lagna_nak_pada,
        grahas=grahas,
        rashi_grahas=rashi_grahas,
        house_grahas=house_grahas,
    )
