# FIX LOG — FASE 2 P0 StealthXGM (2026-11-07)

Perintah eksplisit Gil 2026-11-07 17:38 WIB ("Skrang lu build sama hermes stealhxgm") + 17:49 WIB ("Kita pake rea ini buat build stealtxgm", "Kita tiru adspower", "Tapi design kita harus fresh").
Rencana: `AUDIT-STEALTHXGM-2026-11-06.md` baris 317–345 (P0 item 1–9).
Pengaman: git baseline `3affb45` sebelum fix apa pun; backup tiap file sebelum diedit di `.fix-backups/`; jangan edit `dist/` langsung; kode kritikal di-review; maks 3x coba per bug; regression check per fix.
Remote view SKIP (Gil). Captcha solver TIDAK dibangun. Desain GUI fresh = nanti, bukan fase ini.

## P-01 — Duplikat profil menyalin identitas fingerprint persis (SELESAI)
- File: `gui/profiles.py` `duplicate_profile()` (baris ~330), `docs/USER-GUIDE.md` (baris ~55).
- Backup: `.fix-backups/P-01-profiles.py.bak`, `.fix-backups/P-01-USER-GUIDE.md.bak`.
- Perubahan: `duplicate_profile()` sekarang (a) mengosongkan `cookies` (`p["cookies"] = []`), (b) me-regenerate `fingerprint.identity` via `generate_random(platform, timezone, locale)` + `to_jsonable()` (lazy import, pola sama seperti `gui/app.py:390`); bila regenerasi gagal, identity dihapus supaya launch generate ulang yang konsisten — identitas lama TIDAK PERNAH disalin. Setting lain (features, timezone, locale, platform, proxy, grup) tetap disalin.
- USER-GUIDE: klaim "fingerprint di-generate ulang biar beda" kini BENAR; ditambah keterangan cookies dikosongkan.
- Test (regression, `/tmp/test_p01.py`, DATA_DIR sementara — data live tidak disentuh): 4/4 LOLOS — (1) identity baru (dict beda, UA/GPU beda) + cookies kosong; (2) sumber tanpa identity → tetap tanpa identity + cookies kosong; (3) sumber di trash → None; (4) android → identity baru. `py_compile` OK.
- Catatan: 2 kegagalan awal adalah BUG TEST (bukan bug fix): test membandingkan key `user_agent` padahal generator menyimpan UA di key `_ua`; lalu lupa re-fetch profil setelah update. Keduanya diperbaiki di test, fix tidak diubah.
- Commit: `4aae91a`

## P-02 — Preview fingerprint menampilkan identitas yang TIDAK PERNAH dipakai saat launch (SELESAI)
- File: `gui/app.py` `api_preview()`, `gui/local_api.py` `user_preview()`.
- Backup: `.fix-backups/P-02-app.py.bak`, `.fix-backups/P-02-local_api.py.bak`.
- Perubahan: kedua preview sekarang memanggil `launcher.build_fingerprint_js(p)` yang sama dengan launch (via `_launcher()` yang sudah ada) — identity + `js_length` (termasuk `spoof_js_extra`) persis yang di-inject. Respons tambah `identity_stored` (bool) + `note` bila belum tersimpan ("belum tersimpan — preview ini contoh identitas yang akan digenerate saat launch (acak tiap launch sampai disimpan)"). Field lama (`js_length`, `features_enabled/total`, `timezone`, `platform`, `mobile`, `warp_fallback`) dipertahankan — frontend `previewFp()` (index.html:723) tidak berubah.
- Catatan jujur: untuk profil TANPA identity tersimpan, launch generate acak tiap kali, jadi preview hanya bisa menampilkan satu contoh hasil generate (bukan identitas persis yang akan dipakai) — itulah yang ditandai `identity_stored=false` + note.
- Test (regression, `/tmp/test_p02.py`, Flask test_client + DATA_DIR sementara): 4/4 LOLOS — GUI stored (identity == launch, js_length == launch), GUI no-store (flag false + note), LocalAPI stored (sama), LocalAPI no-store (flag false + note). `py_compile` OK.
- Catatan: 1 kegagalan awal adalah BUG TEST (respons Local API dibungkus `_ok()` di bawah key `data`, test membaca di top level). Fix tidak diubah.
- Commit: `157f229`

