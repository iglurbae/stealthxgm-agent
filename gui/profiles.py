"""Profile manager — JSON storage for browser profiles.

Each profile:
  id: unique string (uuid4 hex[:12])
  name: display name
  group: group/tag for organization
  notes: free text
  fingerprint: {features: {flag: bool}, timezone, locale, platform, mobile: bool}
  proxy: {type: http/socks5/none, host, port, user, pass, sticky: bool}
  warp_fallback: bool — if primary proxy unreachable at launch, auto-fallback to WARP
  cookies: list (import/export)
  created_at, updated_at: ISO timestamps
  deleted: bool — True = soft-deleted (in trash bin)
  deleted_at: ISO timestamp when moved to trash (None if active)
  status: idle | running
"""
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from functools import wraps

import json_store

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")
GROUPS_FILE = os.path.join(DATA_DIR, "groups.json")

MAX_TAGS_PER_PROFILE = 20
MAX_TAG_LENGTH = 50


def _locked(fn):
    """P-07: jalankan mutasi store di bawah lock eksklusif file
    (baca-ubah-tulis atomik antar-proses/thread — GUI + Local API adalah
    dua proses berbeda yang menulis profiles.json yang sama).
    Nested call (batch_* -> single) aman: lock reentrant per thread."""
    @wraps(fn)
    def wrapper(*a, **k):
        with json_store.locked(PROFILES_FILE):
            return fn(*a, **k)
    return wrapper

# All 29 feature flags from our fingerprint engine
FEATURE_FLAGS = [
    # Navigator / identity
    ("fp_tostring_trap", "toString Trap", "navigator"),
    ("fp_useragent", "User-Agent Spoof", "navigator"),
    ("fp_webdriver_remove", "WebDriver Remove", "navigator"),
    ("fp_platform", "Platform Spoof", "navigator"),
    ("fp_chrome_runtime", "Chrome Runtime", "navigator"),
    ("fp_languages", "Languages", "navigator"),
    ("fp_storage", "Storage Spoof", "navigator"),
    ("fp_battery", "Battery API", "navigator"),
    ("fp_enumerate_devices", "Media Devices", "navigator"),
    ("fp_client_hints", "Client Hints", "navigator"),
    ("fp_plugins", "Plugins", "navigator"),
    ("fp_voices", "Speech Voices", "navigator"),
    ("fp_perf_memory", "Performance Memory", "navigator"),
    ("fp_datetostring", "Date toString", "navigator"),
    # Hardware / screen
    ("fp_cpu_cores", "CPU Cores", "hardware"),
    ("fp_gpu_vendor", "GPU Vendor", "hardware"),
    # Canvas / Audio / WebGL
    ("fp_canvas_todataurl", "Canvas toDataURL", "canvas_audio"),
    ("fp_canvas_getimagedata", "Canvas getImageData", "canvas_audio"),
    ("fp_webgl_extensions", "WebGL Extensions", "canvas_audio"),
    ("fp_webgl_shader", "WebGL Shader", "canvas_audio"),
    ("fp_webgpu", "WebGPU", "canvas_audio"),
    ("fp_audio_buffer", "Audio Buffer", "canvas_audio"),
    ("fp_audio_samplerate", "Audio SampleRate", "canvas_audio"),
    # Network
    ("fp_network_info", "Network Info", "network"),
    ("fp_geolocation", "Geolocation", "network"),
    # Behavioral
    ("fp_fonts", "Fonts", "behavioral"),
    ("fp_timezone_offset", "Timezone Offset", "behavioral"),
    # Extra (our additions)
    ("fp_webrtc_block", "WebRTC Block", "extra"),
    ("fp_iframe_patch", "iframe Patch", "extra"),
]

# Group flags by category for UI
FLAG_CATEGORIES = {}
for fid, label, cat in FEATURE_FLAGS:
    FLAG_CATEGORIES.setdefault(cat, []).append({"id": fid, "label": label})

