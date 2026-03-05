"""
Surya Siddhanta — Ganita (गणित) — Core Astronomical Computations

Implements the fundamental astronomical calculations from the text:

  1. Ahargana (अहर्गण) — civil day count from Kali Yuga epoch
  2. Madhyama Graha (मध्यम ग्रह) — mean longitudes from revolution numbers
  3. Manda Samskara (मन्द संस्कार) — equation of center (epicyclic correction)
  4. Sphuta Graha (स्फुट ग्रह) — true (corrected) longitudes

The manda samskara corrects for the eccentricity of the orbit.
The SS models this using an epicycle: the planet moves uniformly
on a small circle (epicycle) whose center moves uniformly on a
large circle (deferent). The angular correction is derived from
the geometry of this two-circle system.

Note: The SS only applies manda samskara for Sun and Moon in the
basic Panchanga context. For planets, an additional shighra samskara
(synodic correction) is needed — that's a future extension.
"""

import math
from typing import Optional

from kaalavidya.surya_siddhanta.constants import (
    KALI_EPOCH_JD,
    MAHAYUGA_DAYS,
    TRIJYA,
    REVS_SUN,
    REVS_MOON,
    REVS_SUN_APOGEE,
    REVS_MOON_APOGEE,
    REVS_MOON_NODE,
    MANDA_EPICYCLE,
    SUN_APOGEE_AT_EPOCH,
)


# ──────────────────────────────────────────────────────────────────
#  Ahargana — Day Count from Epoch
# ──────────────────────────────────────────────────────────────────

def compute_ahargana(jd: float) -> float:
    """
    Ahargana (अहर्गण) — elapsed civil days from Kali Yuga epoch.

    The Kali Yuga began at mean midnight at Lanka (Ujjain meridian)
    on February 17/18, 3102 BCE. At this moment, all mean planets
    were at 0° sidereal Aries per the SS model.

    Args:
        jd: Julian Day number (UT)

    Returns:
        Fractional day count from Kali epoch.
    """
    return jd - KALI_EPOCH_JD


# ──────────────────────────────────────────────────────────────────
#  Mean Longitudes (Madhyama Graha)
# ──────────────────────────────────────────────────────────────────

def mean_longitude(ahargana: float, revolutions: int) -> float:
    """
    Mean sidereal longitude from revolution numbers.

    In one Mahayuga (4,320,000 years = 1,577,917,828 days), each body
    completes a known number of sidereal revolutions. The mean daily
    motion is: revolutions × 360° / mahayuga_days.

    At Kali epoch, all mean longitudes = 0° (by definition).
    So: mean_longitude = ahargana × daily_motion (mod 360°).
    """
    return (ahargana * revolutions * 360.0 / MAHAYUGA_DAYS) % 360.0


def mean_sun(ahargana: float) -> float:
    """Mean sidereal longitude of the Sun."""
    return mean_longitude(ahargana, REVS_SUN)


def mean_moon(ahargana: float) -> float:
    """Mean sidereal longitude of the Moon."""
    return mean_longitude(ahargana, REVS_MOON)


def sun_apogee(ahargana: float) -> float:
    """
    Longitude of the Sun's apogee (Ravi Mandochcha).

    The Sun's apogee moves very slowly: 387 revolutions per Mahayuga
    ≈ 0.032°/year. At Kali epoch, it was at 77°17'40" (Burgess).
    """
    motion = mean_longitude(ahargana, REVS_SUN_APOGEE)
    return (SUN_APOGEE_AT_EPOCH + motion) % 360.0


def moon_apogee(ahargana: float) -> float:
    """
    Longitude of the Moon's apogee (Chandra Mandochcha).

    The Moon's apogee completes 488,219 revolutions per Mahayuga
    ≈ one revolution every 8.85 years ≈ 0.111°/day.
    At Kali epoch, it starts at 0° (as per the all-at-0° convention).
    """
    return mean_longitude(ahargana, REVS_MOON_APOGEE)


def moon_node(ahargana: float) -> float:
    """
    Longitude of Rahu (Moon's ascending node).

    Rahu moves retrograde: 232,226 revolutions per Mahayuga.
    We subtract from 360° to get the retrograde position.
    """
    direct = mean_longitude(ahargana, REVS_MOON_NODE)
    return (360.0 - direct) % 360.0


