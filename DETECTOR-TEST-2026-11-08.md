# Tes Detektor Eksternal StealthXGM — 2026-11-08

**Verdict jujur: TIDAK lolos CreepJS.** CreepJS menandai beberapa
inkonsistensi (bagian pink) dan WebGL tidak tersedia sama sekali.
BrowserLeaks canvas + fonts terukur dengan hash nyata; WebGL kosong.
Ini tes detektor eksternal PERTAMA yang pernah jalan (V-01 eksternal) —
sebelumnya hanya cek lokal 11/11.

## 1. Cara peluncuran

- Profil uji `detector-test`, kernel **Chrome for Testing 159.0.8148.0**
  (terdaftar di `gui/data/kernels.json`), headful via `xvfb-run`
  (lapisan extension MV3 hanya jalan headful — mode paling mendekati
  pemakaian nyata). Tanpa proxy (lihat §2 soal jaringan).
- Identitas yang disuntik saat tes (dari `identity.json`):
  UA `Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/159.0.0.0`,
  platform Win32, OS windows, layar 3840×2160, depth 24, dpr 1,
  hw 12 core, mem 4 GB, GPU `ANGLE (AMD, AMD Radeon RX 7900 XT
  Direct3D11 ...)`, timezone Asia/Jakarta, geo -6.21/106.85,
  locale null, vendor Google Inc.
- Viewport jendela saat tes: 1600×900 (disetel driver uji — BUKAN
  bagian identitas profil).
- Catatan: profil uji dibuat via API (dict), bukan dari store GUI —
  identitas di-generate baru tiap launch (freeze hanya berlaku untuk
  profil di store). Dalam satu sesi identitas konsisten.

## 2. Baseline lokal (sebelum tes eksternal)

`python3 tests/live_stealth_check.py` → **11/11 vektor lolos**
(10 PASS + 1 INFO `'webdriver' in navigator` True by design).
Laporan: `tests/live-reports/live-stealth-20261108-033903.json`.
Canvas hash stabil 99e786aa. Ini cek lokal — BUKAN bukti eksternal.

## 3. Kendala jaringan — kenapa situs asli tidak bisa dibuka langsung

Dicoba berurutan, semua gagal dari browser StealthXGM:

1. **Langsung (tanpa proxy):** `net::ERR_CONNECTION_RESET` —
   gateway VM memutus TLS Chromium (sudah diketahui, P-09).
2. **Via egress proxy VM (profile proxy + extension auth):**
   `net::ERR_TUNNEL_CONNECTION_FAILED` — headless maupun headful,
   dengan auth maupun tanpa auth.
3. **Diagnosis:** curl lewat proxy yang sama berhasil (200) untuk
   example.com, CreepJS, browserleaks — termasuk tanpa kredensial dan
   dengan UA Chrome. CONNECT dari Chrome sendiri (dicek via fake
   proxy lokal) bentuknya normal. Penyebab akhir: **proxy melakukan
   MITM TLS** — sertifikat disajikan diterbitkan `CN=Hatch Sandbox
   Egress CA, O=Hatch` (fingerprint SHA256
   `82:01:63:ED:...:C6:07`, sama dengan CA di
   `/usr/local/share/ca-certificates/hatch-egress-ca.crt`).
   curl percaya karena `SSL_CERT_FILE=/run/hatch/egress-tls/ca-bundle.pem`.
   **Chrome tidak percaya CA itu** — `ERR_CERT_AUTHORITY_INVALID` —
   walau CA sudah ada di `~/.pki/nssdb` (trust `C,,`), di
   `/etc/ssl/certs` (symlink `32ce25bf.0`), dan walau policy
   `ChromeRootStoreEnabled: false` dipasang di
   `/etc/opt/chrome/policies/managed/` dan
   `/etc/chromium/policies/managed/` (kedua file policy sudah
   DIHAPUS lagi setelah terbukti tidak berpengaruh).
