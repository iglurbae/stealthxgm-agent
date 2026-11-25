#!/usr/bin/env python3
"""
Antibrowser Launcher — launch real Chromium per profile with fingerprint injection.

Architecture (AdsPower-style, from RND):
  1. subprocess: chromium --user-data-dir=<profile> --remote-debugging-port=<port>
     [proxy args] [anti-throttle flags]
  2. patchright connect_over_cdp(http://127.0.0.1:<port>)
  3. default context -> add_init_script(fingerprint_js)
     (CDP Page.addScriptToEvaluateOnNewDocument — fires BEFORE any page script)
  4. return {debug_port, ws_url, pid} — same shape as AdsPower Local API

Profile isolation: dedicated --user-data-dir per profile id.
Proxy per profile: --proxy-server arg (+ bypass for localhost so CDP keeps working).
Proxy auth (user/pass) is answered by a small MV3 extension
(extension_builder.build_proxy_auth_extension) — credentials NEVER go in argv.

This module lives in ~/workspace/antibrowser/ (separate project).
It NEVER touches ~/workspace/tools/bugbounty-hunt/stealth_browser/ (original).
"""
import argparse
import asyncio
import fcntl
import json
import os
import random
import shutil
import signal
import socket
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # .../antibrowser/launcher
ANTIBROWSER_DIR = os.path.dirname(BASE_DIR)                    # .../antibrowser
BROWSER_PROFILES_DIR = os.path.join(ANTIBROWSER_DIR, "browser_profiles")
SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")


def _json_store():
    """Lazy import gui/json_store.py (locking P-07) — launcher berdiri
    sendiri tanpa dependensi import-time ke package gui."""
    gui_dir = os.path.join(ANTIBROWSER_DIR, "gui")
    if gui_dir not in sys.path:
        sys.path.insert(0, gui_dir)
    import json_store
    return json_store

sys.path.insert(0, ANTIBROWSER_DIR)

# ── Chrome binary discovery ──────────────────────────────────────────────
def find_chrome():
    # 1. patchright bundled chromium (primary)
    try:
        from patchright.sync_api import sync_playwright
        with sync_playwright() as p:
            path = p.chromium.executable_path
            if path and os.path.exists(path):
                return path
    except Exception:
        pass
    # 2. system binaries
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    # 3. known cache locations
    for cand in (
        os.path.expanduser("~/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome"),
        os.path.expanduser("~/.cache/patchright/chromium/chrome-linux/chrome"),
    ):
        if os.path.exists(cand):
            return cand
    raise RuntimeError("Chromium binary not found (patchright not installed?)")


# ── FIX 1 (RND 2026-11-04): TLS/Version Consistency ──────────────────────
# Masalah: fingerprint klaim chrome_ver X (mis. "155.0.0.0") tapi binary
# Chromium yang jalan versi Y (mis. "156.0.8078.4") -> mismatch = red flag
# untuk detector yang korelasikan TLS/JA3 dengan versi browser.
# Solusi: deteksi versi REAL dari binary, sinkronkan identitas sebelum inject.
_REAL_CHROME_VERSION_CACHE = None


def get_real_chrome_version(chrome_path=None):
    """Deteksi versi Chromium aktual dari binary. Return "156.0.8078.4" atau None.

    Di-cache per proses (binary tidak ganti saat runtime).
    """
    global _REAL_CHROME_VERSION_CACHE
    if _REAL_CHROME_VERSION_CACHE is not None:
        return _REAL_CHROME_VERSION_CACHE
    try:
        path = chrome_path or find_chrome()
        out = subprocess.run([path, "--version"], capture_output=True,
                             text=True, timeout=10).stdout or ""
        # "Google Chrome for Testing 156.0.8078.4" / "Chromium 156.0.8078.4"
        import re
        m = re.search(r"(\d+)\.(\d+)\.(\d+)\.(\d+)", out)
        if m:
            _REAL_CHROME_VERSION_CACHE = m.group(0)
            return _REAL_CHROME_VERSION_CACHE
    except Exception:
        pass
    _REAL_CHROME_VERSION_CACHE = None
    return None


def sync_identity_chrome_version(ident, real_version=None):
    """Sinkronkan chrome_ver identitas dengan versi Chromium REAL.

    - ident["chrome_ver"] -> real_version full (mis. "156.0.8078.4")
      dipakai untuk userAgentData.uaFullVersion (navigator.py)
    - ident["_ua"] -> "Chrome/156.0.0.0" (format UA asli: major.0.0.0)
    - ident["app_ver"] -> disesuaikan juga kalau mengandung Chrome/x

    Return ident yang sama (in-place) + True kalau ada perubahan.
    Backward compatible: kalau real_version None -> tidak diubah.
    """
    import re
    if not real_version:
        real_version = get_real_chrome_version()
    if not real_version or not isinstance(ident, dict):
        return ident, False
    major = real_version.split(".")[0]
    changed = False
    # chrome_ver: full real version untuk uaFullVersion
    if ident.get("chrome_ver") != real_version:
        ident["chrome_ver"] = real_version
        changed = True
    # _ua: format asli "Chrome/156.0.0.0" (bukan full build number!)
    ua = ident.get("_ua", "")
    if ua and "Chrome/" in ua:
        new_ua = re.sub(r"Chrome/[\d.]+", f"Chrome/{major}.0.0.0", ua)
        if new_ua != ua:
            ident["_ua"] = new_ua
            changed = True
    # app_ver: mirror dari _ua pattern
    av = ident.get("app_ver", "")
    if av and "Chrome/" in av:
        new_av = re.sub(r"Chrome/[\d.]+", f"Chrome/{major}.0.0.0", av)
        if new_av != av:
            ident["app_ver"] = new_av
            changed = True
    return ident, changed


def free_port(lo=19222, hi=19999):
    for _ in range(50):
        port = random.randint(lo, hi)
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("no free debug port")


# ── Profile loading (reads the GUI's profile store) ──────────────────────
def load_profile(pid):
    gui_dir = os.path.join(ANTIBROWSER_DIR, "gui")
    sys.path.insert(0, gui_dir)
    import profiles as pm
    return pm.get_profile(pid)


# ── Fingerprint JS bundle ────────────────────────────────────────────────
def _runtime_identity(ident):
    """JSON-safe identity (dari GUI/API) -> runtime dict."""
    d = dict(ident or {})
    if isinstance(d.get("vp"), list):
        d["vp"] = tuple(d["vp"])
    return d


def _profile_seed(profile):
    """Seed STABIL per profil untuk canvas/audio noise (P0#3, AUDIT 2026-11-04).

    Sebelumnya seed = random per launch -> canvas hash beda tiap sesi =
    "device baru tiap sesi" (tell longitudinal). Sekarang seed = hash dari
    profile id -> noise konsisten per profil, beda antar profil.
    """
    import hashlib
    pid = str(profile.get("id") or profile.get("name") or "default")
    try:
        return int(hashlib.md5(pid.encode()).hexdigest()[:8], 16)
    except Exception:
        return 123456789


def _consistent_fallback_identity(profile):
    """Generate identitas KONSISTEN untuk profil tanpa identity tersimpan.

    AUDIT 2026-11-04: sebelumnya pakai new_identity() (generator lama) yang
    bisa hasilkan kombinasi ngaco (Apple GPU + platform Win32). Sekarang pakai
    generate_random() dengan OS dari setting profil.
    """
    fp = profile.get("fingerprint", {}) or {}
    try:
        import sys as _sys, os as _os
        _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                         "..", "gui"))
        from fingerprint_gen import generate_random
        if fp.get("mobile"):
            # AUDIT 2026-11-04: hormati platform ios (sebelumnya selalu android)
            os_name = (fp.get("platform") or "android").lower()
            if os_name not in ("android", "ios"):
                os_name = "android"
        else:
            os_name = (fp.get("platform") or "windows").lower()
            if os_name not in ("windows", "macos", "linux", "android"):
                os_name = "windows"
        return generate_random(
            os_name,
            timezone=fp.get("timezone") or "Asia/Jakarta",
            locale=fp.get("locale"),
        )
    except Exception:
        from fingerprint import new_identity
        return new_identity()


