"""Local REST API — AdsPower-compatible (port 50325).

Mirrors AdsPower Local API so existing scripts work:
  GET  /api/v1/status
  GET  /api/v1/browser/start?user_id=XXX
  GET  /api/v1/browser/stop?user_id=XXX
  GET  /api/v1/browser/active?user_id=XXX
  POST /api/v1/user/create
  POST /api/v1/user/update
  GET  /api/v1/user/list
  POST /api/v1/user/delete

OUR EXTENSIONS (AdsPower doesn't have these):
  GET  /api/v1/user/<id>/preview     — fingerprint preview
  POST /api/v1/user/<id>/cookies     — cookie import
  GET  /api/v1/features              — list our 47 fingerprint techniques
"""
import argparse
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from flask import Flask, request, jsonify

import profiles as pm
import backup

api = Flask(__name__)

# P-04: batas ukuran upload/request body (Flask -> 413 bila lewat).
api.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

# Optional API key auth. Set via --api-key (managed from GUI Settings).
API_KEY = ""
# /api/v1/status stays open so tools can health-check without a key.
_PUBLIC_PATHS = {"/api/v1/status"}


@api.before_request
def _check_api_key():
    if not API_KEY:
        return None
    if request.path in _PUBLIC_PATHS:
        return None
    key = request.headers.get("X-API-Key") or request.args.get("api_key", "")
    if key != API_KEY:
        return jsonify({"code": 401, "msg": "invalid or missing api key"}), 401
    return None

# P-12: TIDAK ADA lagi _sessions di proses ini. Satu-satunya registry sesi
# adalah sessions.json + liveness check (launcher.list_running()). Proses
# Local API yang di-restart, atau browser yang di-launch lewat GUI/CLI,
# sebelumnya tidak terlihat di sini (_sessions kosong -> "Inactive" palsu).


def _ok(data=None, msg="success"):
    r = {"code": 0, "msg": msg}
    if data is not None:
        r["data"] = data
    return jsonify(r)


def _err(msg, code=-1):
    return jsonify({"code": code, "msg": msg}), 400


# ── Status ──
@api.route("/api/v1/status", methods=["GET"])
def status():
    # P-12: hitung dari registry hidup, bukan dari dict in-memory proses ini.
    try:
        running = len(_launcher().list_running())
    except Exception:
        running = 0
    return _ok({"running_profiles": running, "total_profiles": len(pm.list_profiles())})


# ── Browser control ──
def _launcher():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "antibrowser_launcher",
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "launcher", "launcher.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@api.route("/api/v1/browser/start", methods=["GET"])
def browser_start():
    user_id = request.args.get("user_id")
    if not user_id:
        return _err("user_id required")
    p = pm.get_profile(user_id)
    if not p:
        return _err(f"profile {user_id} not found")
    # P-14: parameter headless (?headless=true) — default False = headful.
    # AdsPower Local API mendukung param yang sama.
    headless = request.args.get("headless", "false").strip().lower() in (
        "1", "true", "yes", "on")
    # Real launch: Chromium + fingerprint injection. Same response shape
    # as AdsPower Local API so existing scripts keep working.
    try:
        launcher = _launcher()
        sess = launcher.launch_profile(p, headless=headless)
    except Exception as e:
        return _err(f"launch failed: {e}")
    pm.update_profile(user_id, {"status": "running"})
    return _ok({
        "ws": {"selenium": sess["webdriver"], "puppeteer": sess["ws_url"]},
        "debug_port": sess["debug_port"],
        "webdriver": sess["webdriver"],
        "headless": sess["headless"],
        # P-15: ringkasan inject cookie (terverifikasi baca-balik daemon).
        "cookies": {"total": sess.get("cookies_total", 0),
                    "injected": sess.get("cookies_injected", 0),
                    "failed": sess.get("cookies_failed", 0)},
    })


@api.route("/api/v1/browser/fingerprint-check", methods=["GET"])
def browser_fingerprint_check():
    """P-18: baca fingerprint LIVE dari browser yang jalan + bandingkan
    dengan identity profil. Bukan klaim config — bukti dari halaman."""
    user_id = request.args.get("user_id")
    if not user_id:
        return _err("user_id required")
    p = pm.get_profile(user_id)
    if not p:
        return _err(f"profile {user_id} not found")
    try:
        sess = _launcher().list_running().get(user_id)
    except Exception:
        sess = None
    if not sess:
        return _err("browser tidak jalan — launch dulu")
    rpa_mod = _rpa()
    if rpa_mod is None:
        return _err("modul rpa tidak ditemukan")
    # P-18: identity HARUS yang tercatat saat launch (identity.json) —
    # build ulang memberi identitas random lain (FAIL palsu).
    ident = _launcher().get_launched_identity(user_id)
    if not ident:
        return _err("identity launch tidak tercatat — relaunch profil ini dulu")
    try:
        result = rpa_mod.check_fingerprint(sess["debug_port"], ident)
    except Exception as e:
        return _err(f"fingerprint-check gagal: {e}")
    return _ok(result)


# ── RPA sederhana (P-18) ──────────────────────────────────────────────────
def _rpa():
    """Muat launcher/rpa.py (seperti _launcher() — launcher/ tidak ada
    di sys.path proses GUI). F5-2: via rpa_loader (di-cache per proses)
    supaya state modul bertahan antar request. Return modul atau None."""
    try:
        import rpa_loader
        return rpa_loader.load_rpa()
    except Exception:
        return None


def _rpa_port(user_id):
    """debug_port profil yang jalan, atau None."""
    try:
        sess = _launcher().list_running().get(user_id)
    except Exception:
        return None
    return sess["debug_port"] if sess else None


