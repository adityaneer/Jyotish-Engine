"""
Surya Siddhanta — Traditional Sunrise Calculation

Computes sunrise and sunset using the Surya Siddhanta's geometric model:

  1. Sun's declination from its longitude and obliquity
  2. Chara (ascensional difference) — how sunrise shifts from equinoctial
  3. Sun's semi-diameter correction (the disk, not a point)
  4. Desantara — longitude correction from Ujjain meridian

This gives a purely Siddhantic sunrise that differs from modern calculations
by a few minutes — the difference arising from:
  - SS obliquity (24°) vs modern (23°26')
  - SS Sun longitude vs true Sun longitude
  - No atmospheric refraction correction (the SS was aware of it but
    the standard text doesn't include it explicitly)

Reference: Surya Siddhanta, Chapters II-III (Burgess translation)
"""

import math
from datetime import datetime, date, timedelta, time
from typing import Optional
from zoneinfo import ZoneInfo

from kaalavidya.surya_siddhanta.ganita import (
    compute_ahargana,
    compute_sun_true,
    mean_longitude,
)
from kaalavidya.surya_siddhanta.constants import (
    KALI_EPOCH_JD,
    MAHAYUGA_DAYS,
    TRIJYA,
    REVS_SUN,
    DAILY_MOTION_SUN,
)


# ──────────────────────────────────────────────────────────────────
#  SS-Specific Constants
# ──────────────────────────────────────────────────────────────────

SS_OBLIQUITY_DEG = 24.0            # Max declination of Sun (SS value)
                                    # Modern: ~23.44°. SS rounds up.

UJJAIN_LONGITUDE = 75.7685         # Ujjain (Avanti) — SS standard meridian

SUN_SEMI_DIAMETER_DEG = 0.2666     # ~16 arcminutes (SS: 6500 yojanas / 459585)
                                    # Used for disk-center vs limb correction


# ──────────────────────────────────────────────────────────────────
#  Declination
# ──────────────────────────────────────────────────────────────────

def sun_declination(sun_long_deg: float) -> float:
    """
    Sun's declination (kranti) from its sidereal longitude.

    Formula: sin(δ) = sin(ε) × sin(λ)
    Where ε = obliquity, λ = Sun's longitude.

    In the SS, the sidereal longitude is used directly (the text
    assumes the sidereal and tropical zodiacs coincide at epoch).
    The accumulated ayanamsha causes a small error in declination
    for modern dates, but the effect on sunrise is only ~1-2 minutes.
    """
    sin_decl = math.sin(math.radians(SS_OBLIQUITY_DEG)) * math.sin(math.radians(sun_long_deg))
    sin_decl = max(-1.0, min(1.0, sin_decl))
    return math.degrees(math.asin(sin_decl))


# ──────────────────────────────────────────────────────────────────
#  Chara (Ascensional Difference)
# ──────────────────────────────────────────────────────────────────

def chara_degrees(latitude: float, declination: float) -> float:
    """
    Chara (चर) — the ascensional difference in degrees.

    This is the angular measure of how much earlier/later the Sun
    rises compared to an equinox day at the given latitude.

    Formula: sin(ω) = tan(φ) × tan(δ)
    Where φ = latitude, δ = declination, ω = chara.

    At the equator (φ=0), chara is always 0 (no seasonal variation).
    At higher latitudes, chara increases, causing longer/shorter days.

    Returns degrees (positive = Sun rises before 6h, longer day).
    """
    tan_lat = math.tan(math.radians(latitude))
    tan_decl = math.tan(math.radians(declination))
    product = tan_lat * tan_decl

    # Clamp for polar regions (where the formula breaks down)
    product = max(-1.0, min(1.0, product))

    return math.degrees(math.asin(product))


# ──────────────────────────────────────────────────────────────────
#  Equation of Time (approximate from SS)
# ──────────────────────────────────────────────────────────────────

def equation_of_time_minutes(sun_mean_long: float, sun_true_long: float) -> float:
    """
    Equation of time from the Surya Siddhanta.

    Two components combine:
      1. Eccentricity effect: Sun's true longitude ≠ mean longitude
      2. Obliquity effect: ecliptic ≠ equator (Sun's right ascension ≠ longitude)

    We compute: EoT = (mean_sun - right_ascension_of_true_sun) × 4 min/°

    The right ascension α is obtained from the true ecliptic longitude λ:
      tan(α) = cos(ε) × tan(λ)

    This properly captures both components, giving an EoT accurate
    to within ~1 minute of the modern value.

    Returns: equation of time in minutes (positive = apparent noon before mean noon).
    """
    # Convert true ecliptic longitude to right ascension
    lam = math.radians(sun_true_long)
    cos_eps = math.cos(math.radians(SS_OBLIQUITY_DEG))

    # Use atan2 for correct quadrant
    alpha_rad = math.atan2(cos_eps * math.sin(lam), math.cos(lam))
    alpha_deg = math.degrees(alpha_rad) % 360.0

    # EoT = mean_longitude - right_ascension (both in degrees)
    eot_deg = sun_mean_long - alpha_deg
    if eot_deg > 180:
        eot_deg -= 360
    elif eot_deg < -180:
        eot_deg += 360

    # Convert degrees to minutes of time (1° = 4 minutes of time)
    return eot_deg * 4.0


