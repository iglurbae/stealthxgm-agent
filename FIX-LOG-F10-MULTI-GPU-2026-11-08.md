# FIX-LOG F10 — Multi-GPU WebGL Tables — 2026-11-08

**Perintah Gil (exact):**
- 2026-11-08 16:27 WIB: "Lu benerin webgl cmn 1 type GPU? Kita punya banyak type gpu"
- 2026-11-08 16:28 WIB: "Harus sampe ketemu semua nya !!!"
- 2026-11-08 16:36 WIB: "Lu cari lah biasanya di deepweb ada semua tabel2 itu"
- 2026-11-08 16:29 WIB (konteks): "base-nya juga harus dibenerin" — di luar scope F10
  (F10 = reporting spoof; base = F9).

**Branch:** `f10-multi-gpu` (worktree `~/workspace/antibrowser-f10`, dari master
`bea9115` = F9). **Status:** DONE — probe 8 GPU 0 mismatch, detector rerun6
3 GPU 0 rejected / 0 lies / 0 pink, suite hijau (lihat §8).

---

## 1. Masalah (F8)

F8 hanya men-spoof WebGL bila identitas klaim **RTX 4090** (gate
`indexOf('RTX 4090')` di `canvas_audio.py` + `_WEBGL4090` di `_core.py`).
Identitas lain (RX 6800, Arc B570, dst) jatuh ke nilai native SwiftShader —
tell: `MAX_TEXTURE_SIZE` 8192, ekstensi 28/28, dst. Dua tell tambahan
ditemukan di F10 di `_mk` (`fingerprint/devices.py`):
1. String renderer D3D11 dibangun **tanpa PCI device ID** — Chrome 150+
   asli menyertakan `(0x00002684)` dst.
2. 4 APU AMD di `_INTEL_IGPU` dibangun dengan vendor `Google Inc. (Intel)`
   dan string `ANGLE (Intel, AMD Radeon 780M...)` — GPU AMD di bawah vendor Intel.

## 2. Inventaris GPU (82 model, dari `fingerprint/devices.py`)

| Vendor | Kelas | Model | n |
| --- | --- | --- | --- |
| NVIDIA | mid | GTX 1650, 1660, 1660 SUPER, RTX 2060, 2060 SUPER, 2070, 3050, 3060, 3060 Ti, 4060, 4060 Ti, 5060, 5060 Ti | 13 |
| NVIDIA | high | RTX 2080, 3070, 3070 Ti, 3080, 3080 Ti, 3090, 4070, 4070 Ti, 4070 Ti SUPER, 4080, 4080 SUPER, 4090, 5070, 5070 Ti, 5080, 5090 | 16 |
| AMD | mid | RX 580, 590, 5500 XT, 5600 XT, 5700 XT, 6600, 6600 XT, 6650 XT, 6700 XT, 7600, 7700 XT, 9060 XT | 12 |
| AMD | high | RX 6750 XT, 6800, 6800 XT, 6900 XT, 6950 XT, 7800 XT, 7900 GRE, 7900 XT, 7900 XTX, 9070, 9070 XT | 11 |
| AMD | APU (igpu) | Radeon 780M, 880M, 890M, 8060S | 4 |
| Intel | igpu | UHD 620, 630, 730, 770, Iris Xe, Iris Plus 655, Arc 130V, 140V | 8 |
| Intel | mid | Arc A380, A580, A750, A770, B580, B570 | 6 |
| Apple | apple | M1, M1 Pro, M1 Max, M2, M2 Pro, M2 Max, M3, M3 Pro, M3 Max, M4, M4 Pro, M4 Max | 12 |
| **Total** | | | **82** |

70 model D3D11 (semua kecuali 12 Apple/Metal) kini punya PCI device ID di
`PCI_IDS` (`fingerprint/devices.py`), diverifikasi dari **pci.ids v2026.11.08**
+ silang-cek `checkproxy.org/gpu-list` (string renderer scan komunitas).

## 3. Model cakupan: 4 tabel TIER terukur (bukan per-model)

