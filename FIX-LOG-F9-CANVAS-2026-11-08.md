# FIX-LOG-F9-CANVAS-2026-11-08.md

**Fase 9 — Canvas 2d (base-level fix) + konsistensi WebGPU RTX 4090**
**Tanggal:** 2026-11-08 · **Order Gil:** 16:23 WIB "Lah kalo benerin cmn 1 gmna mau jadi browser
Stealth nomor 1" + "Canva juga" — target: browser Stealth nomor 1, NOL flag detector.
**Status: SELESAI — Canvas 2d LOLOS CreepJS (hash span bersih, bold-fail 11→9); WebGPU device
kini 0x2684 (RTX 4090), konsisten dengan WebGL.**
**Suite: SELESAI — 822 PASS / 0 FAIL (29 file), exit 0 (log dibaca langsung).**
**Attempt: 1 dari maks 3.**

---

## 0. Catatan scope — spoof vs base (konteks dari merra, MEMORY.md 2026-11-08 sore)

Yang dibenerin F7B/F8 sejauh ini adalah level **SPOOF** (nilai yang dilaporkan ke situs),
BUKAN base (renderer SwiftShader masih yang menggambar beneran). Canvas cuma bisa bener
di level **base** — dan itulah yang dilakukan F9: mengubah jalur render canvas 2D yang
dipakai browser (GPU → CPU raster), bukan mengubah nilai yang dilaporkan. Gil 16:29 WIB:
"base-nya juga harus dibenerin" — fix ini menjawab perintah itu untuk Canvas.

Perintah WebGL semua tipe GPU (Gil 16:27 WIB "Harus sampe ketemu semua nya") adalah scope
F10 (branch f10-multi-gpu, agent terpisah) — BUKAN scope F9. F9 tidak menyentuh tabel WebGL.

---

## 1. Apa yang diukur CreepJS (dibaca dari kode, bukan asumsi)

Salinan lokal: `tests/live-reports/detector-site-creepjs/creep.js`, fungsi `getCanvas2d()`
(baris 3104–3280).

Urutan gambar (baris ~3227–3245):
1. Canvas 2×2. `fillStyle '#000'`, `fillRect(0,0,2,2)` — keempat piksel hitam.
2. `fillStyle '#fff'`, `fillRect(2,2,1,1)` — di LUAR canvas 2×2, tidak berpengaruh.
3. `beginPath(); arc(0,0,2, 0,1, true); closePath(); fill();` — busur putih berpusat di
   (0,0), radius 2, sudut 0→1 radian, counterclockwise (= jalur panjang ~5,28 rad,
   hampir seluruh lingkaran). Daerah yang terisi = cakram radius 2 MINUS segmen kecil
   antara chord (1.08,1.68)→(2,0) dan busur pendek. Piksel (1,1) jatuh di dalam
   segmen/wedge itu → abu-abu gelap; piksel (0,0) putih penuh.
4. `getImageData(0,0,2,2).data.join('')` — 16 angka (4 piksel × RGBA) digabung jadi string.

Cek (baris 3263–3271): string HARUS ada di `KnownImageData.BLINK` (8 nilai, semua
grayscale — R=G=B — dari Chrome asli di GPU fisik). Bila tidak ada → `LowerEntropy.CANVAS
= true` → hash section `bold-fail`. **Ini bukan cek "cocok GPU tertentu"** — ini
allowlist kecil nilai-nilai yang dihasilkan berbagai implementasi Blink asli. Sasarannya
bukan meniru GPU, melainkan mendarat DI DALAM allowlist.

Nilai kita sebelum F9 (rerun4): hash `9fc93baa` — string ke-9 di luar daftar
(diukur ulang di §2: `255255255255128128128255191191191255000255`).

---

## 2. Pengukuran — nilai kita vs allowlist, per jalur render

Runner: `tests/f9_canvas_probe.py` (Chrome kernel CfT 159 polos, tanpa spoof — SAH karena
`getImageData` native sejak F6, `fingerprint/canvas_audio.py` `section_canvas_getimagedata()`
adalah no-op; tes 2×2 ini tidak pakai teks, jadi tidak ada spoof yang menyentuhnya).
Bukti: `tests/live-reports/f9-probes/f9-canvas-variants.json` (dibaca langsung).

| Varian (flag) | 2×2 ImageData (main ctx) | Di allowlist? | WebGL hidup? |
|---|---|---|---|
| **base** (flag launcher saat ini: `--enable-unsafe-swiftshader --use-gl=angle --use-angle=swiftshader`) | `255255255255128128128255191191191255000255` | **TIDAK** (piksel (1,1) = 0,0,0,255 — hitam penuh) | Ya (SwiftShader Vulkan) |
| **noaccel2d** (base + `--disable-accelerated-2d-canvas`) | `255255255255192192192255244244244255535353255` | **YA — entri BLINK #8 persis** | Ya (SwiftShader Vulkan) |
| disablegpu (`--disable-gpu`) | sama, YA | YA | Tidak (null) |
| llvmpipe (`--use-angle=gl` + `LIBGL_ALWAYS_SOFTWARE=1`) | sama, YA | YA | Tidak (null) |
| swonly (hanya `--enable-unsafe-swiftshader`) | sama, YA | YA | Tidak (null) |
| disablegpu-noaccel2d | sama, YA | YA | Tidak |
| glswiftshader (`--use-gl=swiftshader`) | sama, YA | YA | Ya |
| llvmpipe-noaccel2d | sama, YA | YA | Tidak (null) |

