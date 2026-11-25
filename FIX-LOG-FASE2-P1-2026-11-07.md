# FIX LOG — FASE 2 P1 StealthXGM (2026-11-07)

Perintah eksplisit Gil 2026-11-07 17:38 WIB ("Skrang lu build sama hermes stealhxgm") + 18:14 WIB ("Okay lu tuntasin ya").
P0 SELESAI (9/9 fix, 50/50 test, log: FIX-LOG-FASE2-P0-2026-11-07.md). Sekarang P1.
Pengaman: git baseline P0 (commit `1d26aec` + P0 fixes); backup tiap file sebelum diedit di `.fix-backups/`; commit terpisah per fix; maks 3x coba per bug; regression check per fix.
Remote view SKIP (Gil). Captcha solver TIDAK dibangun. Desain GUI TIDAK diubah di fase ini.
CodeGraph: repo sudah di-index (`~/codegraph/bin/codegraph`) — dipakai buat navigasi kode, bukan grep buta. `codegraph sync` setelah edit besar.
Urutan P1 (audit): P-07 → P-17 → P-12 → P-09 → P-10 → P-14 → P-15 → P-18 → P-16 → P-04 follow-up.

## P-07 — file locking semua JSON store + per-profile launch guard (SELESAI)
- Masalah: semua store baca-ubah-tulis (tmp + os.replace) tanpa lock. GUI (Flask, multi-thread)
  + Local API = dua proses berbeda menulis file yang sama → lost update diam-diam. Dua klik
  Launch bersamaan untuk profil yang sama → dua Chromium di satu user-data-dir (profil korup).
- Perbaikan:
  - **`gui/json_store.py` (baru): `locked(path, timeout=10)` + `atomic_update(path, default, mutate)`.**
    Lock per store `<path>.lock` (dibuat saat perlu, TIDAK PERNAH dihapus); antar-proses
    fcntl.flock LOCK_EX (non-blocking + retry 50ms sampai timeout); antar-thread RLock per path
    (tanpa ini dua thread satu proses saling blokir); reentrant via refcount (nested locked()
    di thread yang sama tidak flock ulang — flock kedua pada fd berbeda di proses yang sama
    DEADLOCK di Linux). Timeout → `StoreLockTimeout`, pemanggil tidak boleh retry buta.
    Read-only TIDAK perlu lock (os.replace = pembaca selalu lihat versi lengkap).
  - **`gui/profiles.py`:** decorator `@_locked` di 8 mutasi (create/update/delete/restore/
    permanent_delete/empty_trash/auto_cleanup_trash/duplicate_profile); batch_* aman
    (reentrant). Migrasi field trash di `_load` kini simpan di bawah lock DENGAN baca ulang.
  - **`gui/proxy_pools.py`:** `@_locked` di create/update/delete/record_check; seed default
    di `_load` di bawah lock + cek ulang (double-checked).
  - **`gui/api_config.py`:** `@_locked` di save_config/generate_key; seed + reset-corrupt
    di `_load` di bawah lock + baca ulang.
  - **`gui/extension_manager.py`:** semua mutasi DB via `atomic_update` — `_register`,
    `_update_info` (baru; ganti pola load+save ulang yang racy di add_crx/add_zip/add_from_cws),
    delete_extension (library + assignment, masing-masing atomik), assign/unassign/set_enabled.
    Download/extract file TIDAK di bawah lock (bisa makan detik) — hanya load+save DB-nya.
  - **`launcher/launcher.py`:** (a) `_json_store()` lazy import; semua baca-ubah-tulis
    sessions.json di bawah `locked(SESSIONS_FILE)` — cek sesi hidup + buang basi di awal
    launch, catat sesi di akhir launch, pop di stop_profile (kill proses SETELAH lock lepas),
    prune_stale_sessions (liveness dicek tanpa lock, pop+write di bawah lock DENGAN
    verifikasi ulang — profil yang sempat mati lalu di-launch ulang tidak ikut terhapus);
    (b) **per-profile launch guard:** `_try_launch_lock(pid)` flock non-blocking pada
    `browser_profiles/<pid>/.launch.lock`, dipegang SELAMA launch; launch kedua →
    `{"ok": False, "error": "already_launching"}`; file lock TIDAK PERNAH dihapus.
  - **`gui/json_store.py` `save_json_atomic`:** tmp UNIK per pemanggilan (mkstemp) — sebelumnya
    `<path>.tmp` tetap, dua save bersamaan tabrakan nama tmp (FileNotFoundError di os.replace).
  - **`.gitignore`:** `*.lock` + `.codegraph/` ditambah (file lock runtime + index lokal).