4. **Jalan keluar yang dipakai:** relay CONNECT lokal di
   `127.0.0.1:18081` (`/tmp/relay.py`, sudah dimatikan) membuktikan
   jalur CONNECT + TLS berfungsi — satu-satunya blokir adalah
   validasi sertifikat. Launcher tidak punya hook untuk flag
   `--ignore-certificate-errors`, dan menambahkannya = ubah kode
   (dilarang untuk tugas tes ini).
5. **Solusi pengukuran:** kode detector ASLI diunduh via curl lalu
   disajikan lokal (origin `127.0.0.1`, tanpa proxy — localhost
   di-bypass launcher):
   - CreepJS persis dari `abrahamjuliot.github.io/creepjs/`
     (`index.html` + `creep.js` 550 KB + `style.min.css`) di port 18083.
     CreepJS 100% client-side (tidak ada fetch jaringan di kodenya
     selain link dokumentasi) — yang diukur adalah komputasi
     fingerprint asli.
   - BrowserLeaks canvas/webgl/fonts persis dari `browserleaks.com`
     (HTML + `js/canvas.js`, `js/webgl.js`, `js/fonts.js`,
     `js/default.js`, `css/style.css`) di port 18084.
   - Server sudah dimatikan setelah tes. File sumber di `/tmp`
     (bukan bagian proyek).
   - **Batasan metode:** origin localhost (bukan domain asli);
     pemeriksaan yang butuh server (IP, WebRTC STUN, lookup
     uniqueness) tidak bisa jalan — dicatat sebagai tidak teruji,
     bukan lolos.

## 4. CreepJS — hasil

Kode asli, disajikan lokal. FP ID:
`79e9fcfaadf69932cde6cba4e213fe6a3f933bf9060ceaa1226eeb6553e9de45`,
Fuzzy: `031ff24cce2c8901059d3a94d14623056f1f1a7ab97cbaf89a19000000000000`.
Screenshot: `tests/live-reports/detector-2026-11-08/creepjs.png`
(teks lengkap: `creepjs.txt`).
CreepJS versi ini tidak menampilkan satu skor numerik tunggal;
bagian berlatar pink = inkonsistensi yang ditandai.

### 4.1 Kebocoran / inkonsistensi (yang ditandai CreepJS)

1. **Web Worker TIDAK ikut di-spoof (paling keras).**
   Main thread: Windows (Win32), `lang id-ID, id, en-US, en`,
   timezone Asia/Jakarta, cores 12, ram 4.
   Worker: UA `Mozilla/5.0 (X11; Linux x86_64) ... Chrome/159.0.0.0`,
   `lang/timezone: en-US (1 US dollar), UTC (0)`,
   device `Linux (Linux x86_64), cores: 4, ram: 8`, gpu unsupported,
   userAgentData `Chromium 159 (159.0.8148.0), Linux x86_64`.
   Injeksi fingerprint tidak berlaku di dalam Worker — detector
   tinggal bandingkan main thread vs worker dan ketahuan.
2. **Font Linux di mesin "Windows" (bagian Fonts pink).**
   Hanya 8/51 font ter-load; daftarnya `DejaVu Sans`,
   `Liberation Mono`, `Noto Color Emoji`, `Noto Sans ...`,
   OpenSymbol — font Linux. Mesin Windows 10 asli punya Arial,
   Segoe UI, Times New Roman, dst. `load (8/51): Like undefined`.
3. **Sinyal headless (bagian Headless).**
   `chromium: true`, `38% like headless`, `33% headless`,
   `40% stealth`. Bukan vonis 100%, tapi CreepJS mengukur
   kemiripan dengan headless Chromium — dan `chromium: true`
   positif.
4. **WebGL tidak tersedia (bagian WebGL, semua "blocked").**
   `images: blocked, pixels: blocked, params (0): blocked,
   exts (0): blocked, gpu: blocked`. Lihat §6 — ini masalah
   kernel 159, bukan kode spoof.
5. **Canvas 2d (bagian pink): noise terdeteksi.**
   `data: 9342d82a`, `rendering: 6% rgba noise`.
   Noise-nya bekerja (hash diacak), tapi CreepJS mengukur dan
   menampilkan persentase noise-nya.
