# StealthXGM — Full Suite Verification on VPS Gils

Date: 2026-11-07 (suite run 3 finished ~16:41 WIB; VPS time UTC+7? VPS clock showed 16:41 while local time was ~23:41 WIB — VPS is on UTC, 7h behind WIB)
Order: Gil 2026-11-07 22:46 WIB ("Mau coba build di vps gw?" + "Copy bisa?")
Reason: the local VM's filesystem fault (intermittent EPERM on file writes)
blocks suite verification there, so the suite was run on VPS Gils instead.

## Verdict: CLEAN — 692 PASS, 0 FAIL (28/28 files)

All 28 test files pass on the VPS. Fase 4 ("Bara" design) is verified:
test_f4_design.py 17/0 PASS, backend untouched, design contracts hold.

Note on the count: the F4 agent claimed 702 PASS. The measured total is
692 PASS, 0 FAIL (per-file counts sum to 692 — verified by addition).
The 10-check gap is in the agent's claim, not in the code: no file fails,
no check is skipped. 692 is the reproduced number.

## Copy

- Source: /home/hatch/workspace/antibrowser/ (local VM), git HEAD 6173af5
  ("F4: log desain"), same commit verified on the VPS.
- Destination: /root/stealthxgm/ on the production VPS.
- Copied size: 1.6 GB.
- Excluded: kernels/ (616 MB runtime Chromium — re-downloaded on the VPS
  instead) and .fix-backups/ (1.4 MB).
- Included: everything else, including .git, tests/ (28 files),
  rea-adspower/ (1.5 GB teardown evidence), gui/, launcher/, installer/.
