"""
Kaalavidya — Chandra (Moon) Module

The heart of Panchanga calculations. Computes:
  - Tithi (lunar day) with exact transition times + devata/group
  - Nakshatra (lunar mansion) with transition times, pada, devata, graha lord
  - Yoga (soli-lunar combination) with transition times
  - Karana (half-tithi) with transition times
  - Moon and Sun rashi (zodiac sign)

All positions use Lahiri Ayanamsha (sidereal/nirayana system),
the standard for Indian Panchanga and Jyotish.

Methodology:
  We scan the day (sunrise to next sunrise) in small steps and detect
  when a tithi/nakshatra/yoga/karana boundary is crossed. Then we use
  binary search to pinpoint the exact transition moment.
"""

from datetime import date, datetime, timedelta
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
    AYANAMSHA_LAHIRI,
    TITHI_SPAN, NAKSHATRA_SPAN, YOGA_SPAN, KARANA_SPAN,
    TOTAL_TITHIS, TOTAL_NAKSHATRAS, TOTAL_YOGAS, TOTAL_KARANAS,
    TOTAL_RASHIS,
    tithi_name, karana_name, name,
    NAKSHATRA, YOGA, RASHI,
    TITHI_DEVATA, TITHI_GROUP_NAMES, TITHI_GROUP_INDEX,
    NAKSHATRA_DEVATA, NAKSHATRA_GRAHA,
    TARA_NAMES, TARA_GUNA, CHANDRABALAM_GOOD,
)
from kaalavidya.models import (
    TithiEntry, NakshatraEntry, YogaEntry, KaranaEntry, RashiInfo, MasaInfo,
    MaudhyaInfo,
)


# ──────────────────────────────────────────────────────────────────
#  Swiss Ephemeris Setup
# ──────────────────────────────────────────────────────────────────

swe.set_sid_mode(AYANAMSHA_LAHIRI)


# ──────────────────────────────────────────────────────────────────
#  Longitude Provider — Switchable Engine
#
#  By default, longitudes come from Swiss Ephemeris (Drik ganita).
#  When the Surya Siddhanta engine is active, these are replaced
#  with SS-computed positions. All downstream functions (tithi,
#  nakshatra, yoga, karana, rashi, masa, etc.) automatically use
#  whichever provider is active.
# ──────────────────────────────────────────────────────────────────

_longitude_provider = "drik"   # "drik" or "ss"


def set_longitude_provider(provider: str):
    """Switch the longitude computation engine: 'drik' or 'ss'."""
    global _longitude_provider
    assert provider in ("drik", "ss"), f"Unknown provider: {provider}"
    _longitude_provider = provider


from contextlib import contextmanager

@contextmanager
def use_ss_longitudes():
    """
    Context manager to temporarily switch to Surya Siddhanta longitudes.

    Usage:
        with use_ss_longitudes():
            tithi = compute_tithi(sunrise, next_sunrise)
            # All positions use SS formulas within this block
    """
    global _longitude_provider
    old = _longitude_provider
    _longitude_provider = "ss"
    try:
        yield
    finally:
        _longitude_provider = old


def _ss_moon_longitude(jd: float) -> float:
    """Moon longitude from Surya Siddhanta (lazy import to avoid circular)."""
    from kaalavidya.surya_siddhanta.ganita import compute_ahargana, compute_moon_true
    return compute_moon_true(compute_ahargana(jd))


def _ss_sun_longitude(jd: float) -> float:
    """Sun longitude from Surya Siddhanta (lazy import to avoid circular)."""
    from kaalavidya.surya_siddhanta.ganita import compute_ahargana, compute_sun_true
    return compute_sun_true(compute_ahargana(jd))


# ──────────────────────────────────────────────────────────────────
#  Low-Level Astronomical Helpers
# ──────────────────────────────────────────────────────────────────

def datetime_to_jd(dt: datetime) -> float:
    """Convert a timezone-aware datetime to Julian Day (UTC)."""
    from datetime import timezone
    if dt.tzinfo is not None:
        utc_dt = dt.astimezone(timezone.utc)
    else:
        utc_dt = dt
    return swe.julday(
        utc_dt.year, utc_dt.month, utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    )


def jd_to_datetime(jd: float, tz) -> datetime:
    """Convert Julian Day back to a timezone-aware datetime."""
    from datetime import timezone
    year, month, day, hour_dec = swe.revjul(jd)
    hour = int(hour_dec)
    minute_dec = (hour_dec - hour) * 60
    minute = int(minute_dec)
    second = int((minute_dec - minute) * 60)
    utc_dt = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    return utc_dt.astimezone(tz)


def moon_longitude(jd: float) -> float:
    """
    Sidereal longitude of the Moon. Returns 0–360.
    Uses Drik (Swiss Ephemeris / Lahiri) or Surya Siddhanta,
    depending on the active longitude provider.
    """
    if _longitude_provider == "ss":
        return _ss_moon_longitude(jd)
    flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
    result = swe.calc_ut(jd, swe.MOON, flags)
    return result[0][0] % 360


def sun_longitude(jd: float) -> float:
    """
    Sidereal longitude of the Sun. Returns 0–360.
    Uses Drik (Swiss Ephemeris / Lahiri) or Surya Siddhanta,
    depending on the active longitude provider.
    """
    if _longitude_provider == "ss":
        return _ss_sun_longitude(jd)
    flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
    result = swe.calc_ut(jd, swe.SUN, flags)
    return result[0][0] % 360


def elongation(jd: float) -> float:
    """Moon–Sun elongation (sidereal). Determines tithi."""
    return (moon_longitude(jd) - sun_longitude(jd)) % 360


def yoga_angle(jd: float) -> float:
    """Sum of Moon and Sun longitudes (mod 360). Determines yoga."""
    return (moon_longitude(jd) + sun_longitude(jd)) % 360


# ──────────────────────────────────────────────────────────────────
#  Transition Detection Engine
# ──────────────────────────────────────────────────────────────────

def _get_index(angle: float, span: float, total: int) -> int:
    """Which segment does this angle fall in?"""
    return int(angle / span) % total