def build_fingerprint_js(profile, identity_override=None, chrome_path=None):
    from fingerprint import spoof_js, spoof_js_extra
    from fingerprint.mobile import mobile_spoof_js_from_dict
    from fingerprint.mobile_devices import mobile_gpu_spoof_js
    fp = profile.get("fingerprint", {})
    features = {k: v for k, v in fp.get("features", {}).items() if v}
    # Prioritas: override (test sekali) > identity tersimpan > generate baru
    stored = identity_override or fp.get("identity")
    ident = _runtime_identity(stored) if stored else _consistent_fallback_identity(profile)
    # FIX 1 (RND 2026-11-04): sinkronkan chrome_ver dengan binary REAL.
    # Tanpa ini: identitas klaim "155.0.0.0" tapi Chromium jalan 156.x =
    # mismatch yang bisa dikorelasikan detector via TLS/JA3 atau feature check.
    # Hanya untuk desktop (mobile pakai UA sendiri, bukan binary version).
    # F3-4: chrome_path = binary kernel pilihan profil (bila ada) — versi
    # identitas harus mengikuti binary YANG JALAN, bukan Chromium sistem.
    if not ident.get("is_mobile"):
        try:
            real = None
            if chrome_path:
                real = get_real_chrome_version(chrome_path)
            sync_identity_chrome_version(ident, real)
        except Exception:
            pass
    # P-08 (bonus): isi geo_lat/geo_lon dari timezone bila identity tidak
    # punya (identitas mobile + manual lama). Tanpa ini network.py jatuh ke
    # default Singapore (1.3521, 103.8198) walau timezone bilang Tokyo.
    if ident.get("geo_lat") is None or ident.get("geo_lon") is None:
        try:
            from fingerprint.geo import _COUNTRY_GEO
            _tz = ident.get("timezone") or fp.get("timezone") or "Asia/Jakarta"
            for _cc, (_ctz, _cloc, _lat, _lon) in _COUNTRY_GEO.items():
                if _ctz == _tz:
                    ident.setdefault("geo_lat", _lat)
                    ident.setdefault("geo_lon", _lon)
                    break
        except Exception:
            pass
    tz = fp.get("timezone", "Asia/Jakarta") if not stored else ident.get("timezone", "Asia/Jakarta")
    loc = fp.get("locale") if not stored else ident.get("locale")
    if ident.get("is_mobile"):
        js = mobile_spoof_js_from_dict(ident, timezone=tz, locale=loc)
        try:
            js += "\n" + mobile_gpu_spoof_js(ident.get("chipset", ""))
        except Exception:
            pass
    else:
        # P0#3: seed stabil dari profile id (bukan random per launch)
        js = spoof_js(ident, timezone=tz, locale=loc, features=features,
                      seed=_profile_seed(profile))
        try:
            js += "\n" + spoof_js_extra(features if features else None)
        except Exception:
            pass
    # P-03 (2026-11-07): NO document.title prefix. The old code prepended
    # '[StealthXGM] <profile>' to every page title via MutationObserver —
    # readable by any site's JS, leaking both the tool name and the profile
    # name. Window identity belongs in StealthXGM's own UI (GUI / OS window
    # title / brand new-tab page), never inside the web page. Do NOT re-add.
    # P-17: once-guard — daemon (CDP add_init_script) + extension MV3
    # (content script world=MAIN) menyuntik JS YANG SAMA ke realm yang
    # sama di mode headful; tanpa guard, JS jalan dua kali per dokumen
    # (double-wrap canvas/getContext, dll). Guard pakai Symbol global
    # (bukan properti string di window — tidak muncul di Object.keys /
    # for-in / JSON) dan didefinisikan non-enumerable. Guard reset
    # sendiri per dokumen (realm baru tiap dokumen/frame) — tiap dokumen
    # tetap di-inject tepat satu kali. Seluruh JS sudah berupa IIFE
    # tanpa top-level return/await, jadi bungkus luar ini aman.
    js = (
        "(() => {\n"
        "  const _sxg = Symbol.for(\"sxg\");\n"
        "  if (globalThis[_sxg]) return;\n"
        "  Object.defineProperty(globalThis, _sxg,\n"
        "    {value: 1, configurable: true});\n"
        + js +
        "\n})();\n"
    )
    return js, ident


# ── Proxy resolution ─────────────────────────────────────────────────────
# GUI proxy types: sticky | http | socks5 | warp | none
STICKY_PROXY = "http://127.0.0.1:18080"   # proxy-bot (DataImpulse)
WARP_PROXY = "socks5://127.0.0.1:40000"    # Cloudflare WARP fallback
WARP_HOST, WARP_PORT = "127.0.0.1", 40000


def _parse_proxy_host_port(proxy_server):
    """Extract (host, port) from a proxy URL like http://user:pass@host:port."""
    from urllib.parse import urlparse
    try:
        u = urlparse(proxy_server)
        if u.hostname and u.port:
            return u.hostname, u.port
    except Exception:
        pass
    return None, None


def _tcp_alive(host, port, timeout=3):
    """Quick liveness check: can we open a TCP connection to the proxy?"""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except OSError:
        return False


def _resolve_primary_proxy(profile):
    """Original proxy resolution (pool-based, backward compatible).

    Return (proxy_server, note, auth). P-09: proxy_server TIDAK PERNAH
    mengandung kredensial; auth = (user, pass) atau None — kredensial
    dijawab extension auth, bukan ditempel di URL/argv.
    """
    px = profile.get("proxy", {}) or {}
    # NEW: pool-based resolution (backward compatible — old profiles without
    # pool_id fall through to the legacy type-based logic below).
    pool_id = px.get("pool_id")
    if pool_id:
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "..", "gui"))
            import proxy_pools as pp
            pool = pp.get_pool(pool_id)
            if pool and pool.get("active"):
                server, note = pp.pool_to_proxy_server(pool)
                return server, note, pp.pool_proxy_auth(pool)
            # pool missing or disabled -> fall through to legacy type logic
        except Exception:
            pass
    ptype = (px.get("type") or "none").lower()
    if ptype == "sticky":
        return STICKY_PROXY, "sticky -> 127.0.0.1:18080", None
    if ptype == "warp":
        return WARP_PROXY, "warp -> 127.0.0.1:40000", None
    if ptype == "env":
        return "env", "inherit environment proxy vars", None
    if ptype in ("http", "https", "socks5"):
        host, port = px.get("host", ""), px.get("port", "")
        if not host or not port:
            return None, f"{ptype} configured but host/port empty -> no proxy", None
        scheme = "socks5" if ptype == "socks5" else "http"
        # P-09: legacy profile menyimpan user/pass tapi kode lama MEMBUANGNYA
        # (URL tanpa kredensial) — sekarang diteruskan sebagai auth terpisah.
        auth = None
        user = (px.get("user") or "").strip()
        if user:
            auth = (user, px.get("pass") or "")
        note = f"{ptype} {host}:{port}" + (" (auth)" if auth else "")
        return f"{scheme}://{host}:{port}", note, auth
    return None, "no proxy", None


def resolve_proxy_with_auth(profile):
    """Return (proxy_server, note, auth) dengan WARP fallback.

    auth = (user, pass) atau None. Bila fallback ke WARP, auth=None
    (WARP tanpa auth). proxy_server selalu tanpa kredensial (P-09)."""
    proxy_server, note, auth = _resolve_primary_proxy(profile)

    if not profile.get("warp_fallback"):
        return proxy_server, note, auth
    # Nothing to fall back from: direct / env / already WARP
    if not proxy_server or proxy_server == "env" or proxy_server == WARP_PROXY:
        return proxy_server, note, auth

    host, port = _parse_proxy_host_port(proxy_server)
    if host and port and _tcp_alive(host, port, timeout=3):
        return proxy_server, note, auth  # primary healthy

    # Primary unreachable -> try WARP
    if _tcp_alive(WARP_HOST, WARP_PORT, timeout=3):
        return WARP_PROXY, (
            f"primary {proxy_server} unreachable -> WARP fallback "
            f"({WARP_HOST}:{WARP_PORT})"
        ), None
    return proxy_server, note + " [warp_fallback ON but WARP down — keeping primary]", auth


