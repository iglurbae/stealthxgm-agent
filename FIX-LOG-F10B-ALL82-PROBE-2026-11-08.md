# FIX-LOG F10B — Probe Semua 82 Model GPU (Addendum F10)

**Tanggal:** 2026-11-08 (sore) · **Perintah Gil (17:31 WIB):** "8gpu dong dari 82 model?"
**Cakupan:** F10 (commit `b478439`) hanya probe 8 GPU sebagai wakil tier.
Tugas ini: probe SEMUA 82 model di `fingerprint/devices.py` GPUS, per model
(WebGL params vs tabel tier, extensions, precision, unmasked renderer, PCI ID,
tier assignment, WebGPU device/description/architecture).
**Hasil akhir: 82/82 PASS** (final `--force` re-run, 732 detik, 0 error).
**Suite: 880 PASS / 0 FAIL** (baseline F10 dipertahankan).

## Bukti

- `tests/live-reports/f10-probes/f10-webgl-probe-all82.json` (5,8 MB, 82 entry;
  gitignored — bukti hidup di disk, bukan di git)
- Runner: `tests/f10b_webgl_probe_all82.py` (dibuat di tugas ini, di-commit)
- Log run: `/tmp/f10b_probe_full.log` (run 1), `/tmp/f10b_probe_rerun.log`
  (re-run pasca-fix), `/tmp/f10b_probe_final.log` (final `--force`)
- Suite: `/tmp/f10b_suite_final.log` (`=== TOTAL: 880 PASS, 0 FAIL ===`)

## Riwayat run (semua angka dibaca sendiri dari JSON/log, bukan dari klaim)

| Run | Hasil | Keterangan |
| --- | --- | --- |
| 1 — full 82, kode F10 | **3/82 PASS** | 79 gagal di WebGPU device/description (bug 1); 1 gagal worker (bug 2) |
| 2 — re-run pasca-fix device/desc (79 model) | **75/82 PASS** | 7 Apple tersisa: crash probe di apple-m2-max (bug 3), 6 tidak sempat ke-probe |
| 3 — Apple 7 model (pasca-fix bug 3) | **75/82 PASS** | 7 Apple gagal launch: "Chromium did not open debug port in time" — gangguan EPERM VM, bukan produk |
| 4 — Apple 7 model, jendela fault bagus | **78/82 PASS** | m2-max, m3, m3-pro lolos; fault flip di tengah run, 4 terakhir gagal launch |
| 5 — Apple 4 model (waiter + retry loop) | **78/82 PASS** | jendela bagus 5/5 langsung nutup; service restart matikan retry loop |
| 6 — Apple 4 model, jendela bagus | **82/82 PASS** (58 detik) | m3-max, m4, m4-pro, m4-max lolos |
| 7 — FINAL full 82 `--force`, kode final | **82/82 PASS** (732 detik) | satu JSON konsisten, satu versi kode |

Per-model final (dari JSON): `tier_ok` True semua, `pci_ok` True semua,
`webgpu_ok` True semua, 0 error, 0 param mismatch (main + worker).
CreepJS `webglWouldPass`: **70/82** main + worker — 12 Apple False adalah
batas daftar CreepJS (hash Metal tidak ada di daftar era D3D11), BUKAN gagal
spoof; nilai live sama persis dengan capture Metal terukur (sudah dicatat di F10).

## Bug 1 — WebGPU device/description hardcode per vendor (nyata, 79/82)

**Temuan run 1 (dibaca dari JSON):** device live selalu `0x2704` (NVIDIA,
kecuali 4090 `0x2684`), `0x744c` (semua 27 AMD), `0x9bc5` (semua 14 Intel),
`''` (semua 12 Apple); description selalu satu model per vendor
('NVIDIA GeForce RTX 3060' kecuali yang kebetulan cocok, 'AMD Radeon RX 7800 XT',
'Intel(R) UHD Graphics 770', 'Apple M1'). Hanya 3 model yang kebetulan cocok
dengan hardcode itu yang lolos: RTX 4080, RTX 4090, Apple M1.
Pola gagal: 46× (device+desc), 18× (device saja), 14× (desc saja).

**Akar:** `section_webgpu()` di `fingerprint/canvas_audio.py` set `_wDevice`
dan `_wDesc` hardcode per vendor; F9 hanya tambal 4090/4080.

**Fix (attempt 1, commit ini):** device + description diturunkan dari
`ident.gpu_renderer` — string itu sudah membawa nama model + PCI ID
terverifikasi (`devices.py` PCI_IDS):
- D3D11: `ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 (0x00002684) ...)` →
  desc `NVIDIA GeForce RTX 4090`, device `0x2684` (4 digit bawah PCI ID).