def _find_transitions(
    angle_func,
    span: float,
    total: int,
    start_jd: float,
    end_jd: float,
    scan_step_minutes: int = 10,
    precision_minutes: float = 0.5,
) -> list[tuple[float, int, int]]:
    """
    Find all moments when angle_func(jd)/span crosses an integer boundary.
    Returns list of (transition_jd, old_index, new_index).
    """
    transitions = []
    step = scan_step_minutes / (24 * 60)
    precision = precision_minutes / (24 * 60)

    prev_jd = start_jd
    prev_idx = _get_index(angle_func(start_jd), span, total)

    current_jd = start_jd + step
    while current_jd <= end_jd:
        curr_idx = _get_index(angle_func(current_jd), span, total)
        if curr_idx != prev_idx:
            exact_jd = _binary_search_transition(
                angle_func, span, total, prev_jd, current_jd, prev_idx, precision
            )
            transitions.append((exact_jd, prev_idx, curr_idx))
            prev_idx = curr_idx
        prev_jd = current_jd
        current_jd += step

    return transitions


def _binary_search_transition(
    angle_func, span, total,
    lo_jd, hi_jd, lo_idx, precision,
) -> float:
    """Binary search for the exact transition moment."""
    while (hi_jd - lo_jd) > precision:
        mid_jd = (lo_jd + hi_jd) / 2
        mid_idx = _get_index(angle_func(mid_jd), span, total)
        if mid_idx == lo_idx:
            lo_jd = mid_jd
        else:
            hi_jd = mid_jd
    return (lo_jd + hi_jd) / 2


# ──────────────────────────────────────────────────────────────────
#  Adhipati Helpers
# ──────────────────────────────────────────────────────────────────

def _tithi_devata(within_paksha: int, lang: str = "en") -> str:
    """Get devata for a tithi (0-14 within paksha)."""
    return name(TITHI_DEVATA, within_paksha, lang)


def _tithi_group(within_paksha: int, lang: str = "en") -> str:
    """Get group name (Nanda/Bhadra/Jaya/Rikta/Purna) for a tithi (0-14)."""
    group_idx = TITHI_GROUP_INDEX[within_paksha]
    return name(TITHI_GROUP_NAMES, group_idx, lang)


def _nakshatra_devata(nak_idx: int, lang: str = "en") -> str:
    """Get devata for a nakshatra (0-26)."""
    return name(NAKSHATRA_DEVATA, nak_idx, lang)


def _nakshatra_graha(nak_idx: int, lang: str = "en") -> str:
    """Get Vimsottari dasha lord for a nakshatra (0-26)."""
    return name(NAKSHATRA_GRAHA, nak_idx, lang)


# ──────────────────────────────────────────────────────────────────
#  High-Level Panchanga Element Computations
# ──────────────────────────────────────────────────────────────────

def compute_tithi(
    sunrise_dt: datetime,
    next_sunrise_dt: datetime,
    lang: str = "en",
) -> list[TithiEntry]:
    """
    Compute tithi(s) active during the Hindu day with devata and group.

    Every entry always has both starts_at and ends_at filled in —
    even if the boundary falls on the previous or next calendar day.
    The frontend uses -1 / +1 day indicators accordingly.
    """
    tz = sunrise_dt.tzinfo
    start_jd = datetime_to_jd(sunrise_dt)
    end_jd = datetime_to_jd(next_sunrise_dt)

    sunrise_angle = elongation(start_jd)
    sunrise_idx = _get_index(sunrise_angle, TITHI_SPAN, TOTAL_TITHIS)

    transitions = _find_transitions(
        elongation, TITHI_SPAN, TOTAL_TITHIS, start_jd, end_jd
    )

    # ── Always find real start of the sunrise tithi (may be previous day) ──
    actual_start_jd = _find_element_start_before(
        elongation, TITHI_SPAN, TOTAL_TITHIS, start_jd, sunrise_idx
    )

    entries = []
    within = sunrise_idx % 15

    if not transitions:
        # Tithi spans the entire Hindu day — find when it ends after next sunrise
        actual_end_jd = _find_element_end_after(
            elongation, TITHI_SPAN, TOTAL_TITHIS, end_jd, sunrise_idx
        )
        entries.append(TithiEntry(
            index=sunrise_idx,
            name=tithi_name(sunrise_idx, lang),
            devata=_tithi_devata(within, lang),
            group=_tithi_group(within, lang),
            starts_at=jd_to_datetime(actual_start_jd, tz),
            ends_at=jd_to_datetime(actual_end_jd, tz),
            is_active_at_sunrise=True,
        ))
    else:
        entries.append(TithiEntry(
            index=sunrise_idx,
            name=tithi_name(sunrise_idx, lang),
            devata=_tithi_devata(within, lang),
            group=_tithi_group(within, lang),
            starts_at=jd_to_datetime(actual_start_jd, tz),
            ends_at=jd_to_datetime(transitions[0][0], tz),
            is_active_at_sunrise=True,
        ))
        for i, (trans_jd, old_idx, new_idx) in enumerate(transitions):
            new_within = new_idx % 15
            if i + 1 < len(transitions):
                ends_jd = transitions[i + 1][0]
            else:
                # Last tithi in the day — find when it actually ends
                ends_jd = _find_element_end_after(
                    elongation, TITHI_SPAN, TOTAL_TITHIS, end_jd, new_idx
                )
            entries.append(TithiEntry(
                index=new_idx,
                name=tithi_name(new_idx, lang),
                devata=_tithi_devata(new_within, lang),
                group=_tithi_group(new_within, lang),
                starts_at=jd_to_datetime(trans_jd, tz),
                ends_at=jd_to_datetime(ends_jd, tz),
            ))

    return entries