## P-03 — Judul tab `[StealthXGM] <nama profil>` membocorkan tool + nama profil (SELESAI)
- File: `launcher/launcher.py` `build_fingerprint_js()` (baris ~245).
- Backup: `.fix-backups/P-03-launcher.py.bak`.
- Perubahan: blok IIFE MutationObserver yang mem-prefix `document.title` dengan `'[StealthXGM] <nama> '` DIHAPUS total; diganti komentar yang menjelaskan kenapa prefix itu tidak boleh kembali (identitas jendela cukup di UI StealthXGM / judul window OS / brand new-tab page, bukan di dalam halaman web). Satu-satunya kemunculan string `[StealthXGM]` di file kini hanya di komentar itu (baris 246) — tidak ada di JS yang di-generate.
- Verifikasi: `build_extension()` hanya menulis `fingerprint_js` yang diterimanya (dari `build_fingerprint_js`), jadi jalur extension ikut bersih. File `browser_profiles/*/fingerprint_inject.js` lama masih berisi prefix (artefak launch lama, data runtime — diregenerasi tiap launch; bersih-bersih menyeluruh = M-18, P2).
- Test (regression, `/tmp/test_p03.py`): 3/3 LOLOS — desktop tanpa identity (js 37.750 char), desktop dengan identity (37.751), mobile android (6.620): semuanya tanpa `[StealthXGM]`, tanpa `document.title`, identitas tetap dikembalikan. `py_compile` OK.
- Commit: `b45d84a`

## P-04 — GUI (5200) dan Local API (50325) tanpa autentikasi + tanpa proteksi CSRF/CORS (SELESAI)
- File: `gui/api_config.py`, `gui/local_api.py`, `gui/app.py`, `gui/gui_launcher.py`.
- Backup: `.fix-backups/P-04-*.bak` (4 file).
- Perubahan:
  - **Local API key default ON:** `api_config.ensure_api_key()` — bila belum ada key, generate (`secrets.token_urlsafe(24)`) + simpan ke `api_config.json` (chmod 600) saat API pertama kali di-start. `start_api()` dan `gui_launcher --api-only` memakainya; key bisa dibaca automation dari file itu atau dari `POST /api/settings/api/key` (sekali tampil). `save_config` masih bisa mengosongkan key, tapi start berikutnya regenerate — dicatat sebagai perilaku, bukan bug.
  - **Transport key via env, bukan argv:** `start_api()` mengoper key lewat environment `STEALTHXGM_API_KEY`; `local_api.run()`/`__main__` membaca env sebagai fallback. Ini sekaligus menutup bagian argv dari P-09 (sisa P-09 = proxy-auth, tetap P1).
  - **Origin/Referer check GUI** (`app.py` `@app.before_request`): Origin ada → harus sama dengan Host; tidak ada Origin tapi ada Referer → Referer harus sama dengan Host; tidak ada keduanya → klien non-browser (curl/python/automation) diizinkan. Ini menahan CSRF localhost dari situs mana pun; frontend GUI sendiri same-origin jadi tidak terganggu.
  - **`MAX_CONTENT_LENGTH` 50 MB** di GUI dan Local API (Flask → 413 bila lewat).
  - **Peringatan bind:** `run()` mencetak PERINGATAN bila `STEALTHXGM_HOST` bukan localhost (GUI terekspos ke jaringan tanpa login).
- Risiko sisa (jujur): GUI tetap tanpa login — Origin-check menahan CSRF browser, BUKAN curl langsung dari LAN bila bind 0.0.0.0. Auth login GUI penuh = follow-up P1 (terkait P-12). Request tanpa Origin DAN Referer diizinkan by design (automation).
- Test (regression, `/tmp/test_p04.py`, DATA_DIR sementara): 6/6 LOLOS — (1) ensure key generate+persist+idempotent; (2) Origin/Referer: same-origin + tanpa header lolos, lintas-origin 403; (3) 413 pada body oversize; (4) Local API 401 tanpa key, lolos dengan key, `/status` tetap publik; (5) `start_api` proses sungguhan di port 50399: key TIDAK ada di `/proc/<pid>/cmdline` (tanpa `--api-key`), auth live 401/400 sesuai; (5b) `stop_api` bersih, tidak ada proses sisa. `py_compile` OK (4 file).
- Commit: `e5adb38`

