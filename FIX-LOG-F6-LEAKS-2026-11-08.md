# FIX LOG — F6: Perbaikan Kebocoran Fingerprint (Detector Test)

**Tanggal:** 2026-11-08 · **Perintah Gil:** "Gas, perbaiki kebocorannya" (10:55 WIB) ·
" Kalo susah minta bantuan hermes" (11:51 WIB)
**Repo:** `~/workspace/antibrowser/` (master lokal) · **Baseline:** CreepJS TIDAK LOLOS
(`DETECTOR-TEST-2026-11-08.md`, bukti `tests/live-reports/detector-2026-11-08/`)
**Suite baseline:** 822 PASS / 0 FAIL (Fase 5)

## Ringkasan + verdict

**Verdict: BELUM LOLOS CreepJS, tapi membaik di semua jalur yang bisa diukur.**

- Suite: **822 PASS / 0 FAIL** (final, `/tmp/f6_suite_final5.log`, 552 detik).
- Lie harness (queryLies asli CreepJS, 71 API): **14/71 — semuanya artefak harness,
  0 lie nyata** (sama seperti sebelum F6; kontrol Chromium polos: 18 artefak).
- Detector re-run final (CreepJS asli, disajikan lokal 127.0.0.1:18083, headful xvfb,
  identitas baru 2560×1440 / dpr 1.25 / Asia/Jakarta / AMD RX 6800 / 12 core / 4 GB):
  section pink 10 (baseline juga 10) — **tapi komposisinya berubah**:
  - **Bersih sekarang:** Speech (dulu pink), Worker (data kini terspoof penuh),
    Intl, Headless, Resistance, Media, CSS Media, Computed Style, Error,
    Window, HTMLElement.
  - **Masih pink:** Timezone, Screen, Canvas 2d, Fonts, DOMRect*, SVGRect*,
    Audio, Math, Navigator, WebGL* (*baru muncul karena WebGL kini hidup).
  - \* DOMRect/SVGRect = **bukan leak** (Chromium polos memberi diff identik —
    sudah dibuktikan di F6 awal; jangan tambah jitter).
  - \* WebGL pink **baru** — sebelumnya WebGL mati total (tidak ada section);
    kini hidup + spoof berlaku, tapi CreepJS mendeteksi params/ext SwiftShader
    tidak cocok dengan GPU AMD yang diklaim (lihat §4).

## Perbaikan per leak

### 1. Worker tidak ikut di-spoof — SEBAGIAN BERES (dedicated + shared ✅, service worker ❌)
- **Mekanisme:** `launcher/worker_injector.js` **v2 → v3** (baru) + `spoof_js_worker()`
  di `fingerprint/_core.py`. v2: page-session `Target.setAutoAttach`
  (`waitForDebuggerOnStart`) + explicit attach fallback (`targetCreated`).
  v3: + polling `Target.getTargets` tiap 2 detik + resume eksplisit
  (`Runtime.runIfWaitingForDebugger`) setelah inject.
- **Bukti beres (dedicated/shared):** probe dedicated worker F6 awal — semua field
  cocok main thread. Detector re-run final: CreepJS memakai **SharedWorkerGlobalScope**
  dan datanya **terspoof penuh**: `id-ID`, `Asia/Jakarta`, `Windows (Win32)`,
  `Windows 10 (64-bit)`, `cores: 12, ram: 4`, GPU `ANGLE (AMD, AMD Radeon RX 6800…)`,
  UA Windows. Section Worker **tidak pink** (`f383ceec`, class `hash`).
