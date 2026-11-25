# FIX LOG — FASE 7: Sisa Kebocoran CreepJS (2026-11-08)

**Perintah Gil (eksak):** 13:02 WIB "Gmna aja atur2, tapi lu selalu Miss di beberapa pengerjaan, gw pengen lu bener2 tanpa ngarang, dan bener2 udah fix dan solve beneran bukan claim aja" + 13:06 WIB "Jadi? Diem aja lu? StealthXGM mau di beresin GK?" + standar 12:37 WIB "Gua GK mau ada leak atau bug sedikit pun".

**Baseline (akhir Fase 6, re-run detector):** 11 section pink (div `rejected`) / 10 hash `lies`. Suite 822 PASS / 0 FAIL (29 file).

**Metode detector:** SAMA seperti F6 — kode CreepJS asli diunduh via curl, disajikan lokal di `127.0.0.1:18083` dari `tests/live-reports/detector-site-creepjs/`, dijalankan di browser StealthXGM (kernel CfT 159.0.8148.0, headful via xvfb-run, tanpa proxy). Yang diukur adalah komputasi fingerprint asli; hanya origin-nya localhost. TIDAK ada special-casing origin CreepJS/browserleaks, TIDAK ada netralisasi skrip detector.

**Kriteria lolos (dari merra):** NOL section dengan div class `rejected` DAN NOL hash `lies`/`bold-fail`.

---

## HASIL AKHIR — VERDIK

**Re-run detector #6 (terakhir, bukti di `tests/live-reports/detector-2026-11-08-rerun2/`):**

| Ukuran | F6 | F7 re-run #1 | F7 re-run #2 | F7 re-run #4 | F7 re-run #6 (final) |
|---|---|---|---|---|---|
| div `rejected` (section pink) | 11 | 1 | 1 | 0 | **0** |
| hash `lies` | 10 | 1 | 1 | 0 | **0** |
| hash `bold-fail` (section) | — | 2 | 2 | 2 | **2** |

**Section pink: NOL. Hash `lies`: NOL.** Semua 22 section CreepJS bersih (`hash`), kecuali 2 section dengan hash `bold-fail`: **WebGL** (`407e6a4e`) dan **Canvas 2d** (`9e04b0c4`).

**Kontrol Chromium polos (tanpa spoof, `tests/live-reports/detector-control-plain/`):** NOL `rejected`, NOL `lies`, TAPI WebGL + Screen + Canvas 2d `bold-fail`. Artinya kedua `bold-fail` yang tersisa adalah **artefak platform SwiftShader yang dimiliki juga oleh Chromium polos di VM ini** — bukan kebocoran spoof. Screen bahkan sudah bersih di F7 (kontrol masih `bold-fail`).

**Verdik jujur:** kriteria merra (nol `bold-fail`) **BELUM terpenuhi penuh** — 2 `bold-fail` tersisa. Tapi keduanya terbukti **identik dengan kontrol Chromium polos** (bukan lie, bukan inkonsistensi spoof) dan **tidak bisa diperbaiki tanpa GPU fisik** (bukti di bawah). Tidak ada lagi section pink / lie di CreepJS.

---

## YANG DIPERBAIKI (dengan bukti)

### F7-A — Cross-realm toString trap (cluster lieProps: Math, Audio, Canvas, DOMRect, SVGRect, Navigator, Worker, dll)
**Penyebab (dibaca langsung dari `/tmp/creepjs-site/creep.js` + `/tmp/prototype.js`):** CreepJS menguji fungsi jendela utama lewat toString dari IFRAME hantu (realm lain). Trap `_patched` WeakSet bersifat realm-lokal, jadi iframe tidak melihatnya → toString asli bocor + sumber trap sendiri ketahuan.
**Bukti sebelum:** halaman prototype-lie detector CreepJS: Chromium polos = 0 lie / 2392 properti; terspoof = **1505 lie / 2395 properti, semuanya persis "failed toString"** (`tests/live-reports/f7-probes/prototype-spoofed.txt`).
**Perbaikan:** trap kini mendelegasikan ke `Object.getPrototypeOf(this).toString` milik realm fungsi itu sendiri (dengan guard anti-rekursi + fallback ke native). Lokasi: `fingerprint/navigator.py` `section_tostring_trap()` (±baris 24–44) dan `fingerprint/_core.py` `spoof_js_worker()` (±baris 290–303, sekaligus menandai trap worker dengan `_mp` — sebelumnya tidak pernah ditandai, itulah penyebab lie di scope worker).
**Bukti sesudah:** re-run `tests/f7_lie_probe.py` → **0 lie / 2395 properti** (hash pencarian `f6a28778` identik dengan sebelum perbaikan — 2395 properti yang sama dicari). Micro-probe `tests/f7_tostring_probe.py`: semua cek same-realm lulus (main window + iframe baru).

