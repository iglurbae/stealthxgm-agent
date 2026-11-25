#!/usr/bin/env python3
"""StealthXGM CLI — kontrol Local REST API dari cmd / termux.

Tidak butuh library tambahan (stdlib saja). Jalan di mana aja ada python3.

Penggunaan:
  python3 antibrowser-cli.py list
  python3 antibrowser-cli.py create --name "Akun1" --group "bugbounty"
  python3 antibrowser-cli.py launch <id> [--headless]
  python3 antibrowser-cli.py stop <id>
  python3 antibrowser-cli.py delete <id>        # ke Trash (bisa restore)
  python3 antibrowser-cli.py status             # status API + browser jalan
  python3 antibrowser-cli.py api-start          # nyalakan Local API
  python3 antibrowser-cli.py api-stop           # matikan Local API

Opsi global:
  --port 50325        (default: baca dari gui/data/api_config.json)
  --key SECRET        (default: baca dari gui/data/api_config.json)
  --gui URL           (default: http://127.0.0.1:5200, untuk api-start/stop)
  --json              output mentah JSON

Contoh termux (satu baris):
  python3 antibrowser-cli.py create --name "tokped1" && python3 antibrowser-cli.py launch <id>
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(HERE, "gui", "data", "api_config.json")
GUI_URL = "http://127.0.0.1:5200"
# F3-8: token sesi login GUI (chmod 600) — dibuat oleh `login`.
SESSION_FILE = os.path.join(os.path.expanduser("~"), ".cache", "stealthxgm",
                            "session.json")


def _load_session_token():
    try:
        with open(SESSION_FILE) as f:
            data = json.load(f)
        return data.get("token") if isinstance(data, dict) else None
    except Exception:
        return None


def _save_session_token(token):
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump({"token": token}, f)
    os.chmod(SESSION_FILE, 0o600)


def _clear_session_token():
    try:
        os.remove(SESSION_FILE)
    except OSError:
        pass


def load_cfg():
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def api_req(method, path, data=None, base=None, key=None, raw=False,
            timeout=30):
    base = base or f"http://127.0.0.1:{load_cfg().get('port', 50325)}"
    url = base + path
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("X-API-Key", key)
    # F3-8: sertakan token sesi login GUI bila ada (untuk rute /api/* GUI).
    token = _load_session_token()
    if token:
        req.add_header("X-Session-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            out = json.loads(e.read().decode())
        except Exception:
            out = {"code": e.code, "msg": f"HTTP {e.code}"}
    except Exception as e:
        out = {"code": -99, "msg": f"koneksi gagal: {e}"}
    if raw:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    return out


def resolve(args):
    cfg = load_cfg()
    port = args.port or cfg.get("port", 50325)
    key = args.key if args.key is not None else cfg.get("api_key", "")
    base = f"http://127.0.0.1:{port}"
    return base, key, args.gui


def cmd_list(a):
    base, key, _ = resolve(a)
    qs = "/api/v1/user/list?page_size=200"
    if getattr(a, "group", ""):
        qs += "&group=" + urllib.parse.quote(a.group)
    if getattr(a, "tags", ""):
        qs += "&tags=" + urllib.parse.quote(a.tags)
    r = api_req("GET", qs, base=base, key=key, raw=a.json)
    if a.json:
        return
    if r.get("code") != 0:
        print("❌", r.get("msg")); return
    items = r["data"]["list"]
    print(f"📋 {len(items)} profil:")
    for p in items:
        tags = ",".join(p.get("tags") or [])
        print(f"  {p['user_id']}  {p['name']:<24} [{p.get('status','idle')}]"
              + (f" #{tags}" if tags else ""))


def cmd_create(a):
    base, key, _ = resolve(a)
    data = {"name": a.name}
    if a.group:
        data["group"] = a.group
    r = api_req("POST", "/api/v1/user/create", data, base=base, key=key, raw=a.json)
    if a.json:
        return
    print("✅ ID:", r["data"]["user_id"] if r.get("code") == 0 else "❌ " + r.get("msg"))


def cmd_launch(a):
    base, key, _ = resolve(a)
    # P-14: --headless diteruskan sebagai query param (Local API).
    qs = "?user_id=" + a.id + ("&headless=true" if a.headless else "")
    r = api_req("GET", f"/api/v1/browser/start{qs}", base=base, key=key, raw=a.json)
    if a.json:
        return
    if r.get("code") == 0:
        d = r["data"]
        print(f"✅ Browser jalan — debug port {d.get('debug_port')}"
              + (" (headless)" if d.get("headless") else ""))
    else:
        print("❌", r.get("msg"))


def cmd_stop(a):
    base, key, _ = resolve(a)
    r = api_req("GET", f"/api/v1/browser/stop?user_id={a.id}", base=base, key=key, raw=a.json)
    if not a.json:
        print("✅ Stop" if r.get("code") == 0 else "❌ " + r.get("msg"))


def cmd_delete(a):
    base, key, _ = resolve(a)
    r = api_req("POST", "/api/v1/user/delete", {"user_id": a.id}, base=base, key=key, raw=a.json)
    if not a.json:
        print("✅ Ke Trash" if r.get("code") == 0 else "❌ " + r.get("msg"))


def cmd_status(a):
    base, key, gui = resolve(a)
    r = api_req("GET", "/api/v1/status", base=base, key=key, raw=a.json)
    if a.json:
        return
    if r.get("code") != 0:
        print("❌ API mati / tidak bisa dijangkau —", r.get("msg"))
        return
    d = r["data"]
    print(f"✅ API jalan — {d.get('total_profiles',0)} profil, "
          f"{d.get('running_profiles',0)} browser aktif")


def cmd_api_start(a):
    _, _, gui = resolve(a)
    r = api_req("POST", "/api/settings/api/start", {}, base=gui, raw=a.json)
    if not a.json:
        print("✅ API start" if r.get("ok") else "❌ " + r.get("msg", "gagal"))


def cmd_api_stop(a):
    _, _, gui = resolve(a)
    r = api_req("POST", "/api/settings/api/stop", {}, base=gui, raw=a.json)
    if not a.json:
        print("✅ API stop" if r.get("ok") else "❌ " + r.get("msg", "gagal"))


# ── P-18: RPA + fingerprint-check ─────────────────────────────────────────
def cmd_fp_check(a):
    base, key, _ = resolve(a)
    r = api_req("GET", f"/api/v1/browser/fingerprint-check?user_id={a.id}",
                base=base, key=key, raw=a.json)
    if a.json:
        return
    if r.get("code") != 0:
        print("❌", r.get("msg")); return
    d = r["data"]
    print(f"🔍 Fingerprint-check: {'✅ SEMUA COCOK' if d.get('ok') else '⚠️ ADA YANG TIDAK COCOK'}")
    for c in d.get("checks", []):
        mark = "✅" if c.get("ok") is True else ("ℹ️" if c.get("ok") is None else "❌")
        print(f"  {mark} {c['field']}: live={c.get('live')!r}"
              + (f" (harus {c.get('expected')!r})" if c.get("ok") is False else "")
              + (f" — {c['note']}" if c.get("ok") is None and c.get("note") else ""))


def cmd_rpa_run(a):
    base, key, _ = resolve(a)
    if a.flow:
        data = {"user_id": a.id, "flow": a.flow}
    else:
        try:
            steps = json.load(open(a.steps_file))
        except Exception as e:
            print(f"❌ file steps tidak bisa dibaca: {e}"); return
        data = {"user_id": a.id, "steps": steps}
    r = api_req("POST", "/api/v1/rpa/run", data, base=base, key=key,
                raw=a.json, timeout=180)
    if a.json:
        return
    if r.get("code") != 0:
        print("❌", r.get("msg")); return
    d = r["data"]
    print(f"🤖 RPA: {'✅ semua langkah ok' if d.get('ok') else '⚠️ ada langkah gagal'}"
          + (" (gerak manusiawi)" if d.get("human") else " (native — behavioral_human tidak ada)"))
    for s in d.get("steps", []):
        print(f"  {'✅' if s['ok'] else '❌'} [{s['step']}] {s['type']} ({s['ms']} ms) — {s['detail']}")


def cmd_rpa_flows(a):
    base, key, _ = resolve(a)
    r = api_req("GET", "/api/v1/rpa/flows", base=base, key=key, raw=a.json)
    if a.json:
        return
    if r.get("code") != 0:
        print("❌", r.get("msg")); return
    flows = r["data"]["flows"]
    print(f"📋 {len(flows)} flow RPA:")
    for f in flows:
        print(f"  {f['name']} — {f['steps']} langkah (update {f.get('updated_at','')})")


def cmd_rpa_save(a):
    base, key, _ = resolve(a)
    try:
        steps = json.load(open(a.steps_file))
    except Exception as e:
        print(f"❌ file steps tidak bisa dibaca: {e}"); return
    r = api_req("POST", "/api/v1/rpa/flows", {"name": a.name, "steps": steps},
                base=base, key=key, raw=a.json)
    if not a.json:
        print(f"✅ Flow '{a.name}' tersimpan ({r.get('data', {}).get('steps', '?')} langkah)"
              if r.get("code") == 0 else "❌ " + r.get("msg"))


# ── F3-2: Synchronizer / Cermin ──────────────────────────────────────────
def cmd_sync_start(a):
    base, key, _ = resolve(a)
    data = {"user_id": a.leader}
    if a.followers:
        data["follower_ids"] = [x.strip() for x in a.followers.split(",") if x.strip()]
    if a.delay:
        data["open_delay_ms"] = a.delay
    r = api_req("POST", "/api/v1/sync/toSyncOperateBrowser", data,
                base=base, key=key, raw=a.json)
    if a.json:
        return
    if r.get("code") != 0:
        print("❌", r.get("msg")); return
    d = r["data"]
    print(f"🪞 Cermin jalan — leader {d.get('leader_id')}, "
          f"{len(d.get('followers', []))} follower, jeda {d.get('open_delay_ms')} ms")


def cmd_sync_stop(a):
    base, key, _ = resolve(a)
    r = api_req("POST", "/api/v1/sync/toStopSyncOperateBrowser", {},
                base=base, key=key, raw=a.json)
    if not a.json:
        print("✅ Cermin berhenti" if r.get("code") == 0 else "❌ " + r.get("msg"))


def cmd_sync_status(a):
    base, key, _ = resolve(a)
    r = api_req("GET", "/api/v1/sync/getOperateBrowser", base=base, key=key, raw=a.json)
    if a.json:
        return
    if r.get("code") != 0:
        print("❌", r.get("msg")); return
    d = r["data"]
    if not d.get("active"):
        print("🪞 Cermin tidak aktif"); return
    print(f"🪞 Cermin aktif — leader {d.get('leader_id')} "
          f"(jeda {d.get('open_delay_ms')} ms, sejak {d.get('started_at')})")
    for t in d.get("targets", []):
        print(f"  {t['profile_id']} [{t['role']}] port {t.get('debug_port')}")


def _sync_print_result(r, label):
    if r.get("code") != 0:
        print("❌", r.get("msg")); return
    d = r["data"]
    ok = d.get("ok")
    print(f"🪞 {label}: {'✅ semua jendela ok' if ok else '⚠️ ada jendela gagal'}")
    for pid, res in (d.get("results") or {}).items():
        print(f"  {'✅' if res.get('ok') else '❌'} {pid} — "
              + (str(res.get('url') or res.get('detail') or res.get('error') or res)[:100]))


def cmd_sync_open(a):
    base, key, _ = resolve(a)
    r = api_req("POST", "/api/v1/sync/openUrl", {"url": a.url},
                base=base, key=key, raw=a.json, timeout=120)
    if not a.json:
        _sync_print_result(r, "buka URL")


def cmd_sync_input(a):
    base, key, _ = resolve(a)
    data = {"text": a.text}
    if a.selector:
        data["selector"] = a.selector
    r = api_req("POST", "/api/v1/sync/toInputTxt", data,
                base=base, key=key, raw=a.json, timeout=120)
    if not a.json:
        _sync_print_result(r, "ketik")


def cmd_sync_refresh(a):
    base, key, _ = resolve(a)
    r = api_req("POST", "/api/v1/sync/toRefreshTab", {},
                base=base, key=key, raw=a.json, timeout=120)
    if not a.json:
        _sync_print_result(r, "refresh")


def cmd_sync_steps(a):
    base, key, _ = resolve(a)
    try:
        steps = json.load(open(a.steps_file))
    except Exception as e:
        print(f"❌ file steps tidak bisa dibaca: {e}"); return
    r = api_req("POST", "/api/v1/sync/steps", {"steps": steps},
                base=base, key=key, raw=a.json, timeout=180)
    if not a.json:
        _sync_print_result(r, "langkah")


# ── F3-3: tags + grup ─────────────────────────────────────────────────────
def cmd_tags(a):
    base, key, _ = resolve(a)
    r = api_req("GET", "/api/v2/browser-tags/list", base=base, key=key, raw=a.json)
    if a.json:
        return
    if r.get("code") != 0:
        print("❌", r.get("msg")); return
    tags = r["data"]["list"]
    print(f"🏷️ {len(tags)} tag:")
    for t in tags:
        print(f"  {t['name']} ({t['count']} profil)")


def cmd_set_tags(a):
    base, key, _ = resolve(a)
    tags = [t.strip() for t in (a.tags or "").split(",") if t.strip()]
    r = api_req("POST", "/api/v2/browser-profile/update",
                {"user_id": a.id, "tags": tags}, base=base, key=key, raw=a.json)
    if not a.json:
        print(f"✅ Tag profil {a.id}: {', '.join(tags) if tags else '(kosong)'}"
              if r.get("code") == 0 else "❌ " + r.get("msg"))


def cmd_group_list(a):
    base, key, _ = resolve(a)
    r = api_req("GET", "/api/v1/group/list", base=base, key=key, raw=a.json)
    if a.json:
        return
    if r.get("code") != 0:
        print("❌", r.get("msg")); return
    groups = r["data"]["list"]
    print(f"📁 {len(groups)} grup:")
    for g in groups:
        print(f"  {g['name']} ({g['count']} profil)")


def cmd_group_rename(a):
    base, key, _ = resolve(a)
    r = api_req("POST", "/api/v1/group/update",
                {"name": a.old, "new_name": a.new}, base=base, key=key, raw=a.json)
    if not a.json:
        print(f"✅ Grup '{a.old}' -> '{a.new}'"
              if r.get("code") == 0 else "❌ " + r.get("msg"))


# ── F3-4: kernel manager ──────────────────────────────────────────────────
def cmd_backup_create(a):
    base, key, gui = resolve(a)
    data = {"include_cache": not a.no_cache}
    r = api_req("POST", f"/api/profiles/{a.profile}/backup", data,
                base=gui, key=None, raw=a.json, timeout=120)
    if not a.json:
        print(f"✅ Backup dibuat: {r.get('file')} ({r.get('human')})"
              f" — cache {'ikut' if r.get('include_cache') else 'tidak ikut'}"
              if r.get("ok") else "❌ " + r.get("error"))


def cmd_backup_list(a):
    base, key, gui = resolve(a)
    r = api_req("GET", "/api/backups", base=gui, key=None, raw=a.json)
    if a.json:
        return
    bks = r.get("backups", [])
    print(f"💾 {len(bks)} backup:")
    for b in bks:
        tag = "✅" if b.get("valid") else "⚠️ rusak"
        print(f"  {tag} {b['file']} ({b.get('human', b.get('bytes'))})"
              + (f" — {b.get('profile_name')} @ {b.get('exported_at')}"
                 if b.get("valid") else ""))


def cmd_backup_restore(a):
    base, key, gui = resolve(a)
    data = {"new_name": a.name} if a.name else {}
    r = api_req("POST", f"/api/backups/{a.file}/restore", data,
                base=gui, key=None, raw=a.json, timeout=120)
    if not a.json:
        p = r.get("profile", {})
        print(f"✅ Restore jadi profil baru: {p.get('name')} ({p.get('id')})"
              if r.get("ok") else "❌ " + r.get("error"))


def cmd_backup_delete(a):
    base, key, gui = resolve(a)
    r = api_req("DELETE", f"/api/backups/{a.file}", base=gui, key=None,
                raw=a.json)
    if not a.json:
        print(f"✅ Backup {a.file} dihapus" if r.get("ok") else "❌ " + r.get("error"))


def cmd_cache_size(a):
    base, key, gui = resolve(a)
    r = api_req("GET", f"/api/profiles/{a.profile}/cache-size",
                base=gui, key=None, raw=a.json)
    if not a.json:
        print(f"💾 Cache {a.profile}: {r.get('human')} ({r.get('bytes')} byte)"
              if r.get("ok") else "❌ " + r.get("error"))


def cmd_batch_import(a):
    base, key, gui = resolve(a)
    with open(a.file, encoding="utf-8-sig") as f:
        content = f.read()
    fmt = a.format or ("json" if a.file.lower().endswith(".json") else "csv")
    r = api_req("POST", "/api/profiles/import?async=1",
                {"content": content, "format": fmt},
                base=gui, key=None, raw=a.json, timeout=30)
    if a.json:
        return
    if not r.get("ok"):
        print("❌", r.get("error")); return
    job_id = r["job_id"]
    print(f"📥 Job impor {job_id} ({r['total']} baris) — memantau...")
    _poll_batch_job(gui, job_id)


def _poll_batch_job(gui, job_id, interval=0.5, timeout=300):
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = api_req("GET", f"/api/batch/jobs/{job_id}", base=gui, key=None)
        job = r.get("job") or {}
        state = job.get("state")
        if state in ("done", "cancelled", "error"):
            print(f"  {state}: {job.get('done', 0)}/{job.get('total', 0)} "
                  f"— dibuat {len(job.get('created', []))}, "
                  f"gagal {len(job.get('failed', []))}")
            for f_ in job.get("failed", [])[:10]:
                print(f"    ⚠️ baris {f_.get('line')}: {f_.get('error')}")
            return
        time.sleep(interval)
    print("⏳ Job masih berjalan (timeout pantau — cek batch-job", job_id, ")")


def cmd_batch_export(a):
    base, key, gui = resolve(a)
    data = {"format": a.format}
    if a.group:
        data["group"] = a.group
    r = api_req("POST", "/api/profiles/export", data, base=gui, key=None,
                raw=a.json, timeout=30)
    if a.json:
        return
    if not r.get("ok"):
        print("❌", r.get("error")); return
    job_id = r["job_id"]
    print(f"📤 Job ekspor {job_id} ({r['total']} profil) — memantau...")
    import time
    t0 = time.time()
    while time.time() - t0 < 120:
        rr = api_req("GET", f"/api/batch/jobs/{job_id}", base=gui, key=None)
        job = rr.get("job") or {}
        if job.get("state") == "done":
            fname = (job.get("result") or {}).get("filename", f"{job_id}.{a.format}")
            out = a.out or fname
            import urllib.request
            urllib.request.urlretrieve(f"{gui}/api/batch/jobs/{job_id}/download", out)
            print(f"✅ Ekspor tersimpan: {out} ({job['result']['bytes']} byte)")
            return
        if job.get("state") in ("cancelled", "error"):
            print("❌ Job", job.get("state"), job.get("failed")); return
        time.sleep(0.5)
    print("⏳ Job masih berjalan — cek batch-job", job_id)


def cmd_batch_jobs(a):
    base, key, gui = resolve(a)
    r = api_req("GET", "/api/batch/jobs", base=gui, key=None, raw=a.json)
    if a.json:
        return
    for j in r.get("jobs", [])[:15]:
        print(f"  {j['job_id']} [{j['kind']}] {j['state']} "
              f"{j.get('done', 0)}/{j.get('total', 0)} "
              f"({j.get('started_at', '')})")


def cmd_batch_job(a):
    base, key, gui = resolve(a)
    r = api_req("GET", f"/api/batch/jobs/{a.job}", base=gui, key=None, raw=a.json)
    if a.json:
        return
    job = r.get("job")
    if not job:
        print("❌", r.get("error")); return
    print(f"📋 {job['job_id']} [{job['kind']}] {job['state']} "
          f"{job.get('done', 0)}/{job.get('total', 0)}")
    print(f"   dibuat {len(job.get('created', []))}, gagal {len(job.get('failed', []))}")
    for f_ in job.get("failed", [])[:10]:
        print(f"    ⚠️ baris {f_.get('line')}: {f_.get('error')}")


def cmd_batch_cancel(a):
    base, key, gui = resolve(a)
    r = api_req("POST", f"/api/batch/jobs/{a.job}/cancel", {},
                base=gui, key=None, raw=a.json)
    if not a.json:
        print(f"✅ Pembatalan diminta: {r.get('job', {}).get('state')}"
              if r.get("ok") else "❌ " + r.get("error"))


def _upload_file(base, route, filepath, timeout=120):
    """Upload multipart 1 file ke GUI. Return dict JSON (atau error)."""
    import http.client
    import mimetypes
    import uuid
    from urllib.parse import urlparse
    u = urlparse(base)
    boundary = uuid.uuid4().hex
    with open(filepath, "rb") as f:
        data = f.read()
    fname = os.path.basename(filepath)
    ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    body = (f"--{boundary}\r\n".encode()
            + f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'.encode()
            + f"Content-Type: {ctype}\r\n\r\n".encode()
            + data + f"\r\n--{boundary}--\r\n".encode())
    conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)
    conn.request("POST", route, body=body,
                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8", errors="replace")
    conn.close()
    try:
        return json.loads(raw)
    except Exception:
        return {"ok": False, "error": f"HTTP {resp.status}: {raw[:200]}"}


def cmd_ext_list(a):
    base, key, gui = resolve(a)
    r = api_req("GET", "/api/extensions", base=gui, key=None, raw=a.json)
    if a.json:
        return
    exts = r.get("extensions", [])
    print(f"🧩 {len(exts)} extension:")
    for e in exts:
        risk = (e.get("risk") or {}).get("level", "?")
        pin = f" 📌{e['pinned_version']}" if e.get("pinned_version") else ""
        print(f"  {e['id']} — {e.get('name')} v{e.get('version')} "
              f"[risk:{risk}]{pin}")


def cmd_ext_preview(a):
    base, key, gui = resolve(a)
    r = _upload_file(gui, "/api/extensions/preview", a.file)
    if a.json:
        print(json.dumps(r, indent=1)); return
    if not r.get("ok"):
        print("❌", r.get("error")); return
    p = r["preview"]
    m = p["manifest"]
    print(f"🧩 {m['name']} v{m['version']} (manifest v{m['manifest_version']})")
    print(f"   izin: {', '.join(m.get('permissions') or ['-'])}")
    print(f"   host: {', '.join(m.get('host_permissions') or ['-'])}")
    risk = m.get("risk") or {}
    print(f"   risiko: {risk.get('level')}")
    for fl in risk.get("flags", []):
        print(f"    ⚠️ {fl}")
    if p.get("crx"):
        c = p["crx"]
        print(f"   CRX: {c.get('format')} valid={c.get('valid')} "
              f"zip_ok={c.get('zip_ok')} "
              f"key={str(c.get('public_key_sha256'))[:16]}...")


def cmd_ext_install(a):
    base, key, gui = resolve(a)
    r = _upload_file(gui, "/api/extensions", a.file)
    if a.json:
        print(json.dumps(r, indent=1)); return
    if not r.get("ok"):
        print("❌", r.get("error")); return
    e = r["extension"]
    print(f"✅ Terinstal: {e['name']} v{e['version']} ({e['id']}) "
          f"[risk:{(e.get('risk') or {}).get('level')}]")


def cmd_ext_pin(a):
    base, key, gui = resolve(a)
    data = {"version": a.version} if a.version else {}
    r = api_req("POST", f"/api/extensions/{a.id}/pin", data,
                base=gui, key=None, raw=a.json)
    if not a.json:
        print(f"✅ {a.id} dikunci ke v{r.get('extension', {}).get('pinned_version')}"
              if r.get("ok") else "❌ " + r.get("error"))


def cmd_ext_unpin(a):
    base, key, gui = resolve(a)
    r = api_req("DELETE", f"/api/extensions/{a.id}/pin", base=gui, key=None,
                raw=a.json)
    if not a.json:
        print(f"✅ Kunci versi {a.id} dilepas" if r.get("ok") else "❌ " + r.get("error"))


def cmd_ext_update(a):
    base, key, gui = resolve(a)
    route = f"/api/extensions/{a.id}/update" + ("?force=1" if a.force else "")
    r = _upload_file(gui, route, a.file)
    if a.json:
        print(json.dumps(r, indent=1)); return
    if not r.get("ok"):
        print("❌", r.get("error")); return
    e = r["extension"]
    print(f"✅ Update: {e['name']} kini v{e['version']} ({e['id']})")


def cmd_ext_delete(a):
    base, key, gui = resolve(a)
    r = api_req("DELETE", f"/api/extensions/{a.id}", base=gui, key=None,
                raw=a.json)
    if not a.json:
        print(f"✅ Extension {a.id} dihapus" if r.get("ok") else "❌ " + r.get("error"))


def cmd_login(a):
    """F3-8: login ke GUI (simpan token sesi chmod 600)."""
    import getpass
    base, key, gui = resolve(a)
    pw = a.password or getpass.getpass("Password GUI: ")
    r = api_req("POST", "/api/auth/login", {"password": pw},
                base=gui, key=None, raw=a.json)
    if a.json:
        return
    if r.get("ok") and r.get("token"):
        _save_session_token(r["token"])
        print("✅ Login OK — token sesi tersimpan "
              f"({SESSION_FILE})")
    else:
        print("❌", r.get("error", r))
        if r.get("error") == "login diperlukan":
            print("   (GUI butuh login — jalankan login dulu)")
    if r.get("code") == 429 or "terlalu banyak" in str(r.get("error", "")):
        print("   (terkunci 15 menit karena 5x gagal)")


def cmd_logout(a):
    """F3-8: logout dari GUI (hapus sesi server + token lokal)."""
    base, key, gui = resolve(a)
    r = api_req("POST", "/api/auth/logout", {}, base=gui, key=None,
                raw=a.json)
    _clear_session_token()
    if not a.json:
        print("✅ Logout OK" if r.get("ok") else "ℹ️ Token lokal dihapus")


def cmd_kernel_list(a):
    base, key, gui = resolve(a)
    r = api_req("GET", "/api/kernels", base=gui, key=None, raw=a.json)
    if a.json:
        return
    if r.get("ok") is not True and "kernels" not in r:
        print("❌", r.get("error", r)); return
    print(f"🧩 Kernel default: {r.get('default')}")
    if r.get("system"):
        s = r["system"]
        print(f"  system — Chromium {s.get('version')} ({s.get('path')})")
    for k in r.get("kernels", []):
        print(f"  {k['id']} — {k['name']} [{k['engine']}]"
              + (" [default]" if k.get("is_default") else "")
              + f" ({k.get('path')})")


def cmd_kernel_download(a):
    base, key, gui = resolve(a)
    r = api_req("POST", "/api/kernels/download", {"version": a.version or None},
                base=gui, key=None, raw=a.json, timeout=30)
    if a.json:
        return
    if not r.get("ok"):
        print("❌", r.get("error")); return
    print(f"⬇️ Unduh kernel dimulai — job {r.get('job_id')} "
          f"(versi {r.get('version')}). Pantau: kernel-downloads {r.get('job_id')}")


def cmd_kernel_downloads(a):
    base, key, gui = resolve(a)
    path = f"/api/kernels/downloads/{a.job}" if a.job else "/api/kernels/downloads"
    r = api_req("GET", path, base=gui, key=None, raw=a.json)
    if a.json:
        return
    if a.job:
        if not r.get("ok"):
            print("❌", r.get("error")); return
        print(f"⬇️ {r['job_id']}: {r['state']} {r.get('downloaded',0)}/{r.get('total',0)}"
              + (f" kernel {r.get('kernel_id')}" if r.get("kernel_id") else "")
              + (f" — {r.get('error')}" if r.get("error") else ""))
        return
    jobs = r.get("jobs", [])
    print(f"⬇️ {len(jobs)} job unduh:")
    for j in jobs:
        print(f"  {j['job_id']} — {j['state']} (versi {j.get('version')})")


def cmd_kernel_register(a):
    base, key, gui = resolve(a)
    data = {"path": a.path, "engine": a.engine}
    if a.name:
        data["name"] = a.name
    r = api_req("POST", "/api/kernels/register", data,
                base=gui, key=None, raw=a.json)
    if not a.json:
        print(f"✅ Kernel terdaftar: {r['kernel']['id']} ({r['kernel']['version']})"
              if r.get("ok") else "❌ " + r.get("error"))


def cmd_kernel_default(a):
    base, key, gui = resolve(a)
    r = api_req("POST", f"/api/kernels/{a.id}/default", {},
                base=gui, key=None, raw=a.json)
    if not a.json:
        print(f"✅ Default kernel: {r.get('default')}"
              if r.get("ok") else "❌ " + r.get("error"))


def cmd_kernel_remove(a):
    base, key, gui = resolve(a)
    r = api_req("DELETE", f"/api/kernels/{a.id}", base=gui, key=None, raw=a.json)
    if not a.json:
        print("✅ Kernel dihapus" if r.get("ok") else "❌ " + r.get("error"))


def cmd_kernel_set(a):
    base, key, gui = resolve(a)
    r = api_req("POST", f"/api/profiles/{a.profile}/kernel",
                {"kernel_id": a.kernel}, base=gui, key=None, raw=a.json)
    if not a.json:
        print(f"✅ Profil {a.profile} memakai kernel {a.kernel}"
              if r.get("ok") else "❌ " + r.get("error"))


def main():
    p = argparse.ArgumentParser(prog="antibrowser-cli.py",
                                description="Kontrol StealthXGM Local API dari cmd/termux")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--key", default=None)
    p.add_argument("--gui", default=GUI_URL)
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("list", help="list profil")
    c.add_argument("--group", default="", help="filter grup (F3-3)")
    c.add_argument("--tags", default="", help="filter tag, pisah koma (F3-3)")
    c = sub.add_parser("create", help="bikin profil")
    c.add_argument("--name", required=True)
    c.add_argument("--group", default="")
    c = sub.add_parser("launch", help="launch browser")
    c.add_argument("id")
    c.add_argument("--headless", action="store_true",
                   help="launch tanpa jendela (P-14)")
    c = sub.add_parser("stop", help="stop browser")
    c.add_argument("id")
    c = sub.add_parser("delete", help="hapus profil (ke Trash)")
    c.add_argument("id")
    sub.add_parser("status", help="status API")
    sub.add_parser("api-start", help="nyalakan Local API")
    sub.add_parser("api-stop", help="matikan Local API")
    c = sub.add_parser("fp-check", help="fingerprint-check live profil yang jalan (P-18)")
    c.add_argument("id")
    c = sub.add_parser("rpa-run", help="jalankan langkah/flow RPA (P-18)")
    c.add_argument("id")
    c.add_argument("--steps-file", help="file JSON berisi daftar langkah")
    c.add_argument("--flow", help="nama flow tersimpan")
    sub.add_parser("rpa-flows", help="daftar flow RPA tersimpan (P-18)")
    c = sub.add_parser("rpa-save", help="simpan flow RPA dari file JSON (P-18)")
    c.add_argument("name")
    c.add_argument("--steps-file", required=True)
    c = sub.add_parser("sync-start", help="mulai Cermin: mirror aksi ke semua jendela (F3-2)")
    c.add_argument("leader", help="profile id leader")
    c.add_argument("--followers", help="daftar follower dipisah koma (kosong = semua yang jalan)")
    c.add_argument("--delay", type=int, default=0, help="jeda ms antar-jendela")
    sub.add_parser("sync-stop", help="hentikan Cermin (F3-2)")
    sub.add_parser("sync-status", help="status sesi Cermin (F3-2)")
    c = sub.add_parser("sync-open", help="buka URL di semua jendela Cermin (F3-2)")
    c.add_argument("url")
    c = sub.add_parser("sync-input", help="ketik teks di semua jendela Cermin (F3-2)")
    c.add_argument("text")
    c.add_argument("--selector", help="selector CSS (kosong = elemen fokus)")
    sub.add_parser("sync-refresh", help="refresh semua jendela Cermin (F3-2)")
    c = sub.add_parser("sync-steps", help="cerminkan langkah RPA ke semua jendela (F3-2)")
    c.add_argument("--steps-file", required=True)
    sub.add_parser("tags", help="daftar tag + jumlah profil (F3-3)")
    c = sub.add_parser("set-tags", help="timpa tag satu profil (F3-3)")
    c.add_argument("id")
    c.add_argument("--tags", default="", help="tag pisah koma (kosong = hapus semua)")
    sub.add_parser("group-list", help="daftar grup (F3-3)")
    c = sub.add_parser("group-rename", help="ganti nama grup (F3-3)")
    c.add_argument("old")
    c.add_argument("new")
    sub.add_parser("kernel-list", help="daftar kernel browser (F3-4)")
    c = sub.add_parser("kernel-download", help="unduh kernel Chromium terbaru/versi tertentu (F3-4)")
    c.add_argument("version", nargs="?", help="versi, mis. 156.0.8078.4 (kosong = terbaru)")
    c = sub.add_parser("kernel-downloads", help="status job unduh kernel (F3-4)")
    c.add_argument("job", nargs="?", help="job id (kosong = semua job)")
    c = sub.add_parser("kernel-register", help="daftarkan binary browser yang sudah ada (F3-4)")
    c.add_argument("path")
    c.add_argument("--name", default="")
    c.add_argument("--engine", default="chromium", choices=["chromium", "firefox"])
    c = sub.add_parser("kernel-default", help="jadikan kernel default (F3-4)")
    c.add_argument("id")
    c = sub.add_parser("kernel-remove", help="hapus kernel terdaftar (F3-4)")
    c.add_argument("id")
    c = sub.add_parser("kernel-set", help="pilih kernel untuk satu profil (F3-4)")
    c.add_argument("profile")
    c.add_argument("kernel", help="id kernel atau 'system'")
    c = sub.add_parser("backup-create", help="ekspor profil ke ZIP (F3-5)")
    c.add_argument("profile")
    c.add_argument("--no-cache", action="store_true",
                   help="jangan sertakan cache")
    sub.add_parser("backup-list", help="daftar file backup (F3-5)")
    c = sub.add_parser("backup-restore", help="restore backup jadi profil baru (F3-5)")
    c.add_argument("file")
    c.add_argument("--name", default="")
    c = sub.add_parser("backup-delete", help="hapus file backup (F3-5)")
    c.add_argument("file")
    c = sub.add_parser("cache-size", help="ukuran cache profil (F3-3/F3-5)")
    c.add_argument("profile")
    c = sub.add_parser("batch-import", help="impor batch CSV/JSON (job async, F3-6)")
    c.add_argument("file")
    c.add_argument("--format", default="", choices=["", "csv", "json"])
    c = sub.add_parser("batch-export", help="ekspor profil ke CSV/JSON (job async, F3-6)")
    c.add_argument("--format", default="csv", choices=["csv", "json"])
    c.add_argument("--group", default="")
    c.add_argument("--out", default="")
    sub.add_parser("batch-jobs", help="daftar job batch (F3-6)")
    c = sub.add_parser("batch-job", help="status satu job batch (F3-6)")
    c.add_argument("job")
    c = sub.add_parser("batch-cancel", help="batalkan job batch (F3-6)")
    c.add_argument("job")
    sub.add_parser("ext-list", help="daftar extension library (F3-7)")
    c = sub.add_parser("ext-preview", help="pratinjau file extension tanpa install (F3-7)")
    c.add_argument("file")
    c = sub.add_parser("ext-install", help="install extension .crx/.zip (F3-7)")
    c.add_argument("file")
    c = sub.add_parser("ext-pin", help="kunci extension ke satu versi (F3-7)")
    c.add_argument("id")
    c.add_argument("version", nargs="?", help="versi (kosong = versi terinstal)")
    c = sub.add_parser("ext-unpin", help="lepas kunci versi extension (F3-7)")
    c.add_argument("id")
    c = sub.add_parser("ext-update", help="update extension dari file baru (F3-7)")
    c.add_argument("id")
    c.add_argument("file")
    c.add_argument("--force", action="store_true",
                   help="izinkan reinstall versi sama/lebih lama")
    c = sub.add_parser("ext-delete", help="hapus extension dari library (F3-7)")
    c.add_argument("id")
    c = sub.add_parser("login", help="login ke GUI — simpan token sesi (F3-8)")
    c.add_argument("--password", default="",
                   help="password (kosong = ditanya interaktif)")
    sub.add_parser("logout", help="logout dari GUI — hapus sesi (F3-8)")

    a = p.parse_args()
    {"list": cmd_list, "create": cmd_create, "launch": cmd_launch,
     "stop": cmd_stop, "delete": cmd_delete, "status": cmd_status,
     "api-start": cmd_api_start, "api-stop": cmd_api_stop,
     "fp-check": cmd_fp_check, "rpa-run": cmd_rpa_run,
     "rpa-flows": cmd_rpa_flows, "rpa-save": cmd_rpa_save,
     "sync-start": cmd_sync_start, "sync-stop": cmd_sync_stop,
     "sync-status": cmd_sync_status, "sync-open": cmd_sync_open,
     "sync-input": cmd_sync_input, "sync-refresh": cmd_sync_refresh,
     "sync-steps": cmd_sync_steps,
     "tags": cmd_tags, "set-tags": cmd_set_tags,
     "group-list": cmd_group_list, "group-rename": cmd_group_rename,
     "kernel-list": cmd_kernel_list, "kernel-download": cmd_kernel_download,
     "kernel-downloads": cmd_kernel_downloads,
     "kernel-register": cmd_kernel_register,
     "kernel-default": cmd_kernel_default,
     "kernel-remove": cmd_kernel_remove,
     "kernel-set": cmd_kernel_set,
     "backup-create": cmd_backup_create, "backup-list": cmd_backup_list,
     "backup-restore": cmd_backup_restore,
     "backup-delete": cmd_backup_delete,
     "cache-size": cmd_cache_size,
     "batch-import": cmd_batch_import, "batch-export": cmd_batch_export,
     "batch-jobs": cmd_batch_jobs, "batch-job": cmd_batch_job,
     "batch-cancel": cmd_batch_cancel,
     "ext-list": cmd_ext_list, "ext-preview": cmd_ext_preview,
     "ext-install": cmd_ext_install, "ext-pin": cmd_ext_pin,
     "ext-unpin": cmd_ext_unpin, "ext-update": cmd_ext_update,
     "ext-delete": cmd_ext_delete,
     "login": cmd_login, "logout": cmd_logout}[a.cmd](a)


if __name__ == "__main__":
    main()
