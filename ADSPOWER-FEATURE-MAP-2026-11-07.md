# ADSPOWER FEATURE MAP — buat dibangun ulang di StealthXGM

**Tanggal:** 2026-11-07 (17:50–18:10 WIB)
**Perintah eksplisit Gil (17:47–17:49 WIB, verbatim):** "kita buat adspower versi lengkap kita" + "Kita pake rea ini buat build stealtxgm" + "Kita tiru adspower" + "Tapi design kita harus fresh"
**Aturan:** R46 (perintah eksplisit = jalan), R48 (audit dalem sampe akar), PETA-AGENT slice RND (`client-reverse`, `modern-web-framework-attacks`, `local-vuln-lab`, `exploit-depth`).

## BATAS — dibaca dulu

- **Yang ditiru: FITUR dan cara kerjanya** (apa yang bisa dilakukan user, endpoint apa yang ada, data apa yang disimpan).
- **Yang TIDAK ditiru: DESAIN.** Tampilan, layout, nama produk (`SunBrowser`, `FlowerBrowser`, `RPA Plus`, `AI Plus`), warna, ikon, dan susunan UI AdsPower TIDAK boleh dijiplak. StealthXGM pakai desain fresh kita sendiri.
- **TIDAK ADA kode AdsPower yang disalin ke StealthXGM.** Semua yang di sini adalah deskripsi perilaku + nama endpoint/string sebagai bukti keberadaan fitur — bukan potongan kode. Bangun ulang dari nol dengan kode kita.
- **TIDAK ADA akun/login AdsPower yang dibuat, aplikasi TIDAK PERNAH dijalankan** (hanya diekstrak dan dibaca statis). Download gratis dari CDN resmi, tanpa akun, tanpa bayar.

## SUMBER & METODE

| Item | Fakta |
|---|---|
| Target | **AdsPower Global 8.6.3** (Linux x64, Global build) |
| Download | `https://version.adspower.net/software/linux-x64-global/8.6.3/AdsPower-Global-8.6.3-x64.deb` — 315.341.062 byte |
| SHA256 .deb | `1ad4ffb5720bca1f9cc9c60023bdf754c2fb0812ce6f1834f5897e3907be9c63` |
| Ekstraksi | `dpkg-deb -x` (tanpa install) → `app.asar` 327.195.599 byte, 8.199 entri → `npx @electron/asar extract` → `app-src/` (420 MB) → `app-code/` (8,7 MB: `package.json` + `dist/`, tanpa `node_modules` 176 MB dan tanpa kernel zip) |
| App | Electron, `name: adspower_global`, `main: ./dist/main.js`, homepage adspower.com. Deps: `@electron/remote`, `axios`, `electron-log`, `electron-store`, `electron-updater`, `extract-zip`, `jsonwebtoken`, `koffi`, `mailparser`, `puppeteer-core`, `sharp`, `tree-kill`, `rimraf`, `ico-endec` |
| REA | `rea-agents@latest` = **rea 6.8.0**, Node v24.22.1, `analyze-javascript-application` pada `app-code/` — selesai, rc=0, ~238 detik |
| Bukti REA | `~/workspace/antibrowser/rea-adspower/adspower-8.6.3-evidence.json` (**52.666.015 byte**), confidence `derived`, authority `shipped-artifact` |
| REA — isi | 4 file JS di-parse, **513 modul**, 569.539 AST node, **3.747 findings**, graph **1.097 node / 4.289 edge** (javascript-module 796, endpoint 223, ipc-channel 47, ipc-handler 9, storage 3, electron-main 1, electron-renderer 1, worker 1, package 1). IPC: 49 operasi, 43 channel literal. **Route inventory: 0** — rute HTTP didefinisikan dinamis, bukan pola statis (lihat Batasan) |
| Mining string | `mine.py` (satu pass Python atas `main.js` + `main.min.js`): **208 path `/api/...`** (v1: 19, v2: 32), 42 host adspower, hitung kata kunci per area fitur |
| Dokumen publik | Help/docs AdsPower + review independen 2026 (Pixelscan ✓, CreepJS ✓, Iphey ✗ — Iphey mengenali SunBrowser dari namanya) — dipakai hanya sebagai cross-check, BUKAN sumber utama |

## ARSITEKTUR ADSPOWER (cara kerjanya, ringkas)

