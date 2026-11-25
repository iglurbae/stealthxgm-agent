#!/usr/bin/env python3
"""
Extension Manager untuk StealthXGM.

Library extension global + assignment per profil.
Extension dimuat saat launch via --load-extension (unpacked dirs, comma-separated).
Lihat docs/RND-EXTENSIONS.md untuk hasil RND.

Struktur:
  ~/workspace/antibrowser/extensions/<ext_id>/   <- unpacked extension
  gui/data/extensions.json                        <- metadata library (chmod 600)
  gui/data/profile_extensions.json                <- {profile_id: [{ext_id, enabled}]}
"""
import io
import json
import os
import re
import shutil
import stat
import tempfile
import urllib.request
import zipfile

import json_store

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_DIR = os.path.join(BASE_DIR, "extensions")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
EXT_DB = os.path.join(DATA_DIR, "extensions.json")
ASSIGN_DB = os.path.join(DATA_DIR, "profile_extensions.json")

CWS_ID_RE = re.compile(r"^[a-z]{32}$")
CWS_URL_RE = re.compile(r"([a-z]{32})")


def _now():
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")


def _chmod600(path):
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _load_json(path, default):
    # P-11: JSON rusak -> karantina (jangan reset diam-diam).
    data, quarantined = json_store.load_json_safe(path, default)
    if quarantined:
        print(f"[extensions] WARNING: {path} corrupt, "
              f"dikarantina ke {quarantined}")
    return data


def _save_json(path, data):
    # P-11: backup bergilir (.bak) sebelum menimpa, tulis atomik, chmod 600.
    json_store.save_json_atomic(path, data, chmod=0o600)


def _db():
    return _load_json(EXT_DB, {})


def _db_save(db):
    _save_json(EXT_DB, db)


def _assign():
    return _load_json(ASSIGN_DB, {})


def _assign_save(a):
    _save_json(ASSIGN_DB, a)


def _new_id():
    import secrets
    return "ext_" + secrets.token_hex(4)


def _parse_manifest(ext_dir):
    """Baca manifest.json. Return dict atau raise ValueError."""
    mf = os.path.join(ext_dir, "manifest.json")
    if not os.path.isfile(mf):
        raise ValueError("manifest.json tidak ditemukan — bukan extension valid")
    try:
        with open(mf) as f:
            m = json.load(f)
    except ValueError:
        raise ValueError("manifest.json rusak (bukan JSON valid)")
    mv = m.get("manifest_version")
    if mv not in (2, 3):
        raise ValueError(f"manifest_version {mv} tidak didukung (harus 2/3)")
    perms = _norm_perm_list(m.get("permissions"))
    hosts = _norm_perm_list(m.get("host_permissions"))
    return {
        "name": m.get("name") or os.path.basename(ext_dir.rstrip("/")),
        "version": str(m.get("version") or "0.0.0"),
        "description": m.get("description") or "",
        "manifest_version": mv,
        # P-05: izin extension ditampilkan ke pengguna sebelum/saat install
        # (permissions + host_permissions dari manifest).
        "permissions": perms,
        "host_permissions": hosts,
        # F3-7: penilaian risiko permission (high/medium/low + flags).
        "risk": risk_for(perms, hosts),
    }


def _norm_perm_list(v):
    """Normalisasi field permission manifest jadi list[str]."""
    if isinstance(v, list):
        return [str(x) for x in v]
    if isinstance(v, str):
        return [v]
    return []


# ── F3-7: penilaian risiko permission + pin versi ─────────────────────────
HIGH_PERMS = {"cookies", "webRequest", "webRequestBlocking", "debugger",
              "management", "nativeMessaging", "proxy", "privacy",
              "browsingData", "system.storage"}
MEDIUM_PERMS = {"tabs", "storage", "scripting", "declarativeNetRequest",
                "history", "downloads", "bookmarks", "webNavigation",
                "contextMenus", "notifications", "alarms", "topSites",
                "sessions", "identity", "clipboardRead", "clipboardWrite",
                "desktopCapture", "geolocation", "tts"}
BROAD_HOSTS = {"<all_urls>", "*://*/*", "*://*", "http://*/*", "https://*/*",
               "*://*/*"}


