"""
Surya Siddhanta — Constants & Parameters

All numerical parameters from the Surya Siddhanta text.
Reference: E. Burgess translation (1860), with cross-references
to modern commentaries by K.S. Shukla and K.V. Sarma.

Key concepts:
  - Mahayuga: 4,320,000 sidereal years. The fundamental time cycle.
  - Bhagana: revolution count of a body in one Mahayuga.
  - Trijya: 3438 arcminutes = radius of the standard circle (≈ 21600/2π).
  - Mandochcha: the apogee (farthest point) of a body's orbit.
  - Mandaparidhi: circumference of the manda (equation of center) epicycle.
"""


# ──────────────────────────────────────────────────────────────────
#  Epoch
# ──────────────────────────────────────────────────────────────────

# Kali Yuga epoch: mean midnight at Lanka (Ujjain meridian, 0° latitude)
# February 17/18, 3102 BCE (Julian calendar)
# At this moment, all mean planets were at 0° sidereal Aries.
KALI_EPOCH_JD = 588465.5


# ──────────────────────────────────────────────────────────────────
#  Mahayuga Parameters
# ──────────────────────────────────────────────────────────────────

MAHAYUGA_YEARS = 4_320_000          # sidereal years in one Mahayuga
MAHAYUGA_DAYS = 1_577_917_828       # civil days in one Mahayuga

# Sidereal year length (derived)
SIDEREAL_YEAR_DAYS = MAHAYUGA_DAYS / MAHAYUGA_YEARS   # ≈ 365.258756 days


# ──────────────────────────────────────────────────────────────────
#  Revolution Numbers (Bhagana) in one Mahayuga
#
#  These encode the mean angular velocity of each body.
#  daily_motion = bhagana × 360° / mahayuga_days
# ──────────────────────────────────────────────────────────────────

# Luminaries
REVS_SUN = 4_320_000               # Sun's revolutions (= Mahayuga years)
REVS_MOON = 57_753_336             # Moon's sidereal revolutions

# Apsides and nodes
REVS_SUN_APOGEE = 387              # Ravi Mandochcha (very slow)
REVS_MOON_APOGEE = 488_219         # Chandra Mandochcha
REVS_MOON_NODE = 232_226           # Rahu (Moon's ascending node, retrograde)

# Planets (for future Jyotish extension)
REVS_MARS = 2_296_824
REVS_MERCURY_SIGHROCCHA = 17_937_020   # Mercury's shighra (synodic) apogee
REVS_JUPITER = 364_220
REVS_VENUS_SIGHROCCHA = 7_022_388      # Venus's shighra apogee
REVS_SATURN = 146_564


# ──────────────────────────────────────────────────────────────────
#  Trijya (Standard Radius)
#
#  The SS uses a circle of circumference 21600 arcminutes (= 360°).
#  Radius = 21600 / (2π) ≈ 3438 arcminutes.
#  All trigonometric calculations use this as the base radius.
# ──────────────────────────────────────────────────────────────────

TRIJYA = 3438


# ──────────────────────────────────────────────────────────────────
#  Manda Epicycle (Mandaparidhi) — degrees of circumference
#
#  The SS gives two values per body:
#    - at uccha (apogee)
#    - at end of odd quadrant (90° from apogee)
#  The actual epicycle is interpolated between them.
#  For Sun and Moon, both values are effectively equal.
# ──────────────────────────────────────────────────────────────────

# (at_uccha, at_quadrant_end)
MANDA_EPICYCLE = {
    "sun":     (14.0, 14.0),      # ~2°14' max equation
    "moon":    (32.0, 32.0),      # ~5°5' max equation
    "mars":    (75.0, 72.0),
    "mercury": (30.0, 28.0),
    "jupiter": (33.0, 32.0),
    "venus":   (12.0, 11.0),
    "saturn":  (49.0, 48.0),
}


# ──────────────────────────────────────────────────────────────────
#  Sun's Apogee (Mandochcha) at Kali Epoch
#
#  The Sun's apogee moves extremely slowly (387 revolutions per
#  Mahayuga ≈ 0.032°/year). At Kali epoch, it was at ~77°17'.
#  This is derived from the Kalpa-level calculation in the SS.
# ──────────────────────────────────────────────────────────────────

SUN_APOGEE_AT_EPOCH = 77.2944      # 77°17'40" (Burgess)


# ──────────────────────────────────────────────────────────────────
#  Ayanamsha — SS Precession Model
#
#  The SS uses a TREPIDATION model: the equinox oscillates ±27°
#  with a period. This differs from the modern continuously
#  increasing precession (~50.3"/year).
#
#  For comparison with Lahiri ayanamsha, we note the difference
#  but compute SS positions in the SS's own sidereal frame.
# ──────────────────────────────────────────────────────────────────

SS_AYANAMSHA_AMPLITUDE = 27.0       # degrees (maximum displacement)
SS_AYANAMSHA_PERIOD_YEARS = 7200    # years for one complete oscillation


# ──────────────────────────────────────────────────────────────────
#  Derived Daily Motions (for reference / debugging)
#
#  These are computed from revolution numbers. Listed here for
#  easy comparison with known values.
#
#  Sun:  0.985602... °/day  (modern: 0.985609°)
#  Moon: 13.17635... °/day  (modern: 13.17636°)
# ──────────────────────────────────────────────────────────────────

DAILY_MOTION_SUN = REVS_SUN * 360.0 / MAHAYUGA_DAYS
DAILY_MOTION_MOON = REVS_MOON * 360.0 / MAHAYUGA_DAYS
DAILY_MOTION_MOON_APOGEE = REVS_MOON_APOGEE * 360.0 / MAHAYUGA_DAYS
DAILY_MOTION_SUN_APOGEE = REVS_SUN_APOGEE * 360.0 / MAHAYUGA_DAYS