@api.route("/api/v1/rpa/run", methods=["POST"])
def rpa_run():
    """P-18: jalankan langkah RPA di browser yang jalan.
    Body: {"user_id", "steps": [...]} atau {"user_id", "flow": "nama"}.
    Langkah: goto{url} / wait{ms} / click{selector} / type{selector,text} /
    scroll{delta_y} / press{key}. Satu langkah gagal tidak menghentikan run."""
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return _err("user_id required")
    rpa_mod = _rpa()
    if rpa_mod is None:
        return _err("modul rpa tidak ditemukan")
    steps = data.get("steps")
    if steps is None and data.get("flow"):
        try:
            steps = rpa_mod.get_flow(data["flow"])["steps"]
        except KeyError as e:
            return _err(str(e))
    if steps is None:
        return _err("steps atau flow wajib diisi")
    port = _rpa_port(user_id)
    if not port:
        return _err("browser tidak jalan — launch dulu")
    try:
        steps = rpa_mod.validate_steps(steps)
    except ValueError as e:
        return _err(f"steps tidak valid: {e}")
    try:
        result = rpa_mod.run_steps(port, steps,
                                   timeout=int(data.get("timeout", 120)))
    except Exception as e:
        return _err(f"rpa gagal: {e}")
    return _ok(result)


@api.route("/api/v1/rpa/flows", methods=["GET", "POST"])
def rpa_flows():
    """P-18: simpan (POST {"name", "steps"}) / daftar (GET) alur RPA."""
    rpa_mod = _rpa()
    if rpa_mod is None:
        return _err("modul rpa tidak ditemukan")
    if request.method == "GET":
        flows = rpa_mod.list_flows()
        return _ok({"flows": [{"name": f["name"],
                               "steps": len(f["steps"]),
                               "updated_at": f.get("updated_at")}
                              for f in flows.values()]})
    data = request.get_json(force=True, silent=True) or {}
    try:
        flow = rpa_mod.save_flow(data.get("name"), data.get("steps"))
    except (ValueError, KeyError) as e:
        return _err(str(e))
    return _ok({"name": flow["name"], "steps": len(flow["steps"])})


@api.route("/api/v1/rpa/flows/<name>", methods=["GET", "DELETE"])
def rpa_flow_one(name):
    rpa_mod = _rpa()
    if rpa_mod is None:
        return _err("modul rpa tidak ditemukan")
    if request.method == "GET":
        try:
            return _ok(rpa_mod.get_flow(name))
        except KeyError as e:
            return _err(str(e))
    try:
        rpa_mod.delete_flow(name)
    except KeyError as e:
        return _err(str(e))
    return _ok()


@api.route("/api/v1/rpa/templates", methods=["GET"])
def rpa_templates():
    """F5-3: daftar template alur per platform."""
    rpa_mod = _rpa()
    if rpa_mod is None:
        return _err("modul rpa tidak ditemukan")
    return _ok({"templates": [
        {"key": k, **v} for k, v in rpa_mod.list_templates().items()]})


@api.route("/api/v1/rpa/templates/<key>", methods=["GET"])
def rpa_template_one(key):
    """F5-1: satu template lengkap (untuk builder Alur)."""
    rpa_mod = _rpa()
    if rpa_mod is None:
        return _err("modul rpa tidak ditemukan")
    try:
        return _ok(rpa_mod.get_template(key))
    except KeyError as e:
        return _err(str(e))


@api.route("/api/v1/rpa/templates/<key>/install", methods=["POST"])
def rpa_template_install(key):
    """F5-3: salin template jadi alur tersimpan. Body: {"name": ...}."""
    rpa_mod = _rpa()
    if rpa_mod is None:
        return _err("modul rpa tidak ditemukan")
    data = request.get_json(force=True, silent=True) or {}
    try:
        flow = rpa_mod.install_template(key, data.get("name"))
    except KeyError as e:
        return _err(str(e))
    except ValueError as e:
        return _err(str(e))
    return _ok({"name": flow["name"], "steps": len(flow["steps"]),
                "template": flow.get("template")})


@api.route("/api/v1/rpa/run-multi", methods=["POST"])
def rpa_run_multi():
    """F5-4: jalankan satu alur di banyak profil (job async).
    Body: {"flow": "nama"} atau {"steps": [...]},
    {"profile_ids": [...]}."""
    import rpa_jobs as rj
    rpa_mod = _rpa()
    if rpa_mod is None:
        return _err("modul rpa tidak ditemukan")
    data = request.get_json(force=True, silent=True) or {}
    steps = data.get("steps")
    flow_name = data.get("flow") or "(langkah langsung)"
    if steps is None and data.get("flow"):
        try:
            steps = rpa_mod.get_flow(data["flow"])["steps"]
        except KeyError as e:
            return _err(str(e))
    profile_ids = data.get("profile_ids") or []
    if not isinstance(profile_ids, list) or not profile_ids:
        return _err("profile_ids wajib list tidak kosong")
    if len(profile_ids) > 50:
        return _err("maks 50 profil per job")
    try:
        steps = rpa_mod.validate_steps(steps)
    except ValueError as e:
        return _err(f"steps tidak valid: {e}")
    job = rj.start_multi_job(flow_name, steps, profile_ids,
                             _launcher(), rpa_mod, pm)
    return _ok({"job_id": job["job_id"], "total": job["total"]})


@api.route("/api/v1/rpa/jobs", methods=["GET"])
def rpa_jobs_list():
    """F5-4: daftar job multi-profil (terbaru dulu)."""
    import rpa_jobs as rj
    return _ok({"jobs": rj.list_jobs()})


@api.route("/api/v1/rpa/jobs/<job_id>", methods=["GET"])
def rpa_job_one(job_id):
    """F5-4: status satu job multi-profil."""
    import rpa_jobs as rj
    job = rj.get_job(job_id)
    if not job:
        return _err("job tidak ditemukan")
    return _ok({"job": job})


@api.route("/api/v1/rpa/jobs/<job_id>/cancel", methods=["POST"])
def rpa_job_cancel(job_id):
    """F5-4: minta job multi-profil berhenti (dicek antar profil)."""
    import rpa_jobs as rj
    job = rj.cancel_job(job_id)
    if not job:
        return _err("job tidak ditemukan")
    return _ok({"job": job})


