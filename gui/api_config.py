"""Local API settings + process manager for StealthXGM.

Settings (stored in data/api_config.json, chmod 600):
  enabled: bool — start API alongside GUI (default True)
  port: int — Local REST API port (default 50325, AdsPower-compatible)
  api_key: str — auth key for the Local API. P-04 (2026-11-07): default ON —
    if no key is configured, one is auto-generated at first API start
    (ensure_api_key) and saved here. Empty = auth OFF only until the next
    start, which regenerates a key. The key is passed to the API process
    via environment (STEALTHXGM_API_KEY), NEVER via argv (ps-visible).

The API itself runs as a separate process (gui/local_api.py) so the GUI
can start/stop it at runtime. PID is tracked in data/api_server.pid.
"""
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.request
from functools import wraps

import json_store

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CONFIG_FILE = os.path.join(DATA_DIR, "api_config.json")
PID_FILE = os.path.join(DATA_DIR, "api_server.pid")
LOCAL_API = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_api.py")

DEFAULT_PORT = 50325
MIN_PORT, MAX_PORT = 1024, 65535


def _locked(fn):
    """P-07: mutasi config di bawah lock eksklusif file (baca-ubah-tulis
    atomik antar-proses/thread). Nested call aman (reentrant)."""
    @wraps(fn)
    def wrapper(*a, **k):
        with json_store.locked(CONFIG_FILE):
            return fn(*a, **k)
    return wrapper


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _default():
    return {"enabled": True, "port": DEFAULT_PORT, "api_key": "",
            "updated_at": _now_iso()}


def _load():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        # P-07: seed default di bawah lock + cek ulang (dua proses yang
        # sama-sama first-run tidak boleh saling menimpa).
        with json_store.locked(CONFIG_FILE):
            if not os.path.exists(CONFIG_FILE):
                cfg = _default()
                _save(cfg)
                return cfg
    # P-11: config rusak -> karantina (jangan reset diam-diam — API key
    # lama tersimpan di file .corrupt-* dan bisa dipulihkan manual),
    # lalu kembali ke default.
    cfg, quarantined = json_store.load_json_safe(CONFIG_FILE, None)
    if quarantined:
        print(f"[api_config] WARNING: {CONFIG_FILE} corrupt, "
              f"dikarantina ke {quarantined}")
    if cfg is None:
        # P-07: reset ke default di bawah lock (baca ulang dulu — proses
        # lain mungkin sudah memperbaiki file di antara).
        with json_store.locked(CONFIG_FILE):
            cfg2, _ = json_store.load_json_safe(CONFIG_FILE, None)
            if cfg2 is None:
                cfg = _default()
                _save(cfg)
                return cfg
            cfg = cfg2
    # fill missing keys defensively
    d = _default()
    for k in d:
        if k not in cfg:
            cfg[k] = d[k]
    return cfg


def _save(cfg):
    # P-11: backup bergilir (.bak) sebelum menimpa, tulis atomik, chmod 600.
    json_store.save_json_atomic(CONFIG_FILE, cfg, chmod=0o600)
    return cfg


def get_config():
    cfg = _load()
    return {k: v for k, v in cfg.items() if k != "updated_at"}


@_locked
def save_config(data):
    cfg = _load()
    if "enabled" in data:
        cfg["enabled"] = bool(data["enabled"])
    if "port" in data:
        try:
            port = int(data["port"])
        except (TypeError, ValueError):
            raise ValueError("port harus angka")
        if not (MIN_PORT <= port <= MAX_PORT):
            raise ValueError(f"port harus {MIN_PORT}-{MAX_PORT}")
        cfg["port"] = port
    if "api_key" in data:
        key = str(data["api_key"] or "")
        if len(key) > 128:
            raise ValueError("api_key terlalu panjang")
        cfg["api_key"] = key
    cfg["updated_at"] = _now_iso()
    return _save(cfg)


@_locked
def generate_key():
    """Generate a new random API key and save it."""
    key = secrets.token_urlsafe(24)
    cfg = _load()
    cfg["api_key"] = key
    cfg["updated_at"] = _now_iso()
    _save(cfg)
    return key


def ensure_api_key():
    """P-04: API key default ON. Return the configured key, generating +
    persisting one first if none is set (first-run). The key lives in
    api_config.json (chmod 600) and is shown once by POST
    /api/settings/api/key; automation reads it from that file."""
    cfg = _load()
    if cfg.get("api_key"):
        return cfg["api_key"]
    return generate_key()


# ── Process management ──

def _read_pid():
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _probe(port, timeout=2):
    """True if the Local API answers /api/v1/status."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/status")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def api_is_running(port=None):
    port = port or _load()["port"]
    pid = _read_pid()
    return bool(pid and _pid_alive(pid) and _probe(port))


def api_status():
    cfg = _load()
    pid = _read_pid()
    alive = bool(pid and _pid_alive(pid))
    return {
        "enabled": cfg["enabled"],
        "port": cfg["port"],
        "api_key_set": bool(cfg["api_key"]),
        "running": alive and _probe(cfg["port"]),
        "pid": pid if alive else None,
    }


def start_api():
    """Start local_api.py as a background process. Returns status dict.

    P-04: ensures an API key exists (default ON) and passes it via the
    process ENVIRONMENT (STEALTHXGM_API_KEY), never via argv — argv is
    world-readable via ps / /proc/<pid>/cmdline."""
    cfg = _load()
    port = cfg["port"]
    if api_is_running(port):
        return {"ok": True, "already": True, **api_status()}
    key = ensure_api_key()
    cmd = [sys.executable, LOCAL_API, "--port", str(port)]
    env = dict(os.environ)
    env["STEALTHXGM_API_KEY"] = key
    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, env=env)
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))
    try:
        os.chmod(PID_FILE, 0o600)
    except OSError:
        pass
    # wait up to ~5s for the port to answer
    for _ in range(25):
        if _probe(port):
            break
        time.sleep(0.2)
    st = api_status()
    return {"ok": st["running"], "already": False, **st}


def stop_api():
    """Stop the Local API process. Returns status dict."""
    pid = _read_pid()
    if pid and _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                if not _pid_alive(pid):
                    break
                time.sleep(0.1)
            if _pid_alive(pid):
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        os.remove(PID_FILE)
    except OSError:
        pass
    st = api_status()
    return {"ok": not st["running"], **st}