- Test (regression, `tests/test_p07_locking.py` — BARU, di-commit ke repo; DATA_DIR/SESSIONS_FILE
  sementara, data live tidak disentuh): **14/14 LOLOS** — (1) nested locked() tidak deadlock;
  (2) timeout saat lock ditahan thread lain; (3) atomic_update gagal → file tidak berubah;
  (4) 8 proses × 25 create_profile bersamaan → **200/200 selamat**; (5) 4 proses
  assign/unassign bersamaan → hasil akhir konsisten (tepat 1 assignment enabled);
  (6) launch guard: kedua ditolak, launch_profile → already_launching tanpa sentuh Chromium,
  guard bisa dipegang lagi setelah release, file .launch.lock tetap ada;
  (7) 6 proses × 30 tulis sessions.json → 180/180 selamat.
  **Kontrol tanpa lock (lock di-monkeypatch jadi no-op): 200 create → hanya 29 selamat
  (171 hilang)** — test ini terbukti menangkap bugnya; sebelum tmp unik, kontrol malah crash
  FileNotFoundError massal (yang memicu perbaikan mkstemp di atas).
  Regression silang P0 (file yang diubah P-07): P-01 4/4, P-04 6/6, P-05 7/7, P-06 6/6,
  P-08 6/6, P-11 9/9 — semua tetap PASS. `py_compile` OK (6 file). CodeGraph sync OK.
- File: diubah `gui/json_store.py`, `gui/profiles.py`, `gui/proxy_pools.py`,
  `gui/api_config.py`, `gui/extension_manager.py`, `launcher/launcher.py`, `.gitignore`;
  baru `tests/test_p07_locking.py`.

## P-17 — arsitektur injeksi diputuskan: daemon + extension (SELESAI)
- Keputusan: **daemon + extension, daemon utama.** Daemon satu-satunya jalur yang jalan
  di headless (MV3 content script tidak jalan di `--headless=new` — docs/RND-EXTENSIONS.md:57),
  jadi daemon tidak bisa diganti. Extension adalah lapisan kedua yang berharga di headful:
  bertahan bila daemon mati (persis mode gagal P-10). Menghapus build_extension yang sudah
  jadi = membuang mitigasi P-10. Yang dihapus: `_connect_and_inject()` (nol pemanggil,
  komentarnya menyesatkan — mengklaim injeksi via extension padahal yang aktif hanya daemon).
- Perbaikan:
  - **`launcher/launcher.py` `build_fingerprint_js()`:** once-guard di sekeliling SELURUH
    JS — `Symbol.for("sxg")` di globalThis (bukan properti string di window: tidak muncul
    di Object.keys/for-in/JSON), non-enumerable. Kedua lapis menyuntik JS yang sama ke
    realm yang sama di headful; tanpa guard JS jalan 2x per dokumen (double-wrap
    canvas/getContext dll). Guard reset sendiri per dokumen (realm baru) — tiap dokumen
    tetap dieksekusi tepat 1x. JS sudah berupa IIFE tanpa top-level return/await, jadi
    bungkus luar aman. (Komentar P-03 dipertahankan — sempat terhapus satu edit, dikembalikan.)
  - **`launcher/launcher.py` `_launch_profile_inner()`:** panggil `build_extension()` dan
    masukkan `fp_ext/` ke `--load-extension` — HANYA bila tidak headless. Gagal build
    extension tidak menggagalkan launch (daemon tetap jalan).
  - **`launcher/extension_builder.py` + `launcher/README.md` + `BEDAH-GUIDE.md`:** dok
    diperbaiki — extension kini "lapisan kedua (headful)" bukan "alternatif"; alur data
    BEDAH-GUIDE menyebut kedua lapis + guard. (Klaim audit soal BEDAH-GUIDE "persistent
    MV3" ternyata sudah tidak harfiah di file saat ini; yang menyesatkan adalah komentar
    di `_connect_and_inject` — sudah dihapus bersama fungsinya.)