6. **DOMRect / SVGRect (bagian pink): nilai A/B identik persis.**
   `elems A = elems B = range A = range B = 0.24583372172851561`.
   Nilai yang terlalu sempurna antar pengukuran ditandai.
7. **Intl vs navigator (inkonsistensi ringan).**
   Intl: `en-US,id-ID`, `American English`;
   navigator.languages: `id-ID, id, en-US, en (id-ID)`.
   Locale default Intl (en-US) tidak cocok dengan bahasa
   utama navigator (id-ID).
8. **Bagian pink lain tanpa detail terbaca:** Math, Error,
   Window (keys 1231), HTMLElement (keys 370), Navigator
   (properties 69) — hash bagian-bagian ini ditandai tidak
   cocok dengan profil yang diklaim. Detail isi tidak
   terbaca dari teks (hanya "details").

### 4.2 Yang TIDAK bocor di CreepJS

- **WebRTC:** IP disamarkan `000.000.000.000`, foundation
  `0000000000`, kandidat host `.local` (mDNS acak), devices (0).
  Tidak ada IP asli yang keluar.
- **Timezone:** `Western Indonesia Time`, konsisten Asia/Jakarta.
- **Navigator main thread:** konsisten dengan identitas
  (Windows, Win32, cores 12, ram 4, plugins 5, vendor
  Google Inc., `navigator.webdriver === false`, UA Chrome 159).
- **Screen:** `3840 x 2160`, avail `3840 x 2120`, depth `24|24`,
  touch false — cocok identitas (viewport 1600×900 adalah
  setelan driver uji).
- **Audio:** fingerprint terhitung (`data: 964bca77`,
  `unique: 4738`) tanpa penanda bocor.

## 5. BrowserLeaks — hasil

Kode JS asli, disajikan lokal. IP dan WebRTC **tidak teruji**
(halaman itu server-side — butuh koneksi ke server browserleaks).

### 5.1 Canvas — TERUKUR, hash nyata

- Canvas 2D API: True; Text API: True; toDataURL: True.
- **Signature: `F0140397E1723925609FF0EA9DEA1CE1`**
- Gambar: PNG 220×30, 8334 bytes, 1385 warna.
- Uniqueness: `Data retrieval error [retry]` — lookup ke DB
  browserleaks gagal karena disajikan lokal (bukan kebocoran).
- Screenshot: `bl-canvas.png`.

### 5.2 WebGL — TIDAK TERSEDIA

- `This browser supports WebGL: ✖ False (supported, but disabled
  or unavailable)` — sama untuk WebGL 2.
- Semua field kosong: hash, vendor, renderer, params, extensions.
- Catatan: `HTTP User-Agent: curl/8.5.0` di halaman itu adalah
  artefak fetch via curl, bukan UA browser.
- Screenshot: `bl-webgl.png`. Lihat §6.

### 5.3 Fonts — TERUKUR, 224 font Linux

- Font Metrics fingerprint: `9A00B5963D557B507F31BFE87E3A4495`
- `224 fonts and 109 unique metrics found`
- Unicode Glyphs fingerprint: `E39652F9`
- Screenshot: `bl-fonts.png`.

## 6. Temuan WebGL: masalah kernel CfT 159, bukan spoof

Dibuktikan 3 lapis (tanggal 2026-11-08):

1. **Launcher + kernel 159** (headless DAN headful):
   `getContext('webgl')` → `null`, `getContext('webgl2')` → `null`.
2. **CfT 159 langsung** (tanpa launcher, tanpa injeksi):
   `webgl: False`. Jadi bukan kode spoof yang memblokir.
3. **Launcher + fallback Playwright Chromium 156**
   (tanpa kernel 159): WebGL **jalan**, dan spoof berlaku —
   unmasked renderer `ANGLE (AMD, AMD Radeon RX 6600
   Direct3D11 ...)` (GPU spoof, bukan GPU asli VM).

