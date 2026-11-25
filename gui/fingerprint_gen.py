"""Fingerprint Generator — visual configurator backend.

2 mode:
  RANDOM  — generate identitas yang KONSISTEN per OS ("ngotak"):
            Mac -> Apple GPU/Metal, Windows -> D3D11, Linux -> OpenGL,
            Android/iOS -> SoC->GPU mapping, CPU tier match GPU tier.
  MANUAL  — user pilih tiap field, validate() kasih warning kalau tidak konsisten.

Identity dict (canonical, JSON-safe):
  Desktop: {os, is_mobile, platform, oscpu, chrome_ver, vendor, app_ver, _ua,
            gpu_vendor, gpu_renderer, gpu_class, screen_w, screen_h, dpr,
            hw, mem, vp, color_depth, pixel_depth, timezone, locale}
  Mobile:  {os, is_mobile, mobile_platform, model, os_version, chipset,
            ram_gb, _ua, screen_w, screen_h, dpr, hw, mem, vp, platform,
            gpu_vendor, gpu_renderer, timezone, locale, ...}

PENTING: tidak ada credential di file ini. Hanya teknik spoofing.
"""

# ── BATASAN (jujur, diukur — adopsi GLM 5.3 P5, 2026-11-05) ──────────────
# Tulis apa yang TIDAK bisa dilakukan file ini, dengan angka/bukti, supaya
# tidak ada yang mengira fingerprint ini sempurna:
# - deviceMemory (mem) hanya 4/8: Chrome meng-cap navigator.deviceMemory di
#   8 — nilai 16 TIDAK BISA di-spoof (validate_identity menolak mem > 8).
# - Hanya Chrome: UA Edge (Edg/), ChromeOS (CrOS), 32-bit (WOW64) DIBUANG di
#   _ua_for_platform — userAgentData kita selalu "Google Chrome" 64-bit,
#   jadi UA itu tidak bisa konsisten.
# - Mobile GPU renderer adalah APROKSIMASI format kita sendiri
#   ("Adreno (Qualcomm, Snapdragon ...)") — bukan string ANGLE persis yang
#   dibaca dari WebGL device asli. Belum pernah dibandingkan dengan
#   getParameter() perangkat nyata.
# - iOS: userAgentData.platformVersion dihitung dari os_version, dan model
#   TIDAK di-expose (Apple tidak mengekspos model di userAgentData).
# - generate_* TIDAK punya seed: dua panggilan tidak bisa direproduksi persis.
#   Kalau butuh reproduksibilitas, set random.seed() dari luar sebelum panggil.
# - TERUKUR 2026-11-05: 1000 identitas acak (200/OS x windows/macos/linux/
#   android/ios) → 0 warning validate_identity, 0 pelanggaran viewport<screen.
#   Itu bukti generator ini konsisten, BUKAN bukti anti-bot tidak bisa
#   mendeteksinya — deteksi nyata belum pernah diuji terhadap CreepJS/dsb.
# ──────────────────────────────────────────────────────────────────────────

import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from fingerprint.devices import (
    _mk, SCREENS, HWS, MEMS,
    _NVIDIA_MID, _NVIDIA_HIGH, _AMD_MID, _AMD_HIGH, _AMD_APU,
    _INTEL_IGPU, _INTEL_MID, _APPLE_SILICON,
)
from fingerprint.geo import BROWSER_DETAILS, SCREEN_DETAILS, USER_AGENTS, _COUNTRY_GEO
from fingerprint.mobile_devices import (
    new_mobile_identity_soc_gpu, soc_to_gpu, weighted_tier,
)

OS_LIST = ["windows", "macos", "linux", "android", "ios"]

# platform navigator per OS (harus match BROWSER_DETAILS["platform"])
_OS_PLATFORM = {
    "windows": "Win32",
    "macos": "MacIntel",
    "linux": "Linux x86_64",
}

