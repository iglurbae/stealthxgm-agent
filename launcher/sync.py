#!/usr/bin/env python3
"""
Synchronizer ("Cermin", F3-2) — mirror aksi ke semua jendela terbuka.

Model: 15 rute /sync/* AdsPower 8.6.3 (bukti REA, lihat
ADSPOWER-FEATURE-MAP-2026-11-07.md §8):
  toSyncOperateBrowser, toStopSyncOperateBrowser, getOperateBrowser,
  toInputTxt, toRefreshTab, toRangeBrowser, toOpenDelay, toShowBrowser,
  manageUrlTab, openUrl, paste, syncSize, getPosition, resetDownload,
  clear.

Nama pasar AdsPower ("Synchronizer") TIDAK dipakai — fitur ini bernama
"Cermin" di StealthXGM (desain fresh). Arsitektur juga beda: AdsPower
mencerminkan aksi lewat client internalnya; di sini pencerminan adalah
PERINTAH (command mirroring) — operator/GUI/API/CLI memerintahkan satu
aksi (goto, ketik, refresh, klik, scroll, ...) dan mesin menjalankannya
di leader + semua follower yang ikut, dengan jeda antar-jendela
(toOpenDelay). Pencerminan mouse/ketik LANGSUNG dari jendela leader
(menangkap event nyata user lalu replay) TIDAK ada di fase ini — itu
butuh content-script penangkap event di tiap halaman; dicatat sebagai
pekerjaan lanjutan, bukan diklaim sudah ada.

State sesi sync disimpan di gui/data/sync_state.json (lock P-07) supaya
GUI (5200) dan Local API (50325) — dua proses berbeda — melihat sesi
yang sama. Tiap aksi menghubungkan ulang ke debug port tiap target
(connect_over_cdp per panggilan); tidak ada thread latar yang harus
dijaga hidup.

Target = profil yang sedang jalan (registry hidup launcher.list_running).
Leader = jendela acuan (untuk syncSize + posisi). Follower = yang ikut.
Range "all" = semua profil jalan kecuali leader; "selected" = daftar
eksplisit.
"""
import json
import os
import sys
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_GUI_DIR = os.path.join(_REPO, "gui")
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
if _GUI_DIR not in sys.path:
    sys.path.insert(0, _GUI_DIR)

import json_store  # noqa: E402

STATE_FILE = os.path.join(_GUI_DIR, "data", "sync_state.json")
MAX_LOG = 200

# Nama rute AdsPower -> fungsi kita (dipakai GUI/Local API/CLI).
ROUTES = (
    "toSyncOperateBrowser", "toStopSyncOperateBrowser", "getOperateBrowser",
    "toInputTxt", "toRefreshTab", "toRangeBrowser", "toOpenDelay",
    "toShowBrowser", "manageUrlTab", "openUrl", "paste", "syncSize",
    "getPosition", "resetDownload", "clear",
)


def _default_state():
    return {"active": False, "leader_id": None, "followers": [],
            "range": "all", "open_delay_ms": 0, "started_at": None,
            "log": []}


def _load_state():
    data, _q = json_store.load_json_safe(STATE_FILE, _default_state())
    if not isinstance(data, dict):
        return _default_state()
    base = _default_state()
    base.update(data)
    return base


def _save_state(state):
    json_store.save_json_atomic(STATE_FILE, state, chmod=0o600)


def _launcher():
    import launcher as _l
    return _l


def _running():
    """{pid: session} profil yang sedang jalan (registry hidup)."""
    try:
        return _launcher().list_running()
    except Exception:
        return {}


def _targets(state):
    """Daftar pid target yang AKTIF (leader + follower yang masih jalan),
    leader dulu."""
    running = _running()
    out = []
    leader = state.get("leader_id")
    if leader and leader in running:
        out.append(leader)
    if state.get("range") == "all":
        for pid in running:
            if pid != leader and pid not in out:
                out.append(pid)
    else:
        for pid in state.get("followers") or []:
            if pid in running and pid not in out:
                out.append(pid)
    return out


