"""
Kaalavidya — Panchanga (Main Entry Point)

The Panchanga class ties together all calculation modules and produces
a complete daily panchanga for any date and location.

Supports two computation methods:
  - "drik"      : Modern astronomical positions (Swiss Ephemeris / NASA JPL DE431)
  - "siddhantic": Traditional positions from Surya Siddhanta (~400 CE)

Usage:
    from kaalavidya import Panchanga

    # Drik (default)
    p = Panchanga(year=2025, month=2, day=17, latitude=16.5062, longitude=80.648)
    print(p.compute().summary())

    # Siddhantic comparison
    p = Panchanga(year=1998, month=12, day=3, ..., method="both")
    result = p.compute()
    print(result.summary())             # Drik output
    print(result.ss_panchanga.summary()) # SS comparison

All calculations use Vedic sunrise (center of Sun's disk at horizon)
as the primary day boundary — the traditional Indian standard.
"""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from kaalavidya.models import DailyPanchanga, EraYear, MasaInfo
from kaalavidya.constants import (
    name, VARA, VARA_GRAHA, MASA, PAKSHA,
    samvatsara_name, compute_era_years, purnimanta_masa_index,
    RITU, AYANA, LUNAR_RITU_MAP, solar_ritu_index, ayana_index,
    GRAHA, VARA_GRAHA_LORD,
    KALI_YUGA_EPOCH_JD,
    compute_disha_shoola, compute_agnivasa, compute_shivavasa,
)
from kaalavidya.surya import (
    compute_sun_times,
    compute_next_sunrise,
    compute_prev_sunset,
    compute_moonrise_moonset,
    compute_rahu_kala,
    compute_yamagandam,
    compute_gulika_kala,
    compute_brahma_muhurta,
    compute_abhijit_muhurta,
    compute_hora_table,
    compute_durmuhurta,
    compute_dina_muhurtas,
    compute_ratri_muhurtas,
    compute_varjyam,
    compute_amrit_kalam,
)
from kaalavidya.chandra import (
    datetime_to_jd,
    sun_longitude,
    moon_longitude,
    compute_tithi,
    compute_nakshatra,
    compute_yoga,
    compute_karana,
    compute_moon_rashi,
    compute_sun_rashi,
    compute_masa,
    compute_maudhya,
    compute_tarabalam,
    compute_chandrabalam,
)
from kaalavidya.lagna import compute_lagna_table
from kaalavidya.chart import compute_sunrise_chart
from kaalavidya.grahana import check_eclipses_on_day
from kaalavidya.surya_siddhanta.panchanga_ss import compute_full_ss_panchanga
from kaalavidya.sankalpa import generate_sankalpa