# GPU pool per OS — backend HARUS match OS (D3D11 Mac = tell instan!)
def _gpu_pool(os_name):
    if os_name == "macos":
        return _mk("Apple", _APPLE_SILICON, "apple", backend="metal")
    if os_name == "linux":
        return (_mk("NVIDIA", _NVIDIA_MID, "mid", backend="gl")
                + _mk("NVIDIA", _NVIDIA_HIGH, "high", backend="gl")
                + _mk("AMD", _AMD_MID, "mid", backend="gl")
                + _mk("AMD", _AMD_HIGH, "high", backend="gl")
                + _mk("AMD", _AMD_APU, "igpu", backend="gl")
                + _mk("Intel", _INTEL_IGPU, "igpu", backend="gl")
                + _mk("Intel", _INTEL_MID, "mid", backend="gl"))
    # windows: D3D11 (default backend)
    return (_mk("NVIDIA", _NVIDIA_MID, "mid") + _mk("NVIDIA", _NVIDIA_HIGH, "high")
            + _mk("AMD", _AMD_MID, "mid") + _mk("AMD", _AMD_HIGH, "high")
            + _mk("AMD", _AMD_APU, "igpu")
            + _mk("Intel", _INTEL_IGPU, "igpu") + _mk("Intel", _INTEL_MID, "mid"))

_GPU_POOL_CACHE = {os_name: _gpu_pool(os_name) for os_name in ("windows", "macos", "linux")}

# Chrome versions yang plausible (sinkron dengan BROWSER_DETAILS)
CHROME_VERSIONS = sorted({b["chrome_ver"] for b in BROWSER_DETAILS})

# Timezone options dari geo DB
TIMEZONE_LIST = [
    {"timezone": tz, "locale": loc, "country": cc}
    for (tz, loc), cc in sorted(
        { (tz, loc): cc for cc, (tz, loc, _a, _b) in _COUNTRY_GEO.items() }.items()
    )
]


# ── helpers ──────────────────────────────────────────────────────────────
def _ua_for_platform(platform):
    cands = [u for u in USER_AGENTS if {
        "Win32": "Windows NT",
        "MacIntel": "Macintosh",
        "Linux x86_64": "Linux x86_64",
    }[platform] in u]
    # AUDIT 2026-11-04: buang UA yang tidak bisa kita spoof dengan konsisten:
    # - CrOS: ChromeOS (platform kita bukan CrOS)
    # - WOW64: Chrome 32-bit (client hints bitness kita selalu 64)
    # - Edg/: Microsoft Edge (brands userAgentData kita "Google Chrome")
    cands = [u for u in cands if "CrOS" not in u and "WOW64" not in u
             and "Edg/" not in u]
    return random.choice(cands) if cands else random.choice(USER_AGENTS)


# reverse map: timezone -> (lat, lon) untuk geolocation yang konsisten
# (dibangun dari _COUNTRY_GEO; semua tz di TIMEZONE_LIST ter-cover)
_TZ_GEO = {tz: (lat, lon) for _cc, (tz, _loc, lat, lon) in _COUNTRY_GEO.items()}


def _browser_for_platform(platform, chrome_ver=None):
    cands = [b for b in BROWSER_DETAILS if b["platform"] == platform]
    if chrome_ver:
        cands = [b for b in cands if b["chrome_ver"] == chrome_ver] or cands
    return random.choice(cands)


def to_runtime(ident):
    """JSON-safe dict -> runtime dict (list jadi tuple untuk vp)."""
    d = dict(ident or {})
    if isinstance(d.get("vp"), list):
        d["vp"] = tuple(d["vp"])
    return d


def to_jsonable(ident):
    """Runtime dict -> JSON-safe (tuple jadi list, buang objek internal)."""
    import json
    d = dict(ident or {})
    if isinstance(d.get("vp"), tuple):
        d["vp"] = list(d["vp"])
    # buang field internal yang tidak bisa di-serialize (mis. objek MobileFingerprint)
    for k in list(d.keys()):
        if k.startswith("_") and k != "_ua":
            d.pop(k, None)
    for k in list(d.keys()):
        try:
            json.dumps(d[k])
        except TypeError:
            d.pop(k, None)
    return d


