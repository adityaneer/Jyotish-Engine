"""
Kaalavidya — Grahana (Eclipse) Module

Computes solar and lunar eclipses using Swiss Ephemeris.

Eclipse types:
  Solar (Surya Grahana): Total, Annular, Partial
  Lunar (Chandra Grahana): Total, Partial, Penumbral

Key functions:
  check_eclipses_on_day()  — for daily panchanga
  find_eclipses_in_year()  — for year-long calendar
"""

from datetime import datetime, date, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

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

from kaalavidya.models import EclipseInfo
from kaalavidya.chandra import datetime_to_jd, jd_to_datetime


# ──────────────────────────────────────────────────────────────────
#  Eclipse Type Flags (from Swiss Ephemeris)
# ──────────────────────────────────────────────────────────────────

_ECL_TOTAL = swe.ECL_TOTAL          # 4
_ECL_ANNULAR = swe.ECL_ANNULAR      # 8
_ECL_PARTIAL = swe.ECL_PARTIAL      # 16
_ECL_PENUMBRAL = swe.ECL_PENUMBRAL  # 64


def _eclipse_subtype(retflag: int, is_solar: bool) -> str:
    """Decode the eclipse subtype from Swiss Ephemeris return flags."""
    if retflag & _ECL_TOTAL:
        return "total"
    elif retflag & _ECL_ANNULAR:
        return "annular"
    elif retflag & _ECL_PARTIAL:
        return "partial"
    elif retflag & _ECL_PENUMBRAL:
        return "penumbral"
    return "partial"  # default


# ──────────────────────────────────────────────────────────────────
#  Daily Eclipse Check
# ──────────────────────────────────────────────────────────────────

def check_eclipses_on_day(
    sunrise_jd: float,
    next_sunrise_jd: float,
    latitude: float,
    longitude: float,
    tz: ZoneInfo,
) -> list[EclipseInfo]:
    """
    Check if any eclipse (solar or lunar) occurs during this Hindu day.

    A Hindu day = sunrise to next sunrise. We check if any part of an
    eclipse is visible from this location during that window.

    Strategy:
      1. Search for the next solar eclipse from 1 day before sunrise.
         If its max time falls near our day, include it.
      2. Same for lunar eclipse.
    This is efficient because Swiss Ephemeris quickly jumps to the
    next eclipse (no scanning needed).
    """
    eclipses = []
    geopos = (longitude, latitude, 0.0)

    # ── Solar Eclipse ──
    solar = _check_solar_eclipse(sunrise_jd, next_sunrise_jd, geopos, tz)
    if solar:
        eclipses.append(solar)

    # ── Lunar Eclipse ──
    lunar = _check_lunar_eclipse(sunrise_jd, next_sunrise_jd, geopos, tz)
    if lunar:
        eclipses.append(lunar)

    return eclipses


def _check_solar_eclipse(
    sunrise_jd: float,
    next_sunrise_jd: float,
    geopos: tuple,
    tz: ZoneInfo,
) -> Optional[EclipseInfo]:
    """Check for a solar eclipse visible from this location on this day."""
    try:
        search_jd = sunrise_jd - 1.0
        retflag, tret, attr = swe.sol_eclipse_when_loc(search_jd, geopos)

        # tret layout for solar eclipses:
        #   0: maximum, 1: first contact, 4: fourth contact
        #   5: sunrise during eclipse, 6: sunset during eclipse
        # If eclipse starts before sunrise: tret[1]=0, use tret[5] (sunrise)
        # If eclipse ends after sunset: tret[4]=0, use tret[6] (sunset)
        ecl_max = tret[0]
        ecl_start = tret[1] if tret[1] != 0.0 else tret[5]
        ecl_end = tret[4] if tret[4] != 0.0 else tret[6]

        # Still no valid times → not visible
        if ecl_start == 0.0 or ecl_end == 0.0:
            return None

        # Check if any part of the eclipse overlaps with our Hindu day
        if ecl_end < sunrise_jd or ecl_start > next_sunrise_jd:
            return None

        return EclipseInfo(
            eclipse_type="solar",
            subtype=_eclipse_subtype(retflag, is_solar=True),
            max_time=jd_to_datetime(ecl_max, tz),
            start_time=jd_to_datetime(ecl_start, tz),
            end_time=jd_to_datetime(ecl_end, tz),
            magnitude=attr[0],
            obscuration=attr[2],
        )
    except Exception:
        return None