Pemeriksaan pendukung: kode spoof hanya menimpa `getParameter` /
`getExtension` / `readPixels` (file `fingerprint/canvas_audio.py`)
— tidak ada override `getContext`; launcher tidak memberi flag
`--disable-webgl`; library SwiftShader ada di kernel
(`libvk_swiftshader.so`, `libEGL.so`, `libGLESv2.so`);
`ldd` tidak menunjukkan library hilang. Penyebab pasti gagalnya
inisialisasi GL di binary 159 di VM ini **belum terisolasi**
(bukan tugas tes ini).

**Dampak detector:** browser yang mengaku Chrome 159 desktop
dengan GPU kelas atas tapi WebGL-nya mati total adalah
inkonsistensi yang mudah ditandai detector — terlepas dari
penyebabnya. Perbaikan (pilih kernel lain / perbaiki init GL
159) adalah keputusan terpisah — BUKAN bagian tugas ini.

## 7. Daftar kebocoran (ringkas)

| # | Kebocoran | Bukti |
|---|---|---|
| 1 | Worker tidak di-spoof (UA Linux, tz UTC, lang en-US, cores 4/ram 8) | CreepJS §Worker vs Navigator |
| 2 | Font Linux di mesin "Windows" (8/51) | CreepJS Fonts; BL 224 font |
| 3 | Sinyal headless (`chromium: true`, 33–40%) | CreepJS Headless |
| 4 | WebGL mati total (kernel 159) | CreepJS blocked; BL False |
| 5 | Noise canvas terukur 6% rgba | CreepJS Canvas 2d |
| 6 | DOMRect/SVGRect A/B identik persis | CreepJS (pink) |
| 7 | Intl en-US vs navigator id-ID | CreepJS Intl vs Navigator |
| 8 | Math/Error/Window/HTMLElement/Navigator ditandai pink | CreepJS (tanpa detail isi) |

Yang tidak bocor: IP WebRTC (disamarkan), timezone, UA/platform/
hardware main thread, screen, audio.

## 8. Verdict per detector

- **CreepJS: TIDAK LOLOS.** Beberapa inkonsistensi terdeteksi,
  yang paling keras adalah Worker yang tidak di-spoof dan font
  Linux. Jangan klaim "lolos CreepJS" sebelum kebocoran 1–4
  diperbaiki dan diuji ulang.
- **BrowserLeaks canvas: TERUKUR** (signature nyata
  `F0140397...`), bukan vonis lolos/gagal — hash-nya ada dan
  stabil per profil (noise di-seed dari ID profil).
- **BrowserLeaks fonts: TERUKUR** (224 font Linux).
- **BrowserLeaks WebGL: GAGAL TOTAL** (tidak tersedia —
  masalah kernel 159, §6).
- **BrowserLeaks IP / WebRTC: TIDAK TERUJI** (butuh server;
  tidak bisa disajikan lokal).

## 9. File bukti

- `tests/live-reports/live-stealth-20261108-033903.json` (baseline 11/11)
- `tests/live-reports/detector-2026-11-08/creepjs.png` (screenshot CreepJS)
- `tests/live-reports/detector-2026-11-08/creepjs.txt` (teks lengkap)
- `tests/live-reports/detector-2026-11-08/bl-canvas.png` + `bl-canvas.txt`
- `tests/live-reports/detector-2026-11-08/bl-webgl.png` + `bl-webgl.txt`
- `tests/live-reports/detector-2026-11-08/bl-fonts.png` + `bl-fonts.txt`
- `tests/live-reports/detector-2026-11-08/identity.json` (identitas yang diuji)
- Log kerja: `/tmp/detector_run.py`, `/tmp/webgl_probe.py`,
  `/tmp/webgl_156.py`, `/tmp/relay.log`, `/tmp/fake_proxy.log`
  (semua di /tmp; server lokal + relay sudah dimatikan,
  profil uji sudah dihapus, file policy Chrome percobaan sudah
  dihapus — tidak ada sisa kredensial proxy di workspace).

## 10. Yang TIDAK dilakukan (sesuai perintah)

Tidak ada perubahan kode, tidak ada perbaikan kebocoran,
tidak ada packaging, tidak ada panggilan Hermes, tidak ada
yang berbayar.