def compute_nakshatra(
    sunrise_dt: datetime,
    next_sunrise_dt: datetime,
    lang: str = "en",
) -> tuple[list[NakshatraEntry], list[tuple[int, float]]]:
    """
    Compute nakshatra(s) active during the Hindu day.

    Returns:
        (entries, nakshatra_start_jds)
        nakshatra_start_jds: list of (nakshatra_index, start_jd) —
          needed for Varjyam calculation.
    """
    tz = sunrise_dt.tzinfo
    start_jd = datetime_to_jd(sunrise_dt)
    end_jd = datetime_to_jd(next_sunrise_dt)

    sunrise_moon = moon_longitude(start_jd)
    sunrise_idx = _get_index(sunrise_moon, NAKSHATRA_SPAN, TOTAL_NAKSHATRAS)
    sunrise_pada = _compute_pada(sunrise_moon, sunrise_idx)

    transitions = _find_transitions(
        moon_longitude, NAKSHATRA_SPAN, TOTAL_NAKSHATRAS, start_jd, end_jd
    )

    entries = []
    nak_start_jds = []  # (index, start_jd) for Varjyam

    # Find when the sunrise nakshatra started (search backwards)
    sunrise_nak_start_jd = _find_nakshatra_start_before(start_jd, sunrise_idx)
    nak_start_jds.append((sunrise_idx, sunrise_nak_start_jd))

    # ── Always find real start of the sunrise nakshatra ──
    actual_start_jd = sunrise_nak_start_jd  # already computed above

    # Build raw nakshatra entries (one per nakshatra), then split by pada
    raw_entries = []

    if not transitions:
        actual_end_jd = _find_element_end_after(
            moon_longitude, NAKSHATRA_SPAN, TOTAL_NAKSHATRAS, end_jd, sunrise_idx
        )
        raw_entries.append(NakshatraEntry(
            index=sunrise_idx,
            name=name(NAKSHATRA, sunrise_idx, lang),
            pada=sunrise_pada,
            devata=_nakshatra_devata(sunrise_idx, lang),
            graha_lord=_nakshatra_graha(sunrise_idx, lang),
            starts_at=jd_to_datetime(actual_start_jd, tz),
            ends_at=jd_to_datetime(actual_end_jd, tz),
            is_active_at_sunrise=True,
        ))
    else:
        raw_entries.append(NakshatraEntry(
            index=sunrise_idx,
            name=name(NAKSHATRA, sunrise_idx, lang),
            pada=sunrise_pada,
            devata=_nakshatra_devata(sunrise_idx, lang),
            graha_lord=_nakshatra_graha(sunrise_idx, lang),
            starts_at=jd_to_datetime(actual_start_jd, tz),
            ends_at=jd_to_datetime(transitions[0][0], tz),
            is_active_at_sunrise=True,
        ))
        for i, (trans_jd, old_idx, new_idx) in enumerate(transitions):
            trans_moon = moon_longitude(trans_jd + 0.001)
            new_pada = _compute_pada(trans_moon, new_idx)
            nak_start_jds.append((new_idx, trans_jd))
            if i + 1 < len(transitions):
                ends_jd = transitions[i + 1][0]
            else:
                ends_jd = _find_element_end_after(
                    moon_longitude, NAKSHATRA_SPAN, TOTAL_NAKSHATRAS, end_jd, new_idx
                )
            raw_entries.append(NakshatraEntry(
                index=new_idx,
                name=name(NAKSHATRA, new_idx, lang),
                pada=new_pada,
                devata=_nakshatra_devata(new_idx, lang),
                graha_lord=_nakshatra_graha(new_idx, lang),
                starts_at=jd_to_datetime(trans_jd, tz),
                ends_at=jd_to_datetime(ends_jd, tz),
            ))

    # ── Split each entry by pada transitions ──
    for raw in raw_entries:
        entries.extend(_split_entry_by_pada(raw, raw.index, lang))

    # ── Filter: exclude pada entries that START after next sunrise ──
    # Such entries belong to the next Hindu day.
    entries = [e for e in entries if e.starts_at is None or e.starts_at < next_sunrise_dt]

    return entries, nak_start_jds


def _find_element_start_before(
    angle_func, span: float, total: int,
    start_jd: float, expected_idx: int,
    step_hours: float = 1.0,
    max_steps: int = 72,
) -> float:
    """
    Search BACKWARDS from start_jd to find when element *expected_idx* began.
    Returns the Julian Day of the transition into this element.
    """
    step = step_hours / 24
    current_jd = start_jd

    for _ in range(max_steps):
        prev_jd = current_jd - step
        prev_idx = _get_index(angle_func(prev_jd), span, total)
        if prev_idx != expected_idx:
            return _binary_search_transition(
                angle_func, span, total,
                prev_jd, current_jd, prev_idx, 0.5 / (24 * 60)
            )
        current_jd = prev_jd

    return start_jd  # fallback


def _find_element_end_after(
    angle_func, span: float, total: int,
    end_jd: float, expected_idx: int,
    step_hours: float = 1.0,
    max_steps: int = 72,
) -> float:
    """
    Search FORWARDS from end_jd to find when element *expected_idx* ends.
    Returns the Julian Day of the transition out of this element.
    """
    step = step_hours / 24
    current_jd = end_jd

    for _ in range(max_steps):
        next_jd = current_jd + step
        next_idx = _get_index(angle_func(next_jd), span, total)
        if next_idx != expected_idx:
            return _binary_search_transition(
                angle_func, span, total,
                current_jd, next_jd, expected_idx, 0.5 / (24 * 60)
            )
        current_jd = next_jd

    return end_jd  # fallback


def _find_nakshatra_start_before(sunrise_jd: float, expected_idx: int) -> float:
    """
    Search backwards from sunrise to find when the current nakshatra began.
    Needed for Varjyam calculation of the sunrise nakshatra.
    Delegates to the generic helper.
    """
    return _find_element_start_before(
        moon_longitude, NAKSHATRA_SPAN, TOTAL_NAKSHATRAS,
        sunrise_jd, expected_idx,
    )


def _compute_pada(moon_long: float, nakshatra_idx: int) -> int:
    """Pada (quarter) of a nakshatra. Each pada = 3°20'."""
    nakshatra_start = nakshatra_idx * NAKSHATRA_SPAN
    raw_offset = (moon_long - nakshatra_start) % 360
    # Clamp to valid range within nakshatra.
    # At exact boundary, floating-point may give offset ≈ 360 instead of ≈ 0,
    # which would incorrectly compute pada as 4 instead of 1.
    if raw_offset >= NAKSHATRA_SPAN:
        offset = raw_offset % NAKSHATRA_SPAN
    else:
        offset = raw_offset
    pada = int(offset / (NAKSHATRA_SPAN / 4)) + 1
    return min(pada, 4)