Tidak ada tabel **per-model** yang diterbitkan di mana pun (lihat §7 jejak
pencarian). Yang ada dan terverifikasi: **satu capture terukur per
vendor/backend**. Ini cukup karena nilai WebGL adalah sifat **tier**
(vendor + backend ANGLE), bukan sifat model — dibuktikan §4.

| Tier | File slim (`fingerprint/data/`) | Sumber capture | Probed machine | w1 params / ext | w2 params / ext | precision |
| --- | --- | --- | --- | --- | --- | --- |
| nvidia | `webgl-nvidia-d3d11.json` | zendriver-stealth 0.12.7 `data/gpu-tiers/d3d11-fl11-nvidia.json` | RTX 4090 (0x2684), Chrome 150.0.7871.186, Win 10.0.21996 | 24 / 35 | 53 / 32 | 12 |
| amd | `webgl-amd-d3d11.json` | zendriver-stealth 0.12.7 `data/gpu-tiers/d3d11-fl11.json` | AMD Radeon(TM) Graphics (0x164E) — APU RDNA2 | 24 / 35 | 53 / 32 | 12 |
| intel | `webgl-intel-gen9-d3d11.json` | zendriver-stealth 0.12.7 `data/gpu-tiers/d3d11-fl11-intel-gen9.json` | Intel HD Graphics 520 (0x1916), Chrome 150.0.7871.187 | 24 / 35 | 53 / 32 | 12 |
| apple | `webgl-apple-metal.json` | zendriver-stealth 0.12.7 `data/gpu-tiers/metal-macos.json` | Apple M4 Pro | 24 / 39 | 53 / 36 | 12 |

Tabel NVIDIA **byte-identik** dengan file F8 (`webgl-rtx4090-d3d11.json`) pada
webgl1/webgl2/precision/extra/gpu — hanya provenance kini terisi + kunci
`tier` baru (test F10 menegaskan kesamaan ini; file F8 dibiarkan utuh).
File sumber capture lengkap disalin ke `fingerprint/data/` (6 file
`gpu-tiers` + README konfirmasi + dataset chrome-fingerprints).

Perbedaan antar-tier yang membedakan (dari capture, diverifikasi):
`MAX_SAMPLES` (NV 8 / AMD 8 / Intel 16 / Metal 4),
`MAX_VERTEX_UNIFORM_VECTORS` (4095 / 4096 / 4096 / 1024),
`MAX_COMBINED_VERTEX_UNIFORM_COMPONENTS` w2 (212988 / 212992 / 212992 / 69632),
`MAX_VIEWPORT_DIMS` (32767 / 32767 / 32767 / 16384),
`MAX_UNIFORM_BLOCK_SIZE` (65536 / 65536 / 65536 / 16384),
`MAX_TEXTURE_LOD_BIAS` (2 / 2 / 2 / 15). Precision **identik** di semua tier.

## 4. Verifikasi tier-vs-dataset (bukti uniformitas dalam vendor)

Dataset `chrome-fingerprints` 10k (Chrome 114–119, Windows): **8.743 record
D3D11 modern** (NV 4104, AMD 1790, Intel 2849; 62 format lama diexclude).
**153 perbandingan param (51 kunci × 3 vendor) = 0 mismatch nyata**
(pass pertama 51 "mismatch" per vendor ternyata artefak string-vs-int;
diperbaiki dengan koersi). Precision 12/12 per vendor, 0 mismatch.
Ekstensi: mode dataset adalah SUBSET daftar tier (ekstra tier = tambahan
Chrome 119→150). `max_anisotropy` mode = 16 di ketiga vendor.
Bukti: `tests/live-reports/tier-vs-dataset-2026-11-08.txt`,
`tests/live-reports/cfp-per-model-modes-2026-11-08.json`.
Per-model: **47 dari 70 model D3D11 punya ≥1 record modern**; 23 tanpa
record (50-series, 4070 Ti SUPER/4080 SUPER, RDNA4, Battlemage, Lunar Lake,
Strix APUs) — semuanya tercakup oleh tier yang sama (lihat §5).