- Metal: `ANGLE Metal Renderer: Apple M4 Pro, ...` → desc `Apple M4 Pro`,
  device `''`.
- Regex D3D11 memakai `(.+?)` agar nama dengan `(TM)`/`(R)` (mis.
  `AMD Radeon(TM) 780M Graphics`) tidak terpotong; format GL (tanpa PCI ID)
  hanya ambil description; parse gagal → fallback nilai lama, bukan crash.
- Tidak ada nilai tabel yang diubah; tidak ada nilai yang ditebak.

**Verifikasi sebelum probe ulang:** `node --check` JS hasil generate OK;
simulasi regex di Node untuk 82 renderer: 0 buruk; cross-check Python
(parse vs `webgpu_expected` probe): 82/82 cocok, 0 mismatch.

## Bug 2 — RTX 5060 Ti: worker TIDAK ter-spoof (flake, 1 kejadian)

**Temuan run 1:** main thread 0 mismatch, worker mentah SwiftShader
(`Google Inc. (Google)` / `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device
(Subzero) (0x0000C0DE))...)`, MAX_TEXTURE_SIZE 8192, dst.) — injector worker
tidak masuk di launch itu. Model kembar RTX 5060 (tier sama, jalur kode sama)
lolos; 80 model lain worker-nya ter-spoof. **Bukan bug per-model** — race
injeksi worker sekali jalan. **Re-run: lolos** (0 mismatch main+worker).
Tidak ada fix kode untuk ini; dicatat sebagai flakiness injeksi worker yang
diketahui (1 kejadian dari 82+82+82 launch).

## Bug 3 — Probe crash `KeyError: 'params'` (tool, bukan produk)

**Temuan re-run 2:** script mati di `apple-m2-max` — `creepjs_webgl_check`
indeks `live["webgl1"]["params"]` padahal worker tidak mengembalikan params
(launch terganggu fault). Akibat: 6 model Apple sesudahnya tidak ke-probe,
entry `apple-m2-max` tidak ke-save (stale run 1).

**Fix (tool `tests/f10b_webgl_probe_all82.py`):**
- `creepjs_webgl_check` kembalikan error dict bila params hilang (jangan raise).
- Syarat break retry loop = worker DAN main punya webgl1 params; gagal →
  entry `pass=False` + `error` jelas, tetap di-save, lanjut model berikut.
- Retry 2 → **3 attempt** + jeda 5 detik antar attempt (fault EPERM suka flip
  dalam hitungan detik; retry langsung kena jendela gagal yang sama).
- `_save` retry 5× (2 detik) bila write gagal EPERM, lalu JANGAN crash run
  (hasil tetap di memori; save berikutnya menulis ulang semua entry) +
  satu save terakhir sebelum `DONE`.
- Flag `--force`: re-probe walau entry sudah PASS (dipakai final re-run).

## Attempt 2 — WebGPU architecture per generasi (info-only → diperbaiki)

**Temuan:** `architecture` live masih nilai lama per vendor/kelas
(`ada`/`ampere`/`rdna-3`/`xe`/`apple-m1`) — bahkan untuk RTX 4090 yang
terukur, capture bilang `lovelace`, bukan `ada`. Probe tidak menggagalkan
ini (info-only), tapi detector yang cross-check adapter info bisa menandai.

**Riset kosakata Dawn (sumber terverifikasi, bukan tebakan):**
Web3D Survey (nilai `adapter.info` dunia nyata) + spider-rs/spider_fingerprint
(semua profil macOS M1–M5 → `metal-3`) + capture zendriver-stealth
(RTX 4090 → `lovelace`, APU RDNA2 → `rdna-2`, HD 520 → `gen-9`,
M4 Pro → `metal-3`). Nilai yang muncul di data nyata:
NVIDIA `turing`/`ampere`/`lovelace`/`blackwell`; AMD `rdna-1`/`rdna-2`/`rdna-3`;
Intel `gen-9`/`gen-12lp` (+ `gen-8`/`gen-11` untuk generasi yang tidak ada di
inventaris); Apple `metal-3` (macOS) dan `apple` (iOS — tidak dipakai di sini).

