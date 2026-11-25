"""Mobile identity generation.

Extracted from fingerprint.py — logic unchanged.
"""
# GLM P4: import relatif dibuat LAZY (di dalam fungsi) supaya file ini bisa
# dibuktikan langsung (python3 fingerprint/mobile.py), bukan cuma via -m.


def new_mobile_identity(platform="random", country="sg"):
    """Generate identitas MOBILE yang konsisten (bukan desktop!).

    Args:
        platform: "random" | "ios" | "android" | "tablet"
        country: kode negara untuk geo (default "sg")

    Returns:
        dict identitas mobile dengan flag is_mobile=True.
        JANGAN campur dengan new_identity() (desktop)!

    Sumber: gmail/mobile_fingerprint.py — MobileFingerprint (451 device).
    """
    try:
        from ..gmail.mobile_fingerprint import MobileFingerprint, check_consistency
    except ImportError:
        # StealthXGM standalone: pakai vendored copy (tanpa dependensi stealth_browser)
        import os as _os
        import sys as _sys
        _sys.path.insert(0, _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "vendor"))
        from mobile_fingerprint import MobileFingerprint, check_consistency

    fp = MobileFingerprint(platform=platform)
    issues = check_consistency(fp)
    if issues:
        # Retry sekali kalau tidak konsisten (seharusnya tidak terjadi)
        fp = MobileFingerprint(platform=platform)
        issues = check_consistency(fp)
        if issues:
            raise ValueError(f"Mobile fingerprint inkonsisten: {issues}")

    d = fp.to_dict()

    # Geo konsisten dari country (seperti auto_identity)
    from .geo import _COUNTRY_GEO
    c = (country or "sg").strip().lower()
    tz, loc, lat, lon = _COUNTRY_GEO.get(c, _COUNTRY_GEO["sg"])

    return dict(
        is_mobile=True,  # FLAG PENTING: ini mobile, bukan desktop!
        mobile_platform=fp.platform,  # "ios" | "android" | "tablet"
        model=d["model"],
        os_version=d["os_version"],
        chipset=d["chipset"],
        ram_gb=d["ram_gb"],
        _ua=d["user_agent"],  # user agent mobile
        screen_w=d["viewport"]["width"],
        screen_h=d["viewport"]["height"],
        dpr=d["device_pixel_ratio"],
        hw=d["hardware_concurrency"],
        mem=d["device_memory"],
        vp=(d["viewport"]["width"], d["viewport"]["height"]),
        platform=d["platform_str"],  # "iPhone" | "iPad" | "Linux armv8l"
        max_touch_points=d["max_touch_points"],
        touch_support=d["touch_support"],
        screen_orientation=d["screen_orientation"],
        orientation_angle=d["orientation_angle"],
        color_depth=d["color_depth"],
        pixel_depth=d["pixel_depth"],
        screen_width_px=d["screen_width_px"],
        screen_height_px=d["screen_height_px"],
        user_agent_data=d["user_agent_data"],
        camoufox_os=d["camoufox_os"],
        # Geo (override dari mobile default id-ID kalau country beda)
        timezone=tz,
        locale=loc,
        geo_lat=lat,
        geo_lon=lon,
        geo_country=c,
        # Simpan objek asli untuk spoof_js mobile
        _mobile_fp=fp,
    )


