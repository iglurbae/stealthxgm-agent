"""Geo-sync: sinkronkan timezone/locale profil dengan negara IP proxy (RND 2026-11-04).

Masalah (FIX 3): IP proxy di negara A tapi timezone profil klaim negara B
-> mismatch instan yang mudah dideteksi (ip-api vs Date/timezone).

Solusi:
  - suggest_geo_for_pool(pool): baca pool.last_check.country -> {timezone, locale, lat, lon}
  - check_geo_mismatch(profile, pool): warning kalau timezone profil != negara IP
  - API: POST /api/profiles/<id>/sync-geo -> auto-set timezone+locale dari pool

Tidak ada credential di file ini. Hanya mapping geo.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    from fingerprint.geo import _COUNTRY_GEO
except ImportError:
    _COUNTRY_GEO = {}

# reverse map: timezone -> country code
_TZ_TO_CC = {tz: cc for cc, (tz, _loc, _lat, _lon) in _COUNTRY_GEO.items()}


def country_code_from_pool(pool):
    """Extract country code dari pool.last_check.country.

    Format last_check.country: "Singapore (SG)" -> "sg".
    Juga dukung pool.country langsung ("SG", "sg", "auto", "-").
    Return lowercase cc atau None.
    """
    if not isinstance(pool, dict):
        return None
    # 1. dari last_check (hasil test_pool via ip-api)
    lc = (pool.get("last_check") or {})
    c = lc.get("country", "")
    m = re.search(r"\(([A-Za-z]{2})\)", c or "")
    if m:
        return m.group(1).lower()
    # 2. dari pool.country langsung
    pc = (pool.get("country") or "").strip().lower()
    if pc and pc not in ("auto", "-", "none", ""):
        # bisa "SG" atau "sg"
        if len(pc) == 2 and pc in _COUNTRY_GEO:
            return pc
    return None


def geo_for_country(cc):
    """Return {timezone, locale, lat, lon, country_code} untuk country code.

    cc: "sg" (lowercase). Return None kalau tidak dikenal.
    """
    if not cc:
        return None
    entry = _COUNTRY_GEO.get(cc.lower())
    if not entry:
        return None
    tz, loc, lat, lon = entry
    return {
        "timezone": tz,
        "locale": loc,
        "lat": lat,
        "lon": lon,
        "country_code": cc.lower(),
    }


def suggest_geo_for_pool(pool):
    """Saran geo lengkap untuk sebuah pool. Return dict atau None.

    None = tidak bisa tentukan (pool belum di-test / negara tidak dikenal).
    """
    cc = country_code_from_pool(pool)
    return geo_for_country(cc)


def check_geo_mismatch(profile, pool):
    """Cek apakah timezone profil mismatch dengan negara IP pool.

    Return None kalau OK / tidak bisa dicek, atau dict warning:
      {"type": "geo_mismatch", "profile_tz": ..., "profile_cc": ...,
       "pool_cc": ..., "suggested_tz": ..., "message": ...}
    """
    if not isinstance(profile, dict) or not isinstance(pool, dict):
        return None
    pool_cc = country_code_from_pool(pool)
    if not pool_cc:
        return None  # pool belum di-test -> tidak bisa cek
    fp = profile.get("fingerprint", {}) or {}
    prof_tz = fp.get("timezone") or "Asia/Jakarta"
    prof_cc = _TZ_TO_CC.get(prof_tz)
    if not prof_cc:
        return None  # timezone custom tidak di DB -> skip
    if prof_cc == pool_cc:
        return None  # konsisten
    suggested = geo_for_country(pool_cc) or {}
    return {
        "type": "geo_mismatch",
        "profile_tz": prof_tz,
        "profile_cc": prof_cc,
        "pool_cc": pool_cc,
        "pool_name": pool.get("name", ""),
        "suggested_tz": suggested.get("timezone"),
        "suggested_locale": suggested.get("locale"),
        "message": (
            f"Timezone profil ({prof_tz}) tidak match negara IP pool "
            f"'{pool.get('name', '')}' ({pool_cc.upper()}). "
            f"Saran: {suggested.get('timezone')} / {suggested.get('locale')}."
        ),
    }


def apply_geo_to_profile_data(profile_data, geo):
    """Terapkan geo suggestion ke dict update profil (untuk pm.update_profile).

    P-08: selain timezone/locale profil, update JUGA identity tersimpan —
    geo_lat/geo_lon + timezone/locale di dalamnya. Launcher memakai nilai
    dari identity bila ada (build_fingerprint_js), jadi tanpa ini geo-sync
    mengubah label timezone tapi geolocation tetap koordinat lama.
    Profil tanpa identity tersimpan tidak perlu apa-apa (launch generate
    baru yang konsisten dari timezone).
    Return {"fingerprint": {"timezone", "locale", "identity"?}}.
    """
    if not geo:
        return {}
    out_fp = {
        "timezone": geo["timezone"],
        "locale": geo["locale"],
    }
    fp = (profile_data or {}).get("fingerprint", {}) or {}
    ident = fp.get("identity")
    if isinstance(ident, dict):
        new_ident = dict(ident)
        new_ident["geo_lat"] = geo["lat"]
        new_ident["geo_lon"] = geo["lon"]
        new_ident["timezone"] = geo["timezone"]
        if geo.get("locale"):
            new_ident["locale"] = geo["locale"]
        out_fp["identity"] = new_ident
    return {"fingerprint": out_fp}


# ── Self-test ────────────────────────────────────────────────────────────
def self_test():
    # pool mock dengan last_check Singapore
    pool_sg = {
        "name": "Test SG",
        "country": "auto",
        "last_check": {"status": "online", "ip": "1.2.3.4",
                       "country": "Singapore (SG)", "latency_ms": 50},
    }
    cc = country_code_from_pool(pool_sg)
    assert cc == "sg", f"cc={cc}"
    geo = suggest_geo_for_pool(pool_sg)
    assert geo["timezone"] == "Asia/Singapore", geo
    assert geo["locale"] == "en-SG", geo

    # mismatch: profil Jakarta + pool SG
    profile = {"fingerprint": {"timezone": "Asia/Jakarta"}}
    w = check_geo_mismatch(profile, pool_sg)
    assert w is not None, "harus warning!"
    assert w["pool_cc"] == "sg" and w["profile_cc"] == "id", w
    assert w["suggested_tz"] == "Asia/Singapore", w

    # match: profil Singapore + pool SG -> no warning
    profile2 = {"fingerprint": {"timezone": "Asia/Singapore"}}
    assert check_geo_mismatch(profile2, pool_sg) is None

    # pool belum di-test -> no warning (tidak bisa cek)
    pool_fresh = {"name": "Fresh", "last_check": None, "country": "auto"}
    assert check_geo_mismatch(profile, pool_fresh) is None

    return {"country_extract": cc, "suggest": geo["timezone"],
            "mismatch_detected": True, "match_ok": True}


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
    print("GEO-SYNC SELF-TEST: PASS")