def _sync():
    """Muat launcher/sync.py (seperti _rpa()). Return modul atau None."""
    try:
        import importlib.util
        sync_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "launcher", "sync.py")
        spec = importlib.util.spec_from_file_location("antibrowser_sync",
                                                      sync_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


# ── Synchronizer / Cermin (F3-2) — nama rute mengikuti AdsPower /sync/* ──
@api.route("/api/v1/sync/toSyncOperateBrowser", methods=["POST"])
def sync_start():
    """Mulai sesi cermin. Body: {user_id (leader), follower_ids?,
    open_delay_ms?}."""
    data = request.get_json(force=True, silent=True) or {}
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    if not data.get("user_id"):
        return _err("user_id (leader) required")
    try:
        state = mod.start_sync(data["user_id"],
                               follower_ids=data.get("follower_ids"),
                               open_delay_ms=data.get("open_delay_ms", 0))
    except ValueError as e:
        return _err(str(e))
    return _ok(state)


@api.route("/api/v1/sync/toStopSyncOperateBrowser", methods=["POST"])
def sync_stop():
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    return _ok(mod.stop_sync())


@api.route("/api/v1/sync/getOperateBrowser", methods=["GET"])
def sync_status():
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    return _ok(mod.get_state())


@api.route("/api/v1/sync/toInputTxt", methods=["POST"])
def sync_input():
    """Ketik teks di semua jendela. Body: {text, selector?}."""
    data = request.get_json(force=True, silent=True) or {}
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    try:
        return _ok(mod.input_text(data.get("text"), selector=data.get("selector")))
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/sync/toRefreshTab", methods=["POST"])
def sync_refresh():
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    try:
        return _ok(mod.refresh_all())
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/sync/toRangeBrowser", methods=["POST"])
def sync_range():
    """Body: {range: "all"|"selected", follower_ids?}."""
    data = request.get_json(force=True, silent=True) or {}
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    try:
        return _ok(mod.set_range(data.get("range", "all"),
                                 follower_ids=data.get("follower_ids")))
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/sync/toOpenDelay", methods=["POST"])
def sync_delay():
    """Body: {ms} — jeda antar-jendela saat aksi dicerminkan."""
    data = request.get_json(force=True, silent=True) or {}
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    try:
        return _ok(mod.set_open_delay(data.get("ms", 0)))
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/sync/toShowBrowser", methods=["POST"])
def sync_show():
    """Body: {user_id} — aktifkan tab pertama jendela itu."""
    data = request.get_json(force=True, silent=True) or {}
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    if not data.get("user_id"):
        return _err("user_id required")
    try:
        return _ok(mod.show_browser(data["user_id"]))
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/sync/manageUrlTab", methods=["GET", "POST"])
def sync_tabs():
    """Kelola tab. GET ?user_id= -> daftar tab. POST {user_id,
    action: "open"|"close"|"activate", url?, target_id?}."""
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    if request.method == "GET":
        user_id = request.args.get("user_id")
        if not user_id:
            return _err("user_id required")
        try:
            return _ok({"tabs": mod.list_tabs(user_id)})
        except ValueError as e:
            return _err(str(e))
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id")
    action = (data.get("action") or "").lower()
    if not user_id:
        return _err("user_id required")
    try:
        if action == "open":
            return _ok(mod.open_tab(user_id, data.get("url")))
        if action == "close":
            return _ok({"closed": mod.close_tab(user_id, data.get("target_id"))})
        if action == "activate":
            return _ok({"activated": mod.activate_tab(user_id, data.get("target_id"))})
        if action == "list":
            return _ok({"tabs": mod.list_tabs(user_id)})
    except (ValueError, RuntimeError) as e:
        return _err(str(e))
    return _err("action harus open | close | activate | list")


@api.route("/api/v1/sync/openUrl", methods=["POST"])
def sync_open_url():
    """Buka URL di halaman aktif semua jendela. Body: {url}."""
    data = request.get_json(force=True, silent=True) or {}
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    try:
        return _ok(mod.open_url(data.get("url")))
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/sync/paste", methods=["POST"])
def sync_paste():
    """Tempel (ketik) teks di halaman aktif semua jendela. Body: {text}."""
    data = request.get_json(force=True, silent=True) or {}
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    try:
        return _ok(mod.input_text(data.get("text")))
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/sync/syncSize", methods=["POST"])
def sync_size():
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    try:
        return _ok(mod.sync_size())
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/sync/getPosition", methods=["GET"])
def sync_position():
    user_id = request.args.get("user_id")
    if not user_id:
        return _err("user_id required")
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    try:
        return _ok(mod.get_position(user_id))
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/sync/resetDownload", methods=["POST"])
def sync_reset_download():
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    return _ok(mod.reset_download())


@api.route("/api/v1/sync/clear", methods=["POST"])
def sync_clear():
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    return _ok(mod.clear_log())


@api.route("/api/v1/sync/steps", methods=["POST"])
def sync_steps():
    """Ekstensi kami (AdsPower tidak punya rute ini): cerminkan daftar
    langkah RPA. Body: {steps: [...]}."""
    data = request.get_json(force=True, silent=True) or {}
    mod = _sync()
    if mod is None:
        return _err("modul sync tidak ditemukan")
    try:
        return _ok(mod.mirror_steps(data.get("steps")))
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/browser/stop", methods=["GET"])
def browser_stop():
    user_id = request.args.get("user_id")
    if not user_id:
        return _err("user_id required")
    try:
        launcher = _launcher()
        launcher.stop_profile(user_id)
    except Exception:
        pass
    pm.update_profile(user_id, {"status": "idle"})
    return _ok()


@api.route("/api/v1/browser/active", methods=["GET"])
def browser_active():
    user_id = request.args.get("user_id")
    if not user_id:
        return _err("user_id required")
    # P-12: baca registry hidup — browser yang di-launch lewat GUI/CLI
    # tetap terlihat Active di sini.
    try:
        sess = _launcher().list_running().get(user_id)
    except Exception:
        sess = None
    if sess:
        return _ok({"status": "Active", **sess})
    return _ok({"status": "Inactive"})


# ── User (profile) management ──
@api.route("/api/v1/user/create", methods=["POST"])
def user_create():
    data = request.get_json(force=True, silent=True) or {}
    # Accept AdsPower-style fields, map to our schema
    mapped = {}
    if "name" in data:
        mapped["name"] = data["name"]
    if "group_id" in data or "group" in data:
        mapped["group"] = data.get("group", data.get("group_id", "default"))
    if "fingerprint" in data:
        mapped["fingerprint"] = data["fingerprint"]
    if "proxy" in data:
        mapped["proxy"] = data["proxy"]
    if "tags" in data:
        mapped["tags"] = data["tags"]
    try:
        p = pm.create_profile(mapped)
    except ValueError as e:
        return _err(str(e))
    return _ok({"id": p["id"], "user_id": p["id"]})


@api.route("/api/v1/user/update", methods=["POST"])
def user_update():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id") or data.get("id")
    if not user_id:
        return _err("user_id required")
    p = pm.update_profile(user_id, data)
    if not p:
        return _err("profile not found")
    return _ok({"id": p["id"]})


@api.route("/api/v1/user/list", methods=["GET"])
def user_list():
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 100))
    search = request.args.get("search")
    # F3-3 (M-19): filter grup + tag — list_profiles sudah mendukung,
    # Local API yang belum meneruskannya.
    group = request.args.get("group")
    tags = request.args.get("tags")
    tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    profiles = pm.list_profiles(search=search, group=group, tags=tags)
    total = len(profiles)
    start = (page - 1) * page_size
    items = profiles[start:start + page_size]
    # P-12: status berasal dari registry hidup, bukan field tersimpan
    # (bisa basi pasca-crash). Satu sumber kebenaran untuk semua jalur.
    # P-10: injection_ok (None = tidak ada browser).
    try:
        sessions = _launcher().list_running()
    except Exception:
        sessions = {}
    live = set(sessions)
    # AdsPower-compatible shape
    return _ok({
        "list": [{"user_id": p["id"], "name": p["name"], "group": p.get("group"),
                  "tags": p.get("tags") or [],
                  "status": "running" if p["id"] in live else "idle",
                  "injection_ok": (sessions.get(p["id"], {}).get("injection_ok")
                                   if p["id"] in live else None)}
                 for p in items],
        "total": total, "page": page, "page_size": page_size,
    })