def mobile_spoof_js(mobile_ident, timezone=None, locale=None):
    """Generate spoof JS untuk MOBILE identity.

    Args:
        mobile_ident: dict dari new_mobile_identity()
        timezone: override timezone (default dari ident)
        locale: override locale (default dari ident)

    Returns:
        str JS untuk inject via add_init_script / evaluate.

    CATATAN: Mobile pakai spoof_js() dari MobileFingerprint (touch,
    orientation, dll) + tambahan konsistensi geo. Desktop spoof
    (WebGL desktop, plugins, dll) TIDAK dipakai untuk mobile!
    """
    if not mobile_ident.get("is_mobile"):
        raise ValueError("mobile_spoof_js() hanya untuk mobile identity! "
                         "Pakai spoof_js() untuk desktop.")
    fp = mobile_ident["_mobile_fp"]
    js = fp.spoof_js()
    # NOTE: Mobile pakai spoof_js() dari MobileFingerprint (touch points,
    # orientation, screen, DPR, platform, hardwareConcurrency, deviceMemory).
    # Geo/timezone utama via proxy + browser context (seperti desktop).
    # Mobile browser real juga pakai timezone device, jadi ini acceptable.
    # Desktop spoof (WebGL desktop vendor, plugins, fonts, dll) SENGAJA
    # tidak dipakai untuk mobile — jangan campur!
    return js


def auto_mobile_identity(platform="random", country="sg"):
    """Generate identitas mobile LENGKAP otomatis — 1 baris!

    Contoh:
        ident = auto_mobile_identity("ios", "sg")
        js = mobile_spoof_js(ident)

    Returns:
        dict identitas mobile (is_mobile=True).
    """
    return new_mobile_identity(platform=platform, country=country)