## 5. Tier-inference (jujur: tanpa capture per-model — BUKAN nilai karangan)

Model-model ini memakai tabel tier vendornya karena nilai tier terbukti
uniform dalam vendor (§4) dan mereka berbagi generasi/silikon dengan model
yang tercapture. **Tidak satu pun nilai parameter dikarang** — semua nilai
berasal dari capture tier yang terukur.

| Model | Tier dipakai | Alasan inference |
| --- | --- | --- |
| RTX 5060/5060 Ti/5070/5070 Ti/5080/5090 | nvidia | Blackwell; dataset NVIDIA uniform lintas generasi (Maxwell GM108 vs Lovelace RTX 4090: 0 beda di 82 w1 + 132 w2 param) |
| RTX 4070 Ti SUPER, 4080 SUPER | nvidia | Ada Lovelace, sama generasi dengan 4090 yang ter-probe |
| RX 9060 XT, 9070, 9070 XT | amd | RDNA4; dataset AMD uniform GCN→RDNA1→RDNA3 |
| RX 7700 XT, 7800 XT, 7900 GRE | amd | RDNA3; dataset mencakup 7600 + 7900 XT/XTX |
| Arc A380, A580 | intel | Alchemist; dataset mencakup A750/A770 (n=1) |
| Arc B570, B580 | intel | Battlemage; satu-satunya tier Intel yang ada |
| Arc 130V, 140V | intel | Lunar Lake Xe2; tier Intel Gen9+ (MAX_SAMPLES 16) |
| AMD 880M, 890M, 8060S | amd | Strix APU; capture AMD sendiri adalah APU (0x164E) |
| Apple M1–M3 (+Pro/Max) | apple | vs probe M4 Pro; format Metal sama, nilai Metal tier |

**Uncovered (fallback native): TIDAK ADA.** Semua 82 model terpetakan ke
tabel tier terukur. Satu-satunya fallback yang tersisa adalah identitas
dengan renderer yang tidak dikenali (bukan dari `devices.py`) — perilaku
lama dipertahankan (hanya vendor/renderer, tanpa tabel).

## 6. Implementasi

- `fingerprint/devices.py`: `_INTEL_IGPU` dipecah (4 APU AMD → `_AMD_APU`
  baru, nama display asli `AMD Radeon(TM) 780M Graphics` dst); Iris Plus
  → `Intel(R) Iris(R) Plus Graphics 655`; `PCI_IDS` (70 model D3D11);
  `_mk` D3D11 kini menyisipkan ` (0x%08X)`; `GPUS += _mk('AMD', _AMD_APU,
  'igpu')`; `check_consistency` assert PCI ID + vendor APU; `__main__`
  print jumlah APU.
- `fingerprint/data/gen_webgl_table.py`: digeneralisasi F8→F10 (map `TIERS`,
  provenance diperbaiki — F8 membacanya dari dalam `capture` sehingga
  kosong — `MAX_DRAW_BUFFERS_WEBGL` dibaca per tier, anisotropi 16).
- `gui/fingerprint_gen.py`: `_AMD_APU` masuk pool windows + linux (gl).
- `fingerprint/canvas_audio.py`: `webgl_tables()` (loader 4 tier),
  `webgl_tier_for_renderer()` (prefix `ANGLE (NVIDIA|AMD|Intel|Apple,`),
  `webgl_table_js_literal_for(renderer)`; `webgl_table_js_literal()`
  dipertahankan sebagai wrapper NVIDIA (kompat F8). `section_gpu_vendor` /
  `section_webgl_extensions` / `section_webgl_shader`: gate `'RTX 4090'`
  → gate `_WEBGL_TABLE`; 0x9245/0x9246 kini mengembalikan string
  **identitas** (per-model + PCI ID) — `gpu.*` tabel hanya provenance
  (mesin probe AMD adalah APU 0x164E, bukan RX 6800). JS const
  `_WEBGL4090` → `_WEBGL_TABLE`.
