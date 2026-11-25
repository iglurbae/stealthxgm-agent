"""Batch Import — import banyak profil sekaligus dari CSV/JSON.

CSV format (header wajib, case-insensitive):
    name,group,pool,platform,timezone,notes,warp_fallback,mobile

- name: wajib, unik (duplikat ditolak)
- group: opsional (default: "default")
- pool: opsional, nama pool (harus ada di proxy pools; kosong = pool default)
- platform: opsional (windows|macos|linux|android|ios; default windows)
  - ios SELALU mobile (mobile dipaksa True — iOS tidak punya desktop)
- timezone: opsional (default Asia/Jakarta)
- notes: opsional
- warp_fallback: opsional (true/false/1/0/yes/no; default true)
- mobile: opsional (true/false/1/0/yes/no; default false)

JSON format: array of profile objects, sama shape dengan POST /api/profiles,
plus field "pool" (nama pool) sebagai shortcut untuk proxy.pool_id.

Semua validasi dilakukan per baris; baris yang gagal tidak diimport
dan dilaporkan dengan alasan.
"""
import csv
import io
import json

import profiles as pm
import proxy_pools as pp

PLATFORMS = {"windows", "macos", "linux", "android", "ios"}

TRUE_SET = {"true", "1", "yes", "y", "on"}
FALSE_SET = {"false", "0", "no", "n", "off"}


def _parse_bool(v, default):
    if v is None or (isinstance(v, str) and not v.strip()):
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in TRUE_SET:
        return True
    if s in FALSE_SET:
        return False
    return default


def csv_template():
    """Return example CSV content."""
    return (
        "name,group,pool,platform,timezone,notes,warp_fallback,mobile\r\n"
        "Tokopedia Akun 1,marketplace,DataImpulse (proxy-bot),windows,Asia/Jakarta,akun utama,true,false\r\n"
        "Shopee Akun 2,marketplace,,android,Asia/Jakarta,,true,true\r\n"
        "iPhone Akun 3,marketplace,,ios,Asia/Jakarta,,true,true\r\n"
    )


def json_template():
    """Return example JSON content."""
    return json.dumps([
        {
            "name": "Tokopedia Akun 1",
            "group": "marketplace",
            "pool": "DataImpulse (proxy-bot)",
            "notes": "akun utama",
            "fingerprint": {"platform": "windows", "timezone": "Asia/Jakarta", "mobile": False},
            "warp_fallback": True,
        },
        {
            "name": "Shopee Akun 2",
            "group": "marketplace",
            "fingerprint": {"platform": "android", "timezone": "Asia/Jakarta", "mobile": True},
        },
    ], indent=2, ensure_ascii=False)


def _pool_lookup():
    """name (lower) -> pool id, plus id -> id passthrough."""
    pools = pp.list_pools()
    by_name = {}
    for p in pools:
        by_name[p["name"].strip().lower()] = p["id"]
        by_name[p["id"].lower()] = p["id"]
    return by_name


def _default_pool_id():
    p = pp.get_default_pool()
    return p["id"] if p else None


def parse_csv(content):
    """Parse CSV text -> (rows, errors).

    rows: list of dicts {line, data} where data is normalized profile input.
    errors: list of {line, error} for header/structural problems.
    """
    errors = []
    rows = []
    try:
        reader = csv.DictReader(io.StringIO(content))
    except Exception as e:
        return [], [{"line": 0, "error": f"gagal baca CSV: {e}"}]

    if reader.fieldnames is None:
        return [], [{"line": 0, "error": "file kosong atau tanpa header"}]

    headers = {h.strip().lower(): h for h in reader.fieldnames if h and h.strip()}
    if "name" not in headers:
        return [], [{"line": 0, "error": "header 'name' wajib ada"}]

    pools = _pool_lookup()
    default_pid = _default_pool_id()

    for i, raw in enumerate(reader, start=2):  # line 1 = header
        # skip fully empty rows
        if not any((v or "").strip() for v in raw.values() if v is not None):
            continue
        get = lambda k: (raw.get(headers.get(k, k)) or "").strip() if headers.get(k) else ""

        name = get("name")
        if not name:
            errors.append({"line": i, "error": "nama kosong"})
            continue

        group = get("group") or "default"
        pool_name = get("pool")
        platform = (get("platform") or "windows").lower()
        timezone = get("timezone") or "Asia/Jakarta"
        notes = get("notes")

        if platform not in PLATFORMS:
            errors.append({"line": i, "name": name,
                           "error": f"platform '{platform}' tidak valid (windows|macos|linux|android)"})
            continue

        pool_id = None
        if pool_name:
            pool_id = pools.get(pool_name.strip().lower())
            if not pool_id:
                errors.append({"line": i, "name": name,
                               "error": f"pool '{pool_name}' tidak ditemukan"})
                continue
        else:
            pool_id = default_pid

        # F3-6: iOS selalu mobile (launcher hanya memakai platform ios
        # bila fp.mobile True — lihat launcher._consistent_fallback_identity).
        mobile = _parse_bool(get("mobile"), False)
        if platform == "ios":
            mobile = True

        rows.append({
            "line": i,
            "data": {
                "name": name,
                "group": group,
                "notes": notes,
                "fingerprint": {
                    "platform": platform,
                    "timezone": timezone,
                    "mobile": mobile,
                },
                "proxy": {"pool_id": pool_id} if pool_id else {"type": "none"},
                "warp_fallback": _parse_bool(get("warp_fallback"), True),
            },
        })
    return rows, errors