ALL_FLAGS_DEFAULT_ON = {fid for fid, _, _ in FEATURE_FLAGS}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(PROFILES_FILE):
        return {}
    # P-11: JSON rusak -> karantina (jangan reset diam-diam).
    data, quarantined = json_store.load_json_safe(PROFILES_FILE, {})
    if quarantined:
        print(f"[profiles] WARNING: {PROFILES_FILE} corrupt, "
              f"dikarantina ke {quarantined}")
    if not isinstance(data, dict):
        return {}
    # Migrate: old profiles without trash fields get defaults (no crash)
    changed = False
    for p in data.values():
        if not isinstance(p, dict):
            continue
        if "deleted" not in p:
            p["deleted"] = False
            changed = True
        if "deleted_at" not in p:
            p["deleted_at"] = None
            changed = True
        if "tags" not in p:  # F3-3: profil lama belum punya tags
            p["tags"] = []
            changed = True
    if changed:
        # P-07: simpan migrasi di bawah lock DENGAN baca ulang — save
        # tanpa lock di sini bisa menimpa perubahan penulis lain yang
        # masuk di antara _load dan _save (lost update). Reentrant, jadi
        # aman dipanggil dari fungsi mutasi yang sudah memegang lock.
        with json_store.locked(PROFILES_FILE):
            fresh, _ = json_store.load_json_safe(PROFILES_FILE, {})
            for p in fresh.values():
                if not isinstance(p, dict):
                    continue
                if "deleted" not in p:
                    p["deleted"] = False
                if "deleted_at" not in p:
                    p["deleted_at"] = None
                if "tags" not in p:
                    p["tags"] = []
            json_store.save_json_atomic(PROFILES_FILE, fresh)
            data = fresh
    return data


def _save(profiles):
    # P-11: backup bergilir (.bak) sebelum menimpa, tulis atomik.
    json_store.save_json_atomic(PROFILES_FILE, profiles)


def default_profile(name="New Profile"):
    return {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "group": "default",
        "notes": "",
        "fingerprint": {
            "features": {fid: True for fid in ALL_FLAGS_DEFAULT_ON},
            "timezone": "Asia/Jakarta",
            "locale": None,  # auto from timezone
            "platform": "windows",  # windows | macos | linux | android | ios
            "mobile": False,
        },
        "proxy": {
            "type": "sticky",  # sticky | http | socks5 | warp | none
            "host": "",
            "port": "",
            "user": "",
            "pass": "",
        },
        "warp_fallback": True,    # auto-fallback to WARP if primary proxy is down
        "kernel": "system",       # F3-4: id kernel (registry) atau "system"
        "cache_backup": True,     # F3-5: saklar backup cache (ala AdsPower)
        "cookies": [],
        "tags": [],               # F3-3: tag bebas (filter di list + API v2)
        "deleted": False,        # trash bin: True = soft-deleted (in trash)
        "deleted_at": None,      # ISO timestamp when moved to trash
        "created_at": _now(),
        "updated_at": _now(),
        "status": "idle",
    }


def normalize_tags(tags):
    """F3-3: normalisasi daftar tag — list[str], strip, buang kosong,
    dedupe (jaga urutan), maks 20 tag @ 50 karakter. Raise ValueError bila
    bukan list / ada tag bukan string."""
    if tags is None:
        return []
    if not isinstance(tags, (list, tuple)):
        raise ValueError("tags harus list string")
    out = []
    for t in tags:
        if not isinstance(t, str):
            raise ValueError(f"tag harus string, dapat {type(t).__name__}")
        t = t.strip()
        if not t:
            continue
        if len(t) > MAX_TAG_LENGTH:
            raise ValueError(f"tag '{t[:20]}...' terlalu panjang "
                             f"(maks {MAX_TAG_LENGTH} karakter)")
        if t not in out:
            out.append(t)
    if len(out) > MAX_TAGS_PER_PROFILE:
        raise ValueError(f"maks {MAX_TAGS_PER_PROFILE} tag per profil")
    return out


def list_profiles(search=None, group=None, include_deleted=False, tags=None):
    profiles = _load()
    result = list(profiles.values())
    if not include_deleted:
        result = [p for p in result if not p.get("deleted")]
    if search:
        s = search.lower()
        result = [p for p in result if s in p["name"].lower() or s in p.get("notes", "").lower()]
    if group:
        result = [p for p in result if p.get("group") == group]
    if tags:
        # F3-3: filter tag = OR (profil cocok bila punya SALAH SATU tag).
        want = set(tags)
        result = [p for p in result if want & set(p.get("tags") or [])]
    result.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
    return result


