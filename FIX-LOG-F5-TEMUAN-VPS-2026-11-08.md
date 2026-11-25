# StealthXGM — Perbaikan 2 Temuan VPS (F5)

Tanggal: 2026-11-08 (verifikasi VPS selesai ~02:53 UTC / 09:53 WIB)
Perintah: Gil 2026-11-08 09:32 WIB ("Gas, perbaiki 2 temuannya")
Sumber temuan: `VPS-SUITE-REPORT-2026-11-07.md` (suite 692 PASS / 0 FAIL,
28/28 file — 2 temuan nyata tidak diperbaiki saat itu)

## Verdict: KEDUA TEMUAN TERPERBAIKI + TERVERIFIKASI — 692 PASS, 0 FAIL

Suite penuh di VPS Gils SETELAH perbaikan, TANPA shim path, kode hasil fix:
`=== TOTAL: 692 PASS, 0 FAIL ===` (28/28 file, per-file di bawah).
Kernel fresh hasil unduh ulang via `download_kernel` (kode baru) launch
headless TANPA chmod manual: `/json/version` jawab `Chrome/159.0.8148.0`.

## Temuan 1 — download_kernel tidak chmod crashpad handler / sandbox

### Masalah
`launcher/kernels.py::download_kernel` hanya `os.chmod(binary, 0o755)`
untuk `chrome`. ZIP Chrome for Testing tidak menyimpan bit exec, jadi
kernel fresh tidak bisa launch Chrome sampai di-chmod manual:
`FATAL: posix_spawn .../chrome_crashpad_handler: Permission denied (13)`.
Lokal ini hanya diperbaiki manual di `kernels/` (gitignored) — tidak
pernah masuk kode.

### Perbaikan (commit `9e49311`)
Helper baru `_chmod_kernel_binaries(chrome_dir)` + konstanta
`_KERNEL_EXECUTABLES = ("chrome", "chrome_crashpad_handler",
"chrome_sandbox")`. Di-chmod 0o755 untuk nama yang dikenal DAN file
tanpa ekstensi lain di `chrome-linux64/` (calon helper binary di rilis
CfT mendatang). Dipanggil 2x di `download_kernel`: sesudah extract di
tmpdir, dan sesudah pindah ke `dest_dir` (menggantikan 2 blok
`os.chmod(binary, 0o755)` lama).

Unit-test lokal helper (dir palsu): `chrome`, `chrome_crashpad_handler`,
`chrome_sandbox` → 0o755; `chrome_100_percent.pak`, `resources.pak`,
`libvk_swiftshader.so`, `icudtl.dat` tetap 0o644. `py_compile` OK.

### Bukti di VPS (tanpa chmod manual sama sekali)
- Kernel lama dihapus (`rm -rf /root/stealthxgm/kernels/159.0.8148.0`,
  disk 1,6 GB → 2,0 GB free), lalu unduh ulang via kode baru:
  `ENTRY: chromium-159.0.8148.0 159.0.8148.0
  /root/stealthxgm/kernels/159.0.8148.0/chrome-linux64/chrome`
- Mode hasil unduh (ls -l, TANPA chmod manual):
  `-rwxr-xr-x chrome`, `-rwxr-xr-x chrome-wrapper`,
  `-rwxr-xr-x chrome_crashpad_handler`, `-rwxr-xr-x chrome_sandbox`;
  `.pak` tetap `-rw-r--r--`. (Heuristik tanpa-ekstensi juga
  menangkap `chrome-wrapper` — tidak berbahaya.)
- Launch headless TANPA chmod manual → `curl
  http://127.0.0.1:9333/json/version` jawab:
  `"Browser": "Chrome/159.0.8148.0"`, Protocol-Version 1.3,
  HeadlessChrome/159.0.0.0.

## Temuan 2 — Test hardcode /home/hatch/workspace/antibrowser

### Masalah
`test_p01/p02/p03/p04/p05/p06/p08/p11` memasukkan path absolut
`/home/hatch/workspace/antibrowser` ke `sys.path` (plus `open()` path
absolut di p05/p06/p11, dan `R = "/home/hatch/workspace/antibrowser"`
di p13). Suite hanya jalan bila repo ada di path itu persis — di VPS
run 3 hanya lolos berkat symlink shim
`/home/hatch/workspace/antibrowser -> /root/stealthxgm`.

