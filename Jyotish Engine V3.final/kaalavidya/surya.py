"""
Kaalavidya — Surya (Sun) Module

Computes sunrise/sunset (Vedic and Drik), twilight, day-part divisions,
inauspicious periods (Rahu Kala, Durmuhurta, Varjyam), auspicious
periods (Brahma Muhurta, Abhijit Muhurta), and Hora table.

Uses Swiss Ephemeris (pyswisseph) for precise sunrise/sunset with
control over center-of-disk vs upper-limb.

Vedic sunrise = center of Sun's disk at the horizon (with refraction).
Drik sunrise  = upper limb of Sun at the horizon (civil/standard).
"""

from datetime import datetime, date, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

# swisseph stubbed - sun/moon rise calculations not available without it
class _swe_stub:
    SUN = 0; MOON = 1
    CALC_RISE = 1; CALC_SET = 2; CALC_MTRANSIT = 4; CALC_ITRANSIT = 8
    BIT_DISC_CENTER = 256; BIT_NO_REFRACTION = 512
    SIDM_LAHIRI = 1
    FLG_SIDEREAL = 64; FLG_SWIEPH = 2; FLG_SPEED = 256
    def rise_trans(self, *a, **kw): return None, None
    def julday(self, y,m,d,h=0): 
        # Julian Day Number (approximate)
        a = (14-m)//12; y2=y+4800-a; m2=m+12*a-3
        return d + (153*m2+2)//5 + 365*y2 + y2//4 - y2//100 + y2//400 - 32045 + h/24.0 - 0.5
    def revjul(self, jd):
        jd2 = int(jd+0.5); z=jd2; a=int((z-1867216.25)/36524.25)
        a=z+1+a-a//4; b=a+1524; c=int((b-122.1)/365.25); d=int(365.25*c)
        e=int((b-d)/30.6001)
        day=b-d-int(30.6001*e); month=e-1 if e<14 else e-13; year=c-4716 if month>2 else c-4715
        hour=(jd+0.5-int(jd+0.5))*24; return year,month,day,hour
    def calc_ut(self, *a, **kw): return ([0,0,0,0],)
    def set_sid_mode(self, *a): pass
swe = _swe_stub()

# astral stubbed
from datetime import timezone as _tz_mod
class _AstralStub:
    class LocationInfo:
        def __init__(self, name='', region='', timezone='UTC', latitude=0, longitude=0):
            self.name=name;self.region=region;self.timezone=timezone
            self.latitude=latitude;self.longitude=longitude
    class _Observer:
        def __init__(self, lat, lon, elev=0):
            self.latitude=lat;self.longitude=lon;self.elevation=elev
_astral_stub = _AstralStub()
LocationInfo = _AstralStub.LocationInfo


from kaalavidya.models import SunTimes, TimePeriod, HoraEntry, MuhurtaEntry
from kaalavidya.constants import (
    RAHU_KALA, YAMAGANDAM, GULIKA_KALA,
    HORA_CYCLE, HORA_WEEKDAY_START,
    DURMUHURTA, DINA_MUHURTA_NAMES, RATRI_MUHURTA_NAMES,
    DINA_MUHURTA_GUNA, RATRI_MUHURTA_GUNA,
    DINA_MUHURTA_ALT, RATRI_MUHURTA_ALT,
    VARJYAM_GHATI_OFFSET, VARJYAM_DURATION_GHATI,
    AMRIT_KALAM_GHATI_OFFSET, AMRIT_KALAM_DURATION_GHATI,
    AYANAMSHA_LAHIRI, name,
)


# ──────────────────────────────────────────────────────────────────
#  Swiss Ephemeris rise/transit flags
# ──────────────────────────────────────────────────────────────────

_CALC_RISE = 1
_CALC_SET = 2
_BIT_DISC_CENTER = 256    # center of disk instead of upper limb