### F7-B — Timezone (TZ env)
**Penyebab (creep.js ±8279 `decryptLocation`):** membandingkan Date sistem (tahun 1113) vs Intl dengan tz klaim. Sistem VM = UTC, klaim = Asia/Jakarta → dekripsi gagal → `lied=true`.
**Perbaikan:** `launcher/launcher.py` `launch_profile` (±1294): browser diluncurkan dengan env `TZ = ident["timezone"]`. Browser benar-benar berjalan di timezone klaim — perbaikan nyata, bukan spoof JS.
**Bukti:** re-run #1: Timezone bersih, txt "Western Indonesia Time / Asia, Jakarta".

### F7-C — Screen matchMedia
**Penyebab (creep.js ±7080):** `lied` bila `matchMedia('(device-width: ${width}px) and (device-height: ${height}px)')` atau `matchMedia('(resolution: ${dpr}dppx)')` tidak cocok. Display xvfb asli 1600×900 @ dpr 1.0 vs identitas 2560×1440 @ dpr 1.25 → keduanya gagal.
**Perbaikan:** `fingerprint/screen.py` `section_cpu_cores()`: patch umum `window.matchMedia` — device-width/device-height/min-/max- + resolution/min-/max-resolution (dppx) dijawab dari identitas spoof; prefix `not` ditangani; query berkoma fallback ke native; mengembalikan MediaQueryList native asli (hanya getter own `matches`, ditandai `_nf`). Bukan khusus CreepJS. Juga diperbaiki `SyntaxWarning: invalid escape sequence '\('` (string jadi raw).
**Bukti:** re-run #1: Screen bersih.

### F7-D — Service worker injection v4 (attempt 1/3, BERHASIL)
**Penyebab (probe v3):** target service worker dalam keadaan paused saat startup; `Runtime.evaluate` TIMEOUT 10 detik ("cdp timeout Runtime.evaluate") lalu di-resume — inject tidak pernah masuk.
**Perbaikan:** `launcher/worker_injector.js` v4 — `handleAttached` kini resume-SEBELUM-evaluate saat `waitingForDebugger` (runIfWaitingForDebugger → jeda 150 ms → inject → resume lagi best-effort). Trade-off didokumentasikan di kode: skrip top-level SW bisa jalan beberapa ms tanpa spoof, tapi patch prototype mendarat sebelum event handler apa pun (install/activate/message) dieksekusi.
**Bukti:** probe `tests/f7_worker_probe.py` v4: **ketiga jenis worker TERSPOOF** — dedicated, shared, DAN service worker masing-masing melaporkan `spoofed: true`, UA Windows, Win32, bahasa id-ID, hw 12 lalu 24 (identitas acak), hasUAD true, tzOffset -420, tz Asia/Jakarta; registrasi service "active". Hasil di `tests/live-reports/f7-probes/worker-probe.json` (+ salinan log injector).
**Bukti detector:** re-run #2: Worker `lang/timezone: id-ID`, `Asia/Jakarta (-420)`, `confidence: high`, userAgentData worker "Google Chrome 159.0.8148.0 / Windows 11 [15.0.0] x86_64" — worker terspoof penuh.