- **Service worker TIDAK beres (3 attempt habis, dilaporkan unresolved):**
  v1 browser-level autoAttach → tidak tangkap dedicated worker.
  v2 page-session autoAttach + explicit → dedicated worker beres, tapi service
  worker CreepJS tetap Linux (en-US/UTC/X11/4 core) dan tidak ada log inject
  setelah page load.
  v3 polling + resume → **tidak memperbaiki**: probe `swtest.js` membuktikan
  target service worker ADA di `/json/list` tapi registrasi tanpa
  active/installing/waiting, page hang di `serviceWorker.ready`; Chromium polos:
  worker yang sama aktif normal. Jadi injector-lah yang membuat service worker
  macet (kemungkinan ter-pause oleh page-session autoAttach tanpa resume, atau
  `Runtime.evaluate` hang di worker yang ter-pause — `runIfWaitingForDebugger`
  di v3 dipanggil SETELAH evaluate, jadi tidak menolong bila evaluate-nya yang
  hang). **Hipotesis perbaikan berikutnya (belum dicoba, butuh perintah baru):
  panggil `runIfWaitingForDebugger` SEBELUM `Runtime.evaluate` di explicitWorker.**
  - Dampak praktis terbatas: CreepJS gagal di jalur service worker lalu **fallback
    ke shared/dedicated worker yang terspoof**, jadi section Worker tetap bersih.
    Tapi situs yang KERAS memakai service worker (dan tidak fallback) masih
    bisa melihat Linux.
- **Hermes:** 1 panggilan untuk item ini (2026-11-08 ~05:38 WIB, prompt Inggris,
  minta tulis ke `/tmp/f6_hermes_serviceworker.md`) → **gagal: rate-limited**
  (`gpt-6.1-sol` token rate limit, eastus2). Tidak retry (sesuai aturan).
  File temuan Hermes tidak terbentuk.

### 2. Font Linux di mesin "Windows" — MEMBAIK, BELUM TUNTAS
- **Mekanisme:** `FontFace.load` di-override agar font yang diklaim OS Windows
  resolve (sebelumnya `document.fonts.check()` saja tidak cukup — Chromium polos
  pun return true untuk font acak).
- **Bukti:** CreepJS Fonts `load (11/51)` (baseline 8/51). Daftar kini memuat
  `Segoe MDL2 Assets` dan `Segoe UI Emoji` (font Windows) di samping DejaVu /
  Liberation / Noto. Section tetap pink — deteksi berbasis **pengukuran**
  (bukan `check()`) hanya menemukan 11/51 karena sistem Linux memang tidak
  punya font Windows. Perbaikan penuh butuh font Windows terinstal atau
  pemalsuan hasil pengukuran (belum dikerjakan).

### 3. Sinyal headless — MEMBAIK
- **Bukti:** CreepJS Headless: `chromium: true`, **31% like headless / 33% headless /
  20% stealth** (baseline 38% / 33% / 40%). `chromium: true` tetap (tidak bisa
  dihilangkan tanpa mengubah binary). Section **tidak pink**.

### 4. WebGL mati total — BERES (hidup + spoof), tapi kini pink karena params
- **Mekanisme:** `--enable-unsafe-swiftshader` di `build_launch_args`
  (`launcher/launcher.py`) + **F6-rev: `--use-gl=angle --use-angle=swiftshader`**.
  Flag pertama saja tidak cukup di **headful** (xvfb): `getContext('webgl')`
  tetap null karena headful Chrome coba GL via display X dan tidak fallback.
  Dua flag tambahan memaksa ANGLE ke backend SwiftShader.
- **Bukti:** probe langsung kernel 159 — headless: WebGL true (AMD RX 6700 XT);
  **headful xvfb: WebGL true (NVIDIA RTX 3060 Ti)**, spoof vendor/renderer berlaku.
  Detector re-run final: section WebGL kini ada dan hidup — worker WebGL
  `images / pixels / params (78) / exts (56)`, GPU `AMD Radeon RX 6800`.