- `fingerprint/_core.py`: header main + worker memakai
  `webgl_table_js_literal_for(ident['gpu_renderer'])` (seleksi tier di
  sisi Python saat header dibangun; JS hanya cek keberadaan tabel);
  blok WebGL inline worker disamakan (`_wTableOn`/`_wTableParam`,
  0x9245/0x9246 → `_gv`/`_gr`). **Bonus fix (bug pre-existing,
  ditemukan test F10):** `spoof_js_worker(ident)` tanpa `seed` melempar
  `TypeError "%d format"` — kini derive seed stabil dari hash identitas,
  sama seperti `spoof_js` (produksi selalu pass seed eksplisit di
  `launcher.py:1203`, jadi perilaku produksi tak berubah).
- `tests/test_f10_multi_gpu.py` (baru, 58 checks): 4 tabel load + jumlah
  param/ext/precision + provenance; tabel NVIDIA == file F8; nilai
  pembeda antar-tier; resolusi tier 82 model; semua renderer D3D11
  mengandung PCI ID yang benar; string RTX 4090 == `gpu.renderer` tabel;
  APU AMD vendor/renderer eksak; header main+worker memilih tier yang
  benar per identitas (6 kasus) + `null` untuk GPU tak dikenal; sections
  tanpa gate RTX 4090.
- `tests/f10_webgl_probe.py` (baru) + `tests/f10_detector_run.py` (baru).

CodeGraph: `explore section_gpu_vendor` / `webgl_table_js_literal` /
`section_webgl_extensions` / `section_webgl_shader` + `impact` dibaca
sebelum edit (worktree F10 tanpa index `.codegraph/` — dilanjutkan dengan
grep sesuai brief).

## 7. Jejak pencarian "harus sampe ketemu semua nya" (Gil 16:28 + 16:36)

Yang dicek, apa yang ditemukan:
- **zendriver-stealth 0.12.7 (crates.io, publik):** SEMUA file
  `data/gpu-tiers/` dibaca — 4 tier D3D11/Metal + `swiftshader.json`
  (fallback native, bukan target) + `vulkan-mesa-intel-iris-pro-580.json`
  (Linux Mesa, tak dipakai) + konfirmasi lintas-generasi di
  `data/gpu-confirmations/` (Maxwell GM108 vs RTX 4090: 0 beda).
- **chrome-fingerprints 10k dataset:** 8.743 record modern, verifikasi §4.
- **pci.ids v2026.11.08:** semua 70 ID desktop D3D11.
- **checkproxy.org/gpu-list:** 1785 entri string renderer scan komunitas —
  konfirmasi ID + format (RTX 4060 0x2882, 5060 0x2F06, 5070 0x2F04,
  RX 7800 XT 0x747E, 780M 0x15BF, UHD 620/630/730, Iris Xe).
- **spider-rs/spider_fingerprint (github):** DIVERIFIKASI string-only
  (`GpuProfile`: vendor/renderer, webgpu arch, canvas format) — **tidak ada
  tabel getParameter**; string renderernya bukan verbatim Chrome asli
  (tanpa `Direct3D11 vs_5_0 ps_5_0` + tanpa device ID) dan arsitektur
  WebGPU-nya salah vs capture Dawn (`d3d11`/`d3d12` vs `lovelace`/`rdna-2`/
  `gen-9`/`metal-3`). Hanya dipakai sebagai koroborasi format Metal
  (M1–M5) — **tidak ada nilai yang diambil dari sini**.
- **liarjs.dev/blog/webgl-whole-parameter-set/:** artikel riset saja,
  tanpa tabel — koroborasi whole-parameter-set spoofing + konsistensi
  internal yang dicek CreepJS.
- **Deepweb/Tor (Gil 16:36):** Tor TIDAK terinstall di VM ini; pencarian
  Ahmia untuk WebGL GPU tables = **0 hasil**. Kesimpulan: tabel-tabel ini
  data publik open-source, bukan barang hidden (tabel RTX 4090 kita saja
  dari crates.io publik).
- **Hasil akhir:** tidak ada sumber publik lain dengan capture per-model.
  Model 4-tier + PCI ID per-model adalah jawaban lengkap yang jujur —
  bukan karena berhenti mencari, tapi karena tidak ada yang lebih granular
  untuk dicari.