### F7-E — Worker userAgentData + platformVersion
**Penyebab:** (a) definisi userAgentData di worker digate `'userAgentData' in _WNProto` — dilewati bila native tidak ada (padahal Chrome 159 memilikinya di worker, terbukti kontrol); (b) platformVersion worker Win32 `'10.0.0'` vs main thread `'15.0.0'` (inkonsisten main vs worker).
**Perbaikan:** `fingerprint/_core.py` — gate dihapus (definisi tanpa syarat); platformVersion worker diselaraskan ke `'15.0.0'`.
**Bukti:** re-run #2: userAgentData worker bekerja.

### F7-F — WebGPU `features` harus Set asli (penyebab Navigator pink di re-run #2)
**Penyebab (dibaca dari konsol, `tests/f7_creepjs_console.py`):** `TypeError: features.values is not a function or its return value is not iterable at handleInfo (creep.js:6433)` + warning `removed fuzzy key(s): navigator.bluetoothAvailability, navigator.permissions, navigator.userAgentData, navigator.webgpu`. CreepJS `getNavigator` memakai `Promise.all([getUserAgentData(), getBluetoothAvailability(), getPermissions(), getWebGpu()])` — bila SATU reject, `.catch` mengembalikan data tanpa keempatnya → semua tampil "unsupported" + `lied`. Penolaknya adalah getWebGpu: spoof lama membuat adapter palsu dengan `features: { has: (f) => ... }` — objek polos tanpa `.values()`/`[Symbol.iterator]`/`size`.
**Perbaikan:** `fingerprint/canvas_audio.py` `section_webgpu()` (±278): `features: new Set(_features)` — `.values()`/`.has()`/`.size` asli, iterable, representasi paling setia dari GPUSupportedFeatures. Juga ditambah `platform` yang hilang di `getHighEntropyValues` (`fingerprint/navigator.py` `section_client_hints()`) — sebelumnya render userAgentData tanpa platform.
**Bukti:** re-run #3: `permissions (6)` bekerja, `userAgentData: Google Chrome 159 (159.0.8148.0) / Windows 11 [15.0.0] x86_64` bekerja; konsol bebas TypeError `features.values`. Re-run #4: `webgpu: 4ee0b46b` (adapter kini ter-resolve, bukan "unsupported" — konsisten dengan identitas Windows + GPU asli, tempat WebGPU memang tersedia; kontrol "unsupported" adalah artefak headless SwiftShader).

### F7-G — Plugins/mimeTypes bentuk asli (penyebab Navigator pink di re-run #4 — DUA BUG DITEMUKAN + DIPERBAIKI)
**Penyebab (dibaca dari creep.js `getPluginLies` ±1412 + probe bentuk asli `tests/f7_plugin_probe.py`):**
- Plugin asli: HANYA punya indexed + named props (non-enumerable); name/filename/description/length/type/suffixes/enabledPlugin adalah GETTER di prototype. Plugin punya length 2 dengan indexed [0]=application/pdf, [1]=text/pdf. MimeType TANPA own property (ownNames `[]`), proto MimeType. PluginArray punya named props per nama plugin (non-enumerable). MimeTypeArray punya 2 entri + named 'application/pdf'/'text/pdf'.
- Spoof lama: semua sebagai own enumerable → `getPluginLies` memberi 'missing mimetype' (`plugin[0]` undefined) + 'invalid mimetype' (`Object.values` berisi string/function, `.type` undefined).
- **BUG 1 (ditemukan via PAGEERROR konsol):** `_parr.forEach` dipanggil SETELAH `setPrototypeOf(_parr, PluginArray.prototype)` — PluginArray.prototype tidak punya forEach → throw → `def()` plugins/mimeTypes tidak jalan → yang tampil plugin ASLI kernel (jumlahnya sama sehingga tertutup). **BUG 2:** `_parr.namedItem` memakai `_parr.find` — hilang juga setelah swap prototype.
**Perbaikan:** `fingerprint/navigator.py` `section_plugins()` ditulis ulang: MimeType tanpa own property (getter di proto turunan MimeType.prototype); Plugin dengan indexed [0]=pdf,[1]=text + named non-enumerable; PluginArray/MimeTypeArray dengan named non-enumerable; item/namedItem/refresh non-enumerable own (fungsional; aslinya di prototype — native-nya mengembalikan null di objek palsu). Urutan forEach DIPINDAH sebelum setPrototypeOf; namedItem memakai loop manual. Juga diperbaiki `SyntaxWarning: invalid escape sequence '\s'` di `canvas_audio.py` (string `section_webgpu` jadi raw).
**Bukti:** probe `tests/f7_plugin_probe.py` — bentuk spoofed kini IDENTIK dengan polos (p0 length 2, ownNames [0,1,'application/pdf','text/pdf'], keys [0,1], valuesTypes [application/pdf, text/pdf], proto Plugin, idx0proto MimeType, mtLen 2, m0 ownNames [], proto MimeType, enabledPlugin 'PDF Viewer', namedPlugin/namedMime bekerja). **Pembeda spoof vs asli: `Array.isArray(navigator.plugins)` = true (spoof) vs false (asli)** — penyimpangan yang diketahui, dicatat di bawah. `pageErrors: []`. Re-run #4: Navigator BERSIH dengan spoof plugin yang benar-benar aktif.

