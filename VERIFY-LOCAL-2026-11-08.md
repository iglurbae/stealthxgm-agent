# StealthXGM — Verifikasi Ulang Lokal di VM (pasca-fault)

Tanggal: 2026-11-08 (suite selesai ~09:59 WIB; bukti kernel ~10:06 WIB)
Perintah: Gil 2026-11-08 09:56 WIB ("Sok lanjutin pekerjaan cek ulang semua StealthXGM yang di VM")
Alasan: suite lokal kemarin terblokir gangguan filesystem VM (EPERM intermiten); pagi ini
probe tulis 20/20 lolos (09:53 WIB), kegagalan terakhir terkonfirmasi 03:00 WIB (aging Gmail).

## Verdict: BERSIH — 702 PASS, 0 FAIL (28/28 file) + F5-1 TERBUKTI LOKAL

## 1. State repo (sebelum suite)

- git HEAD: `7ef722d` "F5-2: test hitung path repo dari __file__, bukan hardcode /home/hatch/..."
  di atas `9e49311` (F5-1) dan `6173af5` (F4). Sesuai ekspektasi.
- grep `/home/hatch` di tests/ + launcher/ + gui/: **0 hasil di kode**.
  Satu-satunya hit: `gui/data/kernels.json:9` — itu data runtime (path kernel yang
  terdaftar), bukan hardcode di kode. Bukan temuan.
- `_chmod_kernel_binaries` ada di `launcher/kernels.py:298`, dipanggil di :341
  (sesudah extract) dan :352 (sesudah pindah ke dest_dir).
- Disk /home/hatch: 150G total, 117G free.

## 2. Suite penuh lokal — 702 PASS, 0 FAIL

Perintah: `cd ~/workspace/antibrowser && python3 tests/run_all.py`
(via plain exec, runtime yang background-kan; durasi 224,8 detik; exit 0)
Log: `/tmp/verify-local-2026-11-08.log`

| file | pass | fail |
|---|---|---|
| test_f3_api.py | 86 | 0 |
| test_f3_backup.py | 49 | 0 |
| test_f3_batch.py | 49 | 0 |
| test_f3_extensions.py | 57 | 0 |
| test_f3_freeze.py | 21 | 0 |
| test_f3_kernels.py | 58 | 0 |
| test_f3_login.py | 63 | 0 |
| test_f3_sync.py | 55 | 0 |
| test_f4_design.py | 17 | 0 |
| test_p01.py | 4 | 0 |
| test_p02.py | 4 | 0 |
| test_p03.py | 3 | 0 |
| test_p04.py | 6 | 0 |
| test_p05.py | 7 | 0 |
| test_p06.py | 6 | 0 |
| test_p07_locking.py | 14 | 0 |
| test_p08.py | 6 | 0 |
| test_p09_proxy_auth.py | 25 | 0 |
| test_p10_watchdog.py | 20 | 0 |
| test_p11.py | 9 | 0 |
| test_p12_registry.py | 15 | 0 |
| test_p13.py | 5 | 0 |
| test_p14_headless.py | 11 | 0 |
| test_p15_cookies.py | 20 | 0 |
| test_p16_api_contract.py | 19 | 0 |
| test_p16_consistency.py | 11 | 0 |
| test_p17_injection.py | 19 | 0 |
| test_p18_rpa.py | 43 | 0 |
| **TOTAL** | **702** | **0** |

### Koreksi catatan sebelumnya: klaim "702" F4 TERNYATA BENAR

Laporan VPS kemarin menulis "klaim 702 TIDAK ter-reproduksi (selisih 10 ada di
klaim, bukan kode)". Itu **salah**: 702 ter-reproduksi di VM lokal. Selisih
10 vs run VPS (692) murni lingkungan:

- test_p09_proxy_auth.py: lokal 25 vs VPS 20 (+5)
- test_p17_injection.py: lokal 19 vs VPS 14 (+5)
- Semua file lain identik.

Penyebab: kedua file punya seksi headful (xvfb) yang hanya jalan bila
`xvfb-run` ada (`test_p09_proxy_auth.py:219`, `test_p17_injection.py:149`).
Lokal: `xvfb-run` ada di `/usr/bin/xvfb-run` → seksi jalan (+5 check tiap file).
VPS: xvfb-run tidak ada → seksi di-SKIP. Bukan bug, bukan klaim palsu.