### Perbaikan (commit `7ef722d`, 9 file)
Pola yang sama seperti `test_f4_design.py` / `test_p07_locking.py`:
```python
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "gui"))   # + "launcher" bila perlu
```
- p01, p04: ROOT + gui. p02, p08: ROOT + gui + launcher.
  p03: ROOT + gui + launcher (tambah `import os` — sebelumnya hanya
  `import sys`). p06: ROOT + launcher.
- p05: `open()` → `os.path.join(ROOT, "gui", "extension_manager.py")`
  dan `os.path.join(ROOT, "gui", "templates", "index.html")`.
- p06: tuple path → `os.path.join(ROOT, "gui", "app.py")` dan
  `os.path.join(ROOT, "gui", "local_api.py")`.
- p11: `open()` → `os.path.join(ROOT, "gui", "templates", "index.html")`.
- p13: `R = os.path.dirname(HERE)` (dipakai semua assert + pemanggilan
  `installer/build-copy.sh`, `smoke-test-build.sh`, `dpkg-deb`).
- Logika dan assert test TIDAK diubah, hanya resolusi path.
- Verifikasi lokal: `grep -rn "/home/hatch" tests/ launcher/ gui/*.py`
  = 0 hasil (satu-satunya sisa adalah data registry
  `gui/data/kernels.json` — path runtime, bukan kode).
  `py_compile` 9 file OK.

### Bukti di VPS (tanpa shim)
- Shim dihapus SEBELUM suite: `rm -f /home/hatch/workspace/antibrowser`;
  `ls -la /home/hatch/workspace/` = direktori kosong.
- File fix di-sync ke VPS (rsync, hanya 10 file berubah + `.git` 2,8 MB);
  HEAD VPS terverifikasi `7ef722d`.
- Suite penuh dari `/root/stealthxgm` (lihat per-file di bawah).

## Suite penuh di VPS (pasca-fix, tanpa shim)

Per-file (semua PASS): f3_api 86, f3_backup 49, f3_batch 49,
f3_extensions 57, f3_freeze 21, f3_kernels 58, f3_login 63, f3_sync 55,
f4_design 17, p01 4, p02 4, p03 3, p04 6, p05 7, p06 6, p07_locking 14,
p08 6, p09_proxy_auth 20, p10_watchdog 20, p11 9, p12_registry 15,
p13 5, p14_headless 11, p15_cookies 20, p16_api_contract 19,
p16_consistency 11, p17_injection 14, p18_rpa 43.

`=== TOTAL: 692 PASS, 0 FAIL ===` — sama persis dengan run 3
pra-perbaikan (692). Tidak ada regresi; total "702" klaim agent F4
tetap tidak ter-reproduksi (selisih 10 ada di klaim, bukan kode).

Log: `/root/suite_f5.log` di VPS.

## Insiden saat verifikasi (bukan bug kode)

1. **SSH putus di tengah suite pertama** (02:42 UTC): koneksi NAT VPS
   ditutup remote host saat suite berjalan (~4 menit). Akibat: log
   `/root/suite_f5.log` 0 byte — output `run_all.py` masih di buffer
   pipe saat proses mati. Solusi: suite diulang detached
   (`setsid nohup python3 -u tests/run_all.py > /root/suite_f5.log
   2>&1`), dicek berkala via SSH pendek. Run kedua selesai penuh
   (~10 menit, 1 CPU).
2. **Quirk shell subagent:** `~` di shell ini = `/root`, bukan
   `/home/hatch` — SSH harus pakai path absolut
   `/home/hatch/.ssh/id_ed25519` (key ada di sana, mode 600).
3. **Disk VPS:** 1,6 GB free sebelum → 2,0 GB sesudah hapus kernel →
   1,4 GB free di akhir. Tidak pernah di bawah batas stop 1 GB.

## File diubah + commit (repo lokal ~/workspace/antibrowser/)

- `9e49311` F5-1: `launcher/kernels.py` (+27/−8)
- `7ef722d` F5-2: `tests/test_p01.py`, `test_p02.py`, `test_p03.py`,
  `test_p04.py`, `test_p05.py`, `test_p06.py`, `test_p08.py`,
  `test_p11.py`, `test_p13.py` (+43/−25)
- Working tree bersih sesudahnya (kecuali 2 file .md untracked yang
  sudah ada sebelumnya, bukan bagian perubahan ini).
- VPS lain tidak disentuh. Tidak ada packaging,
  detector test, atau kerja berbayar yang dimulai — STOP sesuai perintah.
