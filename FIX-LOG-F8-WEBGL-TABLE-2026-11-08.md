# FIX-LOG-F8-WEBGL-TABLE-2026-11-08.md

**Fase 8 — WebGL reporting spoof dari tabel terukur (zendriver-stealth RTX 4090)**
**Tanggal:** 2026-11-08 · **Order Gil:** 15:36 WIB "Webgl nya sama canva nya dong"
**Status: SELESAI — WebGL capability checks LOLOS CreepJS; Canvas 2d tetap flagged (out of scope, lihat §6).**
**Suite: 822 PASS / 0 FAIL (29 file).** Attempt: 2 dari maks 3.

---

## 1. Titik awal — temuan Hermes (sudah diverifikasi sendiri, bukan ditelan mentah)

Hermes menjawab 2026-11-08 ~15:52 (`hermes-webgl-canvas-2026-11-08.md`, dibaca merra):
verdict "NOT POSSIBLE as a supported/verified fix on the GPU-less SwiftShader stack" —
**tapi** ada lead nyata: **zendriver-stealth 0.12.7** mempublikasikan capture WebGL RTX 4090
terukur di `https://docs.rs/crate/zendriver-stealth/0.12.7/source/data/gpu-tiers/d3d11-fl11-nvidia.json`
(Chrome 150, Windows 10, ANGLE D3D11). Hermes memverifikasi file-nya ADA, **bukan** asal
hardware-nya. Canvas tidak bisa direkonstruksi dari tabel kapabilitas — **Canvas OUT OF SCOPE**,
jangan disentuh, jangan klaim fixed.

---

## 2. Verifikasi tabel (dilakukan sendiri, bukan atas kata Hermes)

- Crate diunduh dari crates.io: `zendriver-stealth-0.12.7.crate`, **205.750 byte**,
  diekstrak ke `/tmp/zendriver-crate/` (masih ada saat penulisan log ini).
- File `data/gpu-tiers/d3d11-fl11-nvidia.json` — struktur:
  **webgl1: 82 param + 35 ekstensi + 12 presisi; webgl2: 132 param + 32 ekstensi + 12 presisi;
  0 null.**
- Unmasked renderer: `ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 (0x00002684) Direct3D11 vs_5_0 ps_5_0, D3D11)`,
  vendor `Google Inc. (NVIDIA)`; provenance tercatat `probed: Chrome 150.0.7871.186 on Windows 10.0.21996`.
- Sanity-check terhadap nilai NVIDIA/ANGLE yang dikenal — **semua cocok**:
  `MAX_VERTEX_UNIFORM_VECTORS 4095`, `MAX_FRAGMENT_UNIFORM_VECTORS 1024`,
  `MAX_VERTEX_UNIFORM_BLOCKS 12`, `ALIASED_LINE_WIDTH_RANGE [1,1]`,
  `ALIASED_POINT_SIZE_RANGE [1,1024]`, `MAX_VIEWPORT_DIMS [32767,32767]`,
  `MAX_SAMPLES 8`, presisi `HIGH_FLOAT [127,127,23]`, `HIGH_INT [31,30,0]`.
  webgl1 vs webgl2 shared keys: **ZERO diff** (kecuali 3 kunci VersionParam).
- **Caveat jujur:** asal hardware tabel ini TIDAK bisa diverifikasi dari sini — yang
  terverifikasi adalah file-nya ada di crates.io, strukturnya lengkap, dan nilainya
  konsisten dengan pola ANGLE D3D11 yang dikenal. Bukan nilai tebakan.

Tabel ramping yang dipakai: `fingerprint/data/webgl-rtx4090-d3d11.json`
(generator `fingerprint/data/gen_webgl_table.py`; salinan sumber utuh
`fingerprint/data/zendriver-d3d11-fl11-nvidia-source.json` disimpan untuk reproduksibilitas):
webgl1 **24 param kapabilitas / 35 ekstensi**, webgl2 **53 param kapabilitas / 32 ekstensi**,
presisi 12 kombinasi, `extra` `{MAX_TEXTURE_MAX_ANISOTROPY_EXT: 16, MAX_DRAW_BUFFERS_WEBGL: 8}`.