- **Electron, 2 proses:** main (`dist/main.js`, webpack bundle 116 KB, 513 modul) + renderer (`dist/static/lib/main.min.js`, 8,4 MB, UI). Preload `dist/static/js/preload.js` (12 KB) mengekspos `window.xrkClientAPI` — **contextIsolation MATI** (contextBridge dikomentari, API ditempel langsung ke `window`). 47 channel IPC REA = jembatan itu: `window:*`, `screen:*`, `store:*`, `shortcut:*`, `update:*`, `system:*`, `dialog:*`, `clipboard:*`, `webFrame:*`, `theme`, `lang`, `notification`, `get-token`.
- **Server lokal (Express) di dalam aplikasi:** renderer memanggil `http://local.adspower.net:50325/api/...` (port 50325; port lain 20725 terlihat di bundle). 208 rute `/api/*` internal + Local API publik v1/v2 di port yang sama. Local API butuh `Authorization: Bearer <api-key>` bila verifikasi API diaktifkan (default di AdsPower: opsional; di StealthXGM harus default ON — temuan P-04).
- **Penyimpanan lokal: SQLite** (`better_sqlite3`, 2 node storage REA) untuk data profil + `electron-store` untuk settings + session-storage `SET_COOKIE`. Ada **worker thread** khusus hitung `cacheSize`.
- **Kernel browser terpisah:** SunBrowser (Chromium) + FlowerBrowser (Firefox) diunduh/dikelola terpisah dari aplikasi utama (kernel ikut terbundel di .deb, lalu diekstrak saat pertama jalan; kernel lain diunduh lewat version API). `puppeteer-core` dipakai untuk kendali browser.
- **Update mandiri:** `electron-updater` + endpoint update client, kernel, RPA, dan JS (`/api/getUpdateBrowser`, `/api/toCheckBrowserUpdate`, `/api/autoUpdateRpaPlus`, `/api/autoUpdateJs`).

## PETA FITUR

Kolom **Status StealthXGM** dari `AUDIT-STEALTHXGM-2026-11-06.md`: ✅ ada · ⚠️ sebagian · ❌ belum ada · ➖ luar scope (sah) · 🚫 sengaja tidak ada.

### 1. Manajemen profil

| Fitur AdsPower | Bukti (REA / mining / docs) | Status StealthXGM |
|---|---|---|
| Profil tanpa batas, CRUD | `/api/v1/user/create|update|delete|list`, `/api/v2/browser-profile/create|update|delete|list` | ✅ Ya (CRUD + grup + trash/restore + duplikat) |
| Grup profil | `/api/v1/group/create|list|update`, `/api/v2/user-group/list`, `group_id` 22 hit | ✅ Ya |
| Tag profil | `/api/v2/browser-tags/create|delete|list|update`, `tag` 286 hit | ⚠️ Sebagian (grup ada, tag belum tentu) |
| Folder / kategori | `/api/v2/category/list`, `folder` 34 hit | ⚠️ Sebagian |
| Recycle bin / trash + restore | `recycle`, `trash`, `duplicate` di bundle; `/api/v1/user/delete` | ✅ Ya (trash/restore ada) |
| Duplikat profil | `duplicate` 26 hit | ⚠️ **RUSAK — P-01: duplikat menyalin fingerprint identity + cookies persis** (wajib regenerate) |
| Remark / catatan per profil | `remark` 27 hit, `serial_number` 34 hit | ⚠️ Sebagian (cek field remark) |
| Username + password tersimpan per profil | `username` 149 hit; profil bawa kredensial login sendiri | ⚠️ Sebagian (StealthXGM simpan cookie, bukan username/password terstruktur) |
| Batch operations (hapus/pindah/assign pool massal) | `batch` 105 hit, `/api/batcCloseBrowser`, `/api/stopAllBrowser` | ✅ Ya (tapi `batch_assign_pool` hardcode `sticky` — M-04) |
| Batch import CSV/JSON + progress + cancel | `/import/start|getStatus|cancel`, `/api/export/percent|stop`, `/api/export/accounts` | ⚠️ Sebagian (import ada, tanpa progress/cancel, tolak `ios` — M-11) |
| Export profil / akun | `/api/export/accounts` | ⚠️ Sebagian (cookie export ada di GUI) |
| Pencarian & filter profil | `user/list` + filter grup (dokumen publik); `/api/v2/browser-profile/list` | ⚠️ Sebagian (`user/list` StealthXGM tanpa filter `group_id` — M-19) |
| Buka banyak profil sekaligus + antrian | `/api/putIntoOpenQueue`, `/api/clearOpenQueue`, `/api/checkOpen`, `/api/checkProfileOpen` | ⚠️ Sebagian (launch per profil ada, antrian buka massal belum) |
| Profil dibagikan ke anggota tim | `/api/v2/browser-profile/share`, `share` 40 hit | ➖ Luar scope (butuh server tim) |