def list_trash():
    """All soft-deleted profiles, newest-deleted first."""
    profiles = _load()
    result = [p for p in profiles.values() if p.get("deleted")]
    result.sort(key=lambda p: p.get("deleted_at", ""), reverse=True)
    return result


def get_profile(pid):
    return _load().get(pid)


@_locked
def create_profile(data):
    profiles = _load()
    p = default_profile(data.get("name", "New Profile"))
    # Merge user overrides
    for key in ("group", "notes", "kernel"):
        if key in data:
            p[key] = data[key]
    if "cache_backup" in data:
        p["cache_backup"] = bool(data["cache_backup"])
    if "fingerprint" in data:
        p["fingerprint"].update(data["fingerprint"])
    if "proxy" in data:
        p["proxy"].update(data["proxy"])
    if "warp_fallback" in data:
        p["warp_fallback"] = bool(data["warp_fallback"])
    if "tags" in data:
        p["tags"] = normalize_tags(data["tags"])
    profiles[p["id"]] = p
    _save(profiles)
    return p


@_locked
def update_profile(pid, data):
    profiles = _load()
    p = profiles.get(pid)
    if not p:
        return None
    for key in ("name", "group", "notes", "warp_fallback", "status", "kernel",
                "cache_backup"):
        if key in data:
            p[key] = data[key]
    if "tags" in data:
        p["tags"] = normalize_tags(data["tags"])
    if "fingerprint" in data:
        fp = p["fingerprint"]
        for fk, fv in data["fingerprint"].items():
            if fk == "features" and isinstance(fv, dict):
                fp["features"].update(fv)
            else:
                fp[fk] = fv
    if "proxy" in data:
        p["proxy"].update(data["proxy"])
    if "cookies" in data:
        p["cookies"] = data["cookies"]
    p["updated_at"] = _now()
    profiles[pid] = p
    _save(profiles)
    return p


@_locked
def delete_profile(pid):
    """Soft delete: move to trash (NOT permanent). Use permanent_delete() to wipe."""
    profiles = _load()
    p = profiles.get(pid)
    if not p or p.get("deleted"):
        return False
    p["deleted"] = True
    p["deleted_at"] = _now()
    p["updated_at"] = _now()
    profiles[pid] = p
    _save(profiles)
    return True


@_locked
def restore_profile(pid):
    """Restore a trashed profile back to the active list."""
    profiles = _load()
    p = profiles.get(pid)
    if not p or not p.get("deleted"):
        return None
    p["deleted"] = False
    p["deleted_at"] = None
    p["updated_at"] = _now()
    profiles[pid] = p
    _save(profiles)
    return p


def _remove_browser_data(pid):
    """Remove on-disk Chromium profile dir for permanent deletes."""
    import shutil
    data_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "browser_profiles", pid)
    try:
        if os.path.isdir(data_dir):
            shutil.rmtree(data_dir)
            return True
    except OSError:
        pass
    return False


@_locked
def permanent_delete(pid):
    """Hard delete: remove profile + its browser data dir. Cannot be undone."""
    profiles = _load()
    if pid not in profiles:
        return False
    del profiles[pid]
    _save(profiles)
    _remove_browser_data(pid)
    return True


@_locked
def empty_trash():
    """Permanently delete everything in the trash. Returns count."""
    profiles = _load()
    trashed = [pid for pid, p in profiles.items() if p.get("deleted")]
    for pid in trashed:
        del profiles[pid]
        _remove_browser_data(pid)
    _save(profiles)
    return len(trashed)


@_locked
def auto_cleanup_trash(days=30):
    """Permanently delete trash items older than `days`. Returns count."""
    profiles = _load()
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=days)).isoformat()
    old = [pid for pid, p in profiles.items()
           if p.get("deleted") and (p.get("deleted_at") or "") < cutoff]
    for pid in old:
        del profiles[pid]
        _remove_browser_data(pid)
    _save(profiles)
    return len(old)


def batch_delete(pids):
    """Soft-delete multiple profiles -> trash. Returns {trashed: [...], failed: [...]}."""
    trashed, failed = [], []
    for pid in pids or []:
        if delete_profile(pid):
            trashed.append(pid)
        else:
            failed.append(pid)
    return {"trashed": trashed, "failed": failed}


