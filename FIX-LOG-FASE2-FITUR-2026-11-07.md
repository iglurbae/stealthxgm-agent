# FIX-LOG — Fase 3 Fitur (AdsPower top-10 sisa + P2 pendukung)

Perintah Gil: "Skrang lu build sama hermes stealhxgm" (2026-11-07 17:38 WIB) +
"Okay lu tuntasin ya" (18:14 WIB) + "Kita tiru adspower" + "Tapi design kita
harus fresh" (17:49 WIB). Sumber fitur: ADSPOWER-FEATURE-MAP-2026-11-07.md
(REA 6.8.0 vs AdsPower Global 8.6.3). Prasyarat: P0 SELESAI (9/9, 50/50),
P1 SELESAI (9/9, suite 247 PASS 0 FAIL, commit f069267).

## Baseline (sebelum fitur)

- `python3 tests/run_all.py` (2026-11-07 ~19:30 WIB): **204 PASS, 1 FAIL** —
  `test_p18_rpa.py` 0/1 FAIL: `RuntimeError: injector daemon did not become
  ready (timeout 20s)` di `launcher.py:1074` `_launch_profile_inner` →
  `_spawn_injector_daemon` (baris 654). Tree bersih sejak commit P1 f069267
  (git status clean), jadi BUKAN regresi kode.
- Re-run isolasi `python3 tests/test_p18_rpa.py` (2026-11-07 ~19:35 WIB):
  **43 PASS, 0 FAIL** (47 detik). Tidak ada proses chromium/injector sisa.
  Kesimpulan: **flaky lingkungan** — timeout daemon 20 detik saat suite penuh
  (banyak launch Chromium berurutan, beban CPU). Penanganan: retry-1x saat
  spawn daemon (lihat F3-0 di bawah). Bila terulang, naikkan timeout atau
  selidiki beban mesin saat suite jalan.

## Urutan bangun

