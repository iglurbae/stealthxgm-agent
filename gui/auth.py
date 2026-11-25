#!/usr/bin/env python3
"""
Login GUI — operator tunggal (F3-8, follow-up P-04).

Desain (diputuskan di fase ini, dicatat jujur):
- SATU password operator (bukan multi-user — Gil satu-satunya operator).
  Manajemen user tidak dibangun; bila nanti multi-user, modul ini yang
  diganti.
- Penyimpanan: gui/data/auth.json (chmod 600), PBKDF2-HMAC-SHA256
  600.000 iterasi + salt acak 16 byte. TIDAK PERNAH plaintext.
- Sesi: token acak (secrets.token_urlsafe), yang disimpan hanya SHA256
  token di gui/data/gui_sessions.json (chmod 600). Berlaku 12 jam,
  diperpanjang tiap request aktif (maks 24 jam sejak login).
- Penegakan OPT-IN: bila belum ada password (is_setup() False), GUI
  berperilaku seperti dulu (terbuka) — supaya CLI + test lama tidak
  pecah. Begitu password diset, SEMUA /api/* (kecuali /api/auth/*)
  butuh sesi, dan GET / mengarah ke /login bila belum login.
  Bind non-localhost TANPA password = DITOLAK saat start (P-04d).
- Brute-force: 5 gagal per IP -> kunci 15 menit (429). Hitungan di
  memori proses (restart GUI mereset — diterima, dicatat).
- Semua tulis file lewat json_store.atomic_update (pola P-07).
"""
import hashlib
import hmac
import os
import secrets
import time

import json_store

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
AUTH_FILE = os.path.join(DATA_DIR, "auth.json")
SESSIONS_FILE = os.path.join(DATA_DIR, "gui_sessions.json")

MIN_PASSWORD_LEN = 8
PBKDF2_ITERATIONS = 600_000
SESSION_TTL = 12 * 3600        # 12 jam
SESSION_MAX_AGE = 24 * 3600    # maks 24 jam sejak login
SESSION_EXTEND_THRESHOLD = 2 * 3600  # perpanjang bila sisa < 2 jam
MAX_FAILED = 5
LOCKOUT_SECONDS = 15 * 60

_FAILED = {}  # ip -> {"count": int, "until": epoch}


def _now():
    return time.time()


def _read_json(path):
    """Baca JSON aman (load_json_safe return (data, quarantined))."""
    data, _q = json_store.load_json_safe(path, {})
    return data if isinstance(data, dict) else {}


def _hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                             PBKDF2_ITERATIONS)
    return {"algo": "pbkdf2-sha256", "iterations": PBKDF2_ITERATIONS,
            "salt": salt.hex(), "hash": dk.hex()}


def _verify_hash(password, stored):
    try:
        salt = bytes.fromhex(stored["salt"])
        want = bytes.fromhex(stored["hash"])
        got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                  int(stored.get("iterations", PBKDF2_ITERATIONS)))
        return hmac.compare_digest(got, want)
    except Exception:
        return False


def is_setup():
    """True bila password operator sudah diset."""
    return bool(_read_json(AUTH_FILE).get("password"))


def setup_password(password):
    """Set password pertama. Hanya bila belum ada. Return True.
    Raise ValueError bila sudah diset / password terlalu pendek."""
    if not password or len(password) < MIN_PASSWORD_LEN:
        raise ValueError(
            f"password minimal {MIN_PASSWORD_LEN} karakter")
    if is_setup():
        raise ValueError("password sudah diset — pakai ganti password")
    def _mut(db):
        if db.get("password"):
            raise ValueError("password sudah diset — pakai ganti password")
        db["password"] = _hash_password(password)
        return True
    return json_store.atomic_update(AUTH_FILE, {}, _mut, chmod=0o600)


def change_password(old, new):
    """Ganti password (butuh password lama). Return True.
    Raise ValueError bila belum diset / lama salah / baru pendek."""
    if not is_setup():
        raise ValueError("password belum diset")
    if not new or len(new) < MIN_PASSWORD_LEN:
        raise ValueError(
            f"password baru minimal {MIN_PASSWORD_LEN} karakter")
    auth = _read_json(AUTH_FILE)
    if not _verify_hash(old, auth.get("password") or {}):
        raise ValueError("password lama salah")
    def _mut(db):
        db["password"] = _hash_password(new)
        return True
    json_store.atomic_update(AUTH_FILE, {}, _mut, chmod=0o600)
    # Ganti password = semua sesi lama hangus (token dicuri ikut mati).
    _clear_sessions()
    return True