### 2. Fingerprint per profil (50+ parameter, klaim vendor)

| Fitur AdsPower | Bukti (REA / mining / docs) | Status StealthXGM |
|---|---|---|
| Canvas | `canvas` 67 hit | ✅ Ya (flag) |
| WebGL (+ renderer/unmasked) | `webgl` 173 hit, `renderer` 56, `unmasked` 8 | ✅ Ya (flag; string renderer mobile belum terverifikasi — V-04) |
| WebGPU | `webgpu` 20 hit | ✅ Ya (flag) |
| AudioContext | `audioContext` 1 hit | ✅ Ya (flag) |
| Fonts | `fonts` 77 hit, `/api/toFontBrowser` | ✅ Ya (flag) |
| Timezone + geolocation sinkron | `timezone` 229 hit, `/api/postTZGeoLocation`, `/api/updateTzGeo` | ✅ Ya, **lebih baik (geo-sync)** — tapi tidak update `geo_lat/lon` identity tersimpan (P-08) |
| WebRTC | `webrtc` 74 hit | ✅ Ya (flag) |
| User-Agent + Client Hints | `userAgent` 215 hit, `clientHints` 5, `platform` 365 | ✅ Ya (flag; `platformVersion` Mac hardcode — M-09) |
| Screen / resolusi / DPR | `screenResolution` 23, `devicePixelRatio`, `colorDepth` | ✅ Ya (flag) |
| Hardware (concurrency, memory) | `hardwareConcurrency` 17, `deviceMemory` 14 | ✅ Ya (flag) |
| Media devices | `mediaDevices` 53 hit | ✅ Ya (flag) |
| Speech voices | `speechVoices` 11 hit | ⚠️ Cek (ada di kode StealthXGM? belum diaudit) |
| Plugins / clientRects | `plugins` 2, `clientRects` 13 hit | ✅ Ya (flag, sebagian) |
| DoNotTrack / bahasa / locale | `doNotTrack` 19, `languages` 31, `vendor` 19 | ✅ Ya (flag; peta timezone→locale cuma 27 zona — M-07) |
| Device name | Dokumen publik (masking 2023: Device name) | ⚠️ Cek |
| Mode noise / off / real per parameter | `noise` 4 hit (lemah) | ⚠️ Belum dikonfirmasi (StealthXGM: flag on/off) |
| Emulasi mobile Android 9–13 / iOS 14–15 | Dokumen publik | ✅ Ya (mobile fingerprint; GPU renderer aproksimasi — V-04) |
| Fingerprint-check live (cek lawan detector) | **TIDAK TERBUKTI dari kode** (`fingerprintCheck` 0 hit; `/api/checkPage` ada tapi tujuan tidak jelas) | ❌ Belum ada (P-16/P-18) — jangan klaim AdsPower punya ini sebelum verifikasi |
| Generator identitas konsisten | Arsitektur fingerprint per profil | ✅ Ya, lebih baik (`assert_consistent`) — tapi preview salah (P-02) |

### 3. Proxy per profil