# ──────────────────────────────────────────────────────────────────
#  Manda Samskara (Equation of Center)
#
#  The SS corrects mean positions using epicyclic geometry:
#
#    Planet P rides on a small circle (epicycle) of radius r,
#    centered on point M that moves on the deferent (radius R).
#
#    M = mean position on the deferent
#    P = planet's actual position on the epicycle
#    C = center of the deferent (Earth)
#
#    The angle MCP (planet as seen from C vs. mean position) is
#    the manda equation (mandaphala). It corrects for the fact
#    that the orbit is not circular but elliptical.
#
#    Geometrically:
#      bhuja = r × sin(kendra)           [perpendicular component]
#      koti  = r × cos(kendra)           [along the apse line]
#      karna = sqrt((R + koti)² + bhuja²) [true distance]
#      sin(equation) = bhuja / karna
#
#    Where kendra = mean_longitude - apogee (the anomaly).
# ──────────────────────────────────────────────────────────────────

def _interpolate_epicycle(epicycle_pair: tuple, kendra_deg: float) -> float:
    """
    Interpolate the manda epicycle circumference.

    The SS gives two values: at uccha (apogee) and at quadrant end.
    The actual value varies with the anomaly (kendra):

      epicycle = (val_uccha + val_quad)/2
                 + (val_uccha - val_quad)/2 × |cos(2 × kendra)|

    For Sun and Moon, both values are equal, so this returns a constant.
    For planets, it produces a smooth variation.
    """
    val_uccha, val_quad = epicycle_pair
    if val_uccha == val_quad:
        return val_uccha
    avg = (val_uccha + val_quad) / 2.0
    diff = (val_uccha - val_quad) / 2.0
    return avg + diff * abs(math.cos(math.radians(2 * kendra_deg)))


def _manda_equation(
    mean_long: float,
    apogee_long: float,
    epicycle_pair: tuple,
) -> float:
    """
    Compute the manda equation (mandaphala) for one iteration.

    The equation of center tells how far the true position deviates
    from the mean position due to orbital eccentricity.

    Returns the equation in degrees (signed: positive when mean > true).
    """
    kendra = mean_long - apogee_long
    kendra_rad = math.radians(kendra)

    epicycle = _interpolate_epicycle(epicycle_pair, kendra)
    epi_radius = (epicycle / 360.0) * TRIJYA

    bhuja = epi_radius * math.sin(kendra_rad)
    koti = epi_radius * math.cos(kendra_rad)

    karna = math.sqrt((TRIJYA + koti) ** 2 + bhuja ** 2)

    if karna == 0:
        return 0.0

    sin_eq = bhuja / karna
    sin_eq = max(-1.0, min(1.0, sin_eq))  # float safety

    return math.degrees(math.asin(sin_eq))


def true_longitude(
    mean_long: float,
    apogee_long: float,
    epicycle_pair: tuple,
) -> float:
    """
    True longitude after manda samskara.

    Uses the SS two-step iterative method:
      1. Compute equation from raw anomaly
      2. Half-correct the mean longitude
      3. Recompute equation from corrected anomaly
      4. true = mean - second_equation

    The half-correction improves accuracy, especially for the Moon
    where the epicycle is larger.
    """
    # First iteration: raw anomaly
    eq1 = _manda_equation(mean_long, apogee_long, epicycle_pair)

    # Half-correction
    corrected = mean_long - eq1 / 2.0

    # Second iteration: refined anomaly
    eq2 = _manda_equation(corrected, apogee_long, epicycle_pair)

    return (mean_long - eq2) % 360.0


# ──────────────────────────────────────────────────────────────────
#  True Longitudes of Sun and Moon
# ──────────────────────────────────────────────────────────────────

def compute_sun_true(ahargana: float) -> float:
    """
    True sidereal longitude of the Sun per Surya Siddhanta.

    Steps:
      1. Mean Sun from revolution number
      2. Sun's apogee position
      3. Manda samskara (equation of center)

    Sun's max equation ≈ 2°14' (modern: ~1°55').
    The difference is because the SS was calibrated ~1600 years ago.
    """
    m_sun = mean_sun(ahargana)
    m_apogee = sun_apogee(ahargana)
    return true_longitude(m_sun, m_apogee, MANDA_EPICYCLE["sun"])