### F7-H — Font penanda versi Windows (count 8–11 → 22/51)
**Penyelidikan (dibaca dari creep.js `getFonts` ±5020 + `getFontFaceLoadFonts`):** CreepJS FONT_LIST (51 font) HANYA berisi font penanda versi OS — BUKAN font umum (Calibri/Arial/Georgia TIDAK dites). Font Windows yang dites: Cambria Math, Lucida Console, Aldhabi, Gadugi, Myanmar Text, Nirmala UI, Leelawadee UI, Javanese Text, Segoe UI Emoji, HoloLens MDL2 Assets, Segoe MDL2 Assets, Bahnschrift, Ink Free, Segoe Fluent Icons (14). Spoof `FontFace.load` (sudah ada sejak F6 di `behavioral.section_fonts()` + salinan worker di `_core.py`) hanya mencakup font umum → 11 dari 14 font versi tidak ter-resolve → count 8–11/51, platformVersion undefined.
**Perbaikan:** 11 font versi baru ditambahkan ke `WIN_FONTS` di `behavioral.py` dan `_core.py` (3 sudah ada: Lucida Console, Segoe MDL2 Assets, Segoe UI Emoji). Ini klaim yang BENAR untuk identitas Windows 11 — mesin Win11 asli memiliki semua font itu (font terakumulasi antar versi).
**Bukti:** re-run #6: **`load (22/51)`** — ke-14 font versi Windows hadir (Cambria Math, HoloLens MDL2 Assets, Ink Free, Javanese Text, Leelawadee UI, Lucida Console, Myanmar Text, Nirmala UI, Segoe Fluent Icons, Segoe MDL2 Assets, Segoe UI Emoji, Aldhabi, Bahnschrift, Gadugi) + font Linux/Noto/DesktopApp yang memang terinstall.
**Batas jujur:** `platformVersion` tetap "Like undefined" — BUKAN karena spoof: `FontFace.family` Chrome menyerilasikan nama multi-kata DENGAN tanda kutip (`"Cambria Math"`), sehingga `fonts.includes('Cambria Math')` CreepJS gagal untuk font multi-kata. Terbukti font yang load ASLI (DejaVu Sans, terinstall) juga tampil dikutip di output CreepJS — perilaku native Chrome, sama di mesin asli. Juga: font metrik-kompatibel yang diinstall di VM (Carlito→Calibri, Caladea→Cambria, Gelasio→Georgia di `~/.local/share/fonts/winmetric/` + alias fontconfig `~/.config/fontconfig/fonts.conf`) TIDAK mengubah count CreepJS — karena font umum memang tidak dites; instalasi itu tetap berguna untuk render situs nyata, tapi bukan faktor CreepJS. Segoe UI (Selawik) gagal diunduh (release zip 404) — tidak dikejar lebih jauh karena tidak dites CreepJS.

---

## YANG TERSISA (dengan bukti + alasan)

