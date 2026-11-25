# INSTALLER — StealthXGM

Cara build installer StealthXGM untuk PC. Source tree **tidak pernah** dimodifikasi —
semua build jalan dari copy bersih di `installer/build/src/` (dibuat oleh `build-copy.sh`).

## Ringkasan artefak

| Artefak | Status | Ukuran | Catatan |
|---|---|---|---|
| `stealthxgm_1.0.0.deb` (Linux) | ✅ jadi & teruji | ~113 KB | butuh `python3` + pip; Chromium diunduh saat first-run |
| `StealthXGM.exe` (Windows) | 🛠️ script siap, **build di Windows** | ~65 MB (estimasi) | PyInstaller tidak bisa cross-compile Linux→Windows |

## 1. Linux .deb (sudah jadi)

File: `installer/deb/stealthxgm_1.0.0.deb`

**Isi paket:**
- `/opt/stealthxgm/` — seluruh aplikasi (code + templates + docs)
- `/usr/bin/stealthxgm` — wrapper: set data-dir user, cek dependency, first-run Chromium
- `/usr/share/applications/stealthxgm.desktop` — entry menu aplikasi
- Data user: `~/.local/share/stealthxgm/` (profil, proxy, settings — writable per-user)

**Install:**
```bash
sudo dpkg -i installer/deb/stealthxgm_1.0.0.deb
stealthxgm
# buka http://127.0.0.1:5200
```

**Rebuild .deb dari source:**
```bash
./installer/build-copy.sh          # bikin copy bersih + patch path
./installer/build-deb.sh           # stage + dpkg-deb --build
```

**Yang terjadi saat first-run:** wrapper cek `flask` & `playwright` (auto-install via pip bila
hilang), lalu `python3 -m playwright install chromium` (~170MB, sekali saja).

## 2. Windows .exe (build di mesin Windows)

> **Kenapa tidak bisa di-build di Linux:** PyInstaller hanya bisa membuat binary untuk
> OS tempat ia dijalankan. Tidak ada cross-compile Linux→Windows yang didukung.

**Langkah di Windows 10/11 (Python 3.10+):**
```bat
git clone <repo> & cd antibrowser        :: atau copy folder project
installer\build-windows.bat
```
Hasil: `installer\build\dist\StealthXGM.exe` (~65MB, onefile, windowed/tanpa console).

File `.bat` menjalankan, berurutan:
1. `pip install pyinstaller flask playwright`
2. `installer\build-copy-win.bat` → copy bersih + `patch-copy.py`
   (setara `build-copy.sh`; butuh Python saja, tanpa Git Bash)
3. `pyinstaller installer\stealthxgm.spec`

**Spec file:** `installer/stealthxgm.spec` — entry `stealthxgm_main.py`, bundel
`gui/templates`, `gui/static`, `gui/docs`, `docs/`, `vendor/` sebagai data;
`hiddenimports` mencakup flask, playwright, dan semua modul fingerprint/gui.

**Catatan Windows:**
- Chromium **tidak** dibundel (~400MB). Saat pertama dijalankan, user perlu:
  `python -m playwright install chromium` — atau biarkan auto-prompt.
- Data user: `%APPDATA%\StealthXGM\` (profil, proxy, settings).
- Bila SmartScreen muncul: klik "More info" → "Run anyway" (binary belum di-sign).

## 3. Validasi yang sudah dilakukan (Linux, 2026-11-04)

- [x] `build-copy.sh` — 5 patch path tepat, source tree 0 perubahan (grep verifikasi)
- [x] `.deb` — `dpkg -i` sukses, `dpkg -s` = install ok
- [x] App terinstall jalan: GUI HTTP 200, `POST /api/profiles` bikin profil,
      data tertulis ke `~/.local/share/stealthxgm/` (bukan /opt)
- [x] PyInstaller Linux onefile — build sukses (62MB), binary jalan:
      GUI 200, API OK, Local API auto-start port 50325, data-dir override bekerja
- [x] `patch-copy.py` — hasil identik dengan `build-copy.sh` (5/5 patch)

## 4. File-file installer

```
installer/
├── stealthxgm_main.py      # entry point packaging (data-dir user + run GUI)
├── stealthxgm.spec         # PyInstaller spec (Windows & Linux)
├── build-copy.sh           # copy bersih + patch (Linux/macOS)
├── build-copy-win.bat      # copy bersih (Windows native)
├── patch-copy.py           # patch path (Windows, dipanggil .bat)
├── build-windows.bat       # orkestrasi build .exe di Windows
├── build-deb.sh            # orkestrasi build .deb
└── deb/
    ├── stealthxgm_1.0.0.deb            # artefak jadi
    └── stealthxgm_1.0.0/               # staging (DEBIAN/ + opt/ + usr/)
```

## 5. Batasan yang jujur

1. **.exe harus di-build di Windows** — tidak ada jalan pintas yang reliabel.
2. **Chromium tidak dibundel** di artefak mana pun (terlalu besar); diunduh saat first-run.
3. Paket `.deb` `Architecture: all` karena isinya murni Python; butuh koneksi internet
   saat first-run untuk pip + Chromium.
4. Flask dev server dipakai apa adanya (sama seperti versi source) — cukup untuk
   pemakaian personal; bukan untuk multi-user production.