- Test (regression, `tests/test_p17_injection.py` — BARU, di-commit; launch nyata Chromium,
  browser_profiles/p17-test dibersihkan sesudahnya): **19/19 LOLOS** — (1) _connect_and_inject
  hilang, launch memanggil build_extension, komentar menyesatkan hilang; (2) guard Symbol
  ada di JS; (3) evaluasi JS 2x di realm yang sama: tidak throw, UA spoof identik, guard=1,
  webdriver=false; (4) launch headless nyata: UA spoof via daemon, fp_ext TIDAK dibuat;
  (5) launch headful nyata (xvfb): fp_ext/manifest.json + inject.js (berisi guard) ada,
  UA spoof + webdriver false dengan 2 lapis aktif. 1 kegagalan awal adalah BUG TEST
  (finally menghapus prof_dir sebelum fp_ext dicek — diperbaiki, cek dipindah sebelum cleanup).
  Regression: P-03 3/3, P-06 6/6, P-07 14/14 — semua tetap PASS. `py_compile` OK.
- File: diubah `launcher/launcher.py`, `launcher/extension_builder.py`,
  `launcher/README.md`, `BEDAH-GUIDE.md`; baru `tests/test_p17_injection.py`.

## P-12 — satu registry sesi (SELESAI)
- Masalah: tiga sumber status yang bisa berbeda — GUI `RUNNING={}`, Local API
  `_sessions={}`, `sessions.json` — plus field `status` di profiles.json yang basi
  selamanya pasca-crash. Browser launch lewat GUI → Local API jawab "Inactive".
- Perbaikan (satu sumber kebenaran: `sessions.json` + liveness via
  `launcher.list_running()`):
  - **`gui/local_api.py`:** `_sessions` DIHAPUS. `/api/v1/status` hitung
    `running_profiles` dari registry; `/api/v1/browser/active` baca registry
    (launch lewat GUI/CLI tetap terlihat Active); `/api/v1/user/list` turunkan
    status tiap profil dari registry; browser_start/stop/user_delete tidak lagi
    menyentuh dict in-memory. `run()` sync status file setelah prune.
  - **`gui/app.py`:** `RUNNING` DIHAPUS (ternyata write-only — tidak pernah dibaca).
    `GET /api/profiles` + `GET /api/profiles/<id>` timpa field status dari registry
    via helper baru `_with_live_status()` (return salinan, file tidak diubah).
    `run()` sync status file setelah prune.
  - **`launcher/launcher.py`:** helper baru `sync_profile_statuses(pm)` — rekonsiliasi
    field tersimpan dari registry hidup (hanya baris yang berubah yang ditulis,
    di bawah lock P-07); dipakai startup GUI + Local API. CLI tidak diubah —
    ia hanya konsumsi respons API (status + list) sehingga otomatis benar.
- Test (regression, `tests/test_p12_registry.py` — BARU, di-commit; DATA_DIR +
  SESSIONS_FILE sementara; sesi "hidup" dipalsukan dengan PID sendiri + fake
  server /json/version lokal, tanpa launch browser): **15/15 LOLOS** — (1)
  _sessions/RUNNING tidak ada; (2) sesi yang ditulis langsung ke sessions.json
  terlihat di /status (1), /browser/active (Active), /user/list (running),
  GUI list + single (running) — padahal Local API tidak pernah launch;
  (3) simulasi crash (fake port dimatikan) → prune → semua 0/Inactive/idle;
  (4) sync: status basi "running" di file → "idle"; dengan sesi hidup → "running".
  Regression: P-04 6/6, P-06 6/6, P-07 14/14, P-17 19/19 — semua tetap PASS.
  `py_compile` OK.
- File: diubah `launcher/launcher.py`, `gui/app.py`, `gui/local_api.py`;
  baru `tests/test_p12_registry.py`.