## P-05 — Zip Slip di instalasi extension (SELESAI)
- File: `gui/extension_manager.py`, `gui/templates/index.html`.
- Backup: `.fix-backups/P-05-extension_manager.py.bak`, `.fix-backups/P-05-index.html.bak`.
- Perubahan:
  - **`_safe_extractall(z, dest)` baru:** validasi SEMUA member dulu, baru extract — tolak path absolut, komponen `..`, symlink Unix, dan path hasil-resolve yang keluar dari dest. Satu member jahat = seluruh archive ditolak, tidak ada file tertulis. `add_crx()` dan `add_zip()` sekarang memakainya (tidak ada lagi `.extractall(`).
  - **`_cws_download`:** `tempfile.mktemp` (racy/deprecated) → `mkstemp` + `os.close(fd)`.
  - **Permission manifest:** `_parse_manifest()` kini mengembalikan `permissions` + `host_permissions` (dinormalisasi ke list[str]) dan tersimpan di info extension (DB + respons install). Frontend menampilkannya di kartu library (`🔑 Izin: ... • 🌐 ...`) dan di pesan sukses upload/CWS.
- Catatan: `add_unpacked()` (install dari folder lokal milik operator sendiri) tidak diubah — jalur unduhan (zip/crx/CWS) yang rawan sudah ditutup. Verifikasi signature CRX tetap tidak ada (audit mencatatnya; di luar P-05).
- Test (regression, `/tmp/test_p05.py`, LIB_DIR/DB sementara): 7/7 LOLOS — (1) traversal `../` ditolak + tidak ada file tertulis + tidak ter-register; (2) path absolut ditolak; (3) symlink ditolak; (4) zip benign sukses + permissions tersimpan; (5) CRX traversal ditolak; (6) CRX benign sukses; (7) tidak ada `.extractall(`/`mktemp(` tersisa, frontend tampilkan izin. `py_compile` OK.
- Catatan: 1 kegagalan awal adalah BUG TEST (assert `"extractall" not in src` ikut kena nama fungsi `_safe_extractall` sendiri; diperbaiki jadi `.extractall(`). Fix tidak diubah.
- Commit: `e37abcc`

## P-06 — Launch mengembalikan "already_running" untuk browser yang sudah mati (SELESAI)
- File: `launcher/launcher.py`, `gui/app.py` (`run()`), `gui/local_api.py` (`run()`).
- Backup: `.fix-backups/P-06-launcher.py.bak`, `.fix-backups/P-06-app.py.bak`, `.fix-backups/P-06-local_api.py.bak`.
- Perubahan:
  - **`_session_alive(sess)` baru:** sesi hidup = `browser_pid` hidup (os.kill sinyal 0) DAN debug port menjawab `GET /json/version` dengan body mengandung `"Browser"`. PID saja tidak cukup (PID bisa dipakai ulang); port saja tidak cukup (port bisa dipakai ulang).
  - **`prune_stale_sessions()` baru:** hapus entri `sessions.json` yang browser-nya mati (crash/kill/VM restart), return jumlah yang dihapus. `list_running()` kini prune dulu sebelum mengembalikan daftar.
  - **Gate di `launch_profile()`:** entri ada + hidup → `already_running` seperti dulu; entri ada + basi → hapus lalu lanjut launch normal (tidak ada lagi jebakan stuck).
  - **Prune saat start:** `gui/app.py run()` dan `gui/local_api.py run()` memanggil `prune_stale_sessions()` via `_launcher()` (try/except — gagal prune tidak boleh menggagalkan start).
