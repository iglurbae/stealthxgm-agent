#!/usr/bin/env python3
"""
Kernel manager (F3-4) — unduh/ganti versi Chromium per profil.

AdsPower punya dual-engine (SunBrowser/Chromium + FlowerBrowser/Firefox)
dan kernel yang bisa diunduh/diganti per profil (bukti REA:
`/api/v2/browser-profile/kernels`, `download-kernel`,
`/api/getUpdateBrowser`). StealthXGM sebelumnya terkunci ke Chromium
sistem (find_chrome).

Sumber unduhan: Chrome for Testing (CfT) — endpoint resmi Google:
  known-good-versions-with-downloads.json (daftar versi + URL unduh)
  storage.googleapis.com/chrome-for-testing-public/<ver>/linux64/
  chrome-linux64.zip (binary "chrome" lengkap, bukan headless-shell).
Tidak ada tool/service berbayar; unduhan langsung dari Google.

Slot Firefox: registry + resolve + launch mendukung engine firefox
(binary didaftarkan manual). Unduh OTOMATIS Firefox BELUM didukung
(tidak ada endpoint CfT sepadan yang di-wire) — daftar binary Firefox
yang sudah terpasang via register_kernel(engine="firefox").

Registry: gui/data/kernels.json {"default": id|None, "kernels": {...}}.
Binary unduhan: <repo>/kernels/<version>/chrome-linux64/chrome.
Job unduh: gui/data/kernel_downloads.json (dibagi GUI + Local API —
dua proses — via lock P-07; progress ditulis max 1x/detik).

Profil memilih kernel lewat field "kernel" (id registry atau "system").
Launcher: resolve_kernel_chrome(profile) -> path binary, fallback ke
find_chrome() bila kosong/tidak dikenal.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_GUI_DIR = os.path.join(_REPO, "gui")
if _GUI_DIR not in sys.path:
    sys.path.insert(0, _GUI_DIR)

import json_store  # noqa: E402

CFT_VERSIONS_URL = ("https://googlechromelabs.github.io/chrome-for-testing/"
                    "known-good-versions-with-downloads.json")
KERNELS_DIR = os.path.join(_REPO, "kernels")
REGISTRY_FILE = os.path.join(_GUI_DIR, "data", "kernels.json")
DOWNLOADS_FILE = os.path.join(_GUI_DIR, "data", "kernel_downloads.json")

CHROME_PLATFORMS = ("linux64",)
FIREFOX_DOWNLOAD_NOTE = ("unduh otomatis Firefox belum didukung — "
                         "daftarkan binary Firefox yang sudah terpasang "
                         "via register_kernel(engine='firefox')")


def _load_registry():
    data, _q = json_store.load_json_safe(
        REGISTRY_FILE, {"default": None, "kernels": {}})
    if not isinstance(data, dict):
        return {"default": None, "kernels": {}}
    data.setdefault("default", None)
    data.setdefault("kernels", {})
    if not isinstance(data["kernels"], dict):
        data["kernels"] = {}
    return data


def _save_registry(reg):
    json_store.save_json_atomic(REGISTRY_FILE, reg, chmod=0o600)


def _slug_version(version):
    return "".join(c if (c.isalnum() or c in ".-") else "_" for c in version)


def detect_version(binary_path):
    """Versi binary dari `<path> --version`. Return "156.0.8078.4" atau
    None. Dipakai untuk Chromium DAN Firefox (keduanya mencetak versi
    dalam bentuk x.y.z)."""
    import re
    try:
        out = subprocess.run([binary_path, "--version"], capture_output=True,
                             text=True, timeout=15).stdout or ""
    except Exception:
        return None
    # "156.0.8078.4" (Chromium) maupun "140.0" (Firefox) — 2-4 komponen.
    m = re.search(r"(\d+(?:\.\d+){1,3})", out)
    if not m:
        return None
    return m.group(1)


def list_kernels():
    """Daftar kernel terdaftar (tanpa 'system' — itu ditambah pemanggil)."""
    reg = _load_registry()
    out = []
    for kid, e in reg["kernels"].items():
        d = dict(e)
        d["is_default"] = (reg.get("default") == kid)
        out.append(d)
    out.sort(key=lambda e: e.get("version", ""), reverse=True)
    return out


def get_kernel(kid):
    if not kid or kid == "system":
        return None
    return _load_registry()["kernels"].get(kid)


def get_default_kernel():
    reg = _load_registry()
    kid = reg.get("default")
    if kid:
        return reg["kernels"].get(kid)
    return None


def register_kernel(path, name=None, engine="chromium"):
    """Daftarkan binary browser yang sudah ada di disk. Return entry.
    Raise ValueError bila path tidak ada / bukan executable / versi tak
    terdeteksi. engine: "chromium" | "firefox"."""
    engine = (engine or "chromium").lower()
    if engine not in ("chromium", "firefox"):
        raise ValueError("engine harus 'chromium' atau 'firefox'")
    if not path or not os.path.isfile(path):
        raise ValueError(f"binary tidak ditemukan: {path}")
    if not os.access(path, os.X_OK):
        raise ValueError(f"binary tidak executable: {path}")
    version = detect_version(path)
    if not version:
        raise ValueError(f"versi tidak terdeteksi dari {path} --version")
    kid = f"{engine}-{_slug_version(version)}"
    entry = {"id": kid, "name": name or f"{engine} {version}",
             "version": version, "engine": engine, "path": path,
             "source": "manual",
             "installed_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    reg = _load_registry()
    reg["kernels"][kid] = entry
    _save_registry(reg)
    return entry


def set_default_kernel(kid):
    """Jadikan kernel default untuk profil tanpa pilihan kernel.
    kid "system"/None = kembali ke Chromium sistem. Return entry/None."""
    reg = _load_registry()
    if kid in (None, "system"):
        reg["default"] = None
        _save_registry(reg)
        return None
    if kid not in reg["kernels"]:
        raise ValueError(f"kernel {kid} tidak dikenal")
    reg["default"] = kid
    _save_registry(reg)
    return reg["kernels"][kid]


def remove_kernel(kid):
    """Hapus kernel dari registry + hapus foldernya bila di KERNELS_DIR.
    Tolak bila kernel adalah default. Return True."""
    reg = _load_registry()
    if kid not in reg["kernels"]:
        raise ValueError(f"kernel {kid} tidak dikenal")
    if reg.get("default") == kid:
        raise ValueError(f"kernel {kid} adalah default — ganti default dulu")
    entry = reg["kernels"].pop(kid)
    _save_registry(reg)
    path = entry.get("path", "")
    # Hanya hapus folder bila binary ada di dalam KERNELS_DIR (unduhan
    # kami); binary manual di luar sana jangan disentuh.
    if path.startswith(os.path.realpath(KERNELS_DIR) + os.sep):
        top = path
        while os.path.dirname(top) != os.path.realpath(KERNELS_DIR) \
                and os.path.dirname(top) != top:
            top = os.path.dirname(top)
        # top = kernels/<version> (satu level di bawah KERNELS_DIR)
        parent = os.path.dirname(os.path.realpath(path))
        if os.path.basename(parent).startswith("chrome-"):
            top = os.path.dirname(parent)
        elif parent != os.path.realpath(KERNELS_DIR):
            top = parent
        shutil.rmtree(top, ignore_errors=True)
    return True


def resolve_kernel_chrome(profile):
    """Path binary untuk profil: kernel pilihan profil > kernel default >
    None (pemanggil fallback ke find_chrome). Return path atau None."""
    if not isinstance(profile, dict):
        return None
    kid = profile.get("kernel")
    if kid and kid != "system":
        entry = get_kernel(kid)
        if entry and os.path.isfile(entry["path"]):
            return entry["path"]
    default = get_default_kernel()
    if default and os.path.isfile(default["path"]):
        return default["path"]
    return None


# ── Unduhan Chrome for Testing ────────────────────────────────────────────
def fetch_known_good_versions(url=None):
    """Ambil daftar versi CfT. Return list[{version, downloads}].
    Raise ValueError bila gagal / format tak dikenal."""
    target = url or CFT_VERSIONS_URL
    req = urllib.request.Request(target, headers={
        "User-Agent": "StealthXGM-kernel-manager"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise ValueError(f"gagal ambil daftar versi CfT: {e}")
    versions = data.get("versions")
    if not isinstance(versions, list) or not versions:
        raise ValueError("daftar versi CfT kosong / format tak dikenal")
    return versions


def find_download_url(versions, version=None, platform="linux64"):
    """Cari URL unduh chrome untuk versi. version None = terbaru.
    Bila versi persis tidak ada, pakai versi terbaru dengan major yang
    sama. Return (version_ditemukan, url). Raise ValueError bila tidak ada."""
    if version:
        for v in versions:
            if v.get("version") == version:
                url = _chrome_url(v, platform)
                if url:
                    return version, url
        major = version.split(".")[0]
        for v in versions:
            if v.get("version", "").split(".")[0] == major:
                url = _chrome_url(v, platform)
                if url:
                    return v["version"], url
        raise ValueError(f"versi {version} tidak ada di CfT "
                         f"(dan tidak ada major {major})")
    for v in reversed(versions):
        url = _chrome_url(v, platform)
        if url:
            return v["version"], url
    raise ValueError("tidak ada versi CfT dengan unduhan chrome linux64")


def _chrome_url(version_entry, platform):
    dls = (version_entry.get("downloads") or {}).get("chrome") or []
    for d in dls:
        if d.get("platform") == platform:
            return d.get("url")
    return None


def _download_file(url, dest, progress_cb=None, timeout=600):
    """Unduh file (chunked). progress_cb(downloaded, total). Return byte."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "StealthXGM-kernel-manager"})
    total = 0
    with urllib.request.urlopen(req, timeout=timeout) as r:
        total = int(r.headers.get("Content-Length") or 0)
        downloaded = 0
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb:
                    progress_cb(downloaded, total)
    return downloaded