def parse_json(content):
    """Parse JSON text -> (rows, errors). Expects array of objects."""
    errors = []
    rows = []
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return [], [{"line": 0, "error": f"JSON tidak valid: {e}"}]

    if not isinstance(data, list):
        return [], [{"line": 0, "error": "JSON harus array of objects"}]

    pools = _pool_lookup()
    default_pid = _default_pool_id()

    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            errors.append({"line": i, "error": "item bukan object"})
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            errors.append({"line": i, "error": "nama kosong"})
            continue

        item = dict(item)  # copy
        item["name"] = name

        # pool name -> pool_id shortcut
        pool_name = item.pop("pool", None)
        if pool_name:
            pool_id = pools.get(str(pool_name).strip().lower())
            if not pool_id:
                errors.append({"line": i, "name": name,
                               "error": f"pool '{pool_name}' tidak ditemukan"})
                continue
            proxy = item.get("proxy") or {}
            proxy["pool_id"] = pool_id
            item["proxy"] = proxy
        elif "proxy" not in item and default_pid:
            item["proxy"] = {"pool_id": default_pid}

        # validate platform if given
        fp = item.get("fingerprint") or {}
        platform = str(fp.get("platform", "windows")).lower()
        if platform not in PLATFORMS:
            errors.append({"line": i, "name": name,
                           "error": f"platform '{platform}' tidak valid"})
            continue
        fp["platform"] = platform
        # F3-6: iOS selalu mobile (lihat parse_csv).
        if platform == "ios":
            fp["mobile"] = True
        item["fingerprint"] = fp

        rows.append({"line": i, "data": item})
    return rows, errors


def preview_rows(rows):
    """Lightweight preview: name/group/pool/platform per row."""
    pools = {p["id"]: p["name"] for p in pp.list_pools()}
    out = []
    for r in rows:
        d = r["data"]
        pool_id = (d.get("proxy") or {}).get("pool_id")
        out.append({
            "line": r["line"],
            "name": d.get("name"),
            "group": d.get("group", "default"),
            "pool": pools.get(pool_id, "-") if pool_id else "-",
            "platform": (d.get("fingerprint") or {}).get("platform", "windows"),
        })
    return out


def _create_one(row, existing, seen_batch):
    """Buat satu profil dari baris tervalidasi.

    Return (profile, None) bila sukses, (None, {line, name, error}) bila
    gagal. Dipisah supaya job impor (thread) dan test bisa memakainya.
    """
    d = row["data"]
    name = d["name"]
    key = name.strip().lower()
    if key in existing or key in seen_batch:
        return None, {"line": row["line"], "name": name,
                      "error": "nama duplikat (sudah ada)"}
    try:
        p = pm.create_profile(d)
    except Exception as e:
        return None, {"line": row["line"], "name": name,
                      "error": f"gagal buat profil: {e}"}
    seen_batch.add(key)
    return p, None


def import_rows(rows):
    """Create profiles from validated rows. Returns (created, failed).

    created: list of created profile dicts.
    failed: list of {line, name, error}.
    """
    existing = {p["name"].strip().lower() for p in pm.list_profiles()}
    created, failed = [], []
    seen_batch = set()

    for r in rows:
        p, err = _create_one(r, existing, seen_batch)
        if err:
            failed.append(err)
        else:
            created.append(p)
    return created, failed


# ── F3-6: export + job impor/ekspor (progress + cancel) ───────────────────
import datetime
import os
import secrets
import threading