def batch_move_group(pids, group):
    """Move multiple profiles to a group. Trashed profiles are skipped.
    Returns {moved: [...], failed: [...]}."""
    moved, failed = [], []
    for pid in pids or []:
        cur = get_profile(pid)
        if not cur or cur.get("deleted"):
            failed.append(pid)
            continue
        if update_profile(pid, {"group": group}):
            moved.append(pid)
        else:
            failed.append(pid)
    return {"moved": moved, "failed": failed}


def batch_assign_pool(pids, pool_id):
    """Assign a proxy pool to multiple profiles. pool_id may be '' to clear.
    Trashed profiles are skipped."""
    moved, failed = [], []
    proxy = {"pool_id": pool_id or None, "type": "sticky",
             "host": "", "port": "", "user": "", "pass": ""}
    for pid in pids or []:
        cur = get_profile(pid)
        if not cur or cur.get("deleted"):
            failed.append(pid)
            continue
        if update_profile(pid, {"proxy": proxy}):
            moved.append(pid)
        else:
            failed.append(pid)
    return {"assigned": moved, "failed": failed}


@_locked
def duplicate_profile(pid):
    """Duplicate a profile as a DIFFERENT identity (P-01 fix).

    The copy keeps settings (features, timezone, locale, platform, proxy,
    group) but MUST NOT share the source's fingerprint identity or session
    cookies — otherwise two "different accounts" look like one device and
    share one login session. Identity is regenerated with the same OS /
    timezone / locale; if regeneration fails, the stored identity is
    dropped so launch generates a fresh consistent one. Cookies are
    always cleared."""
    profiles = _load()
    src = profiles.get(pid)
    if not src or src.get("deleted"):
        return None
    import copy
    p = copy.deepcopy(src)
    p["id"] = uuid.uuid4().hex[:12]
    p["name"] = src["name"] + " (copy)"
    p["status"] = "idle"
    p["deleted"] = False
    p["deleted_at"] = None
    p["created_at"] = _now()
    p["updated_at"] = _now()
    # P-01: never copy identity or cookies — regenerate / clear.
    p["cookies"] = []
    fp = p.get("fingerprint") or {}
    if fp.get("identity") is not None:
        try:
            from fingerprint_gen import generate_random, to_jsonable
            ident = generate_random(
                fp.get("platform", "windows"),
                timezone=fp.get("timezone") or "Asia/Jakarta",
                locale=fp.get("locale"),
            )
            fp["identity"] = to_jsonable(ident)
        except Exception:
            # Regeneration failed: drop stored identity, launch will
            # generate a fresh consistent one. Never keep the old one.
            fp.pop("identity", None)
    profiles[p["id"]] = p
    _save(profiles)
    return p


def list_groups():
    profiles = _load()
    groups = {}
    for p in profiles.values():
        if p.get("deleted"):
            continue
        g = p.get("group", "default")
        groups[g] = groups.get(g, 0) + 1
    # F3-3: gabung grup kosong yang tercatat di registry (dibuat via
    # group/create tapi belum dipakai profil mana pun).
    for name in _load_groups():
        groups.setdefault(name, 0)
    return [{"name": k, "count": v} for k, v in sorted(groups.items())]