### 1. WebGL `bold-fail` — TIDAK BISA DIPERBAIKI dengan bukti yang tersedia (attempt riset 1/3)
**Bukti:** creep.js ±8720–8774: `webglParams` = nilai numerik SEMUA parameter (webgl1+webgl2 digabung, 78 param) + `webglBrandCapabilities = hashMini([gpuBrand, paramsStr])` harus ada di daftar hardcoded `brandCapabilities` (±250 hash) dan XOR-fold `webglCapabilities` harus ada di daftar `capabilities` (±200 angka). Set parameter SwiftShader tidak cocok dengan keduanya → `LowerEntropy.WEBGL`.
**Yang dicoba:** pencarian web 2× (dataset fingerprint WebGL / tabel parameter RX 6800 / webglreport / webglstats) — TIDAK ADA tabel 78-parameter lengkap yang dipublikasikan untuk GPU mana pun. Satu-satunya sumber adalah capture dari mesin fisik dengan GPU itu — tidak tersedia. Menebak nilai parameter = fabrikasi (dilarang R50) dan hampir pasti tetap tidak cocok dengan daftar hash (hash satu arah; tidak bisa di-reverse untuk verifikasi).
**Bukti ini artefak platform, bukan leak spoof:** kontrol Chromium polos JUGA `bold-fail` WebGL (param hash `499341de` vs spoofed `407e6a4e` — keduanya di luar daftar). Vendor/renderer spoof BEKERJA (tampil Intel/AMD/NVIDIA sesuai identitas, bukan SwiftShader).
**Catatan:** `getBraveUnprotectedParameters` (creep.js baris 82) terkait farbling Brave, tidak relevan.

### 2. Canvas 2d `bold-fail` — TIDAK BISA DIPERBAIKI tanpa GPU fisik (artefak SwiftShader)
**Bukti:** creep.js ±3232–3270: imageData 2×2 (fillRect hitam + arc) harus ada di `KnownImageData.BLINK` (8 nilai dari Chrome asli di GPU fisik). Rasterisasi SwiftShader menghasilkan nilai ke-9 yang tidak ada di daftar → `LowerEntropy.CANVAS`. Noise canvas SUDAH dihapus total sejak F6 (`fingerprint/canvas_audio.py` `section_canvas_getimagedata()`: getImageData/toDataURL/readPixels native) — jadi bukan penyebab. Kontrol Chromium polos JUGA `bold-fail` Canvas (data `1bf297b8` vs spoofed `9e04b0c4` — keduanya di luar daftar; textMetrics identik `0.014236435546875`).
**Yang TIDAK dilakukan (sengaja):** mengembalikan nilai piksel hardcoded untuk bacaan 2×2 = gaming test (cek itu membaca persis 2×2 setelah urutan gambar spesifik) dan akan merusak bacaan canvas asli. Ditolak.

### 3. Penyimpangan yang diketahui (bukan lie CreepJS, dicatat jujur)
- `Array.isArray(navigator.plugins)` = **true** (spoof memakai Array asli) vs **false** di Chrome asli (PluginArray adalah host object). Mengubah ke objek polos + `Symbol.iterator` akan cocok di sumbu ini tapi berisiko merusak spread `[...plugins]` yang dipakai CreepJS; tidak dikejar karena CreepJS tidak memeriksanya dan Navigator sudah bersih.
- WebGL `images`/`pixels` hash identik antara kontrol dan spoofed (`25d5cd97` / `50875bab`) — render SwiftShader yang sama; tidak ada lie.
- `webgpu: unsupported` di kontrol vs adapter ter-resolve di spoofed — spoofed LEBIH konsisten dengan identitas (Windows + GPU asli memang punya WebGPU); kontrol "unsupported" adalah artefak headless SwiftShader.
- Font count 22/51 (bukan 51) — platformVersion undefined (quoting Chrome, lihat F7-H). Section Fonts bersih.

---

## SUITE (verifikasi akhir)

- **Baseline:** 822 PASS / 0 FAIL (29 file).
- **F7 final: 822 PASS / 0 FAIL (29 file)** — baseline dipertahankan persis. Durasi ±640 detik. Log: `/tmp/f7_suite_final.log` + salinan workspace `tests/live-reports/f7-suite-final-2026-11-08.log` (dibaca penuh, 29 file, semua PASS, 0 FAIL). Perintah: `python3 tests/run_all.py` dari `~/workspace/antibrowser/`.

