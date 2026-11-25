#!/usr/bin/env python3
"""
RPA sederhana + live fingerprint-check (P-18, Fase 2 P1).

Sebelumnya: helper gerak manusiawi (fingerprint/behavioral_human.py) sudah
ada tapi TIDAK BISA dipakai dari mana pun — tidak ada UI/API untuk
menjalankan alur, dan tidak ada cara memverifikasi fingerprint yang
disuntik benar-benar aktif di browser (hanya klaim dari config).

Isi modul ini:
  1. run_steps(port, steps) — jalankan daftar langkah JSON di browser
     profil yang SUDAH jalan (via CDP): goto / wait / click / type /
     scroll / press. Klik/ketik/scroll memakai behavioral_human
     (gerak mouse Bezier + rhythm ketik) bila tersedia, fallback ke
     Playwright native bila helper tidak ada.
  2. check_fingerprint(port, ident) — buka halaman baru, baca nilai
     fingerprint LANGSUNG dari browser (UA, webdriver, timezone,
     platform, screen, WebGL renderer, hw, mem, canvas hash) dan
     bandingkan dengan identity profil. Bukan klaim config — bukti live.
  3. Flow store — simpan/muat/daftar/hapus alur bernama sebagai JSON
     (gui/data/rpa_flows.json, di bawah lock P-07).

Window sync (sinkronisasi multi-window ala AdsPower) TIDAK di sini —
itu P2, setelah P-18 (lihat AUDIT-STEALTHXGM-2026-11-06 baris 341).
"""
import json
import os
import sys
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_GUI_DIR = os.path.join(_REPO, "gui")
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
if _GUI_DIR not in sys.path:
    sys.path.insert(0, _GUI_DIR)

# behavioral_human: gerak manusiawi (Bezier + rhythm). Bila tidak ada,
# runner tetap jalan dengan Playwright native (kurang manusiawi, tetap
# berfungsi) — dicatat di hasil sebagai "native".
try:
    from fingerprint.behavioral_human import (
        human_click_page, human_type_page, human_scroll_page)
    _HUMAN = True
except ImportError:
    _HUMAN = False

    def human_click_page(page, x, y, button="left"):
        page.mouse.click(x, y, button=button)

    def human_type_page(page, text, wpm=None):
        page.keyboard.type(text)

    def human_scroll_page(page, delta_y, steps=None):
        page.mouse.wheel(0, delta_y)


FLOWS_FILE = os.path.join(_GUI_DIR, "data", "rpa_flows.json")
MAX_STEPS = 200

STEP_TYPES = ("goto", "wait", "click", "type", "scroll", "press")


# ── Flow store ────────────────────────────────────────────────────────────
def _store():
    import json_store
    return json_store


def save_flow(name, steps, extra=None):
    """Simpan alur bernama. Return flow dict. Raise ValueError bila
    nama kosong / steps tidak valid. extra: dict metadata tambahan
    (mis. {"template": "youtube"}) yang ikut tersimpan."""
    if not name or not isinstance(name, str):
        raise ValueError("nama flow wajib string tidak kosong")
    steps = validate_steps(steps)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    store = _store()

    # atomic_update menyimpan `data` yang DITERIMA mutate — jadi mutate
    # HARUS ubah in-place (bukan salin + return); return value hanya hasil.
    def _mut(d):
        d[name] = {"name": name, "steps": steps, "updated_at": now,
                   "created_at": d.get(name, {}).get("created_at", now)}
        if extra:
            d[name].update(extra)
        return d[name]
    store.atomic_update(FLOWS_FILE, {}, _mut)
    out = {"name": name, "steps": steps, "updated_at": now}
    if extra:
        out.update(extra)
    return out


def list_flows():
    store = _store()
    data, _quarantined = store.load_json_safe(FLOWS_FILE, {})
    return data if isinstance(data, dict) else {}


def get_flow(name):
    flows = list_flows()
    if name not in flows:
        raise KeyError(f"flow '{name}' tidak ditemukan")
    return flows[name]


def delete_flow(name):
    store = _store()

    def _mut(d):
        if name not in d:
            raise KeyError(f"flow '{name}' tidak ditemukan")
        del d[name]
    store.atomic_update(FLOWS_FILE, {}, _mut)