def risk_for(permissions, host_permissions):
    """Nilai risiko permission manifest. Return {level, flags}.

    level: high bila ada izin berbahaya (baca cookie, intersepsi request,
    debugger, manajemen extension lain, pesan native) ATAU host luas
    digabung izin berbahaya; medium bila ada izin sensitif / host luas;
    low bila minimal. Dipakai saat preview & install — pengguna melihat
    risikonya SEBELUM extension masuk library.
    """
    perms = set(permissions or [])
    hosts = set(host_permissions or [])
    flags = []
    broad = bool(hosts & BROAD_HOSTS)
    for p in sorted(perms & HIGH_PERMS):
        flags.append(f"izin berbahaya: {p}")
    if broad:
        flags.append("host luas: akses semua situs")
        if perms & {"scripting", "tabs", "cookies", "webRequest"}:
            flags.append("host luas + izin baca/ubah halaman")
    for p in sorted(perms & MEDIUM_PERMS):
        flags.append(f"izin sensitif: {p}")
    if any("cookies" in p for p in perms):
        pass  # sudah ditangkap HIGH_PERMS
    if any(f.startswith("izin berbahaya") for f in flags) or \
            any(f.startswith("host luas + izin") for f in flags):
        level = "high"
    elif flags:
        level = "medium"
    else:
        level = "low"
    return {"level": level, "flags": flags}


def compare_versions(a, b):
    """Bandingkan versi semver-ish. Return -1/0/1 (a<b, a==b, a>b).

    Komponen non-numerik diabaikan ("1.0.0-beta" == "1.0.0"); komponen
    yang hilang dianggap 0 ("1.0" == "1.0.0").
    """
    def parts(v):
        out = []
        for chunk in str(v or "0").split("."):
            num = ""
            for ch in chunk:
                if ch.isdigit():
                    num += ch
                else:
                    break
            out.append(int(num) if num else 0)
        return out
    pa, pb = parts(a), parts(b)
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    return (pa > pb) - (pa < pb)


def _pb_varint(buf, i):
    n = 0
    shift = 0
    while i < len(buf):
        b = buf[i]
        i += 1
        n |= (b & 0x7F) << shift
        if not (b & 0x80):
            return n, i
        shift += 7
        if shift > 63:
            raise ValueError("varint protobuf terlalu panjang")
    raise ValueError("varint protobuf terpotong")


def _pb_fields(buf):
    """Iterator (field_no, wire_type, bytes|None) untuk pesan protobuf.

    Hanya wire 0 (varint), 1 (64-bit), 2 (length-delimited), 5 (32-bit)
    yang didukung — cukup untuk header CRX3.
    """
    i = 0
    while i < len(buf):
        tag, i = _pb_varint(buf, i)
        field, wire = tag >> 3, tag & 7
        if wire == 0:
            _v, i = _pb_varint(buf, i)
            yield field, wire, None
        elif wire == 2:
            ln, i = _pb_varint(buf, i)
            if i + ln > len(buf):
                raise ValueError("field protobuf melewati akhir buffer")
            yield field, wire, buf[i:i + ln]
            i += ln
        elif wire == 1:
            i += 8
            yield field, wire, None
        elif wire == 5:
            i += 4
            yield field, wire, None
        else:
            raise ValueError(f"wire type protobuf tak dikenal: {wire}")


def _crx3_public_key(header):
    """Ambil public key pertama dari header CRX3 (field 1 -> submessage
    field 1). Return bytes atau None bila tidak ditemukan / gagal parse."""
    try:
        for field, _wire, val in _pb_fields(header):
            if field == 1 and val is not None:
                for f2, _w2, v2 in _pb_fields(val):
                    if f2 == 1 and v2 is not None:
                        return v2
    except Exception:
        return None
    return None