def _swe_rise_set(
    target_date: date,
    latitude: float,
    longitude: float,
    rise_or_set: int,
    disc_center: bool = True,
) -> float:
    """
    Compute sunrise or sunset Julian Day (UT) using Swiss Ephemeris.

    Args:
        rise_or_set: _CALC_RISE or _CALC_SET
        disc_center: True for Vedic (center of disk), False for Drik (upper limb)

    Returns:
        Julian day (UT) of the event.

    Note:
        swe.rise_trans returns the *next* event after jd_start.
        For eastern longitudes, 0h UT can be *after* local sunrise
        (e.g. Kolkata: 0h UT = 5:30 AM IST, but sunrise is ~5:00 AM).
        We start from local midnight (in UT) to ensure we capture
        the correct day's sunrise. For sunset, we start from local noon.
    """
    jd_ut_midnight = swe.julday(target_date.year, target_date.month, target_date.day, 0.0)

    # Approximate local midnight in UT by subtracting longitude-based offset
    local_midnight_offset = longitude / 360.0  # days east of Greenwich
    jd_start = jd_ut_midnight - local_midnight_offset

    # For sunset, advance to local noon so we find the same day's sunset
    if rise_or_set & _CALC_SET:
        jd_start += 0.5

    geopos = (longitude, latitude, 0.0)
    rsmi = rise_or_set
    if disc_center:
        rsmi |= _BIT_DISC_CENTER

    result = swe.rise_trans(jd_start, swe.SUN, rsmi, geopos, 1013.25, 15)
    return result[1][0]


def _jd_to_datetime(jd_ut: float, tz: ZoneInfo) -> datetime:
    """Convert a Julian Day (UT) to a timezone-aware datetime."""
    year, month, day, hour_frac = swe.revjul(jd_ut)
    hours = int(hour_frac)
    remainder = (hour_frac - hours) * 60
    minutes = int(remainder)
    seconds = int((remainder - minutes) * 60)
    microseconds = int((((remainder - minutes) * 60) - seconds) * 1_000_000)

    dt_utc = datetime(year, month, day, hours, minutes, seconds, microseconds,
                      tzinfo=ZoneInfo("UTC"))
    return dt_utc.astimezone(tz)


def compute_sun_times(
    target_date: date,
    latitude: float,
    longitude: float,
    timezone_str: str,
    city: str = "",
) -> SunTimes:
    """
    Compute both Vedic and Drik sunrise/sunset for a location and date.

    Vedic = center of Sun's disk at the horizon (traditional Indian standard).
    Drik  = upper limb visible at the horizon (modern civil standard).

    Dawn/dusk use astral library (civil twilight, depression=6°).
    """
    tz = ZoneInfo(timezone_str)

    # Vedic sunrise/sunset (center of disk — default for all calculations)
    jd_vedic_rise = _swe_rise_set(target_date, latitude, longitude, _CALC_RISE, disc_center=True)
    jd_vedic_set  = _swe_rise_set(target_date, latitude, longitude, _CALC_SET,  disc_center=True)

    vedic_sunrise = _jd_to_datetime(jd_vedic_rise, tz)
    vedic_sunset  = _jd_to_datetime(jd_vedic_set,  tz)

    # Drik sunrise/sunset (upper limb — for reference display)
    jd_drik_rise = _swe_rise_set(target_date, latitude, longitude, _CALC_RISE, disc_center=False)
    jd_drik_set  = _swe_rise_set(target_date, latitude, longitude, _CALC_SET,  disc_center=False)

    drik_sunrise = _jd_to_datetime(jd_drik_rise, tz)
    drik_sunset  = _jd_to_datetime(jd_drik_set,  tz)

    # Dawn/dusk via astral (civil twilight at 6° depression)
    location = LocationInfo(name=city, region="", timezone=timezone_str,
                            latitude=latitude, longitude=longitude)
    try:
        dawn_local = dawn(location.observer, target_date, depression=6).astimezone(tz)
        dusk_local = dusk(location.observer, target_date, depression=6).astimezone(tz)
    except ValueError:
        dawn_local = vedic_sunrise
        dusk_local = vedic_sunset

    day_hrs = (vedic_sunset - vedic_sunrise).total_seconds() / 3600.0

    return SunTimes(
        sunrise=vedic_sunrise,
        sunset=vedic_sunset,
        sunrise_apparent=drik_sunrise,
        sunset_apparent=drik_sunset,
        dawn=dawn_local,
        dusk=dusk_local,
        day_duration_hrs=day_hrs,
    )