def _find_chrome_in(extracted_dir):
    """Binary chrome hasil extract zip CfT: chrome-linux64/chrome."""
    for cand in (os.path.join(extracted_dir, "chrome-linux64", "chrome"),
                 os.path.join(extracted_dir, "chrome-linux", "chrome"),
                 os.path.join(extracted_dir, "chrome")):
        if os.path.isfile(cand):
            return cand
    return None


# Binary yang harus executable di dalam chrome-linux64/ hasil extract CfT.
# ZIP CfT tidak menyimpan bit exec, jadi tanpa chmod eksplisit Chrome gagal
# launch (FATAL posix_spawn .../chrome_crashpad_handler: Permission
# denied). Selain nama yang dikenal, file tanpa ekstensi juga di-chmod —
# itu calon helper binary di rilis CfT mendatang.
_KERNEL_EXECUTABLES = ("chrome", "chrome_crashpad_handler", "chrome_sandbox")


def _chmod_kernel_binaries(chrome_dir):
    """Jadikan executable binary + helper kernel di chrome_dir."""
    try:
        names = os.listdir(chrome_dir)
    except OSError:
        return
    for name in names:
        path = os.path.join(chrome_dir, name)
        if not os.path.isfile(path):
            continue
        if name in _KERNEL_EXECUTABLES or "." not in name:
            try:
                os.chmod(path, 0o755)
            except OSError:
                pass