def _log(state, action, detail=""):
    log = state.get("log") or []
    log.append({"at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "action": action, "detail": detail})
    state["log"] = log[-MAX_LOG:]


# ── Sesi ──────────────────────────────────────────────────────────────────
def start_sync(leader_id, follower_ids=None, open_delay_ms=0):
    """Mulai sesi cermin. leader_id wajib jalan; follower_ids None = semua
    profil jalan lain (range all). Return state. Raise ValueError bila
    leader tidak jalan / tidak ada target."""
    running = _running()
    if leader_id not in running:
        raise ValueError(f"leader {leader_id} tidak jalan — launch dulu")
    if follower_ids is None:
        followers = [pid for pid in running if pid != leader_id]
        rng = "all"
    else:
        followers = [pid for pid in follower_ids if pid != leader_id]
        missing = [pid for pid in followers if pid not in running]
        if missing:
            raise ValueError(f"follower tidak jalan: {', '.join(missing)}")
        rng = "selected"
    if not followers:
        raise ValueError("tidak ada follower — butuh ≥1 profil lain yang jalan")
    state = _default_state()
    state.update({"active": True, "leader_id": leader_id,
                  "followers": followers, "range": rng,
                  "open_delay_ms": max(0, int(open_delay_ms)),
                  "started_at": time.strftime("%Y-%m-%d %H:%M:%S")})
    _log(state, "start", f"leader={leader_id} followers={len(followers)}")
    _save_state(state)
    return state


def stop_sync():
    """Hentikan sesi cermin. Return state (active=False)."""
    state = _load_state()
    state["active"] = False
    _log(state, "stop")
    _save_state(state)
    return state


def get_state():
    """State sesi + status hidup tiap target. Return dict."""
    state = _load_state()
    running = _running()
    targets = []
    for pid in _targets(state):
        sess = running.get(pid, {})
        targets.append({"profile_id": pid, "debug_port": sess.get("debug_port"),
                        "role": "leader" if pid == state.get("leader_id")
                        else "follower"})
    return {**state, "targets": targets,
            "targets_running": len(targets)}


def set_range(mode, follower_ids=None):
    """toRangeBrowser: ubah cakupan sesi aktif. mode "all" | "selected".
    Return state. Raise ValueError bila sesi tidak aktif / mode salah."""
    if mode not in ("all", "selected"):
        raise ValueError("range harus 'all' atau 'selected'")
    state = _load_state()
    if not state.get("active"):
        raise ValueError("tidak ada sesi cermin aktif")
    running = _running()
    if mode == "all":
        state["range"] = "all"
        state["followers"] = [pid for pid in running
                              if pid != state.get("leader_id")]
    else:
        if not follower_ids:
            raise ValueError("range 'selected' butuh follower_ids")
        missing = [pid for pid in follower_ids
                   if pid not in running or pid == state.get("leader_id")]
        if missing:
            raise ValueError(f"follower tidak jalan: {', '.join(missing)}")
        state["range"] = "selected"
        state["followers"] = list(follower_ids)
    _log(state, "range", f"{mode} followers={len(state['followers'])}")
    _save_state(state)
    return state


def set_open_delay(ms):
    """toOpenDelay: jeda (ms) antar-jendela saat aksi dicerminkan.
    Return state. Raise ValueError bila sesi tidak aktif."""
    state = _load_state()
    if not state.get("active"):
        raise ValueError("tidak ada sesi cermin aktif")
    state["open_delay_ms"] = max(0, int(ms))
    _log(state, "open_delay", f"{state['open_delay_ms']} ms")
    _save_state(state)
    return state


def clear_log():
    """clear: kosongkan log aksi sesi. Return state."""
    state = _load_state()
    state["log"] = []
    _save_state(state)
    return state


def reset_download():
    """resetDownload: kosongkan entri unduhan dari log aksi.

    StealthXGM tidak melacak unduhan per jendela seperti AdsPower — yang
    ada hanya log aksi cermin. Fungsi ini menghapus entri log bertipe
    download (goto ke file: / unduhan yang dicatat) dan mencatat resetnya.
    Jujur: ini reset LOG, bukan reset state unduhan browser."""
    state = _load_state()
    before = len(state.get("log") or [])
    state["log"] = [e for e in (state.get("log") or [])
                    if e.get("action") != "download"]
    _log(state, "reset_download", f"{before - len(state['log'])} entri dihapus")
    _save_state(state)
    return state


# ── Aksi cermin ───────────────────────────────────────────────────────────
def _require_active():
    state = _load_state()
    if not state.get("active"):
        raise ValueError("tidak ada sesi cermin aktif — start dulu")
    targets = _targets(state)
    if not targets:
        raise ValueError("tidak ada target jalan dalam sesi cermin")
    return state, targets


def _fan_out(state, targets, fn, action, detail=""):
    """Jalankan fn(pid, port) di tiap target berurutan dengan jeda
    open_delay antar-jendela. Return {ok, results: {pid: ...}}."""
    delay = (state.get("open_delay_ms") or 0) / 1000.0
    running = _running()
    results, failed = {}, 0
    for i, pid in enumerate(targets):
        if i and delay:
            time.sleep(delay)
        port = running.get(pid, {}).get("debug_port")
        try:
            results[pid] = fn(pid, port)
        except Exception as e:
            results[pid] = {"ok": False, "error": str(e)[:200]}
            failed += 1
    _log(state, action, detail)
    _save_state(state)
    return {"ok": failed == 0, "results": results}


def mirror_steps(steps, targets=None):
    """Cerminkan daftar langkah RPA (goto/click/type/scroll/wait/press)
    ke leader + follower. targets=None = target sesi aktif. Return
    {ok, results: {pid: rpa_result}}."""
    import rpa as rpa_mod
    steps = rpa_mod.validate_steps(steps)
    if targets is None:
        state, targets = _require_active()
    else:
        state = _load_state()
        running = _running()
        bad = [p for p in targets if p not in running]
        if bad:
            raise ValueError(f"target tidak jalan: {', '.join(bad)}")
    return _fan_out(state, targets,
                    lambda pid, port: rpa_mod.run_steps(port, steps),
                    "mirror_steps", f"{len(steps)} langkah ke {len(targets)} jendela")


def open_url(url):
    """openUrl: buka URL di halaman aktif tiap target. Return fan-out."""
    if not url or not isinstance(url, str):
        raise ValueError("url wajib string tidak kosong")
    state, targets = _require_active()

    def _go(pid, port):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = b.contexts[0] if b.contexts else b.new_context()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            out = {"ok": True, "url": page.url,
                   "status": resp.status if resp else None}
            b.close()
            return out

    return _fan_out(state, targets, _go, "open_url", url)


def input_text(text, selector=None):
    """toInputTxt / paste: ketik teks di tiap target.

    selector diisi -> ketik ke elemen itu (klik dulu, lalu ketik manusiawi
    bila helper ada). selector kosong -> ketik ke elemen yang sedang fokus
    di halaman aktif (keyboard.type). Return fan-out."""
    if text is None:
        raise ValueError("text wajib diisi")
    text = str(text)
    state, targets = _require_active()

    def _type(pid, port):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = b.contexts[0] if b.contexts else b.new_context()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            if selector:
                loc = page.locator(selector).first
                loc.wait_for(state="visible", timeout=10000)
                loc.click(timeout=10000)
                page.keyboard.type(text)
            else:
                page.keyboard.type(text)
            out = {"ok": True, "chars": len(text),
                   "selector": selector or "(fokus)"}
            b.close()
            return out

    return _fan_out(state, targets, _type, "input_text",
                    f"{len(text)} karakter" + (f" ke {selector}" if selector else ""))


def refresh_all():
    """toRefreshTab: muat ulang halaman aktif tiap target. Return fan-out."""
    state, targets = _require_active()

    def _refresh(pid, port):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = b.contexts[0] if b.contexts else b.new_context()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.reload(wait_until="domcontentloaded", timeout=30000)
            out = {"ok": True, "url": page.url}
            b.close()
            return out

    return _fan_out(state, targets, _refresh, "refresh", "reload halaman aktif")


# ── Tab (manageUrlTab) ────────────────────────────────────────────────────
def _cdp_http(port, path, method="GET"):
    """Panggil HTTP endpoint DevTools Chromium (/json/*). Return parsed JSON
    atau None (untuk /json/new tanpa body JSON). Raise bila port mati."""
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read()
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return None


def list_tabs(pid):
    """Daftar target halaman (tab) satu profil yang jalan."""
    running = _running()
    sess = running.get(pid)
    if not sess:
        raise ValueError(f"profil {pid} tidak jalan")
    targets = _cdp_http(sess["debug_port"], "/json/list") or []
    return [{"id": t.get("id"), "type": t.get("type"),
             "title": t.get("title"), "url": t.get("url")}
            for t in targets if t.get("type") == "page"]


def open_tab(pid, url):
    """Buka tab baru di profil yang jalan. Return info target baru."""
    if not url:
        raise ValueError("url wajib diisi")
    running = _running()
    sess = running.get(pid)
    if not sess:
        raise ValueError(f"profil {pid} tidak jalan")
    from urllib.parse import quote
    info = _cdp_http(sess["debug_port"], f"/json/new?{quote(url, safe='')}",
                     method="PUT")
    if not info:
        raise RuntimeError("gagal buka tab baru (endpoint /json/new kosong)")
    return {"id": info.get("id"), "url": info.get("url"),
            "title": info.get("title")}


def close_tab(pid, target_id):
    """Tutup satu tab (target id dari list_tabs). Return True bila tertutup.

    /json/close bersifat async — target bisa masih muncul di /json/list
    sesaat sesudahnya. Fungsi ini memverifikasi dengan poll (maks ~2 detik)
    dan return False bila target masih ada setelah itu."""
    running = _running()
    sess = running.get(pid)
    if not sess:
        raise ValueError(f"profil {pid} tidak jalan")
    _cdp_http(sess["debug_port"], f"/json/close/{target_id}")
    deadline = time.time() + 2.0
    while time.time() < deadline:
        targets = _cdp_http(sess["debug_port"], "/json/list") or []
        if not any(t.get("id") == target_id for t in targets):
            return True
        time.sleep(0.1)
    return False


def activate_tab(pid, target_id):
    """Aktifkan satu tab. Return True."""
    running = _running()
    sess = running.get(pid)
    if not sess:
        raise ValueError(f"profil {pid} tidak jalan")
    _cdp_http(sess["debug_port"], f"/json/activate/{target_id}")
    return True


def show_browser(pid):
    """toShowBrowser: tampilkan jendela profil (aktifkan tab pertamanya).

    Headless / tanpa window manager, "tampilkan" berarti tab pertama jadi
    aktif di jendela itu — tidak ada jaminan jendela muncul di depan layar
    (itu urusan window manager OS). Return True + tab yang diaktifkan."""
    tabs = list_tabs(pid)
    if not tabs:
        raise ValueError(f"profil {pid} tidak punya tab")
    activate_tab(pid, tabs[0]["id"])
    return {"ok": True, "profile_id": pid, "tab": tabs[0]}


# ── Posisi + ukuran jendela (getPosition / syncSize) ──────────────────────
def get_position(pid):
    """getPosition: posisi + ukuran jendela profil yang jalan (screenX/Y,
    outerWidth/Height dari halaman aktif). Return dict."""
    running = _running()
    sess = running.get(pid)
    if not sess:
        raise ValueError(f"profil {pid} tidak jalan")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(
            f"http://127.0.0.1:{sess['debug_port']}")
        ctx = b.contexts[0] if b.contexts else b.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        pos = page.evaluate("() => ({x: window.screenX, y: window.screenY,"
                            " width: window.outerWidth,"
                            " height: window.outerHeight})")
        b.close()
    return {"profile_id": pid, **pos}


def sync_size():
    """syncSize: samakan ukuran jendela follower dengan leader.

    Via CDP Browser.setWindowBounds (sesi browser-level Playwright).
    Bila CDP browser-level tidak tersedia di Playwright terpasang, fallback
    ke window.resizeTo di halaman aktif (terbatas: tidak jalan untuk
    jendela yang tidak dibuka lewat script). Hasil per jendela dilaporkan
    jujur (ok/metode yang dipakai). Return fan-out."""
    state, targets = _require_active()
    leader = state.get("leader_id")
    try:
        leader_pos = get_position(leader)
    except Exception as e:
        raise ValueError(f"gagal baca posisi leader: {e}")
    w, h = leader_pos["width"], leader_pos["height"]

    def _resize(pid, port):
        # Coba CDP browser-level dulu (Playwright >= 1.28).
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                sess = b.new_browser_cdp_session()
                targets_json = _cdp_http(port, "/json/list") or []
                page_t = next((t for t in targets_json
                               if t.get("type") == "page"), None)
                if not page_t:
                    raise RuntimeError("tidak ada tab page")
                win = sess.send("Browser.getWindowForTarget",
                                {"targetId": page_t["id"]})
                sess.send("Browser.setWindowBounds",
                          {"windowId": win["windowId"],
                           "bounds": {"width": w, "height": h}})
                sess.detach()
                b.close()
            return {"ok": True, "method": "cdp", "width": w, "height": h}
        except Exception as e:
            err_cdp = str(e)[:120]
        # Fallback: resizeTo di halaman aktif.
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                ctx = b.contexts[0] if b.contexts else b.new_context()
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.evaluate(f"window.resizeTo({w}, {h})")
                got = page.evaluate("() => ({width: window.outerWidth,"
                                    " height: window.outerHeight})")
                b.close()
            ok = got["width"] == w and got["height"] == h
            return {"ok": ok, "method": "resizeTo", "width": got["width"],
                    "height": got["height"],
                    "error": None if ok else f"CDP gagal: {err_cdp}"}
        except Exception as e2:
            return {"ok": False, "method": "none",
                    "error": f"CDP: {err_cdp}; resizeTo: {str(e2)[:120]}"}

    followers = [pid for pid in targets if pid != leader]
    out = _fan_out(state, followers, _resize, "sync_size",
                   f"leader {leader} {w}x{h} ke {len(followers)} follower")
    out["leader"] = {"profile_id": leader, "width": w, "height": h}
    return out