## P-09 — proxy-auth via extension + tanpa kredensial di argv (SELESAI)
- Masalah: (a) pool http/socks5 ber-user/pass mentok di dialog 407 — Chromium
  modern mengabaikan user:pass di --proxy-server; profil legacy malah kehilangan
  kredensialnya (URL dibangun tanpa user/pass). (b) password pool terlihat di
  `ps aux` / /proc/cmdline lewat --proxy-server.
- Perbaikan:
  - **`gui/proxy_pools.py`:** `pool_to_proxy_server()` TIDAK PERNAH lagi mengembalikan
    URL ber-kredensial; baru `pool_proxy_auth(pool)` -> (user, pass) | None, dan
    `_requests_proxies(pool)` untuk test_pool (kredensial BOLEH di URL karena
    in-process saja; user/pass di-quote agar `@`/`:` di password tidak merusak URL).
  - **`launcher/launcher.py`:** baru `resolve_proxy_with_auth(profile)` ->
    (proxy_server, note, auth); `resolve_proxy()` jadi wrapper backward-compat.
    Legacy http/socks5 kini teruskan user/pass sebagai auth (sebelumnya dibuang).
    WARP fallback -> auth=None. `build_launch_args()` defense-in-depth:
    `_strip_proxy_creds()` buang userinfo bila ada yang lolos. `_launch_profile_inner`
    membangun extension auth bila ada kredensial (gagal build tidak menggagalkan launch).
  - **`launcher/extension_builder.py`:** baru `build_proxy_auth_extension()` —
    MV3 extension `proxy_auth_ext/` (permissions webRequest + webRequestAuthProvider,
    background service worker) yang menjawab 407 via onAuthRequired HANYA bila
    details.isProxy (kredensial tidak pernah dikirim ke origin server).
    background.js chmod 600, kredensial di-escape via json.dumps. Listener SINKRON
    + ["blocking"] (pola MV3 yang didokumentasikan) + flag diagnostik
    __sxg_proxy_auth_ready/error.
  - **`gui/gui_launcher.py`:** contoh docstring `--api-key SECRET` diganti env var
    (kode sudah bersih sejak P-04: start_api oper key via env, bukan argv — diverifikasi).
- Test (regression, `tests/test_p09_proxy_auth.py` — BARU, di-commit; fake proxy
  lokal yang menuntut Basic auth, launch Chromium nyata): **25/25 LOLOS** —
  (1) pool helpers tanpa kredensial di URL + quote karakter khusus; (2) legacy +
  pool -> URL bersih + auth tuple; (3) build_launch_args strip kredensial;
  (4) manifest/background.js benar + chmod 600; (5) headless + (6) headful (xvfb):
  fetch lewat proxy ber-auth -> PROXY-AUTH-OK, proxy mencatat auth valid,
  password TIDAK ada di /proc/cmdline browser.
  **Jejak debug (3 percobaan, dicatat supaya tidak diulang):** (1) background.js
  async + ["blocking"] tidak valid — diganti sinkron + ["blocking"]; (2) page.goto
  ke host eksternal gagal net::ERR_BLOCKED_BY_CLIENT bahkan di bare Chromium
  tanpa proxy/extension — BUKAN bug kode: sandbox VM ini memblokir navigasi
  top-level eksternal (policy /etc/chromium/policies/managed/policy.json +
  egress), E2E dibuktikan lewat fetch() yang menempuh jalur 407 -> extension
  -> 200 yang identik; (3) request internal clients2.google.com sempat diduga
  "meracuni" state proxy — TERBANTAH: dengan clients2 dibalas 200, goto tetap
  gagal tanpa request ke proxy (blokir navigasi, bukan auth).
  Regression: P-04 6/6, P-06 6/6, P-07 14/14, P-12 15/15, P-17 19/19 — PASS.
  `py_compile` OK.
- File: diubah `gui/proxy_pools.py`, `launcher/launcher.py`,
  `launcher/extension_builder.py`, `gui/gui_launcher.py`;
  baru `tests/test_p09_proxy_auth.py`.

## P-10 — watchdog daemon injeksi (SELESAI)
- Masalah: daemon mati = fingerprint hilang diam-diam (tidak ada yang memeriksa
  lagi setelah startup); browser mati = daemon jadi yatim selamanya; stdout/stderr
  daemon ke DEVNULL (log crash hilang total).