def verify_crx(crx_path):
    """Verifikasi file CRX (struktural + integritas arsip + kunci).

    Return dict {valid, format, header_sha256, public_key_sha256,
    zip_ok, manifest, errors}. JUJUR: ini BUKAN verifikasi tanda tangan
    penuh (tidak ada rantai PKI ke Google di codebase ini) — yang
    diperiksa: magic Cr24, versi header 2/3, panjang header masuk akal,
    ZIP di offset benar + CRC semua member lolos, manifest ada & valid,
    dan sidik jari kunci publik header (untuk kontinuitas kunci saat
    update: kunci berubah = extension dicurigai berbeda).
    """
    import hashlib
    errors = []
    result = {"valid": False, "format": None, "header_sha256": None,
              "public_key_sha256": None, "zip_ok": False,
              "manifest": None, "errors": errors}
    try:
        with open(crx_path, "rb") as f:
            data = f.read()
    except OSError as e:
        errors.append(f"tidak bisa dibaca: {e}")
        return result
    if data[:4] != b"Cr24":
        errors.append("bukan file CRX (magic Cr24 tidak ditemukan)")
        return result
    ver = int.from_bytes(data[4:8], "little")
    if ver not in (2, 3):
        errors.append(f"versi CRX {ver} tidak didukung")
        return result
    result["format"] = f"crx{ver}"
    try:
        if ver == 3:
            hlen = int.from_bytes(data[8:12], "little")
            offset = 12 + hlen
            header = data[12:offset]
        else:
            klen = int.from_bytes(data[8:12], "little")
            slen = int.from_bytes(data[12:16], "little")
            offset = 16 + klen + slen
            header = data[16:16 + klen]
    except Exception as e:
        errors.append(f"header CRX rusak: {e}")
        return result
    if offset <= 0 or offset >= len(data):
        errors.append("offset ZIP CRX di luar file")
        return result
    result["header_sha256"] = hashlib.sha256(header).hexdigest()
    if ver == 3:
        key = _crx3_public_key(header)
        if key:
            result["public_key_sha256"] = hashlib.sha256(key).hexdigest()
    else:
        # CRX2: header = public key mentah (klen byte pertama).
        klen = int.from_bytes(data[8:12], "little")
        if 0 < klen <= len(data):
            result["public_key_sha256"] = hashlib.sha256(
                data[16:16 + klen]).hexdigest()
    # Integritas ZIP + manifest.
    try:
        with zipfile.ZipFile(io.BytesIO(data[offset:])) as z:
            bad = z.testzip()
            if bad:
                errors.append(f"member ZIP rusak (CRC gagal): {bad}")
                return result
            result["zip_ok"] = True
            tmpdir = tempfile.mkdtemp(prefix="ext_verify_")
            try:
                _safe_extractall(z, tmpdir)
                cand = tmpdir
                if not os.path.isfile(os.path.join(tmpdir, "manifest.json")):
                    subs = [d for d in os.listdir(tmpdir)
                            if os.path.isdir(os.path.join(tmpdir, d))]
                    found = [d for d in subs if os.path.isfile(
                        os.path.join(tmpdir, d, "manifest.json"))]
                    if not found:
                        errors.append("isi CRX tidak mengandung manifest.json")
                        return result
                    cand = os.path.join(tmpdir, found[0])
                result["manifest"] = _parse_manifest(cand)
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
    except zipfile.BadZipFile:
        errors.append("bagian ZIP CRX bukan ZIP valid")
        return result
    result["valid"] = not errors
    return result