def mobile_spoof_js_from_dict(d, timezone=None, locale=None):
    """Bangun mobile spoof JS dari dict tersimpan (tanpa objek MobileFingerprint).

    Dipakai launcher & preview untuk identitas mobile yang disimpan di profil
    (objek asli tidak bisa di-serialize ke JSON).
    screen_avail_* tidak tersimpan -> aproksimasi dari ukuran layar.
    """
    import json as _json
    import re as _re
    vp = d.get("vp") or [d.get("screen_w") or 412, d.get("screen_h") or 858]
    vp_w, vp_h = vp[0], vp[1]
    # AUDIT 2026-11-04: avail HARUS CSS px (= viewport), bukan physical px!
    # (sebelumnya availWidth=physical 1170 > width=390 = tell instan.
    #  Reference MobileFingerprint: avail = viewport, mobile tidak ada taskbar)
    avail_w, avail_h = vp_w, vp_h

    # ── userAgentData (AUDIT 2026-11-04) ──
    # Tanpa ini, nilai desktop Chromium asli bocor (platform "Linux",
    # mobile:false) padahal UA = mobile = mismatch!
    # - Chrome Android/iOS (CriOS): spoof mobile:true + platform Android/iOS
    # - Safari iOS (user_agent_data kosong): real Safari TIDAK PUNYA
    #   userAgentData -> sembunyikan (best effort: getter -> undefined)
    _uad = d.get("user_agent_data") or {}
    _uad_js = ""
    if _uad:
        _brands = _uad.get("brands", [])
        _uad_platform = _uad.get("platform", "Android")
        _osv = str(d.get("os_version", ""))
        _m = _re.search(r"(\d+(?:\.\d+)*)", _osv)
        _pv = (_m.group(1) + ".0.0") if _m else ""
        if _pv.count(".") == 1:
            _pv += ".0"
        _uam = _re.search(r"(?:Chrome|CriOS)/([\d.]+)", d.get("_ua", "") or "")
        _full = _uam.group(1) if _uam else ""
        _major = _full.split(".")[0] if _full else ""
        _model = "" if _uad_platform == "iOS" else str(d.get("model", ""))
        _uad_js = f"""
// userAgentData mobile ( konsisten dengan UA )
// AUDIT 2026-11-04 P0#2: getter BERNAMA + _mpm (mini trap mobile).
try {{
    const _b = {_json.dumps(_brands)};
    const _fl = _b.map(b => ({{brand: b.brand, version: b.version}}));
    const _fGHE = function(h) {{ return Promise.resolve({{
        architecture: 'arm', bitness: '64',
        model: {_json.dumps(_model)}, platformVersion: {_json.dumps(_pv)},
        uaFullVersion: {_json.dumps(_full)},
        fullVersionList: _fl
    }}); }};
    _mpm(_fGHE);
    const _fUAD = function() {{ return {{
        brands: _b, mobile: true, platform: {_json.dumps(_uad_platform)},
        getHighEntropyValues: _fGHE
    }}; }};
    try {{ Object.defineProperty(_fUAD, 'name', {{ value: 'get userAgentData', configurable: true }}); }} catch(e) {{}}
    Object.defineProperty(navigator, 'userAgentData', {{get: _fUAD, configurable: true}});
    _mpm(_fUAD);
}} catch (e) {{}}
"""
    elif str(d.get("platform", "")) in ("iPhone", "iPad"):
        # Safari iOS: tidak punya userAgentData -> sembunyikan
        # AUDIT 2026-11-04 P0#2: getter BERNAMA + _mpm.
        _uad_js = """
// Safari iOS tidak punya navigator.userAgentData -> sembunyikan
try {
    const _fUADh = function() { return undefined; };
    try { Object.defineProperty(_fUADh, 'name', { value: 'get userAgentData', configurable: true }); } catch(e) {}
    Object.defineProperty(navigator, 'userAgentData', {get: _fUADh, configurable: true});
    _mpm(_fUADh);
} catch (e) {}
"""

    # AUDIT 2026-11-04 P0#2: mobile standalone tidak punya tostring trap —
    # getter anonim "() => ..." bocor via .toString(). Tambahkan mini trap +
    # getter BERNAMA ("get userAgent") seperti spoof_js desktop.
    def _mg(prop, obj, val_js, _c=[0]):
        _c[0] += 1
        _v = f"_gm{_c[0]}"
        return (
            "try {\n"
            f"  const {_v} = function() {{ return {val_js}; }};\n"
            f"  try {{ Object.defineProperty({_v}, 'name', {{ value: 'get {prop}', configurable: true }}); }} catch(e) {{}}\n"
            f"  Object.defineProperty({obj}, '{prop}', {{ get: {_v}, configurable: true }});\n"
            f"  _mpm({_v});\n"
            "} catch(e) {}"
        )

    _mini_trap = """// ── Mobile fingerprint spoof (model: %s, %s, %s) ──
// mini toString trap (mobile standalone — tidak pakai spoof_js desktop)
(() => {
  try {
    const _oTS = Function.prototype.toString;
    const _ps = new WeakSet();
    Function.prototype.toString = function() {
      if (_ps.has(this)) {
        const _n = this.name || '';
        return _n ? `function ${_n}() { [native code] }` : 'function () { [native code] }';
      }
      return _oTS.call(this);
    };
    window.__markPatched = (fn) => { try { _ps.add(fn); } catch(e) {} };
  } catch(e) {}
})();
const _mpm = (fn) => { try { if (window.__markPatched) window.__markPatched(fn); } catch(e) {} };
""" % (d.get('model'), d.get('os_version'), d.get('chipset'))

    _getters = "\n".join([
        _mg("userAgent", "navigator", _json.dumps(d.get('_ua', ''))),
        _mg("maxTouchPoints", "navigator", str(d.get('max_touch_points', 5))),
        _mg("hardwareConcurrency", "navigator", str(d.get('hw', 8))),
        _mg("deviceMemory", "navigator", str(d.get('mem', 4))),
        _mg("platform", "navigator", _json.dumps(d.get('platform', ''))),
        _mg("width", "screen", str(vp_w)),
        _mg("height", "screen", str(vp_h)),
        _mg("availWidth", "screen", str(avail_w)),
        _mg("availHeight", "screen", str(avail_h)),
        _mg("colorDepth", "screen", str(d.get('color_depth', 24))),
        _mg("pixelDepth", "screen", str(d.get('pixel_depth', 24))),
        _mg("devicePixelRatio", "window", str(d.get('dpr', 2))),
    ])

    _orient_js = ""
    if True:
        _orient_js = "\n".join([
            "if (screen.orientation) {",
            "    try {",
            "        " + _mg("type", "screen.orientation",
                            _json.dumps(d.get('screen_orientation', 'portrait-primary'))).replace("\n", "\n        "),
            "        " + _mg("angle", "screen.orientation",
                            str(d.get('orientation_angle', 0))).replace("\n", "\n        "),
            "    } catch (e) {}",
            "}",
        ])

    return _mini_trap + _getters + """
window.ontouchstart = null;  // touch support terdeteksi
""" + _orient_js + "\n" + _uad_js