- Catatan: cek ini hanya MEMBACA (tidak kill PID apa pun) — bahaya PID-reuse di `stop_profile` (M-12) tetap P2, bukan bagian fix ini.
- Test (regression, `/tmp/test_p06.py`, SESSIONS_FILE sementara + fake server `/json/version` lokal): 6/6 LOLOS — (1) hidup butuh PID+port, PID-saja / port-saja = basi; (2) prune hapus 2 basi sisakan 1 hidup; (3) `list_running` prune; (4) sesi hidup → `already_running` tanpa launch; (5) sesi basi → gate lolos (terbukti `find_chrome` terpanggil via monkeypatch) + entri terhapus; (6) `run()` GUI + API memanggil prune. `py_compile` OK (3 file).
- Commit: `a806e98`

## P-08 — Geo-sync tidak memperbarui koordinat geolocation di identity tersimpan (SELESAI)
- File: `gui/geo_sync.py`, `launcher/launcher.py`, `gui/app.py` (respons sync-geo).
- Backup: `.fix-backups/P-08-geo_sync.py.bak`, `.fix-backups/P-08-launcher.py.bak`, `.fix-backups/P-08-app.py.bak`.
- Perubahan:
  - **`apply_geo_to_profile_data()`** kini membaca identity tersimpan dari `profile_data` dan mengembalikan `fingerprint.identity` yang diperbarui: `geo_lat`/`geo_lon` + `timezone` + `locale` dari negara pool. (Launcher memakai nilai dari identity bila ada — tanpa ini geo-sync hanya mengubah label timezone sementara geolocation tetap koordinat lama.) Profil tanpa identity tidak berubah perilakunya (launch generate baru yang konsisten). Dict identity asli tidak dimutasi (copy dulu).
  - **Bonus (launcher):** `build_fingerprint_js()` mengisi `geo_lat`/`geo_lon` dari timezone (peta `_COUNTRY_GEO`) bila identity tidak punya — mencakup identitas mobile/manual lama. Tanpa ini `network.py` jatuh ke default Singapore (1.3521, 103.8198) walau timezone Tokyo. Nilai geo yang sudah ada TIDAK ditimpa. Literal Singapore di `network.py` kini hanya jadi last resort untuk timezone di luar peta 29 negara.
  - Respons `POST /api/profiles/<id>/sync-geo` tambah `lat`/`lon` yang diterapkan.
- Test (regression, `/tmp/test_p08.py`, DATA_DIR sementara): 6/6 LOLOS — (1) apply update identity (geo+tz+locale), original tidak berubah; (2) tanpa identity → hanya tz/locale; geo None → {}; (3) alur penuh update_profile + launch pakai koordinat SG baru; (4) launcher isi geo mobile dari timezone Jakarta (bukan Singapore); (5) isi geo Tokyo dari timezone; (6) geo yang ada tidak ditimpa. Self-test bawaan `python3 gui/geo_sync.py` tetap PASS. `py_compile` OK (3 file).
- Catatan: 1 kegagalan awal adalah BUG TEST (asumsi identitas mobile tanpa geo — ternyata `generate_random("android")` sudah mengisi geo dari country; test diperbaiki dengan menghapus geo dulu untuk simulasi identitas lama). Fix tidak diubah.
- Commit: `78f9810`

## P-11 — File JSON corrupt = data hilang diam-diam (SELESAI)
- File: baru `gui/json_store.py`; diubah `gui/profiles.py`, `gui/proxy_pools.py`, `gui/api_config.py`, `gui/extension_manager.py` (kelas bug yang sama), `gui/app.py` (endpoint), `gui/templates/index.html` (banner).
- Backup: `.fix-backups/P-11-*.bak` (6 file).
- Perubahan:
  - **`gui/json_store.py` baru:** `load_json_safe()` — JSON rusak / bukan dict → file DIPINDAH ke `<nama>.corrupt-<timestamp>` (karantina, tidak pernah dihapus), kembalikan default; file hilang → default tanpa karantina; OSError baca → default tanpa menyentuh file. `save_json_atomic()` — tulis atomik (tmp + replace); sebelum menimpa, salin file lama ke `<nama>.bak` HANYA bila file lama masih JSON valid (supaya .bak selalu versi terakhir yang bagus). `list_quarantined()` untuk GUI.
  - **Keempat store** (`profiles`, `proxy_pools`, `api_config`, `extension_manager`) kini pakai helper itu; tiap `_load` mencetak WARNING ke log saat karantina terjadi. Perilaku first-run tidak berubah (file hilang → seed/default seperti dulu). `api_config._save` tetap mengembalikan `cfg` (dipakai `save_config`).
  - **Peringatan GUI:** endpoint baru `GET /api/system/storage-health` (daftar file `.corrupt-*` + status `.bak` tiap store); frontend `init()` memanggil `checkStorageHealth()` dan menampilkan banner merah bila ada file karantina.