**Param GL STATE yang bisa berubah sengaja DIKECUALIKAN** (stencil mask, blend, viewport/scissor,
pack/unpack, SAMPLES/SAMPLE_BUFFERS, COMPRESSED_TEXTURE_FORMATS — probe menserialisasikannya
sebagai `[]`, native mengembalikan format asli). Men-spoof state yang berubah-ubah = lie yang
gampang ketahuan; yang di-spoof hanya kapabilitas tetap hardware.

---

## 3. Implementasi (git diff: 2 file, +141/−19 — belum di-commit saat log ditulis)

**`fingerprint/canvas_audio.py`**
- Loader baru `webgl_table_js_literal()` (cached; mengembalikan `'null'` bila file hilang —
  fail-safe ke perilaku lama, bukan crash).
- `section_gpu_vendor()` sekarang berkonsultasi ke tabel bila identitas mengklaim RTX 4090
  (gate: `ident.gpu_renderer` mengandung `'RTX 4090'`), mengembalikan nilai tabel termasuk
  cloning typed-array untuk param array (`Int32Array` untuk MAX_VIEWPORT_DIMS 0x0D3A,
  `Float32Array` untuk sisanya), `0x84FF → 16`, `0x8824 → 8`, `0x9245/0x9246 →` string
  unmasked tabel.
- `section_webgl_extensions()` mengembalikan daftar tabel per konteks bila aktif
  (**35/32**), selain itu EXT_COMMON (28).
- `section_webgl_shader()` mengembalikan 12 kombinasi presisi tabel penuh — sekaligus
  **memperbaiki bug lama: HIGH_FLOAT rangeMin tadinya 23, sekarang 127** (sesuai tabel).

**`fingerprint/_core.py`**
- `const _WEBGL4090 = %s;` ditambahkan ke KEDUA header (main: urutan placeholder
  ident/TZ/LOCALE/_WEBGL4090/seed; worker: ident/TZ/LOCALE/seed/_WEBGL4090) + `_args` yang cocok.
- Blok WebGL worker ditulis ulang identik (param/ekstensi/presisi tabel bila aktif,
  selain itu perilaku lama).

**CodeGraph (wajib, sebelum edit):** `explore section_gpu_vendor` + `explore spoof_js_worker`
+ `impact section_gpu_vendor` dibaca dulu — blast radius: spoof_js → build_fingerprint_js →
auto_spoof_js/preview_identity. Tidak ada flag "changed on disk", tidak perlu sync.
Keempat bundle JS hasil generate (4090 + Intel × main + worker) lolos `node --check`.

**Tanpa detector-detection:** spoof berlaku untuk SEMUA situs; gate hanya pada identitas
GPU yang diklaim profil (bukan pada origin/halaman). Tidak ada pengecualian CreepJS/browserleaks.

---

## 4. Probe — attempt 1 GAGAL di satu nilai, attempt 2 LOLOS

Runner `tests/f8_webgl_probe.py`, situs `tests/f8-probe-site/`,
bukti `tests/live-reports/f8-probes/f8-webgl-probe.json` (dibaca langsung).

**Attempt 1 — GAGAL satu nilai:** live `MAX_DRAW_BUFFERS_WEBGL = 6` (native SwiftShader),
bukan 8. Root cause ditemukan lewat probe konstanta langsung: konstanta ekstensi yang benar
adalah **0x8824 (34852), BUKAN 0x8CA8** — 0x8CA8 bukan enum WebGL sungguhan sama sekali
(tidak ada di tabel; asumsi awal agen salah). Diperbaiki 0x8CA8 → 0x8824 di kedua patch.

**Attempt 2 — LOLOS.** Identitas RTX 4090 beku (validate_identity warnings: []):
- **main + worker: 0 mismatch param vs tabel**, ekstensi eksak, presisi eksak, unmasked OK.
- Cek CreepJS yang dihitung live: brandHash **`24306836` IN LIST**,
  XOR fold **`-2147361778` IN LIST**, **WOULD PASS: True** (main dan worker).