def preview_file(path):
    """Pratinjau file extension TANPA menginstal. Return
    {kind, manifest (+risk), crx (verify, bila .crx)}.

    Dipakai GUI/CLI untuk menampilkan nama, versi, permission, dan
    risiko SEBELUM pengguna memutuskan install.
    """
    if not os.path.isfile(path):
        raise ValueError(f"file tidak ada: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext == ".crx":
        v = verify_crx(path)
        if not v["valid"]:
            raise ValueError("CRX tidak valid: " + "; ".join(v["errors"]))
        return {"kind": "crx", "manifest": v["manifest"], "crx": v}
    if ext == ".zip":
        if not zipfile.is_zipfile(path):
            raise ValueError("bukan file ZIP valid")
        tmpdir = tempfile.mkdtemp(prefix="ext_preview_")
        try:
            with zipfile.ZipFile(path) as z:
                _safe_extractall(z, tmpdir)
            cand = tmpdir
            if not os.path.isfile(os.path.join(tmpdir, "manifest.json")):
                subs = [d for d in os.listdir(tmpdir)
                        if os.path.isdir(os.path.join(tmpdir, d))]
                found = [d for d in subs if os.path.isfile(
                    os.path.join(tmpdir, d, "manifest.json"))]
                if not found:
                    raise ValueError("ZIP tidak mengandung manifest.json")
                cand = os.path.join(tmpdir, found[0])
            return {"kind": "zip", "manifest": _parse_manifest(cand),
                    "crx": None}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    raise ValueError("format harus .crx atau .zip")


def pin_version(eid, version=None):
    """Kunci extension ke satu versi. Update ke versi lain ditolak
    sampai unpin. version kosong = kunci ke versi terinstal saat ini.
    Return info terbaru."""
    info = get_extension(eid)
    if not info:
        raise ValueError(f"extension {eid} tidak ada di library")
    target = str(version) if version else info.get("version", "0.0.0")
    return _update_info(eid, pinned_version=target) or info


def unpin_version(eid):
    """Lepas kunci versi. Return info terbaru."""
    info = get_extension(eid)
    if not info:
        raise ValueError(f"extension {eid} tidak ada di library")
    return _update_info(eid, pinned_version=None) or info


def update_from_file(eid, path, force=False):
    """Update extension yang sudah ada ke versi baru dari file (.crx/.zip).

    Aturan: (1) pin versi menolak versi lain; (2) versi baru harus LEBIH
    BARU kecuali force=True; (3) kunci publik CRX harus sama (kontinuitas
    identitas — kunci berubah = extension dicurigai berbeda).
    ID extension + assignment profil dipertahankan.
    """
    info = get_extension(eid)
    if not info:
        raise ValueError(f"extension {eid} tidak ada di library")
    prev = preview_file(path)
    new_version = prev["manifest"]["version"]
    pinned = info.get("pinned_version")
    if pinned and compare_versions(new_version, pinned) != 0:
        raise ValueError(
            f"versi dikunci ke {pinned} — update ke {new_version} ditolak "
            "(unpin dulu bila memang mau ganti versi)")
    if not force and compare_versions(new_version, info.get("version", "0.0.0")) <= 0:
        raise ValueError(
            f"versi baru {new_version} tidak lebih baru dari "
            f"{info.get('version')} (pakai force bila memang mau reinstall)")
    if prev["kind"] == "crx":
        old_key = info.get("public_key_sha256")
        new_key = (prev["crx"] or {}).get("public_key_sha256")
        if old_key and new_key and old_key != new_key:
            raise ValueError(
                "kunci publik CRX berubah — extension dicurigai berbeda, "
                "update ditolak (hapus + install baru bila memang sengaja)")
    # Ganti isi folder library (id sama) — extract ke temp lalu swap.
    tmpdir = tempfile.mkdtemp(prefix="ext_update_")
    try:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".crx":
            with open(path, "rb") as f:
                data = f.read()
            offset = _crx_zip_offset(data)
            with zipfile.ZipFile(io.BytesIO(data[offset:])) as z:
                _safe_extractall(z, tmpdir)
        else:
            with zipfile.ZipFile(path) as z:
                _safe_extractall(z, tmpdir)
        cand = tmpdir
        if not os.path.isfile(os.path.join(tmpdir, "manifest.json")):
            subs = [d for d in os.listdir(tmpdir)
                    if os.path.isdir(os.path.join(tmpdir, d))]
            found = [d for d in subs if os.path.isfile(
                os.path.join(tmpdir, d, "manifest.json"))]
            cand = os.path.join(tmpdir, found[0])
        dest = os.path.join(LIB_DIR, eid)
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(LIB_DIR, exist_ok=True)
        shutil.copytree(cand, dest)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    meta = prev["manifest"]
    fields = {"version": meta["version"], "name": meta["name"],
              "description": meta["description"],
              "manifest_version": meta["manifest_version"],
              "permissions": meta["permissions"],
              "host_permissions": meta["host_permissions"],
              "risk": meta["risk"],
              "updated_at": _now()}
    if prev["kind"] == "crx":
        fields["public_key_sha256"] = (prev["crx"] or {}).get("public_key_sha256")
        fields["header_sha256"] = (prev["crx"] or {}).get("header_sha256")
    return _update_info(eid, **fields) or info


def _safe_extractall(z, dest):
    """Extract ZIP hanya bila SEMUA member aman (anti Zip Slip, P-05).

    Tolak sebelum menulis file apa pun: path absolut, komponen '..',
    symlink, dan path hasil-resolve yang keluar dari dest. Validasi
    semua member dulu, baru extract — satu member jahat = seluruh
    archive ditolak, tidak ada file yang tertulis."""
    dest_real = os.path.realpath(dest)
    members = z.infolist()
    for m in members:
        name = m.filename
        if not name:
            raise ValueError("member ZIP tanpa nama ditolak")
        if os.path.isabs(name):
            raise ValueError(f"member ZIP path absolut ditolak: {name!r}")
        parts = [p for p in name.replace("\\", "/").split("/")
                 if p not in ("", ".")]
        if ".." in parts:
            raise ValueError(f"member ZIP traversal ditolak: {name!r}")
        # symlink Unix (bit mode dari external_attr); zip Windows = 0, aman.
        if ((m.external_attr >> 16) & 0o170000) == 0o120000:
            raise ValueError(f"member ZIP symlink ditolak: {name!r}")
        target = os.path.realpath(os.path.join(dest_real, *parts))
        if target != dest_real and not target.startswith(dest_real + os.sep):
            raise ValueError(f"member ZIP keluar dari folder tujuan: {name!r}")
    for m in members:
        z.extract(m, dest)


def _register(ext_id, info):
    """P-07: insert DB atomik (load + save dalam satu lock) — dua install
    bersamaan tidak boleh saling menimpa."""
    def _mut(db):
        db[ext_id] = info
        return info
    return json_store.atomic_update(EXT_DB, {}, _mut, chmod=0o600)


def _update_info(ext_id, **fields):
    """P-07: update field info atomik. Dipakai add_crx/add_zip/add_from_cws
    yang sebelumnya load+save ulang di luar lock (racy)."""
    def _mut(db):
        if ext_id in db:
            db[ext_id].update(fields)
        return db.get(ext_id)
    return json_store.atomic_update(EXT_DB, {}, _mut, chmod=0o600)


def add_unpacked(src_dir, name_hint=None):
    """Install dari folder unpacked. Return info dict."""
    if not os.path.isdir(src_dir):
        raise ValueError(f"folder tidak ada: {src_dir}")
    meta = _parse_manifest(src_dir)
    ext_id = _new_id()
    dest = os.path.join(LIB_DIR, ext_id)
    os.makedirs(LIB_DIR, exist_ok=True)
    shutil.copytree(src_dir, dest)
    info = {
        "id": ext_id,
        "source": "unpacked",
        "path": dest,
        "installed_at": _now(),
        **meta,
    }
    if name_hint:
        info["name"] = name_hint
    return _register(ext_id, info)


def _crx_zip_offset(data):
    if data[:4] != b"Cr24":
        raise ValueError("bukan file CRX (magic Cr24 tidak ditemukan)")
    ver = int.from_bytes(data[4:8], "little")
    if ver == 3:
        hlen = int.from_bytes(data[8:12], "little")
        return 12 + hlen
    if ver == 2:
        klen = int.from_bytes(data[8:12], "little")
        slen = int.from_bytes(data[12:16], "little")
        return 16 + klen + slen
    raise ValueError(f"versi CRX {ver} tidak didukung")


def add_crx(crx_path, filename=None):
    """Install dari file .crx (parse header -> extract zip -> unpacked)."""
    with open(crx_path, "rb") as f:
        data = f.read()
    offset = _crx_zip_offset(data)
    # F3-7: simpan sidik jari header + kunci publik untuk kontinuitas
    # identitas saat update (kunci berubah = update ditolak).
    verify = verify_crx(crx_path)
    tmpdir = tempfile.mkdtemp(prefix="ext_crx_")
    try:
        with zipfile.ZipFile(io.BytesIO(data[offset:])) as z:
            _safe_extractall(z, tmpdir)
        # CRX kadang bungkus 1 subdir; cari manifest.json
        cand = tmpdir
        if not os.path.isfile(os.path.join(tmpdir, "manifest.json")):
            subs = [d for d in os.listdir(tmpdir)
                    if os.path.isdir(os.path.join(tmpdir, d))]
            found = [d for d in subs
                     if os.path.isfile(os.path.join(tmpdir, d, "manifest.json"))]
            if not found:
                raise ValueError("isi CRX tidak mengandung manifest.json")
            cand = os.path.join(tmpdir, found[0])
        info = add_unpacked(cand)
        extra = {"source": "crx"}
        if verify.get("public_key_sha256"):
            extra["public_key_sha256"] = verify["public_key_sha256"]
        if verify.get("header_sha256"):
            extra["header_sha256"] = verify["header_sha256"]
        if filename:
            extra["file"] = filename
        info = _update_info(info["id"], **extra) or info
        return info
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def add_zip(zip_path, filename=None):
    """Install dari .zip berisi extension unpacked."""
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("bukan file ZIP valid")
    tmpdir = tempfile.mkdtemp(prefix="ext_zip_")
    try:
        with zipfile.ZipFile(zip_path) as z:
            _safe_extractall(z, tmpdir)
        cand = tmpdir
        if not os.path.isfile(os.path.join(tmpdir, "manifest.json")):
            subs = [d for d in os.listdir(tmpdir)
                    if os.path.isdir(os.path.join(tmpdir, d))]
            found = [d for d in subs
                     if os.path.isfile(os.path.join(tmpdir, d, "manifest.json"))]
            if not found:
                raise ValueError("ZIP tidak mengandung manifest.json")
            cand = os.path.join(tmpdir, found[0])
        info = add_unpacked(cand)
        info = _update_info(info["id"], source="zip",
                            **({"file": filename} if filename else {})) or info
        return info
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _cws_download(store_id, timeout=60):
    url = ("https://clients2.google.com/service/update2/crx?response=redirect"
           "&prodversion=131.0.0.0"
           f"&x=id%3D{store_id}%26installsource%3Dondemand%26uc")
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/131.0.0.0 Safari/537.36"),
    })
    # P-05: mkstemp (bukan mktemp yang racy/deprecated) — file dibuat
    # atomik dengan fd eksklusif, bukan ditebak namanya.
    fd, tmp = tempfile.mkstemp(prefix="ext_cws_", suffix=".crx")
    os.close(fd)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        return tmp
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise ValueError(f"download CWS gagal: {e}")