# ── Validasi langkah ──────────────────────────────────────────────────────
def validate_steps(steps):
    """Validasi struktur daftar langkah. Return steps (salinan).
    Raise ValueError bila bukan list / >MAX_STEPS / item bukan dict /
    type tidak dikenal / field wajib hilang."""
    if not isinstance(steps, list):
        raise ValueError("steps harus list")
    if len(steps) > MAX_STEPS:
        raise ValueError(f"maks {MAX_STEPS} langkah per run")
    out = []
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            raise ValueError(f"langkah {i}: bukan dict")
        t = s.get("type")
        if t not in STEP_TYPES:
            raise ValueError(f"langkah {i}: type tidak dikenal: {t!r} "
                             f"(boleh: {', '.join(STEP_TYPES)})")
        if t == "goto" and not s.get("url"):
            raise ValueError(f"langkah {i}: goto butuh 'url'")
        if t in ("click", "type") and not s.get("selector"):
            raise ValueError(f"langkah {i}: {t} butuh 'selector'")
        if t == "type" and s.get("text") is None:
            raise ValueError(f"langkah {i}: type butuh 'text'")
        if t == "press" and not s.get("key"):
            raise ValueError(f"langkah {i}: press butuh 'key'")
        out.append(dict(s))
    return out


# ── Runner ────────────────────────────────────────────────────────────────
def _center(box):
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _run_one(page, step):
    """Satu langkah. Return (ok, detail). Raise hanya untuk error tak
    terduga; locator gagal ditangkap pemanggil sebagai step gagal."""
    t = step["type"]
    if t == "goto":
        resp = page.goto(step["url"], wait_until="domcontentloaded",
                         timeout=30000)
        return True, f"-> {page.url}" + (f" (HTTP {resp.status})" if resp else "")
    if t == "wait":
        ms = int(step.get("ms", 1000))
        ms = max(0, min(ms, 60000))
        time.sleep(ms / 1000)
        return True, f"{ms} ms"
    if t == "click":
        loc = page.locator(step["selector"]).first
        loc.wait_for(state="visible", timeout=10000)
        loc.scroll_into_view_if_needed(timeout=10000)
        box = loc.bounding_box()
        if box:
            x, y = _center(box)
            human_click_page(page, x, y)
            return True, f"{step['selector']} @ ({x:.0f},{y:.0f})" + (
                "" if _HUMAN else " [native: behavioral_human tidak ada]")
        loc.click(timeout=10000)  # elemen tak punya kotak (hidden) — native
        return True, f"{step['selector']} [native click: tanpa bounding box]"
    if t == "type":
        loc = page.locator(step["selector"]).first
        loc.wait_for(state="visible", timeout=10000)
        loc.scroll_into_view_if_needed(timeout=10000)
        box = loc.bounding_box()
        if box:
            x, y = _center(box)
            human_click_page(page, x, y)
        else:
            loc.click(timeout=10000)
        human_type_page(page, str(step["text"]))
        return True, f"{step['selector']} ({len(str(step['text']))} karakter)" + (
            "" if _HUMAN else " [native: behavioral_human tidak ada]")
    if t == "scroll":
        dy = int(step.get("delta_y", step.get("delta", 600)))
        human_scroll_page(page, dy)
        return True, f"delta_y={dy}" + (
            "" if _HUMAN else " [native: behavioral_human tidak ada]")
    if t == "press":
        page.keyboard.press(step["key"])
        return True, step["key"]
    return False, f"type tidak dikenal: {t}"