- Test (regression, `/tmp/test_p11.py`, DATA_DIR sementara): 9/9 LOLOS — (1) profiles corrupt → karantina isi utuh + load {} + .bak ada; (2) proxy_pools corrupt → seed default + karantina; (3) api_config corrupt → default, key lama terselamatkan di .bak (bukan di karantina — karantina berisi bytes rusak); (4) extensions.json corrupt → default + karantina; (5) JSON bukan-dict → karantina; (6) file hilang → default tanpa karantina; (7) save atomik chmod 600 + .bak = versi sebelumnya; (8) endpoint laporkan 4 file karantina; (9) banner ada di frontend. Regression silang: test P-01, P-04, P-08 dijalankan ulang — semua tetap PASS. `py_compile` OK (6 file).
- Catatan: 1 temuan nyata saat testing — `.bak` sempat bisa tertimpa bytes rusak bila `_save` jalan saat file di disk corrupt; diperbaiki di helper (backup hanya bila JSON lama valid) + test diperketat. 1 kegagalan awal adalah BUG TEST (ekspektasi key lama ada di karantina — yang benar: key lama ada di .bak, karantina berisi bytes rusak).
- Commit: `d887b5a`

## P-13 — Build bisa bocorkan kredensial live ke installer (SELESAI)
- File: diubah `installer/build-copy.sh`, `installer/build-deb.sh`; baru `installer/smoke-test-build.sh` (ditulis Hermes, direview + diperluas merra).
- Backup: `.fix-backups/P-13-build-copy.sh.bak`, `.fix-backups/P-13-build-deb.sh.bak`, `.fix-backups/P-13-smoke-test-build.sh.hermes`.
- Perubahan:
  - **`installer/build-copy.sh`:** rsync exclude ditambah `gui/data/` (lubang utama — folder ini berisi profiles.json, proxy_pools.json, api_config.json, extensions.json, profile_extensions.json LIVE), `launcher/sessions.json`, `.fix-backups/`, `rea-adspower/`, `dist/`, `*.bak`, `*.corrupt-*`, `*.pid`, `*.tmp`. Smoke test `installer/smoke-test-build.sh "$DEST"` dijalankan sebelum "done" — `set -e` membuat build GAGAL bila smoke test gagal.
  - **`installer/build-deb.sh`:** smoke test dijalankan pada stage `.deb` (`$STAGE/opt/stealthxgm`) sebelum `dpkg-deb --build` — tangkap kebocoran bila `build/src` pernah diedit manual.
  - **Smoke test (Hermes + review merra):** gagal (exit 1) bila ada file JSON live-data (`profiles.json`, `proxy_pools.json`, `api_config.json`, `sessions.json`, `extensions.json`, `profile_extensions.json`), file JSON apa pun di bawah `gui/data/`, atau `"api_key": "<non-empty>"` di JSON mana pun; `launcher/brand/manifest.json` dikecualikan (file publik).