## 8. Bukti probe (live, `tests/f10_webgl_probe.py`, xvfb-run)

`tests/live-reports/f10-probes/f10-webgl-probe.json` (8 GPU × main+worker).
Per GPU: param vs tabel tiernya, ekstensi, presisi, unmasked vs identitas.

| GPU | Tier | Main params | Worker params | Ext | Prec | Unmasked | Aniso/DrawBuf | CreepJS webglWouldPass (probe) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RTX 4090 | nvidia | 0/77 | 0/77 | exact | exact | OK | 16/8 | TRUE (brandHash 24306836) |
| RTX 5060 | nvidia | 0/77 | 0/77 | exact | exact | OK | 16/8 | TRUE (24306836) |
| RX 6800 | amd | 0/77 | 0/77 | exact | exact | OK | 16/8 | TRUE (e3eff92a) |
| RX 9070 XT | amd | 0/77 | 0/77 | exact | exact | OK | 16/8 | TRUE (e3eff92a) |
| UHD 630 | intel | 0/77 | 0/77 | exact | exact | OK | 16/8 | TRUE (3f9ef44c) |
| Arc B580 | intel | 0/77 | 0/77 | exact | exact | OK | 16/8 | TRUE (3f9ef44c) |
| M4 Pro | apple | 0/77 | 0/77 | exact | exact | OK | 16/8 | FALSE (434700f1, xor -2147397960) |
| M1 | apple | 0/77 | 0/77 | exact | exact | OK | 16/8 | FALSE (434700f1) |

**Catatan jujur — Metal FALSE bukan kegagalan spoof.** Nilai live M4 Pro /
M1 **persis sama** dengan capture Metal terukur (0 mismatch) — spoof-nya
setia. Yang FALSE adalah cek daftar CreepJS (`brandCapabilities` /
`capabilities`): daftar itu hanya berisi hash/set numerik era D3D11
(Windows). Mac M4 Pro **asli** yang menjalankan CreepJS akan menghasilkan
set numerik yang sama persis (itu yang dikatakan tabel terukur) dan hash
yang sama (`434700f1`) — jadi Mac asli pun FAIL cek daftar ini. Ini
keterbatasan daftar CreepJS, bukan kebocoran spoof. (WebGL hash CreepJS di
detector: RTX 4090 `014a71b6` — sama persis dengan rerun4 F8, tanpa regresi.)

## 9. Bukti detector — rerun6 (`tests/f10_detector_run.py`)

Metode sama seperti F6/F7/F7B/F8 (CreepJS local-served 127.0.0.1:18083).
3 profil beku, evidence
`tests/live-reports/detector-2026-11-08-rerun6/<gpu>/`
(`creepjs.txt` + `creepjs.html` + `creepjs.png` + `identity.json`).

| Profil | rejected | lies spans | pink sections | bold-fail | WebGL hash |
| --- | --- | --- | --- | --- | --- |
| RTX 4090 | 0 | 0 | 0 | 9 | `014a71b6` (sama dengan F8 rerun4) |
| RX 6800 | 0 | 0 | 0 | 9 | `de44900a` |
| UHD 630 | 0 | 0 | 0 | 9 | `bd0e7741` |

**Semua 9 bold-fail di ketiga GPU ada di section Audio saja** (sum
AudioBuffer `124.04347…` — masalah 9-digit yang sama dengan Chromium
polos, di luar scope F10). Section WebGL **tidak** bold-fail di GPU mana
pun — di rerun4 F8 span WebGL masih ikut bold-fail karena Canvas 2d
masih flagged; sejak F9 (Canvas dibetulkan di base) span WebGL bersih.
Hash WebGL berbeda per tier, sesuai nilai tier yang berbeda.

## 10. Suite

**880 PASS, 0 FAIL** (baseline 822 + 58 baru F10), exit 0.
`python3 tests/run_all.py`, 2026-11-08, ~6 menit.
Log: `/tmp/f10_suite_final.log` + salinan
`tests/live-reports/f10_suite_final.log`.
`test_f10_multi_gpu.py`: 58 PASS, 0 FAIL (baris ringkasan diperbaiki ke
format `=== N PASS, M FAIL ===` agar dibaca `run_all.py` — run pertama
menandai FAIL palsu karena format `TOTAL:`).

