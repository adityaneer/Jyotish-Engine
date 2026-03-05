"""
Kaalavidya — Lagna (Ascendant) Module

Computes the rising sign (lagna/ascendant) table for the full day.

The ascendant is the rashi (sidereal zodiac sign) that is rising
on the eastern horizon at any given moment. It changes roughly
every 2 hours, but durations vary significantly:

  - At tropical latitudes (like India), Mesha/Vrishabha rise quickly
    (~1.5 hours) while Kanya/Tula rise slowly (~2.5+ hours).
  - This is due to oblique ascension — the ecliptic meets the horizon
    at different angles as the sky rotates.

The lagna table is essential for Muhurta (auspicious time) selection.
"""

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

from kaalavidya.constants import AYANAMSHA_LAHIRI, TOTAL_RASHIS, name, RASHI
from kaalavidya.models import LagnaEntry
from kaalavidya.chandra import datetime_to_jd, jd_to_datetime


def ascendant_longitude(jd: float, latitude: float, longitude: float) -> float:
    """
    Sidereal ascendant (lagna) longitude at the given moment and place.

    Returns 0–360 degrees (Lahiri ayanamsha applied).
    """
    # swe.houses_ex gives house cusps and ascendant/MC in one call
    # We use Placidus houses (standard for Jyotish lagna calculation)
    cusps, angles = swe.houses_ex(
        jd, latitude, longitude,
        bytes("P", "ascii"),  # Placidus house system
        swe.FLG_SIDEREAL
    )
    # angles[0] = ascendant longitude (sidereal, with ayanamsha applied)
    return angles[0] % 360


def ascendant_rashi(jd: float, latitude: float, longitude: float) -> int:
    """Get the rashi index (0–11) of the ascendant at a given moment."""
    asc_long = ascendant_longitude(jd, latitude, longitude)
    return int(asc_long / 30) % TOTAL_RASHIS


def compute_lagna_table(
    sunrise_dt: datetime,
    next_sunrise_dt: datetime,
    latitude: float,
    longitude: float,
    lang: str = "en",
) -> list[LagnaEntry]:
    """
    Compute the lagna (ascendant) timetable for the full Hindu day.

    Scans from sunrise to next sunrise and records when each rashi
    starts and ends as the ascendant.

    Returns:
        List of LagnaEntry, one per rashi period during the day.
        Typically 12–13 entries (all 12 rashis appear, since the
        ascendant completes a full rotation in ~24 hours).
    """
    tz = sunrise_dt.tzinfo
    start_jd = datetime_to_jd(sunrise_dt)
    end_jd = datetime_to_jd(next_sunrise_dt)

    entries = []

    # Find all lagna transition points by scanning in small steps
    scan_step = 2.0 / (24 * 60)  # 2-minute steps (lagnas can be short)
    precision = 0.25 / (24 * 60)  # ~15-second precision

    current_rashi = ascendant_rashi(start_jd, latitude, longitude)
    period_start_jd = start_jd

    jd = start_jd + scan_step
    while jd <= end_jd:
        rashi_now = ascendant_rashi(jd, latitude, longitude)

        if rashi_now != current_rashi:
            # Binary search for exact transition
            exact_jd = _binary_search_lagna(
                jd - scan_step, jd,
                current_rashi, latitude, longitude, precision
            )

            duration_minutes = (exact_jd - period_start_jd) * 24 * 60

            entries.append(LagnaEntry(
                index=current_rashi,
                name=name(RASHI, current_rashi, lang),
                starts_at=jd_to_datetime(period_start_jd, tz),
                ends_at=jd_to_datetime(exact_jd, tz),
                duration_minutes=round(duration_minutes, 1),
            ))

            current_rashi = rashi_now
            period_start_jd = exact_jd

        jd += scan_step

    # Close the last period at end of day (next sunrise)
    duration_minutes = (end_jd - period_start_jd) * 24 * 60
    entries.append(LagnaEntry(
        index=current_rashi,
        name=name(RASHI, current_rashi, lang),
        starts_at=jd_to_datetime(period_start_jd, tz),
        ends_at=jd_to_datetime(end_jd, tz),
        duration_minutes=round(duration_minutes, 1),
    ))

    return entries


def _binary_search_lagna(
    lo_jd: float,
    hi_jd: float,
    expected_rashi: int,
    latitude: float,
    longitude: float,
    precision: float,
) -> float:
    """
    Binary search to find when the ascendant rashi changes
    from expected_rashi to something else.
    """
    while (hi_jd - lo_jd) > precision:
        mid_jd = (lo_jd + hi_jd) / 2
        mid_rashi = ascendant_rashi(mid_jd, latitude, longitude)

        if mid_rashi == expected_rashi:
            lo_jd = mid_jd
        else:
            hi_jd = mid_jd

    return (lo_jd + hi_jd) / 2