def resolve_proxy(profile):
    """Resolve proxy for a profile, with real WARP fallback.

    Backward-compat wrapper atas resolve_proxy_with_auth — return
    (proxy_server, note) saja. Pemanggil yang butuh kredensial pakai
    resolve_proxy_with_auth().
    """
    proxy_server, note, _auth = resolve_proxy_with_auth(profile)
    return proxy_server, note


# ── Launch args ──────────────────────────────────────────────────────────
def resolve_user_extensions(profile):
    """Unpacked extension dirs (ENABLED) milik profil, dari extension_manager."""
    try:
        gui_dir = os.path.join(ANTIBROWSER_DIR, "gui")
        if gui_dir not in sys.path:
            sys.path.insert(0, gui_dir)
        import extension_manager as em
        return em.resolve_extension_paths(profile["id"])
    except Exception:
        return []


def _strip_proxy_creds(proxy_server):
    """P-09 defense-in-depth: buang userinfo (user:pass@) dari URL proxy
    bila ada yang lolos ke sini — argv Chromium tidak boleh mengandung
    kredensial dalam bentuk apa pun. Kredensial proxy ditangani extension
    auth (resolve_proxy_with_auth), bukan URL."""
    if not proxy_server or "@" not in proxy_server:
        return proxy_server
    from urllib.parse import urlparse, urlunparse
    try:
        u = urlparse(proxy_server)
        if u.username is None:
            return proxy_server
        netloc = u.hostname or ""
        if u.port:
            netloc += f":{u.port}"
        return urlunparse((u.scheme, netloc, u.path, u.params,
                           u.query, u.fragment))
    except Exception:
        return proxy_server


def build_launch_args(profile, debug_port, chrome_path, headless, ext_path=None,
                       user_ext_paths=None, proxy_resolved=None):
    user_data_dir = os.path.join(BROWSER_PROFILES_DIR, profile["id"])
    os.makedirs(user_data_dir, exist_ok=True)
    if proxy_resolved is not None:
        proxy_server, proxy_note = proxy_resolved
    else:
        proxy_server, proxy_note = resolve_proxy(profile)
    proxy_server = _strip_proxy_creds(proxy_server)

    args = [
        chrome_path,
        f"--user-data-dir={user_data_dir}",
        f"--remote-debugging-port={debug_port}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        # AdsPower invariant (RND): prevent Chromium stalling when occluded
        "--disable-backgrounding-occluded-windows",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        # hide automation flag at blink level (JS spoof is the main layer)
        # F11 (2026-11-08): WebAudioRustFft appended — Chrome 152+ switched
        # the WebAudio FFT backend PFFFT -> RustFFT; CreepJS KnownAudio holds
        # PFFFT-era sums, so genuine 152+/159 output (sum 124.04347776696522)
        # shows 9 bold digits. On a CfT 152 kernel this flag restores the
        # PFFFT path (verified independently in F11: sum 124.04347527516074,
        # 0 bold digits, buffer byte-identical to 120/131/142/151). No-op on
        # 159 (legacy FFT path removed). Real rendering-path change, all
        # sites. Kernel 152 became the DEFAULT on 2026-11-09 (Gil's call
        # 2026-11-08 21:47, applied 02:50 WIB) — the trade-off note in
        # FIX-LOG-F11 §3 (default stays 159) is superseded.
        # See FIX-LOG-F11-BASE-LEAKS-2026-11-08.md §3.
        "--disable-blink-features=AutomationControlled,WebAudioRustFft",
        # F6 (2026-11-08): WebGL mati total di kernel CfT 159 tanpa flag ini
        # (getContext('webgl') = null, headless maupun headful; Chromium 156
        # WebGL jalan). --enable-unsafe-swiftshader mengaktifkan software
        # GL (SwiftShader) di mesin tanpa GPU — perbaikan umum untuk mesin
        # tanpa GPU, bukan khusus detector. Spoof WebGL (vendor/renderer)
        # tetap berlaku di atas SwiftShader (getParameter di-spoof).
        # F6-rev (2026-11-08): --enable-unsafe-swiftshader SAJA tidak cukup
        # di HEADFUL (xvfb): getContext('webgl') tetap null — headful Chrome
        # coba GL via display X dan tidak fallback ke SwiftShader. Paksa
        # ANGLE ke backend SwiftShader supaya WebGL jalan headful juga.
        "--enable-unsafe-swiftshader",
        "--use-gl=angle",
        "--use-angle=swiftshader",
        # F9 (2026-11-08): paksa raster CPU Skia untuk canvas 2D.
        # Terukur (tests/f9_canvas_probe.py): canvas 2D terakselerasi GPU di
        # SwiftShader menghasilkan piksel AA arc di luar allowlist
        # KnownImageData.BLINK CreepJS (2x2 = ...128...191...000) — 9th value;
        # raster CPU menghasilkan nilai yang dilaporkan Chrome asli
        # (...192...244...53, entri BLINK #8). Perbaikan jalur render nyata,
        # berlaku untuk semua situs; jalur WebGL tidak disentuh (WebGL tetap
        # hidup via --use-gl=angle --use-angle=swiftshader di atas).
        "--disable-accelerated-2d-canvas",
        # required when running as root (VM); patchright adds this automatically too
        "--no-sandbox",
        # keep localhost CDP reachable when a proxy is set
        "--proxy-bypass-list=localhost,127.0.0.1",
    ]
    if proxy_server == "env":
        pass  # inherit HTTP_PROXY/HTTPS_PROXY from environment
    elif proxy_server:
        args.append(f"--proxy-server={proxy_server}")
    else:
        # explicit direct: env HTTP_PROXY/HTTPS_PROXY would otherwise leak in
        args.append("--no-proxy-server")
    exts = []
    if ext_path:
        exts.append(ext_path)
    for p in (user_ext_paths or []):
        if p and os.path.isdir(p) and p not in exts:
            exts.append(p)
    if exts:
        # persistent fingerprint extension (MV3, world=MAIN, document_start)
        # + user extensions, comma-separated (RND docs/RND-EXTENSIONS.md)
        joined = ",".join(exts)
        args.append(f"--load-extension={joined}")
        args.append(f"--disable-extensions-except={joined}")
    if headless:
        args.append("--headless=new")
    return args, user_data_dir, proxy_note


def wait_debug_port(user_data_dir, port, timeout=25):
    """Wait until Chromium's remote debugging endpoint responds.

    Primary: HTTP GET http://127.0.0.1:port/json/version
    Fallback: DevToolsActivePort file in user-data-dir (not written in headless=new).
    """
    import urllib.request
    start = time.time()
    url = f"http://127.0.0.1:{port}/json/version"
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return port
        except Exception:
            pass
        # fallback: file written by headful mode
        port_file = os.path.join(user_data_dir, "DevToolsActivePort")
        if os.path.exists(port_file):
            try:
                with open(port_file) as f:
                    return int(f.read().strip().splitlines()[0])
            except (ValueError, IndexError):
                pass
        time.sleep(0.3)
    raise RuntimeError("Chromium did not open debug port in time")


# ── Cookie sanitization (Playwright add_cookies format) ──────────────────
_COOKIE_KEYS = ("name", "value", "domain", "path", "expires",
                "httpOnly", "secure", "sameSite")
_SAMESITE_OK = {"Strict", "Lax", "None"}