# ── RANDOM (ngotak) ──────────────────────────────────────────────────────
def generate_desktop(os_name, timezone="Asia/Jakarta", locale=None, chrome_ver=None):
    """Generate identitas desktop yang konsisten untuk OS tertentu."""
    if os_name not in _OS_PLATFORM:
        raise ValueError(f"os harus salah satu {list(_OS_PLATFORM)}")
    platform = _OS_PLATFORM[os_name]

    gv, gr, cls = random.choice(_GPU_POOL_CACHE[os_name])
    screens = SCREENS[cls]
    if cls == "apple":
        # Mac: pilih layar Retina (dpr=2); 1920x1080@1x itu monitor eksternal,
        # bukan default yang "ngotak" untuk random
        retina = [s for s in screens if s[2] == 2]
        screens = retina or screens
    sw, sh, dpr = random.choice(screens)
    hw = random.choice(HWS[cls])
    mem = random.choices(MEMS, weights=[1, 4])[0]
    vw = random.randint(int(sw * 0.6), sw - 40)
    vh = random.randint(int(sh * 0.6), sh - 80)

    browser = _browser_for_platform(platform, chrome_ver)
    screen_det = random.choice(SCREEN_DETAILS)
    ua = _ua_for_platform(platform)
    # AUDIT 2026-11-04: SELALU sinkronkan versi Chrome di UA dengan chrome_ver
    # (sebelumnya hanya kalau param chrome_ver diisi -> 43-59% mismatch
    #  antara UA string vs userAgentData.uaFullVersion = tell!)
    if "Chrome/" in ua:
        ua = re.sub(r"Chrome/[\d.]+", f"Chrome/{browser['chrome_ver']}", ua)

    # AUDIT 2026-11-04: geolocation konsisten dengan timezone
    # (sebelumnya geo_lat tidak di-set -> default Singapore padahal
    #  timezone bisa Tokyo = inkonsisten)
    _lat, _lon = _TZ_GEO.get(timezone, (None, None))

    ident = dict(
        os=os_name, is_mobile=False,
        platform=platform, oscpu=browser["oscpu"],
        chrome_ver=browser["chrome_ver"], vendor=browser["vendor"],
        app_ver=browser["app_ver"], _ua=ua,
        gpu_vendor=gv, gpu_renderer=gr, gpu_class=cls,
        screen_w=sw, screen_h=sh, dpr=dpr,
        hw=hw, mem=mem, vp=(vw, vh),
        color_depth=screen_det["color_depth"],
        pixel_depth=screen_det["pixel_depth"],
        timezone=timezone, locale=locale,
    )
    if _lat is not None:
        ident["geo_lat"] = _lat
        ident["geo_lon"] = _lon
    out = to_jsonable(ident)
    assert_consistent(out)  # GLM P2: generator tidak boleh loloskan inkonsistensi
    return out


def generate_mobile(os_name, country="id"):
    """Generate identitas mobile konsisten (SoC->GPU mapping)."""
    if os_name not in ("android", "ios"):
        raise ValueError("os harus android atau ios")
    ident = new_mobile_identity_soc_gpu(platform=os_name, country=country)
    ident["os"] = os_name
    # timezone/locale konsisten dari country
    tz, loc, _lat, _lon = _COUNTRY_GEO.get(country, _COUNTRY_GEO["sg"])
    ident["timezone"] = tz
    ident["locale"] = loc
    out = to_jsonable(ident)
    assert_consistent(out)  # GLM P2: generator tidak boleh loloskan inkonsistensi
    return out


def generate_random(os_name, timezone="Asia/Jakarta", locale=None,
                    chrome_ver=None, country="id"):
    """Satu pintu untuk mode random."""
    if os_name in ("android", "ios"):
        return generate_mobile(os_name, country=country)
    return generate_desktop(os_name, timezone=timezone, locale=locale,
                            chrome_ver=chrome_ver)