PADA_SPAN = NAKSHATRA_SPAN / 4  # 3°20' = 3.3333...°


def _find_pada_transitions(
    nak_idx: int,
    start_jd: float,
    end_jd: float,
    scan_step_minutes: int = 10,
    precision_minutes: float = 0.5,
) -> list[tuple[float, int, int]]:
    """
    Find pada boundary crossings within a single nakshatra.

    Returns list of (transition_jd, old_pada, new_pada).
    """
    transitions = []
    step = scan_step_minutes / (24 * 60)
    precision = precision_minutes / (24 * 60)

    prev_jd = start_jd
    # Use small offset at start to avoid floating-point boundary issues
    prev_pada = _compute_pada(moon_longitude(start_jd + 0.0001), nak_idx)

    current_jd = start_jd + step
    while current_jd <= end_jd:
        curr_pada = _compute_pada(moon_longitude(current_jd), nak_idx)
        if curr_pada != prev_pada:
            # Binary search for exact pada boundary
            lo, hi = prev_jd, current_jd
            while (hi - lo) > precision:
                mid = (lo + hi) / 2
                mid_pada = _compute_pada(moon_longitude(mid), nak_idx)
                if mid_pada == prev_pada:
                    lo = mid
                else:
                    hi = mid
            exact_jd = (lo + hi) / 2
            transitions.append((exact_jd, prev_pada, curr_pada))
            prev_pada = curr_pada
        prev_jd = current_jd
        current_jd += step

    return transitions


def _split_entry_by_pada(
    entry: NakshatraEntry,
    nak_idx: int,
    lang: str,
) -> list[NakshatraEntry]:
    """
    Split a single NakshatraEntry into multiple entries if pada changes
    within its time span. Returns a list (often 1-3 entries).

    Always computes the actual pada at entry.starts_at rather than
    relying on entry.pada (which may be the pada at sunrise, not at
    the entry's actual start time).
    """
    if entry.starts_at is None or entry.ends_at is None:
        return [entry]

    start_jd = datetime_to_jd(entry.starts_at)
    end_jd = datetime_to_jd(entry.ends_at)

    # Compute actual pada at entry start (not sunrise pada).
    # Use a tiny JD offset (+0.0001 ≈ 8.6 seconds) to avoid floating-point
    # issues at exact nakshatra boundaries where the longitude may be
    # infinitesimally below the boundary, causing pada to appear as 4
    # instead of 1.
    start_moon = moon_longitude(start_jd + 0.0001)
    actual_start_pada = _compute_pada(start_moon, nak_idx)

    pada_trans = _find_pada_transitions(nak_idx, start_jd, end_jd)

    if not pada_trans:
        # No pada change — return single entry with corrected pada
        return [NakshatraEntry(
            index=entry.index,
            name=entry.name,
            pada=actual_start_pada,
            devata=entry.devata,
            graha_lord=entry.graha_lord,
            starts_at=entry.starts_at,
            ends_at=entry.ends_at,
            is_active_at_sunrise=entry.is_active_at_sunrise,
        )]

    tz = entry.starts_at.tzinfo
    results = []

    # First sub-entry: from original start to first pada transition
    first_end_jd = pada_trans[0][0]
    results.append(NakshatraEntry(
        index=entry.index,
        name=entry.name,
        pada=actual_start_pada,
        devata=entry.devata,
        graha_lord=entry.graha_lord,
        starts_at=entry.starts_at,
        ends_at=jd_to_datetime(first_end_jd, tz),
        is_active_at_sunrise=entry.is_active_at_sunrise,
    ))

    # Subsequent sub-entries (pada transitions)
    for i, (trans_jd, old_pada, new_pada) in enumerate(pada_trans):
        sub_end_jd = pada_trans[i + 1][0] if i + 1 < len(pada_trans) else end_jd
        results.append(NakshatraEntry(
            index=entry.index,
            name=entry.name,
            pada=new_pada,
            devata=entry.devata,
            graha_lord=entry.graha_lord,
            starts_at=jd_to_datetime(trans_jd, tz),
            ends_at=jd_to_datetime(sub_end_jd, tz),
            is_active_at_sunrise=False,
        ))

    return results


def compute_yoga(
    sunrise_dt: datetime,
    next_sunrise_dt: datetime,
    lang: str = "en",
) -> list[YogaEntry]:
    """Compute yoga(s) active during the Hindu day — always with full start/end times."""
    tz = sunrise_dt.tzinfo
    start_jd = datetime_to_jd(sunrise_dt)
    end_jd = datetime_to_jd(next_sunrise_dt)

    sunrise_angle = yoga_angle(start_jd)
    sunrise_idx = _get_index(sunrise_angle, YOGA_SPAN, TOTAL_YOGAS)

    transitions = _find_transitions(
        yoga_angle, YOGA_SPAN, TOTAL_YOGAS, start_jd, end_jd
    )

    actual_start_jd = _find_element_start_before(
        yoga_angle, YOGA_SPAN, TOTAL_YOGAS, start_jd, sunrise_idx
    )

    entries = []
    if not transitions:
        actual_end_jd = _find_element_end_after(
            yoga_angle, YOGA_SPAN, TOTAL_YOGAS, end_jd, sunrise_idx
        )
        entries.append(YogaEntry(
            index=sunrise_idx,
            name=name(YOGA, sunrise_idx, lang),
            starts_at=jd_to_datetime(actual_start_jd, tz),
            ends_at=jd_to_datetime(actual_end_jd, tz),
            is_active_at_sunrise=True,
        ))
    else:
        entries.append(YogaEntry(
            index=sunrise_idx,
            name=name(YOGA, sunrise_idx, lang),
            starts_at=jd_to_datetime(actual_start_jd, tz),
            ends_at=jd_to_datetime(transitions[0][0], tz),
            is_active_at_sunrise=True,
        ))
        for i, (trans_jd, old_idx, new_idx) in enumerate(transitions):
            if i + 1 < len(transitions):
                ends_jd = transitions[i + 1][0]
            else:
                ends_jd = _find_element_end_after(
                    yoga_angle, YOGA_SPAN, TOTAL_YOGAS, end_jd, new_idx
                )
            entries.append(YogaEntry(
                index=new_idx,
                name=name(YOGA, new_idx, lang),
                starts_at=jd_to_datetime(trans_jd, tz),
                ends_at=jd_to_datetime(ends_jd, tz),
            ))
    return entries