def validate_cookies(cookies):
    """F3-3: validasi per-cookie (dipakai API v2 /browser-profile/cookies).

    Return {"accepted": [...], "rejected": [{"index","name","reason"}],
            "notes": [{"index","name","note"}]}. Aturan sama dengan
    sanitize_cookies, tapi tiap keputusan dilaporkan — bukan dibuang diam.
    Cookie DITOLAK hanya bila: bukan dict, tanpa nama, atau tanpa value.
    Field buruk lain (expires bukan angka, sameSite tak dikenal) dihapus
    dari cookie dengan catatan, cookie-nya tetap diterima."""
    accepted, rejected, notes = [], [], []
    for i, c in enumerate(cookies or []):
        if not isinstance(c, dict):
            rejected.append({"index": i, "name": None,
                             "reason": "bukan object"})
            continue
        name, value = c.get("name"), c.get("value")
        if not name:
            rejected.append({"index": i, "name": None,
                             "reason": "tanpa name"})
            continue
        if value is None:
            rejected.append({"index": i, "name": str(name),
                             "reason": "tanpa value"})
            continue
        nc = {"name": str(name), "value": str(value)}
        for k in ("domain", "path"):
            if c.get(k):
                nc[k] = str(c[k])
        if "expires" in c:
            if isinstance(c.get("expires"), (int, float)) and c["expires"] > 0:
                nc["expires"] = float(c["expires"])
            else:
                notes.append({"index": i, "name": str(name),
                              "note": "expires bukan angka >0 — dihapus"})
        for k in ("httpOnly", "secure"):
            if k in c:
                nc[k] = bool(c[k])
        ss = c.get("sameSite")
        if ss is not None:
            if ss in _SAMESITE_OK:
                nc["sameSite"] = ss
            else:
                notes.append({"index": i, "name": str(name),
                              "note": f"sameSite {ss!r} tidak dikenal — dihapus"})
        accepted.append(nc)
    return {"accepted": accepted, "rejected": rejected, "notes": notes}


def sanitize_cookies(cookies):
    """Keep only valid Playwright cookie fields; drop malformed entries."""
    return validate_cookies(cookies)["accepted"]


# ── Session registry (shared between CLI and GUI processes) ──────────────
def _read_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _write_sessions(s):
    tmp = SESSIONS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=1)
    os.replace(tmp, SESSIONS_FILE)


def get_launched_identity(pid):
    """P-18: identity yang disuntik pada launch terakhir profil ini
    (browser_profiles/<pid>/identity.json). Return dict atau None bila
    belum pernah launch sejak P-18 / file hilang. JANGAN ganti dengan
    build_fingerprint_js() ulang — identitas random per panggilan."""
    try:
        with open(os.path.join(BROWSER_PROFILES_DIR, pid,
                               "identity.json")) as f:
            ident = json.load(f)
        return ident if isinstance(ident, dict) else None
    except Exception:
        return None


def freeze_identity(profile, ident):
    """F3-1 (P2): BEKUKAN identity ke profil saat launch pertama.

    Profil tanpa identity tersimpan sebelumnya mendapat identitas RANDOM
    tiap launch (temuan P-18) — terlihat sebagai device berbeda tiap sesi
    (longitudinal tell) dan membuat fingerprint-check membandingkan apel
    vs jeruk. Fungsi ini menyimpan identitas yang BARU SAJA disuntik
    (ident dari build_fingerprint_js, sudah sinkron chrome_ver) ke
    profiles.json, sehingga launch berikutnya memakai identitas yang SAMA.

    Aturan: hanya bila profil belum punya fingerprint.identity tersimpan
    (baca ulang dari store — proses lain mungkin sudah membekukan duluan)
    dan ident valid. identity_override (test sekali-pakai) TIDAK PERNAH
    dibekukan — pemanggil yang menjamin itu. Return True bila disimpan,
    False bila sudah ada / gagal (gagal simpan tidak menggagalkan launch).
    """
    if not isinstance(profile, dict) or not isinstance(ident, dict):
        return False
    if (profile.get("fingerprint") or {}).get("identity"):
        return False
    pid = profile.get("id")
    if not pid:
        return False
    try:
        gui_dir = os.path.join(ANTIBROWSER_DIR, "gui")
        if gui_dir not in sys.path:
            sys.path.insert(0, gui_dir)
        import profiles as pm
        from fingerprint_gen import to_jsonable
        cur = pm.get_profile(pid)
        if not cur:
            return False
        if (cur.get("fingerprint") or {}).get("identity"):
            return False
        pm.update_profile(pid, {"fingerprint": {"identity": to_jsonable(ident)}})
        return True
    except Exception:
        return False


def list_running():
    prune_stale_sessions()
    sessions = _read_sessions()
    # P-10: watchdog — anotasi tiap sesi hidup dengan status injeksi;
    # daemon mati + browser hidup -> coba re-inject (throttled di dalam
    # ensure_injection). Anotasi hanya di dict yang dikembalikan (tidak
    # ditulis ke file).
    for pid, sess in sessions.items():
        h = daemon_health(pid, sess)
        sess["daemon_alive"] = h["daemon_alive"]
        sess["injection_ok"] = h["injection_ok"]
        if h["browser_alive"] and not h["daemon_alive"]:
            r = ensure_injection(pid)
            if r.get("ok"):
                sess["daemon_alive"] = True
                sess["injection_ok"] = True
                sess["daemon_pid"] = r.get("daemon_pid", sess.get("daemon_pid"))
                sess["injection_recovered"] = True
    return sessions


def _daemon_log_path(user_data_dir):
    return os.path.join(user_data_dir, "injector_daemon.log")


def _read_log_tail(user_data_dir, lines=20):
    """Ekor log daemon (P-10) — diagnosis tanpa buka file."""
    try:
        with open(_daemon_log_path(user_data_dir)) as f:
            all_lines = f.read().splitlines()
        return "\n".join(all_lines[-lines:])
    except OSError:
        return ""


def _spawn_injector_daemon(user_data_dir, port, js_file, ready_file,
                           cookies_file, timeout=20):
    """Spawn injector daemon + tunggu ready_file. Return (proc, log_path).

    P-10: stdout/stderr daemon ke injector_daemon.log (BUKAN DEVNULL —
    log crash daemon sebelumnya hilang total). Raise RuntimeError bila
    daemon mati/tidak ready — pesan menyertakan ekor log supaya
    penyebabnya kebaca. TIDAK menyentuh browser (pemanggil yang
    memutuskan nasib browser bila spawn gagal)."""
    if os.path.exists(ready_file):
        os.remove(ready_file)
    log_path = _daemon_log_path(user_data_dir)
    lf = open(log_path, "a")
    try:
        daemon = subprocess.Popen(
            [sys.executable, os.path.join(BASE_DIR, "injector_daemon.py"),
             "--port", str(port), "--js-file", js_file,
             "--ready-file", ready_file, "--cookies-file", cookies_file],
            stdout=lf, stderr=lf, start_new_session=True)
    finally:
        lf.close()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(ready_file):
            return daemon, log_path
        if daemon.poll() is not None:
            tail = _read_log_tail(user_data_dir)
            raise RuntimeError(
                f"injector daemon died on startup (exit {daemon.returncode})"
                + (f" — log tail:\n{tail}" if tail else ""))
        time.sleep(0.2)
    daemon.terminate()
    raise RuntimeError("injector daemon did not become ready "
                       f"(timeout {timeout}s)")


def _worker_injector_log_path(user_data_dir):
    return os.path.join(user_data_dir, "worker_injector.log")


