"""
Kaalavidya — Sankalpa Generator

Generates the desha-kala (place-time) portion of the Hindu sankalpa
(ritualistic declaration of time and place) based on panchanga data
and location.

The sankalpa text is always in Sanskrit, with the script (lipi) varying
by language selection. Telugu state (AP/TS) style desha-kala format.

Only available for Indian locations.
"""

from typing import Optional

from kaalavidya.constants import (
    name, VARA, TITHI, NAKSHATRA, YOGA, MASA, PAKSHA, RITU, AYANA,
    samvatsara_name,
)


# ──────────────────────────────────────────────────────────────────
#  India Location Check
# ──────────────────────────────────────────────────────────────────

def is_indian_location(lat: float, lon: float) -> bool:
    """Check if coordinates fall within India's approximate bounds."""
    return 6.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0


# ──────────────────────────────────────────────────────────────────
#  Devanagari → Other Indic Script Transliteration
#
#  Uses Unicode block offset mapping. All major Indic scripts
#  (Telugu, Kannada, Malayalam) are laid out in the same order in
#  Unicode, offset from Devanagari by a fixed amount.
#
#  Tamil lacks many Sanskrit consonants; for sacred Sanskrit texts
#  like sankalpa, Devanagari is preserved (standard practice in
#  Tamil panchangas for mantra text).
# ──────────────────────────────────────────────────────────────────

_SCRIPT_OFFSETS = {
    "te": 0x0C00 - 0x0900,  # Telugu
    "kn": 0x0C80 - 0x0900,  # Kannada
    "ml": 0x0D00 - 0x0900,  # Malayalam
}


def transliterate(text: str, lang: str) -> str:
    """
    Transliterate Devanagari text to the target language's script.

    - sa, hi, en: kept as Devanagari (Sanskrit/Hindi are Devanagari;
      English users reading sankalpa can read Devanagari)
    - ta: kept as Devanagari (Tamil lacks Sanskrit consonants)
    - te, kn, ml: Unicode offset transliteration
    """
    if lang in ("sa", "hi", "en", "ta"):
        return text

    offset = _SCRIPT_OFFSETS.get(lang)
    if not offset:
        return text

    result = []
    for ch in text:
        cp = ord(ch)
        # Devanagari block: U+0900 – U+097F
        if 0x0900 <= cp <= 0x097F:
            result.append(chr(cp + offset))
        else:
            result.append(ch)
    return "".join(result)


# ──────────────────────────────────────────────────────────────────
#  State → Sanskrit Desha Name Mapping
# ──────────────────────────────────────────────────────────────────

DESHA_MAP = {
    "Andhra Pradesh": "आन्ध्रदेशे",
    "Telangana": "तेलङ्गाणदेशे",
    "Karnataka": "कर्णाटकदेशे",
    "Tamil Nadu": "द्रविडदेशे",
    "Kerala": "केरलदेशे",
    "Maharashtra": "महाराष्ट्रदेशे",
    "Gujarat": "गुर्जरदेशे",
    "Rajasthan": "राजस्थानदेशे",
    "Uttar Pradesh": "कोसलदेशे",
    "Madhya Pradesh": "मालवदेशे",
    "Bihar": "मगधदेशे",
    "West Bengal": "गौडदेशे",
    "Odisha": "कलिङ्गदेशे",
    "Punjab": "पञ्चनददेशे",
    "Haryana": "कुरुक्षेत्रदेशे",
    "Delhi": "इन्द्रप्रस्थनगरे",
    "Assam": "प्राग्ज्योतिषदेशे",
    "Goa": "गोमान्तकदेशे",
    "Chhattisgarh": "दक्षिणकोसलदेशे",
    "Jharkhand": "वनाञ्चलदेशे",
    "Uttarakhand": "उत्तराखण्डदेशे",
    "Himachal Pradesh": "हिमाचलदेशे",
    "Jammu and Kashmir": "काश्मीरदेशे",
}


# ──────────────────────────────────────────────────────────────────
#  State → River-pair (X-Y-नद्योर्मध्यदेशे format)
#
#  Traditional sankalpa uses "between two rivers" format:
#    "[River1][River2]नद्योर्मध्यदेशे"
#  meaning "in the middle land between rivers [1] and [2]".
#  This is the standard practice (e.g. Telugu states:
#  "कृष्णागोदावरीनद्योर्मध्यदेशे").
# ──────────────────────────────────────────────────────────────────