def compute_next_sunrise(
    target_date: date,
    latitude: float,
    longitude: float,
    timezone_str: str,
) -> datetime:
    """Next day's Vedic sunrise (needed for night hora, lagna, etc.)."""
    next_date = target_date + timedelta(days=1)
    tz = ZoneInfo(timezone_str)
    jd = _swe_rise_set(next_date, latitude, longitude, _CALC_RISE, disc_center=True)
    return _jd_to_datetime(jd, tz)


def compute_prev_sunset(
    target_date: date,
    latitude: float,
    longitude: float,
    timezone_str: str,
) -> datetime:
    """Previous day's Vedic sunset (needed for Brahma Muhurta night-muhurta calc)."""
    prev_date = target_date - timedelta(days=1)
    tz = ZoneInfo(timezone_str)
    jd = _swe_rise_set(prev_date, latitude, longitude, _CALC_SET, disc_center=True)
    return _jd_to_datetime(jd, tz)


# ──────────────────────────────────────────────────────────────────
#  Chandrodaya / Chandrasta — Moonrise & Moonset
# ──────────────────────────────────────────────────────────────────

def compute_moonrise_moonset(
    target_date: date,
    latitude: float,
    longitude: float,
    timezone_str: str,
) -> tuple:
    """
    Compute moonrise and moonset for the given date.

    Returns (vedic_rise, vedic_set, drik_rise, drik_set):
      - Vedic: center of Moon's disk touches the horizon (traditional)
      - Drik:  upper limb of Moon's disk visible (modern civil standard)

    Searches from local midnight. Either may be None if the Moon doesn't
    rise or set that day (extremely rare at Indian latitudes).
    """
    tz = ZoneInfo(timezone_str)

    # Start from local midnight → JD UT
    local_midnight = datetime(
        target_date.year, target_date.month, target_date.day,
        0, 0, 0, tzinfo=tz,
    )
    utc_midnight = local_midnight.astimezone(ZoneInfo("UTC"))
    jd_start = swe.julday(
        utc_midnight.year, utc_midnight.month, utc_midnight.day,
        utc_midnight.hour + utc_midnight.minute / 60.0 + utc_midnight.second / 3600.0,
    )

    geopos = (longitude, latitude, 0.0)

    def _moon_event(rise_or_set: int, disc_center: bool) -> Optional[datetime]:
        """Compute a single moon rise/set event."""
        rsmi = rise_or_set
        if disc_center:
            rsmi |= _BIT_DISC_CENTER
        try:
            result = swe.rise_trans(jd_start, swe.MOON, rsmi, geopos, 1013.25, 15)
            dt = _jd_to_datetime(result[1][0], tz)
            if dt.date() == target_date or dt.date() == target_date + timedelta(days=1):
                return dt
        except Exception:
            pass
        return None

    # Vedic: center of Moon's disk at horizon
    vedic_rise = _moon_event(_CALC_RISE, disc_center=True)
    vedic_set  = _moon_event(_CALC_SET,  disc_center=True)

    # Drik: upper limb at horizon
    drik_rise = _moon_event(_CALC_RISE, disc_center=False)
    drik_set  = _moon_event(_CALC_SET,  disc_center=False)

    return vedic_rise, vedic_set, drik_rise, drik_set


# ──────────────────────────────────────────────────────────────────
#  Dina Vibhaga — 15 Daytime Muhurtas (sunrise → sunset)
# ──────────────────────────────────────────────────────────────────