| Fitur AdsPower | Bukti (REA / mining / docs) | Status StealthXGM |
|---|---|---|
| HTTP / HTTPS / SOCKS4 / SOCKS5 / SSH | `socks5` 42, `socks4` 3, `ssh` 224, `proxy_type` 36 | ✅ Ya (tipe ada; SSH cek implementasi) |
| Auth proxy (user/pass) native | `proxy_user` 32, `proxy_password` ada, `/api/getProxy`, `/api/proxy` | ❌ **RUSAK — P-09: kredensial dibuang, dialog auth tak terisi; password bocor di argv** |
| Proxy checker (cek IP/negara) | `/api/checkProxy`, `/api/checkIpCountry`, `/api/checkProxyCache`, `/api/checkProxyTool`, `/api/getCustomIp` | ✅ Ya (`test_pool` via ip-api; tapi HTTP polos — M-17) |
| Provider proxy built-in | `922S5` 47, `ipidea` 57, `luminati` 34, `/api/getLumiIp`, `/api/getOxyIp`, `/api/getIpFoxyIp`, `/api/getKookautoIp`, `/api/getIphtmlIp`, `/api/getOtherSoftIp`, `/api/get922S5authIp` | ❌ Belum ada (StealthXGM: pool custom + proxy-bot DataImpulse) |
| Proxy list (kelola daftar proxy) | `/api/v2/proxy-list/create|delete|list|update` | ✅ Ya (pool) |
| Refresh / rotate proxy URL | `/api/refreshProxyUrl`, `/api/findProxyPort`, `/api/findLocalServerProxy`, `/api/downloadProxyTool` | ⚠️ Sebagian (sticky via proxy-bot) |
| System proxy (pakai proxy OS) | `/api/getSystemProxy`, `/api/setSystemProxy`, `/api/getSystemProxyConfig`, `/api/triggerGetSystemProxy` | ❌ Belum ada |
| Proxy per profil di Local API | `proxy_user`, `proxy_password` di objek profil API | ⚠️ Sebagian |

### 4. Kernel browser (SunBrowser / FlowerBrowser)

| Fitur AdsPower | Bukti (REA / mining / docs) | Status StealthXGM |
|---|---|---|
| Dua engine: Chromium + Firefox | `SunBrowser` 28, `FlowerBrowser` 16, `firefox` 131, `chromium` 14 | ❌ **Belum ada — StealthXGM hanya Chromium sistem** |
| Download / kelola kernel | `/api/v2/browser-profile/kernels`, `/api/v2/browser-profile/download-kernel`, `/api/getUpdateBrowser`, `/api/toInstallBrowser`, `/api/checkKernelUninstall`, `/api/pushDownloadBrowser`, `/api/getLocalBrowser` | ❌ Belum ada (Chromium tidak dibundel; unduh manual) |
| Multi-versi kernel per profil | `browserVersion` 16, `browser_version` 7, kernel 190 hit | ❌ Belum ada |
| Update kernel otomatis | `/api/toCheckBrowserUpdate`, `/api/getUpdateBrowser` | ❌ Belum ada |

### 5. Local API (otomasi via HTTP)

| Fitur AdsPower | Bukti (REA / mining / docs) | Status StealthXGM |
|---|---|---|
| Port 50325 (+20725), Bearer API key | `local.adspower.net:50325` (docs + bundle), `127.0.0.1:20725`, `Bearer` 39, `api_key` ada | ⚠️ Sebagian (port 50325 ada; **auth default OFF — P-04**) |
| v1: status, browser start/stop/active, user/group CRUD | 19 path: `/api/v1/browser/start|stop|active|cloud-active|local-active`, `/api/v1/user/create|update|delete|list|delete-cache|regroup`, `/api/v1/group/*`, `/api/v1/application/list`, `/api/v1/fb/*`, `/api/v1/fbbird/user/list` | ⚠️ Sebagian (endpoint inti ada; tanpa `headless`, tanpa cookie, tanpa filter grup — P-14/M-02/M-19) |
| v2: browser-profile lengkap | 32 path: `/api/v2/browser-profile/start|stop|stop-all|active|create|update|delete|list|cookies|kernels|download-kernel|new-fingerprint|share|ua|update-patch`, `/api/v2/browser-tags/*`, `/api/v2/proxy-list/*`, `/api/v2/category/list`, `/api/v2/user-group/list`, `/api/v2/user/*` | ❌ Belum ada (v2 belum diimplementasi) |
| Start kembalikan ws.puppeteer + ws.selenium + debug_port + webdriver | Dokumen publik + `/api/v1/browser/start` | ⚠️ Sebagian (ws/CDP ada; cek `webdriver` path chromedriver) |
| Headless via API | Dokumen publik (`headless` param) | ❌ **Belum ada — P-14 (GUI/API/CLI hardcode headful)** |
| Cookie via API | `/api/v2/browser-profile/cookies` | ❌ Belum ada di API (hanya GUI; gagal diam-diam — P-15/M-02) |
| API key management | `api_key`/`apiKey`, `Authorization` | ⚠️ Sebagian (key ada tapi default kosong — P-04) |

### 6. Server lokal internal (bukan API publik — cara kerja aplikasi)