def _spawn_worker_injector(user_data_dir, port, js_file, ready_file,
                           timeout=20):
    """Spawn worker injector daemon (Node, worker_injector.js) + tunggu
    ready_file. Return (proc, log_path). F6 (2026-11-08): inject spoof
    ke worker (dedicated/shared/service) via CDP setAutoAttach +
    waitForDebuggerOnStart — Playwright add_init_script tidak berlaku
    untuk worker. Node dipakai karena punya WebSocket global (tanpa
    dependency); Python di VM ini tidak punya websockets/websocket-client.
    Gagal spawn = launch tetap jalan tapi worker TIDAK di-spoof (dicatat
    di sesi sebagai worker_daemon_pid=None + worker_injector_error) —
    JANGAN gagalkan launch karenanya (worker spoof adalah lapisan
    tambahan, bukan syarat browser jalan)."""
    if os.path.exists(ready_file):
        os.remove(ready_file)
    log_path = _worker_injector_log_path(user_data_dir)
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node tidak ketemu (butuh worker_injector.js)")
    lf = open(log_path, "a")
    try:
        proc = subprocess.Popen(
            [node, os.path.join(BASE_DIR, "worker_injector.js"),
             "--port", str(port), "--js-file", js_file,
             "--ready-file", ready_file],
            stdout=lf, stderr=lf, start_new_session=True)
    finally:
        lf.close()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(ready_file):
            return proc, log_path
        if proc.poll() is not None:
            tail = ""
            try:
                with open(log_path) as f:
                    tail = "\n".join(f.read().splitlines()[-20:])
            except OSError:
                pass
            raise RuntimeError(
                f"worker injector died on startup (exit {proc.returncode})"
                + (f" — log tail:\n{tail}" if tail else ""))
        time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("worker injector did not become ready "
                       f"(timeout {timeout}s)")


def daemon_health(pid, sess=None):
    """P-10: status injeksi satu profil. Return dict: daemon_alive,
    browser_alive, injection_ok (ketiganya benar = injeksi jalan),
    daemon_pid, log_tail (ekor log daemon)."""
    if sess is None:
        sess = _read_sessions().get(pid)
    if not sess:
        return {"daemon_alive": False, "browser_alive": False,
                "injection_ok": False, "daemon_pid": None, "log_tail": ""}
    dpid = sess.get("daemon_pid")
    dalive = _pid_alive(dpid)
    balive = _session_alive(sess)
    udd = sess.get("user_data_dir") or ""
    ready = bool(udd) and os.path.exists(
        os.path.join(udd, "injector_ready.json"))
    return {"daemon_alive": dalive, "browser_alive": balive,
            "injection_ok": bool(dalive and balive and ready),
            "daemon_pid": dpid,
            "log_tail": _read_log_tail(udd) if udd else ""}


_LAST_REINJECT_ATTEMPT = {}


def ensure_injection(pid, retry_interval=60):
    """P-10 watchdog (re-inject): bila browser hidup tapi daemon mati,
    spawn ulang daemon dengan JS/cookies yang sama dari launch.
    Return dict. Throttle: percobaan gagal tidak diulang <60 detik
    (supaya status check yang berulang tidak stall berkali-kali)."""
    sessions = _read_sessions()
    sess = sessions.get(pid)
    if not sess:
        return {"ok": False, "reason": "no_session"}
    if not _session_alive(sess):
        return {"ok": False, "reason": "browser_dead"}
    if _pid_alive(sess.get("daemon_pid")):
        # F6: daemon utama hidup — tetap cek worker injector (bisa mati
        # sendiri sementara daemon utama hidup).
        _udd = sess.get("user_data_dir") or ""
        _port = sess.get("debug_port")
        if _udd and _port:
            _ensure_worker_injector(pid, _udd, _port)
        return {"ok": True, "already": True}
    now = time.monotonic()
    last = _LAST_REINJECT_ATTEMPT.get(pid, 0)
    if now - last < retry_interval:
        return {"ok": False, "reason": "throttled",
                "retry_in": round(retry_interval - (now - last), 1)}
    _LAST_REINJECT_ATTEMPT[pid] = now
    udd = sess.get("user_data_dir") or ""
    port = sess.get("debug_port")
    # P-16 (bug interaksi P-10/P-12): sesi tanpa user_data_dir/port
    # (mis. sesi palsu test P-12) TIDAK BOLEH coba respawn — dulu spawn
    # daemon dengan path relatif di CWD + menulis injector_daemon.log liar.
    if not udd or not port:
        return {"ok": False, "reason": "no_user_data_dir"}
    js_file = os.path.join(udd, "fingerprint_inject.js")
    cookies_file = os.path.join(udd, "profile_cookies.json")
    ready_file = os.path.join(udd, "injector_ready.json")
    try:
        daemon, _log = _spawn_injector_daemon(
            udd, port, js_file, ready_file, cookies_file)
    except Exception as e:
        return {"ok": False, "reason": f"respawn_failed: {e}"}
    with _json_store().locked(SESSIONS_FILE):
        fresh = _read_sessions()
        if pid in fresh:
            fresh[pid]["daemon_pid"] = daemon.pid
            _write_sessions(fresh)
    if pid in _PROCS:
        # F6: _PROCS 3-tuple (proc, daemon, worker_daemon); sesi lama
        # (2-tuple) tetap ditangani.
        _entry = _PROCS[pid]
        old_proc = _entry[0]
        _PROCS[pid] = (old_proc, daemon, _entry[2] if len(_entry) > 2 else None)
    # F6: respawn worker injector juga bila mati (browser hidup, worker
    # JS masih ada). Gagal respawn = dicatat, bukan error fatal.
    _ensure_worker_injector(pid, udd, port)
    return {"ok": True, "re_injected": True, "daemon_pid": daemon.pid}


def _ensure_worker_injector(pid, udd, port):
    """F6: respawn worker injector daemon bila mati (browser masih hidup
    + worker_inject.js ada). Dipanggil dari ensure_injection. Return
    True bila worker daemon hidup/berhasil di-respawn, False bila tidak
    (dicatat di sesi, bukan error fatal)."""
    try:
        sessions = _read_sessions()
        sess = sessions.get(pid)
        if not sess:
            return False
        if _pid_alive(sess.get("worker_daemon_pid")):
            return True
        worker_js_file = os.path.join(udd, "worker_inject.js")
        if not os.path.exists(worker_js_file):
            return False
        worker_ready_file = os.path.join(udd, "worker_ready.json")
        worker_daemon = None
        for _attempt in range(2):
            try:
                worker_daemon, _wlog = _spawn_worker_injector(
                    udd, port, worker_js_file, worker_ready_file)
                break
            except RuntimeError:
                if _attempt == 0:
                    time.sleep(1)
        if worker_daemon is None:
            return False
        with _json_store().locked(SESSIONS_FILE):
            fresh = _read_sessions()
            if pid in fresh:
                fresh[pid]["worker_daemon_pid"] = worker_daemon.pid
                fresh[pid]["worker_injector_error"] = None
                _write_sessions(fresh)
        if pid in _PROCS:
            _entry = _PROCS[pid]
            _PROCS[pid] = (_entry[0], _entry[1], worker_daemon)
        return True
    except Exception:
        return False


def sync_profile_statuses(pm):
    """P-12: rekonsiliasi field status di profiles.json dari registry hidup.
    Dipanggil saat startup GUI/Local API (setelah prune) supaya status basi
    pasca-crash (profil 'running' padahal browser sudah mati) tidak
    tertinggal selamanya di file. Endpoint list/status TIDAK memakai field
    ini — mereka baca registry langsung — sync ini hanya merapikan file.
    pm = modul profiles (diinjeksikan, bukan diimpor — hindari import cycle).
    Return set id yang sedang running."""
    live = set(list_running())
    for p in pm.list_profiles(include_deleted=True):
        want = "running" if p["id"] in live else "idle"
        if p.get("status", "idle") != want:
            pm.update_profile(p["id"], {"status": want})
    return live