**Diagnosis (terukur, bukan tebakan):** dengan flag base, canvas 2D di-raster GPU
(Ganesh di atas SwiftShader Vulkan) — AA tepi chord/busur-nya menghasilkan piksel (1,1)
hitam penuh (0% coverage), di luar allowlist. SEMUA jalur lain (termasuk konteks CPU
`willReadFrequently` di run base — juga entri #8) memakai raster CPU Skia dan
menghasilkan nilai allowlist yang sama persis. Jadi perbedaan ini adalah **perbedaan
algoritma antialiasing rasterizer**, bukan nilai yang salah di-spoof.

**Determinisme:** `noaccel2d` diulang 3× (profil fresh tiap run) — ketiganya
`...192...244...53`, WebGL hidup. Stabil, bukan flaky.

**Yang TIDAK dicoba (alasan):** Mesa llvmpipe sebagai backend GL tidak diperlukan —
`--disable-accelerated-2d-canvas` mencapai hasil yang sama tanpa mengganti stack GL
(llvmpipe malah membuat WebGL null di setup ini). Font/skia hinting tidak relevan —
tes ini tidak menggambar teks.

---

## 3. Implementasi (git diff: 2 file)

**`launcher/launcher.py` — `build_launch_args()` (attempt 1, BERHASIL)**
- Tambah `"--disable-accelerated-2d-canvas"` setelah flag SwiftShader, dengan komentar
  F9 yang menjelaskan alasan + bukti pengukuran. Ini memaksa raster CPU Skia untuk
  SEMUA canvas 2D di SEMUA situs (perubahan jalur render nyata, bukan khusus detector;
  tidak ada deteksi origin CreepJS/browserleaks). Jalur WebGL tidak disentuh.
- Trade-off jujur: canvas 2D jadi CPU-bound (lebih lambat untuk workload canvas berat).
  Untuk browser antidetect yang dipakai kelola akun/otomasi, ini dapat diterima — dan
  ini HARGA yang benar: nilai allowlist itu memang berasal dari raster CPU Chrome asli.

**`fingerprint/canvas_audio.py` — `section_webgpu()` (konsistensi WebGPU)**
- Sebelumnya: cabang NVIDIA selalu `_wDevice = '0x2704'` (RTX 4080) walau `_wDesc`
  diambil dari renderer (mis. "NVIDIA GeForce RTX 4090") — mismatch lintas API.
- Sekarang: model yang ter-parse dari renderer dipetakan ke PCI ID terverifikasi —
  `RTX 4090 → 0x2684` (terverifikasi dari string renderer di
  `fingerprint/data/zendriver-d3d11-fl11-nvidia-source.json`: "RTX 4090 (0x00002684)"),
  `RTX 4080 → 0x2704` (perilaku lama dipertahankan). Model lain yang tidak
  terverifikasi di sini tetap fallback 0x2704 — tidak ada nilai baru yang ditebak.
- Observasi di luar scope (TIDAK diubah): cabang AMD memakai `_wDevice = '0x744c'`
  dengan deskripsi "RX 7800 XT" dan Intel `0x9bc5` / "UHD Graphics 770" — belum
  diverifikasi cocok/tidaknya; dicatat untuk audit lanjutan, bukan ditebak di sini.

**CodeGraph (wajib, sebelum edit):** `codegraph sync` dulu (file F8 ditandai "changed on
disk"), lalu `explore section_webgpu` + `explore build_launch_args` + `impact
section_webgpu` — blast radius: `section_webgpu` → `spoof_js` → `build_fingerprint_js` →
`auto_spoof_js`/`preview_identity`; `build_launch_args` → `launch_profile` (diuji via
`tests/f7_detector_run.py` + 17 pemanggil lain).

---

## 4. Detector re-run #5 — CreepJS (metode sama seperti F6/F7/F7B/F8)

Runner: `tests/f9_detector_run.py` (salinan f8, profil `detector-test4`, identitas RTX 4090
beku, server CreepJS lokal 127.0.0.1:18083). Bukti:
`tests/live-reports/detector-2026-11-08-rerun5/` (creepjs.txt/html/png + identity.json,
dibaca langsung).

| Ukuran | rerun4 (F8) | **rerun5 (F9)** |
|---|---|---|
| div `class="rejected"` (section pink) | 0 | **0** |
| span `class="lies"` | 0 | **0** |
| bold-fail total (semua span) | 11 | **9** |
| Canvas 2d hash span | `bold-fail hash` (9fc93baa) | **`hash` (d3765ae2) — BERSIH** |
| WebGL hash span | `bold-fail hash` (014a71b6) | **`hash` (014a71b6) — BERSIH** |
| WebGL params / exts | (78): 54cf9774 / (67): 096fe525 | sama persis |
| WebGPU modal | device 0x2704 | **device 0x2684, RTX 4090 ×4, 0× "0x2704"/"RTX 4080"** |
| Worker | RTX 4090, id-ID, Asia/Jakarta | tetap bersih (hash d3c9aaef) |

**Sisa bold-fail (9 span): semuanya inline digit di section Audio**
(`sum: 124.04347 7 7 6 6 9 6 5 2 2`) — nilai `124.04347776696522` IDENTIK dengan
rerun4 DAN dengan kontrol Chromium polos (F7/F8). Ini artefak audio rendering
lingkungan (SwiftShader/headless), bukan lie spoof — tidak ada section yang flagged
lagi. Di luar scope F9 (perintah: Canvas + konsistensi WebGPU); dicatat, bukan dikejar
di sini.

**Tidak ada flag baru.** 19+ section bersih; Canvas 2d + WebGL kini bersih di CreepJS.

---

## 5. Suite — tetap hijau

`python3 tests/run_all.py` — **822 PASS / 0 FAIL (29 file)**, exit 0, ~516 detik (lebih
lambat dari F8 karena F10 jalan paralel di VM yang sama). Log dibaca langsung:
`/tmp/f9_suite_final.log` — 30 baris "PASS" (29 file + TOTAL), 0 FAIL (2 baris yang
mengandung kata "fail" hanyalah header kolom + baris TOTAL "0 FAIL"). Salinan:
`tests/live-reports/f9-suite-final-2026-11-08.log`.

---

## 6. Hermes (Canvas) — jawaban dibaca, KONFIRMASI INDEPENDEN

File `hermes-canvas-2026-11-08.md` dibaca penuh (3.566 byte). Hermes TIDAK menebak —
dia mengukur sendiri dengan Chrome for Testing **159.0.8148.0 DAN 156.0.8078.4** polos
(tanpa spoof), headful Xvfb, profil fresh, ops gambar + sampel Blink diambil dari
`creep.js` baris 3221–3265 yang sama:

| Jalur | Piksel (grayscale, row-major) | Allowlist |
|---|---|---|
| Flag SwANGLE saat ini, Canvas2D default | 255, 128, 191, 0 | Di luar |
| Flag sama + `--disable-accelerated-2d-canvas` | 255, 192, 244, 53 | Di dalam |

String ImageData CPU persis sama dengan pengukuran F9:
`255255255255192192192255244244244255535353255`. Konteks `willReadFrequently: true`
juga menghasilkan byte CPU yang sama tanpa flag. **WebGL tetap ANGLE/SwiftShader di
kedua varian.** Verdict Hermes: pertahankan flag yang ada, tambah HANYA flag Canvas2D —
tanpa penggantian piksel, override API, pengenalan detector, atau replay gambar.

Hermes juga mencatat: font/Skia settings tidak bisa menjelaskan/memperbaiki cek ini
(tidak ada teks yang digambar); llvmpipe tidak diperlukan (trial `--disable-gpu` lolos
piksel tapi kehilangan WebGL); Raphaël Mille hanya klaim publik tanpa source — bukan
implementasi terverifikasi untuk RTX 4090. Bukti mentah Hermes:
`/home/hatch/.hermes/cache/scratch/hermes-canvas-backend-results.json`.

**Kesimpulan: dua pihak independen (F9 + Hermes), dua Chrome (159 + 156), nilai yang
sama persis, fix yang sama persis.** F9 tidak menunggu Hermes — pengukuran §2 sudah
memberi jawaban sebelum file Hermes ada — tapi Hermes mengkonfirmasinya secara independen.

---

## 7. Ringkasan

| Item | Status |
|---|---|
| Cek Canvas CreepJS (apa yang diukur) | Dibaca dari creep.js: 2×2 fillRect hitam + arc putih, string harus di KnownImageData.BLINK (8 nilai) |
| Nilai kita (base) | `...128...191...000` — di luar daftar (piksel (1,1) hitam penuh, raster GPU SwiftShader) |
| Nilai kita (CPU raster) | `...192...244...53` — entri BLINK #8 persis, stabil 3/3 run |
| Fix attempt 1 | `--disable-accelerated-2d-canvas` di `build_launch_args()` — jalur render nyata, semua situs |
| WebGPU device | 0x2704 (RTX 4080) → 0x2684 (RTX 4090, terverifikasi dari tabel zendriver di disk) |
| CreepJS re-run #5 | 0 rejected, 0 lies, bold-fail 11→9; Canvas 2d + WebGL span bersih; sisa hanya 9 digit inline Audio (sama seperti kontrol polos) |
| Suite | **822/0 (29 file)**, exit 0, ~516 detik |
| Hermes | TIDAK dipakai langsung oleh F9 (merra yang bertanya); jawaban dibaca penuh — **konfirmasi independen**: nilai + fix SAMA PERSIS (Chrome 159 + 156, tanpa spoof) |