def add_from_cws(url_or_id):
    """Install dari Chrome Web Store URL atau 32-char extension ID."""
    s = (url_or_id or "").strip()
    m = CWS_URL_RE.search(s)
    if not m:
        raise ValueError("ID/URL Chrome Web Store tidak valid (butuh 32 char id)")
    store_id = m.group(1)
    # cegah duplikat store_id
    for eid, info in _db().items():
        if info.get("store_id") == store_id:
            raise ValueError(f"sudah ada di library: {info['name']} ({eid})")
    crx_path = _cws_download(store_id)
    try:
        info = add_crx(crx_path, filename=f"{store_id}.crx")
        info = _update_info(info["id"], source="cws", store_id=store_id,
                            cws_url=f"https://chromewebstore.google.com/detail/{store_id}") or info
        return info
    finally:
        if os.path.exists(crx_path):
            os.remove(crx_path)


def list_extensions():
    return sorted(_db().values(), key=lambda e: e.get("installed_at", ""))


def get_extension(eid):
    return _db().get(eid)


def delete_extension(eid):
    # P-07: pop dari library atomik; assignment dibersihkan atomik juga.
    def _mut_db(db):
        return db.pop(eid, None)
    info = json_store.atomic_update(EXT_DB, {}, _mut_db, chmod=0o600)
    if not info:
        return False
    shutil.rmtree(os.path.join(LIB_DIR, eid), ignore_errors=True)
    # hapus dari semua assignment
    def _mut_assign(a):
        for pid in list(a.keys()):
            new = [x for x in a[pid] if x.get("ext_id") != eid]
            if len(new) != len(a[pid]):
                a[pid] = new
        return True
    json_store.atomic_update(ASSIGN_DB, {}, _mut_assign, chmod=0o600)
    return True