@api.route("/api/v1/user/delete", methods=["POST"])
def user_delete():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id") or data.get("id")
    if not user_id:
        return _err("user_id required")
    if pm.delete_profile(user_id):
        return _ok()
    return _err("profile not found")


# ── F3-3: v1 yang masih hilang ────────────────────────────────────────────
@api.route("/api/v1/browser/cloud-active", methods=["GET"])
def browser_cloud_active():
    """AdsPower: status browser cloud. StealthXGM mode LOKAL saja — tidak
    ada browser cloud. Jujur: selalu Inactive + cloud_supported false,
    bukan dipalsukan Active."""
    user_id = request.args.get("user_id")
    if not user_id:
        return _err("user_id required")
    return _ok({"status": "Inactive", "cloud_supported": False,
                "note": "StealthXGM mode lokal — tidak ada browser cloud"})


@api.route("/api/v1/browser/local-active", methods=["GET"])
def browser_local_active():
    """Alias browser/active (AdsPower memisah local vs cloud)."""
    return browser_active()


@api.route("/api/v1/group/create", methods=["POST"])
def group_create():
    data = request.get_json(force=True, silent=True) or {}
    try:
        g = pm.create_group(data.get("name") or data.get("group_id") or "")
    except ValueError as e:
        return _err(str(e))
    return _ok(g)


@api.route("/api/v1/group/list", methods=["GET"])
def group_list():
    return _ok({"list": pm.list_groups()})


@api.route("/api/v1/group/update", methods=["POST"])
def group_update():
    """Ganti nama grup. Body: {group_id|name, new_name}."""
    data = request.get_json(force=True, silent=True) or {}
    old = data.get("group_id") or data.get("name") or ""
    new = data.get("new_name") or data.get("group_name") or ""
    try:
        r = pm.rename_group(old, new)
    except ValueError as e:
        return _err(str(e))
    if r is None:
        return _err(f"group {old} tidak ditemukan")
    return _ok(r)


@api.route("/api/v1/user/delete-cache", methods=["POST"])
def user_delete_cache():
    """Hapus cache profil (browser harus sudah stop). Body: {user_id}."""
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id") or data.get("id")
    if not user_id:
        return _err("user_id required")
    if not pm.get_profile(user_id):
        return _err("profile not found")
    try:
        import backup as backup_mod
        return _ok(backup_mod.clear_cache(user_id))
    except RuntimeError as e:
        return _err(str(e))


@api.route("/api/v1/user/regroup", methods=["POST"])
def user_regroup():
    """Pindah profil ke grup lain. Body: {user_id, group}."""
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id") or data.get("id")
    group = data.get("group")
    if not user_id or not group:
        return _err("user_id dan group wajib diisi")
    r = pm.batch_move_group([user_id], group)
    if r["failed"]:
        return _err("profile not found")
    return _ok({"moved": r["moved"]})


@api.route("/api/v1/application/list", methods=["GET"])
def application_list():
    """Daftar aplikasi/browser terpasang yang bisa dipakai profil.

    F3-3: Chromium sistem (via launcher.find_chrome). F3-4 menambahkan
    kernel yang diunduh/didaftar di kernel manager."""
    try:
        launcher = _launcher()
        chrome = launcher.find_chrome()
        ver = launcher.get_real_chrome_version(chrome)
    except Exception as e:
        return _ok({"applications": [], "note": f"chromium tidak ditemukan: {e}"})
    apps = [{"name": "Chromium", "path": chrome, "version": ver,
             "engine": "chromium", "default": True}]
    km = _kernels()
    if km is not None:
        try:
            apps.extend(km.list_kernels())
        except Exception:
            pass
    return _ok({"applications": apps})