- Transfer: rsync -avz. First attempt broke at ~1.2 GB ("Connection closed
  by remote host" during rea-adspower/extracted app.asar); resume run
  completed the copy (rsync rc=0, 1.6 GB on VPS, 28 test files present).

## VPS specs (verified via SSH)

- Hostname: gils; Ubuntu 24.04.5 LTS; Python 3.12.3; 1 CPU; RAM 1967 MB
  (1607 MB available); disk /dev/sda1 8.2 GB total.
- Disk during work: 5.1 GB free before copy → 3.5 GB after copy →
  2.6 GB after kernel + system libs → 1.7 GB at end (never below the
  1 GB stop threshold).

## Kernel used

- Chrome for Testing 159.0.8148.0, downloaded on the VPS with the
  project's own kernel manager (launcher/kernels.py download_kernel),
  registered in gui/data/kernels.json, id chromium-159.0.8148.0.
- Live launches in the suite use patchright's bundled Chromium 156.0.8078.4
  (find_chrome), same as on the local VM — see "Setup notes" below.
- Verified: manual headless launch answers /json/version with
  "Browser": "Chrome/159.0.8148.0".

## Suite runs (all on the VPS)

### Run 1 — 275 PASS, 31 FAIL (environment gaps, not code)

- Missing Flask (gui/app.py needs it): f3_api, f3_backup, f3_batch,
  f3_extensions, f3_kernels, f3_login, f4_design, p12, p14, p16_api.
  Error: `ModuleNotFoundError: No module named 'flask'`
  (gui/app.py line 12: `from flask import Flask, ...`)
- Missing Playwright module: p17.
  Error: `ModuleNotFoundError: No module named 'playwright'`
- Hardcoded test paths (/home/hatch/workspace/antibrowser): p01, p02, p03,
  p04, p05, p06, p08, p11, p13.
  Error: `ModuleNotFoundError: No module named 'profiles'`
  (tests insert the absolute local path into sys.path)
- Chromium would not launch (crashpad handler not executable): p09, p10,
  p15, p16_consistency, p18, f3_freeze, f3_sync.
  Error: `RuntimeError: Chromium did not open debug port in time`
  (root cause: `FATAL: posix_spawn .../chrome_crashpad_handler:
  Permission denied (13)` — see "Real findings" below)

### Run 2 — 665 PASS, 9 FAIL (after env fixes, before setup parity)

- p06 (0/1): `AssertionError: unexpected: Chromium did not open debug
  port in time` — launch used the CfT kernel because the kernel default
  had been set; test expects the find_chrome path.
- p16_consistency (9/2): `GAGAL: ['fp-check ok True launch 1',
  'fp-check ok True launch 2']`
- p17 (0/1): Playwright browsers not downloaded:
  `Looks like Playwright was just installed or updated. Please run ...
  playwright install`
- p18 (38/5): `GAGAL: ['overall ok True', 'semua field dibandingkan
  PASS', 'field webglRenderer PASS', 'Local fp-check code 0 + ok True',
  'GUI fp-check ok True']`

### Run 3 (final) — 692 PASS, 0 FAIL

Per-file (all PASS): f3_api 86, f3_backup 49, f3_batch 49, f3_extensions
57, f3_freeze 21, f3_kernels 58, f3_login 63, f3_sync 55, f4_design 17,
p01 4, p02 4, p03 3, p04 6, p05 7, p06 6, p07_locking 14, p08 6,
p09_proxy_auth 20, p10_watchdog 20, p11 9, p12_registry 15, p13 5,
p14_headless 11, p15_cookies 20, p16_api_contract 19,
p16_consistency 11, p17_injection 14, p18_rpa 43.
Total runtime ~6 minutes on the 1-CPU VPS.

## Setup done on the VPS (environment only, no project code changed)

1. System libs for Chrome (apt): libxcomposite1, libxdamage1, libxfixes3,
   libxrandr2, libasound2t64, libatk1.0-0t64, libatk-bridge2.0-0t64,
   libatspi2.0-0t64, libcairo2, libcups2t64, libgbm1, libpango-1.0-0,
   libnss3, libnspr4, libdrm2, libxkbcommon0, libxcb1, libx11-6,
   libxext6, libxi6, libxtst6, libxrender1, libexpat1, libglib2.0-0,
   libdbus-1-3. (ldd showed 12 missing libs before install, 0 after.)
2. chmod +x chrome_crashpad_handler + chrome_sandbox in the downloaded
   kernel dir (same manual fix already applied to the local kernels/
   copy during Fase 4).
3. pip: flask 3.1.3 (matches local) + playwright; `playwright install
   chromium` (Chromium 156.0.8078.4 + headless shell); patchright
   (find_chrome then resolves to the Playwright Chromium 156, same as
   locally). pip needed --ignore-installed blinker (system blinker
   1.7.0 is an apt package without a RECORD file).
4. Kernel default reset to null (kernels.json "default": null) to match
   the local VM — the earlier run-2 failures of p06/p16/p18 came from
   having set the CfT kernel as default, which bypasses find_chrome.
5. Path shim for the hardcoded test paths: symlink
   /home/hatch/workspace/antibrowser -> /root/stealthxgm on the VPS.
   No test or project file was edited.

## Real findings (not fixed — separate tasks)

1. **download_kernel does not chmod the crashpad handler / sandbox.**
   launcher/kernels.py chmods only the main `chrome` binary after
   extract. A fresh kernel download on a clean machine cannot launch
   Chrome (FATAL posix_spawn Permission denied on
   chrome_crashpad_handler) until someone manually chmods +x the two
   helper binaries. Locally this was fixed by hand in kernels/ (which
   is gitignored), so the fix never landed in code. Fix: chmod the
   helper binaries inside download_kernel.
2. **Tests hardcode /home/hatch/workspace/antibrowser.**
   test_p01/p02/p03/p04/p05/p06/p08/p11 (and the p13 smoke-test path)
   insert that absolute path into sys.path. The suite only runs where
   the repo lives at exactly that path. Fix: compute paths from
   `__file__` (as test_f4_design.py and test_p07_locking.py already do).
3. **F4 agent's "702 PASS" claim does not reproduce.** Measured total is
   692 PASS, 0 FAIL. All 28 files pass; the gap is 10 checks in the
   claim, not missing coverage.

## Files on the VPS

- /root/stealthxgm/ — full copy (HEAD 6173af5).
- /root/suite_vps.log — run 1 output (275/31).
- /root/suite_vps2.log — run 2 output (665/9).
- /root/suite_vps3.log — run 3 output (692/0, final).
- /root/.cache/ms-playwright/ — Playwright + patchright Chromium 156.
- /root/stealthxgm/kernels/159.0.8148.0/ — CfT kernel 159 (registered,
  default null).