- drawBuffers 8, anisotropy 16.
- Fallback Intel (gate MATI; GTX 1650 lalu Arc A380 di re-run): MAX_TEXTURE_SIZE 8192
  (native), unmasked = string identitas, ekstensi 28/28 EXT_COMMON — **gate terbukti tidak
  membocorkan tabel ke GPU lain**.

**Celah yang diketahui (terdokumentasi, bukan regresi):** `getExtension()` mengembalikan null
untuk 5 ekstensi yang terdaftar (webgl1: `KHR_parallel_shader_compile`,
`WEBGL_blend_func_extended`; webgl2: + `EXT_render_snorm`, `EXT_texture_norm16`,
`WEBGL_provoking_vertex`) — SwiftShader tidak mengimplementasikannya. Hal yang sama muncul
di run Intel (KHR_parallel_shader_compile null bahkan dengan EXT_COMMON; ekstensi core
webgl2 null di main thread) — jadi ini perilaku Chrome/SwiftShader yang sudah ada,
bukan regresi. CreepJS tidak memeriksa konsistensi daftar-vs-getExtension.

---

## 5. Detector re-run #4 — CreepJS (metode sama seperti F6/F7/F7B: kode detector asli di-serve lokal)

Runner `tests/f8_detector_run.py`, profil `detector-test3`, identitas RTX 4090 beku
(2560×1440, dpr 1.25, hw 24, mem 8, Win32), server CreepJS di-restart di port 18083.
Bukti: `tests/live-reports/detector-2026-11-08-rerun4/` (creepjs.txt/html/png + identity.json).

Hasil (dibaca langsung dari `creepjs.txt` + `creepjs.html`):
- div `class="rejected"`: **0** · span `class="lies"`: **0** · bold-fail total: **11**
  (rerun3 F7B juga 11 — jumlah sama, komposisi berubah).
- **params (78): 54cf9774 · exts (67): 096fe525** (sebelumnya 56) · WebGL hash `014a71b6`.
- Worker: string RTX 4090, confidence high, `id-ID (1 Dolar Amerika Serikat)`,
  `Asia/Jakarta (-420)` — flag worker F7B tetap bersih.
- **Section yang flagged: HANYA WebGL + Canvas 2d.** 19 dari 21 section bersih
  (Timezone, Intl, Headless, Resistance, Worker, Screen, Fonts, DOMRect, SVGRect, Audio,
  Speech, Media, CSS Media Queries, Computed Style, Math, Error, Window, HTMLElement, Navigator).
- Modal WebGL di `creepjs.html` baris 300 memuat nilai-nilai tabel secara harfiah:
  `MAX_TEXTURE_SIZE: 16384`, `MAX_DRAW_BUFFERS: 8`, `MAX_DRAW_BUFFERS_WEBGL: 8`,
  `MAX_TEXTURE_MAX_ANISOTROPY_EXT: 16`, `UNMASKED_RENDERER_WEBGL: ANGLE (NVIDIA, NVIDIA
  GeForce RTX 4090 (0x00002684) Direct3D11 vs_5_0 ps_5_0, D3D11)`,
  `HIGH_FLOAT rangeMin 127 / rangeMax 127 / precision 23`, `MAX_VIEWPORT_DIMS: 32767,32767`,
  `MAX_VERTEX_UNIFORM_VECTORS: 4095`, `MAX_FRAGMENT_UNIFORM_VECTORS: 1024`,
  `MAX_SAMPLES: 8`, `MAX_COLOR_ATTACHMENTS: 8`,
  `MAX_COMBINED_VERTEX_UNIFORM_COMPONENTS: 212988`,
  `MAX_COMBINED_FRAGMENT_UNIFORM_COMPONENTS: 200704`,
  `MAX_ELEMENT_INDEX: 4294967294`, `MAX_3D_TEXTURE_SIZE: 2048`, `antialias: true`,
  `SHADING_LANGUAGE_VERSION: WebGL GLSL ES 3.00`.

### Interpretasi jujur — span WebGL masih bold-fail, TAPI cek WebGL-nya sendiri LOLOS