| Fitur AdsPower | Bukti (REA / mining / docs) | Status StealthXGM |
|---|---|---|
| Buka/tutup browser + batch | `/api/openBrowser`, `/api/openBrowserV3`, `/api/batcCloseBrowser`, `/api/closeAllBrowser`, `/api/stopAllBrowser`, `/api/frontBrowser`, `/api/getChromeOpened`, `/api/getTabUrls`, `/api/updateTabs` | ✅ Ya (launch/stop; batch close cek) |
| Cache profil + backup/restore | `/api/cache/local|upload`, `/api/checkCache`, `/api/clearCache`, `/api/deleteCacheById`, `/api/deleteAllCache`, `/api/getCacheConfig`, `/api/setCacheConfig`, `/api/getCacheBackupSwitch`, `/api/setCacheBackup`, `/api/getBackupList`, `/api/deleteBackup`, `/api/restoreBackup`, `/api/cacheSize` (+ worker thread) | ⚠️ Sebagian (cookie/cache ada; backup/restore profil belum) |
| Posisi jendela tersimpan | `/api/getWindowPosition`, `/api/setWindowPosition` | ⚠️ Cek |
| System info / GPU / aksesibilitas | `/api/getSystemInfo`, `/api/getGPUSwitch`, `/api/setGPUSwitch`, `/api/getRendererAccessibility`, `/api/setRendererAccessibility`, `/api/getOsName`, `/api/getUniqueId`, `/api/checkSystemTime` | ⚠️ Sebagian |
| Log & crash report | `/api/reportLog`, `/api/reportCollapseLog`, `/api/log`, `/api/checkApplicationException`, `/api/resetApplicationException` | ⚠️ Sebagian (log daemon dibuang ke DEVNULL — P-10) |
| Update client + browser + RPA + JS | `/api/update`, `/api/getUpdateClient`, `/api/pushDownloadClient`, `/api/updateActionId`, `/api/getVersion`, `/api/getLastVersion`, `/api/getVersionUpdateConfig`, `/api/setVersionUpdateConfig` | ❌ Belum ada auto-update (M-21) |
| Data path bisa dipindah | `/api/getDataPath`, `/api/updateDataPath`, `/api/setCustomBrowserPath` | ⚠️ Sebagian (env override ada; inkonsisten — M-05/M-19) |

### 7. RPA & otomasi (pembeda terbesar AdsPower)

| Fitur AdsPower | Bukti (REA / mining / docs) | Status StealthXGM |
|---|---|---|
| RPA no-code (visual builder, record & replay) | `rpa` 124, `RPA` 78, `flow` 332, `task` 381, `/api/getRpaStatus`, `/api/stopRpa`, `/api/checkRpaPlusUpdate`, `/api/autoUpdateRpaPlus` | ❌ **Belum ada — P-18 (hanya helper `behavioral_human.py`)** |
| Template RPA per platform (FB, YT, TikTok, Amazon, LinkedIn, Discord, IG) | Dokumen publik | ❌ Belum ada |
| Jalankan alur di banyak profil sekaligus | Dokumen publik (RPA multi-profil) | ❌ Belum ada |
| Cookie Robot (warming cookie otomatis) | `cookieRobot` 10, `/api/checkCookieRobotTask`, `/api/putCookieRobotTask`, `/api/runCookieRobotTask`, `/api/getCookieRobotTask`, `/api/clearCookieRobotTask`, `/api/deleteOpenedCookieRobot`, `/api/putOpenedCookieRobot` | ❌ Belum ada |
| AI Plus / Agent Core (otomasi AI) | `/api/ai/plus/checkAgentCoreUpdate`, `/api/ai/plus/checkStart`, `/api/ai/plus/internal-progress`, `/api/ai/plus/stop`, `/api/ai/getOpenedById`, `/api/getAssistantConfig`, `/api/setAssistantConfig`, `/api/tabAssistant/features` | ❌ Belum ada (di luar scope awal — catat sebagai fase jauh) |
| Scheduler tugas | `scheduler` 0 hit di bundle (tidak terbukti) | ❌ Belum ada |

### 8. Synchronizer (aksi dicerminkan ke banyak jendela)

