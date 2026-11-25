"""GUI Profile Manager — Flask app on port 5200.

Mobile-friendly (Gil uses OPPO A78). Vanilla JS, no build step.
Serves both the GUI and proxies to the Local REST API.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, make_response
import auth as gui_auth

import profiles as pm
import proxy_pools as pp
import backup
import batch_import as bi
import rpa_jobs as rj
import extension_manager as em
import fingerprint_gen as fg
import api_config as ac

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))

# P-04: batas ukuran upload/request body (Flask -> 413 bila lewat).
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB


# ── P-04: CSRF / Origin check ─────────────────────────────────────────────
@app.before_request
def _check_origin():
    """Tolak request browser lintas-origin (CSRF localhost).

    Ancaman: situs web mana pun yang dibuka di browser bisa mengirim request
    ke http://127.0.0.1:5200 (baca/tulis profil, proxy, cookies) — SOP
    memblokir MEMBACA respons, tapi request-nya tetap jalan.
    Aturan: request browser selalu membawa Origin (POST) dan/atau Referer.
    - Ada Origin -> harus sama dengan Host request ini.
    - Tidak ada Origin tapi ada Referer -> Referer harus sama dengan Host.
    - Tidak ada keduanya -> klien non-browser (curl/python/automation),
      diizinkan. Ini tradeoff yang disengaja: serangan CSRF dari browser
      selalu membawa salah satu header itu.
    """
    from urllib.parse import urlparse
    origin = request.headers.get("Origin")
    if origin:
        try:
            netloc = urlparse(origin).netloc
        except Exception:
            return jsonify({"error": "forbidden: bad Origin"}), 403
        if not netloc or netloc != request.host:
            return jsonify({"error": "forbidden: cross-origin request"}), 403
        return None
    referer = request.headers.get("Referer")
    if referer:
        try:
            netloc = urlparse(referer).netloc
        except Exception:
            return jsonify({"error": "forbidden: bad Referer"}), 403
        if not netloc or netloc != request.host:
            return jsonify({"error": "forbidden: cross-origin request"}), 403
    return None


# ── Pages ──
@app.route("/")
def index():
    return render_template("index.html")


# ── Login GUI (F3-8, follow-up P-04) ──────────────────────────────────────
@app.before_request
def _auth_gate():
    """Penegakan login GUI (OPT-IN — lihat gui/auth.py).

    - /api/auth/*, /login, /favicon.ico: selalu terbuka.
    - /api/* lain: bila password belum diset -> terbuka (mode lama);
      bila sudah diset -> butuh sesi (cookie sxgm_session atau header
      X-Session-Token), kalau tidak 401 JSON.
    - GET /: bila password diset & belum login -> redirect /login.
    - /static/*: terbuka (aset statis tidak mengandung data).
    """
    path = request.path
    if path.startswith("/api/auth/") or path in ("/login", "/favicon.ico"):
        return None
    if path.startswith("/api/"):
        if not gui_auth.is_setup():
            return None
        token = request.cookies.get("sxgm_session") or \
            request.headers.get("X-Session-Token")
        if token and gui_auth.validate_token(token):
            return None
        return jsonify({"ok": False, "error": "login diperlukan"}), 401
    if path == "/" and gui_auth.is_setup():
        token = request.cookies.get("sxgm_session")
        if not (token and gui_auth.validate_token(token)):
            return redirect("/login")
    return None


@app.route("/login")
def login_page():
    """Halaman login minimal (self-contained — tanpa aset eksternal)."""
    if gui_auth.is_setup():
        token = request.cookies.get("sxgm_session")
        if token and gui_auth.validate_token(token):
            return redirect("/")
    return render_template("login.html")


@app.route("/api/auth/status", methods=["GET"])
def api_auth_status():
    """Status login: setup_required? authenticated?"""
    token = request.cookies.get("sxgm_session") or \
        request.headers.get("X-Session-Token")
    authed = bool(token and gui_auth.validate_token(token))
    return jsonify({"ok": True,
                    "setup_required": not gui_auth.is_setup(),
                    "authenticated": authed,
                    "active_sessions": gui_auth.active_sessions()})


@app.route("/api/auth/setup", methods=["POST"])
def api_auth_setup():
    """Set password operator pertama. Hanya bila belum ada password.
    Body: {password} (min 8 karakter)."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        gui_auth.setup_password(data.get("password") or "")
    except ValueError as e:
        code = 403 if "sudah diset" in str(e) else 400
        return jsonify({"ok": False, "error": str(e)}), code
    return jsonify({"ok": True,
                    "message": "password diset — login kini aktif"}), 201


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    """Login. Body: {password}. 5 gagal/IP -> kunci 15 menit (429).
    Sukses: cookie httponly sxgm_session + token di JSON (untuk CLI)."""
    ip = request.remote_addr or ""
    if gui_auth.is_locked_out(ip):
        return jsonify({"ok": False,
                        "error": "terlalu banyak percobaan gagal — "
                                 "coba lagi 15 menit lagi"}), 429
    if not gui_auth.is_setup():
        return jsonify({"ok": False,
                        "error": "password belum diset — "
                                 "set dulu via /api/auth/setup"}), 400
    data = request.get_json(force=True, silent=True) or {}
    if not gui_auth.verify_password(data.get("password") or ""):
        gui_auth.record_failed(ip)
        return jsonify({"ok": False, "error": "password salah"}), 401
    gui_auth.reset_failures(ip)
    token = gui_auth.create_session(ip)
    resp = make_response(jsonify({"ok": True, "token": token}))
    resp.set_cookie("sxgm_session", token, httponly=True, samesite="Lax",
                    max_age=gui_auth.SESSION_TTL, path="/")
    return resp


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Logout: hapus sesi + cookie."""
    token = request.cookies.get("sxgm_session") or \
        request.headers.get("X-Session-Token")
    gui_auth.destroy_session(token)
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("sxgm_session", path="/")
    return resp


@app.route("/api/auth/change-password", methods=["POST"])
def api_auth_change_password():
    """Ganti password (butuh sesi + password lama). Semua sesi lama
    hangus sesudah ganti."""
    token = request.cookies.get("sxgm_session") or \
        request.headers.get("X-Session-Token")
    if gui_auth.is_setup() and not (token and gui_auth.validate_token(token)):
        return jsonify({"ok": False, "error": "login diperlukan"}), 401
    data = request.get_json(force=True, silent=True) or {}
    try:
        gui_auth.change_password(data.get("old") or "", data.get("new") or "")
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    resp = make_response(jsonify({"ok": True,
                                  "message": "password diganti — "
                                             "silakan login ulang"}))
    resp.delete_cookie("sxgm_session", path="/")
    return resp


# ── Profile API (GUI backend) ──
@app.route("/api/profiles", methods=["GET"])
def api_list():
    search = request.args.get("search")
    group = request.args.get("group")
    tags = request.args.get("tags")
    tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    profiles = pm.list_profiles(search=search, group=group, tags=tags)
    # P-12: status berasal dari registry hidup, bukan field tersimpan.
    return jsonify({"profiles": _with_live_status(profiles)})


def _with_live_status(profiles):
    """P-12: timpa field 'status' tiap profil dari registry hidup
    (sessions.json + liveness). Terima dict tunggal atau list; return
    salinan (file profiles.json tidak diubah di sini).
    P-10: sertakan 'injection_ok' — None = tidak ada browser;
    True/False = daemon injeksi jalan/mati (tanda "injeksi mati" di data,
    tanpa ubah desain GUI)."""
    try:
        sessions = _launcher().list_running()
    except Exception:
        sessions = {}
    live = set(sessions)
    single = isinstance(profiles, dict)
    items = [profiles] if single else list(profiles)
    out = []
    for p in items:
        q = dict(p)
        q["status"] = "running" if p["id"] in live else "idle"
        q["injection_ok"] = (sessions.get(p["id"], {}).get("injection_ok")
                             if p["id"] in live else None)
        out.append(q)
    return out[0] if single else out


@app.route("/api/profiles", methods=["POST"])
def api_create():
    data = request.get_json(force=True, silent=True) or {}
    p = pm.create_profile(data)
    return jsonify({"profile": p}), 201


@app.route("/api/profiles/<pid>", methods=["GET"])
def api_get(pid):
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify({"profile": _with_live_status(p)})


@app.route("/api/profiles/<pid>", methods=["PUT", "PATCH"])
def api_update(pid):
    data = request.get_json(force=True, silent=True) or {}
    p = pm.update_profile(pid, data)
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify({"profile": p})


@app.route("/api/profiles/<pid>", methods=["DELETE"])
def api_delete(pid):
    """Soft delete -> trash bin (restorable). Use /api/trash/<id> for permanent."""
    if pm.delete_profile(pid):
        return jsonify({"ok": True, "trashed": True})
    return jsonify({"error": "not found"}), 404


@app.route("/api/profiles/batch", methods=["POST"])
def api_batch():
    """Batch operations on multiple profiles.
    Body: {"action": "delete"|"move_group"|"assign_pool", "ids": [...],
            "group": "name", "pool_id": "xxx"}
    delete -> soft delete (to trash). move_group / assign_pool as named.
    """
    data = request.get_json(force=True, silent=True) or {}
    action = (data.get("action") or "").lower()
    ids = data.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "ids (list) wajib"}), 400
    if action == "delete":
        return jsonify({"ok": True, **pm.batch_delete(ids)})
    if action == "move_group":
        group = (data.get("group") or "").strip() or "default"
        return jsonify({"ok": True, **pm.batch_move_group(ids, group)})
    if action == "assign_pool":
        pool_id = data.get("pool_id") or ""
        if pool_id and not pp.get_pool(pool_id):
            return jsonify({"error": "pool tidak ditemukan"}), 404
        return jsonify({"ok": True, **pm.batch_assign_pool(ids, pool_id)})
    return jsonify({"error": "action harus delete | move_group | assign_pool"}), 400


# ── Trash bin ──
@app.route("/api/trash", methods=["GET"])
def api_trash_list():
    return jsonify({"trash": pm.list_trash(), "count": len(pm.list_trash())})


@app.route("/api/trash/<pid>/restore", methods=["POST"])
def api_trash_restore(pid):
    p = pm.restore_profile(pid)
    if not p:
        return jsonify({"error": "not found di trash"}), 404
    return jsonify({"ok": True, "profile": p})


@app.route("/api/trash/<pid>", methods=["DELETE"])
def api_trash_perm_delete(pid):
    """Permanent delete: profile + browser data dir. Cannot be undone."""
    if pm.permanent_delete(pid):
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@app.route("/api/trash/empty", methods=["POST"])
def api_trash_empty():
    n = pm.empty_trash()
    return jsonify({"ok": True, "deleted": n})


@app.route("/api/trash/cleanup", methods=["POST"])
def api_trash_cleanup():
    """Auto-delete trash items older than `days` (default 30)."""
    data = request.get_json(force=True, silent=True) or {}
    days = data.get("days", 30)
    try:
        days = int(days)
    except (TypeError, ValueError):
        return jsonify({"error": "days harus angka"}), 400
    n = pm.auto_cleanup_trash(days=max(1, days))
    return jsonify({"ok": True, "deleted": n, "days": max(1, days)})


@app.route("/api/profiles/<pid>/duplicate", methods=["POST"])
def api_duplicate(pid):
    p = pm.duplicate_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify({"profile": p}), 201


@app.route("/api/groups", methods=["GET"])
def api_groups():
    return jsonify({"groups": pm.list_groups()})


@app.route("/api/groups", methods=["POST"])
def api_groups_create():
    data = request.get_json(force=True, silent=True) or {}
    try:
        g = pm.create_group(data.get("name") or "")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"group": g}), 201


@app.route("/api/groups/<name>", methods=["PUT", "PATCH"])
def api_groups_rename(name):
    data = request.get_json(force=True, silent=True) or {}
    try:
        r = pm.rename_group(name, data.get("new_name") or "")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if r is None:
        return jsonify({"error": "group tidak ditemukan"}), 404
    return jsonify({"ok": True, **r})


@app.route("/api/groups/<name>", methods=["DELETE"])
def api_groups_delete(name):
    try:
        r = pm.delete_group(name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if r is None:
        return jsonify({"error": "group tidak ditemukan"}), 404
    return jsonify({"ok": True, **r})


# ── Tags (F3-3) ───────────────────────────────────────────────────────────
@app.route("/api/tags", methods=["GET"])
def api_tags_list():
    return jsonify({"tags": pm.list_tags()})


@app.route("/api/tags", methods=["POST"])
def api_tags_create():
    """Validasi nama tag (tag terbentuk saat dipakai profil)."""
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name wajib diisi"}), 400
    if len(name) > pm.MAX_TAG_LENGTH:
        return jsonify({"error": f"tag terlalu panjang (maks {pm.MAX_TAG_LENGTH})"}), 400
    return jsonify({"tag": {"name": name},
                    "note": "tag terbentuk saat dipakai oleh profil"}), 201


@app.route("/api/tags/<name>", methods=["PUT", "PATCH"])
def api_tags_rename(name):
    data = request.get_json(force=True, silent=True) or {}
    try:
        r = pm.rename_tag(name, data.get("new_name") or "")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, **r})


@app.route("/api/tags/<name>", methods=["DELETE"])
def api_tags_delete(name):
    return jsonify({"ok": True, **pm.delete_tag(name)})


@app.route("/api/profiles/<pid>/tags", methods=["POST", "PUT"])
def api_profile_tags(pid):
    """Timpa tag satu profil. Body: {tags: [...]}."""
    if not pm.get_profile(pid):
        return jsonify({"error": "not found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    try:
        p = pm.set_profile_tags(pid, data.get("tags"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "tags": p["tags"]})


@app.route("/api/flags", methods=["GET"])
def api_flags():
    """All fingerprint feature flags grouped by category."""
    return jsonify({
        "categories": pm.FLAG_CATEGORIES,
        "total": len(pm.FEATURE_FLAGS),
    })


# ── Proxy Pool API ──
@app.route("/api/pools", methods=["GET"])
def api_pools_list():
    active_only = request.args.get("active_only") == "1"
    return jsonify({"pools": pp.list_pools(active_only=active_only)})


@app.route("/api/pools", methods=["POST"])
def api_pools_create():
    data = request.get_json(force=True, silent=True) or {}
    try:
        p = pp.create_pool(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"pool": p}), 201


@app.route("/api/pools/<pid>", methods=["GET"])
def api_pools_get(pid):
    p = pp.get_pool(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify({"pool": p})


@app.route("/api/pools/<pid>", methods=["PUT", "PATCH"])
def api_pools_update(pid):
    data = request.get_json(force=True, silent=True) or {}
    try:
        p = pp.update_pool(pid, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify({"pool": p})


@app.route("/api/pools/<pid>", methods=["DELETE"])
def api_pools_delete(pid):
    try:
        ok = pp.delete_pool(pid)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/pools/<pid>/test", methods=["POST"])
def api_pools_test(pid):
    if not pp.get_pool(pid):
        return jsonify({"error": "not found"}), 404
    result = pp.test_pool(pid)
    return jsonify({"result": result})


@app.route("/api/pools/default", methods=["GET"])
def api_pools_default():
    p = pp.get_default_pool()
    return jsonify({"pool": p})


# ── Batch Import ──
@app.route("/api/profiles/template/csv", methods=["GET"])
def api_template_csv():
    from flask import Response
    return Response(bi.csv_template(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=profile-template.csv"})


@app.route("/api/profiles/template/json", methods=["GET"])
def api_template_json():
    from flask import Response
    return Response(bi.json_template(), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=profile-template.json"})


@app.route("/api/profiles/import", methods=["POST"])
def api_import():
    """Upload CSV/JSON file -> preview (?preview=1) or import.

    Accepts multipart 'file' or JSON body {"content": ..., "format": "csv"|"json"}.
    """
    preview_only = request.args.get("preview") == "1"

    content, fmt = None, None
    if "file" in request.files:
        f = request.files["file"]
        content = f.read().decode("utf-8-sig", errors="replace")
        fn = (f.filename or "").lower()
        fmt = "json" if fn.endswith(".json") else "csv"
    else:
        data = request.get_json(force=True, silent=True) or {}
        content = data.get("content", "")
        fmt = (data.get("format") or "").lower()

    if not content or not content.strip():
        return jsonify({"error": "file kosong"}), 400
    if fmt == "json":
        rows, errors = bi.parse_json(content)
    elif fmt == "csv":
        rows, errors = bi.parse_csv(content)
    else:
        return jsonify({"error": "format harus csv atau json"}), 400

    if preview_only:
        return jsonify({
            "rows": bi.preview_rows(rows),
            "parse_errors": errors,
            "total_valid": len(rows),
        })

    # F3-6: ?async=1 -> job latar (progress + cancel), 202 + job_id.
    if request.args.get("async") == "1":
        job = bi.start_import_job(content, fmt)
        return jsonify({"ok": True, "job_id": job["job_id"],
                        "total": job["total"],
                        "parse_errors": errors}), 202

    created, failed = bi.import_rows(rows)
    failed = errors + failed  # parse errors also reported
    return jsonify({
        "created": [{"id": p["id"], "name": p["name"]} for p in created],
        "failed": failed,
        "summary": {"success": len(created), "failed": len(failed)},
    })


# ── Batch jobs: progress + cancel (F3-6) ──────────────────────────────────
@app.route("/api/batch/jobs", methods=["GET"])
def api_batch_jobs():
    """F3-6: daftar job impor/ekspor (terbaru dulu)."""
    return jsonify({"ok": True, "jobs": bi.list_jobs()})


@app.route("/api/batch/jobs/<job_id>", methods=["GET"])
def api_batch_job(job_id):
    """F3-6: status satu job."""
    job = bi.get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "job tidak ditemukan"}), 404
    return jsonify({"ok": True, "job": job})


@app.route("/api/batch/jobs/<job_id>/cancel", methods=["POST"])
def api_batch_job_cancel(job_id):
    """F3-6: minta job berhenti (dicek antar baris)."""
    job = bi.cancel_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "job tidak ditemukan"}), 404
    return jsonify({"ok": True, "job": job})


@app.route("/api/batch/jobs/<job_id>/download", methods=["GET"])
def api_batch_job_download(job_id):
    """F3-6: unduh hasil job ekspor yang sudah selesai."""
    from flask import send_file
    fpath = bi.export_result_path(job_id)
    if not fpath:
        return jsonify({"ok": False,
                        "error": "hasil ekspor belum tersedia"}), 404
    return send_file(fpath, as_attachment=True,
                     download_name=os.path.basename(fpath))


@app.route("/api/profiles/export", methods=["POST"])
def api_profiles_export():
    """F3-6: ekspor profil (async job). Body: {ids?, format?, group?}."""
    data = request.get_json(force=True, silent=True) or {}
    fmt = (data.get("format") or "csv").lower()
    try:
        job = bi.start_export_job(ids=data.get("ids"),
                                  fmt=fmt, group=data.get("group"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "job_id": job["job_id"],
                    "total": job["total"]}), 202


# ── Fingerprint Generator ──
@app.route("/api/fingerprint/options", methods=["GET"])
def api_fp_options():
    """Dropdown options untuk mode manual. ?os=windows"""
    os_name = request.args.get("os", "windows")
    try:
        return jsonify({"ok": True, "options": fg.manual_options(os_name)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/fingerprint/generate", methods=["POST"])
def api_fp_generate():
    """Mode random: generate identitas konsisten. Body: {os, timezone, locale, chrome_ver, country}"""
    data = request.get_json(force=True, silent=True) or {}
    os_name = (data.get("os") or "windows").lower()
    try:
        ident = fg.generate_random(
            os_name,
            timezone=data.get("timezone") or "Asia/Jakarta",
            locale=data.get("locale"),
            chrome_ver=data.get("chrome_ver"),
            country=data.get("country") or "id",
        )
        return jsonify({"ok": True, "identity": ident})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/fingerprint/validate", methods=["POST"])
def api_fp_validate():
    """Cek konsistensi identitas manual. Body: {identity}"""
    data = request.get_json(force=True, silent=True) or {}
    ident = data.get("identity") or {}
    try:
        warnings = fg.validate_identity(ident)
        return jsonify({"ok": True, "consistent": not warnings, "warnings": warnings})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/fingerprint/preview", methods=["POST"])
def api_fp_preview():
    """Preview field identitas + panjang JS. Body: {identity, features?}"""
    data = request.get_json(force=True, silent=True) or {}
    ident = data.get("identity") or {}
    try:
        preview = fg.preview_identity(ident, features=data.get("features"))
        return jsonify({"ok": True, "preview": preview})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/profiles/<pid>/fingerprint", methods=["POST", "PUT"])
def api_profile_fingerprint(pid):
    """Simpan identitas generator ke profil. Body: {identity}"""
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    ident = data.get("identity") or {}
    if not ident.get("platform"):
        return jsonify({"error": "identity kosong/tidak valid"}), 400
    fp = p.get("fingerprint", {})
    fp["identity"] = fg.to_jsonable(ident)
    # sinkronkan field turunan biar konsisten
    if ident.get("timezone"):
        fp["timezone"] = ident["timezone"]
    if ident.get("locale"):
        fp["locale"] = ident["locale"]
    if ident.get("is_mobile"):
        fp["mobile"] = True
        fp["platform"] = {"android": "android", "ios": "ios"}.get(ident.get("os"), "android")
    else:
        fp["mobile"] = False
        fp["platform"] = {"windows": "windows", "macos": "macos",
                          "linux": "linux"}.get(ident.get("os"), fp.get("platform", "windows"))
    updated = pm.update_profile(pid, {"fingerprint": fp})
    # AUDIT 2026-11-04: kembalikan warning validasi biar user tahu kalau
    # identitas manualnya tidak konsisten (tidak diblokir, cuma info)
    warnings = fg.validate_identity(ident)
    return jsonify({"ok": True, "warnings": warnings,
                    "profile": {"id": pid, "fingerprint": updated["fingerprint"]}})


@app.route("/api/profiles/<pid>/fingerprint", methods=["DELETE"])
def api_profile_fingerprint_clear(pid):
    """Hapus identitas tersimpan -> kembali ke generate acak tiap launch."""
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    fp = p.get("fingerprint", {})
    fp.pop("identity", None)
    updated = pm.update_profile(pid, {"fingerprint": fp})
    return jsonify({"ok": True})


# ── Fingerprint preview ──
@app.route("/api/profiles/<pid>/preview", methods=["GET"])
def api_preview(pid):
    """Preview fingerprint yang BENAR-BENAR dipakai saat launch (P-02).

    Dulu preview generate identitas acak baru dan mengabaikan identity
    tersimpan — angka yang ditampilkan tidak pernah dipakai. Sekarang preview
    memanggil launcher.build_fingerprint_js() yang sama dengan launch, jadi
    identity + js_length (termasuk spoof_js_extra) persis yang di-inject.
    Bila profil belum punya identity tersimpan, launch generate acak tiap
    kali — preview menandainya (identity_stored=false) dan menampilkan satu
    contoh hasil generate."""
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    try:
        launcher = _launcher()
        js, ident = launcher.build_fingerprint_js(p)
        fp = p["fingerprint"]
        features = {k: v for k, v in fp.get("features", {}).items() if v}
        stored = bool(fp.get("identity"))
        out = {
            "ok": True,
            "identity": {k: str(v)[:80] for k, v in ident.items()},
            "identity_stored": stored,
            "js_length": len(js),
            "features_enabled": len(features),
            "features_total": len(pm.FEATURE_FLAGS),
            "timezone": fp.get("timezone"),
            "platform": fp.get("platform"),
            "mobile": fp.get("mobile"),
            "warp_fallback": p.get("warp_fallback"),
        }
        if not stored:
            out["note"] = ("belum tersimpan — preview ini contoh identitas yang "
                           "akan digenerate saat launch (acak tiap launch sampai disimpan)")
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── FIX 3 (RND 2026-11-04): Geo-sync API ──────────────────────────────
# Sinkronkan timezone/locale profil dengan negara IP proxy pool.
@app.route("/api/profiles/<pid>/sync-geo", methods=["POST"])
def api_sync_geo(pid):
    """Auto-set timezone+locale profil dari negara IP pool-nya.

    Syarat: pool sudah di-test (last_check ada country).
    Return: {"ok": true, "timezone": ..., "locale": ...} atau error.
    """
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    try:
        import geo_sync
        import proxy_pools as pp
        pool_id = (p.get("proxy") or {}).get("pool_id")
        if not pool_id:
            return jsonify({"error": "profile has no pool_id"}), 400
        pool = pp.get_pool(pool_id)
        if not pool:
            return jsonify({"error": "pool not found"}), 404
        geo = geo_sync.suggest_geo_for_pool(pool)
        if not geo:
            return jsonify({"error": "pool country unknown — test pool dulu"}), 400
        upd = geo_sync.apply_geo_to_profile_data(p, geo)
        p2 = pm.update_profile(pid, upd)
        return jsonify({"ok": True, "timezone": geo["timezone"],
                        "locale": geo["locale"],
                        "lat": geo["lat"], "lon": geo["lon"],
                        "country_code": geo["country_code"],
                        "pool": pool.get("name")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/profiles/<pid>/geo-check", methods=["GET"])
def api_geo_check(pid):
    """Cek mismatch timezone profil vs negara IP pool. Return warning atau ok."""
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    try:
        import geo_sync
        import proxy_pools as pp
        pool_id = (p.get("proxy") or {}).get("pool_id")
        pool = pp.get_pool(pool_id) if pool_id else None
        w = geo_sync.check_geo_mismatch(p, pool) if pool else None
        if w:
            return jsonify({"ok": False, "warning": w})
        return jsonify({"ok": True, "message": "geo konsisten"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Cookie import/export ──
@app.route("/api/profiles/<pid>/cookies", methods=["GET"])
def api_cookies_get(pid):
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify({"cookies": p.get("cookies", [])})


@app.route("/api/profiles/<pid>/cookies", methods=["POST", "PUT"])
def api_cookies_set(pid):
    data = request.get_json(force=True, silent=True) or {}
    cookies = data.get("cookies", [])
    p = pm.update_profile(pid, {"cookies": cookies})
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True, "count": len(cookies)})


# ── Launch/Stop ──
# Actual browser launch happens via launcher.launch_profile (same code path
# as Local API + CLI). P-12: TIDAK ADA lagi dict RUNNING in-memory di sini —
# satu-satunya registry sesi adalah sessions.json + liveness check.


def _launcher():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "antibrowser_launcher",
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "launcher", "launcher.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@app.route("/api/profiles/<pid>/launch", methods=["POST"])
def api_launch(pid):
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    # P-14: parameter headless (bool atau string "true"/"1"); default False
    # = headful (perilaku lama). Headless berguna untuk automation/CI.
    headless = data.get("headless", False)
    if isinstance(headless, str):
        headless = headless.strip().lower() in ("1", "true", "yes", "on")
    try:
        launcher = _launcher()
        sess = launcher.launch_profile(
            p, headless=bool(headless),
            url=data.get("url"),
            identity_override=data.get("identity"),
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    pm.update_profile(pid, {"status": "running"})
    out = {k: v for k, v in sess.items() if not k.startswith("_")}
    return jsonify({"ok": True, "profile_id": pid, "status": "running", **out})


@app.route("/api/profiles/<pid>/fingerprint-check", methods=["GET"])
def api_fingerprint_check(pid):
    """P-18: fingerprint-check live untuk profil yang sedang jalan."""
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    try:
        sess = _launcher().list_running().get(pid)
    except Exception:
        sess = None
    if not sess:
        return jsonify({"ok": False, "error": "browser tidak jalan — launch dulu"}), 400
    rpa_mod = _rpa()
    if rpa_mod is None:
        return jsonify({"ok": False, "error": "modul rpa tidak ditemukan"}), 500
    # P-18: identity HARUS yang tercatat saat launch (identity.json).
    ident = _launcher().get_launched_identity(pid)
    if not ident:
        return jsonify({"ok": False,
                        "error": "identity launch tidak tercatat — relaunch profil ini dulu"}), 400
    try:
        result = rpa_mod.check_fingerprint(sess["debug_port"], ident)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "profile_id": pid, **result})


@app.route("/api/profiles/<pid>/rpa", methods=["POST"])
def api_rpa_run(pid):
    """P-18: jalankan langkah RPA di profil yang sedang jalan.
    Body: {"steps": [...]} atau {"flow": "nama"}."""
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    rpa_mod = _rpa()
    if rpa_mod is None:
        return jsonify({"ok": False, "error": "modul rpa tidak ditemukan"}), 500
    steps = data.get("steps")
    if steps is None and data.get("flow"):
        try:
            steps = rpa_mod.get_flow(data["flow"])["steps"]
        except KeyError as e:
            return jsonify({"ok": False, "error": str(e)}), 404
    if steps is None:
        return jsonify({"ok": False, "error": "steps atau flow wajib diisi"}), 400
    try:
        sess = _launcher().list_running().get(pid)
    except Exception:
        sess = None
    if not sess:
        return jsonify({"ok": False, "error": "browser tidak jalan — launch dulu"}), 400
    try:
        steps = rpa_mod.validate_steps(steps)
    except ValueError as e:
        return jsonify({"ok": False, "error": f"steps tidak valid: {e}"}), 400
    try:
        result = rpa_mod.run_steps(sess["debug_port"], steps,
                                   timeout=int(data.get("timeout", 120)))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "profile_id": pid, **result})


@app.route("/api/profiles/<pid>/rpa/record/start", methods=["POST"])
def api_rpa_record_start(pid):
    """F5-2: mulai merekam aksi user di profil yang jalan. Perekam
    tinggal di proses GUI (state di modul rpa yang di-cache) — start
    dan stop harus lewat API ini (bukan Local API)."""
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    rpa_mod = _rpa()
    if rpa_mod is None:
        return jsonify({"ok": False, "error": "modul rpa tidak ditemukan"}), 500
    try:
        sess = _launcher().list_running().get(pid)
    except Exception:
        sess = None
    if not sess:
        return jsonify({"ok": False, "error": "browser tidak jalan — launch dulu"}), 400
    try:
        result = rpa_mod.start_recording(sess["debug_port"])
    except (ValueError, RuntimeError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "profile_id": pid, **result})


@app.route("/api/profiles/<pid>/rpa/record/stop", methods=["POST"])
def api_rpa_record_stop(pid):
    """F5-2: berhenti merekam; kembalikan langkah yang terekam (dan
    simpan jadi alur bila body berisi {"name": ...})."""
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    rpa_mod = _rpa()
    if rpa_mod is None:
        return jsonify({"ok": False, "error": "modul rpa tidak ditemukan"}), 500
    try:
        sess = _launcher().list_running().get(pid)
    except Exception:
        sess = None
    if not sess:
        return jsonify({"ok": False, "error": "browser tidak jalan — launch dulu"}), 400
    data = request.get_json(force=True, silent=True) or {}
    try:
        result = rpa_mod.stop_recording(sess["debug_port"],
                                        name=data.get("name") or None)
    except KeyError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except (ValueError, RuntimeError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "profile_id": pid, **result})


@app.route("/api/profiles/<pid>/rpa/record/status", methods=["GET"])
def api_rpa_record_status(pid):
    """F5-2: status perekaman (sedang jalan / sudah berapa langkah)."""
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    rpa_mod = _rpa()
    if rpa_mod is None:
        return jsonify({"ok": False, "error": "modul rpa tidak ditemukan"}), 500
    try:
        sess = _launcher().list_running().get(pid)
    except Exception:
        sess = None
    if not sess:
        return jsonify({"ok": False, "recording": False,
                        "error": "browser tidak jalan — launch dulu"}), 200
    return jsonify({"ok": True, "profile_id": pid,
                    **rpa_mod.recording_status(sess["debug_port"])})


@app.route("/api/rpa/flows", methods=["GET", "POST"])
def api_rpa_flows():
    """P-18: simpan (POST {"name", "steps"}) / daftar (GET) alur RPA."""
    rpa_mod = _rpa()
    if rpa_mod is None:
        return jsonify({"ok": False, "error": "modul rpa tidak ditemukan"}), 500
    if request.method == "GET":
        flows = rpa_mod.list_flows()
        return jsonify({"ok": True, "flows": [
            {"name": f["name"], "steps": len(f["steps"]),
             "updated_at": f.get("updated_at")} for f in flows.values()]})
    data = request.get_json(force=True, silent=True) or {}
    try:
        flow = rpa_mod.save_flow(data.get("name"), data.get("steps"))
    except (ValueError, KeyError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "name": flow["name"], "steps": len(flow["steps"])})


@app.route("/api/rpa/flows/<name>", methods=["GET", "DELETE"])
def api_rpa_flow_one(name):
    rpa_mod = _rpa()
    if rpa_mod is None:
        return jsonify({"ok": False, "error": "modul rpa tidak ditemukan"}), 500
    if request.method == "GET":
        try:
            return jsonify({"ok": True, **rpa_mod.get_flow(name)})
        except KeyError as e:
            return jsonify({"ok": False, "error": str(e)}), 404
    try:
        rpa_mod.delete_flow(name)
    except KeyError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    return jsonify({"ok": True})


def _rpa():
    """P-18: muat launcher/rpa.py (launcher/ tidak ada di sys.path
    proses GUI). F5-2: via rpa_loader (di-cache per proses) supaya state
    modul — mis. perekam Alur — bertahan antar request. Return modul
    atau None."""
    try:
        import rpa_loader
        return rpa_loader.load_rpa()
    except Exception:
        return None


@app.route("/api/rpa/templates", methods=["GET"])
def api_rpa_templates():
    """F5-3: daftar template alur per platform."""
    rpa_mod = _rpa()
    if rpa_mod is None:
        return jsonify({"ok": False, "error": "modul rpa tidak ditemukan"}), 500
    return jsonify({"ok": True, "templates": [
        {"key": k, **v} for k, v in rpa_mod.list_templates().items()]})


@app.route("/api/rpa/templates/<key>", methods=["GET"])
def api_rpa_template_one(key):
    """F5-1: satu template lengkap (untuk builder Alur)."""
    rpa_mod = _rpa()
    if rpa_mod is None:
        return jsonify({"ok": False, "error": "modul rpa tidak ditemukan"}), 500
    try:
        return jsonify({"ok": True, **rpa_mod.get_template(key)})
    except KeyError as e:
        return jsonify({"ok": False, "error": str(e)}), 404


@app.route("/api/rpa/templates/<key>/install", methods=["POST"])
def api_rpa_template_install(key):
    """F5-3: salin template jadi alur tersimpan. Body: {"name": ...}."""
    rpa_mod = _rpa()
    if rpa_mod is None:
        return jsonify({"ok": False, "error": "modul rpa tidak ditemukan"}), 500
    data = request.get_json(force=True, silent=True) or {}
    try:
        flow = rpa_mod.install_template(key, data.get("name"))
    except KeyError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "name": flow["name"],
                    "steps": len(flow["steps"]),
                    "template": flow.get("template")})


@app.route("/api/rpa/run-multi", methods=["POST"])
def api_rpa_run_multi():
    """F5-4: jalankan satu alur di banyak profil (job async, progres +
    cancel). Body: {"flow": "nama"} atau {"steps": [...]},
    {"profile_ids": ["id1", "id2"]}. Profil yang belum jalan di-launch
    headless lalu di-stop lagi."""
    rpa_mod = _rpa()
    if rpa_mod is None:
        return jsonify({"ok": False, "error": "modul rpa tidak ditemukan"}), 500
    data = request.get_json(force=True, silent=True) or {}
    steps = data.get("steps")
    flow_name = data.get("flow") or "(langkah langsung)"
    if steps is None and data.get("flow"):
        try:
            steps = rpa_mod.get_flow(data["flow"])["steps"]
        except KeyError as e:
            return jsonify({"ok": False, "error": str(e)}), 404
    profile_ids = data.get("profile_ids") or []
    if not isinstance(profile_ids, list) or not profile_ids:
        return jsonify({"ok": False, "error": "profile_ids wajib list tidak kosong"}), 400
    if len(profile_ids) > 50:
        return jsonify({"ok": False, "error": "maks 50 profil per job"}), 400
    try:
        steps = rpa_mod.validate_steps(steps)
    except ValueError as e:
        return jsonify({"ok": False, "error": f"steps tidak valid: {e}"}), 400
    job = rj.start_multi_job(flow_name, steps, profile_ids,
                             _launcher(), rpa_mod, pm)
    return jsonify({"ok": True, "job_id": job["job_id"], "total": job["total"]})


@app.route("/api/rpa/jobs", methods=["GET"])
def api_rpa_jobs():
    """F5-4: daftar job multi-profil (terbaru dulu)."""
    return jsonify({"ok": True, "jobs": rj.list_jobs()})


@app.route("/api/rpa/jobs/<job_id>", methods=["GET"])
def api_rpa_job(job_id):
    """F5-4: status satu job multi-profil."""
    job = rj.get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "job tidak ditemukan"}), 404
    return jsonify({"ok": True, "job": job})


@app.route("/api/rpa/jobs/<job_id>/cancel", methods=["POST"])
def api_rpa_job_cancel(job_id):
    """F5-4: minta job multi-profil berhenti (dicek antar profil)."""
    job = rj.cancel_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "job tidak ditemukan"}), 404
    return jsonify({"ok": True, "job": job})


@app.route("/api/profiles/<pid>/stop", methods=["POST"])
def api_stop(pid):
    p = pm.get_profile(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    try:
        launcher = _launcher()
        r = launcher.stop_profile(pid)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    pm.update_profile(pid, {"status": "idle"})
    return jsonify({"ok": True, "profile_id": pid, "status": "idle", **r})


# ── Extensions ──
@app.route("/api/extensions", methods=["GET"])
def api_ext_list():
    return jsonify({"extensions": em.list_extensions()})


@app.route("/api/extensions", methods=["POST"])
def api_ext_add():
    """Upload file (.crx/.zip) ATAU form/json {cws_url}."""
    try:
        if "file" in request.files and request.files["file"].filename:
            f = request.files["file"]
            from werkzeug.utils import secure_filename
            fn = secure_filename(f.filename)
            ext = os.path.splitext(fn)[1].lower()
            tmp = os.path.join(tempfile.gettempdir(), fn)
            f.save(tmp)
            try:
                if ext == ".crx":
                    info = em.add_crx(tmp, filename=fn)
                elif ext == ".zip":
                    info = em.add_zip(tmp, filename=fn)
                else:
                    return jsonify({"ok": False, "error": "format harus .crx atau .zip"}), 400
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
            return jsonify({"ok": True, "extension": info})
        data = request.get_json(silent=True) or request.form
        cws_url = (data.get("cws_url") or "").strip()
        if cws_url:
            info = em.add_from_cws(cws_url)
            return jsonify({"ok": True, "extension": info})
        return jsonify({"ok": False, "error": "kirim file (.crx/.zip) atau cws_url"}), 400
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/extensions/preview", methods=["POST"])
def api_ext_preview():
    """F3-7: pratinjau file extension TANPA install — manifest, versi,
    permission, dan risiko. Upload multipart 'file' (.crx/.zip)."""
    try:
        if "file" not in request.files or not request.files["file"].filename:
            return jsonify({"ok": False, "error": "kirim file (.crx/.zip)"}), 400
        f = request.files["file"]
        from werkzeug.utils import secure_filename
        fn = secure_filename(f.filename)
        tmp = os.path.join(tempfile.gettempdir(), fn)
        f.save(tmp)
        try:
            prev = em.preview_file(tmp)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return jsonify({"ok": True, "preview": prev})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/extensions/<eid>/pin", methods=["POST"])
def api_ext_pin(eid):
    """F3-7: kunci extension ke satu versi. Body: {version?} (kosong =
    kunci ke versi terinstal)."""
    data = request.get_json(silent=True) or {}
    try:
        info = em.pin_version(eid, data.get("version"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    return jsonify({"ok": True, "extension": info})


@app.route("/api/extensions/<eid>/pin", methods=["DELETE"])
def api_ext_unpin(eid):
    """F3-7: lepas kunci versi."""
    try:
        info = em.unpin_version(eid)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    return jsonify({"ok": True, "extension": info})


@app.route("/api/extensions/<eid>/update", methods=["POST"])
def api_ext_update(eid):
    """F3-7: update extension ke versi baru dari file (.crx/.zip).
    Pin versi + kunci publik CRX ditegakkan di update_from_file.
    Query ?force=1 = izinkan reinstall versi sama/lebih lama."""
    try:
        if "file" not in request.files or not request.files["file"].filename:
            return jsonify({"ok": False, "error": "kirim file (.crx/.zip)"}), 400
        f = request.files["file"]
        from werkzeug.utils import secure_filename
        fn = secure_filename(f.filename)
        tmp = os.path.join(tempfile.gettempdir(), fn)
        f.save(tmp)
        try:
            info = em.update_from_file(
                eid, tmp, force=request.args.get("force") == "1")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return jsonify({"ok": True, "extension": info})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/extensions/<eid>", methods=["GET"])
def api_ext_get(eid):
    info = em.get_extension(eid)
    if not info:
        return jsonify({"error": "not found"}), 404
    return jsonify(info)


@app.route("/api/extensions/<eid>", methods=["DELETE"])
def api_ext_del(eid):
    if not em.delete_extension(eid):
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/profiles/<pid>/extensions", methods=["GET"])
def api_prof_ext_list(pid):
    if not pm.get_profile(pid):
        return jsonify({"error": "profile not found"}), 404
    return jsonify({"extensions": em.list_profile_extensions(pid)})


@app.route("/api/profiles/<pid>/extensions", methods=["POST"])
def api_prof_ext_assign(pid):
    if not pm.get_profile(pid):
        return jsonify({"error": "profile not found"}), 404
    data = request.get_json(silent=True) or {}
    eid = data.get("ext_id")
    if not eid:
        return jsonify({"ok": False, "error": "ext_id wajib"}), 400
    try:
        em.assign(pid, eid, enabled=data.get("enabled", True))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True})


@app.route("/api/profiles/<pid>/extensions/<eid>", methods=["PUT", "PATCH"])
def api_prof_ext_toggle(pid, eid):
    if not pm.get_profile(pid):
        return jsonify({"error": "profile not found"}), 404
    data = request.get_json(silent=True) or {}
    if "enabled" not in data:
        return jsonify({"ok": False, "error": "enabled wajib"}), 400
    if not em.set_enabled(pid, eid, data["enabled"]):
        return jsonify({"ok": False, "error": "assignment tidak ditemukan"}), 404
    return jsonify({"ok": True})


@app.route("/api/profiles/<pid>/extensions/<eid>", methods=["DELETE"])
def api_prof_ext_unassign(pid, eid):
    if not pm.get_profile(pid):
        return jsonify({"error": "profile not found"}), 404
    if not em.unassign(pid, eid):
        return jsonify({"ok": False, "error": "assignment tidak ditemukan"}), 404
    return jsonify({"ok": True})


# ── Synchronizer / Cermin (F3-2) ─────────────────────────────────────────
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


def _sync_mod_or_500():
    mod = _sync()
    if mod is None:
        return None, (jsonify({"ok": False, "error": "modul sync tidak ditemukan"}), 500)
    return mod, None


@app.route("/api/sync/start", methods=["POST"])
def api_sync_start():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("leader_id"):
        return jsonify({"ok": False, "error": "leader_id wajib"}), 400
    try:
        st = mod.start_sync(data["leader_id"],
                            follower_ids=data.get("follower_ids"),
                            open_delay_ms=data.get("open_delay_ms", 0))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, **st})


@app.route("/api/sync/stop", methods=["POST"])
def api_sync_stop():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    return jsonify({"ok": True, **mod.stop_sync()})


@app.route("/api/sync/status", methods=["GET"])
def api_sync_status():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    return jsonify({"ok": True, **mod.get_state()})


@app.route("/api/sync/range", methods=["POST"])
def api_sync_range():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        st = mod.set_range(data.get("range", "all"),
                           follower_ids=data.get("follower_ids"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, **st})


@app.route("/api/sync/open-delay", methods=["POST"])
def api_sync_delay():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        st = mod.set_open_delay(data.get("ms", 0))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, **st})


@app.route("/api/sync/steps", methods=["POST"])
def api_sync_steps():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        out = mod.mirror_steps(data.get("steps"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, **out})


@app.route("/api/sync/open-url", methods=["POST"])
def api_sync_open_url():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        out = mod.open_url(data.get("url"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, **out})


@app.route("/api/sync/input", methods=["POST"])
def api_sync_input():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        out = mod.input_text(data.get("text"), selector=data.get("selector"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, **out})


@app.route("/api/sync/refresh", methods=["POST"])
def api_sync_refresh():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    try:
        out = mod.refresh_all()
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, **out})


@app.route("/api/sync/tabs/<pid>", methods=["GET"])
def api_sync_tabs_list(pid):
    mod, err = _sync_mod_or_500()
    if err:
        return err
    try:
        return jsonify({"ok": True, "tabs": mod.list_tabs(pid)})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/sync/tabs/<pid>", methods=["POST"])
def api_sync_tabs_open(pid):
    mod, err = _sync_mod_or_500()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify({"ok": True, **mod.open_tab(pid, data.get("url"))})
    except (ValueError, RuntimeError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/sync/tabs/<pid>/<tid>", methods=["DELETE"])
def api_sync_tabs_close(pid, tid):
    mod, err = _sync_mod_or_500()
    if err:
        return err
    try:
        return jsonify({"ok": True, "closed": mod.close_tab(pid, tid)})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/sync/tabs/<pid>/<tid>/activate", methods=["POST"])
def api_sync_tabs_activate(pid, tid):
    mod, err = _sync_mod_or_500()
    if err:
        return err
    try:
        return jsonify({"ok": True, "activated": mod.activate_tab(pid, tid)})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/sync/show/<pid>", methods=["POST"])
def api_sync_show(pid):
    mod, err = _sync_mod_or_500()
    if err:
        return err
    try:
        return jsonify({"ok": True, **mod.show_browser(pid)})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/sync/position/<pid>", methods=["GET"])
def api_sync_position(pid):
    mod, err = _sync_mod_or_500()
    if err:
        return err
    try:
        return jsonify({"ok": True, **mod.get_position(pid)})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/sync/size", methods=["POST"])
def api_sync_size():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    try:
        out = mod.sync_size()
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, **out})


@app.route("/api/sync/clear", methods=["POST"])
def api_sync_clear():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    return jsonify({"ok": True, **mod.clear_log()})


@app.route("/api/sync/reset-download", methods=["POST"])
def api_sync_reset_download():
    mod, err = _sync_mod_or_500()
    if err:
        return err
    return jsonify({"ok": True, **mod.reset_download()})


# ── Kernel manager (F3-4) ─────────────────────────────────────────────────
def _kernels():
    """Muat launcher/kernels.py. Return modul atau None."""
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


def _kernels_or_500():
    mod = _kernels()
    if mod is None:
        return None, (jsonify({"ok": False, "error": "modul kernel tidak ditemukan"}), 500)
    return mod, None


@app.route("/api/profiles/<pid>/backup", methods=["POST"])
def backup_profile(pid):
    """F3-5: ekspor profil ke ZIP (manifest + profile.json + data browser
    + cache bila diizinkan). Body: {include_cache?}."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify({"ok": True, **backup.export_profile(
            pid, include_cache=data.get("include_cache", True))}), 201
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/backups", methods=["GET"])
def list_backups_api():
    """F3-5: daftar file backup (baca manifest — tanpa extract)."""
    return jsonify({"ok": True, "backups": backup.list_backups()})


@app.route("/api/backups/<path:fname>/restore", methods=["POST"])
def restore_backup(fname):
    """F3-5: restore backup jadi profil BARU. Body: {new_name?}."""
    data = request.get_json(force=True, silent=True) or {}
    fpath = os.path.join(backup._backups_root(), fname)
    try:
        r = backup.restore_profile(fpath, new_name=data.get("new_name") or None)
        return jsonify({"ok": True, "profile": r["profile"],
                        "restored_files": r["restored_files"],
                        "from_backup": r["from_backup"],
                        "exported_at": r["exported_at"]}), 201
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), \
            404 if "tidak ditemukan" in str(e) else 400


@app.route("/api/backups/<path:fname>", methods=["DELETE"])
def delete_backup_api(fname):
    """F3-5: hapus file backup."""
    try:
        backup.delete_backup(fname)
        return jsonify({"ok": True, "deleted": fname})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404


@app.route("/api/kernels", methods=["GET"])
def api_kernels_list():
    mod, err = _kernels_or_500()
    if err:
        return err
    system = None
    try:
        launcher = _launcher()
        chrome = launcher.find_chrome()
        system = {"id": "system", "name": "Chromium (sistem)", "path": chrome,
                  "version": launcher.get_real_chrome_version(chrome),
                  "engine": "chromium", "default": False}
    except Exception:
        pass
    kernels = mod.list_kernels()
    default = next((k["id"] for k in kernels if k.get("is_default")), None)
    if system:
        system["is_default"] = default is None
    return jsonify({"ok": True, "kernels": kernels, "system": system,
                    "default": default or "system"})


@app.route("/api/kernels/download", methods=["POST"])
def api_kernels_download():
    mod, err = _kernels_or_500()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    job = mod.start_download(data.get("version"))
    return jsonify({"ok": True, **job}), 202


@app.route("/api/kernels/downloads", methods=["GET"])
def api_kernels_downloads():
    mod, err = _kernels_or_500()
    if err:
        return err
    return jsonify({"ok": True, "jobs": mod.list_downloads()})


@app.route("/api/kernels/downloads/<job_id>", methods=["GET"])
def api_kernels_download_status(job_id):
    mod, err = _kernels_or_500()
    if err:
        return err
    try:
        return jsonify({"ok": True, **mod.get_download_status(job_id)})
    except KeyError as e:
        return jsonify({"ok": False, "error": str(e)}), 404


@app.route("/api/kernels/register", methods=["POST"])
def api_kernels_register():
    mod, err = _kernels_or_500()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        entry = mod.register_kernel(data.get("path"), name=data.get("name"),
                                    engine=data.get("engine", "chromium"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "kernel": entry}), 201


@app.route("/api/kernels/<kid>", methods=["DELETE"])
def api_kernels_delete(kid):
    mod, err = _kernels_or_500()
    if err:
        return err
    try:
        mod.remove_kernel(kid)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True})


@app.route("/api/kernels/<kid>/default", methods=["POST"])
def api_kernels_default(kid):
    mod, err = _kernels_or_500()
    if err:
        return err
    try:
        entry = mod.set_default_kernel(kid)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "default": entry["id"] if entry else "system"})


@app.route("/api/profiles/<pid>/kernel", methods=["POST"])
def api_profile_kernel(pid):
    """Pilih kernel untuk profil. Body: {kernel_id} ("system" = Chromium sistem)."""
    if not pm.get_profile(pid):
        return jsonify({"error": "not found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    kid = data.get("kernel_id") or data.get("kernel") or "system"
    if kid != "system":
        mod, err = _kernels_or_500()
        if err:
            return err
        if not mod.get_kernel(kid):
            return jsonify({"error": f"kernel {kid} tidak dikenal"}), 404
    p = pm.update_profile(pid, {"kernel": kid})
    return jsonify({"ok": True, "kernel": p["kernel"]})


# ── Local API settings (GUI controls the API process) ──
@app.route("/api/settings/api", methods=["GET"])
def api_settings_get():
    cfg = ac.get_config()
    st = ac.api_status()
    return jsonify({
        "enabled": cfg["enabled"],
        "port": cfg["port"],
        "api_key_set": bool(cfg["api_key"]),
        "running": st["running"],
        "pid": st["pid"],
    })


@app.route("/api/settings/api", methods=["PUT", "PATCH"])
def api_settings_put():
    data = request.get_json(silent=True) or {}
    was_running = ac.api_status()["running"]
    try:
        cfg = ac.save_config(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    # If the API was running and settings changed, restart it so
    # the new port / key takes effect immediately.
    if was_running:
        ac.stop_api()
        if cfg["enabled"]:
            st = ac.start_api()
            if not st["ok"]:
                return jsonify({"error": "gagal restart API"}), 500
    cfg = ac.get_config()
    cfg.pop("api_key", None)
    return jsonify({**cfg, "api_key_set": bool(ac.get_config()["api_key"]),
                    "running": ac.api_status()["running"]})


@app.route("/api/settings/api/key", methods=["POST"])
def api_settings_newkey():
    key = ac.generate_key()
    # Restart API so the new key takes effect immediately.
    if ac.api_status()["running"]:
        ac.stop_api()
        st = ac.start_api()
        if not st["ok"]:
            return jsonify({"api_key": key,
                            "warning": "API gagal restart — key aktif setelah restart manual"}), 200
    return jsonify({"api_key": key})


@app.route("/api/settings/api/start", methods=["POST"])
def api_settings_start():
    return jsonify(ac.start_api())


@app.route("/api/settings/api/stop", methods=["POST"])
def api_settings_stop():
    return jsonify(ac.stop_api())


# ── P-11: Storage health (peringatan auto-repair) ────────────────────────
@app.route("/api/system/storage-health", methods=["GET"])
def api_storage_health():
    """Laporkan file JSON yang dikarantina karena corrupt + status backup.

    Frontend menampilkan banner bila ada file .corrupt-* (tanda auto-repair
    pernah terjadi — data lama tersimpan di file karantina, bisa dipulihkan).
    """
    import json_store
    data_dir = pm.DATA_DIR
    stores = {}
    for name in ("profiles.json", "proxy_pools.json", "api_config.json",
                 "extensions.json", "profile_extensions.json"):
        p = os.path.join(data_dir, name)
        stores[name] = {"exists": os.path.exists(p),
                        "bak": os.path.exists(p + ".bak")}
    return jsonify({"quarantined": json_store.list_quarantined(data_dir),
                    "stores": stores})


def run(port=5200, debug=False):
    host = os.environ.get("STEALTHXGM_HOST", "127.0.0.1")
    print(f"[GUI] Profile Manager on http://{host}:{port}")
    # P-06: bersihkan sesi basi (browser mati/crash/VM restart) saat start.
    try:
        n = _launcher().prune_stale_sessions()
        if n:
            print(f"[GUI] {n} sesi basi dibersihkan")
    except Exception:
        pass
    # P-12: rapikan field status di profiles.json dari registry hidup.
    try:
        _launcher().sync_profile_statuses(pm)
    except Exception:
        pass
    if host not in ("127.0.0.1", "localhost", "::1"):
        # P-04d (F3-8): bind non-localhost TANPA password login = DITOLAK.
        # GUI tanpa auth tidak boleh terekspos ke jaringan.
        ok, why = gui_auth.check_bind_allowed(host)
        if not ok:
            print(f"[GUI] FATAL: {why}")
            raise SystemExit(1)
        print(f"[GUI] bind {host} — login aktif "
              f"({gui_auth.active_sessions()} sesi aktif).")
    # Auto-start Local API if enabled in settings (unless already running).
    cfg = ac.get_config()
    if cfg["enabled"] and not ac.api_is_running():
        st = ac.start_api()
        print(f"[GUI] Local API auto-start: {'OK' if st['ok'] else 'GAGAL'} (port {cfg['port']})")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run()