- **Catatan jujur:** section WebGL kini **pink** (`0a5981a2`). Penyebab: params
  (`MAX_TEXTURE_SIZE` dll) dan daftar extension berasal dari SwiftShader, tidak
  cocok dengan GPU AMD yang diklaim — spoof saat ini hanya menimpa
  `UNMASKED_VENDOR/RENDERER` (via `WEBGL_debug_renderer_info`), bukan
  `getParameter`/`getSupportedExtensions`. WebGL hidup tetap lebih baik daripada
  mati (browser asli hampir selalu punya WebGL), tapi params mismatch ini butuh
  pemalsuan params/ext per-GPU (pekerjaan lanjutan, belum dikerjakan).

### 5. Noise canvas terukur 6% rgba — MEMBAIK (hash berubah, tetap pink)
- **Mekanisme:** noise piksel (`getImageData`/`toDataURL`/`toBlob`/`readPixels`)
  **dihapus**; diganti offset `fillText`/`strokeText` ±1px (`rnd()*2.0`, seed sama
  main+worker) — variansi rendering, bukan noise piksel.
- **Bukti:** hash canvas CreepJS berubah tiap perbaikan (baseline `9342d82a` →
  re-run#2 `1e349978` → final `65a8bf73`); `test_p16_consistency` — hash sama
  antar launch profil sama, beda antar profil. Section tetap pink — CreepJS
  masih mendeteksi inkonsistensi (kemungkinan textMetrics atau pola offset).
  Belum tuntas.

### 6. DOMRect/SVGRect A/B identik persis — BUKAN LEAK (tidak diubah)
- **Bukti F6 awal:** Chromium polos memberi diff A/B yang identik persis dengan
  StealthXGM. Menambah jitter justru akan MENAMBAH lie (real browser tidak
  berjitter di sini). Section tetap pink di CreepJS, tapi itu **artefak
  CreepJS vs Chromium**, bukan kebocoran StealthXGM. Tidak ada perubahan kode.

### 7. Intl en-US vs navigator id-ID — BERES
- **Mekanisme:** `Intl` di-wrap untuk SEMUA constructor (locale LOCALE + TZ).
- **Bukti:** CreepJS Intl kini `id-ID,id`, `Juli pukul Waktu Indonesia Barat`,
  `21 juta`, `tahun depan` — semua Indonesia, konsisten dengan
  `navigator.language: id-ID`. Section **tidak pink** (`95dcc15f`).

### 8. Math/Error/Window/HTMLElement/Navigator pink — SEBAGIAN
- **Error / Window / HTMLElement: BERES** — tidak pink di re-run final
  (`92b51d39`, `c15678ec`, `6851d566`). Pink di laporan awal ternyata salah
  baca / artefak.
- **Speech: BERES** — tidak pink (`88579ecb`); dulu pink di baseline.
- **Math: MASIH PINK** (`0e6163f8`). Hasil fungsi Math (sin/cos/dll) beda tipis
  antar platform/compiler; spoof tidak mengubah Math (dan mengubah Math akan
  sangat terdeteksi). Kemungkinan tidak bisa diperbaiki tanpa memalsukan Math —
  belum diputuskan.
- **Navigator: MASIH PINK** (`b6d89344`) meski nilai sudah benar (Windows,
  Win32, 12 core, 4 GB, id-ID, UA Windows). Penyebab pasti belum teridentifikasi
  (kandidat: `userAgentData: unsupported` di section Navigator vs terspoof di
  worker; jumlah properti 69). Butuh baca kode check CreepJS lebih dalam.
- **Timezone: MASIH PINK** (`66e454e8`, hash IDENTIK dengan re-run#2 — nilainya
  tidak berubah). `Western Indonesia Time`, offset `Asia/Jakarta` sudah benar,
  tapi ada nilai `-27028684800000` yang mencurigakan di section ini. Penyebab
  pasti belum teridentifikasi.
- **Screen: MASIH PINK** (`995541f7`). Nilai sudah konsisten (2560×1440,
  avail 2560×1400, depth 30|30 = identity `color_depth: 30`, dpr 1.25).
  Penyebab pasti belum teridentifikasi (kandidat: viewport 1600×900 vs screen,
  orientasi). Butuh baca kode check CreepJS.
- **Audio: MASIH PINK** (`f364d606`) meski trap sudah beres — `data == copy`
  (`f5d91537 == f5d91537`) di re-run#2 dan final. Sinyal trap hilang, tapi
  nilai audio (sum/gain/freq) masih ditandai. Penyebab pasti belum
  teridentifikasi.

### 9. devicePixelRatio (blocker suite, ditemukan saat F6) — BERES
- **Masalah:** `fp-check` gagal 5/5 trial — `devicePixelRatio` live 1 padahal
  identitas 1.5, meski getter terpasang di `Window.prototype` (terbukti via
  `rawToString` + panggil getter langsung → 1.5).
- **Akar:** Chrome asli menaruh `devicePixelRatio` sebagai **own property di tiap
  `window`** (terbukti: Chromium polos `hasOwn=true`, `protoHasGet=null`).
  Patch prototype **terbayangi** own property Chrome → tidak pernah terbaca.
- **Perbaikan:** `fingerprint/screen.py` — `def(window, 'devicePixelRatio',
  ident.dpr, Window)` (instance, seperti Chrome asli) dengan `_nf` + receiver
  check; getter prototype dihapus. Lie harness tetap 14/71 (tidak nambah lie).
- **Bukti:** 5/5 trial `dpr=1.5`; `test_p16_consistency` 11/11 PASS.

## Hasil detector per item (baseline → re-run final)

| Item CreepJS | Baseline | Re-run final (2026-11-08, CreepJS rebuild) |
| --- | --- | --- |
| Timezone | pink | **pink** (`66e454e8`) |
| Intl | bersih | **bersih** (`95dcc15f`) |
| Headless | bersih | **bersih** (31%/33%/20%, dulu 38%/33%/40%) |
| Resistance | bersih | **bersih** |
| Worker | bersih (data Linux!) | **bersih — data terspoof** (shared worker: id-ID/Jakarta/Windows/AMD RX 6800/12 core/4 GB) |
| WebGL | mati/blocked (tanpa section) | **pink** (`0a5981a2`) — hidup + spoof, params SwiftShader mismatch |
| Screen | pink | **pink** (`995541f7`) |
| Canvas 2d | pink | **pink** (`e4821814`, hash `65a8bf73`) |
| Fonts | pink (8/51) | **pink** (11/51, Segoe UI muncul) |
| DOMRect | pink | **pink** (bukan leak — Chromium polos identik) |
| SVGRect | pink | **pink** (bukan leak — Chromium polos identik) |
| Audio | pink | **pink** (`f364d606`, trap beres data==copy) |
| Speech | pink | **bersih** (`88579ecb`) |
| Media | bersih | **bersih** |
| CSS Media | bersih | **bersih** |
| Computed Style | bersih | **bersih** |
| Math | pink | **pink** (`0e6163f8`) |
| Error | bersih | **bersih** |
| Window | bersih | **bersih** |
| HTMLElement | bersih | **bersih** |
| Navigator | pink | **pink** (`b6d89344`) |

Bukti re-run final: `tests/live-reports/detector-2026-11-08-rerun/`
(`creepjs.txt` / `creepjs.html` / `creepjs.png` / `identity.json`).
Metode SAMA dengan run pertama (kode CreepJS asli, disajikan lokal
127.0.0.1:18083, headful xvfb, tanpa game-the-test: tidak ada special-case
origin CreepJS, tidak ada blokir/neuter script detector).

## Tes

- **Suite penuh:** 822 PASS / 0 FAIL (29 file, `/tmp/f6_suite_final5.log`,
  552 detik — lebih lambat dari biasa ~300 detik, kemungkinan startup
  SwiftShader; semua tes lolos).
- **Lie harness:** 71 API, 14 dengan lie — **semuanya artefak harness**
  (12× NO-OWN-GETTER navigator/screen, 1× NO-GETTER Navigator.gpu,
  1× ABSENT enumerateDevices), 0 lie nyata. Kontrol Chromium polos: 18 artefak.
- **Probe DPR:** 5/5 trial `dpr=1.5`.
- **Probe WebGL:** headless true (AMD RX 6700 XT), headful xvfb true
  (NVIDIA RTX 3060 Ti) — spoof berlaku di keduanya.
- **Probe service worker (`swtest.js`):** target ADA tapi tidak aktif
  (registrasi tanpa active/installing/waiting); Chromium polos: aktif normal.
- **Probe p16:** 11/11 PASS.

## Yang belum beres (jujur)

1. **Service worker tidak ter-spoof** — 3 attempt habis (v1/v2/v3). Dedicated +
   shared worker beres; service worker macet + tidak ter-inject. Hipotesis
   lanjutan: `runIfWaitingForDebugger` SEBELUM `Runtime.evaluate`.
2. **WebGL params/ext mismatch** — WebGL hidup + spoof vendor/renderer, tapi
   params/extensions masih SwiftShader → CreepJS pink. Butuh spoof
   `getParameter`/`getSupportedExtensions` per-GPU yang diklaim.
3. **Fonts 11/51** — butuh font Windows sungguhan atau pemalsuan pengukuran.
4. **Timezone / Screen / Navigator / Audio / Math / Canvas pink** — penyebab
   pasti belum teridentifikasi; butuh bedah kode check CreepJS per section.
   (Math kemungkinan tidak bisa diperbaiki tanpa memalsukan Math.)
5. **BrowserLeaks tidak di-re-run di pass final** — situs lokal browserleaks
   (port 18084) ikut hilang saat `/tmp` di-wipe; hanya CreepJS yang di-rebuild
   + di-re-run. Hasil browserleaks terakhir (re-run#2): canvas signature
   `E8BE1922442AD76369B7BB428F2315B9`, webgl "disabled" (artefak snapshot statis
   — UA di halaman menunjukkan `curl/8.5.0`, bukan UA browser live).

## Catatan insiden

- **`/tmp` di-wipe di tengah tugas** (setelah suite final): semua probe F6
  (`f6_*.py`), situs detector (`creepjs-site`, `bl-site`), driver
  (`detector_run.py`), dan output detector re-run#2 hilang. Situs CreepJS
  di-rebuild dari `abrahamjuliot.github.io` (fetch curl 200) + driver minimal
  (`/tmp/detector_run2.py`) dan detector di-re-run (re-run final di atas).
  Bukti final disalin ke workspace supaya tahan wipe.
- **Hermes:** 1 panggilan (service worker), rate-limited, tidak retry.
- **Filesystem fault VM:** tidak kambuh selama F6 (semua write lolos), kecuali
  wipe `/tmp` di atas (kemungkinan pembersihan tmp, bukan fault tulis).
- **Tidak ada game-the-test:** tidak ada special-case origin CreepJS/browserleaks,
  tidak ada blokir/neuter script detector, tidak ada deteksi halaman tes.

## File berubah (belum commit saat log ini ditulis)

- `fingerprint/_core.py` — `spoof_js_worker()`, `_nf` class-method, `def()` prototype.
- `fingerprint/navigator.py` — UA/platform/languages/hw/mem di prototype + toString trap.
- `fingerprint/canvas_audio.py` — hapus noise piksel, offset fillText/strokeText ±1px.
- `fingerprint/behavioral.py`, `fingerprint/network.py`, `fingerprint/__init__.py`,
  `fingerprint/screen.py` — prototype getters + **DPR pindah ke instance window**.
- `launcher/launcher.py` — `--enable-unsafe-swiftshader` +
  `--use-gl=angle --use-angle=swiftshader`.
- `launcher/worker_injector.js` (BARU) — v2 → v3 (polling + resume).