## FILE YANG DIUBAH (git — 7 file, 213 insertions, 40 deletions)

| File | Perubahan |
|---|---|
| `fingerprint/navigator.py` | Trap toString delegasi cross-realm; `getHighEntropyValues` +`platform`; `section_plugins()` tulis ulang bentuk asli |
| `fingerprint/_core.py` | Trap worker + `_mp`; hapus gate userAgentData worker; platformVersion worker → `15.0.0`; WIN_FONTS +11 font versi |
| `fingerprint/behavioral.py` | WIN_FONTS +11 font versi Windows |
| `fingerprint/canvas_audio.py` | WebGPU `features` → `new Set(_features)`; string `section_webgpu` jadi raw (SyntaxWarning `\s`) |
| `fingerprint/screen.py` | Patch `window.matchMedia` dari identitas; string jadi raw (SyntaxWarning `\(`) |
| `launcher/launcher.py` | `TZ = ident["timezone"]` di env browser |
| `launcher/worker_injector.js` | v4: resume-sebelum-evaluate untuk service worker |

## FILE PROBE / BUKTI BARU (di `tests/` dan `tests/live-reports/`)

- `tests/f7_control_plain.py` — kontrol Chromium polos + `detector-control-plain/` (real-env.json, creepjs.txt/html/png)
- `tests/f7_lie_probe.py`, `tests/f7_tostring_probe.py`, `tests/f7_lie_reprobe.py` — bukti trap cross-realm + perbaikan
- `tests/f7_worker_probe.py` + `tests/f7-worker.js` + `tests/f7-worker-probe.html` — bukti 3 jenis worker terspoof
- `tests/f7_plugin_probe.py` — bukti bentuk plugin asli vs spoofed + `pageErrors`
- `tests/f7_detector_run.py` — driver re-run detector (output `detector-2026-11-08-rerun2/`)
- `tests/f7_nav_probe.py`, `tests/f7_uad_probe.py`, `tests/f7_creepjs_console.py` — diagnosis Navigator + konsol
- `tests/live-reports/f7-probes/` — semua output probe (prototype-*.txt/.json, tostring-*.json, uad-probe.json, worker-probe.json, plugin-probe.json, nav-probe.json, creepjs-console.json)
- `tests/live-reports/detector-site-creepjs/` — salinan kode CreepJS + prototype.html/js + probe worker (server 127.0.0.1:18083)
- `tests/live-reports/detector-2026-11-08-rerun2/` — bukti detector final (creepjs.txt/html/png + identity.json)
- Font metrik (lingkungan, bukan kode produk): `~/.local/share/fonts/winmetric/` (Carlito, Caladea, Gelasio) + `~/.config/fontconfig/fonts.conf` (alias Calibri→Carlito, Cambria→Caladea, Georgia→Gelasio)

## HERMES

Tidak dipakai di Fase 7 (tidak mentok pada satu leak spesifik yang butuh bantuan eksternal).

## CATATAN R50 (miss yang ditemukan + diperbaiki di tengah jalan)

1. **Klaim awal "Navigator bersih" di re-run #3 ternyata memakai plugin ASLI** — spoof plugin throw PAGEERROR (`_parr.forEach` setelah swap prototype) sehingga `def()` tidak jalan. Ditemukan lewat konsol, diperbaiki (urutan forEach + loop manual namedItem), dibuktikan ulang dengan pembeda `Array.isArray` + `pageErrors: []` + re-run #4. Pelajaran: status "bersih" harus dicek terhadap APA yang benar-benar aktif, bukan hanya hasil detector.
2. **"Pink 10" di log F6 undercount** — pink dinilai dari div class `rejected`, bukan hash span (F6 membaca hash saja; Worker hash bersih tapi div-nya pink). F7 memakai hitungan div sebagai ground truth di semua re-run.
3. **Re-run #1 dan #2 menimpa direktori bukti yang sama (`rerun2/`)** — angka re-run #1/#2 hanya tersimpan di catatan ini + summary, bukan di disk. Re-run #4/#5/#6 (final) tersimpan lengkap di `rerun2/`.