def compute_karana(
    sunrise_dt: datetime,
    next_sunrise_dt: datetime,
    lang: str = "en",
) -> list[KaranaEntry]:
    """Compute karana(s) active during the Hindu day — always with full start/end times."""
    tz = sunrise_dt.tzinfo
    start_jd = datetime_to_jd(sunrise_dt)
    end_jd = datetime_to_jd(next_sunrise_dt)

    sunrise_angle = elongation(start_jd)
    sunrise_idx = _get_index(sunrise_angle, KARANA_SPAN, TOTAL_KARANAS)

    transitions = _find_transitions(
        elongation, KARANA_SPAN, TOTAL_KARANAS, start_jd, end_jd
    )

    actual_start_jd = _find_element_start_before(
        elongation, KARANA_SPAN, TOTAL_KARANAS, start_jd, sunrise_idx
    )

    entries = []
    if not transitions:
        actual_end_jd = _find_element_end_after(
            elongation, KARANA_SPAN, TOTAL_KARANAS, end_jd, sunrise_idx
        )
        entries.append(KaranaEntry(
            index=sunrise_idx,
            name=karana_name(sunrise_idx, lang),
            starts_at=jd_to_datetime(actual_start_jd, tz),
            ends_at=jd_to_datetime(actual_end_jd, tz),
            is_active_at_sunrise=True,
        ))
    else:
        entries.append(KaranaEntry(
            index=sunrise_idx,
            name=karana_name(sunrise_idx, lang),
            starts_at=jd_to_datetime(actual_start_jd, tz),
            ends_at=jd_to_datetime(transitions[0][0], tz),
            is_active_at_sunrise=True,
        ))
        for i, (trans_jd, old_idx, new_idx) in enumerate(transitions):
            if i + 1 < len(transitions):
                ends_jd = transitions[i + 1][0]
            else:
                ends_jd = _find_element_end_after(
                    elongation, KARANA_SPAN, TOTAL_KARANAS, end_jd, new_idx
                )
            entries.append(KaranaEntry(
                index=new_idx,
                name=karana_name(new_idx, lang),
                starts_at=jd_to_datetime(trans_jd, tz),
                ends_at=jd_to_datetime(ends_jd, tz),
            ))
    return entries


# ──────────────────────────────────────────────────────────────────
#  Rashi (Zodiac Sign) Computation
# ──────────────────────────────────────────────────────────────────

def compute_moon_rashi(jd: float, lang: str = "en") -> RashiInfo:
    """Moon's rashi at the given Julian Day."""
    moon_long = moon_longitude(jd)
    rashi_idx = int(moon_long / 30) % TOTAL_RASHIS
    return RashiInfo(
        index=rashi_idx,
        name=name(RASHI, rashi_idx, lang),
        degree=round(moon_long % 30, 2),
    )


def compute_sun_rashi(jd: float, lang: str = "en") -> RashiInfo:
    """Sun's rashi at the given Julian Day."""
    sun_long = sun_longitude(jd)
    rashi_idx = int(sun_long / 30) % TOTAL_RASHIS
    return RashiInfo(
        index=rashi_idx,
        name=name(RASHI, rashi_idx, lang),
        degree=round(sun_long % 30, 2),
    )


# ──────────────────────────────────────────────────────────────────
#  Amavasya (New Moon) Detection
#  Needed for accurate Masa determination and Adhika/Kshaya detection
# ──────────────────────────────────────────────────────────────────

def find_amavasya_before(reference_jd: float) -> float:
    """
    Find the Amavasya (new moon) just before the given Julian Day.

    At new moon, Moon–Sun elongation wraps from ~360° back to ~0°.
    We scan backward in 1-day steps and detect when the elongation
    jumps up (because going backward past a new moon means going
    from a small angle to a large one).
    """
    jd = reference_jd
    prev_elong = elongation(jd)

    for _ in range(35):  # synodic month ≈ 29.5 days, 35 is safe margin
        jd -= 1.0
        curr_elong = elongation(jd)
        # Going backward: elongation at earlier time > later time by >180°
        # means we crossed a new moon boundary
        if curr_elong > prev_elong + 180:
            return _binary_search_new_moon(jd, jd + 1.0)
        prev_elong = curr_elong

    # Fallback: estimate from current elongation
    elong = elongation(reference_jd)
    return reference_jd - (elong * 29.53 / 360)


def find_amavasya_after(reference_jd: float) -> float:
    """
    Find the Amavasya (new moon) just after the given Julian Day.

    Scans forward in 1-day steps, detecting when elongation drops
    sharply (wraps from ~360° to ~0°).
    """
    jd = reference_jd
    prev_elong = elongation(jd)

    for _ in range(35):
        jd += 1.0
        curr_elong = elongation(jd)
        # Going forward: elongation drops by >180° means new moon crossed
        if curr_elong < prev_elong - 180:
            return _binary_search_new_moon(jd - 1.0, jd)
        prev_elong = curr_elong

    # Fallback: estimate
    elong = elongation(reference_jd)
    return reference_jd + ((360 - elong) * 29.53 / 360)


def _binary_search_new_moon(lo_jd: float, hi_jd: float) -> float:
    """
    Binary search for the exact new moon between lo_jd and hi_jd.

    At lo_jd, elongation is high (approaching 360°).
    At hi_jd, elongation is low (just past 0°).
    We search for the crossover point.
    """
    precision = 1.0 / (24 * 60)  # ~1 minute

    while (hi_jd - lo_jd) > precision:
        mid_jd = (lo_jd + hi_jd) / 2
        if elongation(mid_jd) > 180:
            lo_jd = mid_jd  # still on the high/approaching side
        else:
            hi_jd = mid_jd  # past the new moon

    return (lo_jd + hi_jd) / 2


# ──────────────────────────────────────────────────────────────────
#  Sankranti (Sun entering a new Rashi) Detection
# ──────────────────────────────────────────────────────────────────

