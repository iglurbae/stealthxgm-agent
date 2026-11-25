# AUDIT STEALTHXGM — FASE 1 (read-only, audit dalem sampe akar)

**Tanggal:** 2026-11-06 (20:04–20:30 WIB)
**Target:** `~/workspace/antibrowser/` — browser antidetect ala-AdsPower
**Perintah eksplisit Gil (2026-11-06 20:03 WIB, verbatim):** "Ini udah detail kaya adspower gw pengen bener2 detail, dan kalo ada koding kita yang kurang atau salah atau apapun itu dia auto fix."
**Aturan yang dipakai:** R46 (tanpa perintah eksplisit jangan jalan — perintah ini eksplisit dari Gil), R48 (audit dalem sampe akar), PENGINGAT Merra to Hermes StealthXGM (Gil 2026-11-06 20:07 WIB, dikoreksi 20:08 WIB — BUKAN aturan bernomor, skema auto-fix: audit vs AdsPower → test otomatis → fixer maks 3x/bug + regression check → re-test loop; pengaman: jangan ubah master/dist langsung, backup sebelum fix, kode kritikal jangan auto-fix tanpa review, semua di-log).
**Remote view:** di-skip dulu (Gil 20:02 WIB) — BUKAN temuan, dicatat sebagai keputusan parkir.
**Yang dilakukan fase ini:** AUDIT ONLY. Tidak ada satu baris kode pun yang diubah. Tidak ada file di `dist/` yang disentuh.

## Metode

- Baca semua modul unik (35 file Python sumber, ~11.800 baris termasuk `vendor/mobile_fingerprint.py` 4.663 baris; di luar itu ada 2 salinan build: `installer/build/src/` dan `installer/deb/` yang ikut diperiksa untuk drift).
- Bandingkan klaim dokumen (`BEDAH-GUIDE.md`, `docs/*.md`, docstring) dengan kode yang benar-benar jalan.
- Verifikasi dengan eksekusi read-only: `compileall` seluruh tree, `python3 gui/fingerprint_gen.py` (self-test bawaan), hitung `len(FEATURE_FLAGS)`, `diff` main-vs-build, `grep` pola (auth, CORS, `extractall`, `except: pass`, `%`-formatting, dead code).
- Yang TIDAK dilakukan (bukan bagian fase 1): launch browser live, uji deteksi (CreepJS/browserleaks), uji GUI di browser, instalasi .deb, dan semua bentuk fix.

## Ringkasan eksekutif

| Angka | Nilai |
|---|---|
| File Python unik (sumber) | 35 file, ~11.803 baris |
| Salinan build (installer/build/src + installer/deb) | ~70 file duplikat |
| Test otomatis yang ada | 1 file (`launcher/test_launcher.py`, 1 skenario, ~10 check, hanya launcher) |
| Temuan KRITIKAL | 0 |
| Temuan PENTING | 18 |
| Temuan MINOR | 22 |
| Butuh verifikasi live (belum terverifikasi) | 5 |
| Klaim dokumen yang terbukti salah / tidak sesuai kode | 5 |

**Verdict:** fondasinya bagus dan jujur (lihat "Yang sudah bagus"), tapi klaim "PC 100% selesai, 14 fitur PASS" hanya benar untuk **pengujian fungsional manual 2026-11-04** — bukan untuk ketahanan stealth, bukan untuk concurrency, bukan untuk keamanan localhost, dan bukan untuk parity AdsPower. Ada **18 temuan PENTING** yang bikin StealthXGM belum "bener2 detail kayak AdsPower", dan yang paling berat bukan fitur yang kurang, melainkan **3 hal yang aktif merugikan**: (1) duplikat profil menyalin identitas fingerprint persis (dua "akun beda" dengan sidik jari sama), (2) preview fingerprint menampilkan identitas yang TIDAK PERNAH dipakai saat launch, dan (3) judul tab `[StealthXGM] <nama profil>` membocorkan nama tool + nama profil ke semua situs. Ditambah **0 test otomatis** di luar 1 skenario launcher dan **stealth yang belum pernah diuji lawan detector sungguhan** (diakui sendiri di `fingerprint_gen.py`).

## Yang sudah bagus (JANGAN dirusak saat fix)

