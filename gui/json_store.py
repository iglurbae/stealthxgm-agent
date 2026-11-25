"""JSON store helpers — atomic save + corrupt-file quarantine (P-11, 2026-11-07).

Satu kali tulis terpotong (mati listrik, disk penuh, crash saat save) tidak
boleh lagi menghapus semua profil / pool / API key tanpa jejak:
- load_json_safe(): JSON rusak -> file dipindah ke <path>.corrupt-<timestamp>
  (karantina, TIDAK pernah dihapus), lalu kembalikan default.
- save_json_atomic(): sebelum menimpa, salin file lama ke <path>.bak
  (backup bergilir versi terakhir yang bagus).

Dipakai: profiles.py, proxy_pools.py, api_config.py, extension_manager.py.
"""
import contextlib
import fcntl
import json
import os
import shutil
import tempfile
import threading
import time


class StoreLockTimeout(TimeoutError):
    """Tidak bisa memperoleh lock eksklusif dalam `timeout` detik —
    kemungkinan ada proses/thread lain yang menahan lock terlalu lama
    (atau deadlock antar-proses). Pemanggil TIDAK boleh retry buta."""


# ── P-07: file locking (fcntl.flock) ─────────────────────────────────────
# Masalah: semua JSON store memakai pola baca-ubah-tulis (tmp + os.replace)
# tanpa lock. Flask dev server melayani request di thread berbeda, dan GUI +
# Local API adalah dua proses berbeda yang menulis file yang sama — dua
# create/update bersamaan bisa saling menimpa (lost update diam-diam).
#
# Desain lock:
# - Satu file lock per store: <path>.lock (dibuat saat perlu, TIDAK PERNAH
#   dihapus — menghapus file lock saat proses lain memegang lock pada inode
#   yang sudah ter-unlink akan merusak mutual exclusion).
# - Antar-proses: fcntl.flock LOCK_EX (blocking dengan timeout).
# - Antar-thread dalam satu proses: threading.RLock per path — tanpa ini,
#   dua thread dalam satu proses yang sama-sama flock akan saling blokir.
# - Reentrant: nested locked() di thread yang sama (mis. batch_delete ->
#   delete_profile) dihitung dengan refcount, bukan flock ulang — flock
#   kedua pada fd berbeda di proses yang sama akan DEADLOCK di Linux.
_lock_state = {}        # abspath -> [fd, refcount]
_lock_state_guard = threading.Lock()
_lock_rlocks = {}       # abspath -> threading.RLock


def _rlock_for(abspath):
    with _lock_state_guard:
        return _lock_rlocks.setdefault(abspath, threading.RLock())


@contextlib.contextmanager
def locked(path, timeout=10.0):
    """Lock eksklusif antar-proses + antar-thread untuk satu file store.

    Pakai ini untuk membungkus seluruh urutan baca-ubah-tulis (load ->
    mutasi -> save). Read-only (list/get) TIDAK perlu lock: save memakai
    os.replace sehingga pembaca selalu melihat versi lengkap lama atau
    baru, tidak pernah setengah tulis.

    Timeout default 10 detik — operasi store normal selesai dalam
    milidetik; timeout berarti ada yang menahan lock terlalu lama.
    """
    ap = os.path.abspath(path)
    rlock = _rlock_for(ap)
    if not rlock.acquire(timeout=timeout):
        raise StoreLockTimeout(
            f"timeout mengunci {path} ({timeout}s) — thread lain menahan lock")
    nested = False
    fd = None
    try:
        with _lock_state_guard:
            st = _lock_state.get(ap)
            if st is not None:
                st[1] += 1
                nested = True
        if not nested:
            d = os.path.dirname(ap)
            if d:
                os.makedirs(d, exist_ok=True)
            fd = os.open(ap + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
            deadline = time.monotonic() + timeout
            try:
                while True:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise StoreLockTimeout(
                                f"timeout mengunci {path} ({timeout}s) — "
                                "proses lain menahan lock")
                        time.sleep(0.05)
            except BaseException:
                os.close(fd)
                fd = None
                raise
            with _lock_state_guard:
                _lock_state[ap] = [fd, 1]
        yield
    finally:
        if nested:
            with _lock_state_guard:
                st = _lock_state.get(ap)
                if st is not None:
                    st[1] -= 1
        elif fd is not None:
            with _lock_state_guard:
                _lock_state.pop(ap, None)
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass
        rlock.release()


def atomic_update(path, default, mutate, chmod=None):
    """Load (karantina bila corrupt) -> mutate(data) -> save atomik,
    semuanya di bawah lock eksklusif. mutate(data) -> result (boleh None).
    Bila mutate raise, TIDAK ada save. Return result mutate.

    Ini primitif yang benar untuk read-modify-write: load dan save harus
    dalam satu lock yang sama, kalau tidak dua penulis bersamaan tetap
    bisa lost-update (keduanya load versi lama, yang terakhir save menang).
    """
    with locked(path):
        data, _quarantined = load_json_safe(path, default)
        result = mutate(data)
        save_json_atomic(path, data, chmod=chmod)
        return result


def _quarantine(path):
    """Pindahkan file rusak ke <path>.corrupt-<timestamp>. Return path baru
    atau None bila pemindahan gagal."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = f"{path}.corrupt-{ts}"
    try:
        os.replace(path, dest)
        return dest
    except OSError:
        return None


def load_json_safe(path, default):
    """Baca JSON. Return (data, quarantined_path_atau_None).

    File tidak ada -> (default, None) tanpa membuat file.
    JSON rusak / isi bukan dict -> karantina + (default, quarantined_path).
    OSError saat baca -> (default, None): file TIDAK disentuh (bisa jadi
    cuma masalah izin sementara), jangan dikarantina buta.
    """
    if not os.path.exists(path):
        return default, None
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return default, _quarantine(path)
    except OSError:
        return default, None
    if not isinstance(data, dict):
        return default, _quarantine(path)
    return data, None


def save_json_atomic(path, data, chmod=None):
    """Tulis JSON atomik (tmp + os.replace). Sebelum menimpa, salin file
    lama ke <path>.bak — TAPI hanya bila file lama masih JSON valid, supaya
    .bak selalu berisi versi terakhir yang BAGUS (bukan bytes corrupt).
    chmod (mis. 0o600) diterapkan ke file tmp bila ada."""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    if os.path.exists(path):
        try:
            with open(path) as _f:
                json.load(_f)  # validasi: hanya backup bila JSON valid
            shutil.copy2(path, path + ".bak")
        except (OSError, ValueError):
            pass
    # P-07: tmp UNIK per pemanggilan (mkstemp), bukan <path>.tmp yang
    # tetap — dua save bersamaan ke file yang sama sebelumnya memakai
    # nama tmp yang sama, sehingga os.replace satu proses bisa
    # menghilangkan tmp proses lain (FileNotFoundError) dan isi file
    # saling menimpa. Dengan lock, tabrakan ini seharusnya tidak
    # terjadi; tmp unik menghilangkan kelas bugnya sekalian.
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=d or ".")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        if chmod is not None:
            try:
                os.chmod(tmp, chmod)
            except OSError:
                pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def list_quarantined(data_dir):
    """Daftar file *.corrupt-* di data_dir (untuk peringatan GUI)."""
    import glob
    return sorted(
        os.path.basename(p)
        for p in glob.glob(os.path.join(data_dir, "*.corrupt-*"))
    )