def find_sankrantis_between(jd_start: float, jd_end: float) -> list[tuple[float, int]]:
    """
    Find all Sankrantis (Sun entering a new rashi) between two Julian Days.

    Returns list of (transition_jd, new_rashi_index).
    Sun moves ~1° per day, so at most one Sankranti per ~30 days.
    A normal lunar month (~29.5 days) has exactly one; Adhika has zero,
    Kshaya has two.
    """
    sankrantis = []
    step = 1.0  # 1-day steps (Sun moves ~1°/day)

    jd = jd_start
    prev_rashi = int(sun_longitude(jd) / 30) % TOTAL_RASHIS

    while jd < jd_end:
        jd += step
        curr_rashi = int(sun_longitude(min(jd, jd_end + 0.5)) / 30) % TOTAL_RASHIS

        if curr_rashi != prev_rashi:
            exact_jd = _binary_search_sankranti(jd - step, jd, prev_rashi)
            # Only include if it falls within our window
            if jd_start < exact_jd < jd_end:
                sankrantis.append((exact_jd, curr_rashi))
            prev_rashi = curr_rashi

    return sankrantis


def _binary_search_sankranti(lo_jd: float, hi_jd: float, lo_rashi: int) -> float:
    """Binary search for exact Sankranti moment (Sun changes rashi)."""
    precision = 1.0 / (24 * 60)  # ~1 minute

    while (hi_jd - lo_jd) > precision:
        mid_jd = (lo_jd + hi_jd) / 2
        if int(sun_longitude(mid_jd) / 30) % TOTAL_RASHIS == lo_rashi:
            lo_jd = mid_jd
        else:
            hi_jd = mid_jd

    return (lo_jd + hi_jd) / 2


# ──────────────────────────────────────────────────────────────────
#  Masa Computation (with Adhika/Kshaya detection)
# ──────────────────────────────────────────────────────────────────

def compute_masa(sunrise_jd: float, lang: str = "en") -> MasaInfo:
    """
    Determine the correct Amanta masa using the traditional method.

    Algorithm:
      1. Find the two Amavasyas (new moons) bracketing this date.
         These define the current lunar month in the Amanta system.
      2. Count how many Sankrantis (Sun entering a new rashi) fall
         between these two Amavasyas.
           - 0 Sankrantis → Adhika (intercalary) month
           - 1 Sankranti  → Normal month
           - 2 Sankrantis → Kshaya (skipped) month

    Naming:
      - Normal: month named after the Sankranti's rashi (MASA[rashi])
      - Adhika: same name as the following regular month, prefixed "Adhika"
      - Kshaya: named after the first Sankranti; second Sankranti's month
        is the one that is "skipped"

    Source: Surya Siddhanta, Chapter 14.
    """
    from kaalavidya.constants import MASA

    # Step 1: Find the two Amavasyas bracketing this date
    ama_before = find_amavasya_before(sunrise_jd)
    ama_after = find_amavasya_after(sunrise_jd)

    # Step 2: Find Sankrantis in this lunar month
    sankrantis = find_sankrantis_between(ama_before, ama_after)

    if len(sankrantis) == 0:
        # ── ADHIKA MASA ──
        # No Sankranti in this month. The month takes the name of the
        # next regular month (the one that follows this Adhika month).
        # To find that name: look at the next Sankranti after this month ends.
        next_sankrantis = find_sankrantis_between(ama_after, ama_after + 35)
        if next_sankrantis:
            masa_idx = next_sankrantis[0][1]
        else:
            # Extreme fallback (should never happen)
            masa_idx = int(sun_longitude(ama_after + 15) / 30) % TOTAL_RASHIS
        return MasaInfo(
            index=masa_idx,
            name=name(MASA, masa_idx, lang),
            is_adhika=True,
        )

    elif len(sankrantis) == 1:
        # ── NORMAL MONTH ──
        # The month is named after the rashi the Sun enters.
        # MASA array is aligned: MASA[0]=Chaitra matches Mesha Sankranti.
        masa_idx = sankrantis[0][1]
        return MasaInfo(
            index=masa_idx,
            name=name(MASA, masa_idx, lang),
        )

    else:
        # ── KSHAYA MASA ──
        # Two Sankrantis in one month. The month is named after the
        # first Sankranti's rashi. The second Sankranti's month is
        # the one that's "kshaya" (missing from the calendar).
        masa_idx = sankrantis[0][1]
        kshaya_idx = sankrantis[1][1]
        return MasaInfo(
            index=masa_idx,
            name=name(MASA, masa_idx, lang),
            kshaya_index=kshaya_idx,
            kshaya_name=name(MASA, kshaya_idx, lang),
        )


# ──────────────────────────────────────────────────────────────────
#  Maudhya (Planetary Combustion)
#
#  When a planet is too close to the Sun in sidereal longitude, it
#  becomes invisible in the Sun's glare and is considered "combust"
#  (maudhya / asta). During Guru or Shukra Maudhya, auspicious
#  ceremonies (especially vivaha) are traditionally avoided.
#
#  Combustion limits (Surya Siddhanta):
#    Guru (Jupiter) : 11°
#    Shukra (Venus) : 10° direct, 8° retrograde
# ──────────────────────────────────────────────────────────────────

# Planet IDs and their combustion thresholds
_MAUDHYA_PLANETS = {
    "guru":   (swe.JUPITER, 11.0, 11.0),  # (swe_id, limit_direct, limit_retro)
    "shukra": (swe.VENUS,   10.0,  8.0),
}

# Display names for the two planets
_MAUDHYA_NAMES = {
    "guru":   {"en": "Guru (Jupiter)", "sa": "गुरु", "hi": "गुरु", "te": "గురు", "ta": "குரு", "kn": "ಗುರು", "ml": "ഗുരു"},
    "shukra": {"en": "Shukra (Venus)", "sa": "शुक्र", "hi": "शुक्र", "te": "శుక్ర", "ta": "சுக்ர", "kn": "ಶುಕ್ರ", "ml": "ശുക്ര"},
}


