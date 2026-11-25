#!/usr/bin/env python3
"""
Backup / restore profil + cache (F3-3 cache, F3-5 export/restore).

Cache di sini = folder data browser di browser_profiles/<pid>/ (Cache,
Code Cache, GPUCache, dll). Profil yang sedang JALAN tidak boleh
dibersihkan cache-nya (Chromium memegang file itu — hapus diam-diam bisa
korup sesi); clear_cache menolak bila browser hidup.

F3-3: cache_size + clear_cache (dipakai Local API v1 user/delete-cache
dan v2 browser-profile/delete-cache).
F3-5: export_profile / restore_profile / list_backups (menyusul).
"""
import os
import shutil

CACHE_DIRS = (
    "Cache", "Code Cache", "GPUCache", "Service Worker",
    "ShaderCache", "DawnCache", "GraphiteDawnCache",
    "Media Cache", "Network Persistent State",
)
CACHE_FILES = ("Network Persistent State", "Cookies-journal")


def _profiles_root():
    """Root browser_profiles — dibaca dinamis dari launcher supaya test
    bisa mengarahkan ke tmp (monkeypatch launcher.BROWSER_PROFILES_DIR)."""
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    launcher_dir = os.path.join(repo, "launcher")
    if launcher_dir not in sys.path:
        sys.path.insert(0, launcher_dir)
    import launcher as _l
    return _l.BROWSER_PROFILES_DIR


def profile_dir(pid, root=None):
    return os.path.join(root or _profiles_root(), pid)


def cache_size(pid, root=None):
    """Ukuran cache profil (byte) + rincian per folder. Profil tanpa
    folder cache -> 0. Tidak menyentuh browser yang jalan."""
    base = profile_dir(pid, root)
    total = 0
    detail = {}
    if not os.path.isdir(base):
        return {"profile_id": pid, "bytes": 0, "human": "0 B", "dirs": {}}
    for name in CACHE_DIRS:
        p = os.path.join(base, name)
        if os.path.isdir(p):
            s = 0
            for dp, _dns, fns in os.walk(p):
                for fn in fns:
                    try:
                        s += os.path.getsize(os.path.join(dp, fn))
                    except OSError:
                        pass
            detail[name] = s
            total += s
    for name in CACHE_FILES:
        p = os.path.join(base, name)
        if os.path.isfile(p):
            try:
                s = os.path.getsize(p)
            except OSError:
                s = 0
            detail[name] = s
            total += s
    return {"profile_id": pid, "bytes": total,
            "human": _human(total), "dirs": detail}


def _human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def is_running(pid):
    """True bila browser profil ini sedang jalan (registry hidup)."""
    try:
        import sys
        here = os.path.dirname(os.path.abspath(__file__))
        repo = os.path.dirname(here)
        launcher_dir = os.path.join(repo, "launcher")
        if launcher_dir not in sys.path:
            sys.path.insert(0, launcher_dir)
        import launcher as _l
        return pid in _l.list_running()
    except Exception:
        return False