# ── F3-3: registry grup + tag ─────────────────────────────────────────────
def _load_groups():
    """{name: {created_at}} — grup kosong yang sengaja dibuat. Grup yang
    dipakai profil muncul di list_groups walau tidak ada di registry."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(GROUPS_FILE):
        return {}
    data, quarantined = json_store.load_json_safe(GROUPS_FILE, {})
    if quarantined:
        print(f"[profiles] WARNING: {GROUPS_FILE} corrupt, "
              f"dikarantina ke {quarantined}")
    return data if isinstance(data, dict) else {}


def _save_groups(groups):
    json_store.save_json_atomic(GROUPS_FILE, groups)


def _valid_group_name(name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("nama grup wajib string tidak kosong")
    name = name.strip()
    if len(name) > 100:
        raise ValueError("nama grup terlalu panjang (maks 100 karakter)")
    if "/" in name or "\\" in name:
        raise ValueError("nama grup tidak boleh mengandung / atau \\")
    return name


@_locked
def create_group(name):
    """Buat grup kosong (tercatat di registry). Grup juga terbentuk otomatis
    saat profil memakai nama grup baru — fungsi ini untuk grup yang sengaja
    disiapkan dulu. Return {"name", "count"}."""
    name = _valid_group_name(name)
    groups = _load_groups()
    if name not in groups:
        groups[name] = {"created_at": _now()}
        _save_groups(groups)
    count = sum(1 for p in _load().values()
                if not p.get("deleted") and p.get("group") == name)
    return {"name": name, "count": count}


@_locked
def rename_group(old, new):
    """Ganti nama grup di registry + semua profil yang memakainya.
    Return {"renamed": n_profil} atau None bila grup lama tidak ada."""
    new = _valid_group_name(new)
    old = _valid_group_name(old)
    profiles = _load()
    groups = _load_groups()
    exists = old in groups or any(not p.get("deleted") and p.get("group") == old
                                  for p in profiles.values())
    if not exists:
        return None
    if old == new:
        return {"renamed": 0}
    n = 0
    for p in profiles.values():
        if p.get("group") == old:
            p["group"] = new
            p["updated_at"] = _now()
            n += 1
    if n:
        _save(profiles)
    if old in groups:
        groups[new] = groups.pop(old)
        _save_groups(groups)
    return {"renamed": n}


@_locked
def delete_group(name):
    """Hapus grup: profil di dalamnya dipindah ke 'default', registry
    dibersihkan. Return {"moved": n} atau None bila grup tidak ada."""
    name = _valid_group_name(name)
    if name == "default":
        raise ValueError("grup 'default' tidak bisa dihapus")
    profiles = _load()
    groups = _load_groups()
    exists = name in groups or any(not p.get("deleted") and p.get("group") == name
                                   for p in profiles.values())
    if not exists:
        return None
    n = 0
    for p in profiles.values():
        if p.get("group") == name:
            p["group"] = "default"
            p["updated_at"] = _now()
            n += 1
    if n:
        _save(profiles)
    if name in groups:
        groups.pop(name)
        _save_groups(groups)
    return {"moved": n}


def list_tags():
    """Semua tag yang dipakai + jumlah profil per tag (tanpa profil trash)."""
    counts = {}
    for p in _load().values():
        if p.get("deleted"):
            continue
        for t in p.get("tags") or []:
            counts[t] = counts.get(t, 0) + 1
    return [{"name": k, "count": v} for k, v in sorted(counts.items())]


@_locked
def rename_tag(old, new):
    """Ganti nama tag di semua profil. Return {"renamed": n_profil}."""
    new = (new or "").strip()
    if not new:
        raise ValueError("nama tag baru wajib diisi")
    if len(new) > MAX_TAG_LENGTH:
        raise ValueError(f"tag terlalu panjang (maks {MAX_TAG_LENGTH})")
    profiles = _load()
    n = 0
    for p in profiles.values():
        tags = p.get("tags") or []
        if old in tags:
            p["tags"] = [new if t == old else t for t in tags]
            # dedupe bila new sudah ada di profil yang sama
            seen, dedup = set(), []
            for t in p["tags"]:
                if t not in seen:
                    seen.add(t)
                    dedup.append(t)
            p["tags"] = dedup
            p["updated_at"] = _now()
            n += 1
    if n:
        _save(profiles)
    return {"renamed": n}


@_locked
def delete_tag(name):
    """Hapus tag dari semua profil. Return {"removed_from": n_profil}."""
    profiles = _load()
    n = 0
    for p in profiles.values():
        tags = p.get("tags") or []
        if name in tags:
            p["tags"] = [t for t in tags if t != name]
            p["updated_at"] = _now()
            n += 1
    if n:
        _save(profiles)
    return {"removed_from": n}


@_locked
def set_profile_tags(pid, tags):
    """Timpa tag satu profil. Return profil atau None bila tidak ada."""
    tags = normalize_tags(tags)
    profiles = _load()
    p = profiles.get(pid)
    if not p:
        return None
    p["tags"] = tags
    p["updated_at"] = _now()
    profiles[pid] = p
    _save(profiles)
    return p