def compute_dina_muhurtas(
    sunrise: datetime,
    sunset: datetime,
    weekday: int,
    lang: str = "en",
) -> list[MuhurtaEntry]:
    """
    Divide the day (sunrise → sunset) into 15 equal muhurtas.

    Each muhurta has a traditional name and pāṭhāntara (variant reading).
    The 8th muhurta (Vidhi / Abhijit) is the most auspicious, around local noon.
    Durmuhurta flags are set based on the weekday.
    """
    muhurta_sec = (sunset - sunrise).total_seconds() / 15
    durmuhurta_nums = set(DURMUHURTA[weekday])  # 1-based

    entries = []
    for i in range(15):
        num = i + 1
        start = sunrise + timedelta(seconds=i * muhurta_sec)
        end = sunrise + timedelta(seconds=(i + 1) * muhurta_sec)
        entries.append(MuhurtaEntry(
            number=num,
            name=name(DINA_MUHURTA_NAMES, i, lang),
            starts_at=start,
            ends_at=end,
            guna=DINA_MUHURTA_GUNA[i],
            alt_name=name(DINA_MUHURTA_ALT, i, lang),
            is_durmuhurta=(num in durmuhurta_nums),
            is_abhijit=(num == 8),
        ))
    return entries


# ──────────────────────────────────────────────────────────────────
#  Ratri Vibhaga — 15 Night-time Muhurtas (sunset → next sunrise)
# ──────────────────────────────────────────────────────────────────

def compute_ratri_muhurtas(
    sunset: datetime,
    next_sunrise: datetime,
    lang: str = "en",
) -> list:
    """
    Divide the night (sunset → next sunrise) into 15 equal muhurtas.

    Each muhurta has a traditional name and pāṭhāntara (variant reading).
    Key muhurtas (1-based):
      #8  Vidhātṛ (Dhātṛ)  — Nishitha (निशीथ), midnight, Shiva puja
      #11 Jīva (Amṛta)     — Amṛt Kālam, very auspicious
      #14 Brahma (Brāhma)  — Brahma Muhurta, very auspicious, pre-dawn
    """
    muhurta_sec = (next_sunrise - sunset).total_seconds() / 15

    entries = []
    for i in range(15):
        num = i + 1
        start = sunset + timedelta(seconds=i * muhurta_sec)
        end = sunset + timedelta(seconds=(i + 1) * muhurta_sec)
        entries.append(MuhurtaEntry(
            number=num,
            name=name(RATRI_MUHURTA_NAMES, i, lang),
            starts_at=start,
            ends_at=end,
            guna=RATRI_MUHURTA_GUNA[i],
            alt_name=name(RATRI_MUHURTA_ALT, i, lang),
            is_durmuhurta=False,
            is_abhijit=False,
            is_nishita=(num == 8),
            is_brahma=(num == 14),
            is_amrit=(num == 11),
        ))
    return entries


# ──────────────────────────────────────────────────────────────────
#  Day-Part Divisions (1/8th slots for Rahu Kala etc.)
# ──────────────────────────────────────────────────────────────────

def compute_day_slot(sunrise: datetime, sunset: datetime, slot_index: int) -> TimePeriod:
    """Divide day into 8 equal slots, return time window for the given slot."""
    slot_sec = (sunset - sunrise).total_seconds() / 8
    start = sunrise + timedelta(seconds=slot_index * slot_sec)
    end   = sunrise + timedelta(seconds=(slot_index + 1) * slot_sec)
    return TimePeriod(name="", starts_at=start, ends_at=end)


def compute_rahu_kala(sunrise: datetime, sunset: datetime, weekday: int) -> TimePeriod:
    p = compute_day_slot(sunrise, sunset, RAHU_KALA[weekday])
    p.name = "Rahu Kala"
    return p


def compute_yamagandam(sunrise: datetime, sunset: datetime, weekday: int) -> TimePeriod:
    p = compute_day_slot(sunrise, sunset, YAMAGANDAM[weekday])
    p.name = "Yamagandam"
    return p


def compute_gulika_kala(sunrise: datetime, sunset: datetime, weekday: int) -> TimePeriod:
    p = compute_day_slot(sunrise, sunset, GULIKA_KALA[weekday])
    p.name = "Gulika Kala"
    return p