def download_kernel(version=None, platform="linux64", versions_url=None,
                    download_url=None, progress_cb=None, timeout=600):
    """Unduh + pasang kernel Chromium dari CfT. Return entry registry.

    version None = terbaru. download_url (untuk test) mengalahkan pencarian
    versi — versi tetap dicatat dari argumen / hasil deteksi binary.
    Raise ValueError bila versi tak ada / unduh gagal / zip rusak."""
    if download_url is None:
        versions = fetch_known_good_versions(versions_url)
        version, download_url = find_download_url(versions, version, platform)
    os.makedirs(KERNELS_DIR, exist_ok=True)
    # Temp di KERNELS_DIR (bukan /tmp): /tmp VM ini tmpfs 512 MB, sementara
    # ZIP CfT ~130 MB + hasil extract ~400 MB tidak muat di sana.
    tmpdir = tempfile.mkdtemp(prefix="kernel_dl_", dir=KERNELS_DIR)
    try:
        zip_path = os.path.join(tmpdir, "chrome.zip")
        _download_file(download_url, zip_path, progress_cb, timeout)
        try:
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(tmpdir)
        except zipfile.BadZipFile:
            raise ValueError("file unduhan bukan ZIP valid")
        binary = _find_chrome_in(tmpdir)
        if not binary:
            raise ValueError("ZIP tidak berisi binary chrome "
                             "(chrome-linux64/chrome tidak ditemukan)")
        _chmod_kernel_binaries(os.path.dirname(binary))
        detected = detect_version(binary)
        if not detected:
            raise ValueError("versi binary hasil unduh tidak terdeteksi")
        version = version or detected
        dest_dir = os.path.join(KERNELS_DIR, _slug_version(version))
        if os.path.isdir(dest_dir):
            shutil.rmtree(dest_dir)
        shutil.move(tmpdir, dest_dir)
        tmpdir = None  # sudah dipindah — jangan dihapus di finally
        final_binary = _find_chrome_in(dest_dir)
        _chmod_kernel_binaries(os.path.dirname(final_binary))
        entry = {"id": f"chromium-{_slug_version(version)}",
                 "name": f"Chromium {version}",
                 "version": version, "engine": "chromium",
                 "path": final_binary, "source": "cft",
                 "download_url": download_url,
                 "installed_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        reg = _load_registry()
        reg["kernels"][entry["id"]] = entry
        _save_registry(reg)
        return entry
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── Job unduh latar (dibagi GUI + Local API via file state) ───────────────
def _load_jobs():
    data, _q = json_store.load_json_safe(DOWNLOADS_FILE, {})
    return data if isinstance(data, dict) else {}


def _save_jobs(jobs):
    json_store.save_json_atomic(DOWNLOADS_FILE, jobs, chmod=0o600)


def _update_job(job_id, **fields):
    def _mut(jobs):
        if job_id in jobs:
            jobs[job_id].update(fields)
        return jobs.get(job_id)
    return json_store.atomic_update(DOWNLOADS_FILE, {}, _mut, chmod=0o600)


def start_download(version=None, platform="linux64", versions_url=None):
    """Mulai unduh di thread latar. Return job {job_id, state, version}.
    Job bisa dipantau via get_download_status(job_id)."""
    import secrets
    job_id = "dl_" + secrets.token_hex(6)
    job = {"job_id": job_id, "version": version or "latest",
           "platform": platform, "state": "queued", "downloaded": 0,
           "total": 0, "error": None, "kernel_id": None,
           "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    jobs = _load_jobs()
    jobs[job_id] = job
    _save_jobs(jobs)

    last_write = {"t": 0.0}

    def _progress(downloaded, total):
        now = time.time()
        if now - last_write["t"] < 1.0 and downloaded != total:
            return
        last_write["t"] = now
        _update_job(job_id, state="downloading",
                    downloaded=downloaded, total=total)

    def _run():
        try:
            _update_job(job_id, state="downloading")
            entry = download_kernel(version, platform,
                                    versions_url=versions_url,
                                    progress_cb=_progress)
            _update_job(job_id, state="done", kernel_id=entry["id"],
                        downloaded=_load_jobs().get(job_id, {}).get("total", 0))
        except Exception as e:
            _update_job(job_id, state="error", error=str(e)[:300])

    threading.Thread(target=_run, daemon=True).start()
    return job


def get_download_status(job_id):
    jobs = _load_jobs()
    if job_id not in jobs:
        raise KeyError(f"job {job_id} tidak ditemukan")
    return jobs[job_id]


def list_downloads():
    jobs = _load_jobs()
    return sorted(jobs.values(), key=lambda j: j.get("started_at", ""),
                  reverse=True)