- Perbaikan:
  - **`launcher/injector_daemon.py`:** loop `sleep(3600)` diganti watchdog — cek
    `browser.is_connected()` tiap 5 dtk (--check-interval); bila browser terputus,
    daemon KELUAR SENDIRI (exit 0 = shutdown normal, 1 = error tak terduga) + log
    alasannya. Log timestamp ke stdout (heartbeat dicatat tiap ~1 menit supaya
    tidak banjir; kegagalan selalu dicatat).
  - **`launcher/launcher.py`:** baru `_spawn_injector_daemon()` — stdout/stderr
    daemon ke `browser_profiles/<pid>/injector_daemon.log` (append, BUKAN DEVNULL);
    gagal startup -> RuntimeError berisi ekor log. Baru `daemon_health(pid)` +
    `ensure_injection(pid)` (re-inject: spawn ulang daemon dengan JS/cookies
    launch yang sama, update daemon_pid di sessions.json di bawah lock;
    throttle 60 dtk untuk percobaan gagal). `list_running()` kini menganotasi
    tiap sesi hidup dengan daemon_alive/injection_ok dan me-re-inject daemon
    mati bila browser hidup (injection_recovered=True).
  - **`gui/app.py` + `gui/local_api.py`:** respons profil kini sertakan
    `injection_ok` (None = tidak ada browser; True/False = injeksi jalan/mati) —
    data saja, tanpa ubah desain GUI.
  - **Bonus (temuan saat testing): `_pid_alive()` kini kenali zombie** — kill 0
    sukses untuk proses zombie, jadi daemon/browser yang sudah exit tapi belum
    di-reap parent sebelumnya dilaporkan "hidup" (ini yang membuat test awal
    gagal: daemon sudah mati tapi terdeteksi hidup). Cek /proc/<pid>/stat state
    != 'Z'. Ini juga memperbaiki liveness P-06 untuk browser zombie.
- Test (regression, `tests/test_p10_watchdog.py` — BARU, di-commit; launch Chromium
  nyata headless): **20/20 LOLOS** — (1) log ada + berisi "ready", health ok;
  (2) daemon di-SIGKILL -> health False -> list_running re-inject (pid baru,
  ready_file ada lagi, webdriver false di halaman baru); (3) browser di-SIGKILL
  -> daemon keluar sendiri <=20 dtk, log "browser terputus", sesi di-prune;
  (4) respawn gagal (js_file dihapus) -> respawn_failed, panggilan kedua ->
  throttled; (5) stop setelah respawn matikan browser + daemon baru.
  1 kegagalan awal adalah BUG KODE (zombie — di atas); 1 lagi BUG TEST (semua
  test pakai pid sama sehingga throttle bocor antar-test — tiap test kini pid
  sendiri). Regression: P-06 6/6, P-07 14/14, P-12 15/15, P-17 19/19 — PASS.
  `py_compile` OK.
- File: diubah `launcher/injector_daemon.py`, `launcher/launcher.py`,
  `gui/app.py`, `gui/local_api.py`; baru `tests/test_p10_watchdog.py`.

## P-14 — parameter headless di GUI/API/CLI (SELESAI)
- Masalah: headless di-hardcode False di `gui/app.py` api_launch dan
  `gui/local_api.py` browser_start; CLI mendokumentasikan `[--headless]`
  tapi argumennya tidak ada (docstring bohong).
- Perbaikan: `POST /api/profiles/<id>/launch` terima `{"headless": true}`
  (bool atau string "true"/"1"); Local API `GET /api/v1/browser/start`
  terima `?headless=true` (kompatibel AdsPower) + respons kini sertakan
  `headless`; CLI `launch <id> [--headless]` meneruskan param ke Local API
  dan menampilkan "(headless)" di output. Default tetap False = headful.
  CATATAN: toggle headless di halaman GUI (frontend) TIDAK ditambahkan —
  itu perubahan desain GUI (di luar batas fase ini); endpoint-nya sudah
  siap dipakai automation/script.