# ── VALIDATE (mode manual) ───────────────────────────────────────────────
def validate_identity(ident):
    """Cek konsistensi identitas. Return list warning (kosong = konsisten)."""
    w = []
    d = ident or {}
    platform = d.get("platform", "")
    gr = d.get("gpu_renderer", "")
    ua = d.get("_ua", "")
    mem = d.get("mem")
    cls = d.get("gpu_class", "")
    sw, sh, dpr = d.get("screen_w"), d.get("screen_h"), d.get("dpr")

    if d.get("is_mobile"):
        # mobile checks
        chipset = d.get("chipset", "")
        exp_vendor, exp_renderer = soc_to_gpu(chipset)
        if d.get("gpu_vendor") != exp_vendor:
            w.append(f"GPU vendor '{d.get('gpu_vendor')}' tidak match chipset '{chipset}' "
                     f"(harusnya '{exp_vendor}')")
        if exp_renderer not in str(d.get("gpu_renderer", "")):
            w.append(f"GPU renderer tidak match chipset '{chipset}' "
                     f"(harusnya mengandung '{exp_renderer}')")
        if d.get("os") == "ios" and "Apple" not in str(d.get("gpu_vendor", "")):
            w.append("iOS harus pakai Apple GPU")
        if d.get("os") == "android" and d.get("mobile_platform") == "ios":
            w.append("OS android tapi mobile_platform ios — tidak konsisten")
        return w

    # desktop checks
    if platform == "MacIntel":
        if "Metal" not in gr:
            w.append(f"MacIntel dengan renderer '{gr[:60]}' — Mac harus pakai ANGLE Metal Renderer")
        if cls != "apple":
            w.append(f"MacIntel dengan gpu_class '{cls}' — harusnya 'apple'")
        if "Macintosh" not in ua:
            w.append("User-Agent tidak mengandung 'Macintosh' untuk platform MacIntel")
    elif platform == "Win32":
        if "Direct3D11" not in gr:
            w.append(f"Win32 dengan renderer '{gr[:60]}' — Windows harus pakai Direct3D11")
        if cls == "apple":
            w.append("Win32 dengan GPU Apple — tidak masuk akal")
        if "Windows NT" not in ua:
            w.append("User-Agent tidak mengandung 'Windows NT' untuk platform Win32")
    elif platform == "Linux x86_64":
        if "OpenGL" not in gr:
            w.append(f"Linux dengan renderer '{gr[:60]}' — Linux harus pakai OpenGL")
        if cls == "apple":
            w.append("Linux dengan GPU Apple — tidak masuk akal")
        if "Linux x86_64" not in ua:
            w.append("User-Agent tidak mengandung 'Linux x86_64'")
    else:
        w.append(f"Platform '{platform}' tidak dikenal")

    # AUDIT 2026-11-04: UA string harus konsisten dengan chrome_ver
    # (userAgentData.uaFullVersion diambil dari chrome_ver)
    _m = re.search(r"Chrome/([\d.]+)", ua or "")
    if _m and d.get("chrome_ver") and _m.group(1) != d["chrome_ver"]:
        w.append(f"UA Chrome/{_m.group(1)} != chrome_ver {d['chrome_ver']} "
                 f"(userAgentData bakal mismatch)")
    for _bad in ("WOW64", "Edg/", "CrOS"):
        if _bad in (ua or ""):
            w.append(f"UA mengandung '{_bad}' yang tidak bisa di-spoof konsisten")
    if isinstance(mem, int) and mem > 8:
        w.append(f"deviceMemory {mem} — Chrome cap di 8, nilai >8 = tell bot")
    _retina_native = {(1512, 982), (1728, 1117), (1440, 900), (2560, 1600), (2048, 1152)}
    if cls == "apple" and (sw, sh) in _retina_native and dpr != 2:
        w.append(f"Layar Retina {(sw, sh)} harusnya dpr=2, bukan {dpr}")
    hw = d.get("hw")
    if cls == "igpu" and isinstance(hw, int) and hw > 8:
        w.append(f"iGPU dengan {hw} core — tidak masuk akal (maks 8)")
    if cls == "high" and isinstance(hw, int) and hw < 8:
        w.append(f"GPU high-end dengan {hw} core — tidak masuk akal (min 8)")
    return w