def _pid_alive(pid):
    """True jika PID masih hidup (os.kill sinyal 0, tanpa membunuh).

    P-10: proses ZOMBIE (anak yang sudah exit tapi belum di-reap parent)
    TIDAK dihitung hidup — kill 0 sukses untuk zombie, jadi cek juga
    /proc/<pid>/stat state != 'Z'. Tanpa ini, daemon yang sudah keluar
    (mis. watchdog P-10 mendeteksi browser mati) tetap dilaporkan hidup
    sampai parent-nya memanggil wait()/poll()."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # ada, tapi bukan milik kita
    except OSError:
        return False
    # zombie check (Linux): field state di /proc/<pid>/stat.
    # Format: "<pid> (<comm>) <state> ..." — comm bisa berisi spasi/
    # kurung, jadi potong dari ')' terakhir.
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            state = f.read().rsplit(b")", 1)[-1].split()[0]
        if state == b"Z":
            return False
    except OSError:
        pass
    return True


def _debug_port_alive(port, timeout=2):
    """True jika debug port menjawab /json/version ala Chromium."""
    import urllib.request
    try:
        port = int(port)
    except (TypeError, ValueError):
        return False
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/version",
                timeout=timeout) as r:
            if r.status != 200:
                return False
            body = r.read(4096).decode("utf-8", "replace")
            return '"Browser"' in body
    except Exception:
        return False


def _session_alive(sess):
    """Sesi hidup = browser PID hidup DAN debug port menjawab (P-06).

    PID saja tidak cukup (PID bisa dipakai ulang proses lain); port saja
    tidak cukup (port bisa dipakai ulang). Keduanya harus benar."""
    if not isinstance(sess, dict):
        return False
    return _pid_alive(sess.get("browser_pid")) and \
        _debug_port_alive(sess.get("debug_port"))


def prune_stale_sessions():
    """Hapus entri sessions.json yang browser-nya sudah mati (crash,
    kill paksa, VM restart). Return jumlah entri yang dihapus.

    P-07: liveness dicek dulu tanpa lock, lalu pop+write di bawah lock
    DENGAN verifikasi ulang — profil yang sempat mati lalu di-launch
    ulang di antara dua langkah tidak boleh ikut terhapus."""
    sessions = _read_sessions()
    stale = [pid for pid, s in sessions.items() if not _session_alive(s)]
    if not stale:
        return 0
    with _json_store().locked(SESSIONS_FILE):
        fresh = _read_sessions()
        gone = [pid for pid in stale
                if pid in fresh and not _session_alive(fresh[pid])]
        for pid in gone:
            fresh.pop(pid, None)
        if gone:
            _write_sessions(fresh)
        return len(gone)


# ── FIX 2 (RND 2026-11-04): Behavioral layer — human-like interaction ────
# Re-export dari fingerprint.behavioral_human agar automation cukup:
#   from launcher import human_move, human_type, human_scroll, human_click
# Dua mode: _page (Playwright sync Page) dan _cdp (CDP session callable).
try:
    from fingerprint.behavioral_human import (
        human_move_page, human_click_page, human_type_page, human_scroll_page,
        human_move_cdp, human_click_cdp, human_helpers_js,
    )

    def human_move(page, x1, y1, x2, y2):
        """Gerak mouse manusiawi di Playwright page. Return jumlah step."""
        return human_move_page(page, x1, y1, x2, y2)

    def human_click(page, x, y, button="left"):
        """Move natural + klik di Playwright page."""
        return human_click_page(page, x, y, button)

    def human_type(page, text, wpm=None):
        """Ketik dengan rhythm manusia di Playwright page."""
        return human_type_page(page, text, wpm)

    def human_scroll(page, delta_y, steps=None):
        """Scroll dengan momentum di Playwright page."""
        return human_scroll_page(page, delta_y, steps)

    def human_move_cdp_send(cdp_send, x1, y1, x2, y2):
        """Gerak mouse via CDP session langsung."""
        return human_move_cdp(cdp_send, x1, y1, x2, y2)

    def human_click_cdp_send(cdp_send, x, y, button="left"):
        """Klik via CDP session langsung."""
        return human_click_cdp(cdp_send, x, y, button)
except ImportError:
    # behavioral_human tidak ada -> fungsi jadi no-op aman (backward compat)
    def _noop(*a, **k):
        return 0
    human_move = human_click = human_type = human_scroll = _noop
    human_move_cdp_send = human_click_cdp_send = _noop
    def human_helpers_js():
        return ""


# ── Launch / stop ────────────────────────────────────────────────────────
# P-17 — arsitektur injeksi (diputuskan 2026-11-07): DAEMON + EXTENSION.
#   Lapisan 1 (utama, selalu): injector_daemon.py — sesi CDP persisten,
#     add_init_script di default context (jalan di headless + headful).
#   Lapisan 2 (headful saja): extension MV3 build_extension() —
#     content script world=MAIN, document_start (tidak jalan di
#     --headless=new); bertahan bila daemon mati (P-10). Kedua lapisan
#     menyuntik fingerprint_js yang SAMA; once-guard Symbol di
#     build_fingerprint_js() memastikan tiap dokumen dieksekusi tepat
#     satu kali. Fungsi _connect_and_inject() yang lama DIHAPUS di P-17:
#     nol pemanggil, dan komentarnya menyesatkan (mengklaim injeksi via
#     extension padahal yang aktif hanya daemon).


# ── P-07: per-profile launching guard ──────────────────────────────────
# Dua klik "Launch" bersamaan (atau GUI + API yang bersamaan) untuk profil
# yang sama sebelumnya sama-sama lolos cek sessions.json lalu men-start dua
# Chromium di user-data-dir yang sama — profil Chrome korup / tab saling
# rebut. Guard ini: flock non-blocking pada
# browser_profiles/<pid>/.launch.lock, dipegang SELAMA launch berlangsung
# (bukan cuma saat cek). Lock dilepas saat launch selesai/gagal; file
# TIDAK PERNAH dihapus (menghapus file lock merusak mutual exclusion).
def _try_launch_lock(pid):
    """Return fd lock yang dipegang, atau None bila profil sedang
    di-launch oleh proses lain."""
    user_data_dir = os.path.join(BROWSER_PROFILES_DIR, pid)
    os.makedirs(user_data_dir, exist_ok=True)
    fd = os.open(os.path.join(user_data_dir, ".launch.lock"),
                 os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def _release_launch_lock(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def launch_profile(profile, headless=False, url=None, debug_port=None,
                   identity_override=None):
    """Launch Chromium untuk satu profil. Return session dict.

    identity_override: dict identitas sekali-pakai (dari Fingerprint
    Generator "Test di browser") — tidak disimpan ke profil.

    P-07: launch kedua untuk profil yang sama saat launch pertama masih
    berjalan ditolak dengan error 'already_launching' (bukan dua browser
    di satu user-data-dir)."""
    pid = profile["id"]
    lock_fd = _try_launch_lock(pid)
    if lock_fd is None:
        return {"ok": False, "error": "already_launching",
                "profile_id": pid,
                "message": "profil ini sedang di-launch oleh proses lain"}
    try:
        return _launch_profile_inner(
            profile, headless=headless, url=url, debug_port=debug_port,
            identity_override=identity_override)
    finally:
        _release_launch_lock(lock_fd)


def _launch_profile_inner(profile, headless=False, url=None, debug_port=None,
                          identity_override=None):
    """Isi launch_profile — dipanggil hanya setelah launch guard dipegang."""
    pid = profile["id"]
    # P-07: cek sesi hidup + buang entri basi di bawah lock (baca-ubah-tulis
    # atomik — dua proses tidak boleh sama-sama menganggap sesi basi lalu
    # sama-sama launch).
    with _json_store().locked(SESSIONS_FILE):
        sessions = _read_sessions()
        if pid in sessions:
            if _session_alive(sessions[pid]):
                return {"ok": True, "already_running": True, **sessions[pid]}
            # P-06: entri basi (browser mati / crash / VM restart) — hapus
            # lalu lanjut launch normal; jangan jebak user di
            # "already_running".
            sessions.pop(pid, None)
            _write_sessions(sessions)

    # F3-4: kernel per profil — binary kernel pilihan profil / default,
    # fallback ke Chromium sistem. Versi identitas disinkronkan ke binary
    # YANG JALAN (build_fingerprint_js menerima chrome_path).
    chrome = None
    try:
        _this_dir = os.path.dirname(os.path.abspath(__file__))
        if _this_dir not in sys.path:
            sys.path.insert(0, _this_dir)
        from kernels import resolve_kernel_chrome
        chrome = resolve_kernel_chrome(profile)
    except Exception:
        chrome = None
    if not chrome:
        chrome = find_chrome()
    port = debug_port or free_port()
    fingerprint_js, ident = build_fingerprint_js(
        profile, identity_override=identity_override, chrome_path=chrome)
    user_data_dir = os.path.join(BROWSER_PROFILES_DIR, pid)
    os.makedirs(user_data_dir, exist_ok=True)

    # fingerprint JS to a file for the injector daemon
    js_file = os.path.join(user_data_dir, "fingerprint_inject.js")
    with open(js_file, "w") as f:
        f.write(fingerprint_js)

    # F6 (2026-11-08): worker fingerprint JS (worker_inject.js) — spoof
    # untuk dedicated/shared/service worker via CDP (worker_injector.js).
    # Seed SAMA dengan main thread supaya offset teks canvas & noise
    # deterministik identik (paintURI main == paintCpuURI worker).
    # Mobile: tidak ada worker spoof (mobile_spoof_js_from_dict tidak
    # punya padanan worker) — worker daemon tidak di-spawn untuk mobile.
    # tz/loc dihitung seperti di build_fingerprint_js (variabel itu lokal
    # di sana — JANGAN pakai nama tz/loc langsung di sini, NameError).
    worker_js_file = os.path.join(user_data_dir, "worker_inject.js")
    worker_js = None
    if not ident.get("is_mobile"):
        try:
            _fp = profile.get("fingerprint", {})
            _tz = ident.get("timezone") or _fp.get("timezone") or "Asia/Jakarta"
            _loc = ident.get("locale") or _fp.get("locale")
            from fingerprint import spoof_js_worker
            worker_js = spoof_js_worker(ident, timezone=_tz, locale=_loc,
                                        seed=_profile_seed(profile))
            with open(worker_js_file, "w") as f:
                f.write(worker_js)
        except Exception as e:
            worker_js = None
            try:
                with open(os.path.join(user_data_dir, "worker_injector.log"), "a") as lf:
                    lf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [launcher] "
                             f"worker JS gagal dibuat: {e}\n")
            except Exception:
                pass

    # P-18: rekam identity yang BENAR-BENAR disuntik di launch ini
    # (identity.json). WAJIB untuk fingerprint-check live: profil tanpa
    # identity tersimpan mendapat identitas RANDOM tiap build_fingerprint_js()
    # dipanggil — membandingkan live vs hasil build ULANG memberi FAIL
    # palsu (identitas B vs yang disuntik A). Check harus baca file ini.
    # F3-1 (P2): bekukan identity ke profil saat launch pertama — profil
    # tanpa identity tersimpan tidak lagi terlihat sebagai device berbeda
    # tiap sesi. identity_override (sekali-pakai) tidak dibekukan.
    try:
        with open(os.path.join(user_data_dir, "identity.json"), "w") as f:
            json.dump(ident, f, indent=1, default=str)
    except Exception:
        pass
    if identity_override is None:
        freeze_identity(profile, ident)

    # cookies (BUG 4 fix): write sanitized cookies for the injector daemon
    # so they are present in the browser from the very first page load.
    cookies_file = os.path.join(user_data_dir, "profile_cookies.json")
    cookies = sanitize_cookies(profile.get("cookies"))
    with open(cookies_file, "w") as f:
        json.dump(cookies, f)

    # StealthXGM brand extension: custom new tab page with profile info.
    # Resolve proxy once here (also feeds the brand page + avoids double
    # WARP liveness checks inside build_launch_args). P-09: auth diambil
    # terpisah — proxy_server yang diteruskan ke Chromium tanpa kredensial.
    proxy_server, proxy_note, proxy_auth = resolve_proxy_with_auth(profile)
    try:
        _this_dir = os.path.dirname(os.path.abspath(__file__))
        if _this_dir not in sys.path:
            sys.path.insert(0, _this_dir)
        from brand_builder import build_brand_extension
        brand_ext_dir = build_brand_extension(
            user_data_dir, profile, identity=ident, proxy_note=proxy_note)
    except Exception:
        brand_ext_dir = None

    # P-17: lapisan kedua injeksi (headful saja) — extension MV3
    # build_extension menulis fp_ext/{manifest.json, inject.js} dari
    # fingerprint_js yang SAMA (sudah once-guard). MV3 content script
    # tidak jalan di --headless=new, jadi di headless daemon saja yang
    # bekerja. Extension ini yang bertahan bila daemon mati (P-10).
    fp_ext_dir = None
    if not headless:
        try:
            _this_dir = os.path.dirname(os.path.abspath(__file__))
            if _this_dir not in sys.path:
                sys.path.insert(0, _this_dir)
            from extension_builder import build_extension
            fp_ext_dir = build_extension(
                user_data_dir, fingerprint_js, profile.get("name", pid))
        except Exception:
            fp_ext_dir = None

    user_exts = list(resolve_user_extensions(profile))
    if fp_ext_dir:
        user_exts.append(fp_ext_dir)
    # P-09: extension auth proxy — Chromium modern mengabaikan user:pass di
    # --proxy-server dan memunculkan dialog auth yang tak terisi; extension
    # ini menjawab challenge 407 via webRequest.onAuthRequired (hanya
    # untuk proxy, isProxy=true — bukan untuk auth origin server).
    # background.js berisi kredensial (chmod 600) di dalam user-data-dir
    # profil — TIDAK PERNAH di argv. Gagal build = launch tetap jalan
    # (proxy akan 407 — terlihat, bukan diam-diam tanpa proxy).
    if proxy_auth:
        try:
            _this_dir = os.path.dirname(os.path.abspath(__file__))
            if _this_dir not in sys.path:
                sys.path.insert(0, _this_dir)
            from extension_builder import build_proxy_auth_extension
            auth_ext_dir = build_proxy_auth_extension(
                user_data_dir, proxy_auth[0], proxy_auth[1])
            if auth_ext_dir:
                user_exts.append(auth_ext_dir)
        except Exception:
            pass
    args, user_data_dir, proxy_note = build_launch_args(
        profile, port, chrome, headless,
        ext_path=brand_ext_dir,
        user_ext_paths=user_exts,
        proxy_resolved=(proxy_server, proxy_note))

    # headful without a display? auto-wrap with Xvfb (VM has no screen)
    if not headless and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        args = ["xvfb-run", "-a", "-s", "-screen 0 1280x1024x24"] + args

    # F7 (2026-11-08): TZ ASLI — browser harus benar-benar berjalan di
    # timezone identitas. CreepJS membandingkan system Date vs Intl
    # (decryptLocation tahun 1113); VM ini UTC sementara identitas
    # Asia/Jakarta -> Timezone pink. TZ di env proses browser, bukan
    # di-spoof via JS — perbaikan nyata, berlaku untuk semua situs.
    _env = dict(os.environ)
    try:
        _tz = (ident or {}).get("timezone")
        if _tz:
            _env["TZ"] = _tz
    except Exception:
        pass
    # F7B (2026-11-08): LANG ASLI — browser harus benar-benar berjalan di
    # locale identitas. V8 Intl default locale di Linux dibaca dari env
    # (LANG/LC_ALL); --lang TIDAK mengubahnya (terbukti probe f7b:
    # --lang=id-ID -> Intl tetap en-US, LANG=id_ID.UTF-8 -> Intl 'id' +
    # currency "1 Dolar Amerika Serikat" = system -> CreepJS Worker
    # trusty). Tanpa ini Number.toLocaleString(undefined) di worker/main
    # pakai default en-US ("1 US dollar") -> flag Worker. Nilai POSIX
    # dari LOCALE efektif profil (id-ID -> id_ID.UTF-8), derivasi sama
    # seperti spoof_js (locale profil, else timezone -> _TZ_TO_LOCALE).
    try:
        _loc = ident.get("locale") or profile.get("fingerprint", {}).get("locale")
        if not _loc:
            from fingerprint._core import _TZ_TO_LOCALE as _TZ2LOC
            _loc = _TZ2LOC.get((ident or {}).get("timezone") or "Asia/Jakarta", "en-US")
        if _loc:
            _posix = _loc.replace("-", "_") + ".UTF-8"
            _env["LANG"] = _posix
            _env["LC_ALL"] = _posix
    except Exception:
        pass
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=_env)
    try:
        wait_debug_port(user_data_dir, port)
    except RuntimeError:
        proc.terminate()
        raise

    # persistent injector daemon: holds the CDP session open so the
    # addScriptToEvaluateOnNewDocument registration never vanishes.
    # (RND: registrations die with the registering session; patchright's
    # add_init_script is broken — daemon uses real playwright.)
    # P-10: spawn via helper (log ke file, bukan DEVNULL).
    # F3-0: retry 1x bila spawn gagal — suite penuh pernah kena timeout
    # 20 detik sekali (flaky beban mesin, bukan bug kode); percobaan kedua
    # memberi daemon jendela baru tanpa membuang browser yang sudah jalan.
    ready_file = os.path.join(user_data_dir, "injector_ready.json")
    daemon = None
    daemon_retries = 0
    last_err = None
    for _attempt in range(2):
        try:
            daemon, _daemon_log = _spawn_injector_daemon(
                user_data_dir, port, js_file, ready_file, cookies_file)
            break
        except RuntimeError as e:
            last_err = e
            daemon_retries += 1
            if _attempt == 0:
                time.sleep(1)
    if daemon is None:
        proc.terminate()
        raise last_err

    # F6 (2026-11-08): worker injector daemon (Node, CDP setAutoAttach).
    # Gagal spawn = launch TETAP jalan (worker tidak di-spoof) — dicatat
    # di sesi, bukan digagalkan. Retry 1x seperti injector daemon.
    worker_daemon = None
    worker_injector_error = None
    if worker_js is not None:
        worker_ready_file = os.path.join(user_data_dir, "worker_ready.json")
        for _attempt in range(2):
            try:
                worker_daemon, _wlog = _spawn_worker_injector(
                    user_data_dir, port, worker_js_file, worker_ready_file)
                break
            except RuntimeError as e:
                worker_injector_error = str(e)
                if _attempt == 0:
                    time.sleep(1)
        if worker_daemon is None and worker_injector_error:
            try:
                with open(os.path.join(user_data_dir, "worker_injector.log"), "a") as lf:
                    lf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [launcher] "
                             f"worker injector GAGAL: {worker_injector_error}\n")
            except Exception:
                pass

    page = None
    if url:
        # open URL via real playwright (patchright's add_init_script is broken;
        # injection already handled persistently by the extension)
        async def _open():
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                pg = await browser.new_page()
                await pg.goto(url, wait_until="domcontentloaded", timeout=30000)
                return pg
        page = asyncio.new_event_loop().run_until_complete(_open())

    # P-15: jumlah cookie ASLI dari laporan daemon (cookie_inject_report.json
    # + ready.json) — bukan jumlah yang dicoba. Fallback ke jumlah yang
    # dicoba bila laporan tidak ada (daemon lama / gagal tulis).
    cookie_report = {"total": len(cookies), "ok": len(cookies), "failed": 0}
    try:
        with open(os.path.join(user_data_dir, "cookie_inject_report.json")) as f:
            cookie_report = json.load(f)
    except Exception:
        pass
    sess = {
        "user_id": pid,
        "profile_name": profile.get("name", pid),
        "debug_port": port,
        "browser_pid": proc.pid,
        "daemon_pid": daemon.pid,
        "worker_daemon_pid": worker_daemon.pid if worker_daemon else None,
        "worker_injector_error": worker_injector_error,
        "ws_url": f"ws://127.0.0.1:{port}/devtools/browser/",
        "webdriver": f"http://127.0.0.1:{port}",
        "user_data_dir": user_data_dir,
        "proxy": proxy_note,
        "js_length": len(fingerprint_js),
        "cookies_injected": cookie_report.get("ok", 0),
        "cookies_total": cookie_report.get("total", len(cookies)),
        "cookies_failed": cookie_report.get("failed", 0),
        "headless": headless,
        "daemon_retries": daemon_retries,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Active",
    }
    # P-07: catat sesi di bawah lock (baca ulang dulu — proses lain
    # mungkin mencatat sesi profil lain di antara).
    with _json_store().locked(SESSIONS_FILE):
        sessions = _read_sessions()
        sessions[pid] = sess
        _write_sessions(sessions)
    # keep proc handles for in-process stop()
    # F6: 3-tuple (proc, daemon, worker_daemon) — worker_daemon bisa None.
    _PROCS[pid] = (proc, daemon, worker_daemon)
    return {"ok": True, **sess, "_page": page}


_PROCS = {}


def stop_profile(pid):
    # P-07: pop sesi di bawah lock; kill proses dilakukan SETELAH lock
    # dilepas (terminate + wait bisa makan detik — jangan tahan lock).
    with _json_store().locked(SESSIONS_FILE):
        sessions = _read_sessions()
        sess = sessions.pop(pid, None)
        _write_sessions(sessions)
    ok = False
    if pid in _PROCS:
        # F6: _PROCS 3-tuple (proc, daemon, worker_daemon); sesi lama
        # (2-tuple) tetap ditangani; worker_daemon bisa None.
        _entry = _PROCS.pop(pid)
        proc = _entry[0]
        daemon = _entry[1]
        worker_daemon = _entry[2] if len(_entry) > 2 else None
        for pr in (worker_daemon, daemon, proc):
            if pr is None:
                continue
            try:
                pr.terminate()
                pr.wait(timeout=5)
            except Exception:
                try:
                    pr.kill()
                except Exception:
                    pass
        ok = True
    elif sess:
        # launched from another process — kill by recorded pids
        # (worker_daemon_pid bisa None bila worker injector gagal spawn).
        for key in ("worker_daemon_pid", "daemon_pid", "browser_pid"):
            _wpid = sess.get(key)
            if not _wpid:
                continue
            try:
                os.kill(_wpid, signal.SIGTERM)
                ok = True
            except ProcessLookupError:
                ok = True  # already gone
            except Exception:
                pass
    return {"ok": ok, "profile_id": pid}


# ── CLI ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Antibrowser launcher — Chromium per profile + fingerprint inject")
    ap.add_argument("--profile", required=True, help="profile id (from GUI)")
    ap.add_argument("--url", default=None, help="URL to open after launch")
    ap.add_argument("--headful", action="store_true", help="headful mode (needs display/Xvfb)")
    ap.add_argument("--no-proxy", action="store_true", help="ignore profile proxy")
    ap.add_argument("--debug-port", type=int, default=None)
    ap.add_argument("--stop", action="store_true", help="stop running profile browser")
    ap.add_argument("--list", action="store_true", help="list running sessions")
    args = ap.parse_args()

    if args.list:
        print(json.dumps(list_running(), indent=1))
        return

    if args.stop:
        print(json.dumps(stop_profile(args.profile), indent=1))
        return

    profile = load_profile(args.profile)
    if not profile:
        print(json.dumps({"ok": False, "error": f"profile {args.profile} not found"}))
        sys.exit(1)
    if args.no_proxy:
        profile = dict(profile)
        profile["proxy"] = {"type": "none"}

    sess = launch_profile(profile, headless=not args.headful, url=args.url,
                          debug_port=args.debug_port)
    out = {k: v for k, v in sess.items() if not k.startswith("_")}
    print(json.dumps(out, indent=1))
    if not args.headful and not args.url:
        # keep alive for manual CDP use; Ctrl+C to stop
        print("browser running — Ctrl+C to stop", file=sys.stderr)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print(json.dumps(stop_profile(args.profile), indent=1))


if __name__ == "__main__":
    main()