def _kernels():
    """Muat launcher/kernels.py (F3-4) bila ada. Return modul atau None."""
    try:
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "launcher", "kernels.py")
        if not os.path.exists(path):
            return None
        spec = importlib.util.spec_from_file_location("antibrowser_kernels",
                                                      path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


# ── F3-3: API v2 inti ─────────────────────────────────────────────────────
# v2 memakai bentuk yang sama (code/msg/data). Yang TIDAK dibangun:
# share + user/* tim (fitur server/tim AdsPower — mode lokal tidak punya),
# fb/* (platform-spesifik). Endpoint itu menjawab jelas "tidak didukung",
# bukan dipalsukan.
def _v2_profile_item(p, sessions):
    live = p["id"] in sessions
    return {"user_id": p["id"], "name": p["name"],
            "group": p.get("group"), "tags": p.get("tags") or [],
            "status": "running" if live else "idle",
            "injection_ok": (sessions.get(p["id"], {}).get("injection_ok")
                             if live else None),
            "updated_at": p.get("updated_at")}


def _v2_sessions():
    try:
        return _launcher().list_running()
    except Exception:
        return {}


@api.route("/api/v2/browser-profile/list", methods=["GET"])
def v2_profile_list():
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 100))
    group = request.args.get("group")
    search = request.args.get("search")
    tags = request.args.get("tags")
    tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    profiles = pm.list_profiles(search=search, group=group, tags=tags)
    total = len(profiles)
    start = (page - 1) * page_size
    items = profiles[start:start + page_size]
    sessions = _v2_sessions()
    return _ok({"list": [_v2_profile_item(p, sessions) for p in items],
                "total": total, "page": page, "page_size": page_size})


@api.route("/api/v2/browser-profile/create", methods=["POST"])
def v2_profile_create():
    data = request.get_json(force=True, silent=True) or {}
    mapped = {}
    for k in ("name", "group", "notes", "tags", "fingerprint", "proxy",
              "warp_fallback"):
        if k in data:
            mapped[k] = data[k]
    try:
        p = pm.create_profile(mapped)
    except ValueError as e:
        return _err(str(e))
    return _ok({"id": p["id"], "user_id": p["id"]})


@api.route("/api/v2/browser-profile/update", methods=["POST"])
def v2_profile_update():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id") or data.get("id")
    if not user_id:
        return _err("user_id required")
    try:
        p = pm.update_profile(user_id, data)
    except ValueError as e:
        return _err(str(e))
    if not p:
        return _err("profile not found")
    return _ok({"id": p["id"]})


@api.route("/api/v2/browser-profile/update-patch", methods=["POST"])
def v2_profile_update_patch():
    """Alias update (partial — field yang dikirim saja yang diubah)."""
    return v2_profile_update()


@api.route("/api/v2/browser-profile/delete", methods=["POST"])
def v2_profile_delete():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id") or data.get("id")
    if not user_id:
        return _err("user_id required")
    if pm.delete_profile(user_id):
        return _ok()
    return _err("profile not found")


def _v2_start(user_id, headless):
    p = pm.get_profile(user_id)
    if not p:
        return None, _err(f"profile {user_id} not found")
    try:
        launcher = _launcher()
        sess = launcher.launch_profile(p, headless=headless)
    except Exception as e:
        return None, _err(f"launch failed: {e}")
    pm.update_profile(user_id, {"status": "running"})
    return sess, _ok({
        "ws": {"selenium": sess["webdriver"], "puppeteer": sess["ws_url"]},
        "debug_port": sess["debug_port"],
        "webdriver": sess["webdriver"],
        "headless": sess["headless"],
        "cookies": {"total": sess.get("cookies_total", 0),
                    "injected": sess.get("cookies_injected", 0),
                    "failed": sess.get("cookies_failed", 0)},
    })


@api.route("/api/v2/browser-profile/start", methods=["GET", "POST"])
def v2_profile_start():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        user_id = data.get("user_id")
        headless = data.get("headless", False)
    else:
        user_id = request.args.get("user_id")
        headless = request.args.get("headless", "false")
    if not user_id:
        return _err("user_id required")
    if isinstance(headless, str):
        headless = headless.strip().lower() in ("1", "true", "yes", "on")
    _sess, resp = _v2_start(user_id, bool(headless))
    return resp


@api.route("/api/v2/browser-profile/stop", methods=["GET", "POST"])
def v2_profile_stop():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        user_id = data.get("user_id")
    else:
        user_id = request.args.get("user_id")
    if not user_id:
        return _err("user_id required")
    try:
        _launcher().stop_profile(user_id)
    except Exception:
        pass
    pm.update_profile(user_id, {"status": "idle"})
    return _ok()


@api.route("/api/v2/browser-profile/stop-all", methods=["POST"])
def v2_profile_stop_all():
    sessions = _v2_sessions()
    stopped, failed = [], []
    for pid in list(sessions):
        try:
            _launcher().stop_profile(pid)
            pm.update_profile(pid, {"status": "idle"})
            stopped.append(pid)
        except Exception:
            failed.append(pid)
    return _ok({"stopped": stopped, "failed": failed})


@api.route("/api/v2/browser-profile/active", methods=["GET"])
def v2_profile_active():
    user_id = request.args.get("user_id")
    if not user_id:
        return _err("user_id required")
    sess = _v2_sessions().get(user_id)
    if sess:
        return _ok({"status": "Active", **sess})
    return _ok({"status": "Inactive"})


@api.route("/api/v2/browser-profile/cookies", methods=["GET", "POST"])
def v2_profile_cookies():
    """GET ?user_id= -> cookie tersimpan profil.
    POST {user_id, cookies: [...]} -> simpan dengan validasi PER-COOKIE
    (P-15): cookie buruk ditolak + dilaporkan alasannya, bukan dibuang diam."""
    if request.method == "GET":
        user_id = request.args.get("user_id")
        if not user_id:
            return _err("user_id required")
        p = pm.get_profile(user_id)
        if not p:
            return _err("profile not found")
        return _ok({"cookies": p.get("cookies", [])})
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id")
    cookies = data.get("cookies", [])
    if not user_id:
        return _err("user_id required")
    if not pm.get_profile(user_id):
        return _err("profile not found")
    try:
        launcher = _launcher()
        report = launcher.validate_cookies(cookies)
    except Exception as e:
        return _err(f"validasi cookie gagal: {e}")
    pm.update_profile(user_id, {"cookies": report["accepted"]})
    return _ok({"saved": len(report["accepted"]),
                "rejected": report["rejected"],
                "notes": report["notes"]})