# ── ASSERT KERAS (adopsi GLM 5.3 P2: tegakkan, bukan harapkan) ────────────
def assert_consistent(ident):
    """Validasi keras: raise AssertionError kalau identitas inkonsisten.

    Dipakai di akhir generate_desktop/generate_mobile — identitas yang lolos
    dari generator HARUS konsisten, kalau tidak itu bug generator (bukan
    salah pemakai). Beda dengan validate_identity() yang hanya memberi
    warning untuk mode manual (user boleh sengaja tidak konsisten).
    """
    d = ident or {}
    # 1. Semua warning validate_identity = gagal keras di jalur generate.
    warnings = validate_identity(d)
    assert not warnings, f"identitas inkonsisten: {warnings} | ident={d}"
    # 2. Invarian GLM P2 yang tidak ditangkap validate_identity:
    sw, sh = d.get("screen_w"), d.get("screen_h")
    vp = d.get("vp") or []
    if d.get("is_mobile"):
        # Mobile: viewport == layar (tidak ada taskbar/browser chrome).
        assert list(vp) == [sw, sh], \
            f"mobile vp {vp} != layar {sw}x{sh}"
        # Mobile: RAM sesuai nilai nyata di DB vendor (453 profil, 2026-11-05):
        # {1,2,3,4,6,8,12,16,18,24} — termasuk ROG Phone 8 Pro 24GB.
        # (Asumsi awal (3,4,6,8,12,16) SALAH — assert ini yang menangkapnya.)
        assert d.get("ram_gb") in (1, 2, 3, 4, 6, 8, 12, 16, 18, 24), \
            f"mobile ram_gb aneh: {d.get('ram_gb')}"
    else:
        # Desktop: viewport HARUS lebih kecil dari layar.
        assert len(vp) == 2 and vp[0] < sw and vp[1] < sh, \
            f"desktop vp {vp} >= layar {sw}x{sh}"
        # Desktop: layar iGPU max 1920 lebar.
        if d.get("gpu_class") == "igpu":
            assert sw <= 1920, f"iGPU dengan layar {sw}px (>1920)"
    return True


# ── PREVIEW ──────────────────────────────────────────────────────────────
def preview_identity(ident, features=None, timezone=None, locale=None):
    """Generate JS + ringkasan field untuk preview. Tidak launch browser."""
    from fingerprint import spoof_js
    from fingerprint.mobile import mobile_spoof_js_from_dict
    d = to_runtime(ident)
    tz = timezone or d.get("timezone") or "Asia/Jakarta"
    loc = locale if locale is not None else d.get("locale")

    if d.get("is_mobile"):
        js = mobile_spoof_js_from_dict(d, timezone=tz, locale=loc)
        js += "\n" + (d.get("gpu_spoof_js") or "")
        ua = d.get("_ua", "")
        gpu = f"{d.get('gpu_vendor')} / {d.get('gpu_renderer')}"
    else:
        js = spoof_js(d, timezone=tz, locale=loc, features=features)
        ua = d.get("_ua", "")
        gpu = f"{d.get('gpu_vendor')} / {d.get('gpu_renderer')}"

    return {
        "user_agent": ua,
        "platform": d.get("platform"),
        "gpu": gpu,
        "screen": f"{d.get('screen_w')}x{d.get('screen_h')} @ {d.get('dpr')}x",
        "cores": d.get("hw"),
        "memory_gb": d.get("mem"),
        "timezone": tz,
        "locale": loc or "(auto dari timezone)",
        "webdriver": False,  # spoof_js selalu patch webdriver=false
        "mobile": bool(d.get("is_mobile")),
        "js_length": len(js),
        "warnings": validate_identity(d),
    }


# ── OPTIONS untuk dropdown manual ────────────────────────────────────────
def manual_options(os_name):
    """Opsi dropdown untuk mode manual per OS."""
    opts = {
        "os": OS_LIST,
        "chrome_versions": CHROME_VERSIONS,
        "timezones": TIMEZONE_LIST,
        "mems": MEMS,
    }
    if os_name in ("android", "ios"):
        opts["note"] = "Mobile: GPU otomatis dari SoC (tidak bisa manual)"
        opts["gpus"] = []
        opts["screens"] = []
    else:
        pool = _GPU_POOL_CACHE[os_name]
        seen = []
        for gv, gr, cls in pool:
            # tampilkan nama model singkat dari renderer
            # Metal: "ANGLE (Apple, ANGLE Metal Renderer: Apple M1, ...)" -> "Apple M1"
            # D3D11: "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 ...)" -> model
            # GL:    "ANGLE (NVIDIA, GeForce RTX 3070, OpenGL 4.6)" -> model
            label = gr
            m = re.search(r"Metal Renderer:\s*([^,]+)", gr)
            if m:
                label = m.group(1).strip()
            else:
                m2 = re.search(r"ANGLE\s*\(\s*[^,]+,\s*(.+?)(?:\s+Direct3D11|\s*,\s*OpenGL|\s*\))", gr)
                if m2:
                    label = m2.group(1).strip()
            if label not in [s["label"] for s in seen]:
                seen.append({"label": label[:70], "vendor": gv, "renderer": gr, "class": cls})
        opts["gpus"] = seen
        cls_set = sorted({c for _, _, c in pool})
        opts["screens"] = [
            {"label": f"{w}x{h} @ {dpr}x", "w": w, "h": h, "dpr": dpr, "class": c}
            for c in cls_set for (w, h, dpr) in SCREENS[c]
        ]
        opts["cores"] = sorted({x for c in cls_set for x in HWS[c]})
    return opts