## 3. Bukti F5-1 lokal (download_kernel chmod crashpad/sandbox)

Skrip bukti: `/tmp/f5_kernel_proof.py` (log `/tmp/f5_kernel_proof3.log`).
Metode: `download_kernel(version="159.0.8148.0")` asli, `KERNELS_DIR`
di-override ke temp dir `~/workspace/tmp/f5-kernel-proof` (bukan /tmp: tmpfs
512 MB kekecilan; ZIP ~210 MB + extract ~400 MB). Registry asli di-backup
lalu dipulihkan; temp dir dihapus sesudah bukti. `kernels/` asli tidak disentuh.

Hasil:
- Entry terdaftar: `chromium-159.0.8148.0`, path temp dir.
- PERM **tanpa chmod manual apa pun**: `chrome` 0o755, `chrome_crashpad_handler`
  0o755, `chrome_sandbox` 0o755 — semua executable.
- Headless launch tanpa chmod manual → `/json/version` jawab
  `Chrome/159.0.8148.0` (Protocol 1.3, HeadlessChrome/159.0.0.0).
- Registry dipulihkan (hanya `chromium-159.0.8148.0` terdaftar, sama seperti
  sebelumnya); temp dir dihapus; `kernels/` asli tetap berisi 159.0.8148.0.

### Catatan: fetch jaringan urllib ter-truncate (bukan bug F5, bukan fault filesystem)

Dua percobaan `download_kernel` via URL CfT gagal dengan
`ValueError: file unduhan bukan ZIP valid`. Diagnosis:

- Resolusi versi OK (2619 versi, URL storage.googleapis.com benar).
- `curl` ke URL yang sama: HTTP 200, **210.016.335 byte dalam 6,6 detik**, ZIP valid.
- `_download_file` (urllib, UA `StealthXGM-kernel-manager`): berhenti di
  **204.703.254 byte** (kurang 5.313.081 byte) — stream putus diam-diam,
  `zipfile.testzip()` → `BadZipFile`. Terulang 2x.
- Jadi: gateway VM ini memotong stream urllib (flaky, sudah pernah terjadi —
  unduhan F3 dulu berhasil). Bukan bug di `_chmod_kernel_binaries` dan bukan
  gangguan filesystem (tulis file lokal semua lolos).
- Workaround bukti: ZIP diunduh via curl (terverifikasi valid), lalu
  `download_kernel(..., download_url="file://...")` — jalur kode yang sama
  (extract → chmod → pindah → chmod → registry), hanya fetch jaringannya
  yang diganti transport. Bagian yang diuji F5-1 (extract + chmod) teruji penuh.

## 4. Verdict fault filesystem: REDA (berdasarkan bukti run ini)

- Suite 3,7 menit + ribuan tulis (tempfile, profil browser, log): **0 error
  EPERM / "No usable temporary directory"**.
- Probe tulis 09:53 WIB: 20/20 lolos (10 /tmp + 10 home), mkdtemp OK.
- Kerjaan pagi ini (commit F5, log perbaikan, laporan ini) semua ke-save.
- Caveat jujur: fault ini historisnya flip dalam hitungan detik dan pernah
  reda sesaat lalu kambuh — "REDA" adalah verdict untuk run ini, bukan
  jaminan permanen. Patokan lanjutan: cron live-stealth Senin 09:00 WIB dan
  retry Hermes.

## 5. Yang TIDAK dilakukan (sesuai stop condition)

- Tidak ada perbaikan kode; tidak ada panggilan Hermes; tidak ada packaging;
  tidak ada tes detektor; tidak ada yang berbayar; VPS tidak disentuh.

## File bukti

- `/tmp/verify-local-2026-11-08.log` — output suite lengkap (702/0)
- `/tmp/f5_kernel_proof.py` + `/tmp/f5_kernel_proof3.log` — bukti F5-1 lokal
- `~/workspace/antibrowser/FIX-LOG-F5-TEMUAN-VPS-2026-11-08.md` — log perbaikan F5
- `~/workspace/antibrowser/VPS-SUITE-REPORT-2026-11-07.md` — laporan suite VPS (692/0)