def run_steps(port, steps, timeout=120):
    """Jalankan langkah di browser yang sudah jalan (debug_port).
    Return {"ok", "steps": [{step, type, ok, detail, ms}],
    "human": bool, "error": str|None}. Satu langkah gagal TIDAK
    menghentikan run — langkah berikut tetap dicoba (hasil per langkah
    tercatat); timeout keseluruhan menghentikan sisa langkah."""
    from playwright.sync_api import sync_playwright
    steps = validate_steps(steps)
    deadline = time.monotonic() + max(5, timeout)
    results, failed = [], 0
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        try:
            for i, step in enumerate(steps):
                if time.monotonic() > deadline:
                    results.append({"step": i, "type": step["type"], "ok": False,
                                    "detail": "skipped: timeout keseluruhan",
                                    "ms": 0})
                    failed += 1
                    continue
                t0 = time.monotonic()
                try:
                    ok, detail = _run_one(page, step)
                except Exception as e:
                    ok, detail = False, str(e)[:200]
                ms = int((time.monotonic() - t0) * 1000)
                if not ok:
                    failed += 1
                results.append({"step": i, "type": step["type"], "ok": ok,
                                "detail": detail, "ms": ms})
        finally:
            try:
                page.close()
            except Exception:
                pass
            browser.close()
    return {"ok": failed == 0, "steps": results,
            "human": _HUMAN, "error": None}


# ── Live fingerprint-check ────────────────────────────────────────────────
_PROBE_JS = """() => {
  const nav = navigator;
  let webglRenderer = null, webglVendor = null;
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2') || c.getContext('webgl') || c.getContext('experimental-webgl');
    if (gl) {
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      if (ext) {
        webglRenderer = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);
        webglVendor = gl.getParameter(ext.UNMASKED_VENDOR_WEBGL);
      } else {
        webglRenderer = gl.getParameter(gl.RENDERER);
      }
    }
  } catch (e) {}
  let canvasHash = null;
  try {
    const c = document.createElement('canvas');
    c.width = 200; c.height = 50;
    const x = c.getContext('2d');
    x.fillStyle = '#f60'; x.fillRect(0, 0, 200, 50);
    x.fillStyle = '#069'; x.font = '18px Arial';
    x.fillText('StealthXGM fp-check', 10, 30);
    const d = c.toDataURL();
    let h = 5381;
    for (let i = 0; i < d.length; i++) h = ((h << 5) + h + d.charCodeAt(i)) >>> 0;
    canvasHash = ('0000000' + h.toString(16)).slice(-8);
  } catch (e) {}
  return {
    userAgent: nav.userAgent,
    webdriver: nav.webdriver,
    platform: nav.platform,
    languages: nav.languages ? Array.from(nav.languages) : [],
    hardwareConcurrency: nav.hardwareConcurrency,
    deviceMemory: nav.deviceMemory,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    timezoneOffset: new Date().getTimezoneOffset(),
    screen: {width: screen.width, height: screen.height, colorDepth: screen.colorDepth},
    devicePixelRatio: window.devicePixelRatio,
    webglRenderer, webglVendor, canvasHash,
  };
}"""