Kode render CreepJS (dibaca dari salinan lokal `tests/live-reports/detector-site-creepjs/creep.js`,
~8710–8790): class span hash WebGL adalah
`${lied? 'lies ': (LowerEntropy.CANVAS || LowerEntropy.WEBGL)? 'bold-fail ': ''}` —
**bold-fail muncul bila CANVAS *atau* WEBGL flagged.** Karena Canvas 2d masih flagged
(lihat §6), span WebGL ikut bold-fail walau WebGL-nya bersih.

Bukti cek WebGL-nya bersih (bukan asumsi): 53 param dari modal HTML rerun4 + presisi shader
(23/23/0) + antialias=true, dimasukkan lewat `hashMini` ASLI dari creep.js di Node,
menghasilkan **`24306836` (in list)** dan XOR **`-2147361778` (in list)** →
`hasSusGpu = false` dan `hasSusCapabilities = false` → **`LowerEntropy.WEBGL = false`**.

Jadi: **WebGL FIXED pada level yang bisa diukur CreepJS** (capability/brand checks lolos);
yang tersisa di layar adalah label bold-fail bersama yang diwarisi dari Canvas.

---

## 6. Canvas 2d — TETAP FLAGGED, OUT OF SCOPE (sesuai perintah)

- Canvas 2d hash berubah `9e04b0c4 → 9fc93baa` hanya karena profil/seed berbeda
  (offset sub-pixel teks diturunkan dari seed) — **tetap flagged**.
- Alasan (sudah disampaikan Hermes, diverifikasi logikanya): piksel Canvas dirender
  SwiftShader (CPU rasterizer); tidak ada tabel GPU→piksel yang diterbitkan;
  meng-hardcode piksel = gaming the test, ditolak. Canvas tidak disentuh sama sekali di F8.
- Sisa bold-fail inline lainnya: digit Audio sum (`7`,`7`,`6`,…) — identik dengan kontrol
  Chromium polos (artefak lingkungan, bukan spoof lie).

---

## 7. Suite — tetap hijau

`python3 tests/run_all.py` — **822 PASS / 0 FAIL (29 file)**, exit 0, ~348 detik.
Log: `/tmp/f8_suite_final.log` + salinan `tests/live-reports/f8-suite-final-2026-11-08.log`
(dibaca langsung: 30 baris "PASS" = 29 file + baris TOTAL; nol baris FAIL/ERROR).

---

## 8. Inkonsistensi yang diketahui, belum diperbaiki (di luar scope F8)

- **WebGPU vs WebGL:** section WebGPU meng-hardcode `_wDevice = '0x2704'` untuk NVIDIA
  (0x2704 = PCI ID RTX 4080) sementara WebGL sekarang melaporkan RTX 4090 `0x2684` —
  mismatch lintas API yang sudah ada sebelumnya. Pekerjaan lanjutan.
- 5 ekstensi `getExtension()` null (lihat §4) — perilaku SwiftShader, bukan regresi.

---

## 9. Ringkasan

| Item | Status |
|---|---|
| Tabel RTX 4090 (zendriver-stealth 0.12.7) | Terverifikasi: file ada, struktur lengkap, nilai konsisten ANGLE D3D11; asal hardware tidak terverifikasi |
| Spoof getParameter / getSupportedExtensions / getShaderPrecisionFormat | Implementasi, main + worker, gate identitas RTX 4090, tanpa detector-detection |
| Probe attempt 1 | Gagal 1 nilai (enum 0x8CA8 salah) → diperbaiki ke 0x8824 |
| Probe attempt 2 | LOLOS: 0 mismatch, brandHash + XOR CreepJS IN LIST |
| CreepJS re-run #4 | 0 rejected, 0 lies, params 78, exts 67; cek WebGL LOLOS (LowerEntropy.WEBGL = false); span bold-fail diwarisi dari Canvas |
| Canvas 2d | Tetap flagged (9fc93baa) — out of scope, SwiftShader |
| Suite | 822/0 (29 file) |
| Hermes | TIDAK dipakai di F8 (lead-nya sudah ada dari panggilan merra; tidak ada yang mentok) |