EXPORT_COLUMNS = ("name", "group", "pool", "platform", "timezone", "notes",
                  "warp_fallback", "mobile", "tags", "kernel", "cache_backup")

_JOBS_LOCK = threading.Lock()
_JOBS = {}  # job_id -> dict (cache memori; sumber kebenaran = file JSON)


def _data_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "data")


def _jobs_file():
    return os.path.join(_data_dir(), "batch_jobs.json")


def _exports_dir():
    return os.path.join(_data_dir(), "batch_exports")


def _load_jobs():
    try:
        with open(_jobs_file()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_jobs(jobs):
    os.makedirs(_data_dir(), exist_ok=True)
    tmp = _jobs_file() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(jobs, f)
    os.replace(tmp, _jobs_file())


def _update_job(job_id, **fields):
    with _JOBS_LOCK:
        jobs = _load_jobs()
        job = jobs.get(job_id)
        if not job:
            return None
        job.update(fields)
        jobs[job_id] = job
        _JOBS[job_id] = job
        _save_jobs(jobs)
        return job


def _new_job(kind, total, meta=None):
    job_id = "bj_" + secrets.token_hex(6)
    job = {"job_id": job_id, "kind": kind, "state": "running",
           "total": total, "done": 0,
           "created": [], "failed": [],
           "cancel_requested": False,
           "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "finished_at": None,
           "result": None}
    if meta:
        job.update(meta)
    with _JOBS_LOCK:
        jobs = _load_jobs()
        jobs[job_id] = job
        _JOBS[job_id] = job
        _save_jobs(jobs)
    return job


def get_job(job_id):
    """Ambil satu job (file JSON sumber kebenaran)."""
    return _load_jobs().get(job_id)


def list_jobs():
    """Daftar job, terbaru dulu."""
    jobs = _load_jobs()
    return sorted(jobs.values(), key=lambda j: j.get("started_at", ""),
                  reverse=True)


def cancel_job(job_id):
    """Minta job berhenti. Worker memeriksa flag antar baris; job yang
    sudah selesai tidak bisa dibatalkan. Return job atau None."""
    job = get_job(job_id)
    if not job:
        return None
    if job["state"] in ("done", "cancelled", "error"):
        return job
    return _update_job(job_id, cancel_requested=True)


def _run_import_job(job_id, rows, parse_errors):
    existing = {p["name"].strip().lower() for p in pm.list_profiles()}
    seen_batch = set()
    created, failed = [], list(parse_errors)
    cancelled = False
    for r in rows:
        job = get_job(job_id)
        if job and job.get("cancel_requested"):
            cancelled = True
            break
        p, err = _create_one(r, existing, seen_batch)
        if err:
            failed.append(err)
        else:
            created.append({"id": p["id"], "name": p["name"]})
        _update_job(job_id, done=len(created) + len(failed) - len(parse_errors),
                    created=created, failed=failed)
    _update_job(job_id,
                state="cancelled" if cancelled else "done",
                done=len(created) + len(failed) - len(parse_errors),
                created=created, failed=failed,
                finished_at=datetime.datetime.now().isoformat(timespec="seconds"))


def start_import_job(content, fmt):
    """Mulai impor asinkron. Return job (state running). Pantau via get_job.

    fmt: "csv" | "json". Parse error tidak menggagalkan job — baris yang
    valid tetap diimpor, error dilaporkan di job.failed.
    """
    if fmt == "json":
        rows, errors = parse_json(content)
    elif fmt == "csv":
        rows, errors = parse_csv(content)
    else:
        raise ValueError("format harus csv atau json")
    job = _new_job("import", len(rows),
                   meta={"format": fmt, "failed": list(errors)})
    if not rows:
        return _update_job(job["job_id"], state="done",
                           finished_at=datetime.datetime.now().isoformat(timespec="seconds")) or job
    t = threading.Thread(target=_run_import_job,
                         args=(job["job_id"], rows, errors), daemon=True)
    t.start()
    return job


def _export_dict(p):
    """Satu profil -> dict siap ekspor (bentuk yang bisa diimpor lagi)."""
    pools = {x["id"]: x["name"] for x in pp.list_pools()}
    fp = p.get("fingerprint") or {}
    proxy = p.get("proxy") or {}
    return {"name": p.get("name"), "group": p.get("group", "default"),
            "pool": pools.get(proxy.get("pool_id"), ""),
            "platform": fp.get("platform", "windows"),
            "timezone": fp.get("timezone", "Asia/Jakarta"),
            "notes": p.get("notes", ""),
            "warp_fallback": p.get("warp_fallback", True),
            "mobile": bool(fp.get("mobile")),
            "tags": list(p.get("tags") or []),
            "kernel": p.get("kernel", "system"),
            "cache_backup": bool(p.get("cache_backup", True)),
            "fingerprint": {"platform": fp.get("platform", "windows"),
                            "timezone": fp.get("timezone", "Asia/Jakarta"),
                            "mobile": bool(fp.get("mobile"))},
            "proxy": proxy}


def export_profiles(ids=None, fmt="csv", group=None):
    """Ekspor profil (sinkron, untuk set kecil). Return (filename, content).

    ids: daftar id (kosong = semua). group: filter grup. fmt: csv|json.
    Format keluaran bisa diimpor kembali (round-trip).
    """
    profiles = pm.list_profiles()
    if ids:
        want = set(ids)
        profiles = [p for p in profiles if p["id"] in want]
    if group:
        profiles = [p for p in profiles if p.get("group") == group]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if fmt == "json":
        content = json.dumps([_export_dict(p) for p in profiles],
                             indent=2, ensure_ascii=False)
        return f"profiles-export-{stamp}.json", content
    if fmt != "csv":
        raise ValueError("format harus csv atau json")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(EXPORT_COLUMNS))
    w.writeheader()
    for p in profiles:
        d = _export_dict(p)
        w.writerow({c: (";".join(d[c]) if isinstance(d[c], list) else d[c])
                    for c in EXPORT_COLUMNS})
    return f"profiles-export-{stamp}.csv", buf.getvalue()


