"""
Surya Siddhanta (सूर्यसिद्धान्त) — Traditional Indian Astronomical Engine

An alternative calculation backend for Kaalavidya that uses the
classical formulas from the Surya Siddhanta (~400 CE) instead of
modern Swiss Ephemeris (NASA JPL DE431).

The SS is one of the oldest surviving Indian astronomical texts.
It provides mean positions from revolution numbers and corrects
them using epicyclic geometry (manda samskara).

Usage:
    from kaalavidya.surya_siddhanta import compute_full_ss_panchanga
    from datetime import date

    result = compute_full_ss_panchanga(
        date(1998, 12, 3), latitude=16.5062, longitude=80.648,
    )
    print(result.summary())

Note: SS positions will differ from Drik (modern) values by a few
arcminutes to 1-2° depending on the body and date. This is expected —
the SS was formulated ~1600 years ago with the observational precision
of that era.
"""

from kaalavidya.surya_siddhanta.ganita import (
    compute_ahargana,
    compute_sun_true,
    compute_moon_true,
    compute_tithi_ss,
    compute_nakshatra_ss,
    compute_yoga_ss,
    compute_karana_ss,
)
from kaalavidya.surya_siddhanta.panchanga_ss import compute_full_ss_panchanga
from kaalavidya.surya_siddhanta.sunrise import compute_ss_sunrise_sunset

__all__ = [
    "compute_ahargana",
    "compute_sun_true",
    "compute_moon_true",
    "compute_tithi_ss",
    "compute_nakshatra_ss",
    "compute_yoga_ss",
    "compute_karana_ss",
    "compute_full_ss_panchanga",
    "compute_ss_sunrise_sunset",
]