def clear_cache(pid, root=None):
    """Hapus folder/file cache profil. Return {"cleared_bytes", "removed"}.

    Raise RuntimeError bila browser sedang jalan (jangan korup sesi hidup).
    Profil tanpa folder cache -> 0 byte, sukses."""
    if is_running(pid):
        raise RuntimeError(f"profil {pid} sedang jalan — stop dulu sebelum "
                           "hapus cache")
    base = profile_dir(pid, root)
    before = cache_size(pid, root=root)
    removed = []
    if os.path.isdir(base):
        for name in CACHE_DIRS:
            p = os.path.join(base, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
                removed.append(name)
        for name in CACHE_FILES:
            p = os.path.join(base, name)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                    removed.append(name)
                except OSError:
                    pass
    return {"profile_id": pid, "cleared_bytes": before["bytes"],
            "cleared_human": before["human"], "removed": removed}


# ── F3-5: export / restore ────────────────────────────────────────────────
import datetime
import json as _json
import zipfile

# File data browser yang ikut di-backup (selain cache).
BROWSER_DATA_FILES = (
    "identity.json", "fingerprint_inject.js", "profile_cookies.json",
    "cookie_inject_report.json", "injector_daemon.log",
)
# Jangan pernah ikut: lock launch + file sesi (milik proses yang jalan).
EXCLUDE_FILES = {".launch.lock"}


def _backups_root():
    """Folder backups — dibaca dinamis supaya test bisa mengarahkan."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    return os.path.join(repo, "backups")


def _get_profile(pid):
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import profiles as pm
    return pm.get_profile(pid)


def export_profile(pid, include_cache=True, dest_dir=None, root=None):
    """Ekspor profil lengkap ke ZIP. Return info backup.

    Isi ZIP: manifest.json, profile.json (profil utuh — termasuk identity
    beku + cookies), browser_data/<file data browser>, cache/<folder cache>
    bila include_cache DAN profil mengizinkan (cache_backup=True).
    Profil yang sedang jalan BOLEH di-backup (snapshot best-effort —
    dicatat di manifest); file lock tidak ikut.
    Raise ValueError bila profil tidak ada."""
    profile = _get_profile(pid)
    if not profile:
        raise ValueError(f"profil {pid} tidak ditemukan")
    want_cache = bool(include_cache) and bool(profile.get("cache_backup", True))
    base = profile_dir(pid, root)
    backups = dest_dir or _backups_root()
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_name = "".join(c if (c.isalnum() or c in "-_") else "_"
                        for c in (profile.get("name") or pid))[:40]
    fname = f"{safe_name}-{pid}-{stamp}.zip"
    fpath = os.path.join(backups, fname)
    # Dua ekspor dalam detik yang sama -> nama sama; tambah sufiks -2, -3
    # supaya ekspor kedua tidak menimpa yang pertama.
    n = 2
    while os.path.exists(fpath):
        fname = f"{safe_name}-{pid}-{stamp}-{n}.zip"
        fpath = os.path.join(backups, fname)
        n += 1
    cache_bytes = cache_size(pid, root=root)["bytes"] if want_cache else 0
    manifest = {"format": "stealthxgm-backup", "version": 1,
                "profile_id": pid, "profile_name": profile.get("name"),
                "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "include_cache": want_cache, "cache_bytes": cache_bytes,
                "running_at_export": is_running(pid)}
    with zipfile.ZipFile(fpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", _json.dumps(manifest, indent=1))
        z.writestr("profile.json", _json.dumps(profile, indent=1, default=str))
        if os.path.isdir(base):
            for name in BROWSER_DATA_FILES:
                p = os.path.join(base, name)
                if os.path.isfile(p) and name not in EXCLUDE_FILES:
                    z.write(p, f"browser_data/{name}")
            if want_cache:
                for d in CACHE_DIRS:
                    p = os.path.join(base, d)
                    if os.path.isdir(p):
                        for dp, _dns, fns in os.walk(p):
                            for fn in fns:
                                fp = os.path.join(dp, fn)
                                arc = os.path.join(
                                    "cache", d,
                                    os.path.relpath(fp, p))
                                z.write(fp, arc)
    return {"file": fname, "path": fpath,
            "bytes": os.path.getsize(fpath),
            "human": _human(os.path.getsize(fpath)),
            "profile_id": pid, "profile_name": profile.get("name"),
            "include_cache": want_cache, "cache_bytes": cache_bytes,
            "exported_at": manifest["exported_at"]}


def _read_manifest(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        try:
            raw = z.read("manifest.json")
        except KeyError:
            raise ValueError("ZIP bukan backup StealthXGM (tanpa manifest.json)")
        man = _json.loads(raw.decode("utf-8"))
        if man.get("format") != "stealthxgm-backup":
            raise ValueError("manifest bukan format stealthxgm-backup")
        return man, z.namelist()


def list_backups(dest_dir=None):
    """Daftar backup (baca manifest tiap ZIP — tanpa extract)."""
    backups = dest_dir or _backups_root()
    out = []
    if not os.path.isdir(backups):
        return out
    for fname in sorted(os.listdir(backups)):
        if not fname.endswith(".zip"):
            continue
        fpath = os.path.join(backups, fname)
        try:
            man, _names = _read_manifest(fpath)
        except Exception:
            out.append({"file": fname, "bytes": os.path.getsize(fpath),
                        "valid": False, "error": "manifest rusak / bukan backup"})
            continue
        out.append({"file": fname, "bytes": os.path.getsize(fpath),
                    "human": _human(os.path.getsize(fpath)), "valid": True,
                    "profile_id": man.get("profile_id"),
                    "profile_name": man.get("profile_name"),
                    "exported_at": man.get("exported_at"),
                    "include_cache": man.get("include_cache"),
                    "cache_bytes": man.get("cache_bytes", 0)})
    return out


def delete_backup(fname, dest_dir=None):
    """Hapus file backup. Return True. Raise bila tidak ada / nama jahat."""
    if not fname or "/" in fname or "\\" in fname or ".." in fname:
        raise ValueError("nama file backup tidak valid")
    backups = dest_dir or _backups_root()
    fpath = os.path.join(backups, fname)
    if not os.path.isfile(fpath):
        raise ValueError(f"backup {fname} tidak ditemukan")
    os.remove(fpath)
    return True


def restore_profile(zip_path, new_name=None, root=None):
    """Restore backup jadi profil BARU (id baru). Return profil baru.

    Identity beku + cookies + data browser ikut dipulihkan apa adanya
    (itu gunanya backup: perangkat yang sama). Nama default = nama asli +
    " (restore)". Raise ValueError bila ZIP bukan backup / profil rusak."""
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import profiles as pm
    if not os.path.isfile(zip_path):
        raise ValueError(f"file backup tidak ditemukan: {zip_path}")
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise ValueError("file bukan ZIP / backup rusak")
    with zf as z:
        try:
            man = _json.loads(z.read("manifest.json").decode("utf-8"))
            data = _json.loads(z.read("profile.json").decode("utf-8"))
        except KeyError as e:
            raise ValueError(f"backup rusak (hilang {e})")
        if man.get("format") != "stealthxgm-backup":
            raise ValueError("bukan backup StealthXGM")
        if not isinstance(data, dict) or not data.get("name"):
            raise ValueError("profile.json di backup rusak")
        names = z.namelist()
        new_profile = pm.create_profile({
            "name": new_name or (data.get("name") + " (restore)"),
            "group": data.get("group", "default"),
            "notes": data.get("notes", ""),
            "fingerprint": data.get("fingerprint") or {},
            "proxy": data.get("proxy") or {},
            "warp_fallback": data.get("warp_fallback", True),
            "kernel": data.get("kernel", "system"),
            "cache_backup": data.get("cache_backup", True),
            "tags": data.get("tags") or [],
        })
        # create_profile tidak menerima cookies -> pulihkan terpisah.
        new_profile = pm.update_profile(
            new_profile["id"], {"cookies": data.get("cookies") or []})
        # Data browser (identity.json, cookies daemon, cache) -> folder
        # profil baru. File lock tidak pernah ikut (tidak ada di ZIP).
        base = profile_dir(new_profile["id"], root)
        os.makedirs(base, exist_ok=True)
        restored = []
        for name in names:
            if name.startswith("browser_data/"):
                target = os.path.join(base, os.path.basename(name))
                with open(target, "wb") as f:
                    f.write(z.read(name))
                restored.append(os.path.basename(name))
            elif name.startswith("cache/"):
                rel = name[len("cache/"):]
                target = os.path.join(base, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as f:
                    f.write(z.read(name))
                restored.append("cache/" + rel)
        return {"profile": new_profile, "restored_files": restored,
                "from_backup": man.get("profile_name"),
                "exported_at": man.get("exported_at")}