if __name__ == "__main__":
    # GLM P4: file membuktikan dirinya sendiri saat dibuka.
    # Dijalankan: python3 gui/fingerprint_gen.py  (dari root antibrowser)
    print("=== TEST fingerprint_gen.py (GLM P2/P4: asserts + self-test) ===")
    # 1. generate_* 20x per OS: assert_consistent lolos + 0 warning.
    for _os in ("windows", "macos", "linux", "android", "ios"):
        for _i in range(20):
            _ident = generate_random(_os)
            assert validate_identity(_ident) == [], \
                f"{_os}: validate warning: {validate_identity(_ident)}"
            assert_consistent(_ident)
        print(f"  {_os}: 20 identitas — assert_consistent lolos, 0 warning")
    # 2. Distribusi tier mobile realistis (GLM P6: budget 40/mid 40/flagship 20).
    from collections import Counter as _Counter
    _tiers = _Counter(generate_mobile("android")["device_tier"] for _ in range(100))
    assert set(_tiers) == {"budget", "mid", "flagship"}, \
        f"tier mobile tidak lengkap dalam 100 draw: {_tiers}"
    print(f"  mobile tier 100x: {dict(_tiers)} (ketiga tier muncul)")
    # 3. preview_identity: JS + ringkasan, tanpa warning.
    _pv = preview_identity(generate_random("windows"))
    assert _pv["js_length"] > 1000 and _pv["warnings"] == [], \
        f"preview aneh: js={_pv['js_length']} warnings={_pv['warnings']}"
    _pvm = preview_identity(generate_random("android"))
    assert _pvm["mobile"] is True and _pvm["warnings"] == [], \
        f"preview mobile aneh: {_pvm}"
    print(f"  preview desktop: JS {_pv['js_length']} karakter, 0 warning; "
          f"preview mobile: JS {_pvm['js_length']} karakter, 0 warning")
    # 4. manual_options: dropdown terisi per OS.
    _opts = manual_options("windows")
    assert _opts["gpus"] and _opts["screens"] and _opts["cores"], \
        "manual_options(windows) kosong"
    _optsm = manual_options("android")
    assert "tidak bisa manual" in _optsm["note"], "manual_options(android) aneh"
    print(f"  manual_options: windows {_opts['gpus'].__len__()} GPU, "
          f"{_opts['screens'].__len__()} layar; android: GPU manual ditolak (benar)")
    # 5. assert_consistent MENOLAK identitas yang sengaja dirusak (test negatif).
    _bad = generate_random("windows")
    _bad["mem"] = 16  # Chrome cap 8 — harus ditolak
    try:
        assert_consistent(_bad)
        raise SystemExit("❌ assert_consistent GAGAL menolak mem=16!")
    except AssertionError as _e:
        assert "deviceMemory" in str(_e) or "mem" in str(_e).lower()
    _bad2 = generate_random("windows")
    _bad2["screen_w"] = 1920
    _bad2["vp"] = [2000, 1000]  # viewport lebih besar dari layar
    try:
        assert_consistent(_bad2)
        raise SystemExit("❌ assert_consistent GAGAL menolak vp > layar!")
    except AssertionError:
        pass
    print("  test negatif: mem=16 dan vp>layar DITOLAK assert_consistent (benar)")
    print("\n✅ fingerprint_gen.py OK")