# ── Assignment per profil ──────────────────────────────────────────────

def assign(pid, eid, enabled=True):
    if eid not in _db():
        raise ValueError(f"extension {eid} tidak ada di library")
    # P-07: mutasi assignment atomik (load + save dalam satu lock).
    def _mut(a):
        lst = a.get(pid, [])
        for x in lst:
            if x.get("ext_id") == eid:
                x["enabled"] = bool(enabled)
                break
        else:
            lst.append({"ext_id": eid, "enabled": bool(enabled)})
        a[pid] = lst
        return True
    return json_store.atomic_update(ASSIGN_DB, {}, _mut, chmod=0o600)


def unassign(pid, eid):
    def _mut(a):
        lst = a.get(pid, [])
        new = [x for x in lst if x.get("ext_id") != eid]
        if len(new) == len(lst):
            return False
        a[pid] = new
        return True
    return json_store.atomic_update(ASSIGN_DB, {}, _mut, chmod=0o600)


def set_enabled(pid, eid, enabled):
    def _mut(a):
        for x in a.get(pid, []):
            if x.get("ext_id") == eid:
                x["enabled"] = bool(enabled)
                return True
        return False
    return json_store.atomic_update(ASSIGN_DB, {}, _mut, chmod=0o600)


def list_profile_extensions(pid):
    """Assignment profil digabung info library. Skip ext yang sudah dihapus."""
    db = _db()
    out = []
    for x in _assign().get(pid, []):
        info = db.get(x["ext_id"])
        if not info:
            continue
        out.append({**info, "enabled": bool(x.get("enabled", True))})
    return out


def resolve_extension_paths(pid):
    """Path unpacked dir untuk extension ENABLED milik profil (untuk launcher)."""
    paths = []
    for e in list_profile_extensions(pid):
        p = e.get("path")
        if e.get("enabled") and p and os.path.isdir(p):
            paths.append(p)
    return paths