| Fitur AdsPower | Bukti (REA / mining / docs) | Status StealthXGM |
|---|---|---|
| Mirror klik/ketik/scroll ke semua profil terbuka | **15 rute `/sync/*`**: `/sync/toSyncOperateBrowser`, `/sync/toStopSyncOperateBrowser`, `/sync/getOperateBrowser`, `/sync/toInputTxt`, `/sync/toRefreshTab`, `/sync/toRangeBrowser`, `/sync/toOpenDelay`, `/sync/toShowBrowser`, `/sync/manageUrlTab`, `/sync/openUrl`, `/sync/paste`, `/sync/syncSize`, `/sync/getPosition`, `/sync/resetDownload`, `/sync/clear` | ❌ **Belum ada — P-18** |
| Catatan: string `synchronizer`/`windowSync` = 0 hit — fitur ini bernama `sync` di kode, BUKAN `synchronizer`. Jangan cari dengan nama pasar. | | |

### 9. Extension

| Fitur AdsPower | Bukti (REA / mining / docs) | Status StealthXGM |
|---|---|---|
| Extension Center + install CRX | `extension` 1232 hit, `crx` 35, `/api/extension/update`, `/api/getExtensionList`, `/api/getExtensionStatus`, `/api/postExtDeleted`, `/api/getWebStoreInfo` | ✅ Ya (library + assignment) — **tapi Zip Slip P-05 + tanpa verifikasi tanda tangan** |
| Extension tidak auto-update (dipin versi) | Dokumen publik | ⚠️ Cek (StealthXGM: cek perilaku update extension) |

### 10. Tim, cloud sync & akun (server-side — di luar scope rebuild lokal)

| Fitur AdsPower | Bukti (REA / mining / docs) | Status StealthXGM |
|---|---|---|
| Member / role / permission tim | `member` 119, `role` 92, `permission` 16, `team` 23 | ➖ Luar scope (lokal saja — keputusan sah, audit P-18) |
| Cloud sync profil + backup cloud | `cloud` 125, `backup` 97, `/api/getUserInfoById` | ➖ Luar scope |
| Facebook tools (BM/page, network acceleration) | `/api/v1/fb/bm|list|page`, `/api/v1/fbbird/user/list`, `/api/openFb`, `/api/getFbNetworkAcceleration` | ➖ Luar scope (fitur platform-spesifik) |
| Akun + 2FA + security lock | `2fa` 6, `/api/postBrowserSecurityLock`, `/api/postWhiteList`, `encrypt` 58, `decrypt` 33 | ⚠️ Sebagian (secret 600 + atomic write sudah; security lock belum) |

## TOP 10 — PALING HILANG & PALING LAYAK DIBANGUN DULUAN

Urutan = (hilang di StealthXGM) × (nilai buat Gil: banyak akun) × (bisa dibangun). **Catatan:** fix P0 audit (P-01 duplikat, P-03 title, P-02 preview, P-04 auth, P-05 Zip Slip, P-06 liveness, P-08 geo, P-11 backup JSON, P-13 build-copy) adalah **prasyarat** yang jalan duluan di Fase 2 — daftar di bawah ini adalah FITUR BARU, bukan pengganti P0.