def _fmt_duration(total_seconds: float) -> str:
    """Format a duration in seconds as 'H Hours MM Mins SS Secs'."""
    h = int(total_seconds // 3600)
    m = int((total_seconds % 3600) // 60)
    s = int(total_seconds % 60)
    return f"{h:02d} Hours {m:02d} Mins {s:02d} Secs"


class Panchanga:
    """
    Daily Panchanga calculator.
    Create one per date+location, then call compute() to get all details.

    Args:
        method: "drik" (default, modern), "siddhantic" (SS only), or
                "both" (Drik primary + SS comparison attached).
    """

    def __init__(
        self,
        year: int,
        month: int,
        day: int,
        latitude: float,
        longitude: float,
        timezone: str = "Asia/Kolkata",
        city: str = "",
        state: str = "",
        lang: str = "en",
        show_ghati: bool = False,
        method: str = "drik",
    ):
        self.target_date = date(year, month, day)
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.city = city
        self.state = state
        self.lang = lang
        self.show_ghati = show_ghati
        self.method = method  # "drik", "siddhantic", "both"

    def compute(self) -> DailyPanchanga:
        """
        Compute the full panchanga.

        If method="siddhantic", returns a full DailyPanchanga computed
        entirely from Surya Siddhanta formulas (no Swiss Ephemeris).

        If method="both", computes both Drik and SS panchangas, with
        the Drik as primary and SS attached for comparison.

        Steps (Drik mode):
          1. Vedic sunrise/sunset (via Swiss Ephemeris)
          2. Next sunrise (for Hindu day boundary)
          3. Vara + adhipati
          4. Pancha Anga (tithi, nakshatra, yoga, karana)
          5. Moon/Sun rashi at sunrise
          6. Paksha, Masa (Amanta + Purnimanta), Samvatsara
          7. Ritu (Solar + Lunar), Ayana
          8. Era years
          9. Lagna table
         10. Hora table
         11. Inauspicious periods (Rahu, Yama, Gulika, Durmuhurta, Varjyam)
         12. Auspicious periods
         13. Maudhya (Guru/Shukra combustion)
         14. Eclipse check
         15. SS comparison (if method="both")
        """
        # ── Short-circuit: pure Siddhantic mode ──
        if self.method == "siddhantic":
            return compute_full_ss_panchanga(
                self.target_date, self.latitude, self.longitude,
                self.timezone, self.city, self.state, self.lang, self.show_ghati,
            )

        tz = ZoneInfo(self.timezone)

        # ── Step 1: Sun times ──
        sun_today = compute_sun_times(
            self.target_date, self.latitude, self.longitude,
            self.timezone, self.city,
        )
        sunrise = sun_today.sunrise
        sunset = sun_today.sunset

        # ── Step 2: Next sunrise (Hindu day = sunrise → next sunrise) ──
        next_sunrise = compute_next_sunrise(
            self.target_date, self.latitude, self.longitude, self.timezone,
        )

        # ── Step 3: Vara + graha lord ──
        weekday = self.target_date.weekday()
        vara_str = name(VARA, weekday, self.lang)
        graha_lord_idx = VARA_GRAHA_LORD[weekday]
        vara_lord_str = name(GRAHA, graha_lord_idx, self.lang)

        # ── Step 4: Pancha Anga ──
        tithi_entries = compute_tithi(sunrise, next_sunrise, self.lang)
        nakshatra_entries, nak_start_jds = compute_nakshatra(sunrise, next_sunrise, self.lang)
        yoga_entries = compute_yoga(sunrise, next_sunrise, self.lang)
        karana_entries = compute_karana(sunrise, next_sunrise, self.lang)

        # ── Step 5: Rashi at sunrise ──
        sunrise_jd = datetime_to_jd(sunrise)
        moon_rashi = compute_moon_rashi(sunrise_jd, self.lang)
        sun_rashi = compute_sun_rashi(sunrise_jd, self.lang)

        # ── Step 6: Paksha, Masa, Samvatsara ──
        tithi_at_sunrise = tithi_entries[0].index if tithi_entries else 0
        paksha_idx = tithi_at_sunrise // 15
        paksha_str = name(PAKSHA, paksha_idx, self.lang)

        # Amanta masa: proper calculation with Adhika/Kshaya detection.
        # Finds the two bracketing Amavasyas, counts Sankrantis between them.
        amanta_masa = compute_masa(sunrise_jd, self.lang)

        # Purnimanta masa: same during Shukla, +1 during Krishna.
        # Adhika flag carries over.
        purnimanta_idx = purnimanta_masa_index(amanta_masa.index, paksha_idx)
        purnimanta_masa = MasaInfo(
            index=purnimanta_idx,
            name=name(MASA, purnimanta_idx, self.lang),
            is_adhika=amanta_masa.is_adhika,
        )

        # Samvatsara: Hindu year starts at Ugadi (Chaitra Shukla Pratipada,
        # typically March/April). Before Ugadi, the samvatsara belongs to the
        # previous Ugadi's Gregorian year. We use the Amanta masa index:
        # months Pausha (9) through Phalguna (11) in Jan–March → previous year.
        ugadi_year = self.target_date.year
        if self.target_date.month <= 3 and amanta_masa.index >= 9:
            ugadi_year -= 1
        samvatsara_str = samvatsara_name(ugadi_year, self.lang)

        # ── Step 7: Ritu & Ayana ──
        sun_long = sun_longitude(sunrise_jd)

        ritu_solar_idx = solar_ritu_index(sun_long)
        ritu_solar_str = name(RITU, ritu_solar_idx, self.lang)

        ritu_lunar_idx = LUNAR_RITU_MAP[amanta_masa.index]
        ritu_lunar_str = name(RITU, ritu_lunar_idx, self.lang)

        ayana_idx = ayana_index(sun_long)
        ayana_str = name(AYANA, ayana_idx, self.lang)

        # ── Step 8: Era years ──
        era_raw = compute_era_years(self.target_date.year, self.lang)
        era_years = [EraYear(label=e["label"], year=e["year"], epoch=e["epoch"])
                     for e in era_raw]

        # ── Step 8b: Moonrise & Moonset ──
        moonrise, moonset, moonrise_app, moonset_app = compute_moonrise_moonset(
            self.target_date, self.latitude, self.longitude, self.timezone,
        )

        # ── Step 9: Lagna table ──
        lagna_table = compute_lagna_table(
            sunrise, next_sunrise,
            self.latitude, self.longitude, self.lang,
        )

        # ── Step 9b: Sunrise Chart ──
        sunrise_chart = compute_sunrise_chart(
            sunrise, self.latitude, self.longitude, self.lang,
        )

        # ── Step 10: Hora table ──
        hora_table = compute_hora_table(
            sunrise, sunset, next_sunrise, weekday, self.lang,
        )

        # ── Step 11: Inauspicious periods ──
        rahu_kala = compute_rahu_kala(sunrise, sunset, weekday)
        yamagandam = compute_yamagandam(sunrise, sunset, weekday)
        gulika_kala = compute_gulika_kala(sunrise, sunset, weekday)
        durmuhurta = compute_durmuhurta(sunrise, sunset, weekday)

        # Varjyam & Amrit Kalam: compute for each nakshatra active during the day
        varjyam_periods = []
        amrit_kalam_periods = []
        for nak_idx, nak_start_jd in nak_start_jds:
            varjyam_periods.extend(
                compute_varjyam(nak_idx, nak_start_jd, sunrise, next_sunrise, tz)
            )
            amrit_kalam_periods.extend(
                compute_amrit_kalam(nak_idx, nak_start_jd, sunrise, next_sunrise, tz)
            )

        # ── Step 11b: Dina Vibhaga (day muhurtas) ──
        dina_muhurtas = compute_dina_muhurtas(sunrise, sunset, weekday, self.lang)

        # ── Step 11c: Ratri Vibhaga (night muhurtas) ──
        ratri_muhurtas = compute_ratri_muhurtas(sunset, next_sunrise, self.lang)

        # ── Step 12: Auspicious periods ──
        prev_sunset = compute_prev_sunset(
            self.target_date, self.latitude, self.longitude, self.timezone,
        )
        brahma_muhurta = compute_brahma_muhurta(sunrise, prev_sunset)
        abhijit_muhurta = compute_abhijit_muhurta(sunrise, sunset)

        # ── Step 12b: Vijaya Muhurta (11th day muhurta) ──
        day_dur = (sunset - sunrise).total_seconds()
        muhurta_dur = timedelta(seconds=day_dur / 15)
        vijaya_start = sunrise + 10 * muhurta_dur  # 11th muhurta (0-indexed: 10)
        vijaya_end = vijaya_start + muhurta_dur
        from kaalavidya.models import TimePeriod
        vijaya_muhurta = TimePeriod(name="Vijaya", starts_at=vijaya_start, ends_at=vijaya_end)

        # ── Step 12c: Godhuli Muhurta (sunset ± 24 min) ──
        godhuli_start = sunset - timedelta(minutes=24)
        godhuli_end = sunset + timedelta(minutes=24)
        godhuli_muhurta = TimePeriod(name="Godhuli", starts_at=godhuli_start, ends_at=godhuli_end)

        # ── Step 12d: Tarabalam & Chandrabalam ──
        tarabalam = compute_tarabalam(nakshatra_entries, self.lang)
        chandrabalam = compute_chandrabalam(sunrise, next_sunrise, self.lang)

        # ── Step 12e: Dinamana, Ratrimana, Madhyahna ──
        night_dur = (next_sunrise - sunset).total_seconds()
        dinamana_str = _fmt_duration(day_dur)
        ratrimana_str = _fmt_duration(night_dur)
        madhyahna = sunrise + timedelta(seconds=day_dur / 2)

        # ── Step 12f: Kali Ahargana ──
        kali_ahargana = int(sunrise_jd - KALI_YUGA_EPOCH_JD)

        # ── Step 12g: Disha Shoola, Agnivasa, Shivavasa ──
        disha_shoola = compute_disha_shoola(weekday, self.lang)
        agnivasa = compute_agnivasa(tithi_at_sunrise, weekday, self.lang)
        shivavasa = compute_shivavasa(tithi_at_sunrise, self.lang)

        # ── Step 13: Maudhya (Combustion) check ──
        maudhya_entries = compute_maudhya(sunrise_jd, self.target_date, self.lang)

        # ── Step 14: Eclipse check ──
        next_sunrise_jd = datetime_to_jd(next_sunrise)
        eclipses = check_eclipses_on_day(
            sunrise_jd, next_sunrise_jd,
            self.latitude, self.longitude, tz,
        )

        # ── Step 15: Surya Siddhanta comparison (if requested) ──
        ss_result = None
        if self.method == "both":
            ss_result = compute_full_ss_panchanga(
                self.target_date, self.latitude, self.longitude,
                self.timezone, self.city, self.state, self.lang, self.show_ghati,
            )

        # ── Step 16: Sankalpa (Indian locations only) ──
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
            city=self.city,
            state=self.state,
            lat=self.latitude,
            lon=self.longitude,
            lang=self.lang,
            )

        # ── Build result ──
        return DailyPanchanga(
            date=self.target_date,
            city=self.city,
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
            lang=self.lang,
            sun=sun_today,
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
            lagna_table=lagna_table,
            sunrise_chart=sunrise_chart,
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
            maudhya=maudhya_entries,
            eclipses=eclipses,
            disha_shoola=disha_shoola,
            agnivasa=agnivasa,
            shivavasa=shivavasa,
            sankalpa=sankalpa_text,
            show_ghati=self.show_ghati,
            ss_panchanga=ss_result,
        )
