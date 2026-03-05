"""
Surya Siddhanta — Full Panchanga Computation

Produces a complete DailyPanchanga using Surya Siddhanta longitudes
and SS-derived sunrise/sunset. Feature-identical to the Drik engine
except for features that require Swiss Ephemeris:

  - Lagna: Not computed (requires swe.houses_ex for ascendant)
  - Maudhya: Not computed (requires swe for Jupiter/Venus positions)
  - Eclipses: Not computed (requires swe for precise lunar nodes)

All Panchanga elements (Tithi, Nakshatra, Yoga, Karana, Rashi, Masa,
Hora, Durmuhurta, Varjyam, Amrit Kalam, etc.) are computed using
SS longitudes via the chandra.py provider mechanism. Transition times,
adhipatis, and all rich details are included — exactly like the Drik
output.

The key mechanism:
  chandra.py's moon_longitude() and sun_longitude() are switchable.
  Inside use_ss_longitudes(), they route to SS ganita functions instead
  of Swiss Ephemeris. All downstream functions (compute_tithi, etc.)
  automatically use whichever provider is active.
"""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from kaalavidya.models import DailyPanchanga, SunTimes, EraYear, MasaInfo, TimePeriod
from kaalavidya.constants import (
    name, VARA, MASA, PAKSHA,
    samvatsara_name, compute_era_years, purnimanta_masa_index,
    RITU, AYANA, LUNAR_RITU_MAP, solar_ritu_index, ayana_index,
    GRAHA, VARA_GRAHA_LORD,
    KALI_YUGA_EPOCH_JD,
    compute_disha_shoola, compute_agnivasa, compute_shivavasa,
)
from kaalavidya.chandra import (
    datetime_to_jd,
    sun_longitude,
    compute_tithi,
    compute_nakshatra,
    compute_yoga,
    compute_karana,
    compute_moon_rashi,
    compute_sun_rashi,
    compute_masa,
    compute_tarabalam,
    compute_chandrabalam,
    use_ss_longitudes,
)
from kaalavidya.surya import (
    compute_rahu_kala,
    compute_yamagandam,
    compute_gulika_kala,
    compute_brahma_muhurta,
    compute_abhijit_muhurta,
    compute_hora_table,
    compute_durmuhurta,
    compute_dina_muhurtas,
    compute_ratri_muhurtas,
    compute_moonrise_moonset,
    compute_varjyam,
    compute_amrit_kalam,
)
from kaalavidya.surya_siddhanta.sunrise import compute_ss_sunrise_sunset
from kaalavidya.sankalpa import generate_sankalpa