- Test (`tests/test_p14_headless.py` — BARU; launcher di-stub, plumbing
  param; launch nyata headless sudah dibuktikan P-10/P-17): **11/11 LOLOS**
  — Local API true/1/tanpa-param/0; GUI true/string-true/tanpa-field;
  CLI parse + URL. Regression P-12 15/15 PASS. `py_compile` OK.
- File: diubah `gui/app.py`, `gui/local_api.py`, `antibrowser-cli.py`;
  baru `tests/test_p14_headless.py`.

## P-15 — validasi per-cookie + laporan hasil inject (SELESAI)
- Masalah: daemon memanggil `ctx.add_cookies(SEMUA)` sekali — 1 item invalid
  menggagalkan SEMUA cookies diam-diam; ready.json menghitung jumlah yang
  DICOBA (bukan yang benar-benar masuk); cookie expired / ditolak browser
  tidak pernah ketahuan.
- Perbaikan:
  - **`launcher/injector_daemon.py`:** baru `_validate_cookie()` (name/value
    wajib; domain ATAU url wajib; expires harus angka + belum lewat; sameSite
    harus Strict/Lax/None) + `_inject_cookies()` — inject SATU PER SATU
    (satu jelek tidak menggagalkan yang lain) + VERIFIKASI BACA-BALIK via
    `ctx.cookies()` (Chromium menolak diam-diam cookie expired / SameSite=None
    tanpa Secure). Laporan per cookie ditulis ke
    `browser_profiles/<pid>/cookie_inject_report.json` ({total, ok, failed,
    results: [{name, domain, status: ok/skipped/failed, reason}]}) + ringkasan
    di ready.json (cookies_injected kini = jumlah yang BENAR-BENAR masuk)
    + baris log per kegagalan (alasan kebaca di injector_daemon.log).
  - **`launcher/launcher.py`:** session dict memakai angka ASLI dari laporan
    daemon (cookies_injected/total/failed) — fallback jumlah yang dicoba
    bila laporan tidak ada. Respons GUI launch sudah menyertakan field ini
    otomatis (semua field sesi).
  - **`gui/local_api.py`:** respons browser/start kini sertakan ringkasan
    `"cookies": {"total", "injected", "failed"}`.
- Test (`tests/test_p15_cookies.py` — BARU; unit + E2E launch nyata headless):
  **20/20 LOLOS** — unit: expired/tanpa-domain/bad-sameSite/expires-bukan-angka/
  valid/url-based/session/tanpa-name; E2E 4 cookie (1 valid, 1 expired, 1 tanpa
  domain, 1 SameSite=None tanpa Secure) -> injected=1, total=4, failed=3;
  report berisi status+reason per cookie; cookie valid benar-benar ada di
  browser (baca-balik CDP), 3 jelek tidak ada. Regression: P-10 20/20, P-12
  15/15, P-17 19/19, P-14 11/11 — PASS. `py_compile` OK.
- File: diubah `launcher/injector_daemon.py`, `launcher/launcher.py`,
  `gui/local_api.py`; baru `tests/test_p15_cookies.py`.

## P-18 — RPA sederhana + live fingerprint-check (SELESAI)
- Masalah: helper behavioral_human ada tapi tidak bisa dipakai dari mana pun
  (bukan fitur); tidak ada cara memverifikasi fingerprint yang disuntik
  benar-benar aktif di browser (hanya klaim config).