1. F3-0 Baseline hardening: retry-1x spawn injector daemon.
2. F3-1 P2: BEKUKAN identity ke profil saat launch pertama.
3. F3-2 Synchronizer ("Cermin") — 15 rute /sync/* (model AdsPower).
4. F3-3 Local API v1 lengkap + v2 inti (headless, cookie, filter grup,
   new-fingerprint, tags, proxy-list).
5. F3-4 Kernel manager (unduh/ganti Chromium per profil; slot Firefox).
6. F3-5 Backup/restore profil + cache.
7. F3-6 Batch import/export: progress + cancel + iOS.
8. F3-7 Extension Center aman (verifikasi tanda tangan CRX + pin versi).
9. F3-8 P2: login GUI penuh (follow-up P-04; bila tidak muat, catat sisa).

## Aturan fase ini

- Backup sebelum perubahan besar (.fix-backups/fase3/), commit terpisah per
  fitur, maks 3x coba per bug lalu lapor, regression check per fitur
  (tests/run_all.py harus tetap hijau).
- JANGAN edit dist/ langsung. JANGAN redesign GUI. JANGAN salin kode AdsPower.
  Remote view SKIP. Captcha solver JANGAN dibangun. Cloud sync/tim di luar
  scope. Tanpa tool/service berbayar.
- Hermes: tugas kecil & spesifik, prompt Inggris, tulis ke file, satu call
  lalu tunggu. Bila Hermes tidak menjawab ~10 menit / gagal 2x, kerjakan
  sendiri dan catat.

## Log per fitur

### F3-0 — Baseline hardening: retry-1x spawn injector daemon (SELESAI)

- `launcher/launcher.py` `_launch_profile_inner`: spawn daemon di-retry 1x
  (jeda 1 detik) bila gagal; `daemon_retries` tercatat di session dict.
- Bukti: `tests/test_f3_freeze.py` seksi [4] (mock spawn gagal 1x -> launch
  tetap sukses, daemon_retries=1). Suite penuh pasca-perubahan: 268 PASS,
  0 FAIL (termasuk p18 43/43 — flake tidak terulang di run ini).

### F3-1 — P2: BEKUKAN identity ke profil saat launch pertama (SELESAI)

- `launcher/launcher.py`: fungsi baru `freeze_identity(profile, ident)` —
  simpan identitas yang baru disuntik (sudah sinkron chrome_ver) ke
  `profiles.json` bila profil belum punya `fingerprint.identity`; baca ulang
  store dulu (proses lain mungkin sudah membekukan). Dipanggil di
  `_launch_profile_inner` setelah identity.json ditulis, HANYA bila
  `identity_override is None` (override sekali-pakai tidak dibekukan).
- Bukti: `tests/test_f3_freeze.py` **21 PASS, 0 FAIL** — unit (simpan sekali,
  tidak menimpa, vp tuple JSON-able, tanpa id -> False) + E2E launch nyata
  (identity tersimpan == identity.json; launch kedua identitas SAMA) +
  override tidak dibekukan (Tokyo tetap di identity.json, profil tetap kosong).
- Komentar basi di `_launch_profile_inner` ("temuan P-18, belum diperbaiki")
  diperbarui.

### F3-2 — Synchronizer ("Cermin") — 15 rute /sync/* (SELESAI)

- Modul baru `launcher/sync.py` (~600 baris): command mirroring — start/stop/
  status, range (all/selected), open_delay, mirror_steps (langkah RPA),
  open_url, input_text/paste, refresh_all, manageUrlTab (list/open/close/
  activate via HTTP DevTools /json/*), show_browser, get_position,
  sync_size (CDP Browser.setWindowBounds, fallback window.resizeTo, hasil
  per-jendela jujur), reset_download (reset LOG unduhan — jujur: bukan reset
  state unduhan browser), clear_log. State sesi di `gui/data/sync_state.json`
  (lock P-07) supaya GUI + Local API melihat sesi yang sama.
- Jujur dicatat di modul: pencerminan mouse/ketik LANGSUNG dari jendela
  leader TIDAK ada di fase ini (butuh content-script penangkap event).
- Rute Local API `/api/v1/sync/*` (nama AdsPower: toSyncOperateBrowser,
  toStopSyncOperateBrowser, getOperateBrowser, toInputTxt, toRefreshTab,
  toRangeBrowser, toOpenDelay, toShowBrowser, manageUrlTab, openUrl, paste,
  syncSize, getPosition, resetDownload, clear) + ekstensi kami `/sync/steps`.
- Rute GUI `/api/sync/*` (start/stop/status/range/open-delay/steps/open-url/
  input/refresh/tabs/show/position/size/clear/reset-download).
- CLI: `sync-start|sync-stop|sync-status|sync-open|sync-input|sync-refresh|
  sync-steps` (bicara ke Local API).
- Bukti: `tests/test_f3_sync.py` **55 PASS, 0 FAIL** — unit (mock, fan-out
  3 target + jeda, validasi) + E2E 2 browser nyata (open_url tercermin di
  kedua DOM, input masuk di keduanya, refresh reset input, tab open/close,
  get_position, sync_size via CDP ok) + API contract Local+GUI + CLI --help.
- Bug temu & perbaiki: `close_tab` balapan dengan /json/list (close async) —
  sekarang poll verifikasi maks 2 detik.

### F3-3 — Local API v1 lengkap + v2 inti (SELESAI)

- Tags (baru, `gui/profiles.py`): field `tags` per profil (normalisasi:
  strip/dedupe/maks 20 @ 50 karakter), filter OR di `list_profiles`,
  `list_tags` / `rename_tag` / `delete_tag` / `set_profile_tags`,
  migrasi profil lama (tanpa tags -> []). GUI: /api/tags + /api/profiles/
  <pid>/tags + filter ?tags= di list.
- Grup (baru): registry `gui/data/groups.json` (grup kosong tercatat),
  `create_group` / `rename_group` / `delete_group` (pindah ke default),
  `list_groups` gabung registry + profil. GUI: POST/PUT/DELETE /api/groups.
- `launcher.validate_cookies` (baru): validasi PER-COOKIE — diterima /
  ditolak+alasan / catatan field dihapus; `sanitize_cookies` kini delegasi
  ke fungsi ini (perilaku sama).
- `gui/backup.py` (baru, F3-3 baru cache): `cache_size` + `clear_cache`
  (tolak bila browser jalan; hanya hapus folder cache, file lain aman).
- v1 lengkap: browser/cloud-active (jujur Inactive + cloud_supported false),
  browser/local-active (alias active), group/create|list|update,
  user/delete-cache, user/regroup, application/list (Chromium sistem +
  kernel manager bila ada), user/list filter grup+tag (M-19), user/create
  terima tags.
- v2 inti: browser-profile/list|create|update|update-patch|delete|start|
  stop|stop-all|active, cookies (GET + POST validasi per-cookie),
  new-fingerprint (generate + bekukan, berlaku launch berikut), ua (dari
  identity jalan/tersimpan; tanpa identity -> error jelas), kernels
  (sistem; + kernel manager F3-4), delete-cache. browser-tags/*
  (list/create-validasi/update/delete), category/list + user-group/list
  (= grup), proxy-list/* (CRUD pool), user/list (local owner saja).
- TIDAK dibangun (dijawab jujur, bukan dipalsukan): share + user/* tim
  (code -1 "tidak didukung — mode lokal"), fb/* (tidak ada rute).
- CLI: list --group/--tags, tags, set-tags, group-list, group-rename.
- Bukti: `tests/test_f3_api.py` **86 PASS, 0 FAIL** (unit tags/grup,
  validate_cookies, cache, API v1+v2 mock, GUI, CLI --help).
- Bug temu & perbaiki: edit besar menduplikasi `user_list`/`user_delete`
  di local_api.py (Flask bentrok endpoint) — salinan lama dihapus.

### F3-4 — Kernel manager (SELESAI, unduh nyata sedang berjalan)

- Modul baru `launcher/kernels.py`: registry `gui/data/kernels.json`
  ({default, kernels}), `register/list/get/set_default/remove`,
  `resolve_kernel_chrome(profile)` (kernel profil > default > sistem),
  `detect_version` (Chromium "156.0.8078.4" maupun Firefox "140.0"),
  unduh Chrome for Testing (CfT resmi Google): versions JSON ->
  `find_download_url` (persis / fallback major sama / terbaru) ->
  unduh chunked + progress -> extract `chrome-linux64/chrome` ->
  deteksi versi -> registrasi. Job latar `start_download` +
  `get_download_status`/`list_downloads` (state di
  `gui/data/kernel_downloads.json`, dibagi GUI + Local API).
- Slot Firefox: registry/resolve/launch mendukung engine firefox
  (binary didaftarkan manual); unduh otomatis Firefox BELUM didukung
  (dicatat jujur di modul + error jelas bila diminta).
- Launcher: `_launch_profile_inner` memakai binary kernel pilihan profil;
  `build_fingerprint_js(..., chrome_path=...)` — chrome_ver identitas
  mengikuti binary YANG JALAN (bukan Chromium sistem).
- Profil: field baru `kernel` ("system" default) di create/update.
- GUI: /api/kernels (list + system), /download (job 202), /downloads,
  /register, DELETE /<id>, /<id>/default, /api/profiles/<pid>/kernel.
- Local API: v2 download-kernel (POST job) + status + list; kernels list
  + application/list kini menyertakan kernel terdaftar.
- CLI: kernel-list|download|downloads|register|default|remove|set.
- Bukti: `tests/test_f3_kernels.py` **58 PASS, 0 FAIL** (unit registry,
  unduh via HTTP lokal + job latar, build JS ikut kernel, API, CLI).
- Bug temu & perbaiki: regex versi menuntut x.y.z (Firefox "140.0"
  gagal) -> regex 2-4 komponen; chmod binary SEBELUM deteksi versi.
- Unduh NYATA (CfT, versi terbaru 159.0.8148.0, ~130 MB) sedang berjalan
  di background saat commit ini — hasil dicatat di bawah bila selesai.

### F3-5 — Backup/restore profil + cache (SELESAI, 49/49)

- `gui/backup.py`: `export_profile` (ZIP: manifest.json + profile.json
  utuh + browser_data/identity.json, fingerprint_inject.js,
  profile_cookies.json + cache/<folder> bila diminta DAN profil
  mengizinkan), `restore_profile` (profil BARU id baru — identity beku,
  cookies, tags, data browser, cache ikut pulih), `list_backups` (baca
  manifest tanpa extract; ZIP rusak ditandai valid=False),
  `delete_backup` (tolak `../`, subdir, nama kosong).
- Profil: field baru `cache_backup` (default True) — saklar ala AdsPower;
  ekspor profil jalan BOLEH (snapshot best-effort, dicatat di manifest).
- GUI: POST /api/profiles/<pid>/backup (201), GET /api/backups,
  POST /api/backups/<f>/restore (201), DELETE /api/backups/<f>.
  Local API: v2 backup/backup-list/restore-backup + v1 user/backup* .
- CLI: backup-create [--no-cache] | backup-list | backup-restore
  [--name] | backup-delete | cache-size.
- Bukti: `tests/test_f3_backup.py` **49 PASS, 0 FAIL**.
- Bug temu & perbaiki: (1) app.py pakai `jsonify` bukan `_ok`/`_err`
  (milik local_api); (2) `import backup` hilang di app.py; (3) local_api
  pakai `pm` bukan `_pm`; (4) `BadZipFile` bukan ValueError -> ditangkap
  di restore; (5) layout cache palsu test salah (modul pakai folder
  top-level `Cache/` dst, bukan `Default/Cache/`); (6) dua ekspor dalam
  detik yang sama menimpa file yang sama -> sufiks -2/-3; (7) test
  mengotori `browser_profiles/` asli -> `_profiles_root` diarahkan ke
  tmp + 40 direktori yatim dibersihkan.
- **Unduh kernel NYATA BERHASIL (F3-4, bukti end-to-end):** CfT
  159.0.8148.0, ZIP 210.016.335 byte, terdaftar
  `chromium-159.0.8148.0`, `--version` = "Google Chrome for Testing
  159.0.8148.0", `detect_version` cocok. Bug temu: /tmp tmpfs 512 MB
  penuh saat extract -> temp unduh pindah ke KERNELS_DIR (disk 150 GB).

### F3-6 — Batch import/export + progress/cancel + iOS (SELESAI, 49/49)

- iOS: `PLATFORMS` + "ios"; parse CSV/JSON memaksa `mobile=True` bila
  platform ios (launcher hanya memakai platform ios bila fp.mobile True
  — `_consistent_fallback_identity`); template CSV kini memuat baris iOS.
- Ekspor (baru): `export_profiles(ids?, fmt, group?)` — CSV
  (name,group,pool,platform,timezone,notes,warp_fallback,mobile,tags,
  kernel,cache_backup) atau JSON; format keluaran bisa diimpor lagi
  (round-trip teruji).
- Job (baru): `start_import_job` / `start_export_job` — thread latar,
  state di `gui/data/batch_jobs.json` (file = sumber kebenaran),
  progress done/total per baris/profil, `cancel_job` dicek antar baris;
  hasil ekspor tersimpan di `gui/data/batch_exports/<job_id>.<fmt>`.
  Impor sinkron lama tetap ada (dipakai bila tanpa ?async=1).
- GUI: POST /api/profiles/import?async=1 (202 job), GET /api/batch/jobs,
  GET /api/batch/jobs/<id>, POST .../cancel, POST /api/profiles/export
  (202 job), GET /api/batch/jobs/<id>/download.
- Local API: v2 batch-import/batch-export/batch-job(+cancel) + v1
  batch-import/batch-job. (Di 208 path AdsPower tidak ada endpoint
  batch — API ini desain kita sendiri, dicatat jujur.)
- CLI: batch-import <file> (poll otomatis), batch-export [--format
  --group --out], batch-jobs, batch-job, batch-cancel.
- Bukti: `tests/test_f3_batch.py` **49 PASS, 0 FAIL** (iOS, round-trip,
  cancel deterministik via _create_one diperlambat, API, CLI).
- Bug temu & perbaiki: job impor kosong mengembalikan dict lama
  (state running) -> kembalikan hasil _update_job.

### F3-8 — Login GUI penuh (SELESAI, 63/63)

- Modul baru `gui/auth.py`: SATU password operator (bukan multi-user —
  Gil satu-satunya operator; keputusan desain dicatat), PBKDF2-HMAC-
  SHA256 600.000 iterasi + salt 16 byte di `gui/data/auth.json`
  (chmod 600, tanpa plaintext); sesi token acak, yang disimpan hanya
  SHA256 token di `gui/data/gui_sessions.json` (chmod 600); berlaku
  12 jam, sliding bila sisa < 2 jam, maks 24 jam; ganti password =
  semua sesi lama hangus; brute-force 5 gagal/IP -> kunci 15 menit.
- Penegakan OPT-IN (keputusan sadar): bila password BELUM diset, GUI
  berperilaku seperti dulu (terbuka) — CLI + semua test lama tidak
  pecah. Begitu password diset, semua /api/* (kecuali /api/auth/*)
  butuh sesi (cookie httponly `sxgm_session` atau header
  `X-Session-Token`); GET / redirect ke /login bila belum login.
  Bind non-localhost TANPA password = DITOLAK saat start (P-04d).
- Route: GET /login (halaman minimal self-contained — BUKAN redesign
  GUI), GET /api/auth/status, POST /api/auth/setup (201; kedua -> 403),
  POST /api/auth/login (401 salah, 429 terkunci), POST /api/auth/logout,
  POST /api/auth/change-password (butuh sesi + password lama).
- CLI: `login` (tanya password interaktif / --password, simpan token
  ke ~/.cache/stealthxgm/session.json chmod 600), `logout`;
  `api_req` otomatis menyertakan X-Session-Token bila ada.
- Bukti: `tests/test_f3_login.py` **63 PASS, 0 FAIL** (unit, rate
  limit, API cookie+header, bind guard, penyimpanan, CLI).
- Bug temu & perbaiki: `is_locked_out` menghapus catatan gagal saat
  `until==0` (belum pernah terkunci) -> hitungan gagal ter-reset tiap
  request, lockout tidak pernah tercapai; `load_json_safe` return
  tuple (data, quarantined) bukan dict.
- Sisa yang dicatat (bukan dikerjakan): rate-limit di memori proses —
  restart GUI mereset hitungan gagal; multi-user tidak dibangun.

## RINGKASAN FASE 3

| Fitur | Commit | Test | Hasil |
| --- | --- | --- | --- |
| F3-0 retry daemon + F3-1 bekukan identity | ea4436b | test_f3_freeze.py | 21 PASS |
| F3-2 Synchronizer "Cermin" (15 rute /sync/*) | 26265e8 | test_f3_sync.py | 55 PASS |
| F3-3 Local API v1 lengkap + v2 inti | 30cd11b | test_f3_api.py | 86 PASS |
| F3-4 Kernel manager (CfT) | d3b81d7 | test_f3_kernels.py | 58 PASS |
| F3-5 Backup/restore + cache | e2f2081 | test_f3_backup.py | 49 PASS |
| F3-6 Batch import/export + iOS | 5312d57 | test_f3_batch.py | 49 PASS |
| F3-7 Extension Center aman | e557861 | test_f3_extensions.py | 57 PASS |
| F3-8 Login GUI penuh | (commit ini) | test_f3_login.py | 63 PASS |

Suite penuh pasca F3-6: **565 PASS, 0 FAIL** (25 file). Suite penuh
final: **685 PASS, 0 FAIL** (27 file, ~3 menit) — semua file F3 baru
+ semua regresi P0/P1 hijau.

Bukti end-to-end di luar test: unduh kernel NYATA Chrome for Testing
159.0.8148.0 (ZIP 210 MB) berhasil + terdaftar + `--version`
terverifikasi.

Tidak dikerjakan (sesuai perintah): desain fresh GUI (fase berikut),
remote view (SKIP), captcha solver (JANGAN), cloud sync/tim (di luar
scope), cron live-stealth (tunggu kata Gil).