**Fix (attempt 2, commit ini):** override `_wArch` dari `_wDesc` (nama model
tepat) hanya untuk kelompok terverifikasi — NVIDIA 29/29, AMD 21/27,
Intel 6/14, Apple 12/12 (**68 model**). **14 model TIDAK diubah** (nilai lama
dipertahankan, bukan ditebak): GCN RX 580/590, RDNA4 RX 9060/9070/9070 XT,
RDNA3.5 8060S, Xe-HPG Arc A380/A580/A750/A770, Xe2 Arc B570/B580/130V/140V.
Satu pengecualian dicatat jujur: Iris Plus 655 → `gen-9` adalah **inferensi
keluarga** (Coffee Lake = keluarga Gen9; kosakata Dawn yang teramati tidak
punya nilai `gen-9.5`), bukan nilai teramati langsung.

**Verifikasi:** simulasi Node atas 82 deskripsi (logika persis `section_webgpu`,
pakai `gpu_vendor` asli `Google Inc. (X)`): **82/82, 0 mismatch**
(68 kelompok terverifikasi cocok; 14 fallback tetap di nilai lama).
**Bukti live (final JSON):** arch per vendor — NVIDIA turing 7 / ampere 8 /
lovelace 8 / blackwell 6; AMD rdna-1 3 / rdna-2 9 / rdna-3 15
(9 terverifikasi + 6 fallback); Intel gen-9 3 / gen-12lp 3 / xe 8 (fallback);
Apple metal-3 12. **0 mismatch arsitektur dari 82.**

## Gangguan filesystem VM (EPERM) selama tugas ini — BUKAN produk

Fault yang sama seperti 2026-11-07 kambuh lagi di tengah tugas ini:
- Probe write `/tmp`: **0/20 OK** lalu **0/10 OK** (semua `write()` gagal
  `[Errno 1] Operation not permitted`, ~10 detik berturut-turut), lalu
  **10/10 OK** beberapa menit kemudian — flip dalam hitungan detik/menit.
- Dampak: launch Chromium gagal (`did not open debug port in time`,
  21× di run Apple-7), `_save` JSON gagal (`PermissionError` saat
  `json.dump`), `py_compile` gagal (`.pyc` tidak bisa ditulis — diakali
  dengan `PYTHONDONTWRITEBYTECODE=1`), log probe kosong 0 baris (stdout
  gagal ditulis), **service restart** di tengah retry loop (loop mati,
  `/tmp` ke-wipe, JSON di workspace selamat — masih 78/82).
- Cara kerja yang dipakai: waiter (cek write 5/5 dulu baru jalan), retry
  loop 10×, `_save` ber-retry, jeda antar attempt. Tidak ada data yang
  hilang; yang tertunda hanya waktu.

## Perubahan kode (commit ini)

- `fingerprint/canvas_audio.py` — `section_webgpu()`: (1) parse device +
  description dari `ident.gpu_renderer`; (2) override architecture per
  generasi terverifikasi. Tidak ada perubahan signature; blast radius
  (CodeGraph `explore section_webgpu` + `impact`, sync dulu):
  `spoof_js` → `build_fingerprint_js` → `auto_spoof_js`/`preview_identity`.
  Satu insiden saat edit: blok arch sempat masuk ke fungsi yang salah
  (`_patchExt`, line 271) karena `} catch(e) {}` cocok 3 lokasi — langsung
  dicabut (sed 272-294d), file di-parse ulang OK, lalu dimasukkan di lokasi
  benar (line 414, sebelum `// Limits per kelas`).
- `tests/f10b_webgl_probe_all82.py` (baru): runner 82 model + hardening
  (guard params, retry 3×, `_save` ber-retry, `--force`).
- `FIX-LOG-F10B-ALL82-PROBE-2026-11-08.md` (file ini).
- JSON bukti TIDAK di-commit (gitignored: `tests/live-reports/`).

## Yang TIDAK berubah / sisa jujur

- Tabel WebGL tier (4 file `fingerprint/data/`) TIDAK diubah.
- 14 model arsitekturnya masih nilai lama yang belum terverifikasi
  (GCN, RDNA4, RDNA3.5, Xe-HPG, Xe2) — butuh capture Dawn per generasi
  atau nilai `adapter.info` dunia nyata untuk model itu; jangan ditebak.
- CreepJS `webglWouldPass` 70/82 — 12 Apple False karena daftar hash CreepJS
  era D3D11 (Mac asli pun sama, sudah dicatat F10).
- 9 digit inline Audio (sama kayak Chromium polos) — sisa dari F9, bukan
  cakupan tugas ini.
- Hermes TIDAK dipakai (tidak mentok di satu hal spesifik; riset arsitektur
  selesai lewat Web3D Survey + spider-rs + capture).
- Tidak ada detector re-run 82 model (sesuai brief — probe adalah bukti
  per-model; bukti detector rerun6 3 GPU tetap berdiri).