def _expected_tz_offset_minutes(tz_name):
    """Offset zona waktu yang SEHARUSNYA terlihat (menit, konvensi JS:
    getTimezoneOffset() = UTC - lokal; Jakarta = -420). None bila
    zona tak dikenal / zoneinfo tak tersedia."""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        off = datetime.now(ZoneInfo(tz_name)).utcoffset()
        if off is None:
            return None
        return -int(off.total_seconds() // 60)
    except Exception:
        return None


def check_fingerprint(port, ident):
    """Baca fingerprint LIVE dari browser + bandingkan dengan identity
    profil. ident = dict dari build_fingerprint_js() (kunci: _ua,
    timezone, platform, screen_w/h, gpu_renderer, hw, mem, dpr,
    color_depth, locale). Return {"ok", "checks": [{field, expected,
    live, ok, note}], "live": {...}}. Field yang tidak disediakan ident
    dilaporkan sebagai info (ok=None), bukan gagal. canvasHash hanya
    info — nilai yang diharapkan tidak bisa dihitung dari luar JS spoof
    (noise seeded), tapi hash yang STABIL antar run = konsistensi profil."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        try:
            page.goto("about:blank")
            live = page.evaluate(_PROBE_JS)
        finally:
            try:
                page.close()
            except Exception:
                pass
            browser.close()

    checks = []

    def _cmp(field, expected, got, note=""):
        if expected is None:
            checks.append({"field": field, "expected": None, "live": got,
                           "ok": None, "note": note or "tidak ada nilai pembanding di profil"})
            return
        checks.append({"field": field, "expected": expected, "live": got,
                       "ok": expected == got, "note": note})

    _cmp("userAgent", ident.get("_ua"), live.get("userAgent"))
    _cmp("webdriver", False, live.get("webdriver"),
         "harus False — True = bot terdeteksi")
    _cmp("timezone", ident.get("timezone"), live.get("timezone"))
    exp_off = _expected_tz_offset_minutes(ident.get("timezone")) \
        if ident.get("timezone") else None
    _cmp("timezoneOffset", exp_off, live.get("timezoneOffset"),
         "offset menit zona waktu (JS: UTC-lokal)")
    _cmp("platform", ident.get("platform"), live.get("platform"))
    scr = live.get("screen") or {}
    _cmp("screen.width", ident.get("screen_w"), scr.get("width"))
    _cmp("screen.height", ident.get("screen_h"), scr.get("height"))
    _cmp("screen.colorDepth", ident.get("color_depth"), scr.get("colorDepth"))
    _cmp("devicePixelRatio", ident.get("dpr"), live.get("devicePixelRatio"))
    _cmp("hardwareConcurrency", ident.get("hw"), live.get("hardwareConcurrency"))
    _cmp("deviceMemory", ident.get("mem"), live.get("deviceMemory"))
    _cmp("webglRenderer", ident.get("gpu_renderer"), live.get("webglRenderer"))
    langs = live.get("languages") or []
    locale = ident.get("locale")
    _cmp("languages[0]", locale, langs[0] if langs else None,
         "bahasa utama browser vs locale profil")
    checks.append({"field": "canvasHash", "expected": None,
                   "live": live.get("canvasHash"), "ok": None,
                   "note": "info saja — bandingkan antar run: harus stabil per profil"})
    ok = all(c["ok"] for c in checks if c["ok"] is not None)
    return {"ok": ok, "checks": checks, "live": live}


# ── Record & replay (F5-2) ────────────────────────────────────────────────
# Perekam aksi user di tab profil yang jalan. Cara kerja: init-script
# disuntik ke semua halaman (add_init_script — berlaku juga untuk halaman
# baru + sesudah navigasi); listener DOM menangkap klik / ketik / tombol /
# gulir / navigasi dan menaruhnya di window.__alur_rec (+ sessionStorage
# supaya tidak hilang saat navigasi se-origin). Thread perekam (satu per
# port) memanen array itu tiap 0,3 detik.
#
# State perekaman tinggal di _RECORDERS (modul ini) — karena itu modul
# HARUS dimuat sekali via gui/rpa_loader.load_rpa(), bukan exec ulang
# per request (app.py/_rpa() lama men-exec ulang — state hilang).
# Panen HARUS splice(0) (in-place): listener menutup (closure) array
# `rec` yang sama — `window.__alur_rec = []` membuat array baru dan
# event menumpuk di array lama yang tak terbaca lagi.
_RECORDER_JS = r"""
(() => {
  if (window.__alur_rec) return;
  let rec = [];
  try { rec = JSON.parse(sessionStorage.getItem('__alur_rec') || '[]'); } catch (e) { rec = []; }
  if (!Array.isArray(rec)) rec = [];
  window.__alur_rec = rec;
  function push(step) {
    rec.push(step);
    try { sessionStorage.setItem('__alur_rec', JSON.stringify(rec)); } catch (e) {}
  }
  function sel(el) {
    if (!el || el === document.documentElement || el === document.body) return null;
    if (el.id) return '#' + el.id;
    const tid = el.getAttribute && el.getAttribute('data-testid');
    if (tid) return '[data-testid="' + tid + '"]';
    let s = el.tagName.toLowerCase();
    if (el.className && typeof el.className === 'string') {
      const cls = el.className.trim().split(/\s+/).filter(function (c) {
        return c && !/^(active|hover|focus|selected|open)$/.test(c);
      }).slice(0, 2);
      if (cls.length) s += '.' + cls.join('.');
    }
    const parent = el.parentElement;
    if (parent) {
      const sibs = Array.prototype.filter.call(parent.children, function (c) {
        return c.tagName === el.tagName;
      });
      if (sibs.length > 1) s += ':nth-of-type(' + (sibs.indexOf(el) + 1) + ')';
    }
    return s;
  }
  let lastUrl = location.href;
  document.addEventListener('click', function (e) {
    const t = (e.target && e.target.closest)
      ? (e.target.closest('a,button,input,select,[role=button],summary') || e.target)
      : e.target;
    if (t && t.tagName === 'A' && t.href) { push({type: 'goto', url: t.href}); return; }
    const s = sel(t);
    if (s) push({type: 'click', selector: s});
  }, true);
  let typeTimer = null, typeEl = null;
  document.addEventListener('input', function (e) {
    const t = e.target;
    if (!t || !/^(INPUT|TEXTAREA)$/.test(t.tagName)) return;
    typeEl = t;
    clearTimeout(typeTimer);
    typeTimer = setTimeout(function () {
      const s = sel(typeEl);
      if (s && typeEl.value) push({type: 'type', selector: s, text: typeEl.value});
      typeEl = null;
    }, 600);
  }, true);
  document.addEventListener('change', function (e) {
    const t = e.target;
    if (!t || !/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    if (typeEl === t) { clearTimeout(typeTimer); typeEl = null; }
    const s = sel(t);
    if (s) push({type: 'type', selector: s, text: t.value});
  }, true);
  document.addEventListener('keydown', function (e) {
    if (['Enter', 'Tab', 'Escape', 'ArrowDown', 'ArrowUp',
         'ArrowLeft', 'ArrowRight', 'PageDown', 'PageUp',
         'Home', 'End'].indexOf(e.key) !== -1) push({type: 'press', key: e.key});
  }, true);
  let lastY = window.scrollY || 0, scrollTimer = null;
  window.addEventListener('scroll', function () {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(function () {
      const dy = Math.round((window.scrollY || 0) - lastY);
      lastY = window.scrollY || 0;
      if (dy !== 0) push({type: 'scroll', delta_y: dy});
    }, 400);
  }, true);
  window.addEventListener('load', function () {
    if (location.href !== lastUrl) {
      push({type: 'goto', url: location.href});
      lastUrl = location.href;
    }
  });
})();
"""

_RECORDERS = {}  # port -> {"thread","stop","steps","error","start_url"}
_RECORDERS_LOCK = threading.Lock()


def _clean_recorded_steps(raw, start_url):
    """Bersihkan langkah hasil rekaman jadi langkah valid siap replay:
    - awali goto ke URL saat rekam dimulai (bila langkah pertama bukan goto)
    - buang type kosong, gabung type berurutan di selector sama (ambil
      nilai terakhir), gabung scroll berurutan, buang klik duplikat
      berurutan + goto duplikat berurutan, potong ke MAX_STEPS.
    Return langkah yang sudah lolos validate_steps."""
    steps = []
    for s in (raw or []):
        if not isinstance(s, dict) or s.get("type") not in STEP_TYPES:
            continue
        s = dict(s)
        if s["type"] == "type" and not str(s.get("text", "")):
            continue
        if s["type"] == "scroll":
            try:
                s["delta_y"] = int(s.get("delta_y", 0))
            except Exception:
                continue
            if s["delta_y"] == 0:
                continue
        steps.append(s)
    merged = []
    for s in steps:
        if not merged:
            merged.append(s)
            continue
        prev = merged[-1]
        if (s["type"] == "type" and prev["type"] == "type"
                and s.get("selector") == prev.get("selector")):
            merged[-1] = s  # nilai ketik terakhir yang berlaku
            continue
        if s["type"] == "scroll" and prev["type"] == "scroll":
            prev["delta_y"] = prev["delta_y"] + s["delta_y"]
            if prev["delta_y"] == 0:
                merged.pop()
            continue
        if (s["type"] == "click" and prev["type"] == "click"
                and s.get("selector") == prev.get("selector")):
            continue
        if (s["type"] == "goto" and prev["type"] == "goto"
                and s.get("url") == prev.get("url")):
            continue
        merged.append(s)
    if not merged or merged[0]["type"] != "goto":
        if start_url:
            merged.insert(0, {"type": "goto", "url": start_url})
    return validate_steps(merged[:MAX_STEPS])


def _recorder_thread(port, rec):
    """Thread perekam: sambung CDP, suntik init-script ke context,
    panen window.__alur_rec tiap 0,3 detik."""
    browser = None
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            try:
                ctx.add_init_script(_RECORDER_JS)
            except Exception:
                pass
            pages = list(ctx.pages)
            if not pages:
                pages = [ctx.new_page()]
            for pg in pages:
                try:
                    pg.evaluate(_RECORDER_JS)
                except Exception:
                    pass
            rec["start_url"] = pages[0].url if pages else "about:blank"
            # Navigasi tidak bisa diandalkan dari listener `load` di halaman
            # (init-script jalan SESUDAH navigasi — lastUrl sudah URL baru),
            # jadi poller yang mendeteksi perubahan URL tiap halaman.
            seen_urls = {}
            for pg in pages:
                try:
                    seen_urls[pg] = pg.url
                except Exception:
                    pass
            while not rec["stop"].is_set():
                for pg in list(ctx.pages):
                    try:
                        url = pg.url
                        prev = seen_urls.get(pg)
                        if prev is None:
                            # Halaman baru muncul saat merekam: catat goto
                            # ke URL-nya sekarang (kecuali halaman kosong).
                            seen_urls[pg] = url
                            if url and url not in (
                                    "about:blank", "chrome://new-tab-page/",
                                    rec.get("start_url")):
                                rec["steps"].append({"type": "goto", "url": url})
                        elif url != prev:
                            seen_urls[pg] = url
                            rec["steps"].append({"type": "goto", "url": url})
                        if not pg.evaluate("!!window.__alur_rec"):
                            pg.evaluate(_RECORDER_JS)
                            continue
                        batch = pg.evaluate(
                            "(() => { const a = (window.__alur_rec || []).splice(0);"
                            " try { sessionStorage.removeItem('__alur_rec'); }"
                            " catch (e) {} return a; })()")
                        if batch:
                            rec["steps"].extend(batch)
                    except Exception:
                        pass
                rec["stop"].wait(0.3)
            # Panen terakhir sebelum tutup — aksi di detik terakhir.
            for pg in list(ctx.pages):
                try:
                    batch = pg.evaluate(
                        "(() => { const a = (window.__alur_rec || []).splice(0);"
                        " try { sessionStorage.removeItem('__alur_rec'); }"
                        " catch (e) {} return a; })()")
                    if batch:
                        rec["steps"].extend(batch)
                except Exception:
                    pass
    except Exception as e:
        rec["error"] = str(e)[:300]
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass


def start_recording(port):
    """Mulai merekam aksi user di profil yang jalan (debug_port).
    Return {"ok", "start_url"}. Raise ValueError bila sudah merekam di
    port ini, RuntimeError bila tidak bisa terhubung."""
    with _RECORDERS_LOCK:
        cur = _RECORDERS.get(port)
        if cur and cur["thread"].is_alive():
            raise ValueError("perekaman sudah jalan di port ini")
        rec = {"stop": threading.Event(), "steps": [],
               "error": None, "start_url": None, "thread": None}
        t = threading.Thread(target=_recorder_thread, args=(port, rec),
                             daemon=True, name=f"alur-record-{port}")
        rec["thread"] = t
        _RECORDERS[port] = rec
        t.start()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if rec["start_url"] is not None or rec["error"]:
            break
        time.sleep(0.2)
    if rec["error"]:
        raise RuntimeError(rec["error"])
    if rec["start_url"] is None:
        raise RuntimeError("perekam tidak bisa terhubung ke browser (timeout)")
    return {"ok": True, "port": port, "start_url": rec["start_url"]}


def stop_recording(port, name=None):
    """Berhenti merekam; return {"ok", "steps": [...]} (langkah bersih,
    siap replay). Bila name diisi, alur langsung disimpan dengan nama itu.
    Raise KeyError bila tidak ada perekaman di port ini."""
    with _RECORDERS_LOCK:
        rec = _RECORDERS.get(port)
        if not rec:
            raise KeyError("tidak ada perekaman di port ini")
        rec["stop"].set()
        t = rec["thread"]
    t.join(timeout=15)
    steps = _clean_recorded_steps(list(rec["steps"]), rec.get("start_url"))
    with _RECORDERS_LOCK:
        _RECORDERS.pop(port, None)
    out = {"ok": True, "port": port, "steps": steps}
    if name:
        flow = save_flow(name, steps)
        out["saved"] = flow["name"]
    return out


def recording_status(port):
    """Status perekaman di satu port (tanpa menghentikannya)."""
    with _RECORDERS_LOCK:
        rec = _RECORDERS.get(port)
        if not rec or not rec["thread"].is_alive():
            return {"recording": False, "port": port, "steps_so_far": 0}
        return {"recording": True, "port": port,
                "steps_so_far": len(rec["steps"]),
                "start_url": rec.get("start_url")}


# ── Template alur per platform (F5-3) ─────────────────────────────────────
# Alur awal siap pakai: HANYA buka beranda + tunggu + gulir (navigasi
# umum yang aman). TIDAK ADA login, TIDAK ADA isi kredensial, TIDAK ADA
# klik tombol aksi — pemakai yang menambahkan langkah sensitif sendiri.
TEMPLATES = {
    "youtube": {"label": "YouTube — buka beranda + gulir",
                "steps": [{"type": "goto", "url": "https://www.youtube.com"},
                          {"type": "wait", "ms": 2500},
                          {"type": "scroll", "delta_y": 800},
                          {"type": "wait", "ms": 1200},
                          {"type": "scroll", "delta_y": 800}]},
    "facebook": {"label": "Facebook — buka beranda + gulir",
                 "steps": [{"type": "goto", "url": "https://www.facebook.com"},
                           {"type": "wait", "ms": 2500},
                           {"type": "scroll", "delta_y": 600},
                           {"type": "wait", "ms": 1200},
                           {"type": "scroll", "delta_y": 600}]},
    "tiktok": {"label": "TikTok — buka beranda + gulir",
               "steps": [{"type": "goto", "url": "https://www.tiktok.com"},
                         {"type": "wait", "ms": 2500},
                         {"type": "scroll", "delta_y": 800},
                         {"type": "wait", "ms": 1200},
                         {"type": "scroll", "delta_y": 800}]},
    "instagram": {"label": "Instagram — buka beranda + gulir",
                  "steps": [{"type": "goto", "url": "https://www.instagram.com"},
                            {"type": "wait", "ms": 2500},
                            {"type": "scroll", "delta_y": 600},
                            {"type": "wait", "ms": 1200},
                            {"type": "scroll", "delta_y": 600}]},
    "amazon": {"label": "Amazon — buka beranda + gulir",
               "steps": [{"type": "goto", "url": "https://www.amazon.com"},
                         {"type": "wait", "ms": 2000},
                         {"type": "scroll", "delta_y": 600},
                         {"type": "wait", "ms": 1000},
                         {"type": "scroll", "delta_y": 600}]},
    "linkedin": {"label": "LinkedIn — buka beranda + gulir",
                 "steps": [{"type": "goto", "url": "https://www.linkedin.com"},
                           {"type": "wait", "ms": 2500},
                           {"type": "scroll", "delta_y": 600},
                           {"type": "wait", "ms": 1200},
                           {"type": "scroll", "delta_y": 600}]},
    "discord": {"label": "Discord — buka beranda + gulir",
                "steps": [{"type": "goto", "url": "https://discord.com"},
                          {"type": "wait", "ms": 2500},
                          {"type": "scroll", "delta_y": 600}]},
}


def list_templates():
    """Daftar template: {key: {label, steps}} (jumlah langkah saja)."""
    return {k: {"label": v["label"], "steps": len(v["steps"])}
            for k, v in TEMPLATES.items()}


def get_template(key):
    """Satu template lengkap. Raise KeyError bila key tak dikenal."""
    if key not in TEMPLATES:
        raise KeyError(f"template '{key}' tidak dikenal")
    t = TEMPLATES[key]
    return {"key": key, "label": t["label"],
            "steps": validate_steps(t["steps"])}


def install_template(key, name):
    """Salin template jadi alur tersimpan bernama `name` (dengan
    penanda template asalnya). Return flow dict."""
    t = get_template(key)
    return save_flow(name, t["steps"], extra={"template": key})
