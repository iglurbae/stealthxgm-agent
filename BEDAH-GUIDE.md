# BEDAH-GUIDE — StealthXGM 1.0.0

Panduan buat agent/developer lain yang mau membedah StealthXGM: arsitektur,
alur data, file kunci, dan cara ngetesnya. Ditulis dari source 2026-11-05
(7.102 baris Python, 81 file).

**Sekilas:** StealthXGM = manager profil browser anti-detect ala AdsPower.
Bikin profil Chromium tanpa batas, tiap profil punya identitas fingerprint
sendiri (29 teknik spoofing yang bisa di-toggle), proxy sendiri
(1 profil = 1 IP), plus GUI web + Local REST API yang kompatibel AdsPower.

**Status:** PC 100% selesai — 14 fitur PASS (diuji 2026-11-04). Installer
Linux `.deb` teruji; build Windows `.exe` siap (script ada, build di Windows).

---

## 1. Peta arsitektur

```
StealthXGM
├── fingerprint/      # MESIN fingerprint — 12 modul, ~2.600 baris
│   └── __init__.py   # public API (spoof_js, new_identity, auto_identity, ...)
├── gui/              # GUI web Flask (port 5200) + Local API (port 50325)
│   ├── app.py            # GUI REST API: profil CRUD, batch, trash, pools
│   ├── local_api.py      # Local API AdsPower-compatible (/api/v1/...)
│   ├── fingerprint_gen.py# generator identitas desktop/mobile + validasi
│   ├── profiles.py / proxy_pools.py / api_config.py / extension_manager.py
│   ├── batch_import.py   # import profil massal (CSV/JSON)
│   ├── geo_sync.py       # sinkronisasi geo (timezone/locale dari IP)
│   ├── gui_launcher.py   # entry: GUI + API sekaligus
│   └── templates/ static/ docs/   # UI + dokumentasi
├── launcher/         # Peluncur Chromium (Playwright)
│   ├── launcher.py       # build fingerprint JS, proxy resolve, launch args
│   ├── injector_daemon.py# injeksi fingerprint ke browser hidup
│   ├── extension_builder.py / brand_builder.py / make_icon.py
│   └── brand/            # branding (ikon, new-tab page)
├── vendor/           # fingerprint mobile (modul vendor)
├── antibrowser-cli.py# CLI: list/create/launch/stop/delete/status
├── installer/        # build-copy, build .deb, build .exe (PyInstaller)
└── docs/             # USER-GUIDE, API, CLI-REFERENCE, FINGERPRINT-FLAGS, ...
```

### Alur data (sekali jalan)

```
User (GUI/CLI/API)
  → gui/app.py atau local_api.py
    → gui/profiles.py      (profil disimpan sebagai JSON di data-dir user)
    → gui/fingerprint_gen.py (generate_identity: desktop/mobile, validasi konsistensi)
      → fingerprint/*      (spoof_js: hasilkan JS injeksi dari identitas + 29 flag)
    → launcher/launcher.py (resolve proxy per profil → launch args Playwright)
      → Chromium (user-data-dir per profil, JS injeksi, proxy)
        injeksi 2 lapis (P-17): 1) injector_daemon.py (CDP add_init_script,
        utama — jalan headless + headful); 2) extension MV3 fp_ext/
        (world=MAIN, document_start — headful saja, bertahan bila daemon
        mati). Kedua lapis suntik JS yang sama; once-guard di
        build_fingerprint_js() memastikan tiap dokumen dieksekusi 1x.
```

### Data user (tidak ikut paket)

Semua state user tinggal di luar source tree, via env var:

- Linux: `~/.local/share/stealthxgm/` (`STEALTHXGM_DATA_DIR`)
- Windows: `%APPDATA%\StealthXGM\`
- Profil browser Chromium: `<data-dir>/browser_profiles/` (`STEALTHXGM_PROFILES_DIR`)

File state: `profiles.json`, `proxy_pools.json`, `api_config.json`,
`extensions.json`, `profile_extensions.json`. Kalau file tidak ada, aplikasi
membuat default sendiri saat start (cek `if not os.path.exists(...)` di
`gui/profiles.py`, `gui/proxy_pools.py`, `gui/api_config.py`).

---

## 2. Mesin fingerprint — 12 modul

Silsilah arsitektur: struktur 7-layer (fingerprint → behavioral → network →
canvas/audio → identity → stealth-extra → native-toString) yang di-refactor
jadi 12 modul. Prinsip yang sama: **satu keputusan → semua konsisten**
(consistency cascade).

| Modul | Baris | Tugas |
|---|---|---|
| `_core.py` | 173 | `spoof_js()` — rakit semua section JS jadi satu injeksi |
| `_common.py` | 19 | Helper kecil (`_fon` dkk) |
| `devices.py` | 202 | Pool GPU, screen, hardware; `new_identity()` |
| `geo.py` | 188 | Geo 18 negara, user-agent, `auto_identity()` / `auto_spoof_js()` |
| `navigator.py` | 406 | Section navigator/browser (UA, platform, bahasa, plugin, suara) |
| `canvas_audio.py` | 341 | Section canvas, WebGL, audio (noise anti-fingerprint) |
| `screen.py` | 21 | Section screen/CPU/memory |
| `network.py` | 117 | Section network info + geolocation; `spoof_js_webrtc_block()` |
| `behavioral.py` | 95 | Section behavioral (timezone, font) |
| `behavioral_human.py` | 328 | Perilaku manusia (ketik, scroll, mouse) — dipakai otomasi/API |
| `stealth_extra.py` | 55 | Patch ekstra: iframe, `spoof_js_extra()` |
| `mobile.py` | 310 | Identitas mobile (`new_mobile_identity`, `mobile_spoof_js`) |
| `mobile_devices.py` | 265 | Database HP + mapping SoC→GPU (Snapdragon→Adreno, Dimensity→Mali, dst) |
| `__init__.py` | 39 | Public API — impor dari sini, bukan dari modul dalam |

### Pola kunci #1 — Consistency cascade

`generate_identity()` di `gui/fingerprint_gen.py`:

1. Pilih kelas GPU → tentukan layar, cores, RAM (GPU high = RAM ≥16GB,
   iGPU = layar ≤1920px).
2. Viewport < resolusi layar (ada chrome browser + taskbar).
3. `validate_identity()` + `assert_consistent()` menegakkan aturan di atas —
   inkonsistensi gagal sebelum jalan, bukan pas ketahuan anti-bot.

### Pola kunci #2 — 29 flag fingerprint

Tiap profil punya 29 flag `fp_*` (lihat `docs/FINGERPRINT-FLAGS.md`) yang
bisa di-toggle per profil. Contoh yang wajib-match dan jangan dimatikan:
`fp_webdriver_remove` (sembunyikan `navigator.webdriver`),
`fp_platform`, `fp_client_hints`, `fp_timezone_offset`,
`fp_perf_memory` (deviceMemory di-cap 8 — nilai >8 itu tell bot).
Yang disarankan ON: `fp_webrtc_block` (IP asli bocor lewat STUN kalau mati).

### Pola kunci #3 — Distribusi realistis

Random-nya berbobot sesuai dunia nyata, bukan uniform: budget 40% /
mid 40% / flagship 20%; Windows 10 lebih umum dari Windows 11.
Database device berisi spek HP beneran (resolusi, DPR, SoC, RAM, kode model UA).

---

## 3. GUI + Local API

### GUI (`gui/app.py`, 710 baris, Flask, port 5200)

Route utama (prefix `/api/`):

- `GET/POST /api/profiles` — list / bikin profil
- `GET/PUT|PATCH/DELETE /api/profiles/<pid>` — baca / ubah / hapus
- `POST /api/profiles/batch` — bikin banyak profil sekaligus
- `GET/POST/DELETE /api/trash...` — trash bin (restore, hapus permanen, kosongkan, cleanup)
- `POST /api/profiles/<pid>/duplicate` — duplikat profil
- `GET /api/groups`, `GET /api/flags` — grup + daftar flag fingerprint
- `GET/POST /api/pools`, `GET/PUT|PATCH/DELETE /api/pools/<pid>` — proxy pools

### Local API (`gui/local_api.py`, 250 baris, port 50325, AdsPower-compatible)

- `GET /api/v1/status` — status server
- `GET /api/v1/browser/start|stop|active` — start/stop/cek browser profil
- `POST /api/v1/user/create|update`, `GET /api/v1/user/list`,
  `POST /api/v1/user/delete` — kelola user/profil via API
- `GET /api/v1/features`, `GET /api/v1/user/<id>/preview` — fitur + preview
- Proteksi API key (`_check_api_key()`), key diatur di GUI → bagian API
  atau flag `--api-key`. Jalankan terpisah: `python3 gui/gui_launcher.py --api-only`.

### Launcher (`launcher/launcher.py`, 759 baris)

Fungsi penting:

- `find_chrome()` / `get_real_chrome_version()` — cari Chromium + versinya
- `sync_identity_chrome_version()` — samakan versi Chrome identitas dengan
  Chrome asli (mismatch = tell)
- `build_fingerprint_js()` — rakit JS injeksi dari profil + identitas
- `resolve_proxy()` / `_resolve_primary_proxy()` — pilih proxy per profil
  (sticky per profil, fallback kalau mati)
- `build_launch_args()` — argumen Chromium (debug port, proxy, ekstensi)
- `wait_debug_port()` — tunggu browser siap (timeout 25 dtk)
- `sanitize_cookies()` — bersihkan cookie sebelum simpan
- `list_running()` / `_read_sessions()` / `_write_sessions()` — sesi hidup

---

## 4. Cara jalanin + ngetes (urutan yang disarankan)

```bash
# 1. Extract source, install deps
unzip StealthXGM-1.0.0-source.zip -d StealthXGM && cd StealthXGM
pip install flask playwright
python3 -m playwright install chromium   # ~170MB, sekali saja