- Perbaikan:
  - **BARU `launcher/rpa.py`:** `run_steps(port, steps)` — goto/wait/click/
    type/scroll/press di browser yang jalan (CDP); klik/ketik/scroll pakai
    behavioral_human (Bezier + rhythm; fallback Playwright native bila helper
    tak ada); 1 langkah gagal tidak menghentikan run (hasil per langkah +
    ms tercatat; timeout keseluruhan 120 dtk default). `check_fingerprint
    (port, ident)` — baca nilai LIVE dari halaman baru (UA, webdriver,
    timezone+offset, platform, screen, dpr, hw, mem, WebGL renderer,
    canvasHash) dan bandingkan dengan identity profil. Flow store:
    save/list/get/delete alur bernama di `gui/data/rpa_flows.json`
    (lock P-07 via json_store).
  - **`launcher/launcher.py`:** launch kini merekam `identity.json` di
    user_data_dir + baru `get_launched_identity(pid)`. INI WAJIB: profil
    tanpa identity tersimpan mendapat identitas RANDOM tiap
    build_fingerprint_js() dipanggil — check yang membandingkan live vs
    build ULANG memberi FAIL palsu (terbukti di probe: screen/GPU/hw
    "gagal" padahal spoof jalan; dengan identity tercatat semua PASS).
  - **Local API:** `GET /api/v1/browser/fingerprint-check?user_id=`,
    `POST /api/v1/rpa/run` ({user_id, steps} atau {user_id, flow}),
    `GET/POST /api/v1/rpa/flows`, `GET/DELETE /api/v1/rpa/flows/<name>`.
  - **GUI API:** `GET /api/profiles/<pid>/fingerprint-check`,
    `POST /api/profiles/<pid>/rpa`, `GET/POST /api/rpa/flows`,
    `GET/DELETE /api/rpa/flows/<name>`. (Tanpa ubah template/desain GUI.)
  - **CLI:** `fp-check <id>`, `rpa-run <id> [--steps-file F | --flow N]`,
    `rpa-flows`, `rpa-save <nama> --steps-file F`; api_req() kini terima
    timeout (rpa-run: 180 dtk).
  - **Temuan P-18 (DICATAT, bukan diperbaiki di sini):** identitas profil
    tanpa identity tersimpan TIDAK dipertahankan antar launch — tiap launch
    = device "baru" (longitudinal tell). Perbaikan (P2): bekukan identity
    ke profil saat launch pertama. Window sync tetap P2 (setelah P-18).
- Test (`tests/test_p18_rpa.py` — BARU): **43/43 LOLOS** — unit validasi
  (9) + flow store (7) + fp-check live (9: 12 field dibandingkan SEMUA
  PASS, canvasHash stabil antar run) + RPA E2E (9: goto/click/type/
  scroll/wait/press, langkah gagal tidak hentikan run, helper klik/ketik
  terbukti ubah DOM) + API Local+GUI (9: fp-check + rpa/run + flow
  tersimpan; browser mati -> error jelas). 2 bug ketemu saat testing:
  (1) mutate atomic_update harus in-place (salinan dict tidak tersimpan);
  (2) list_flows kembalikan tuple load_json_safe mentah — keduanya
  diperbaiki. Regression: P-10 20/20, P-12 15/15, P-15 20/20, P-14 11/11
  — PASS. `py_compile` OK. Sisa: file `injector_daemon.log` liar di root
  repo (log daemon dari test) dihapus; dir probe p18-* dibersihkan.
- File: baru `launcher/rpa.py`, `tests/test_p18_rpa.py`; diubah
  `launcher/launcher.py`, `gui/local_api.py`, `gui/app.py`,
  `antibrowser-cli.py`.

## P-16 — test suite otomatis + jadwal live stealth V-01–V-04 (SELESAI)
- **Runner `tests/run_all.py`:** jalankan semua `tests/test_*.py`, rangkum
  per file (PASS/FAIL + waktu), exit 1 bila ada gagal; dukung filter
  substring (`run_all.py p10`). Kenali dua format ringkasan (P1
  `=== N PASS, M FAIL ===` + P0 `ALL P-XX TESTS PASS`).
- **Adopsi test P0:** 9 file dari /tmp (`test_p01/02/03/04/05/06/08/11/13`)
  dipindah ke `tests/` (di /tmp mereka hilang saat VM restart).
- **BARU `tests/test_p16_api_contract.py` (19/19):** bentuk respons Local
  API (/status publik, /user/list, /user/create, /browser/start +
  headless + cookies, error shape code -1 + msg) + auth key (401 tanpa/
  salah key, /status tetap publik) + GUI (/api/profiles + injection_ok,
  404, launch, POST lintas-Origin -> 403) + kegagalan RPA tersurface
  sebagai JSON {ok False, error}, bukan crash.