NADI_MAP = {
    "Andhra Pradesh": "कृष्णागोदावरीनद्योर्मध्यदेशे",
    "Telangana": "गोदावरीकृष्णानद्योर्मध्यदेशे",
    "Karnataka": "कृष्णाकावेरीनद्योर्मध्यदेशे",
    "Tamil Nadu": "कावेरीताम्रपर्णीनद्योर्मध्यदेशे",
    "Kerala": "पेरियार्पम्पानद्योर्मध्यदेशे",
    "Maharashtra": "गोदावरीकृष्णानद्योर्मध्यदेशे",
    "Gujarat": "नर्मदासरस्वतीनद्योर्मध्यदेशे",
    "Uttar Pradesh": "गङ्गायमुनानद्योर्मध्यदेशे",
    "Madhya Pradesh": "नर्मदाताप्तीनद्योर्मध्यदेशे",
    "Bihar": "गङ्गागण्डकीनद्योर्मध्यदेशे",
    "West Bengal": "गङ्गाभागीरथीनद्योर्मध्यदेशे",
    "Odisha": "महानदीगोदावरीनद्योर्मध्यदेशे",
    "Punjab": "सतलजव्यासनद्योर्मध्यदेशे",
    "Haryana": "गङ्गायमुनानद्योर्मध्यदेशे",
    "Delhi": "गङ्गायमुनानद्योर्मध्यदेशे",
    "Rajasthan": "चम्बलसरस्वतीनद्योर्मध्यदेशे",
    "Uttarakhand": "गङ्गायमुनानद्योर्मध्यदेशे",
    "Assam": "ब्रह्मपुत्रालोहित्यनद्योर्मध्यदेशे",
    "Goa": "मण्डवीजुवारीनद्योर्मध्यदेशे",
    "Chhattisgarh": "महानदीशिवनाथनद्योर्मध्यदेशे",
    "Jharkhand": "गङ्गादामोदरनद्योर्मध्यदेशे",
    "Himachal Pradesh": "सतलजव्यासनद्योर्मध्यदेशे",
    "Jammu and Kashmir": "वितस्ताचन्द्रभागानद्योर्मध्यदेशे",
}


# ──────────────────────────────────────────────────────────────────
#  Tithi — Saptami Vibhakti (Locative Case) Forms
#  Used in sankalpa as: "... षष्ठ्यां तिथौ ..."
# ──────────────────────────────────────────────────────────────────

TITHI_SAPTAMI = [
    "प्रतिपदायां",       # Pratipada
    "द्वितीयायां",       # Dvitiya
    "तृतीयायां",         # Tritiya
    "चतुर्थ्यां",       # Chaturthi
    "पञ्चम्यां",         # Panchami
    "षष्ठ्यां",         # Shashthi
    "सप्तम्यां",         # Saptami
    "अष्टम्यां",         # Ashtami
    "नवम्यां",           # Navami
    "दशम्यां",           # Dashami
    "एकादश्यां",         # Ekadashi
    "द्वादश्यां",       # Dvadashi
    "त्रयोदश्यां",     # Trayodashi
    "चतुर्दश्यां",     # Chaturdashi
    "पौर्णमास्यां",     # Purnima (Shukla 15th)
]

AMAVASYA_SAPTAMI = "अमावास्यायां"  # Krishna 15th


# ──────────────────────────────────────────────────────────────────
#  Vara — Sankalpa Forms
#  The vara in sankalpa uses graha-based names with suffix "वासरे"
# ──────────────────────────────────────────────────────────────────

# Python weekday: 0=Mon, 1=Tue, ..., 6=Sun
VARA_SANKALPA = [
    "सौम्य",      # Monday (Soma/Chandra)
    "भौम",        # Tuesday (Mangala/Bhauma)
    "सौम्य",      # Wednesday — actually "बौध" but let me fix
    "गुरु",       # Thursday
    "भार्गव",     # Friday (Shukra/Bhargava)
    "स्थिर",      # Saturday (Shani/Sthira)
    "भानु",       # Sunday (Ravi/Bhanu)
]

# Actually, the standard sankalpa vara names:
VARA_SANKALPA = [
    "सोम",        # Monday
    "भौम",        # Tuesday
    "सौम्य",      # Wednesday
    "गुरु",       # Thursday
    "भृगु",       # Friday
    "स्थिर",      # Saturday
    "भानु",       # Sunday
]