def _run_export_job(job_id, ids, fmt, group):
    try:
        profiles = pm.list_profiles()
        if ids:
            want = set(ids)
            profiles = [p for p in profiles if p["id"] in want]
        if group:
            profiles = [p for p in profiles if p.get("group") == group]
        # Bangun konten per profil supaya progress terlihat.
        if fmt == "json":
            dicts = []
            for i, p in enumerate(profiles, start=1):
                if (get_job(job_id) or {}).get("cancel_requested"):
                    _update_job(job_id, state="cancelled",
                                finished_at=datetime.datetime.now().isoformat(timespec="seconds"))
                    return
                dicts.append(_export_dict(p))
                _update_job(job_id, done=i)
            content = json.dumps(dicts, indent=2, ensure_ascii=False)
            ext = "json"
        else:
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=list(EXPORT_COLUMNS))
            w.writeheader()
            for i, p in enumerate(profiles, start=1):
                if (get_job(job_id) or {}).get("cancel_requested"):
                    _update_job(job_id, state="cancelled",
                                finished_at=datetime.datetime.now().isoformat(timespec="seconds"))
                    return
                d = _export_dict(p)
                w.writerow({c: (";".join(d[c]) if isinstance(d[c], list) else d[c])
                            for c in EXPORT_COLUMNS})
                _update_job(job_id, done=i)
            content = buf.getvalue()
            ext = "csv"
        os.makedirs(_exports_dir(), exist_ok=True)
        fname = f"{job_id}.{ext}"
        fpath = os.path.join(_exports_dir(), fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        _update_job(job_id, state="done", done=len(profiles),
                    result={"filename": fname, "bytes": len(content.encode("utf-8"))},
                    finished_at=datetime.datetime.now().isoformat(timespec="seconds"))
    except Exception as e:
        _update_job(job_id, state="error", failed=[{"error": str(e)}],
                    finished_at=datetime.datetime.now().isoformat(timespec="seconds"))


def start_export_job(ids=None, fmt="csv", group=None):
    """Mulai ekspor asinkron. Return job; hasil diunduh via job.result."""
    if fmt not in ("csv", "json"):
        raise ValueError("format harus csv atau json")
    profiles = pm.list_profiles()
    if ids:
        want = set(ids)
        profiles = [p for p in profiles if p["id"] in want]
    if group:
        profiles = [p for p in profiles if p.get("group") == group]
    job = _new_job("export", len(profiles), meta={"format": fmt})
    t = threading.Thread(target=_run_export_job,
                         args=(job["job_id"], ids, fmt, group), daemon=True)
    t.start()
    return job


def export_result_path(job_id):
    """Path file hasil ekspor job (atau None bila belum selesai / tak ada)."""
    job = get_job(job_id)
    if not job or job.get("kind") != "export" or job.get("state") != "done":
        return None
    fname = (job.get("result") or {}).get("filename")
    if not fname or "/" in fname or ".." in fname:
        return None
    fpath = os.path.join(_exports_dir(), fname)
    return fpath if os.path.isfile(fpath) else None