def compute_full_ss_panchanga(
    target_date: date,
    latitude: float,
    longitude: float,
    timezone: str = "Asia/Kolkata",
    city: str = "",
    state: str = "",
    lang: str = "en",
    show_ghati: bool = False,
) -> DailyPanchanga:
    """
    Compute a full Panchanga using Surya Siddhanta longitudes and sunrise.

    This mirrors the Drik computation in panchanga.py but uses SS formulas
    for all longitude-dependent calculations (Tithi, Nakshatra, Yoga,
    Karana, Rashi, Masa, etc.).

    Features NOT available in SS mode are left empty:
      - Lagna table (requires swe.houses_ex)
      - Maudhya / combustion (requires swe for planet positions)
      - Eclipses (requires swe for precise lunar node data)

    Args:
        target_date: The date to compute.
        latitude: Observer's latitude (°N).
        longitude: Observer's longitude (°E).
        timezone: IANA timezone string.
        city: City name for display.
        lang: Language code (en, sa, hi, te, ta, kn, ml).
        show_ghati: If True, show ghati-vighati alongside clock time.

    Returns:
        DailyPanchanga with computation_method="Surya Siddhanta".
    """
    tz = ZoneInfo(timezone)

    # ── Step 1: SS Sunrise/Sunset ──
    # SS computes sunrise from its own Sun longitude, declination, and
    # equation of time. This is the traditional Siddhantic sunrise.
    ss_sun = compute_ss_sunrise_sunset(target_date, latitude, longitude, timezone)
    sunrise = ss_sun["sunrise"]
    sunset = ss_sun["sunset"]

    # Next day's SS sunrise (Hindu day boundary = sunrise → next sunrise)
    next_day = target_date + timedelta(days=1)
    ss_sun_next = compute_ss_sunrise_sunset(next_day, latitude, longitude, timezone)
    next_sunrise = ss_sun_next["sunrise"]

    # Previous day's SS sunset (needed for Brahma Muhurta)
    prev_day = target_date - timedelta(days=1)
    ss_sun_prev = compute_ss_sunrise_sunset(prev_day, latitude, longitude, timezone)
    prev_sunset = ss_sun_prev["sunset"]

    # Build SunTimes object
    # SS doesn't distinguish Vedic/Drik — its sunrise IS center-of-disk,
    # which is the Vedic standard. We set apparent = same (no upper-limb
    # computation in SS). Dawn/dusk approximated from sunrise ± 48 min.
    day_duration = (sunset - sunrise).total_seconds() / 3600
    sun_times = SunTimes(
        sunrise=sunrise,
        sunset=sunset,
        sunrise_apparent=sunrise,      # SS = center of disk (no Drik distinction)
        sunset_apparent=sunset,
        dawn=sunrise - timedelta(minutes=48),    # approximate civil twilight
        dusk=sunset + timedelta(minutes=48),
        day_duration_hrs=round(day_duration, 2),
    )

    # ── Step 2: All remaining computations use SS longitudes ──
    # The context manager swaps chandra.py's internal longitude functions
    # to route through Surya Siddhanta instead of Swiss Ephemeris.
    with use_ss_longitudes():
        # ── Step 3: Vara + graha lord (weekday-based, engine-independent) ──
        weekday = target_date.weekday()
        vara_str = name(VARA, weekday, lang)
        graha_lord_idx = VARA_GRAHA_LORD[weekday]
        vara_lord_str = name(GRAHA, graha_lord_idx, lang)

        # ── Step 4: Pancha Anga ──
        # All transition detection uses SS longitudes now
        tithi_entries = compute_tithi(sunrise, next_sunrise, lang)
        nakshatra_entries, nak_start_jds = compute_nakshatra(sunrise, next_sunrise, lang)
        yoga_entries = compute_yoga(sunrise, next_sunrise, lang)
        karana_entries = compute_karana(sunrise, next_sunrise, lang)

        # ── Step 5: Rashi at sunrise ──
        sunrise_jd = datetime_to_jd(sunrise)
        moon_rashi = compute_moon_rashi(sunrise_jd, lang)
        sun_rashi = compute_sun_rashi(sunrise_jd, lang)

        # ── Step 6: Paksha, Masa, Samvatsara ──
        tithi_at_sunrise = tithi_entries[0].index if tithi_entries else 0
        paksha_idx = tithi_at_sunrise // 15
        paksha_str = name(PAKSHA, paksha_idx, lang)

        # Amanta masa (uses SS longitudes for Amavasya/Sankranti detection)
        amanta_masa = compute_masa(sunrise_jd, lang)

        # Purnimanta masa
        purnimanta_idx = purnimanta_masa_index(amanta_masa.index, paksha_idx)
        purnimanta_masa = MasaInfo(
            index=purnimanta_idx,
            name=name(MASA, purnimanta_idx, lang),
            is_adhika=amanta_masa.is_adhika,
        )

        # Samvatsara: Hindu year starts at Ugadi (Chaitra Shukla Pratipada).
        # Before Ugadi, the samvatsara belongs to the previous year.
        ugadi_year = target_date.year
        if target_date.month <= 3 and amanta_masa.index >= 9:
            ugadi_year -= 1
        samvatsara_str = samvatsara_name(ugadi_year, lang)

        # ── Step 7: Ritu & Ayana ──
        sun_long = sun_longitude(sunrise_jd)

        ritu_solar_idx = solar_ritu_index(sun_long)
        ritu_solar_str = name(RITU, ritu_solar_idx, lang)

        ritu_lunar_idx = LUNAR_RITU_MAP[amanta_masa.index]
        ritu_lunar_str = name(RITU, ritu_lunar_idx, lang)

        ayana_idx = ayana_index(sun_long)
        ayana_str = name(AYANA, ayana_idx, lang)

    # ── Step 8: Era years (date-based, not longitude-dependent) ──
    era_raw = compute_era_years(target_date.year, lang)
    era_years = [EraYear(label=e["label"], year=e["year"], epoch=e["epoch"])
                 for e in era_raw]

    # ── Step 9: Hora table (based on sunrise/sunset/weekday — engine-independent) ──
    hora_table = compute_hora_table(sunrise, sunset, next_sunrise, weekday, lang)

    # ── Step 10: Inauspicious periods ──
    rahu_kala = compute_rahu_kala(sunrise, sunset, weekday)
    yamagandam = compute_yamagandam(sunrise, sunset, weekday)
    gulika_kala = compute_gulika_kala(sunrise, sunset, weekday)
    durmuhurta = compute_durmuhurta(sunrise, sunset, weekday)

    # Varjyam & Amrit Kalam: based on nakshatra start times from SS
    varjyam_periods = []
    amrit_kalam_periods = []
    for nak_idx, nak_start_jd in nak_start_jds:
        varjyam_periods.extend(
            compute_varjyam(nak_idx, nak_start_jd, sunrise, next_sunrise, tz)
        )
        amrit_kalam_periods.extend(
            compute_amrit_kalam(nak_idx, nak_start_jd, sunrise, next_sunrise, tz)
        )

    # ── Step 11: Auspicious periods ──
    brahma_muhurta = compute_brahma_muhurta(sunrise, prev_sunset)
    abhijit_muhurta = compute_abhijit_muhurta(sunrise, sunset)

    # ── Step 12: Dina Vibhaga (day muhurtas) ──
    dina_muhurtas = compute_dina_muhurtas(sunrise, sunset, weekday, lang)

    # ── Step 13: Ratri Vibhaga (night muhurtas) ──
    ratri_muhurtas = compute_ratri_muhurtas(sunset, next_sunrise, lang)

    # ── Step 14: Moonrise & Moonset (uses Swiss Eph internally, engine-independent) ──
    moonrise, moonset, moonrise_app, moonset_app = compute_moonrise_moonset(
        target_date, latitude, longitude, timezone,
    )

    # ── Step 15: Tarabalam & Chandrabalam ──
    tarabalam = compute_tarabalam(nakshatra_entries, lang)
    chandrabalam = compute_chandrabalam(sunrise, next_sunrise, lang)

    # ── Step 16: Vijaya Muhurta (11th day muhurta) ──
    day_dur_s = (sunset - sunrise).total_seconds()
    muhurta_dur = timedelta(seconds=day_dur_s / 15)
    vijaya_start = sunrise + 10 * muhurta_dur
    vijaya_end = vijaya_start + muhurta_dur
    vijaya_muhurta = TimePeriod(name="Vijaya", starts_at=vijaya_start, ends_at=vijaya_end)

    # ── Step 17: Godhuli Muhurta ──
    godhuli_start = sunset - timedelta(minutes=24)
    godhuli_end = sunset + timedelta(minutes=24)
    godhuli_muhurta = TimePeriod(name="Godhuli", starts_at=godhuli_start, ends_at=godhuli_end)

    # ── Step 18: Dinamana, Ratrimana, Madhyahna ──
    night_dur_s = (next_sunrise - sunset).total_seconds()
    h, rem = divmod(int(day_dur_s), 3600)
    m, s = divmod(rem, 60)
    dinamana_str = f"{h:02d} Hours {m:02d} Mins {s:02d} Secs"
    h2, rem2 = divmod(int(night_dur_s), 3600)
    m2, s2 = divmod(rem2, 60)
    ratrimana_str = f"{h2:02d} Hours {m2:02d} Mins {s2:02d} Secs"
    madhyahna = sunrise + timedelta(seconds=day_dur_s / 2)

    # ── Step 19: Kali Ahargana ──
    kali_ahargana = int(sunrise_jd - KALI_YUGA_EPOCH_JD)

    # ── Step 20: Disha Shoola, Agnivasa, Shivavasa ──
    disha_shoola = compute_disha_shoola(weekday, lang)
    agnivasa = compute_agnivasa(tithi_at_sunrise, weekday, lang)
    shivavasa = compute_shivavasa(tithi_at_sunrise, lang)

    # ── Step 21: Sankalpa (Indian locations only) ──
    tithi_at_sunrise_idx = tithi_entries[0].index if tithi_entries else 0
    nak_at_sunrise_idx = nakshatra_entries[0].index if nakshatra_entries else 0
    yoga_at_sunrise_idx = yoga_entries[0].index if yoga_entries else 0
    sankalpa_text = generate_sankalpa(
        weekday=weekday,
        tithi_index=tithi_at_sunrise_idx,
        nakshatra_index=nak_at_sunrise_idx,
        yoga_index=yoga_at_sunrise_idx,
        masa_index=amanta_masa.index,
        paksha_index=paksha_idx,
        samvatsara_year=ugadi_year,
        ritu_index=ritu_solar_idx,
        ayana_idx=ayana_idx,
        city=city,
        state=state,
        lat=latitude,
        lon=longitude,
        lang=lang,
    )

    # ── Build result ──
    # Lagna, Maudhya, Eclipses, and Sunrise Chart are NOT available in SS
    # mode — they require Swiss Ephemeris which is outside the scope of
    # pure Surya Siddhanta calculations.
    return DailyPanchanga(
        date=target_date,
        city=city,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        lang=lang,
        computation_method="Surya Siddhanta",
        sun=sun_times,
        moonrise=moonrise,
        moonset=moonset,
        moonrise_apparent=moonrise_app,
        moonset_apparent=moonset_app,
        vara=vara_str,
        vara_lord=vara_lord_str,
        tithi=tithi_entries,
        nakshatra=nakshatra_entries,
        yoga=yoga_entries,
        karana=karana_entries,
        moon_rashi=moon_rashi,
        sun_rashi=sun_rashi,
        masa=amanta_masa,
        masa_purnimanta=purnimanta_masa,
        paksha=paksha_str,
        samvatsara=samvatsara_str,
        ritu_solar=ritu_solar_str,
        ritu_lunar=ritu_lunar_str,
        ayana=ayana_str,
        era_years=era_years,
        lagna_table=[],          # Not available in SS mode
        hora_table=hora_table,
        rahu_kala=rahu_kala,
        yamagandam=yamagandam,
        gulika_kala=gulika_kala,
        durmuhurta=durmuhurta,
        varjyam=varjyam_periods,
        brahma_muhurta=brahma_muhurta,
        abhijit_muhurta=abhijit_muhurta,
        amrit_kalam=amrit_kalam_periods,
        dina_muhurtas=dina_muhurtas,
        ratri_muhurtas=ratri_muhurtas,
        vijaya_muhurta=vijaya_muhurta,
        godhuli_muhurta=godhuli_muhurta,
        tarabalam=tarabalam,
        chandrabalam=chandrabalam,
        dinamana=dinamana_str,
        ratrimana=ratrimana_str,
        madhyahna=madhyahna,
        kali_ahargana=kali_ahargana,
        disha_shoola=disha_shoola,
        agnivasa=agnivasa,
        shivavasa=shivavasa,
        maudhya=[],              # Not available in SS mode
        eclipses=[],             # Not available in SS mode
        sankalpa=sankalpa_text,
        show_ghati=show_ghati,
    )