@api.route("/api/v2/browser-profile/new-fingerprint", methods=["POST"])
def v2_profile_new_fingerprint():
    """Generate identitas BARU untuk profil + simpan (bekukan). Berlaku
    mulai launch berikutnya (browser yang sedang jalan tidak berubah).
    Body: {user_id}."""
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return _err("user_id required")
    p = pm.get_profile(user_id)
    if not p:
        return _err("profile not found")
    try:
        import fingerprint_gen as fg
        fp = p.get("fingerprint", {}) or {}
        os_name = (fp.get("platform") or "windows").lower()
        ident = fg.generate_random(
            os_name, timezone=fp.get("timezone") or "Asia/Jakarta",
            locale=fp.get("locale"))
        ident = fg.to_jsonable(ident)
    except Exception as e:
        return _err(f"gagal generate fingerprint: {e}")
    pm.update_profile(user_id, {"fingerprint": {"identity": ident}})
    return _ok({"user_id": user_id, "identity": ident,
                "note": "berlaku mulai launch berikutnya"})


@api.route("/api/v2/browser-profile/ua", methods=["GET"])
def v2_profile_ua():
    """User-Agent profil: dari identity yang sedang jalan / tersimpan.
    Tanpa identity -> error jelas (jangan tampilkan UA contoh acak)."""
    user_id = request.args.get("user_id")
    if not user_id:
        return _err("user_id required")
    if not pm.get_profile(user_id):
        return _err("profile not found")
    try:
        launcher = _launcher()
        ident = launcher.get_launched_identity(user_id)
    except Exception:
        ident = None
    if not ident:
        p = pm.get_profile(user_id)
        ident = (p.get("fingerprint") or {}).get("identity") or {}
    ua = (ident or {}).get("_ua")
    if not ua:
        return _err("profil belum punya identity — launch dulu atau "
                    "POST /api/v2/browser-profile/new-fingerprint")
    return _ok({"user_id": user_id, "user_agent": ua})


@api.route("/api/v2/browser-profile/kernels", methods=["GET"])
def v2_profile_kernels():
    """Daftar kernel browser (F3-3: Chromium sistem; F3-4: + kernel
    manager — unduh/ganti versi)."""
    try:
        launcher = _launcher()
        chrome = launcher.find_chrome()
        ver = launcher.get_real_chrome_version(chrome)
        out = [{"id": "system", "name": "Chromium (sistem)",
                "path": chrome, "version": ver, "engine": "chromium",
                "default": True}]
    except Exception as e:
        out = []
        ver = None
    km = _kernels()
    if km is not None:
        try:
            out.extend(km.list_kernels())
        except Exception:
            pass
    return _ok({"kernels": out})


@api.route("/api/v2/browser-profile/delete-cache", methods=["POST"])
def v2_profile_delete_cache():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id") or data.get("id")
    if not user_id:
        return _err("user_id required")
    if not pm.get_profile(user_id):
        return _err("profile not found")
    try:
        import backup as backup_mod
        return _ok(backup_mod.clear_cache(user_id))
    except RuntimeError as e:
        return _err(str(e))


@api.route("/api/v2/browser-profile/download-kernel", methods=["POST"])
def v2_download_kernel():
    """F3-4: unduh kernel Chromium (Chrome for Testing) di latar.
    Body: {version?} (kosong = terbaru). Return job — pantau via
    .../download-kernel/status?job_id=. Unduhan ~130 MB, butuh menit."""
    data = request.get_json(force=True, silent=True) or {}
    km = _kernels()
    if km is None:
        return _err("modul kernel tidak ditemukan")
    job = km.start_download(data.get("version"))
    return _ok(job)


@api.route("/api/v2/browser-profile/download-kernel/status", methods=["GET"])
def v2_download_kernel_status():
    job_id = request.args.get("job_id")
    if not job_id:
        return _err("job_id required")
    km = _kernels()
    if km is None:
        return _err("modul kernel tidak ditemukan")
    try:
        return _ok(km.get_download_status(job_id))
    except KeyError as e:
        return _err(str(e))


@api.route("/api/v2/browser-profile/download-kernel/list", methods=["GET"])
def v2_download_kernel_list():
    km = _kernels()
    if km is None:
        return _err("modul kernel tidak ditemukan")
    return _ok({"jobs": km.list_downloads()})


@api.route("/api/v2/browser-profile/backup", methods=["POST"])
def v2_backup():
    """F3-5: ekspor profil ke ZIP. Body: {user_id, include_cache?}."""
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("user_id")
    if not pid:
        return _err("user_id required")
    if not pm.get_profile(pid):
        return _err(f"profile {pid} not found")
    try:
        return _ok(backup.export_profile(
            pid, include_cache=data.get("include_cache", True)))
    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        return _err(str(e))


@api.route("/api/v2/browser-profile/backup-list", methods=["GET"])
def v2_backup_list():
    """F3-5: daftar backup."""
    return _ok({"backups": backup.list_backups()})


@api.route("/api/v2/browser-profile/restore-backup", methods=["POST"])
def v2_restore_backup():
    """F3-5: restore backup jadi profil BARU.
    Body: {file (nama file di folder backups), new_name?}."""
    data = request.get_json(force=True, silent=True) or {}
    fname = data.get("file")
    if not fname or "/" in fname or ".." in fname:
        return _err("file (nama backup) required")
    fpath = os.path.join(backup._backups_root(), fname)
    try:
        r = backup.restore_profile(fpath,
                                   new_name=data.get("new_name") or None)
        return _ok({"profile": r["profile"],
                    "restored_files": r["restored_files"],
                    "from_backup": r["from_backup"],
                    "exported_at": r["exported_at"]})
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/user/backup-list", methods=["GET"])
def v1_backup_list():
    """F3-5 (v1): daftar backup."""
    return _ok({"backups": backup.list_backups()})