- Bukti lubang NYATA (sebelum fix): `gui/data/` di source berisi 5 file JSON live; `.deb` lama (2026-11-05) sudah berisi direktori kosong `gui/data/` — kredensial belum bocor hanya karena folder itu kosong saat build lama.
- Test (regression, `/tmp/test_p13.py` + build beneran): 5/5 LOLOS — (1) stage `build/src` bersih (tanpa gui/data, live JSON, .bak/.pid, rea-adspower, .fix-backups); (2) smoke test stage nyata → `OK`; (3) fake stage bocor (profiles.json / api_key) → exit 1 dengan pesan benar; manifest.json publik → lolos; (4) `.deb` baru bersih (0 match live-data/teardown/backup di `dpkg-deb -c`, 89 entri); (5) wiring ada di kedua script build. Build beneran: `build-copy.sh` rc=0, stage 916K (sebelumnya 1,5G karena rea-adspower ikut tersalin); `build-deb.sh` rc=0, `.deb` baru 153.856 byte.
- Catatan: smoke test MENANGKAP 2 kebocoran tambahan saat pengujian pertama — `launcher/sessions.json` ikut tersalin (exclude ditambah) dan `.fix-backups/` ikut tersalin (exclude ditambah) — inilah gunanya smoke test. 1 kegagalan awal adalah artefak pipe (`rc=$?` membaca `tail`, bukan build-copy) — build-nya memang gagal saat itu, sesuai desain.
- Commit: `11f959f`

---

## RINGKASAN AKHIR FASE 2 P0 (2026-11-07)

**9/9 fix P0 SELESAI, semua dengan regression test lolos + commit terpisah:**

| # | Fix | Test | Commit |
|---|---|---|---|
| P-01 | Duplikat profil regenerate identity + kosongkan cookies | 4/4 | `4aae91a` |
| P-03 | Hapus prefix `[StealthXGM]` dari document.title | 3/3 | `b45d84a` |
| P-02 | Preview tampilkan identity yang dipakai launch | 4/4 | `157f229` |
| P-04 | Auth + Origin-check GUI/API, API key default ON, MAX_CONTENT_LENGTH | 6/6 | `e5adb38` |
| P-05 | Zip Slip: validasi member zip, mktemp→mkstemp, tampilkan permission | 7/7 | `e37abcc` |
| P-06 | Liveness check sebelum already_running; prune sesi mati saat start | 6/6 | `a806e98` |
| P-08 | Geo-sync update geo_lat/geo_lon tersimpan | 6/6 | `78f9810` |
| P-11 | Backup + quarantine JSON corrupt (jangan reset diam-diam) | 9/9 | `d887b5a` |
| P-13 | build-copy exclude gui/data/ + smoke test pasca-build | 5/5 | (menyusul di bawah) |

Total regression P0: **50/50 LOLOS** (4+3+4+6+7+6+6+9+5). Regression silang pasca-refactor P-11: P-01, P-04, P-08 dijalankan ulang — semua tetap PASS.
- Repo: `~/workspace/antibrowser/`, baseline `3affb45`, 11 commit fix+log. Backup tiap fix di `.fix-backups/` (gitignored). File test di `/tmp/test_p01.py` … `/tmp/test_p13.py` (ephemeral; hasil tercatat di log ini).
- Hermes: 1 call sukses (skrip smoke test P-13, ditulis ke file, direview + diperluas merra). Tidak ada Hermes call lain.
- Batas dipatuhi: remote view SKIP, captcha solver TIDAK dibangun, tanpa perubahan desain GUI, `stealth-browser-package/` + `dist/` tidak disentuh langsung, tanpa tool/service berbayar.
- Sisa risiko yang dicatat jujur (bukan blocker P0): GUI masih tanpa login (Origin check blokir CSRF browser, bukan curl LAN langsung saat bind 0.0.0.0 — login GUI penuh = follow-up P1); `stale browser_profiles/*/fingerprint_inject.js` masih berisi prefix lama (diregenerasi tiap launch; bersih penuh = M-18, P2); `stop_profile` masih rentan PID-reuse (M-12, P2); CRX signature verification masih absen (di luar P-05); `add_unpacked()` tidak diubah (instalasi folder lokal oleh operator); amass network check belum terverifikasi di VM ini (di luar fase ini).
- TIDAK dikerjakan (di luar scope P0): P1 (P-07, P-09, P-10, P-12, P-14…P-18), P2, dan fitur AdsPower (agen teardown paralel selesai 18:00 WIB — peta fitur ada di `ADSPOWER-FEATURE-MAP-2026-11-07.md`).
