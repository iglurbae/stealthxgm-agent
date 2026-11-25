"""Proxy Pool manager — JSON storage for proxy pools.

Each pool:
  id: unique string (uuid4 hex[:12])
  name: display name
  type: http | socks5 | sticky | warp | none
  host: proxy host (empty for sticky/warp/none)
  port: proxy port
  user: proxy username (optional)
  pass: proxy password (optional)
  country: country label (optional, e.g. ID, SG, US)
  active: bool — pool enabled
  is_default: bool — default pool for new profiles
  last_check: {status, ip, country, latency_ms, checked_at} or None
  created_at, updated_at: ISO timestamps

Notes:
- type=sticky means the DataImpulse proxy-bot at 127.0.0.1:18080
- type=warp means Cloudflare WARP at socks5://127.0.0.1:40000
- type=none means direct connection (no proxy)
- Passwords are stored in the JSON file (local only, chmod 600 recommended).
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone
from functools import wraps

import json_store

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
POOLS_FILE = os.path.join(DATA_DIR, "proxy_pools.json")

POOL_TYPES = ["http", "socks5", "sticky", "warp", "none"]


def _locked(fn):
    """P-07: mutasi pool di bawah lock eksklusif file (baca-ubah-tulis
    atomik antar-proses/thread). Nested call aman (reentrant)."""
    @wraps(fn)
    def wrapper(*a, **k):
        with json_store.locked(POOLS_FILE):
            return fn(*a, **k)
    return wrapper


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(POOLS_FILE):
        # P-07: seed default di bawah lock + cek ulang (dua proses yang
        # sama-sama first-run tidak boleh saling menimpa seed).
        with json_store.locked(POOLS_FILE):
            if not os.path.exists(POOLS_FILE):
                pools = _seed_defaults()
                _save(pools)
                return pools
    # P-11: JSON rusak / bukan dict -> karantina (jangan reset diam-diam),
    # lalu seed ulang default. Pool custom yang lama tersimpan di file
    # .corrupt-* dan bisa dipulihkan manual.
    data, quarantined = json_store.load_json_safe(POOLS_FILE, None)
    if quarantined:
        print(f"[proxy_pools] WARNING: {POOLS_FILE} corrupt, "
              f"dikarantina ke {quarantined}")
    if data is None:
        pools = _seed_defaults()
        _save(pools)
        return pools
    # Defensive: drop any non-dict entries (should never happen, but cheap)
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def _save(pools):
    # P-11: backup bergilir (.bak) sebelum menimpa, tulis atomik, chmod 600.
    json_store.save_json_atomic(POOLS_FILE, pools, chmod=0o600)


def _seed_defaults():
    """Built-in pools: DataImpulse proxy-bot, WARP, Direct. Marked system=True."""
    now = _now()
    pools = {}
    for p in (
        {
            "name": "DataImpulse (proxy-bot)",
            "type": "sticky",
            "host": "127.0.0.1",
            "port": "18080",
            "country": "auto",
            "notes": "Residential pool via local proxy-bot. Built-in.",
            "is_default": True,
            "system": True,
        },
        {
            "name": "Cloudflare WARP",
            "type": "warp",
            "host": "127.0.0.1",
            "port": "40000",
            "country": "auto",
            "notes": "Free fallback when proxy-bot is down. Built-in.",
            "is_default": False,
            "system": True,
        },
        {
            "name": "Direct (no proxy)",
            "type": "none",
            "host": "",
            "port": "",
            "country": "-",
            "notes": "Direct connection, no proxy. Built-in.",
            "is_default": False,
            "system": True,
        },
    ):
        pid = uuid.uuid4().hex[:12]
        pools[pid] = {
            "id": pid,
            "name": p["name"],
            "type": p["type"],
            "host": p.get("host", ""),
            "port": p.get("port", ""),
            "user": "",
            "pass": "",
            "country": p.get("country", ""),
            "notes": p.get("notes", ""),
            "active": True,
            "is_default": p.get("is_default", False),
            "system": p.get("system", False),
            "last_check": None,
            "created_at": now,
            "updated_at": now,
        }
    return pools


def list_pools(active_only=False):
    pools = _load()
    result = list(pools.values())
    if active_only:
        result = [p for p in result if p.get("active")]
    result.sort(key=lambda p: (not p.get("is_default", False), p.get("name", "")))
    return result


def get_pool(pid):
    return _load().get(pid)


def get_default_pool():
    for p in _load().values():
        if p.get("is_default") and p.get("active"):
            return p
    # fall back to first active pool
    active = list_pools(active_only=True)
    return active[0] if active else None


@_locked
def create_pool(data):
    pools = _load()
    ptype = (data.get("type") or "http").lower()
    if ptype not in POOL_TYPES:
        raise ValueError(f"invalid type: {ptype} (must be one of {POOL_TYPES})")
    pid = uuid.uuid4().hex[:12]
    p = {
        "id": pid,
        "name": data.get("name", "New Pool"),
        "type": ptype,
        "host": data.get("host", ""),
        "port": str(data.get("port", "")),
        "user": data.get("user", ""),
        "pass": data.get("pass", ""),
        "country": data.get("country", ""),
        "notes": data.get("notes", ""),
        "active": bool(data.get("active", True)),
        "is_default": bool(data.get("is_default", False)),
        "system": False,
        "last_check": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    if p["is_default"]:
        for q in pools.values():
            q["is_default"] = False
    pools[pid] = p
    _save(pools)
    return p


@_locked
def update_pool(pid, data):
    pools = _load()
    p = pools.get(pid)
    if not p:
        return None
    for key in ("name", "host", "user", "pass", "country", "notes", "active"):
        if key in data:
            p[key] = data[key] if key != "port" else str(data[key])
    if "port" in data:
        p["port"] = str(data["port"])
    if "type" in data:
        ptype = data["type"].lower()
        if ptype not in POOL_TYPES:
            raise ValueError(f"invalid type: {ptype}")
        p["type"] = ptype
    if "is_default" in data:
        if data["is_default"]:
            for q in pools.values():
                q["is_default"] = False
        p["is_default"] = bool(data["is_default"])
    p["updated_at"] = _now()
    pools[pid] = p
    _save(pools)
    return p


@_locked
def delete_pool(pid):
    pools = _load()
    p = pools.get(pid)
    if not p:
        return False
    if p.get("system"):
        raise ValueError("cannot delete built-in pool (disable it instead)")
    was_default = p.get("is_default")
    del pools[pid]
    if was_default:
        # promote first remaining active pool
        for q in pools.values():
            if q.get("active"):
                q["is_default"] = True
                break
    _save(pools)
    return True


@_locked
def record_check(pid, result):
    """Store a test result on the pool. result: {status, ip, country, latency_ms}."""
    pools = _load()
    p = pools.get(pid)
    if not p:
        return None
    p["last_check"] = {**result, "checked_at": _now()}
    p["updated_at"] = _now()
    pools[pid] = p
    _save(pools)
    return p


def pool_proxy_auth(pool):
    """Kredensial proxy pool, bila ada. Return (user, pass) atau None.

    P-09: kredensial TIDAK PERNAH masuk ke URL --proxy-server (Chromium
    modern mengabaikannya + password terlihat di /proc/cmdline). Kredensial
    hanya dipakai oleh extension auth (launcher) dan oleh requests
    in-process (test_pool)."""
    user = (pool.get("user") or "").strip()
    pw = pool.get("pass") or ""
    if user:
        return (user, pw)
    return None


def pool_to_proxy_server(pool):
    """Convert a pool dict to a Chromium --proxy-server value + note.

    Returns (proxy_server, note). proxy_server is None for direct.

    P-09: URL yang dikembalikan TIDAK PERNAH mengandung kredensial —
    Chromium mengabaikan user:pass di --proxy-server dan menampilkannya
    di argv (ps aux). Kredensial diambil terpisah via pool_proxy_auth().
    """
    ptype = (pool.get("type") or "none").lower()
    if ptype == "sticky":
        return "http://127.0.0.1:18080", "pool %s: sticky -> 127.0.0.1:18080" % pool.get("name")
    if ptype == "warp":
        return "socks5://127.0.0.1:40000", "pool %s: warp -> 127.0.0.1:40000" % pool.get("name")
    if ptype == "none":
        return None, "pool %s: direct" % pool.get("name")
    host, port = pool.get("host", ""), pool.get("port", "")
    if not host or not port:
        return None, "pool %s: %s configured but host/port empty -> no proxy" % (pool.get("name"), ptype)
    scheme = "socks5" if ptype == "socks5" else "http"
    has_auth = pool_proxy_auth(pool) is not None
    note = "pool %s: %s %s:%s%s" % (pool.get("name"), ptype, host, port,
                                   " (auth)" if has_auth else "")
    return f"{scheme}://{host}:{port}", note


def _requests_proxies(pool):
    """Proxy dict untuk requests (test_pool) — di sini kredensial BOLEH
    ada di URL karena hanya dipakai in-process, tidak pernah masuk argv."""
    proxy_server, _note = pool_to_proxy_server(pool)
    if proxy_server is None:
        return None
    auth = pool_proxy_auth(pool)
    if auth:
        from urllib.parse import quote, urlparse
        u = urlparse(proxy_server)
        proxy_server = (
            f"{u.scheme}://{quote(auth[0], safe='')}:{quote(auth[1], safe='')}"
            f"@{u.hostname}:{u.port}")
    return {"http": proxy_server, "https": proxy_server}


def test_pool(pid, timeout=15):
    """Test a pool: request ip-api through it. Returns dict, also records it."""
    import requests
    pool = get_pool(pid)
    if not pool:
        return {"status": "error", "error": "pool not found"}
    proxies = _requests_proxies(pool)
    started = time.time()
    try:
        if proxies is None:
            r = requests.get("http://ip-api.com/json/?fields=status,country,countryCode,query",
                             timeout=timeout)
        else:
            r = requests.get("http://ip-api.com/json/?fields=status,country,countryCode,query",
                             proxies=proxies, timeout=timeout)
        latency = int((time.time() - started) * 1000)
        data = r.json()
        if data.get("status") == "success":
            result = {
                "status": "online",
                "ip": data.get("query", ""),
                "country": f"{data.get('country','')} ({data.get('countryCode','')})",
                "latency_ms": latency,
            }
        else:
            result = {"status": "error", "error": "ip-api returned fail", "latency_ms": latency}
    except Exception as e:
        result = {"status": "offline", "error": str(e)[:120],
                  "latency_ms": int((time.time() - started) * 1000)}
    record_check(pid, result)
    return result