@api.route("/api/v1/user/backup", methods=["POST"])
def v1_backup():
    """F3-5 (v1): ekspor profil ke ZIP. Body: {user_id, include_cache?}."""
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("user_id")
    if not pid:
        return _err("user_id required")
    if not pm.get_profile(pid):
        return _err(f"profile {pid} not found")
    try:
        return _ok(backup.export_profile(
            pid, include_cache=data.get("include_cache", True)))
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v1/user/restore-backup", methods=["POST"])
def v1_restore_backup():
    """F3-5 (v1): restore backup jadi profil BARU. Body: {file, new_name?}."""
    data = request.get_json(force=True, silent=True) or {}
    fname = data.get("file")
    if not fname or "/" in fname or ".." in fname:
        return _err("file (nama backup) required")
    fpath = os.path.join(backup._backups_root(), fname)
    try:
        r = backup.restore_profile(fpath,
                                   new_name=data.get("new_name") or None)
        return _ok({"profile": r["profile"],
                    "restored_files": r["restored_files"],
                    "from_backup": r["from_backup"],
                    "exported_at": r["exported_at"]})
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v2/browser-profile/batch-import", methods=["POST"])
def v2_batch_import():
    """F3-6: impor batch asinkron. Body: {content, format: csv|json}.
    Return job_id — pantau via batch-job."""
    data = request.get_json(force=True, silent=True) or {}
    content = data.get("content", "")
    fmt = (data.get("format") or "").lower()
    if not content or not content.strip():
        return _err("content required")
    try:
        import batch_import as bi
        job = bi.start_import_job(content, fmt)
    except ValueError as e:
        return _err(str(e))
    return _ok({"job_id": job["job_id"], "total": job["total"]})


