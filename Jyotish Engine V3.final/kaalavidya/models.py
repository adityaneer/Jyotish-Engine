"""
Kaalavidya — Data Models

Clean data structures for Panchanga results.
Every field is meaningful; no clutter.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional


# ── Ghati-Vighati Formatter ──────────────────────────────────────

def to_ghati_vighati(sunrise: datetime, target: datetime) -> str:
    """
    Convert a timestamp to ghati-vighati measured from sunrise.

    Traditional Indian time: 1 day (sunrise → sunrise) = 60 ghatis.
    1 ghati = 60 vighatis.  1 ghati ≈ 24 minutes.
    """
    elapsed_sec = (target - sunrise).total_seconds()
    total_ghatis = elapsed_sec / (24 * 60)  # 24 min per ghati
    ghati = int(total_ghatis)
    vighati = int((total_ghatis - ghati) * 60)
    return f"{ghati}g {vighati:02d}v"


# ── Data Classes ─────────────────────────────────────────────────

@dataclass
class SunTimes:
    """
    Sunrise, sunset, and related times for a location on a given day.

    'sunrise' and 'sunset' are Vedic (center of Sun's disk at horizon).
    'sunrise_apparent' and 'sunset_apparent' are Drik (upper limb visible).
    All calculations throughout use Vedic sunrise as the day boundary.
    """
    sunrise: datetime          # Vedic — primary, used for all calculations
    sunset: datetime           # Vedic
    sunrise_apparent: datetime  # Drik (upper limb)
    sunset_apparent: datetime   # Drik (upper limb)
    dawn: datetime             # civil twilight start
    dusk: datetime             # civil twilight end
    day_duration_hrs: float    # Vedic sunrise to Vedic sunset


@dataclass
class TithiEntry:
    """One tithi active during the day."""
    index: int                 # 0–29
    name: str
    devata: str = ""           # presiding deity
    group: str = ""            # Nanda / Bhadra / Jaya / Rikta / Purna
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active_at_sunrise: bool = False


@dataclass
class NakshatraEntry:
    """One nakshatra active during the day."""
    index: int                 # 0–26
    name: str
    pada: int                  # 1–4
    devata: str = ""           # presiding deity
    graha_lord: str = ""       # Vimsottari dasha lord
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active_at_sunrise: bool = False


@dataclass
class YogaEntry:
    """One yoga active during the day."""
    index: int
    name: str
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active_at_sunrise: bool = False


@dataclass
class KaranaEntry:
    """One karana active during the day."""
    index: int
    name: str
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active_at_sunrise: bool = False


@dataclass
class RashiInfo:
    """Rashi (zodiac sign) of a graha at a given time."""
    index: int
    name: str
    degree: float              # degree within the rashi (0–30)


@dataclass
class LagnaEntry:
    """One lagna (ascendant sign) period during the day."""
    index: int
    name: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: float


@dataclass
class TimePeriod:
    """A named time window."""
    name: str
    starts_at: datetime
    ends_at: datetime


@dataclass
class HoraEntry:
    """One planetary hora (hour) during the day."""
    planet: str
    number: int                # 1–24
    is_day_hora: bool
    starts_at: datetime
    ends_at: datetime


@dataclass
class MuhurtaEntry:
    """One muhurta (1/15th of day or night)."""
    number: int                # 1–15
    name: str                  # muhurta name (Rudra, Ahi, Mitra, ...)
    starts_at: datetime
    ends_at: datetime
    guna: int = 1              # 0=inauspicious, 1=auspicious, 2=very auspicious
    alt_name: str = ""         # pāṭhāntara (variant reading)
    is_durmuhurta: bool = False
    is_abhijit: bool = False
    is_nishita: bool = False   # 8th night muhurta (Vidhātṛ — midnight, Shiva puja)
    is_brahma: bool = False    # 14th night muhurta (Brahma — pre-dawn)
    is_amrit: bool = False     # 11th night muhurta (Jīva/Amṛta)


@dataclass
class EraYear:
    """One calendar era's year."""
    label: str
    year: int
    epoch: str


@dataclass
class MasaInfo:
    """
    Lunar month information with Adhika/Kshaya detection.

    Adhika (intercalary): No Sankranti falls within the lunar month.
    Kshaya (skipped): Two Sankrantis fall within one lunar month.
    Normal: Exactly one Sankranti.
    """
    index: int               # 0–11 (Chaitra=0 ... Phalguna=11)
    name: str                # localized month name
    is_adhika: bool = False  # True if intercalary month
    kshaya_index: Optional[int] = None    # if Kshaya: index of the skipped month
    kshaya_name: Optional[str] = None     # if Kshaya: name of the skipped month

    def display_name(self) -> str:
        """Name with Adhika/Kshaya prefix if applicable."""
        if self.is_adhika:
            return f"Adhika {self.name}"
        return self.name


@dataclass
class MaudhyaInfo:
    """
    Planetary combustion (Maudhya) information.

    When a planet gets too close to the Sun in sidereal longitude,
    it becomes invisible and is considered weak. During Guru Maudhya
    and Shukra Maudhya, auspicious ceremonies (especially vivaha) are
    traditionally avoided.

    Combustion limits (Surya Siddhanta):
      Guru (Jupiter): 11°     Shukra (Venus): 10° (8° retrograde)
    """
    planet: str                # "Guru" / "Shukra" (localized)
    planet_key: str            # "guru" / "shukra" (internal key)
    is_combust: bool           # whether currently combust
    separation_deg: float      # angular separation from Sun
    combustion_limit: float    # threshold used (degrees)
    is_retrograde: bool = False
    period_start: Optional[date] = None   # combustion began
    period_end: Optional[date] = None     # combustion will end


@dataclass
class EclipseInfo:
    """
    Solar or lunar eclipse details for a specific location.

    All times are timezone-aware datetimes in the user's local timezone.
    """
    eclipse_type: str          # "solar" or "lunar"
    subtype: str               # "total", "annular", "partial", "penumbral"
    max_time: datetime         # time of greatest eclipse
    start_time: datetime       # first contact (solar) / penumbral begin (lunar)
    end_time: datetime         # fourth contact (solar) / penumbral end (lunar)
    magnitude: float           # fraction of diameter covered (solar) / umbral magnitude (lunar)
    obscuration: float = 0.0   # fraction of disk covered (solar only)


@dataclass
class DailyPanchanga:
    """
    Complete Panchanga for one day at a specific location.
    All times are based on Vedic sunrise (center of Sun's disk) unless noted.
    """
    # ── Location & Date ──
    date: date
    city: str
    latitude: float
    longitude: float
    timezone: str
    lang: str = "en"

    # ── Sun Times ──
    sun: Optional[SunTimes] = None

    # ── Moon Times ──
    moonrise: Optional[datetime] = None          # Vedic (center of disk)
    moonset: Optional[datetime] = None            # Vedic (center of disk)
    moonrise_apparent: Optional[datetime] = None   # Drik (upper limb)
    moonset_apparent: Optional[datetime] = None    # Drik (upper limb)

    # ── Pancha Anga (Five Limbs) ──
    vara: str = ""
    vara_lord: str = ""                                    # ruling graha
    tithi: list[TithiEntry] = field(default_factory=list)
    nakshatra: list[NakshatraEntry] = field(default_factory=list)
    yoga: list[YogaEntry] = field(default_factory=list)
    karana: list[KaranaEntry] = field(default_factory=list)

    # ── Rashi ──
    moon_rashi: Optional[RashiInfo] = None
    sun_rashi: Optional[RashiInfo] = None

    # ── Calendar ──
    masa: Optional[MasaInfo] = None      # Amanta lunar month (with Adhika/Kshaya)
    masa_purnimanta: Optional[MasaInfo] = None  # Purnimanta equivalent
    paksha: str = ""
    samvatsara: str = ""
    ritu_solar: str = ""        # Drik (solar) season
    ritu_lunar: str = ""        # Vedic (lunar) season
    ayana: str = ""             # Uttarayana / Dakshinayana

    # ── Era Years ──
    era_years: list[EraYear] = field(default_factory=list)

    # ── Lagna & Hora Tables ──
    lagna_table: list[LagnaEntry] = field(default_factory=list)
    hora_table: list[HoraEntry] = field(default_factory=list)

    # ── Inauspicious Periods ──
    rahu_kala: Optional[TimePeriod] = None
    yamagandam: Optional[TimePeriod] = None
    gulika_kala: Optional[TimePeriod] = None
    durmuhurta: list[TimePeriod] = field(default_factory=list)
    varjyam: list[TimePeriod] = field(default_factory=list)

    # ── Auspicious Periods ──
    brahma_muhurta: Optional[TimePeriod] = None
    abhijit_muhurta: Optional[TimePeriod] = None
    amrit_kalam: list[TimePeriod] = field(default_factory=list)

    # ── Dina Vibhaga (Day Muhurtas) ──
    dina_muhurtas: list[MuhurtaEntry] = field(default_factory=list)

    # ── Ratri Vibhaga (Night Muhurtas) ──
    ratri_muhurtas: list[MuhurtaEntry] = field(default_factory=list)

    # ── Auspicious — Vijaya & Godhuli Muhurta ──
    vijaya_muhurta: Optional[TimePeriod] = None
    godhuli_muhurta: Optional[TimePeriod] = None

    # ── Tarabalam & Chandrabalam ──
    tarabalam: list[dict] = field(default_factory=list)
    chandrabalam: list[dict] = field(default_factory=list)

    # ── Dinamana / Ratrimana / Madhyahna ──
    dinamana: str = ""          # Day length in H:MM:SS format
    ratrimana: str = ""         # Night length in H:MM:SS format
    madhyahna: Optional[datetime] = None   # Midday time

    # ── Kali Ahargana ──
    kali_ahargana: int = 0       # Days since Kali Yuga epoch

    # ── Maudhya (Combustion) ──
    maudhya: list[MaudhyaInfo] = field(default_factory=list)

    # ── Eclipses ──
    eclipses: list[EclipseInfo] = field(default_factory=list)

    # ── Sunrise Chart ──
    sunrise_chart: Optional[object] = None  # SunriseChart from chart.py

    # ── Surya Siddhanta Comparison ──
    ss_panchanga: Optional["DailyPanchanga"] = None  # Full SS panchanga if method="both"

    # ── Disha Shoola / Vasa ──
    disha_shoola: Optional[dict] = None     # {"direction": "...", "direction_key": "E/W/N/S"}
    agnivasa: Optional[dict] = None         # {"name": "Prithvi", "guna": "Auspicious", "is_good": True}
    shivavasa: Optional[dict] = None        # {"name": "Kailase", "guna": "Neutral", "guna_value": 0}

    # ── Sankalpa (Desha-Kala) ──
    sankalpa: Optional[str] = None  # Generated sankalpa text (Indian locations only)

    # ── Display Options ──
    show_ghati: bool = False    # if True, show ghati-vighati alongside clock time
    computation_method: str = "Drik Ganita"  # "Drik Ganita" or "Surya Siddhanta"

    def _fmt(self, dt: datetime) -> str:
        """Format time, adding '+1' if next calendar day."""
        time_str = dt.strftime("%I:%M %p")
        if dt.date() > self.date:
            time_str += "+1"
        return time_str

    def _gv(self, dt: datetime) -> str:
        """Format time with optional ghati-vighati."""
        base = self._fmt(dt)
        if self.show_ghati and self.sun:
            base += f" [{to_ghati_vighati(self.sun.sunrise, dt)}]"
        return base

    def summary(self) -> str:
        """Human-readable summary of the day's panchanga."""
        lines = []
        lines.append(f"═══ Panchanga for {self.date.strftime('%B %d, %Y')} ({self.computation_method}) ═══")
        lines.append(f"📍 {self.city} ({self.latitude:.4f}°N, {self.longitude:.4f}°E)")
        lines.append("")

        if self.sun:
            lines.append(f"🌅 Sunrise   : {self._gv(self.sun.sunrise)}  (Vedic*)")
            lines.append(f"🌇 Sunset    : {self._gv(self.sun.sunset)}  (Vedic*)")
            lines.append(f"   Apparent  : {self._fmt(self.sun.sunrise_apparent)} / {self._fmt(self.sun.sunset_apparent)}  (Drik)")
            lines.append(f"   Day length: {self.sun.day_duration_hrs:.1f} hours")
            if self.moonrise:
                lines.append(f"🌙 Moonrise  : {self._gv(self.moonrise)}")
            if self.moonset:
                lines.append(f"🌑 Moonset   : {self._gv(self.moonset)}")
            lines.append("")

        # ── Calendar ──
        lines.append("── Calendar ──")
        vara_line = f"  Vara        : {self.vara}"
        if self.vara_lord:
            vara_line += f"  — Lord: {self.vara_lord}"
        lines.append(vara_line)
        lines.append(f"  Samvatsara  : {self.samvatsara}")
        if self.masa and self.masa_purnimanta:
            amanta_str = self.masa.display_name()
            purnimanta_str = self.masa_purnimanta.display_name()
            lines.append(f"  Masa        : {amanta_str} (Amanta) / {purnimanta_str} (Purnimanta)")
            if self.masa.kshaya_name:
                lines.append(f"                ⚠ Kshaya: {self.masa.kshaya_name} month skipped")
        lines.append(f"  Paksha      : {self.paksha}")
        lines.append(f"  Ritu        : {self.ritu_solar} (Solar) / {self.ritu_lunar} (Lunar)")
        lines.append(f"  Ayana       : {self.ayana}")
        lines.append("")

        # ── Era Years ──
        if self.era_years:
            lines.append("── Era Years ──")
            for e in self.era_years:
                lines.append(f"  {e.label:<42s}: {e.year}")
            lines.append("")

        # ── Tithi ──
        lines.append("── Tithi ──")
        for t in self.tithi:
            line = f"  {t.name}"
            if t.ends_at:
                line += f"  (until {self._gv(t.ends_at)})"
            elif t.starts_at:
                line += f"  (from {self._gv(t.starts_at)})"
            if t.is_active_at_sunrise:
                line += "  ★"
            extras = []
            if t.devata:
                extras.append(f"Devata: {t.devata}")
            if t.group:
                extras.append(f"Group: {t.group}")
            if extras:
                line += f"  [{', '.join(extras)}]"
            lines.append(line)

        # ── Nakshatra ──
        lines.append("── Nakshatra ──")
        for n in self.nakshatra:
            line = f"  {n.name} (Pada {n.pada})"
            if n.ends_at:
                line += f"  (until {self._gv(n.ends_at)})"
            elif n.starts_at:
                line += f"  (from {self._gv(n.starts_at)})"
            if n.is_active_at_sunrise:
                line += "  ★"
            extras = []
            if n.devata:
                extras.append(f"Devata: {n.devata}")
            if n.graha_lord:
                extras.append(f"Lord: {n.graha_lord}")
            if extras:
                line += f"  [{', '.join(extras)}]"
            lines.append(line)

        # ── Yoga ──
        lines.append("── Yoga ──")
        for y in self.yoga:
            line = f"  {y.name}"
            if y.ends_at:
                line += f"  (until {self._gv(y.ends_at)})"
            elif y.starts_at:
                line += f"  (from {self._gv(y.starts_at)})"
            lines.append(line)

        # ── Karana ──
        lines.append("── Karana ──")
        for k in self.karana:
            line = f"  {k.name}"
            if k.ends_at:
                line += f"  (until {self._gv(k.ends_at)})"
            elif k.starts_at:
                line += f"  (from {self._gv(k.starts_at)})"
            lines.append(line)

        # ── Rashi ──
        if self.moon_rashi:
            lines.append("")
            lines.append(f"🌙 Moon Rashi : {self.moon_rashi.name} ({self.moon_rashi.degree:.1f}°)")
        if self.sun_rashi:
            lines.append(f"☀️  Sun Rashi  : {self.sun_rashi.name} ({self.sun_rashi.degree:.1f}°)")

        # ── Maudhya (Combustion) ──
        active_maudhya = [m for m in self.maudhya if m.is_combust]
        if active_maudhya:
            lines.append("")
            lines.append("── ⚠ Maudhya (Combustion) ──")
            for m in active_maudhya:
                retro_tag = " ℞" if m.is_retrograde else ""
                line = f"  {m.planet} Maudhya{retro_tag}  ({m.separation_deg:.1f}° from Sun, limit {m.combustion_limit:.0f}°)"
                if m.period_start and m.period_end:
                    line += f"\n    Period: {m.period_start.strftime('%b %d, %Y')} → {m.period_end.strftime('%b %d, %Y')}"
                lines.append(line)

        # ── Auspicious Periods ──
        lines.append("")
        lines.append("── Auspicious Periods ──")
        if self.brahma_muhurta:
            lines.append(f"  Brahma Muhurta : {self._gv(self.brahma_muhurta.starts_at)} – {self._gv(self.brahma_muhurta.ends_at)}")
        if self.abhijit_muhurta:
            lines.append(f"  Abhijit Muhurta: {self._gv(self.abhijit_muhurta.starts_at)} – {self._gv(self.abhijit_muhurta.ends_at)}")
        for ak in self.amrit_kalam:
            lines.append(f"  Amrit Kalam    : {self._gv(ak.starts_at)} – {self._gv(ak.ends_at)}")

        # ── Inauspicious Periods ──
        lines.append("")
        lines.append("── Inauspicious Periods ──")
        if self.rahu_kala:
            lines.append(f"  Rahu Kala   : {self._gv(self.rahu_kala.starts_at)} – {self._gv(self.rahu_kala.ends_at)}")
        if self.yamagandam:
            lines.append(f"  Yamagandam  : {self._gv(self.yamagandam.starts_at)} – {self._gv(self.yamagandam.ends_at)}")
        if self.gulika_kala:
            lines.append(f"  Gulika Kala : {self._gv(self.gulika_kala.starts_at)} – {self._gv(self.gulika_kala.ends_at)}")
        for dm in self.durmuhurta:
            lines.append(f"  Durmuhurta  : {self._gv(dm.starts_at)} – {self._gv(dm.ends_at)}")
        for vj in self.varjyam:
            lines.append(f"  Varjyam     : {self._gv(vj.starts_at)} – {self._gv(vj.ends_at)}")

        # ── Dina Vibhaga ──
        if self.dina_muhurtas:
            lines.append("")
            lines.append("── Dina Vibhaga (Day Muhurtas) ──")
            for m in self.dina_muhurtas:
                tags = []
                if m.is_abhijit:
                    tags.append("★ Abhijit")
                if m.is_durmuhurta:
                    tags.append("⛔ Dur")
                tag_str = f"  [{', '.join(tags)}]" if tags else ""
                lines.append(
                    f"  {m.number:>2}. {m.name:<14s} {self._gv(m.starts_at)} – {self._gv(m.ends_at)}{tag_str}"
                )

        # ── Lagna ──
        if self.computation_method == "Surya Siddhanta" and not self.lagna_table:
            lines.append("")
            lines.append("── Lagna Table ──")
            lines.append("  (Not available in Surya Siddhanta mode — requires Swiss Ephemeris)")
        elif self.lagna_table:
            lines.append("")
            lines.append("── Lagna Table ──")
            for lg in self.lagna_table:
                lines.append(
                    f"  {lg.name:<12s} {self._gv(lg.starts_at)} – {self._gv(lg.ends_at)}  ({lg.duration_minutes:.0f} min)"
                )

        # ── Hora ──
        if self.hora_table:
            lines.append("")
            lines.append("── Hora Table ──")
            lines.append("  Day Horas (Sunrise → Sunset):")
            for h in self.hora_table:
                if h.is_day_hora:
                    lines.append(f"    {h.number:>2}. {h.planet:<12s} {self._gv(h.starts_at)} – {self._gv(h.ends_at)}")
            lines.append("  Night Horas (Sunset → Sunrise):")
            for h in self.hora_table:
                if not h.is_day_hora:
                    lines.append(f"    {h.number:>2}. {h.planet:<12s} {self._gv(h.starts_at)} – {self._gv(h.ends_at)}")

        # ── Eclipses ──
        if self.eclipses:
            lines.append("")
            lines.append("── 🌑 Grahana (Eclipse) ──")
            for ecl in self.eclipses:
                etype = "Surya Grahana" if ecl.eclipse_type == "solar" else "Chandra Grahana"
                lines.append(f"  {etype} — {ecl.subtype.title()}")
                lines.append(f"    Begins : {self._gv(ecl.start_time)}")
                lines.append(f"    Maximum: {self._gv(ecl.max_time)}")
                lines.append(f"    Ends   : {self._gv(ecl.end_time)}")
                lines.append(f"    Magnitude: {ecl.magnitude:.4f}")
                if ecl.eclipse_type == "solar" and ecl.obscuration > 0:
                    lines.append(f"    Obscuration: {ecl.obscuration * 100:.1f}%")

        # ── Sunrise Lagna Chart ──
        if self.sunrise_chart is not None:
            lines.append("")
            lines.append(self.sunrise_chart.summary())

        # ── Surya Siddhanta Comparison ──
        if self.ss_panchanga is not None:
            lines.append("")
            lines.append("═" * 60)
            lines.append(self.ss_panchanga.summary())

            # Longitude comparison (Drik vs SS)
            if self.sun_rashi and self.ss_panchanga.sun_rashi:
                drik_sun = self.sun_rashi.index * 30 + self.sun_rashi.degree
                ss_sun = self.ss_panchanga.sun_rashi.index * 30 + self.ss_panchanga.sun_rashi.degree
                drik_moon = self.moon_rashi.index * 30 + self.moon_rashi.degree
                ss_moon = self.ss_panchanga.moon_rashi.index * 30 + self.ss_panchanga.moon_rashi.degree
                lines.append("")
                lines.append("── Drik vs Surya Siddhanta (at sunrise) ──")
                lines.append(f"  Sun  Drik: {drik_sun:7.3f}°  SS: {ss_sun:7.3f}°  Δ = {(ss_sun - drik_sun):+.3f}°")
                lines.append(f"  Moon Drik: {drik_moon:7.3f}°  SS: {ss_moon:7.3f}°  Δ = {(ss_moon - drik_moon):+.3f}°")

        # ── Disha Shoola & Vasa ──
        if self.disha_shoola or self.agnivasa or self.shivavasa:
            lines.append("")
            lines.append("── Disha Shoola & Vasa ──")
            if self.disha_shoola:
                lines.append(f"  Disha Shoola : {self.disha_shoola['direction']} ({self.disha_shoola['direction_key']})")
            if self.agnivasa:
                tag = "✓" if self.agnivasa['is_good'] else "✗"
                lines.append(f"  Agnivasa     : {self.agnivasa['name']} — {self.agnivasa['guna']}  {tag}")
            if self.shivavasa:
                lines.append(f"  Shivavasa    : {self.shivavasa['name']} — {self.shivavasa['guna']}")

        # ── Footer ──
        lines.append("")
        lines.append("* Vedic sunrise = center of Sun's disk at horizon")
        if self.ss_panchanga is not None:
            lines.append("† SS = Surya Siddhanta (traditional ~400 CE), Drik = Swiss Ephemeris (modern)")

        return "\n".join(lines)