def _check_lunar_eclipse(
    sunrise_jd: float,
    next_sunrise_jd: float,
    geopos: tuple,
    tz: ZoneInfo,
) -> Optional[EclipseInfo]:
    """Check for a lunar eclipse visible from this location on this day."""
    try:
        search_jd = sunrise_jd - 1.0
        retflag, tret, attr = swe.lun_eclipse_when_loc(search_jd, geopos)

        # tret layout for lunar eclipses:
        #   0: maximum, 6: penumbral begin, 7: penumbral end
        #   8: moonrise during eclipse, 9: moonset during eclipse
        # If eclipse starts before moonrise: tret[6]=0, use tret[8] (moonrise)
        # If eclipse ends after moonset: tret[7]=0, use tret[9] (moonset)
        ecl_max = tret[0]
        ecl_start = tret[6] if tret[6] != 0.0 else tret[8]
        ecl_end = tret[7] if tret[7] != 0.0 else tret[9]

        if ecl_start == 0.0 or ecl_end == 0.0:
            return None

        # Check overlap with Hindu day
        if ecl_end < sunrise_jd or ecl_start > next_sunrise_jd:
            return None

        return EclipseInfo(
            eclipse_type="lunar",
            subtype=_eclipse_subtype(retflag, is_solar=False),
            max_time=jd_to_datetime(ecl_max, tz),
            start_time=jd_to_datetime(ecl_start, tz),
            end_time=jd_to_datetime(ecl_end, tz),
            magnitude=attr[0],  # umbral magnitude
        )
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────
#  Year-Long Eclipse Search
# ──────────────────────────────────────────────────────────────────

def find_eclipses_in_year(
    year: int,
    latitude: float,
    longitude: float,
    timezone_str: str,
) -> list[EclipseInfo]:
    """
    Find all eclipses visible from a location during a given year.

    Returns both solar and lunar eclipses, sorted by date.
    Typically 2–5 eclipses per year globally, but fewer are visible
    from any single location.
    """
    tz = ZoneInfo(timezone_str)
    geopos = (longitude, latitude, 0.0)
    eclipses = []

    # Start of year (Jan 1) and end of year (Dec 31) in JD
    jd_start = swe.julday(year, 1, 1, 0.0)
    jd_end = swe.julday(year, 12, 31, 23.99)

    # ── Find all solar eclipses in the year ──
    search_jd = jd_start
    for _ in range(10):  # max 10 iterations (safety limit)
        try:
            retflag, tret, attr = swe.sol_eclipse_when_loc(search_jd, geopos)
            ecl_max = tret[0]

            if ecl_max > jd_end:
                break  # past end of year

            # Handle eclipse starting before sunrise or ending after sunset
            ecl_start = tret[1] if tret[1] != 0.0 else tret[5]
            ecl_end = tret[4] if tret[4] != 0.0 else tret[6]

            if ecl_start != 0.0 and ecl_end != 0.0:
                eclipses.append(EclipseInfo(
                    eclipse_type="solar",
                    subtype=_eclipse_subtype(retflag, is_solar=True),
                    max_time=jd_to_datetime(ecl_max, tz),
                    start_time=jd_to_datetime(ecl_start, tz),
                    end_time=jd_to_datetime(ecl_end, tz),
                    magnitude=attr[0],
                    obscuration=attr[2],
                ))

            # Search for next eclipse starting after this one
            search_jd = ecl_max + 20  # skip ahead ~20 days
        except Exception:
            break

    # ── Find all lunar eclipses in the year ──
    search_jd = jd_start
    for _ in range(10):
        try:
            retflag, tret, attr = swe.lun_eclipse_when_loc(search_jd, geopos)
            ecl_max = tret[0]

            if ecl_max > jd_end:
                break

            # Handle eclipse starting before moonrise or ending after moonset
            ecl_start = tret[6] if tret[6] != 0.0 else tret[8]
            ecl_end = tret[7] if tret[7] != 0.0 else tret[9]

            if ecl_start != 0.0 and ecl_end != 0.0:
                eclipses.append(EclipseInfo(
                    eclipse_type="lunar",
                    subtype=_eclipse_subtype(retflag, is_solar=False),
                    max_time=jd_to_datetime(ecl_max, tz),
                    start_time=jd_to_datetime(ecl_start, tz),
                    end_time=jd_to_datetime(ecl_end, tz),
                    magnitude=attr[0],
                ))

            search_jd = ecl_max + 20
        except Exception:
            break

    # Sort by max_time
    eclipses.sort(key=lambda e: e.max_time)
    return eclipses