# ──────────────────────────────────────────────────────────────────
#  Durmuhurta — Inauspicious muhurtas
#  Day is divided into 15 muhurtas (sunrise → sunset).
# ──────────────────────────────────────────────────────────────────

def compute_durmuhurta(sunrise: datetime, sunset: datetime, weekday: int) -> list[TimePeriod]:
    """
    Compute Durmuhurta periods for the day.

    Day (sunrise to sunset) is divided into 15 equal muhurtas.
    Which muhurtas are 'dur' depends on the weekday.
    Source: Dharmasindhu.
    """
    muhurta_sec = (sunset - sunrise).total_seconds() / 15
    periods = []
    for muhurta_num in DURMUHURTA[weekday]:
        idx = muhurta_num - 1  # convert 1-based to 0-based
        start = sunrise + timedelta(seconds=idx * muhurta_sec)
        end = sunrise + timedelta(seconds=(idx + 1) * muhurta_sec)
        periods.append(TimePeriod(
            name=f"Durmuhurta ({muhurta_num}/15)",
            starts_at=start,
            ends_at=end,
        ))
    return periods


# ──────────────────────────────────────────────────────────────────
#  Varjyam — Inauspicious period based on Nakshatra
# ──────────────────────────────────────────────────────────────────

def compute_varjyam(
    nakshatra_index: int,
    nakshatra_start_jd: float,
    sunrise: datetime,
    next_sunrise: datetime,
    tz: ZoneInfo,
) -> list[TimePeriod]:
    """
    Compute Varjyam period for a nakshatra.

    Each nakshatra has a specific ghati offset from its start time where
    the Varjyam (inauspicious period) begins. Duration: ~4 ghatis (≈96 min).

    Only returns the Varjyam if it falls within the current Hindu day
    (sunrise to next sunrise).
    """
    if nakshatra_index < 0 or nakshatra_index >= 27:
        return []

    ghati_offset = VARJYAM_GHATI_OFFSET[nakshatra_index]
    ghati_duration = VARJYAM_DURATION_GHATI

    # 1 ghati = 24 minutes
    offset_minutes = ghati_offset * 24
    duration_minutes = ghati_duration * 24  # 96 minutes

    # Varjyam start = nakshatra start + offset
    # nakshatra_start_jd is Julian Day UT
    varjyam_start_jd = nakshatra_start_jd + (offset_minutes / (24 * 60))
    varjyam_start = _jd_to_datetime(varjyam_start_jd, tz)
    varjyam_end = varjyam_start + timedelta(minutes=duration_minutes)

    # Only include if it overlaps with the current Hindu day
    if varjyam_end <= sunrise or varjyam_start >= next_sunrise:
        return []

    # Clamp to day boundaries
    if varjyam_start < sunrise:
        varjyam_start = sunrise
    if varjyam_end > next_sunrise:
        varjyam_end = next_sunrise

    return [TimePeriod(
        name="Varjyam",
        starts_at=varjyam_start,
        ends_at=varjyam_end,
    )]


# ──────────────────────────────────────────────────────────────────
#  Amrit Kalam — Auspicious period based on Nakshatra
# ──────────────────────────────────────────────────────────────────