# 2. Self-test mesin fingerprint (tiap modul bisa membuktikan dirinya)
python3 -m fingerprint.devices
python3 -m fingerprint.geo
python3 gui/fingerprint_gen.py          # generate + validasi identitas

# 3. Test launcher (tanpa buka browser)
python3 launcher/test_launcher.py

# 4. Jalankan GUI + API
python3 gui/gui_launcher.py
# GUI: http://127.0.0.1:5200  |  API: http://127.0.0.1:50325/api/v1/status

# 5. CLI (butuh GUI/API jalan)
python3 antibrowser-cli.py list
python3 antibrowser-cli.py create --name "test-1"
python3 antibrowser-cli.py launch <id>
python3 antibrowser-cli.py status
python3 antibrowser-cli.py stop <id>
```

### Checklist 14 fitur (status saat paket ini dibuat: semua PASS)

1. CRUD profil (GUI) · 2. Batch import CSV/JSON · 3. Trash bin + restore ·
4. Duplikat profil · 5. Grup profil · 6. 29 flag fingerprint per profil ·
7. Generator identitas desktop/mobile + validasi konsistensi ·
8. Proxy pools (sticky per profil + fallback) · 9. Launch Chromium via
Playwright + injeksi fingerprint · 10. Local API AdsPower-compatible ·
11. Extension manager · 12. Branding (ikon, new-tab) · 13. CLI lengkap ·
14. Installer `.deb` + build `.exe` Windows.

---

## 5. Batasan yang jujur (baca sebelum bedah lebih jauh)

1. **Behavioral layer = otomasi/API saja.** Gerakan manusia (ketik/scroll/
   mouse) ada di `behavioral_human.py` buat dipakai otomasi — GUI-nya sendiri
   manual, jadi sudah natural.
2. **Patch JS di atas patch binary justru terdeteksi.** Pelajaran dari
   codebase ini: injeksi JS tambahan di atas fingerprint level-binary bisa
   menurunkan stealth — makanya injeksi dibatasi ke yang perlu saja
   (WebRTC block dkk).
3. **Chromium tidak dibundel** — diunduh saat first-run.
4. **Flask dev server** — cukup buat personal, bukan multi-user production.
5. **GUI bind 127.0.0.1** — akses jarak jauh butuh tunnel/reverse proxy sendiri.
6. **Captcha solver sengaja tidak dibundel** di proyek ini.
7. **Remote view (lihat + kontrol browser dari HP) belum ada** — fitur berikutnya
   di roadmap, bukan di paket ini.

---

## 6. Urutan baca yang disarankan

1. `docs/USER-GUIDE.md` — pakai dulu, baru bedah.
2. `fingerprint/__init__.py` → `fingerprint/devices.py` → `fingerprint/geo.py`
   → `gui/fingerprint_gen.py` — inti identitas.
3. `fingerprint/_core.py` + `fingerprint/navigator.py` — cara JS dirakit.
4. `launcher/launcher.py` — cara identitas jadi browser hidup.
5. `gui/app.py` → `gui/local_api.py` — permukaan API.
6. `installer/build-copy.sh` + `installer/build-deb.sh` — cara paket dibuat.
7. `docs/FINGERPRINT-FLAGS.md` — referensi 29 flag.