@api.route("/api/v2/browser-profile/batch-export", methods=["POST"])
def v2_batch_export():
    """F3-6: ekspor batch asinkron. Body: {format?, group?, ids?}."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        import batch_import as bi
        job = bi.start_export_job(ids=data.get("ids"),
                                  fmt=(data.get("format") or "csv").lower(),
                                  group=data.get("group"))
    except ValueError as e:
        return _err(str(e))
    return _ok({"job_id": job["job_id"], "total": job["total"]})


@api.route("/api/v2/browser-profile/batch-job/<job_id>", methods=["GET"])
def v2_batch_job(job_id):
    """F3-6: status job batch."""
    import batch_import as bi
    job = bi.get_job(job_id)
    if not job:
        return _err("job tidak ditemukan")
    return _ok({"job": job})


@api.route("/api/v2/browser-profile/batch-job/<job_id>/cancel", methods=["POST"])
def v2_batch_job_cancel(job_id):
    """F3-6: batalkan job batch."""
    import batch_import as bi
    job = bi.cancel_job(job_id)
    if not job:
        return _err("job tidak ditemukan")
    return _ok({"job": job})


@api.route("/api/v1/user/batch-import", methods=["POST"])
def v1_batch_import():
    """F3-6 (v1): impor batch asinkron. Body: {content, format}."""
    data = request.get_json(force=True, silent=True) or {}
    content = data.get("content", "")
    fmt = (data.get("format") or "").lower()
    if not content or not content.strip():
        return _err("content required")
    try:
        import batch_import as bi
        job = bi.start_import_job(content, fmt)
    except ValueError as e:
        return _err(str(e))
    return _ok({"job_id": job["job_id"], "total": job["total"]})


@api.route("/api/v1/user/batch-job/<job_id>", methods=["GET"])
def v1_batch_job(job_id):
    """F3-6 (v1): status job batch."""
    import batch_import as bi
    job = bi.get_job(job_id)
    if not job:
        return _err("job tidak ditemukan")
    return _ok({"job": job})


@api.route("/api/v2/browser-profile/extensions", methods=["GET"])
def v2_extensions():
    """F3-7: daftar extension library (beserta risk + pin)."""
    import extension_manager as em
    return _ok({"extensions": em.list_extensions()})


@api.route("/api/v2/browser-profile/extensions/<eid>/pin", methods=["POST"])
def v2_ext_pin(eid):
    """F3-7: kunci extension ke satu versi. Body: {version?}."""
    data = request.get_json(force=True, silent=True) or {}
    import extension_manager as em
    try:
        info = em.pin_version(eid, data.get("version"))
    except ValueError as e:
        return _err(str(e))
    return _ok({"extension": info})


@api.route("/api/v2/browser-profile/extensions/<eid>/pin", methods=["DELETE"])
def v2_ext_unpin(eid):
    """F3-7: lepas kunci versi."""
    import extension_manager as em
    try:
        info = em.unpin_version(eid)
    except ValueError as e:
        return _err(str(e))
    return _ok({"extension": info})


@api.route("/api/v2/browser-profile/share", methods=["POST"])
def v2_profile_share():
    """Tidak didukung — berbagi profil adalah fitur tim/server AdsPower;
    StealthXGM mode lokal satu pengguna."""
    return _err("browser-profile/share tidak didukung "
                "(fitur tim — mode lokal saja)")


@api.route("/api/v2/browser-tags/list", methods=["GET"])
def v2_tags_list():
    return _ok({"list": pm.list_tags()})


@api.route("/api/v2/browser-tags/create", methods=["POST"])
def v2_tags_create():
    """Validasi nama tag. Tag terbentuk saat dipakai profil (tidak ada
    registry tag terpisah) — endpoint ini mengunci ejaan yang valid."""
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return _err("name wajib diisi")
    if len(name) > pm.MAX_TAG_LENGTH:
        return _err(f"tag terlalu panjang (maks {pm.MAX_TAG_LENGTH})")
    return _ok({"name": name,
                "note": "tag terbentuk saat dipakai oleh profil"})


@api.route("/api/v2/browser-tags/update", methods=["POST"])
def v2_tags_update():
    """Ganti nama tag di semua profil. Body: {name, new_name}."""
    data = request.get_json(force=True, silent=True) or {}
    old = data.get("name") or ""
    new = data.get("new_name") or ""
    try:
        return _ok(pm.rename_tag(old, new))
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v2/browser-tags/delete", methods=["POST"])
def v2_tags_delete():
    """Hapus tag dari semua profil. Body: {name}."""
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name") or ""
    return _ok(pm.delete_tag(name))


@api.route("/api/v2/category/list", methods=["GET"])
def v2_category_list():
    """Kategori = grup profil (AdsPower memisah category/user-group;
    di sini keduanya memetakan ke grup)."""
    return _ok({"list": pm.list_groups()})


@api.route("/api/v2/user-group/list", methods=["GET"])
def v2_user_group_list():
    return _ok({"list": pm.list_groups()})


@api.route("/api/v2/proxy-list/list", methods=["GET"])
def v2_proxy_list():
    import proxy_pools as pp
    return _ok({"list": pp.list_pools()})


@api.route("/api/v2/proxy-list/create", methods=["POST"])
def v2_proxy_create():
    import proxy_pools as pp
    data = request.get_json(force=True, silent=True) or {}
    try:
        return _ok({"pool": pp.create_pool(data)})
    except ValueError as e:
        return _err(str(e))


@api.route("/api/v2/proxy-list/update", methods=["POST"])
def v2_proxy_update():
    import proxy_pools as pp
    data = request.get_json(force=True, silent=True) or {}
    pool_id = data.get("id") or data.get("pool_id")
    if not pool_id:
        return _err("id wajib diisi")
    try:
        p = pp.update_pool(pool_id, data)
    except ValueError as e:
        return _err(str(e))
    if not p:
        return _err("pool not found")
    return _ok({"pool": p})


@api.route("/api/v2/proxy-list/delete", methods=["POST"])
def v2_proxy_delete():
    import proxy_pools as pp
    data = request.get_json(force=True, silent=True) or {}
    pool_id = data.get("id") or data.get("pool_id")
    if not pool_id:
        return _err("id wajib diisi")
    try:
        ok = pp.delete_pool(pool_id)
    except ValueError as e:
        return _err(str(e))
    if not ok:
        return _err("pool not found")
    return _ok()


@api.route("/api/v2/user/list", methods=["GET"])
def v2_user_list():
    """Mode lokal satu pengguna — tidak ada manajemen tim."""
    return _ok({"list": [{"user_id": "local", "name": "Local Owner",
                          "role": "owner",
                          "note": "mode lokal — tanpa tim"}]})


@api.route("/api/v2/user/create", methods=["POST"])
@api.route("/api/v2/user/update", methods=["POST"])
@api.route("/api/v2/user/delete", methods=["POST"])
@api.route("/api/v2/user/reset_password", methods=["POST"])
def v2_user_not_supported():
    return _err("manajemen user tim tidak didukung (mode lokal saja)")


# ── OUR EXTENSIONS ──
@api.route("/api/v1/features", methods=["GET"])
def features():
    """Our 47 fingerprint techniques (AdsPower doesn't expose this)."""
    return _ok({
        "total": len(pm.FEATURE_FLAGS),
        "categories": pm.FLAG_CATEGORIES,
    })


@api.route("/api/v1/user/<user_id>/preview", methods=["GET"])
def user_preview(user_id):
    """Fingerprint preview without launching browser (P-02).

    Dulu preview generate identitas acak baru dan mengabaikan identity
    tersimpan. Sekarang memakai launcher.build_fingerprint_js() yang sama
    dengan launch, jadi js_length + identity persis yang akan di-inject.
    Bila belum ada identity tersimpan, launch generate acak tiap kali —
    preview menandainya (identity_stored=false)."""
    p = pm.get_profile(user_id)
    if not p:
        return _err("profile not found")
    try:
        launcher = _launcher()
        js, ident = launcher.build_fingerprint_js(p)
        fp = p["fingerprint"]
        features = {k: v for k, v in fp.get("features", {}).items() if v}
        stored = bool(fp.get("identity"))
        out = {
            "identity": {k: str(v)[:80] for k, v in ident.items()},
            "identity_stored": stored,
            "js_length": len(js),
            "features_enabled": len(features),
            "warp_fallback": p.get("warp_fallback"),
        }
        if not stored:
            out["note"] = ("belum tersimpan — preview ini contoh identitas yang "
                           "akan digenerate saat launch (acak tiap launch sampai disimpan)")
        return _ok(out)
    except Exception as e:
        return _err(str(e))


def run(port=50325, debug=False, api_key=""):
    global API_KEY
    # P-04: key bisa dari argumen, atau dari environment STEALTHXGM_API_KEY
    # (cara start_api() mengopernya — jangan via argv, ps bisa baca).
    API_KEY = api_key or os.environ.get("STEALTHXGM_API_KEY", "")
    # P-06: bersihkan sesi basi (browser mati/crash/VM restart) saat start.
    try:
        n = _launcher().prune_stale_sessions()
        if n:
            print(f"[API] {n} sesi basi dibersihkan")
    except Exception:
        pass
    # P-12: rapikan field status di profiles.json dari registry hidup.
    try:
        _launcher().sync_profile_statuses(pm)
    except Exception:
        pass
    auth = " + api-key" if API_KEY else ""
    print(f"[API] Local REST API (AdsPower-compatible) on http://127.0.0.1:{port}{auth}")
    api.run(host="127.0.0.1", port=port, debug=debug)


def run_background(port=50325, api_key=""):
    t = threading.Thread(target=run, kwargs={"port": port, "api_key": api_key},
                         daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=50325)
    p.add_argument("--api-key", default="")
    a = p.parse_args()
    # P-04: --api-key boleh kosong — key dibaca dari environment bila ada.
    run(port=a.port, api_key=a.api_key or os.environ.get("STEALTHXGM_API_KEY", ""))