def compute_moon_true(ahargana: float) -> float:
    """
    True sidereal longitude of the Moon per Surya Siddhanta.

    Steps:
      1. Mean Moon from revolution number
      2. Moon's apogee position
      3. Manda samskara (equation of center)

    Moon's max equation ≈ 5°5' (modern: ~6°17').
    The SS Moon lacks evection and other perturbation corrections
    that modern theory includes, so it will be less accurate than
    the Sun (especially around elongation extremes).
    """
    m_moon = mean_moon(ahargana)
    m_apogee = moon_apogee(ahargana)
    return true_longitude(m_moon, m_apogee, MANDA_EPICYCLE["moon"])


# ──────────────────────────────────────────────────────────────────
#  Panchanga Elements from SS Longitudes
#
#  These use the SAME formulas as Drik (from chandra.py) — the only
#  difference is the source of Sun/Moon longitudes.
# ──────────────────────────────────────────────────────────────────

def compute_tithi_ss(sun_long: float, moon_long: float) -> tuple:
    """
    Tithi from SS longitudes.

    Tithi = elongation of Moon from Sun, divided into 12° segments.
    There are 30 tithis in one synodic month.

    Returns (tithi_index, remaining_degrees_in_current_tithi).
    """
    elongation = (moon_long - sun_long) % 360.0
    tithi_idx = int(elongation / 12.0) % 30
    remaining = elongation % 12.0
    return tithi_idx, remaining


def compute_nakshatra_ss(moon_long: float) -> tuple:
    """
    Nakshatra from SS Moon longitude.

    The ecliptic is divided into 27 equal segments of 13°20' each.
    Each segment is a nakshatra, further divided into 4 padas.

    Returns (nakshatra_index, pada, degrees_within_nakshatra).
    """
    nak_span = 360.0 / 27.0  # 13°20'
    nak_idx = int(moon_long / nak_span) % 27
    within_nak = moon_long % nak_span
    pada = min(int(within_nak / (nak_span / 4.0)) + 1, 4)
    return nak_idx, pada, within_nak


def compute_yoga_ss(sun_long: float, moon_long: float) -> int:
    """
    Yoga from SS longitudes.

    Yoga = (Sun + Moon) mod 360°, divided into 27 segments of 13°20'.
    There are 27 yogas, from Vishkambha to Vaidhriti.

    Returns yoga_index.
    """
    total = (sun_long + moon_long) % 360.0
    return int(total / (360.0 / 27.0)) % 27


def compute_karana_ss(sun_long: float, moon_long: float) -> int:
    """
    Karana from SS longitudes.

    Karana = half-tithi. There are 60 karanas in a synodic month.
    The first karana of Shukla Pratipada is always Kimstughna.

    Returns karana_index (0-59, mapped to the 11 karana names).
    """
    elongation = (moon_long - sun_long) % 360.0
    return int(elongation / 6.0) % 60


# ──────────────────────────────────────────────────────────────────
#  Diagnostic / Comparison Helpers
# ──────────────────────────────────────────────────────────────────

def compute_all_mean(ahargana: float) -> dict:
    """
    All mean longitudes at a given ahargana (for debugging).

    Returns a dict with mean positions of Sun, Moon, and their apsides.
    """
    return {
        "mean_sun": mean_sun(ahargana),
        "mean_moon": mean_moon(ahargana),
        "sun_apogee": sun_apogee(ahargana),
        "moon_apogee": moon_apogee(ahargana),
        "moon_node_rahu": moon_node(ahargana),
    }


def compute_all_true(ahargana: float) -> dict:
    """
    All true longitudes at a given ahargana (for debugging).

    Returns a dict with true positions and the applied equations.
    """
    m_sun = mean_sun(ahargana)
    m_moon = mean_moon(ahargana)
    t_sun = compute_sun_true(ahargana)
    t_moon = compute_moon_true(ahargana)

    return {
        "mean_sun": m_sun,
        "true_sun": t_sun,
        "sun_equation": m_sun - t_sun if (m_sun - t_sun) < 180 else m_sun - t_sun - 360,
        "mean_moon": m_moon,
        "true_moon": t_moon,
        "moon_equation": m_moon - t_moon if (m_moon - t_moon) < 180 else m_moon - t_moon - 360,
    }