def compute_amrit_kalam(
    nakshatra_index: int,
    nakshatra_start_jd: float,
    sunrise: datetime,
    next_sunrise: datetime,
    tz: ZoneInfo,
) -> list[TimePeriod]:
    """
    Compute Amrit Kalam (auspicious period) for a nakshatra.

    Each nakshatra has a specific ghati offset from its start time where
    the Amrit Kalam begins. Duration: ~4 ghatis (≈96 min).
    This is the auspicious counterpart to Varjyam.

    Only returns the Amrit Kalam if it falls within the current Hindu day
    (sunrise to next sunrise).
    """
    if nakshatra_index < 0 or nakshatra_index >= 27:
        return []

    ghati_offset = AMRIT_KALAM_GHATI_OFFSET[nakshatra_index]
    ghati_duration = AMRIT_KALAM_DURATION_GHATI

    offset_minutes = ghati_offset * 24        # 1 ghati = 24 minutes
    duration_minutes = ghati_duration * 24    # 96 minutes

    amrit_start_jd = nakshatra_start_jd + (offset_minutes / (24 * 60))
    amrit_start = _jd_to_datetime(amrit_start_jd, tz)
    amrit_end = amrit_start + timedelta(minutes=duration_minutes)

    # Only include if it overlaps with the current Hindu day
    if amrit_end <= sunrise or amrit_start >= next_sunrise:
        return []

    # Clamp to day boundaries
    if amrit_start < sunrise:
        amrit_start = sunrise
    if amrit_end > next_sunrise:
        amrit_end = next_sunrise

    return [TimePeriod(
        name="Amrit Kalam",
        starts_at=amrit_start,
        ends_at=amrit_end,
    )]


# ──────────────────────────────────────────────────────────────────
#  Brahma Muhurta & Abhijit Muhurta
# ──────────────────────────────────────────────────────────────────

def compute_brahma_muhurta(sunrise: datetime, prev_sunset: datetime) -> TimePeriod:
    """
    Brahma Muhurta: 2 night-muhurtas before sunrise.

    Night is divided into 15 equal muhurtas (prev_sunset → sunrise).
    Brahma Muhurta = the 14th muhurta of the night = 2 muhurtas before sunrise.
    Duration varies with night length.
    """
    night_muhurta_sec = (sunrise - prev_sunset).total_seconds() / 15
    start = sunrise - timedelta(seconds=2 * night_muhurta_sec)
    end = sunrise - timedelta(seconds=1 * night_muhurta_sec)
    return TimePeriod(name="Brahma Muhurta", starts_at=start, ends_at=end)


def compute_abhijit_muhurta(sunrise: datetime, sunset: datetime) -> TimePeriod:
    """
    Abhijit Muhurta: the 8th of 15 equal daytime muhurtas.

    This is the muhurta at local noon — the most auspicious period of the day.
    Duration varies with day length (shorter in winter, longer in summer).
    """
    muhurta_sec = (sunset - sunrise).total_seconds() / 15
    start = sunrise + timedelta(seconds=7 * muhurta_sec)  # 8th muhurta (0-based: 7)
    end = sunrise + timedelta(seconds=8 * muhurta_sec)
    return TimePeriod(name="Abhijit Muhurta", starts_at=start, ends_at=end)


# ──────────────────────────────────────────────────────────────────
#  Hora Table (Planetary Hours)
# ──────────────────────────────────────────────────────────────────

def compute_hora_table(
    sunrise: datetime,
    sunset: datetime,
    next_sunrise: datetime,
    weekday: int,
    lang: str = "en",
) -> list[HoraEntry]:
    """
    24 planetary horas: 12 day (sunrise→sunset) + 12 night (sunset→next sunrise).
    Planet order follows the Chaldean cycle starting from the day's lord.
    """
    entries = []
    cycle_start = HORA_WEEKDAY_START[weekday]

    day_sec = (sunset - sunrise).total_seconds() / 12
    for i in range(12):
        pidx = (cycle_start + i) % 7
        entries.append(HoraEntry(
            planet=name(HORA_CYCLE, pidx, lang),
            number=i + 1, is_day_hora=True,
            starts_at=sunrise + timedelta(seconds=i * day_sec),
            ends_at=sunrise + timedelta(seconds=(i + 1) * day_sec),
        ))

    night_sec = (next_sunrise - sunset).total_seconds() / 12
    for i in range(12):
        pidx = (cycle_start + 12 + i) % 7
        entries.append(HoraEntry(
            planet=name(HORA_CYCLE, pidx, lang),
            number=i + 13, is_day_hora=False,
            starts_at=sunset + timedelta(seconds=i * night_sec),
            ends_at=sunset + timedelta(seconds=(i + 1) * night_sec),
        ))

    return entries