| # | Fitur | Kenapa duluan | Bukti AdsPower | Perkiraan usaha |
|---|---|---|---|---|
| 1 | **RPA sederhana** (rekam langkah klik/isi/tunggu → jalankan di 1/banyak profil) | Pembeda terbesar AdsPower; helper `behavioral_human.py` sudah ada — tinggal bungkus jadi UI/API + simpan alur sebagai JSON | `rpa` 124 hit, `/api/getRpaStatus`, `/api/stopRpa` | Sedang |
| 2 | **Synchronizer** (mirror aksi ke semua jendela terbuka) | Nilai langsung buat kelola banyak akun; modelnya jelas: 15 rute `/sync/*` (input teks, refresh tab, atur range, delay, posisi) | `/sync/toSyncOperateBrowser` dkk (15 rute) | Sedang |
| 3 | **Local API v1 lengkap + v2 inti** (`headless`, cookie, filter grup, `browser-profile/cookies`, `new-fingerprint`, tags, proxy-list) | Otomasi merra + kompatibilitas skrip AdsPower; menutup P-14/M-02/M-19 sekaligus | v1 19 path + v2 32 path (terlampir) | Sedang |
| 4 | **Fingerprint-check live** (cek profil lawan CreepJS/browserleaks/Pixelscan, tampilkan field bocor) | Tanpa ini "antidetect" hanya klaim (P-16); AdsPower lolos Pixelscan/CreepJS di uji independen | Uji independen 2026 (bukan dari kode — dari kode TIDAK terbukti ada checker bawaan) | Kecil–Sedang |
| 5 | **Proxy-auth yang jalan** (extension auth / CDP Fetch; kredensial TIDAK di argv) | Tanpa ini pool HTTP/SOCKS ber-user/pass mentok dialog auth (P-09); AdsPower menanganinya native + dukung SSH | `proxy_user`/`proxy_password`, `/api/getSshIp` | Sedang |
| 6 | **Kernel manager** (unduh/ganti versi Chromium per profil; siapkan slot Firefox/FlowerBrowser) | Dual-engine adalah identitas AdsPower; StealthXGM kini kunci ke Chromium sistem | `/api/v2/browser-profile/kernels`, `download-kernel`, `/api/getUpdateBrowser` | Besar |
| 7 | **Cookie manager via API + validasi per-cookie** | Cookie adalah sesi; import gagal total diam-diam hari ini (P-15); AdsPower punya `/api/v2/browser-profile/cookies` | `/api/v2/browser-profile/cookies` | Kecil |
| 8 | **Backup/restore profil + cache** (ekspor profil lengkap, restore, hitung ukuran cache) | AdsPower: cache backup switch, delete/restore backup, worker `cacheSize`; StealthXGM: JSON rawan hilang (P-11) | `/api/cache/*`, `/api/getBackupList`, `/api/restoreBackup` | Kecil–Sedang |
| 9 | **Batch import/export dengan progress + cancel** (termasuk iOS) | AdsPower: `/import/start|getStatus|cancel` + `/api/export/percent|stop`; StealthXGM: tanpa batas baris, tolak iOS (M-11) | `/import/*`, `/api/export/*` | Kecil |
| 10 | **Extension Center aman** (validasi Zip Slip + tampilkan permission manifest + cek tanda tangan CRX + pin versi tanpa auto-update) | P-05 aktif berbahaya; AdsPower: Extension Center + `getWebStoreInfo` + tidak auto-update | `/api/extension/update`, `/api/getExtensionList`, `crx` 35 hit | Kecil–Sedang |

**Tidak masuk top 10 (sengaja):** cloud sync/tim (luar scope lokal), AI Plus (fase jauh, butuh model), captcha solver (keputusan Gil: TIDAK dibangun), remote view (di-skip Gil 20:02 WIB), Facebook tools (platform-spesifik).

## DESAIN FRESH — YANG TIDAK DITIRU

- **Nama:** jangan pakai `SunBrowser`, `FlowerBrowser`, `RPA Plus`, `AI Plus`, `Cookie Robot`, `Synchronizer` (nama pasar AdsPower). Pakai nama kita sendiri (mis. alur otomasi = "Alur", sinkronisasi = "Cermin", dst — nama final diputuskan saat bangun, bukan di peta ini).
- **Tampilan:** layout, warna, ikon, susunan menu, dan alur klik AdsPower TIDAK dicontoh. Desain UI StealthXGM tetap milik kita (GUI 5200 yang sudah ada), ditambah fitur baru dengan bahasa/istilah kita.
- **Arsitektur yang TIDAK ditiru:** contextIsolation MATI + `window.xrkClientAPI` (AdsPower) — StealthXGM harus tetap pakai contextBridge/isolasi yang benar; jangan meniru kelemahan keamanan mereka. Penyimpanan boleh meniru pola (SQLite untuk profil — itu pola umum, bukan milik AdsPower), tapi skema tabel kita rancang sendiri.
- **Pembeda yang sudah kita punya (jangan hilang):** geo-sync timezone/locale dari IP (AdsPower+), `assert_consistent` fingerprint, seed canvas stabil per profil.

## BATASAN & YANG BELUM TERBUKTI (jujur)