if __name__ == "__main__":
    if not __package__:
        # Dijalankan langsung: jalankan ulang sebagai modul paket (GLM P4).
        import os as _os, sys as _sys, runpy as _runpy, warnings as _warnings
        _warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")
        _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        _runpy.run_module("fingerprint.mobile", run_name="__main__")
        raise SystemExit(0)
    print("=== TEST mobile.py (GLM P2/P4: konsistensi + self-test) ===")
    from .mobile_devices import soc_to_gpu as _soc_to_gpu
    from .geo import _COUNTRY_GEO as _GEO
    for _plat in ("android", "ios", "tablet"):
        for _i in range(3):
            _d = new_mobile_identity(platform=_plat, country="id")
            assert _d["is_mobile"] is True, f"{_plat}: is_mobile bukan True"
            assert _d["model"] and _d["chipset"], f"{_plat}: model/chipset kosong"
            # Catatan jujur: dict mentah new_mobile_identity() BELUM berisi
            # gpu_vendor/gpu_renderer — itu ditambahkan wrapper
            # new_mobile_identity_soc_gpu() (mobile_devices.py). Yang dicek di
            # sini: soc_to_gpu(chipset) mengembalikan vendor yang masuk akal
            # untuk platformnya (dicek eksplisit di loop ios/android di bawah).
            # Mobile: viewport == layar (tidak ada taskbar) — beda dari desktop.
            assert _d["vp"] == (_d["screen_w"], _d["screen_h"]), \
                f"{_plat}: vp {_d['vp']} != layar {_d['screen_w']}x{_d['screen_h']}"
            assert _d["dpr"] > 0 and _d["hw"] >= 1, f"{_plat}: dpr/hw aneh: {_d}"
            assert _d["timezone"] == _GEO["id"][0] and _d["locale"] == _GEO["id"][1], \
                f"{_plat}: timezone/locale tidak match country id"
            # mem = deviceMemory (bucket Chrome): hanya {2,4,8} — lihat
            # _RAM_TO_DEVICE_MEMORY di vendor/mobile_fingerprint.py.
            assert _d["mem"] in (2, 4, 8), f"{_plat}: deviceMemory aneh: {_d['mem']}"
        print(f"  {_plat}: 3 identitas — is_mobile, SoC, vp==layar, geo id, mem OK")
    # iOS harus pakai Apple GPU, Android tidak boleh pakai Apple GPU.
    for _i in range(5):
        _d = new_mobile_identity(platform="ios")
        _v, _r = _soc_to_gpu(_d["chipset"])
        assert _v == "Apple", f"iOS chipset {_d['chipset']} -> GPU vendor {_v} (harusnya Apple)"
    for _i in range(5):
        _d = new_mobile_identity(platform="android")
        _v, _r = _soc_to_gpu(_d["chipset"])
        assert _v != "Apple", f"Android chipset {_d['chipset']} -> Apple GPU (tidak masuk akal)"
    print("  ios: 5x Apple GPU; android: 5x bukan Apple GPU")
    # spoof JS dari dict tersimpan (tanpa objek) harus mengandung model + trap.
    _d = new_mobile_identity(platform="android")
    _js = mobile_spoof_js_from_dict(_d)
    assert _d["model"] in _js and "toString" in _js, "mobile_spoof_js_from_dict kosong/aneh"
    print(f"  mobile_spoof_js_from_dict: {len(_js)} karakter, model + toString trap ada")
    print("\n✅ mobile.py OK")