1. **`fingerprint_gen.py` adalah file terbaik di repo.** Punya `assert_consistent()` yang keras, `validate_identity()` untuk mode manual, header "BATASAN (jujur, diukur)" yang mengakui apa yang tidak bisa dilakukan, dan self-test bawaan yang **LOLOS saat audit ini dijalankan** (5 OS × 20 identitas, 0 warning; distribusi tier mobile budget 35 / mid 44 / flagship 21; test negatif mem=16 dan vp>layar ditolak). Pertahankan pola ini sebagai standar semua modul.
2. **Perbaikan audit 2026-11-04 benar-benar ada di kode dan benar:** FIX 1 sinkronisasi `chrome_ver` dengan binary real (`launcher/launcher.py`, `sync_identity_chrome_version`), seed canvas stabil per profil (`_profile_seed`, bukan random per launch), penutup IIFE yang tidak lagi nempel di section `fp_webgpu` (`fingerprint/_core.py`), dan getter bernama + `_mp` untuk toString trap (P0#2).
3. **Penyimpanan rahasia rapi:** `api_config.json` dan `proxy_pools.json` ditulis atomik (tmp + `os.replace`) dengan `chmod 600`. `profiles.json` 660.
4. **Geo-sync adalah keunggulan asli (AdsPower+):** sinkronisasi timezone/locale dari negara IP pool + `geo-check` — AdsPower tidak punya ini seterbuka ini. Sayangnya implementasinya belum lengkap (temuan P-08).
5. **Kejujuran dokumentasi:** `BEDAH-GUIDE.md` bagian "Batasan yang jujur" dan header `fingerprint_gen.py` secara eksplisit menulis keterbatasan (Flask dev server, GUI bind localhost, Chromium tidak dibundel, captcha solver sengaja tidak ada, remote view belum ada). Itu yang bikin audit ini bisa cepat: banyak keterbatasan sudah diakui.
6. **Semua file Python lolos `compileall`** (hanya 1 `SyntaxWarning`, temuan M-20). Tidak ada syntax error di tree manapun.
7. **Artefak build saat ini BERSIH:** `installer/build/src/gui/data/` kosong dan `.deb` tidak mengandung JSON data — tidak ada kredensial live yang ikut ter-packing (tapi pipeline-nya punya lubang, temuan P-13).

---

# TEMUAN PENTING (18)

## P-01 — Duplikat profil menyalin identitas fingerprint persis (dua "akun beda", sidik jari sama)
- **File:** `gui/profiles.py`, `duplicate_profile()` (~baris 330–345)
- **Bukti:** fungsi melakukan `copy.deepcopy(src)` penuh lalu hanya mengganti `id`, `name`, `status`, `deleted`. `fingerprint["identity"]` (UA, GPU, layar, font, dsb.) ikut tersalin verbatim. Seed canvas/audio memang beda karena diturunkan dari profile id baru (`launcher/launcher.py`, `_profile_seed`), tapi identitasnya identik.
- **Dokumen yang salah:** `docs/USER-GUIDE.md:55` — "fingerprint di-generate ulang biar beda". **Tidak benar.** Tidak ada regenerasi.
- **Kenapa masalah:** tujuan duplikat adalah bikin akun kedua yang terlihat sebagai orang/device berbeda. Dengan identitas yang sama, dua profil punya UA + GPU + layar + `platform` + `oscpu` yang identik — korelasi antar-akun jadi gampang. Ini cacat di fitur inti antidetect.
- **Juga:** duplikat ikut menyalin `cookies` (session token!) — dua profil berbagi sesi login yang sama.
- **Fix yang benar:** duplikat harus membersihkan `fingerprint.identity` dan `cookies` (atau regenerate identitas via `generate_random` dengan OS profil), lalu perbaiki USER-GUIDE.

## P-02 — Preview fingerprint menampilkan identitas yang TIDAK PERNAH dipakai saat launch
- **File:** `gui/app.py`, `api_preview()` (~baris 393–400); `gui/local_api.py`, `user_preview()` (~baris 205–216)
- **Bukti:** kedua preview memanggil `generate_random(_osn, ...)` baru setiap kali dan **mengabaikan `fp.get("identity")`** yang tersimpan. Sementara `launcher/launcher.py`, `build_fingerprint_js()` memprioritaskan `identity` tersimpan (`stored = identity_override or fp.get("identity")`). Jadi preview SELALU menampilkan identitas acak yang berbeda dari yang akan dipakai — baik untuk profil yang punya identity tersimpan maupun yang tidak (launch juga generate baru lewat `_consistent_fallback_identity`).
- **Kenapa masalah:** janji fitur ini adalah "preview fingerprint tanpa launch". Pengguna tidak bisa memverifikasi fingerprint apa yang benar-benar akan dipakai. Semua angka di preview (`js_length`, identitas yang ditampilkan) menyesatkan.
- **Fix yang benar:** preview harus memakai identitas yang sama dengan logika launch: `identity` tersimpan kalau ada, kalau tidak ada tampilkan identitas yang AKAN di-generate (dan tandai sebagai "belum tersimpan — akan digenerate saat launch"). Preview juga harus menyertakan `spoof_js_extra` (WebRTC/iframe) supaya `js_length` akurat (saat ini preview hanya memanggil `spoof_js`, bukan `spoof_js_extra`).

## P-03 — Judul tab `[StealthXGM] <nama profil>` membocorkan tool + nama profil ke semua situs
- **File:** `launcher/launcher.py`, `build_fingerprint_js()` (~baris 270–283)
- **Bukti:** JS injeksi menambahkan `MutationObserver` yang mem-prefix SEMUA `document.title` dengan `'[StealthXGM] {name} '`. `document.title` bisa dibaca JavaScript situs mana pun.
- **Kenapa masalah:** ini fitur UX (bedakan jendela antar-profil) yang berubah jadi tell: setiap situs yang dikunjungi langsung tahu (a) user memakai StealthXGM, (b) nama profilnya. Untuk tool antidetect, membocorkan nama tool ke target adalah cacat fatal secara konsep. AdsPower menampilkan nama profil di UI-nya sendiri, bukan di judul halaman.
- **Fix yang benar:** hapus prefix dari `document.title`. Identitas jendela cukup ditampilkan di UI StealthXGM (GUI / judul window OS / brand new-tab page), bukan di dalam halaman web.

## P-04 — GUI (5200) dan Local API (50325) tanpa autentikasi + tanpa proteksi CSRF/CORS
- **File:** `gui/app.py` (seluruh file — tidak ada decorator auth / pengecekan Origin di endpoint mana pun); `gui/local_api.py`, `_check_api_key()` (~baris 38–45, auth opsional, default `API_KEY = ""` = tanpa auth); `gui/gui_launcher.py`; `gui/app.py:698–706` (`STEALTHXGM_HOST` env bisa mengubah bind dari `127.0.0.1` ke `0.0.0.0`).
- **Bukti:** `grep` untuk `CORS|Origin|MAX_CONTENT_LENGTH|csrf|CSRF` di `gui/` dan `launcher/` menghasilkan NOL. Semua endpoint GUI bisa dipanggil siapa saja yang bisa mencapai port: baca/tulis profil, baca proxy (termasuk user/pass — `GET /api/pools` mengembalikan pool lengkap), baca/tulis cookies (session token), upload extension, generate API key baru, hapus profil.
- **Kenapa masalah:** selama bind `127.0.0.1`, ancamannya adalah **CSRF localhost**: situs web apa pun yang dibuka Gil di browser mana pun bisa mengirim request ke `http://127.0.0.1:5200/...` dan menghapus profil / membuat profil / membaca data — tanpa perlu membaca respons (SOP memblokir baca lintas-origin, tapi request-nya tetap jalan). Begitu `STEALTHXGM_HOST=0.0.0.0` dipakai (mis. demi remote view), semua itu terbuka ke jaringan tanpa auth sama sekali.
- **Fix yang benar:** (a) token CSRF/Origin-check di GUI (tolak request yang `Origin`/`Referer`-nya bukan GUI sendiri); (b) Local API key default ON (generate saat first-run, bukan kosong); (c) jangan biarkan GUI bind `0.0.0.0` tanpa auth; (d) `MAX_CONTENT_LENGTH` untuk upload (saat ini tidak ada batas — temuan M-13).

## P-05 — Zip Slip di instalasi extension: `extractall` tanpa validasi member
- **File:** `gui/extension_manager.py:155` (`add_crx`) dan `:185` (`add_zip`) — `z.extractall(tmpdir)` tanpa pemeriksaan nama member.
- **Bukti:** tidak ada sanitasi `../` / path absolut sebelum extract. File `.crx`/`.zip` berbahaya dengan entry `../../...` akan menulis ke luar `tmpdir`.
- **Kenapa masalah:** extension di-install dari upload pengguna atau unduhan Chrome Web Store. Extension berbahaya yang dibagikan di komunitas ("extension wajib buat ...") bisa menulis file arbitrer yang bisa ditulis proses GUI.
- **Terkait:** `_cws_download()` memakai `tempfile.mktemp()` (deprecated, racy, ~baris 205); signature CRX tidak pernah diverifikasi (header hanya dipakai untuk cari offset zip, ~baris 140–150) — CRX yang sudah diutak-atik tetap di-install sebagai unpacked extension tanpa cek tanda tangan.
- **Fix yang benar:** validasi semua member zip sebelum extract (tolak `..` dan path absolut), ganti `mktemp` dengan `mkstemp`, dan tampilkan permission manifest ke pengguna sebelum install.

## P-06 — Launch mengembalikan "already_running" untuk browser yang sudah mati (stuck state)
- **File:** `launcher/launcher.py`, `launch_profile()` (~baris 563–566): `if pid in sessions: return {"already_running": True, ...}` — tanpa pengecekan apakah proses browser/daemon masih hidup.
- **Bukti:** tidak ada liveness check (PID alive / debug port menjawab) sebelum early-return. `sessions.json` hanya dibersihkan oleh `stop_profile()`. Kalau Chromium crash / VM restart / proses di-kill paksa, `sessions.json` tetap berisi entri lama.
- **Kenapa masalah:** setelah crash/restart, profil TIDAK BISA di-launch lagi — selalu dijawab "already_running" — sampai pengguna menghapus `sessions.json` manual atau memanggil stop (yang akan mencoba kill PID basi, temuan P-14). Ini jebakan operasional yang pasti ketemu Gil cepat atau lambat.
- **Fix yang benar:** sebelum early-return, verifikasi `browser_pid` hidup DAN debug port menjawab; kalau tidak, hapus entri basi lalu lanjut launch normal. Tambahkan juga pembersihan sesi basi saat GUI/API start.

## P-07 — Tidak ada file locking: semua JSON store rawan lost-update saat request bersamaan
- **File:** `gui/profiles.py` (`_load`/`_save`), `gui/proxy_pools.py` (`_load`/`_save`), `gui/api_config.py` (`_load`/`_save`), `launcher/launcher.py` (`_read_sessions`/`_write_sessions`).
- **Bukti:** semua memakai pola baca-ubah-tulis (tmp + `os.replace`) tanpa lock. Flask dev server melayani request di thread berbeda; GUI + Local API adalah dua proses berbeda yang menulis `profiles.json` yang sama.
- **Kenapa masalah:** dua create/update/delete yang bersamaan (atau klik Launch ganda) bisa saling menimpa — satu perubahan hilang diam-diam. Untuk launch bersamaan profil yang sama, dua Chromium bisa berebut satu `user-data-dir` (profile lock Chromium akan gagal / corrupt).
- **Fix yang benar:** `fcntl.flock` (Linux) di semua `_load`/`_save` + `_read_sessions`/`_write_sessions`, plus guard "sudah launching" per profil.

## P-08 — Geo-sync tidak memperbarui koordinat geolocation di identity tersimpan
- **File:** `gui/geo_sync.py`, `apply_geo_to_profile_data()` (~baris 140–155) — hanya mengembalikan `{"fingerprint": {"timezone", "locale"}}`.
- **Bukti:** `fingerprint/network.py:41–42` — geolocation spoof memakai `ident.geo_lat || 1.3521` dan `ident.geo_lon || 103.8198` dari **identity tersimpan**. `launcher/launcher.py`, `build_fingerprint_js()` memakai identity tersimpan bila ada. Jadi setelah geo-sync (mis. timezone Jakarta → Singapore), `fingerprint.timezone` berubah tapi `fingerprint.identity.geo_lat/geo_lon` tetap koordinat Jakarta. Hasilnya: timezone bilang Singapore, geolocation bilang Jakarta — mismatch yang persis ingin dicegah geo-sync.
- **Kenapa masalah:** fitur yang diklaim sebagai keunggulan AdsPower+ justru menciptakan inkonsistensi yang dideteksinya gampang, khusus untuk profil yang sudah punya identity tersimpan (yakni semua profil yang pernah di-generate lewat GUI).
- **Fix yang benar:** `apply_geo_to_profile_data` juga harus memperbarui `fingerprint.identity.geo_lat/geo_lon` (atau menghapus identity tersimpan supaya di-generate ulang konsisten). Bonus: default geolocation di `network.py` jangan hardcode Singapore (1.3521, 103.8198) — harus mengikuti timezone.

## P-09 — Proxy dengan autentikasi tidak jalan: kredensial dibuang / tidak ada penanganan auth
- **File:** `launcher/launcher.py`, `_resolve_primary_proxy()` (~baris 320–330) — untuk tipe legacy `http`/`socks5` hanya membangun `f"{scheme}://{host}:{port}"` **tanpa** user/pass; `gui/proxy_pools.py`, `pool_to_proxy_server()` (~baris 240–260) menyertakan kredensial di URL, tapi Chromium modern **mengabaikan kredensial di `--proxy-server`** dan memunculkan dialog auth yang tidak ada yang mengisinya.
- **Bukti:** tidak ada satu pun kode di repo yang menangani proxy auth challenge (tidak ada extension auth, tidak ada `Fetch.enable` + `authChallenge`, tidak ada `webRequest.onAuthRequired`).
- **Kenapa masalah:** pool custom `http`/`socks5` ber-user/pass (yang `proxy_pools.py` sendiri dukung penyimpanannya) akan mentok di dialog auth saat launch — automation diam. Yang jalan hanya `sticky` (proxy-bot lokal, tanpa auth) dan `warp` (tanpa auth). AdsPower menangani proxy auth secara native.
- **Terkait (keamanan):** `pool_to_proxy_server()` menaruh password di URL proxy; URL itu masuk ke argv Chromium (`--proxy-server=...`) sehingga password terlihat lewat `ps aux` / `/proc/<pid>/cmdline` oleh semua user lokal. Hal yang sama terjadi pada API key (`gui/api_config.py`, `start_api()` mengirim `--api-key <key>` di command line).
- **Fix yang benar:** implementasi proxy-auth via extension kecil (MV3 `webRequest.onAuthRequired` dengan kredensial dari pool) atau via CDP `Fetch`; dan JANGAN pernah menaruh kredensial di argv — pakai file/env atau mekanisme CDP.

## P-10 — Daemon injeksi mati = fingerprint hilang diam-diam (tanpa health check)
- **File:** `launcher/launcher.py`, `launch_profile()` (~baris 625–650, hanya cek `daemon.poll()` saat startup); `launcher/injector_daemon.py`, `_run()` (~baris 30–60, `while True: await asyncio.sleep(3600)` tanpa deteksi kematian browser).
- **Bukti:** komentar di kode sendiri mengakui registrasi `addScriptToEvaluateOnNewDocument` **hilang bersama sesi CDP yang mendaftarkannya**. Setelah daemon ready, tidak ada yang memantau daemon lagi. Kalau daemon mati (crash/OOM/kill), browser tetap jalan **tanpa spoofing sama sekali** dan pengguna tidak diberi tahu. Sebaliknya kalau browser mati, daemon tetap hidup selamanya sebagai proses yatim (tidak ada deteksi kematian browser).
- **Kenapa masalah:** ini adalah jalur injeksi SATU-SATUNYA yang aktif (lihat P-17: extension MV3 tidak pernah dipakai). Kegagalan diam-diam di jalur ini = pengguna mengira terlindungi padahal tidak.
- **Fix yang benar:** watchdog: daemon memeriksa koneksi CDP secara berkala dan keluar bila browser mati; launcher/GUI memeriksa daemon hidup lewat PID + `ready_file` (atau endpoint status); bila daemon mati, re-inject atau tandai profil "injeksi mati" di GUI. Bonus: jangan buang stdout/stderr daemon ke DEVNULL (saat ini log crash hilang total).

## P-11 — File JSON corrupt = data hilang diam-diam (tanpa backup, tanpa karantina)
- **File:** `gui/profiles.py`, `_load()` (~baris 62–80) — JSON rusak → `return {}`; save berikutnya **menimpa file corrupt dengan dict kosong** (semua profil hilang). `gui/proxy_pools.py`, `_load()` (~baris 36–55) — JSON rusak / format salah → **re-seed pool bawaan** (semua pool custom hilang). `gui/api_config.py`, `_load()` (~baris 36–50) — config rusak → reset ke default (API key hilang → API jadi tanpa auth tanpa peringatan).
- **Kenapa masalah:** satu kali tulis yang terpotong (mati listrik, disk penuh, crash saat save) bisa menghapus semua profil / pool / API key, tanpa jejak. Tidak ada `.bak`, tidak ada karantina file rusak, tidak ada peringatan ke pengguna.
- **Fix yang benar:** simpan file corrupt ke `<nama>.corrupt-<timestamp>` sebelum reset; buat backup bergilir (`profiles.json.bak`) setiap save; tampilkan peringatan di GUI bila terjadi auto-repair.

## P-12 — Tiga registry sesi yang tidak sinkron (GUI `RUNNING` vs Local API `_sessions` vs `sessions.json`)
- **File:** `gui/app.py`, `RUNNING = {}` (~baris 505); `gui/local_api.py`, `_sessions = {}` (~baris 48); `launcher/launcher.py`, `SESSIONS_FILE` + `_read_sessions`/`_write_sessions` (~baris 480–500).
- **Bukti:** `GET /api/v1/browser/active` membaca `_sessions` milik proses Local API — bila browser di-launch lewat GUI, Local API menjawab "Inactive" padahal browser jalan. `GET /api/v1/status` melaporkan `running_profiles = len(_sessions)` — salah bila launch lewat GUI/CLI. `status` di `profiles.json` juga tidak pernah direkonsiliasi (set `running` saat launch, `idle` saat stop; crash → status basi selamanya).
- **Kenapa masalah:** status adalah sumber kebenaran untuk automation merra dan untuk GUI Gil. Tiga sumber yang bisa berbeda = keputusan yang salah (launch ganda, stop yang tidak berefek, laporan palsu).
- **Fix yang benar:** satu sumber kebenaran: `sessions.json` + liveness check (PID hidup + debug port menjawab). GUI dan Local API hanya membaca/menulis lewat fungsi launcher yang sama.

## P-13 — Pipeline build bisa membocorkan kredensial live ke installer (lubang laten)
- **File:** `installer/build-copy.sh` (rsync tanpa `--exclude 'gui/data/'`, ~baris 15–22) dan `installer/build-deb.sh` (menyalin seluruh `build/src` ke stage `.deb`).
- **Bukti:** artefak saat ini BERSIH (terverifikasi: `installer/build/src/gui/data/` kosong; `.deb` tidak mengandung JSON data). Tapi `gui/data/` di tree kerja SAAT INI berisi `profiles.json`, `proxy_pools.json` (password proxy), dan `api_config.json` (API key). Rebuild hari ini akan menyalin semuanya ke installer.
- **Kenapa masalah:** satu kali rebuild yang lupa akan mem-packing kredensial proxy + API key ke dalam zip/.deb yang dibagikan. Ini kebocoran kredensial lewat jalur build.
- **Fix yang benar:** tambahkan `--exclude 'gui/data/'` (dan `--exclude 'browser_profiles/'` sudah ada) di `build-copy.sh`; tambahkan smoke-test pasca-build yang memastikan tidak ada `*.json` data di stage; pertimbangkan memindahkan data live keluar dari tree source.

## P-14 — Headless tidak bisa diakses dari GUI / Local API / CLI (padahal engine mendukung)
- **File:** `gui/app.py`, `api_launch()` — `launch_profile(p, headless=False, ...)` hardcode; `gui/local_api.py`, `browser_start()` — `launch_profile(p, headless=False)` hardcode; `antibrowser-cli.py` — docstring menjanjikan `launch <id> [--headless]` tapi parser TIDAK punya argumen `--headless` (perintah itu gagal `unrecognized arguments`).
- **Kenapa masalah:** automation (merra) dan pengujian tidak bisa menjalankan browser headless lewat jalur resmi mana pun. AdsPower mendukung parameter headless di Local API. Satu-satunya jalan adalah memanggil Python langsung.
- **Fix yang benar:** tambahkan parameter `headless` di `GET /api/v1/browser/start`, `POST /api/profiles/<id>/launch`, dan argumen `--headless` di CLI (serta perbaiki docstring CLI).

## P-15 — Cookie import bisa gagal total secara diam-diam (all-or-nothing)
- **File:** `launcher/injector_daemon.py`, `_run()` (~baris 38–48): `await ctx.add_cookies(cookies)` dibungkus `except Exception: pass` — satu cookie tidak valid (mis. tanpa `domain`/`url`, atau `sameSite: "None"` tanpa `secure=True` yang diwajibkan Playwright) membuat SELURUH panggilan gagal dan SEMUA cookie batal di-inject, tanpa log.
- **Bukti:** `launcher/launcher.py`, `sanitize_cookies()` (~baris 455–480) tidak menjamin `domain`/`url` ada dan tidak memaksa `secure=True` saat `sameSite == "None"`.
- **Kenapa masalah:** fitur cookie import/export (yang AdsPower punya) jadi tidak bisa diandalkan: pengguna mengira sesi sudah di-inject padahal tidak ada satu pun cookie yang masuk.
- **Fix yang benar:** validasi per-cookie sebelum inject (buang yang tidak valid + laporkan), paksa `secure=True` untuk `sameSite=None`, dan log jumlah cookie yang berhasil/gagal ke `ready_file`/GUI.

## P-16 — Tidak ada test otomatis (kecuali 1 skenario launcher) dan stealth belum pernah diuji lawan detector
- **File:** seluruh repo — satu-satunya test adalah `launcher/test_launcher.py` (1 skenario: launch headless → cek `webdriver` falsy + UA → stop; ~10 check). Tidak ada test untuk GUI API, profiles, proxy pools, `fingerprint_gen` (kecuali self-test manual yang tidak terhubung ke runner), Local API contract, extension manager, batch import, geo-sync, maupun konsistensi fingerprint.
- **Bukti:** `find` test file hanya mengembalikan `test_launcher.py` (plus salinannya di installer). Tidak ada `pytest`/`unittest` runner, tidak ada CI. Klaim "14 fitur PASS" adalah pengujian manual 2026-11-04, bukan regresi otomatis.
- **Bukti kedua (lebih berat):** `gui/fingerprint_gen.py` header secara jujur menulis: "deteksi nyata belum pernah diuji terhadap CreepJS/dsb." dan "Mobile GPU renderer adalah APROKSIMASI ... Belum pernah dibandingkan dengan getParameter() perangkat nyata." Jadi klaim stealth-nya belum terbukti terhadap SATU PUN detector sungguhan.
- **Kenapa masalah:** ini yang paling menghambat tujuan Gil "bener2 detail kayak AdsPower": AdsPower teruji di lapangan melawan detector. Tanpa test otomatis, setiap fix berisiko merusak yang sudah jalan tanpa ketahuan; tanpa uji detector, "antidetect" hanya klaim.
- **Fix yang benar (sesuai PENGINGAT poin 2):** suite test otomatis — unit (profiles/pools/fingerprint_gen/geo_sync/extension_manager), integration (GUI + Local API contract, termasuk contoh AdsPower), fingerprint consistency (1000 identitas acak, 0 warning — sudah ada polanya di self-test `fingerprint_gen.py`), dan uji stealth live (CreepJS / browserleaks / amiunique) sebagai test manual terjadwal. Test harus jalan tiap perubahan kode (bukan manual).

## P-17 — Kode injeksi extension MV3 sudah jadi tapi TIDAK PERNAH dipakai (jalur injeksi hanya daemon)
- **File:** `launcher/extension_builder.py`, `build_extension()` (lengkap, 41 baris) — NOL pemanggil di seluruh repo (hanya disebut di komentar `launcher/launcher.py:551`). `launcher/launcher.py`, `_connect_and_inject()` (~baris 543) juga dead code (nol pemanggil).
- **Bukti:** `grep` untuk `extension_builder|build_extension` di luar definisi hanya mengembalikan komentar. `BEDAH-GUIDE.md` mengklaim injeksi via "persistent MV3 extension" — **tidak sesuai kode**; yang aktif hanya injector daemon.
- **Kenapa masalah:** (a) dokumentasi menyesatkan; (b) ada jalur injeksi yang lebih robust (extension persisten, tidak tergantung sesi CDP) yang sudah ditulis tapi tidak dimanfaatkan — padahal kelemahan daemon (P-10) persis yang diselesaikan extension. Catatan jujur: `docs/RND-EXTENSIONS.md:57` mencatat MV3 content script TIDAK jalan di `--headless=new`, jadi extension bukan pengganti daemon untuk headless — tapi untuk mode headful ia adalah lapisan kedua yang berharga.
- **Fix yang benar:** putuskan arsitektur injeksi secara eksplisit (daemon saja + dokumentasi diperbaiki, ATAU daemon + extension sebagai lapisan ganda untuk headful), hapus atau sambungkan dead code, dan perbaiki BEDAH-GUIDE.

## P-18 — Fitur AdsPower yang tidak ada: RPA/automation flow, window sync, dan fingerprint-check live
- **Bukti:** `grep` seluruh repo untuk RPA/flow/sync-window tidak menghasilkan fitur pengguna. Yang ada hanya helper library `fingerprint/behavioral_human.py` (gerak mouse/ketik/scroll manusiawi) yang harus dipanggil dari kode Python sendiri — bukan fitur otomasi yang bisa dipakai Gil dari GUI.
- **Yang tidak ada (dibanding AdsPower):**
  - **RPA / automation flow builder** — AdsPower punya perekam + eksekutor alur (klik, isi form, tunggu). StealthXGM: tidak ada UI maupun API untuk menjalankan alur.
  - **Window synchronization** — AdsPower bisa menyinkronkan aksi (klik/scroll/ketik) ke banyak jendela sekaligus. StealthXGM: tidak ada.
  - **Fingerprint-check live** — AdsPower punya pengecekan fingerprint bawaan. StealthXGM hanya punya preview (panjang JS + identitas) — dan preview itu pun menampilkan identitas yang salah (P-02). Tidak ada pengecekan terhadap detector nyata.
  - **Cloud sync / tim** — AdsPower punya (berbayar). StealthXGM lokal saja — ini perbedaan scope yang sah, bukan bug; dicatat supaya ekspektasi jelas.
  - **Captcha solver** — sengaja tidak dibangun (keputusan Gil, dicatat di BEDAH-GUIDE). Bukan temuan; parity dengan AdsPower yang juga tidak membundel solver.
- **Fix yang benar:** RPA sederhana (jalankan skrip langkah dari GUI/API memakai helper `behavioral_human` yang sudah ada) adalah nilai tambah terbesar berikutnya setelah P-01–P-16; window sync dan fingerprint-check live sesudahnya. Remote view tetap di-skip (keputusan Gil 20:02 WIB).

---

# TEMUAN MINOR (22)

## M-01 — Klaim "47 teknik fingerprint" tidak berdasar (aslinya 29)
- **Bukti:** `docs/API.md:37` dan `gui/local_api.py:16,193` menyebut "47 teknik fingerprint", tapi `gui/profiles.py` mendefinisikan `FEATURE_FLAGS` = **29 flag** (terverifikasi dengan eksekusi: `len(FEATURE_FLAGS) == 29`), dan endpoint `GET /api/v1/features` mengembalikan `total: 29`. `docs/FINGERPRINT-FLAGS.md:1` sendiri berjudul "29 Flag Fingerprint". Tidak ada daftar 47 di mana pun.
- **Fix:** samakan angka (29 flag yang bisa di-toggle) di semua tempat, atau dokumentasikan dari mana angka 47 berasal.

## M-02 — Docstring Local API menjanjikan endpoint cookie yang tidak ada
- **Bukti:** `gui/local_api.py:14–16` mendokumentasikan `POST /api/v1/user/<id>/cookies — cookie import`, tapi tidak ada route itu di file. Cookie import/export hanya ada di GUI (`gui/app.py`, `/api/profiles/<pid>/cookies`).
- **Fix:** implementasikan endpoint-nya (AdsPower punya cookie management via API) atau hapus dari docstring.

## M-03 — `_launcher()` mengeksekusi ulang `launcher.py` di setiap panggilan
- **File:** `gui/app.py` (~baris 520–530) dan `gui/local_api.py` (~baris 70–78) — `importlib.util.spec_from_file_location` + `exec_module` di setiap launch/stop.
- **Dampak:** (a) lambat (import ulang Playwright dkk. setiap panggilan); (b) state modul (`_PROCS`, cache versi Chrome) selalu kosong di proses GUI/API — jadi jalur stop "in-process" di `launcher.py` tidak pernah terpakai dari GUI/API, selalu jatuh ke kill-by-PID.
- **Fix:** import launcher sekali sebagai modul biasa.

## M-04 — `batch_assign_pool` selalu menulis `type: "sticky"` (termasuk saat pool dikosongkan)
- **File:** `gui/profiles.py`, `batch_assign_pool()` (~baris 310–325): `proxy = {"pool_id": pool_id or None, "type": "sticky", ...}`.
- **Dampak:** menghapus pool dari profil (pool_id kosong) tetap meninggalkan `type: "sticky"` → profil jatuh ke proxy-bot padahal pengguna bermaksud melepas proxy. Juga: tipe pool asli (mis. socks5) tidak pernah tercermin di field `type`.
- **Fix:** `type` harus mengikuti tipe pool yang dipilih, atau `"none"` bila pool dikosongkan.

## M-05 — `stealthxgm_main.py` runtime-patch tidak lengkap (build beku/PyInstaller)
- **File:** `installer/stealthxgm_main.py` (~baris 55–70): loop patch hanya menangani `PROFILES_FILE`, `POOLS_FILE`, `CONFIG_FILE`, `EXTENSIONS_FILE`, `PROFILE_EXTENSIONS_FILE`.
- **Bukti:** `extension_manager.py` tidak punya atribut `EXTENSIONS_FILE`/`PROFILE_EXTENSIONS_FILE` — ia memakai `EXT_DB`/`ASSIGN_DB` yang dihitung saat import dari `DATA_DIR` lama, jadi **tidak ikut pindah** ke user data dir. `api_config.py` punya `PID_FILE` yang juga tidak ada di daftar — PID file API tetap di tree install.
- **Dampak:** pada build beku, data extension dan PID file API tersebar di dua lokasi; bila direktori install read-only (`/opt/stealthxgm`), operasi extension gagal.
- **Catatan:** jalur `.deb` aman dari ini karena `patch-copy.py`/`build-copy.sh` menambal baris `DATA_DIR` di file hasil copy (bukan runtime). Jadi temuan ini khusus jalur PyInstaller/frozen. Perbaiki loop patch (tambahkan `PID_FILE`, `EXT_DB`, `ASSIGN_DB`) atau samakan penamaan konstanta.

## M-06 — `validate_identity()` lebih lemah dari `assert_consistent()` (mode manual bisa menyimpan identitas inkonsisten tanpa warning)
- **File:** `gui/fingerprint_gen.py` — `validate_identity()` tidak memeriksa: `screen_w/h` di luar pool `SCREENS`, `dpr` yang tidak cocok dengan layar, `hw` di luar pool `HWS`, dan `vp` vs layar untuk desktop (yang itu hanya ada di `assert_consistent()`).
- **Dampak:** GUI menampilkan "konsisten" untuk identitas manual yang sebenarnya inkonsisten, lalu launcher memakainya apa adanya.
- **Fix:** samakan cakupan `validate_identity` dengan invarian `assert_consistent` (atau panggil assert yang sama dan ubah hasilnya jadi warning).

## M-07 — Peta timezone→locale tidak lengkap (27 zona; sisanya jatuh ke `en-US`)
- **File:** `fingerprint/_core.py`, `spoof_js()` (~baris 30–55): peta `_tz_to_locale` hanya ~27 zona. Zona lain (mis. `Europe/Warsaw` → harusnya `pl-PL`) jatuh ke `en-US` — locale yang tidak cocok dengan negara timezone.
- **Fix:** lengkapi peta dari `_COUNTRY_GEO` (sudah ada datanya) daripada hardcode.

## M-08 — `navigator.webdriver` di-spoof lewat getter di prototype (tell yang bisa dideteksi)
- **File:** `fingerprint/navigator.py`, `section_webdriver_remove()` (~baris 50–66): `Object.defineProperty(Navigator.prototype, 'webdriver', {get: ...})`.
- **Fakta kode (terverifikasi):** property `webdriver` menjadi ADA di rantai prototype (mengembalikan `false`). Di Chrome asli yang tidak terotomasi, `'webdriver' in navigator` adalah `false` — property itu tidak ada sama sekali.
- **Status deteksi: BELUM TERVERIFIKASI** — belum pernah diuji lawan CreepJS/detector (lihat P-16). Yang terverifikasi adalah mekanismenya; apakah detector memanfaatkan celah ini perlu uji live.
- **Fix yang benar:** jangan definisikan ulang property-nya — cukup hapus (`delete navigator.webdriver`) sehingga `'webdriver' in navigator` tetap `false` seperti browser asli. Uji ulang lawan CreepJS setelah diubah.

## M-09 — Spoofed object ber-prototype polos (tell potensial, belum terverifikasi)
- **Contoh:** `fingerprint/navigator.py`, `section_client_hints()` — `userAgentData` di-spoof sebagai object polos; `Object.prototype.toString.call(navigator.userAgentData)` menghasilkan `"[object Object]"`, bukan `"[object NavigatorUAData]"` seperti aslinya.
- **Status: BELUM TERVERIFIKASI** (butuh uji CreepJS). Dicatat sebagai risiko, bukan vonis.
- **Juga:** `platformVersion` Mac di-hardcode `'14.5.0'` (~baris 200) tanpa mengikuti versi macOS di identitas.

## M-10 — Iframe patch bisa merusak situs asli (termasuk CAPTCHA)
- **File:** `fingerprint/stealth_extra.py`, `spoof_js_iframe_patch()`: `window.length` dipaksa `0`, `frameElement` dipaksa `null`, `window.top`/`window.parent` dipaksa `window` — di SEMUA frame (add_init_script jalan di semua frame).
- **Dampak:** situs yang memakai iframe (payment, embed, dan iframe CAPTCHA seperti reCAPTCHA/hCaptcha) bisa rusak perilakunya. Flag ini ON secara default (semua flag default ON, `gui/profiles.py`).
- **Status: BELUM TERVERIFIKASI** di situs nyata — perlu uji live (buka halaman dengan reCAPTCHA + iframe). Bila terbukti merusak, flag ini harus default OFF atau dibuat per-situs.
- **Terkait:** `availHeight = screen_h - 40` di `fingerprint/screen.py` mengasumsikan taskbar 40px di semua OS (macOS/Linux berbeda).

## M-11 — Tidak ada validasi input di mana-mana (profil, pool, timezone, CSV/JSON)
- **Contoh:** `gui/profiles.py`, `create_profile()` menerima nama kosong/duplikat dan `fingerprint`/`proxy` apa pun tanpa validasi skema; `gui/proxy_pools.py`, `create_pool()` tidak memvalidasi format host/port; timezone apa pun diterima (`"Mars/Olympus"` akan tersimpan lalu `Intl.DateTimeFormat` dengan timezone invalid melempar `RangeError` ke kode situs); `gui/batch_import.py` tidak membatasi jumlah baris (CSV 10.000 baris = 10.000× rewrite JSON penuh, O(n²)).
- **Juga:** `gui/batch_import.py`, `PLATFORMS` tidak memuat `"ios"` — batch import menolak platform iOS padahal GUI mendukungnya.
- **Fix:** validasi skema di `create_profile`/`update_profile`/`create_pool`, validasi timezone terhadap daftar IANA/`_COUNTRY_GEO`, dan batas baris import.

## M-12 — PID-reuse hazard di `stop_profile` / `stop_api`
- **File:** `launcher/launcher.py`, `stop_profile()` (~baris 645–670) dan `gui/api_config.py`, `stop_api()` (~baris 180–200): membunuh berdasarkan PID dari file tanpa memverifikasi PID itu masih milik proses yang dimaksud.
- **Dampak:** bila proses sudah mati dan PID-nya dipakai ulang proses lain, `SIGTERM`/`SIGKILL` mengenai proses yang salah. Probabilitas kecil, dampak besar.
- **Fix:** verifikasi `/proc/<pid>/cmdline` mengandung nama yang diharapkan sebelum kill.

## M-13 — Tidak ada batas ukuran upload / rate limit
- **Bukti:** tidak ada `app.config["MAX_CONTENT_LENGTH"]` di `gui/app.py` maupun `gui/local_api.py`; `add_crx()` membaca seluruh file ke memori (`data = f.read()`); import CSV/JSON tanpa batas ukuran.
- **Fix:** set `MAX_CONTENT_LENGTH` (mis. 50 MB) dan batas baris import.

## M-14 — Kredensial di plaintext di dalam direktori profil browser
- **File:** `launcher/launcher.py`, `launch_profile()` — menulis `fingerprint_inject.js` dan `profile_cookies.json` (cookie sesi plaintext) ke dalam `browser_profiles/<id>/`; tidak dihapus saat stop.
- **Dampak:** siapa pun yang bisa membaca filesystem bisa mengambil semua cookie sesi. (Risiko lokal; di mesin single-user kecil, tapi cookie adalah aset paling berharga di tool ini.)
- **Fix:** hapus `profile_cookies.json` saat stop (atau simpan cookie hanya di memori daemon), dan pertimbangkan enkripsi at-rest untuk cookie.

## M-15 — `profiles.json` 660 berisi cookie plaintext
- **Terkait M-14:** cookie sesi tersimpan di `profiles.json` (mode 660 — bisa dibaca grup). `api_config.json`/`proxy_pools.json` sudah 600; `profiles.json` sebaiknya juga 600.
- **Fix:** samakan ke 600 di `_save()`.

## M-16 — `update_pool` punya kode mati + inkonsistensi boolean
- **File:** `gui/proxy_pools.py`, `update_pool()` (~baris 170–185): loop `for key in ("name","host","user","pass","country","notes","active")` berisi ternary `if key != "port"` yang tidak pernah benar (karena `"port"` tidak ada di tuple); `active` disimpan mentah saat update tapi di-`bool()` saat create.
- **Fix:** bersihkan dead code, samakan koersi boolean.

## M-17 — `test_pool` memakai `http://ip-api.com` (HTTP polos)
- **File:** `gui/proxy_pools.py`, `test_pool()` (~baris 263–293): request HTTP (bukan HTTPS) ke pihak ketiga untuk cek IP — membocorkan IP (asli/proxy) ke ip-api.com dan rentan MITM.
- **Fix:** pakai `https://` (ip-api mendukung HTTPS untuk endpoint ini) atau endpoint cek IP lain via HTTPS.

## M-18 — Test meninggalkan sampah di data live
- **Bukti:** `gui/data/profiles.json` saat ini berisi 2 profil bernama `launcher-test` (keduanya di trash, dari 2026-11-04) karena `launcher/test_launcher.py` memakai `pm.delete_profile()` (soft delete) bukan permanent delete. `browser_profiles/` berisi 26 direktori dari pengujian 2026-11-04 (termasuk `p0live`, `p0verify`, dan satu direktori kosong `fe6f1dc5aef2`, 0 byte — kemungkinan create yang gagal).
- **Fix:** test harus memakai permanent delete + cleanup direktori profilnya; dan bersihkan sisa ini sekali.

## M-19 — Inkonsistensi kecil antar-registry dan default
- `launch_profile` default `headless=False`, tapi `launcher.py:main()` memakai `headless=not args.headful` (default headless=True untuk CLI). Dua default berlawanan.
- `user_list` di `gui/local_api.py` — `int(request.args.get("page", 1))` tanpa try/except: `?page=abc` → 500.
- `user_create` Local API hanya memetakan 4 field (`name`, `group`, `fingerprint`, `proxy`) — field AdsPower lain (username, cookie, dsb.) diabaikan diam-diam. `user/list` tidak mendukung filter `group_id` seperti AdsPower.
- `profiles.py`, `_remove_browser_data()` memakai path relatif terhadap `__file__`, bukan `STEALTHXGM_PROFILES_DIR` (env) — inkonsisten bila env override dipakai.
- CLI `cmd_status` memakai `running_profiles` dari `_sessions` Local API (lihat P-12) sehingga angkanya bisa salah.

## M-20 — `SyntaxWarning: invalid escape sequence '\s'` di `canvas_audio.py:261`
- **Bukti:** `compileall` mengeluarkan warning ini di ketiga salinan (main, build/src, deb). Penyebab: `\s` di dalam string biasa (bukan raw string) di sekitar `section_webgpu()`.
- **Dampak:** saat ini tidak fungsional (Python memperlakukannya sebagai literal), tapi Python berencana menjadikannya `SyntaxError` di versi mendatang.
- **Fix:** jadikan raw string atau escape ganda.

## M-21 — Tidak ada version control (`.git` tidak ada) dan tidak ada auto-update
- **Bukti:** tidak ada direktori `.git` di tree; tidak ada satu pun referensi auto-update di kode/dok. Satu-satunya snapshot adalah `dist/StealthXGM-installer-2026-11-05.zip`.
- **Dampak:** tidak ada riwayat perubahan, tidak bisa rollback per-commit, tidak bisa membedakan versi saat bug dilaporkan. Auto-update sudah dicatat sebagai "sisa" pekerjaan — tetap dicatat di sini supaya masuk rencana fix.
- **Fix:** `git init` + commit baseline sebelum FASE 2 (pengaman R50: backup sebelum fix), lalu auto-update sederhana (cek versi → unduh → verifikasi hash).

## M-22 — Direktori kosong dan dead weight
- `captcha/` kosong (0 file) — captcha solver sengaja tidak dibangun; direktori kosong membingungkan (hapus atau beri README yang menjelaskan keputusan).
- `network/` kosong (0 file) — tidak ada isinya; hapus atau isi.
- `extensions/` kosong (0 file) — wajar (library mulai kosong), tapi `docs/EXTENSIONS.md` tidak menjelaskan bahwa library mulai kosong.
- `vendor/mobile_fingerprint.py` (4.663 baris) adalah modul Gmail-signup yang dipakai ulang; header-nya masih bicara soal Gmail risk score. Fungsional (dipakai `fingerprint/mobile_devices.py` via importlib, tanpa fallback bila file hilang/rusak — `_load_vendor_profiles()` tidak punya try/except). Rapikan provenance-nya dan tambahkan fallback.

---

# BELUM TERVERIFIKASI (butuh uji live — JANGAN ditebak, JANGAN di-fix buta)

| # | Yang belum diketahui | Cara memverifikasi |
|---|---|---|
| V-01 | Apakah detector nyata (CreepJS, browserleaks, amiunique) mendeteksi StealthXGM? | Jalankan 1 profil di browserleaks/CreepJS, catat skor + field yang bocor |
| V-02 | Apakah `navigator.webdriver` di prototype (M-08) benar-benar terdeteksi? | Cek `'webdriver' in navigator` + `getOwnPropertyDescriptor(Navigator.prototype, 'webdriver')` di CreepJS |
| V-03 | Apakah iframe patch (M-10) merusak reCAPTCHA/hCaptcha/iframe payment? | Buka halaman dengan reCAPTCHA + iframe payment di profil dengan flag ON vs OFF |
| V-04 | Apakah string renderer GPU mobile cocok dengan perangkat nyata? | Bandingkan `getParameter(UNMASKED_RENDERER_WEBGL)` hasil spoof dengan perangkat Android/iOS nyata (diakui di `fingerprint_gen.py`) |
| V-05 | Apakah `.deb` terinstal dan jalan di mesin bersih? | Instal di VM/container bersih, first-run (unduh Chromium ~170MB), launch 1 profil |

---

# PERBANDINGAN FITUR vs ADSPOWER

> Kolom AdsPower berdasarkan pengetahuan umum tentang fitur AdsPower yang dipublikasikan (belum diverifikasi live ke situs AdsPower — bila ada yang keliru, koreksi dari dokumentasi resmi). Kolom StealthXGM berdasarkan kode yang dibaca di audit ini.

| Fitur AdsPower | Ada di StealthXGM? | Catatan |
|---|---|---|
| Multi-profil (tanpa batas) | ✅ Ya | CRUD + grup + trash/restore + duplikat |
| Fingerprint per profil (dapat diubah) | ✅ Ya (29 flag) | 29 flag toggleable; klaim "47 teknik" salah (M-01) |
| Generator identitas konsisten | ✅ Ya (lebih baik) | `assert_consistent` + validasi; tapi preview menampilkan identitas yang salah (P-02) |
| Proxy per profil | ✅ Ya | Sticky/WARP/HTTP/SOCKS5; tapi auth proxy tidak jalan (P-09) |
| Proxy checker | ✅ Ya | `test_pool` via ip-api; tapi HTTP polos (M-17) |
| Geo-sync timezone/locale dari IP | ✅ Ya (AdsPower+) | Keunggulan asli; tapi tidak update geo_lat/lon identity tersimpan (P-08) |
| Local API (kompatibel AdsPower) | ⚠️ Sebagian | Endpoint inti ada; tanpa `headless` param (P-14), tanpa endpoint cookie yang dijanjikan (M-02), tanpa filter grup; `_sessions` tidak sinkron (P-12) |
| Cookie import/export | ⚠️ Sebagian | Ada di GUI; gagal total diam-diam bila 1 cookie invalid (P-15); tidak ada di Local API |
| Extension manager | ✅ Ya | Library + assignment per profil; tapi Zip Slip (P-05), tanpa verifikasi tanda tangan CRX |
| Batch import (CSV/JSON) | ✅ Ya | Bagus; tapi tolak `ios` (M-11), tanpa batas baris |
| Batch operations | ✅ Ya | Delete/move group/assign pool; tapi assign pool hardcode `sticky` (M-04) |
| CLI | ⚠️ Sebagian | Hanya list/create/launch/stop/delete/status/api-start/api-stop; docstring janji `--headless` yang tidak ada (P-14) |
| RPA / automation flow | ❌ Tidak ada | Hanya helper library `behavioral_human.py`; tidak ada UI/API untuk menjalankan alur (P-18) |
| Window synchronization | ❌ Tidak ada | Tidak ada di kode mana pun (P-18) |
| Fingerprint-check live | ❌ Tidak ada | Hanya preview panjang JS; tidak ada uji lawan detector (P-16, P-18) |
| Headless mode | ⚠️ Engine ya, interface tidak | `launcher` mendukung; GUI/API/CLI mengunci headful (P-14) |
| Remote view / cloud browser | ❌ Tidak ada | **Di-skip atas keputusan Gil (20:02 WIB)** — bukan temuan |
| Cloud sync / tim | ❌ Tidak ada | Perbedaan scope yang sah (lokal saja); dicatat |
| Captcha solver | ❌ Tidak ada (sengaja) | Keputusan Gil; parity dengan AdsPower (juga tidak membundel) |
| Auto-update | ❌ Tidak ada | Sisa pekerjaan yang sudah dicatat (M-21) |
| Branding (ikon, new-tab) | ✅ Ya | Brand extension + ikon; tapi title-prefix membocorkan tool (P-03) |

---

# RENCANA FIX DIPRIORITASKAN (untuk FASE 2 — belum dieksekusi)

Pengaman FASE 2 (dari PENGINGAT): `git init` + commit baseline dulu; backup sebelum fix; jangan ubah `dist/` langsung (rebuild dari source); kode kritikal (injeksi, auth, proxy) jangan auto-fix tanpa review; tiap fix ≤3 percobaan lalu lapor; regression check tiap fix; semua di-log.

## P0 — Perbaiki dulu (merusak fungsi inti / keamanan / stealth)
1. **P-01** duplikat profil: bersihkan/regenerate `identity` + `cookies` saat duplikat; perbaiki USER-GUIDE.
2. **P-03** hapus prefix `[StealthXGM]` dari `document.title`.
3. **P-02** preview harus menampilkan identitas yang benar-benar akan dipakai saat launch.
4. **P-04** auth + Origin-check GUI, API key default ON, `MAX_CONTENT_LENGTH`.
5. **P-05** Zip Slip: validasi member zip; ganti `mktemp`; tampilkan permission manifest.
6. **P-06** liveness check sebelum `already_running`; bersihkan sesi basi saat start.
7. **P-08** geo-sync harus update `geo_lat`/`geo_lon` di identity tersimpan (atau hapus identity).
8. **P-11** backup + karantina file JSON corrupt (jangan reset diam-diam).
9. **P-13** `build-copy.sh`: exclude `gui/data/` + smoke-test pasca-build (tidak ada kredensial di stage).

## P1 — Penting (keandalan, parity AdsPower)
10. **P-07** file locking (`fcntl.flock`) di semua JSON store + guard launching per profil.
11. **P-09** proxy-auth (extension auth / CDP Fetch) + jangan taruh kredensial di argv (API key juga).
12. **P-10** watchdog daemon injeksi (health check + re-inject + log tidak dibuang ke DEVNULL).
13. **P-12** satu registry sesi (`sessions.json` + liveness) untuk GUI/API/CLI.
14. **P-14** parameter `headless` di GUI/API/CLI.
15. **P-15** validasi per-cookie + laporan hasil inject.
16. **P-16** suite test otomatis (unit + integration + API contract + fingerprint consistency) + jadwal uji stealth live (V-01–V-04).
17. **P-17** putuskan arsitektur injeksi (daemon saja vs daemon+extension), hapus/sambungkan dead code, perbaiki BEDAH-GUIDE.
18. **P-18** RPA sederhana (pakai `behavioral_human` yang sudah ada) + fingerprint-check live; window sync sesudahnya.

## P2 — Minor / higiene (kerjakan sesudah P0–P1)
19. **M-01, M-02** samakan dokumentasi (29 bukan 47; endpoint cookie diimplementasi atau dihapus dari docstring).
20. **M-03** import launcher sekali (bukan exec ulang per panggilan).
21. **M-04, M-16, M-20** perbaikan kecil (batch_assign_pool, dead code update_pool, SyntaxWarning `\s`).
22. **M-05** lengkapi runtime-patch `stealthxgm_main.py` (`PID_FILE`, `EXT_DB`, `ASSIGN_DB`).
23. **M-06, M-07, M-09, M-10** perkuat validator + lengkapi peta locale + uji iframe patch live (V-03).
24. **M-11–M-15, M-17, M-19** validasi input, PID-reuse check, batas upload, hapus cookie file saat stop, `profiles.json` ke 600, HTTPS untuk ip-api.
25. **M-18, M-21, M-22** bersihkan data test, `git init`, hapus/beri README direktori kosong, rapikan provenance vendor.

## Yang TIDAK masuk rencana fix (keputusan Gil / scope sah)
- Remote view — di-skip (Gil 20:02 WIB).
- Captcha solver — sengaja tidak dibangun.
- Cloud sync / tim — di luar scope (lokal saja).

---

# LAMPIRAN

## File yang diaudit (sumber unik)
- `antibrowser-cli.py` (185 baris)
- `fingerprint/` — `_common.py`, `_core.py`, `behavioral.py`, `behavioral_human.py`, `canvas_audio.py`, `devices.py`, `geo.py`, `mobile.py`, `mobile_devices.py`, `navigator.py`, `network.py`, `screen.py`, `stealth_extra.py`, `__init__.py` (~2.600 baris)
- `gui/` — `app.py` (710), `fingerprint_gen.py` (468), `profiles.py` (361), `extension_manager.py` (339), `proxy_pools.py` (293), `batch_import.py` (261), `local_api.py` (250), `api_config.py` (204), `geo_sync.py` (170), `gui_launcher.py` (55), `__init__.py`
- `launcher/` — `launcher.py` (759), `injector_daemon.py` (84), `test_launcher.py` (113), `brand_builder.py`, `extension_builder.py`, `make_icon.py`
- `installer/` — `stealthxgm_main.py`, `patch-copy.py`, `build-copy.sh`, `build-deb.sh`, `build-copy-win.bat`, `build-windows.bat`, `stealthxgm.spec`
- `vendor/mobile_fingerprint.py` (4.663 baris)
- `docs/` — `USER-GUIDE.md`, `API.md`, `CLI-REFERENCE.md`, `FINGERPRINT-FLAGS.md`, `PROXY-POOLS-GUIDE.md`, `EXTENSIONS.md`, `RND-EXTENSIONS.md`, `INSTALLER.md`; `BEDAH-GUIDE.md`, `PROMPT-REVIEW-AI.md`, `gui/README.md`, `launcher/README.md`
- Salinan build diperiksa untuk drift: `installer/build/src/`, `installer/deb/stealthxgm_1.0.0/` (drift yang ditemukan HANYA patch mekanis `DATA_DIR`/`BROWSER_PROFILES_DIR` dari `build-copy.sh`/`patch-copy.py` — by design, bukan drift liar).

## Perintah verifikasi yang dijalankan (read-only)
- `compileall` seluruh tree → semua file lolos (1 `SyntaxWarning` di `canvas_audio.py:261`).
- `python3 gui/fingerprint_gen.py` → self-test LOLOS (5 OS × 20 identitas, 0 warning; tier mobile 35/44/21; test negatif ditolak).
- `python3 -c "import profiles; len(profiles.FEATURE_FLAGS)"` → **29** (bukan 47).
- `diff` main vs `installer/build/src` dan vs `installer/deb` → hanya baris patch env (`STEALTHXGM_DATA_DIR`, `STEALTHXGM_PROFILES_DIR`).
- `grep` auth/CORS/CSRF/`MAX_CONTENT_LENGTH` → NOL di `gui/` + `launcher/`.
- `grep` pemanggil `_connect_and_inject` / `build_extension` → NOL (dead code).
- `grep` test file → hanya `test_launcher.py` (1 skenario).
- `ls installer/build/src/gui/data/` → kosong; `find installer/deb -name "*.json"` → hanya `brand/manifest.json` (artefak saat ini bersih).
- `cat launcher/sessions.json` → `{}` (tidak ada sesi basi saat audit).

## Catatan akhir
Audit ini read-only dan tidak mengubah kode. Semua temuan di atas bisa diverifikasi ulang dari file + baris yang dikutip. Yang diberi label "belum terverifikasi" memang belum diuji — jangan di-fix berdasarkan tebakan; uji live dulu (V-01–V-05). FASE 2 (fix) hanya jalan atas perintah eksplisit Gil.