def _planet_longitude(jd: float, planet_id: int) -> float:
    """Sidereal longitude of a planet at given Julian Day (Lahiri ayanamsha)."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    result = swe.calc_ut(jd, planet_id, swe.FLG_SIDEREAL | swe.FLG_SWIEPH)
    return result[0][0] % 360


def _planet_speed(jd: float, planet_id: int) -> float:
    """Daily speed of a planet in degrees/day. Negative = retrograde."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    result = swe.calc_ut(jd, planet_id, swe.FLG_SIDEREAL | swe.FLG_SWIEPH | swe.FLG_SPEED)
    return result[0][3]


def _angular_separation(long1: float, long2: float) -> float:
    """Minimum angular separation between two ecliptic longitudes (0–180°)."""
    diff = abs(long1 - long2) % 360
    return min(diff, 360 - diff)


def _find_combustion_boundary(
    start_jd: float,
    direction: int,
    planet_id: int,
    limit: float,
    currently_combust: bool,
) -> float:
    """
    Search forward (direction=+1) or backward (direction=-1) from start_jd
    to find the exact JD where the planet enters or exits combustion.

    If currently_combust=True, we search for the exit (separation crossing
    above the limit). If False, we search for the entry.
    """
    step = 1.0  # 1-day steps
    jd = start_jd
    max_days = 90  # Jupiter stays combust ~30–40d, Venus ~30–60d

    for _ in range(max_days):
        jd += direction * step
        sun_long = sun_longitude(jd)
        planet_long = _planet_longitude(jd, planet_id)
        sep = _angular_separation(sun_long, planet_long)

        crossed = (sep > limit) if currently_combust else (sep <= limit)
        if crossed:
            # Binary search between jd-step and jd for the exact boundary
            lo = min(jd - direction * step, jd)
            hi = max(jd - direction * step, jd)
            return _binary_search_combustion(lo, hi, planet_id, limit, currently_combust)

    # Fallback: if not found within max_days
    return jd


def _binary_search_combustion(
    lo_jd: float,
    hi_jd: float,
    planet_id: int,
    limit: float,
    searching_for_exit: bool,
) -> float:
    """Binary search for the exact moment separation crosses the limit."""
    precision = 0.01  # ~15 minutes

    while (hi_jd - lo_jd) > precision:
        mid_jd = (lo_jd + hi_jd) / 2
        sun_long = sun_longitude(mid_jd)
        planet_long = _planet_longitude(mid_jd, planet_id)
        sep = _angular_separation(sun_long, planet_long)

        if searching_for_exit:
            # Looking for sep crossing above limit
            if sep <= limit:
                lo_jd = mid_jd  # still combust, move forward
            else:
                hi_jd = mid_jd  # past the exit
        else:
            # Looking for sep crossing below limit
            if sep > limit:
                lo_jd = mid_jd  # not yet combust
            else:
                hi_jd = mid_jd  # now combust

    return (lo_jd + hi_jd) / 2


def _jd_to_date(jd: float) -> date:
    """Convert Julian Day to Python date."""
    y, m, d, _ = swe.revjul(jd)
    return date(int(y), int(m), int(d))


def compute_maudhya(sunrise_jd: float, target_date: date, lang: str = "en") -> list:
    """
    Check Guru (Jupiter) and Shukra (Venus) combustion status.

    For each planet:
      1. Get sidereal longitudes of planet and Sun at sunrise.
      2. Compute angular separation.
      3. If separation < combustion limit → planet is combust.
      4. Search backward/forward to find the exact combustion period.

    Returns list of MaudhyaInfo (always two entries: Guru and Shukra).
    """
    sun_long = sun_longitude(sunrise_jd)
    results = []

    for key, (planet_id, limit_direct, limit_retro) in _MAUDHYA_PLANETS.items():
        planet_long = _planet_longitude(sunrise_jd, planet_id)
        speed = _planet_speed(sunrise_jd, planet_id)
        is_retrograde = speed < 0

        # Use retrograde limit if applicable
        limit = limit_retro if is_retrograde else limit_direct
        separation = round(_angular_separation(sun_long, planet_long), 2)
        is_combust = separation <= limit

        # Localized planet name
        names = _MAUDHYA_NAMES[key]
        planet_display = names.get(lang, names.get("sa", names["en"]))

        period_start = None
        period_end = None

        if is_combust:
            # Find when this combustion started (search backward)
            entry_jd = _find_combustion_boundary(
                sunrise_jd, direction=-1, planet_id=planet_id,
                limit=limit, currently_combust=True,
            )
            period_start = _jd_to_date(entry_jd)

            # Find when this combustion will end (search forward)
            exit_jd = _find_combustion_boundary(
                sunrise_jd, direction=+1, planet_id=planet_id,
                limit=limit, currently_combust=True,
            )
            period_end = _jd_to_date(exit_jd)

        results.append(MaudhyaInfo(
            planet=planet_display,
            planet_key=key,
            is_combust=is_combust,
            separation_deg=separation,
            combustion_limit=limit,
            is_retrograde=is_retrograde,
            period_start=period_start,
            period_end=period_end,
        ))

    return results


# ──────────────────────────────────────────────────────────────────
#  Tarabalam (Star Strength)
#
#  For each transit nakshatra active during the day, compute the
#  Tara category for every possible Janma (birth) nakshatra.
#
#  This tells the user: "If my birth star is X, today's transit star
#  gives me Tara category Y (good/bad)."
#
#  The cycle of 9 Taras repeats 3 times over 27 nakshatras.
#
#  Returns a list of dicts — one per transit nakshatra period.
# ──────────────────────────────────────────────────────────────────