- **BARU `tests/test_p16_consistency.py` (11/11):** profil DENGAN identity
  tersimpan: launch 2x -> identity.json identik, fp-check ok True,
  canvasHash/UA/WebGL/screen sama; dua profil -> identity + canvasHash
  berbeda (UA SAMA itu benar: UA = f(OS, Chrome), bukan per-profil);
  profil TANPA identity tersimpan -> identity BERBEDA tiap launch
  (mendokumentasikan temuan P-18 sebagai KNOWN LIMITATION, P2).
- **BARU `tests/live_stealth_check.py`:** bagian OTOMATIS V-01/V-02 lokal
  (fp-check live 12 field, canvas stabil, vendor/languages/plugins/
  chrome.runtime/UA, webdriver V-02) — hasil 2026-11-07 12:06 WIB:
  **11/11 vektor lolos** (10 PASS + 1 INFO: `'webdriver' in navigator`
  True by design/H3); laporan JSON di `tests/live-reports/` (di-.gitignore).
- **BARU `docs/LIVE-STEALTH-SCHEDULE.md`:** jadwal + prosedur V-01–V-04.
  Otomatis: mingguan Senin 09:00 WIB (baris cron DIUSULKAN, BELUM dipasang
  — butuh kata Gil) + tiap ubah kode fingerprint + sebelum rilis. Manual:
  V-01 eksternal (CreepJS/browserleaks/amiunique), V-02 di CreepJS, V-03
  (reCAPTCHA/iframe), V-04 (GPU mobile vs HP nyata) — tidak bisa cron
  (butuh browser task + internet + perangkat nyata). Batasan jujur: skor
  CreepJS BELUM pernah diukur — jangan klaim lolos sebelum V-01 eksternal.
- **BARU `tests/README.md`:** peta suite per file + cara jalan + catatan.
- **Suite penuh `run_all.py`: 247 PASS, 0 FAIL (19 file)** — P0 50 +
  P1 197. (Angka runner sempat 239 karena parser belum hitung format
  P0 lama "PASS <nama>:" + "PASS 5b:" — diperbaiki, terverifikasi
  p02=4, p03=3, p04=6.)
- **Bug ketemu saat run suite penuh (diperbaiki):** `ensure_injection`
  mencoba respawn untuk sesi tanpa user_data_dir (sesi palsu test P-12)
  -> daemon spawn dengan path relatif di CWD + `injector_daemon.log`
  liar di root repo. Sekarang: bail `no_user_data_dir` bila udd/port
  kosong. Regression pasca-fix: P-12 15/15, P-10 20/20, tanpa log liar.
- File: baru `tests/run_all.py`, `tests/test_p16_api_contract.py`,
  `tests/test_p16_consistency.py`, `tests/live_stealth_check.py`,
  `tests/README.md`, `docs/LIVE-STEALTH-SCHEDULE.md`,
  `tests/test_p01.py`, `tests/test_p02.py`, `tests/test_p03.py`,
  `tests/test_p04.py`, `tests/test_p05.py`, `tests/test_p06.py`,
  `tests/test_p08.py`, `tests/test_p11.py`, `tests/test_p13.py`;
  diubah `launcher/launcher.py` (guard ensure_injection), `.gitignore`.

## Follow-up P-04 — GUI tanpa login penuh (DINILAI: P2, BUKAN P1)
- Keadaan kini (P0, commit e5adb38): Local API key auth default ON (401,
  key via env, /status publik); GUI Origin/Referer-check anti-CSRF +
  MAX_CONTENT_LENGTH 50 MB + bind 127.0.0.1 default + peringatan bila
  bind non-localhost.
- Penilaian: login GUI penuh (manajemen user + penyimpanan password +
  sesi + UI login/logout + brute-force protection) adalah FITUR, bukan
  fix — butuh keputusan desain (single operator password? simpan di mana?
  expiry sesi?). Ancaman sisa sempit: GUI localhost-only; Origin-check
  menahan CSRF browser; yang tidak ditahan = curl langsung bila operator
  sengaja bind 0.0.0.0 (sudah ada peringatan saat start). TIDAK dikerjakan
  di P1. Pemicu naik ke P1/P2-atas: Gil mau ekspos GUI ke LAN / multi-user.
  Dicatat di sini, bukan di kode.