1. **REA route inventory = 0.** Rute HTTP AdsPower didefinisikan dinamis (Express + string gabungan), jadi REA tidak merekonstruksinya sebagai rute. Daftar 208 path `/api/*` berasal dari string mining (2 metode independen: REA endpoint nodes 176 path-like + `mine.py` 208 path) — keberadaan string ≠ rute aktif. Verifikasi runtime (jalankan server lokalnya) TIDAK dilakukan dan TIDAK boleh dilakukan tanpa perintah (aplikasi tidak dijalankan).
2. **String ≠ perilaku runtime.** Hitungan kata kunci (mis. `sync` 1998 — sebagian besar dari kata `async`) bukan bukti fitur. Yang dipakai sebagai bukti di peta ini hanya: nama path endpoint, nama channel IPC, nama file/modul, dan dokumen publik — bukan hitungan mentah.
3. **Fitur server-side (tim/cloud/sub-akun) tidak bisa diverifikasi dari client.** Yang terlihat di client hanya string `member`/`role`/`share`/`cloud` + endpoint share — logika servernya tidak ada di bundle ini.
4. **Fingerprint-check live TIDAK terbukti dari kode** (`fingerprintCheck` 0 hit). Klaim audit fase 1 bahwa AdsPower punya "fingerprint-check live" berasal dari pengetahuan umum, bukan bukti kode — peta ini mengoreksinya: belum terbukti; yang terbukti adalah AdsPower lolos Pixelscan/CreepJS di uji independen 2026.
5. **Mode noise fingerprint belum dikonfirmasi** (`noise` 4 hit — terlalu lemah untuk menyimpulkan ada mode noise/off/real per parameter).
6. **Scheduler tugas tidak terbukti** (`scheduler` 0 hit).
7. **Versi yang dibedah = 8.6.3 Linux Global.** Build Windows/macOS atau versi lain bisa berbeda. Ulangi bedah ini bila versi naik mayor.
8. **Tidak ada data pengguna AdsPower yang disentuh.** Bundle ini murni kode aplikasi publik (free download). Tidak ada kredensial, cookie, atau data akun di dalamnya — dan tidak dicari.
9. **Batas anggaran hasil REA:** semantic graph `dist/static/lib/main.min.js` melebihi sisa budget hasil REA (fakta statis/modul tetap tersimpan), dan inline JavaScript di `dist/static/html/notification.html` (baris 155) serta `tips.html` (baris 44) TIDAK dianalisis — endpoint/storage dari kedua file itu tidak ada di evidence.

## FILE BUKTI (semua di `~/workspace/antibrowser/rea-adspower/`)

| File | Isi |
|---|---|
| `AdsPower-Global-8.6.3-x64.deb` (315 MB) | Installer resmi (reproduksi: `dpkg-deb -x` → `app.asar` → `asar extract`) |
| `extracted/` (675 MB) | Isi .deb (Electron runtime + `app.asar` + kernel bundel) |
| `app-src/` (420 MB) | Isi `app.asar` (kode + `node_modules`) |
| `app-code/` (8,7 MB) | Kode aplikasi saja (target analisis REA) |
| `adspower-8.6.3-evidence.json` (52,7 MB) | **Evidence REA lengkap** (graph 1.097 node / 4.289 edge) |
| `adspower-8.6.3-evidence.err` | Log progress REA |
| `api-paths-full.txt` (208) | Semua path `/api/*` |
| `api-v1-paths.txt` (19) + `api-v2-paths.txt` (32) | Path Local API v1/v2 |
| `keyword-counts.txt` | Hitungan kata kunci per area fitur |
| `adspower-hosts.txt` (42) | Host adspower.* di bundle |
| `local-api-base.txt` | `local.adspower.net:50325`, `127.0.0.1:20725` |
| `mine.py`, `summarize_evidence.py` | Script mining + ringkas evidence (bisa diulang) |
| `~/workspace/tools/rea-test-pentest-web.json` (30 MB) | Uji REA sebelumnya (pentest-web, 21 file) — bukti REA bekerja sebelum dipakai di sini |

## CHECKLIST KEPATUHAN (RND)

- [x] Baca `PETA-BROWSER.md` (StealthXGM = banyak akun; REA bukan browser — analisis statis file lokal)
- [x] Baca `AUDIT-STEALTHXGM-2026-11-06.md` (tabel perbandingan AdsPower + rencana P0/P1/P2 dipakai untuk kolom Status)
- [x] Baca `PETA-AGENT.md` slice RND (`client-reverse` — packet-first/locate→recover; `modern-web-framework-attacks`, `local-vuln-lab`, `exploit-depth`)
- [x] Baca `CHECKLIST-KEPATUHAN.md` + R46 (perintah eksplisit Gil 17:47–17:49 WIB = jalan)
- [x] Artefak dihasilkan (peta ini + evidence JSON + script mining) — bukan teori doang (Doktrin RND)
- [x] Tidak ada akun/login, tidak jalankan aplikasi, tidak bayar, tidak salin kode, tidak jiplak desain