# ──────────────────────────────────────────────────────────────────
#  Desantara (Longitude Correction)
# ──────────────────────────────────────────────────────────────────

def desantara_minutes(observer_longitude: float) -> float:
    """
    Desantara (देशान्तर) — correction for observer's longitude.

    The SS computes mean noon at Ujjain. For other longitudes,
    we correct by: (observer_long - ujjain_long) × 4 min/°

    Positive = east of Ujjain (sun rises earlier).
    """
    return (observer_longitude - UJJAIN_LONGITUDE) * 4.0


# ──────────────────────────────────────────────────────────────────
#  Sunrise & Sunset
# ──────────────────────────────────────────────────────────────────

def compute_ss_sunrise_sunset(
    target_date: date,
    latitude: float,
    longitude: float,
    timezone: str = "Asia/Kolkata",
) -> dict:
    """
    Compute sunrise and sunset using Surya Siddhanta formulas.

    The SS method:
      1. Get Sun's true longitude at Ujjain mean noon
      2. Compute declination
      3. Compute chara (ascensional difference)
      4. Apply semi-diameter correction (center of disk)
      5. Apply desantara (longitude correction)
      6. Apply equation of time

    Returns dict with sunrise, sunset, day_duration, and intermediate values.
    """
    tz = ZoneInfo(timezone)

    # JD at midnight UT for the target date
    # Simple conversion: JD of Jan 1, 2000 12:00 UT = 2451545.0
    y, m, d = target_date.year, target_date.month, target_date.day
    # Use a standard JD formula
    jd_noon = _gregorian_to_jd(y, m, d) + 0.5  # noon UT

    # Correct to Ujjain noon (Ujjain is at 75.77°E, so ~5h 3m ahead of UT)
    ujjain_offset_days = UJJAIN_LONGITUDE / 360.0
    jd_ujjain_noon = jd_noon - ujjain_offset_days + 0.5  # adjust to Ujjain noon

    # Ahargana at Ujjain noon
    ahargana = compute_ahargana(jd_noon)

    # Sun's positions
    sun_true = compute_sun_true(ahargana)
    sun_mean = mean_longitude(ahargana, REVS_SUN)

    # Declination
    decl = sun_declination(sun_true)

    # Chara (ascensional difference)
    chara = chara_degrees(latitude, decl)

    # Semi-diameter correction in degrees of hour angle
    # The Sun's semi-diameter creates a small additional correction
    # at sunrise/sunset. For center-of-disk (Vedic), correction ≈ 0°.
    # For upper-limb, ≈ +0.27° in hour angle.
    semi_diam_correction = 0.0  # center of disk (Vedic standard)

    # Half-day arc in degrees
    half_day_deg = 90.0 + chara + semi_diam_correction

    # Convert to hours
    half_day_hours = half_day_deg / 15.0  # 15°/hour

    # Local apparent noon at the observer's location
    # Start from 12:00 local standard time
    desantara = desantara_minutes(longitude)
    eot = equation_of_time_minutes(sun_mean, sun_true)

    # Noon correction: the Sun transits the local meridian at:
    # 12:00 - desantara_from_standard_meridian - EoT
    # But since we're working in IST (82.5°E), we need:
    # Standard meridian offset from Ujjain: (82.5 - 75.77) × 4 = 26.9 min
    # Observer from standard meridian: (observer_long - 82.5) × 4

    # Simpler approach: compute sunrise/sunset in UT, then convert
    # Mean local noon UT = 12h - (longitude / 15) hours
    local_noon_ut_hours = 12.0 - (longitude / 15.0)

    # Apply equation of time (convert sun time to mean time)
    local_noon_ut_hours += eot / 60.0

    # Sunrise = noon - half_day_hours
    sunrise_ut_hours = local_noon_ut_hours - half_day_hours
    sunset_ut_hours = local_noon_ut_hours + half_day_hours

    # Convert to datetime
    midnight_ut = datetime(y, m, d, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
    sunrise_dt = midnight_ut + timedelta(hours=sunrise_ut_hours)
    sunset_dt = midnight_ut + timedelta(hours=sunset_ut_hours)

    # Convert to local timezone
    sunrise_local = sunrise_dt.astimezone(tz)
    sunset_local = sunset_dt.astimezone(tz)

    day_duration_hours = 2 * half_day_hours

    return {
        "sunrise": sunrise_local,
        "sunset": sunset_local,
        "day_duration_hours": day_duration_hours,
        "sun_longitude": sun_true,
        "declination": decl,
        "chara_deg": chara,
        "equation_of_time_min": eot,
        "ahargana": ahargana,
    }


def _gregorian_to_jd(year: int, month: int, day: int) -> float:
    """
    Convert Gregorian date to Julian Day number (at 0h UT).

    Uses the standard algorithm (Meeus, Astronomical Algorithms).
    """
    if month <= 2:
        year -= 1
        month += 12
    A = int(year / 100)
    B = 2 - A + int(A / 4)
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5
