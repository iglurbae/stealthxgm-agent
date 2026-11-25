"""Geo data, user agents, browser details, auto identity.

Extracted from fingerprint.py — logic unchanged.
"""
import random

# GLM P4: import relatif dibuat LAZY (di dalam fungsi) supaya file ini bisa
# dibuktikan langsung (python3 fingerprint/geo.py), bukan cuma via -m.
# Tidak ada kode di luar yang impor new_identity/spoof_js dari geo.

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; CrOS x86_64 16836.30.0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; CrOS x86_64 16836.30.0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0",
]

BROWSER_DETAILS = [
    {"platform": "Win32", "oscpu": "Windows NT 10.0; Win64; x64",
     "chrome_ver": "156.0.0.0", "vendor": "Google Inc.",
     "app_ver": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"},
    {"platform": "Win32", "oscpu": "Windows NT 10.0; Win64; x64",
     "chrome_ver": "155.0.0.0", "vendor": "Google Inc.",
     "app_ver": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"},
    # KOREKSI 2026-11-05 (GLM P2): USER_AGENTS punya Chrome/154.0.0.0 tapi
    # BROWSER_DETAILS tidak — self-test menangkapnya. Tambah entri 154.
    {"platform": "Win32", "oscpu": "Windows NT 10.0; Win64; x64",
     "chrome_ver": "154.0.0.0", "vendor": "Google Inc.",
     "app_ver": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"},
    {"platform": "MacIntel", "oscpu": "Intel Mac OS X 10_15_7",
     "chrome_ver": "156.0.0.0", "vendor": "Google Inc.",
     "app_ver": "5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"},
    {"platform": "MacIntel", "oscpu": "Intel Mac OS X 10_15_7",
     "chrome_ver": "155.0.0.0", "vendor": "Google Inc.",
     "app_ver": "5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"},
    {"platform": "Linux x86_64", "oscpu": "Linux x86_64",
     "chrome_ver": "156.0.0.0", "vendor": "Google Inc.",
     "app_ver": "5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"},
    {"platform": "Linux x86_64", "oscpu": "Linux x86_64",
     "chrome_ver": "155.0.0.0", "vendor": "Google Inc.",
     "app_ver": "5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"},
]

SCREEN_DETAILS = [
    {"color_depth": 24, "pixel_depth": 24},
    {"color_depth": 30, "pixel_depth": 30},
    {"color_depth": 24, "pixel_depth": 24},
]



# Country geo data: cc -> (timezone, locale, lat, lon) (29 countries)
# KOREKSI 2026-11-05: komentar lama bilang 28, hitungan nyata 29.
_COUNTRY_GEO = {
    "ae": ("Asia/Dubai", "ar-AE", 25.2, 55.27),
    "au": ("Australia/Sydney", "en-AU", -33.87, 151.21),
    "br": ("America/Sao_Paulo", "pt-BR", -23.55, -46.63),
    "ca": ("America/Toronto", "en-CA", 43.65, -79.38),
    "de": ("Europe/Berlin", "de-DE", 52.52, 13.41),
    "es": ("Europe/Madrid", "es-ES", 40.42, -3.7),
    "fr": ("Europe/Paris", "fr-FR", 48.86, 2.35),
    "gb": ("Europe/London", "en-GB", 51.51, -0.13),
    "hk": ("Asia/Hong_Kong", "zh-HK", 22.32, 114.17),
    "id": ("Asia/Jakarta", "id-ID", -6.21, 106.85),
    "in": ("Asia/Kolkata", "en-IN", 28.61, 77.21),
    "it": ("Europe/Rome", "it-IT", 41.9, 12.5),
    "jp": ("Asia/Tokyo", "ja-JP", 35.68, 139.69),
    "kr": ("Asia/Seoul", "ko-KR", 37.57, 126.98),
    "mx": ("America/Mexico_City", "es-MX", 19.43, -99.13),
    "my": ("Asia/Kuala_Lumpur", "ms-MY", 3.14, 101.69),
    "nl": ("Europe/Amsterdam", "nl-NL", 52.37, 4.9),
    "nz": ("Pacific/Auckland", "en-NZ", -36.85, 174.76),
    "ph": ("Asia/Manila", "en-PH", 14.6, 120.98),
    "pl": ("Europe/Warsaw", "pl-PL", 52.23, 21.01),
    "pt": ("Europe/Lisbon", "pt-PT", 38.72, -9.14),
    "sa": ("Asia/Riyadh", "ar-SA", 24.71, 46.68),
    "se": ("Europe/Stockholm", "sv-SE", 59.33, 18.07),
    "sg": ("Asia/Singapore", "en-SG", 1.35, 103.82),
    "th": ("Asia/Bangkok", "th-TH", 13.76, 100.5),
    "tw": ("Asia/Taipei", "zh-TW", 25.03, 121.57),
    "us": ("America/New_York", "en-US", 40.71, -74.01),
    "vn": ("Asia/Ho_Chi_Minh", "vi-VN", 10.83, 106.65),
    "za": ("Africa/Johannesburg", "en-ZA", -26.2, 28.05),
}



def auto_identity(country="sg"):
    """Generate identitas LENGKAP otomatis dari country code.

    Gil 2026-11-03: "Gw mau semua otomatis"
    Kasih country code (mis. "sg"), dapat:
    - fingerprint (GPU, screen, CPU, browser)
    - timezone, locale, geolocation — SEMUA konsisten!

    Returns: (ident_dict, timezone, locale, lat, lon)
    """
    from .devices import new_identity
    c = (country or "sg").strip().lower()
    tz, loc, lat, lon = _COUNTRY_GEO.get(c, _COUNTRY_GEO["sg"])
    ident = new_identity()
    # Inject geo ke ident untuk geolocation spoof
    ident["geo_lat"] = lat
    ident["geo_lon"] = lon
    ident["geo_country"] = c
    return ident, tz, loc, lat, lon


def auto_spoof_js(country="sg"):
    """Generate spoof JS LENGKAP otomatis — 1 baris, semua konsisten!

    Contoh:
        js = auto_spoof_js("sg")  # Singapore: timezone+locale+geo otomatis
    """
    from ._core import spoof_js
    ident, tz, loc, lat, lon = auto_identity(country)
    return spoof_js(ident, timezone=tz, locale=loc)


# ═══════════════════════════════════════════════════════════════
# MOBILE DEVICE INTEGRATION (Gil 2026-11-03 15:08)
# Copy/adaptasi dari gmail/mobile_fingerprint.py (451 device).
# ATURAN KERAS: mobile dan desktop JANGAN PERNAH campur dalam 1 identity!
# iPhone TIDAK PERNAH pakai Snapdragon (divalidasi check_consistency).
# ═══════════════════════════════════════════════════════════════


if __name__ == "__main__":
    if not __package__:
        # Dijalankan langsung: jalankan ulang sebagai modul paket (GLM P4).
        import os as _os, sys as _sys, runpy as _runpy, warnings as _warnings
        _warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")
        _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        _runpy.run_module("fingerprint.geo", run_name="__main__")
        raise SystemExit(0)
    print("=== TEST geo.py (GLM P4: self-test) ===")
    # 1. _COUNTRY_GEO: 29 negara, format (timezone, locale, lat, lon) valid.
    import re as _re
    assert len(_COUNTRY_GEO) == 29, f"negara: {len(_COUNTRY_GEO)} (harusnya 29)"
    for _cc, (_tz, _loc, _lat, _lon) in _COUNTRY_GEO.items():
        assert "/" in _tz and "-" in _loc, f"geo {_cc} format aneh: {_tz}/{_loc}"
        assert -90 <= _lat <= 90 and -180 <= _lon <= 180, f"geo {_cc} koordinat aneh"
    print(f"  _COUNTRY_GEO: 29 negara, semua format + koordinat valid")
    # 2. Versi Chrome di USER_AGENTS harus ada di BROWSER_DETAILS (konsisten).
    _vers = {b["chrome_ver"] for b in BROWSER_DETAILS}
    _ua_vers = set(_re.findall(r"Chrome/([\d.]+)", " ".join(USER_AGENTS)))
    assert _ua_vers <= _vers, f"UA punya versi Chrome di luar BROWSER_DETAILS: {_ua_vers - _vers}"
    print(f"  USER_AGENTS: {len(USER_AGENTS)} UA, versi Chrome {_ua_vers} "
          f"semua ada di BROWSER_DETAILS")
    # 3. auto_identity: geo konsisten dengan country (tz + lat/lon match).
    for _cc in ("id", "sg", "us", "jp"):
        _ident, _tz, _loc, _lat, _lon = auto_identity(_cc)
        _exp = _COUNTRY_GEO[_cc]
        assert (_tz, _loc, _lat, _lon) == _exp, f"auto_identity({_cc}) geo mismatch"
        assert _ident["geo_lat"] == _lat and _ident["geo_lon"] == _lon, \
            f"auto_identity({_cc}) geo tidak masuk ke ident"
    print("  auto_identity(id/sg/us/jp): timezone+locale+lat/lon konsisten")
    # 4. auto_spoof_js: JS tidak kosong.
    _js = auto_spoof_js("id")
    assert len(_js) > 1000, f"auto_spoof_js terlalu pendek: {len(_js)}"
    print(f"  auto_spoof_js('id'): {len(_js)} karakter JS")
    print("\n✅ geo.py OK")