# ──────────────────────────────────────────────────────────────────
#  Main Sankalpa Generator
# ──────────────────────────────────────────────────────────────────

def generate_sankalpa(
    weekday: int,           # Python weekday: 0=Mon, 1=Tue, ..., 6=Sun
    tithi_index: int,       # 0–29 (0=Shukla Pratipada, 29=Krishna Amavasya)
    nakshatra_index: int,   # 0–26
    yoga_index: int,        # 0–26
    masa_index: int,        # 0–11 (Chaitra=0)
    paksha_index: int,      # 0=Shukla, 1=Krishna
    samvatsara_year: int,   # Gregorian year (adjusted for Ugadi)
    ritu_index: int,        # 0–5
    ayana_idx: int,         # 0=Uttarayana, 1=Dakshinayana
    city: str,
    state: str,
    lat: float,
    lon: float,
    lang: str = "sa",
) -> Optional[str]:
    """
    Generate the desha-kala portion of the sankalpa.

    Returns the sankalpa text in the specified language's script,
    or None if the location is not in India.

    The sankalpa follows the Telugu state (AP/TS) style desha-kala
    sankirtana format, covering the cosmic → geographic → temporal
    context required for nitya krutyas (daily rituals).
    """
    if not is_indian_location(lat, lon):
        return None

    # ── All names in Sanskrit (Devanagari) ──
    samvatsara_sa = samvatsara_name(samvatsara_year, "sa")
    ayana_sa = name(AYANA, ayana_idx, "sa")
    ritu_sa = name(RITU, ritu_index, "sa")
    masa_sa = name(MASA, masa_index, "sa")
    paksha_sa = name(PAKSHA, paksha_index, "sa")
    nakshatra_sa = name(NAKSHATRA, nakshatra_index, "sa")
    yoga_sa = name(YOGA, yoga_index, "sa")

    # Vara (sankalpa-specific names)
    vara_sa = VARA_SANKALPA[weekday]

    # Tithi in saptami vibhakti (locative case)
    tithi_base = tithi_index % 15  # 0–14
    if tithi_index == 29:  # Krishna Amavasya
        tithi_loc = AMAVASYA_SAPTAMI
    else:
        tithi_loc = TITHI_SAPTAMI[tithi_base]

    # ── Location (Desha) parts ──
    desha = DESHA_MAP.get(state, "भारतदेशे")
    # NOTE: Nadi (river-pair) mapping requires GIS-based proximity to actual
    # river courses, not just state-level lookup. E.g. Vijayawada → "कृष्णागोदावरी"
    # but Rajahmundry → "गङ्गागोदावरी". Disabled until proper implementation.
    # nadi = NADI_MAP.get(state, "पुण्यनदीनद्योर्मध्यदेशे")

    # ── Build sankalpa text in Devanagari ──
    # Cosmic context (fixed — same for all panchangas in Kali Yuga)
    lines = [
        "ॐ",
        "श्रीमद्भगवतो महापुरुषस्य विष्णोराज्ञया प्रवर्तमानस्य",
        "आद्यब्रह्मणः द्वितीयपरार्धे श्वेतवाराहकल्पे",
        "वैवस्वतमन्वन्तरे अष्टाविंशतितमे कलियुगे",
        "प्रथमपादे जम्बूद्वीपे भरतवर्षे भरतखण्डे",
        # Geographic context (desha-kala)
        f"मेरोः दक्षिणदिग्भागे {desha}",
        # Nadi line disabled — needs GIS-based river proximity (future)
        # f"{nadi}",
        # Temporal context (kala)
        f"{samvatsara_sa}नाम संवत्सरे {ayana_sa}े {ritu_sa}ऋतौ",
        f"{masa_sa}मासे {paksha_sa}पक्षे {tithi_loc} शुभतिथौ",
        f"{vara_sa}वासरे {nakshatra_sa}नक्षत्रे {yoga_sa}योगे शुभकरणे",
        "एवं गुणविशेषणविशिष्टायां शुभतिथौ",
        # Purpose placeholder (user fills in their specific karma)
        "... श्रीमान् [गोत्रः] [नाम] ... नित्यकर्म करिष्ये ।",
    ]

    sankalpa_deva = "\n".join(lines)

    # ── Transliterate to target script ──
    return transliterate(sankalpa_deva, lang)