def verify_password(password):
    """Cek password tanpa efek samping (rate-limit dicek pemanggil)."""
    auth = _read_json(AUTH_FILE)
    stored = auth.get("password")
    if not stored:
        return False
    return _verify_hash(password or "", stored)


# ── Rate limit login ─────────────────────────────────────────────────────
def is_locked_out(ip):
    rec = _FAILED.get(ip or "")
    if not rec:
        return False
    if rec["count"] < MAX_FAILED:
        return False
    # Pernah mencapai batas: kunci sampai `until`; sesudah itu hapus
    # catatan (bukan sebelum — until==0 berarti belum pernah terkunci).
    if _now() < rec["until"]:
        return True
    _FAILED.pop(ip or "", None)
    return False


def record_failed(ip):
    ip = ip or ""
    rec = _FAILED.get(ip, {"count": 0, "until": 0})
    rec["count"] += 1
    if rec["count"] >= MAX_FAILED:
        rec["until"] = _now() + LOCKOUT_SECONDS
    _FAILED[ip] = rec
    return rec


def reset_failures(ip):
    _FAILED.pop(ip or "", None)


# ── Sesi ─────────────────────────────────────────────────────────────────
def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(ip=None):
    """Buat sesi baru. Return token (hanya sekali terlihat — simpan di
    cookie httponly / header klien)."""
    token = secrets.token_urlsafe(32)
    now = _now()
    entry = {"created_at": now, "expires_at": now + SESSION_TTL,
             "last_seen": now, "ip": ip or ""}
    def _mut(db):
        db[_token_hash(token)] = entry
        return True
    json_store.atomic_update(SESSIONS_FILE, {}, _mut, chmod=0o600)
    return token


def validate_token(token):
    """True bila token ada + belum kedaluwarsa. Perpanjang (sliding)
    bila sisa < 2 jam, maks 24 jam sejak login. Sesi basi dibersihkan
    oportunistik saat validasi."""
    if not token:
        return False
    th = _token_hash(token)
    sessions = _read_json(SESSIONS_FILE)
    entry = sessions.get(th)
    now = _now()
    if not entry:
        return False
    if now > entry.get("expires_at", 0):
        _drop_session(th)
        return False
    if now > entry.get("created_at", 0) + SESSION_MAX_AGE:
        _drop_session(th)
        return False
    # Sliding: perpanjang bila sisa < 2 jam.
    if entry["expires_at"] - now < SESSION_EXTEND_THRESHOLD:
        new_exp = min(now + SESSION_TTL,
                      entry.get("created_at", now) + SESSION_MAX_AGE)
        def _mut(db):
            if th in db:
                db[th]["expires_at"] = new_exp
                db[th]["last_seen"] = now
            return True
        json_store.atomic_update(SESSIONS_FILE, {}, _mut, chmod=0o600)
    else:
        def _mut2(db):
            if th in db:
                db[th]["last_seen"] = now
            return True
        json_store.atomic_update(SESSIONS_FILE, {}, _mut2, chmod=0o600)
    return True


def _drop_session(token_hash):
    def _mut(db):
        db.pop(token_hash, None)
        return True
    json_store.atomic_update(SESSIONS_FILE, {}, _mut, chmod=0o600)


def destroy_session(token):
    """Logout: hapus sesi. Return True bila ada yang dihapus."""
    if not token:
        return False
    th = _token_hash(token)
    if th not in _read_json(SESSIONS_FILE):
        return False
    _drop_session(th)
    return True


def _clear_sessions():
    def _mut(db):
        db.clear()
        return True
    json_store.atomic_update(SESSIONS_FILE, {}, _mut, chmod=0o600)


def active_sessions():
    """Jumlah sesi aktif (tidak basi). Dipakai status/debug."""
    now = _now()
    sessions = _read_json(SESSIONS_FILE)
    return sum(1 for e in sessions.values()
               if now <= e.get("expires_at", 0)
               and now <= e.get("created_at", 0) + SESSION_MAX_AGE)


def check_bind_allowed(host):
    """P-04d: bind non-localhost hanya bila password sudah diset.
    Return (boleh: bool, alasan: str)."""
    if host in ("127.0.0.1", "localhost", "::1"):
        return True, ""
    if is_setup():
        return True, ""
    return False, (f"bind {host} ditolak: GUI tanpa password login "
                   "tidak boleh terekspos ke jaringan — set password dulu "
                   "(POST /api/auth/setup) atau bind 127.0.0.1")