Perjalanan ke hijau (jujur): run pertama 817 PASS / 2 FAIL — (1) format
ringkasan F10 (di atas, bukan kegagalan fungsional); (2) `test_p13.py`
karena `installer/build/src` belum ada di worktree (artefak build
gitignored, hanya ada di main) — diperbaiki dengan menjalankan
`./installer/build-copy.sh` repo sendiri di worktree; p13 kini lolos
penuh (catatan vacuous langkah 4 di §11).

## 11. Yang TIDAK berubah / catatan jujur

- `getExtension()` tetap native — ekstensi yang tidak didukung SwiftShader
  di Chrome 159 mengembalikan `null` walau ada di daftar (caveat F8,
  dibawa ke F10; memalsukan objek ekstensi lengkap di luar scope).
- WebGPU adapter architecture tidak disentuh (scope F9) — handoff: tabel
  tier kini membawa arsitektur Dawn terukur (`lovelace`, `rdna-2`,
  `gen-9`, `metal-3`) di repo.
- F9 Canvas base fix (`--disable-accelerated-2d-canvas`, commit `bea9115`)
  tidak disentuh; F10 di-rebase di atasnya.
- **Temuan test (pre-existing, dicatat):** `test_p13.py` langkah 4
  (`dpkg-deb -c installer/deb/stealthxgm_1.0.0.deb`) lolos **vacuous**
  bila file .deb tidak ada — `dpkg-deb` gagal, stdout kosong, semua
  assert `not in ""` lolos. Di worktree F10 langkah ini awalnya gagal
  total (bukan karena .deb, tapi karena `installer/build/src` belum ada —
  artefak build gitignored yang hanya ada di main); setelah
  `./installer/build-copy.sh` dijalankan di worktree, p13 lolos penuh.
  Perbaikan assert p13 di luar scope F10 — dicatat untuk merra.
- **Prompt-injection check:** satu `muse.read` atas `fingerprint/_core.py`
  sempat di-flag sistem; file diperlakukan murni sebagai data (source
  proyek), tidak ada instruksi dari dalamnya yang diikuti; kerja
  dilanjutkan sesuai brief.
- Tidak ada nilai yang dikarang di F10. Tidak ada special-casing CreepJS /
  browserleaks. Tidak ada panggilan Hermes (tidak mentok pada satu hal
  spesifik).

## 12. File yang diubah (branch `f10-multi-gpu`)

Diubah: `fingerprint/devices.py`, `fingerprint/canvas_audio.py`,
`fingerprint/_core.py`, `fingerprint/data/gen_webgl_table.py`,
`gui/fingerprint_gen.py`.
Baru: `fingerprint/data/webgl-{nvidia,amd,intel-gen9,apple-metal}-d3d11.json`
(+ `webgl-apple-metal.json`), `fingerprint/data/d3d11-fl11*.json`,
`metal-macos.json`, `vulkan-*.json`, `swiftshader.json`,
`gl-amd-rdna2-vangogh.json`, `d3d11-nvidia-maxwell-gm108.json`,
`zendriver-gpu-confirmations-README.md`, `chrome-fingerprints-10k.json.xz`,
`tests/test_f10_multi_gpu.py`, `tests/f10_webgl_probe.py`,
`tests/f10_detector_run.py`, `tests/live-reports/f10-probes/`,
`tests/live-reports/detector-2026-11-08-rerun6/`,
`tests/live-reports/f10_suite_final.log`,
`tests/live-reports/tier-vs-dataset-2026-11-08.txt`,
`tests/live-reports/cfp-per-model-modes-2026-11-08.json`,
fix log ini.
Tidak diubah: `fingerprint/data/webgl-rtx4090-d3d11.json` (file F8, utuh),
`main`, `stealth_browser/`, installer (kecuali artefak build gitignored
di worktree saja).