def compute_tarabalam(
    nakshatra_entries: list[NakshatraEntry],
    lang: str = "en",
) -> list[dict]:
    """
    Compute Tarabalam for each transit nakshatra active during the day.

    For each transit nakshatra, groups all 27 birth nakshatras into
    favorable and unfavorable lists.

    Args:
        nakshatra_entries: List of NakshatraEntry from compute_nakshatra().
        lang: Language code for names.

    Returns:
        List of dicts, one per transit nakshatra (deduplicated by nakshatra
        index, so pada splits are merged), each containing:
          - transit_nakshatra: name of the transit nakshatra
          - transit_index: nakshatra index (0–26)
          - starts_at: start time (ISO str or None)
          - ends_at: end time (ISO str or None)
          - favorable: list of {index, name, tara_index, tara_name}
          - unfavorable: list of {index, name, tara_index, tara_name}
    """
    # Deduplicate: merge pada-split entries back to unique nakshatras
    seen = {}
    for entry in nakshatra_entries:
        idx = entry.index
        if idx not in seen:
            seen[idx] = {
                "index": idx,
                "starts_at": entry.starts_at,
                "ends_at": entry.ends_at,
            }
        else:
            # Extend the period: earliest start, latest end
            if entry.starts_at and (seen[idx]["starts_at"] is None or entry.starts_at < seen[idx]["starts_at"]):
                seen[idx]["starts_at"] = entry.starts_at
            if entry.ends_at and (seen[idx]["ends_at"] is None or entry.ends_at > seen[idx]["ends_at"]):
                seen[idx]["ends_at"] = entry.ends_at

    results = []
    for transit_idx, period in seen.items():
        favorable = []
        unfavorable = []

        for birth_idx in range(TOTAL_NAKSHATRAS):
            count = ((transit_idx - birth_idx) % 27) + 1
            tara_idx = (count - 1) % 9
            tara_guna = TARA_GUNA[tara_idx]
            tara_name_str = name(TARA_NAMES, tara_idx, lang)
            birth_name = name(NAKSHATRA, birth_idx, lang)

            entry_dict = {
                "index": birth_idx,
                "name": birth_name,
                "tara_index": tara_idx,
                "tara_name": tara_name_str,
                "tara_guna": tara_guna,
            }

            if tara_guna > 0:  # 1=auspicious, 2=highly auspicious
                favorable.append(entry_dict)
            else:
                unfavorable.append(entry_dict)

        results.append({
            "transit_nakshatra": name(NAKSHATRA, transit_idx, lang),
            "transit_index": transit_idx,
            "starts_at": period["starts_at"].isoformat() if period["starts_at"] else None,
            "ends_at": period["ends_at"].isoformat() if period["ends_at"] else None,
            "favorable": favorable,
            "unfavorable": unfavorable,
        })

    return results


# ──────────────────────────────────────────────────────────────────
#  Chandrabalam (Moon Strength)
#
#  For each transit Moon rashi during the day, compute which birth
#  rashis have favorable and unfavorable Chandrabalam.
#
#  Moon in positions 1, 3, 6, 7, 10, 11 from Janma Rashi → favorable.
#  Moon in positions 2, 4, 5, 8, 9, 12 from Janma Rashi → unfavorable.
#
#  Returns a list of dicts — one per transit Moon rashi period.
# ──────────────────────────────────────────────────────────────────

def compute_chandrabalam(
    sunrise_dt: datetime,
    next_sunrise_dt: datetime,
    lang: str = "en",
) -> list[dict]:
    """
    Compute Chandrabalam for each Moon rashi transit during the day.

    Scans from sunrise to next sunrise, detects Moon rashi changes,
    and for each transit rashi, groups all 12 birth rashis into
    favorable and unfavorable.

    Args:
        sunrise_dt: Sunrise datetime (timezone-aware).
        next_sunrise_dt: Next sunrise datetime (timezone-aware).
        lang: Language code for names.

    Returns:
        List of dicts, one per transit Moon rashi, each containing:
          - transit_rashi: name of the transit Moon rashi
          - transit_index: rashi index (0–11)
          - starts_at: ISO datetime string
          - ends_at: ISO datetime string
          - favorable: list of {index, name, position}
          - unfavorable: list of {index, name, position}
    """
    sunrise_jd = datetime_to_jd(sunrise_dt)
    next_sunrise_jd = datetime_to_jd(next_sunrise_dt)
    tz = sunrise_dt.tzinfo

    # Find Moon rashi transitions during the day
    swe.set_sid_mode(AYANAMSHA_LAHIRI)
    flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH | swe.FLG_SPEED

    def _moon_rashi_at(jd):
        result = swe.calc_ut(jd, swe.MOON, flags)
        lon = result[0][0] % 360
        return int(lon / 30) % TOTAL_RASHIS

    # Scan the day in small steps to detect rashi changes
    step_days = 1 / 96  # ~15 minute steps
    transitions = []
    current_rashi = _moon_rashi_at(sunrise_jd)
    transitions.append({
        "index": current_rashi,
        "starts_jd": sunrise_jd,
    })

    jd = sunrise_jd + step_days
    while jd < next_sunrise_jd:
        rashi = _moon_rashi_at(jd)
        if rashi != current_rashi:
            # Binary search for exact transition
            lo, hi = jd - step_days, jd
            for _ in range(30):
                mid = (lo + hi) / 2
                if _moon_rashi_at(mid) == current_rashi:
                    lo = mid
                else:
                    hi = mid
            transition_jd = (lo + hi) / 2
            transitions[-1]["ends_jd"] = transition_jd
            transitions.append({
                "index": rashi,
                "starts_jd": transition_jd,
            })
            current_rashi = rashi
        jd += step_days

    # Close the last period
    transitions[-1]["ends_jd"] = next_sunrise_jd

    # Build results
    results = []
    for tr in transitions:
        transit_idx = tr["index"]
        starts_dt = jd_to_datetime(tr["starts_jd"], tz)
        ends_dt = jd_to_datetime(tr["ends_jd"], tz)

        favorable = []
        unfavorable = []

        for birth_idx in range(TOTAL_RASHIS):
            count = ((transit_idx - birth_idx) % 12) + 1
            is_good = CHANDRABALAM_GOOD[count - 1]
            birth_name = name(RASHI, birth_idx, lang)

            entry_dict = {
                "index": birth_idx,
                "name": birth_name,
                "position": count,
            }

            if is_good:
                favorable.append(entry_dict)
            else:
                unfavorable.append(entry_dict)

        results.append({
            "transit_rashi": name(RASHI, transit_idx, lang),
            "transit_index": transit_idx,
            "starts_at": starts_dt.isoformat() if starts_dt else None,
            "ends_at": ends_dt.isoformat() if ends_dt else None,
            "favorable": favorable,
            "unfavorable": unfavorable,
        })

    return results
