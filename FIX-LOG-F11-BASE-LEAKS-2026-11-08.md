# FIX-LOG F11 — Base-Level Leak Fixes — 2026-11-08

Order (Gil, 2026-11-08 19:20 WIB): "Gw mau lu fix dulu dari base dulu. Semua
data kebocoran harus kita fix dari base bener GK?" — fix ALL remaining leak
data at BASE level first (real rendering/data, not reported spoof values).

Base = mesin yang gambar beneran (renderer SwiftShader, Skia, fontconfig,
audio path). Spoof = nilai yang dilaporin. F9 fixed Canvas at BASE (flag
`--disable-accelerated-2d-canvas`, real Skia CPU path). F8/F10 fixed WebGL at
SPOOF level (measured tier tables). F7B fixed worker flags at spoof level.

Main HEAD before F11: `a77ae65` (F10B). Suite baseline: 880 PASS / 0 FAIL.

## 1. BEFORE-measurement (rerun7, 2026-11-08, fresh)

Method: CreepJS local-served (127.0.0.1:18083) + browserleaks local copy
(127.0.0.1:18084, `/canvas.html` `/webgl.html` `/fonts.html` — extensionless
URLs FAIL: http.server serves them as application/octet-stream and Chrome
starts a download instead of rendering; fixed in `tests/f11_detector_run.py`).
3 frozen GPU profiles, kernel CfT 159.0.8148.0, spoof active.
Evidence: `tests/live-reports/detector-2026-11-08-rerun7/<rtx4090|rx6800|uhd630>/`
(creepjs.txt/html/png + bl-*.txt/html/png + identity.json per GPU).

### CreepJS — IDENTICAL on all 3 GPUs
- rejected: **0**, lies: **0**, bold-fail: **9**
- ALL 9 bold-fail are in the **Audio** section, one line:
  `sum: 124.04347` + 9 bold digits (`776696522`). Hash `3dc3901e`.
- WebGL clean: hash `014a71b6` (RTX 4090), params (78), exts (67).
- Canvas 2d clean (hash `9fdb086f`). Worker clean (id-ID, 1 Dolar Amerika
  Serikat, Asia/Jakarta -420, RTX 4090, confidence high). Fonts clean
  (load 22/51, `document.fonts.check` spoof). Headless 31% like-headless,
  0% headless, 0% stealth. Screen, Timezone, Navigator, DOMRect, SVGRect,
  Intl, Speech, Media — all clean.
- Sections: **20 of 21 clean** (only Audio flagged). Leak = 1/21 sections.

### browserleaks — before (rtx4090; rx6800/uhd630 identical counts)
- /canvas: signature `1D0C427FFF9F316B11B2F8E2C64F99FA`, 220x30 PNG, 944 colors.
  (Uniqueness lookup fails: "Data retrieval error" — needs browserleaks.com
  server, unreachable from this VM. Signature itself is the measurement.)
- /webgl: Report Hash `BFE591DF15C190775E628F3F83194049`, Image Hash
  `5F72324B79E619BEA91FEA43B6622487`. Unmasked Vendor `Google Inc. (NVIDIA)`,
  Unmasked Renderer `ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 (0x00002684)
  Direct3D11 vs_5_0 ps_5_0, D3D11)`. Params match RTX 4090 table
  (Max Vertex Uniform Vectors 4095, Max Fragment 1024, Viewport
  [32767,32767], Max Samples 8, Anisotropy 16, Draw Buffers 8).
- /fonts: **229 fonts and 112 unique metrics found**, fingerprint
  `98F7A1A4DDDE20A3208E96E9FF37430B`.
  - Windows fonts PRESENT (measured by offsetWidth, real rendering):
    **6 of 50** — Arial, Calibri, Cambria, Courier New, Georgia, system-ui.
    (All via metric-compatible substitutes already installed: Liberation /
    Carlito / Caladea / Gelasio — NOT real MS fonts.)
  - Windows fonts ABSENT: **44** — Arial Black, Arial Narrow, Candara,
    Comic Sans MS, Consolas, Constantia, Corbel, Impact, Lucida Console,
    Lucida Sans Unicode, Microsoft Sans Serif, Palatino Linotype, Segoe UI,
    Segoe UI Symbol, Tahoma, Times New Roman, Trebuchet MS, Verdana,
    Segoe MDL2 Assets, Segoe UI Emoji, Segoe UI Historic, MS Gothic,
    MS PGothic, Meiryo, Meiryo UI, Malgun Gothic, Microsoft YaHei,
    Microsoft JhengHei, SimSun, PMingLiU, Yu Gothic, Yu Gothic UI,
    Cambria Math, Aldhabi, Gadugi, Myanmar Text, Nirmala UI,
    Leelawadee UI, Javanese Text, HoloLens MDL2 Assets, Bahnschrift,
    Ink Free, Segoe Fluent Icons, MS Shell Dlg.
  - Linux/Noto families detected: **199** — the bulk of the 229.
    A Windows machine has ZERO Noto/DejaVu/Liberation fonts.

## 2. CLASSIFICATION (every remaining leak)

| # | Leak | Location | Class | Disposition |
|---|------|----------|-------|-------------|
| 1 | Audio sum `124.04347776696522` not in KnownAudio allowlist (9 bold digits) | CreepJS Audio, all GPUs + plain-Chromium control | **(iii) real hardware** | See §3. NOT fixed. Hermes consulted by merra (parallel, findings pending). |
| 2 | 14 WebGPU `architecture` values unverified (GCN, RDNA4, RDNA3.5, Xe-HPG, Xe2) | `section_webgpu()` fallback for 14/82 models | **(ii) spoof data — now VERIFIED** | Fixed in F11 §4 from Dawn source. No rebuild. |
| 3 | Iris Plus 655 `gen-9` = family inference, not observed | `section_webgpu()` | **(ii) — now VERIFIED** | Dawn `GPUInfo.cpp` lists IrisPlus655 (0x3EA5/0x3EA8) under gen9. Confirmed. |
| 4 | 44 Windows fonts ABSENT at rendering level (browserleaks measures real metrics, not `document.fonts.check`) | fontconfig / `/usr/share/fonts` | **(i) base-fixable** | Fixed in F11 §5: real MS core fonts installed. |
| 5 | 199 Linux/Noto fonts PRESENT while identity claims Windows | fontconfig / `/usr/share/fonts` | **(i) base-fixable (config)** | Experiment in F11 §6: fontconfig restriction. Decision pending measurement. |
| 6 | Segoe UI + ClearType collection beyond Carlito/Caladea (Consolas, Candara, Corbel, Constantia, Tahoma, Segoe UI Emoji, CJK fonts) have NO real font file | fontconfig | **(iii) no free real font exists** | Selawik (MS open-source Segoe UI metric-compatible) ships only UFO sources, no compiled .ttf; README notes missing kerning. Building it is possible but the result would NOT be Segoe UI (family name differs; needs fontconfig alias). NOT attempted. Documented as known gap. |
| 7 | test_p13 step 4 passes VACUOUSLY when .deb absent (empty stdout, all `not in ""` asserts pass) | `tests/test_p13.py` | test bug, not a leak | Fixed in F11 §7 (drive-by). |
| 8 | browserleaks local copy lost in /tmp wipe (F6); never re-run since F5 | measurement gap | — | Rebuilt + re-run in F11 (rerun7). See §1. |
| 9 | real creepjs.org never tested (VM gateway blocks Chromium TLS); IP/WebRTC never tested (needs a server) | measurement gap | — | Out of scope for F11 (environment limit, not a code leak). Local-served CreepJS measures the real fingerprint computation; only the origin is localhost. |
| 10 | WebGL base = SwiftShader, not a real GPU (5 `getExtension()` nulls: KHR_parallel_shader_compile, WEBGL_blend_func_extended, EXT_render_snorm, EXT_texture_norm16, WEBGL_provoking_vertex) | ANGLE/SwiftShader | **(iii) real GPU hardware** | No rebuild fixes this (see §8). CreepJS + browserleaks do NOT check list-vs-getExtension consistency, so it is not currently flagged by any detector we run. |
| 11 | 12 Apple models `webglWouldPass` False (CreepJS list has no Metal hashes; real M4 Pro Mac produces the same hash) | CreepJS allowlist | not a leak | Unchanged. Real Macs fail the same check. |

## 3. AUDIO — root cause SOLVED by Hermes (RustFFT), fix = CfT 152 + flag (class i)

**CORRECTION to the interim conclusion above (machine-dependent): that was
WRONG. The real root cause was found by Hermes (merra's direct call, report
`hermes-audio-2026-11-08.md`, read in full by F11 + its raw evidence verified
in `/home/hatch/.hermes/cache/scratch/hermes-audio-20261108-660464f0d3fa/`):
Chromium's native FFT backend changed PFFFT → RustFFT in Chrome 152.**
CreepJS's KnownAudio allowlist holds PFFFT-era sums. Our sum
`124.04347776696522` is genuine unmodified Chrome 159 output — the same sum
on 156, 157 and 152 default. The difference vs the allowlisted sum is only
`0.00000249180448` (max per-frame diff 8.94e-08). My own F11 probe (156 vs
159 identical) is CONSISTENT with this: both are RustFFT-era, so both give
the same RustFFT sum. It was never CPU-dependent.

Hermes' measurement (8 versions: 120, 131, 142, 151 → `124.04347527516074`
IN allowlist; 152, 156, 157, 159 → `124.04347776696522` NOT in allowlist;
13 launches, 35 renders, 4 full CreepJS pages): **same-152-executable A/B**
(SHA-256 `115ee0fc6d26768ec757db2b0c6f54554dece46b59e96c7eca653c944db7f3de):
default RustFFT → 9 bold digits; **`--disable-blink-features=WebAudioRustFft`
→ PFFFT buffer restored byte-for-byte, sum `124.04347527516074`, 0 bold
digits.** Same flag on 159 has NO effect (legacy FFT path removed in 159,
commit `39e79486d2f63738c0f047f9b709989623fb8906`; RustFFT reland
`0d3c3f478f9c4d1c5e2ce9f9c6fae6c0f19a41a0` explicitly accepted the
fingerprint change). The 9 digits do NOT trigger CreepJS's
`LowerEntropy.AUDIO` predicate (tuple gain/freq/time absent from the locked
table; Audio container is `relative col-four`, hash class plain `hash`, not
`rejected`) — decoration against a stale reference, and EVERY genuine
Chrome 152+ user gets the same 9 digits.

**Fix implemented in F11 (class i — real rendering path, no rebuild):**
- Flag appended to the EXISTING switch in `launcher/launcher.py:471`
  (CodeGraph explore+impact on `build_launch_args` first; blast radius:
  `_launch_profile_inner`, `launch_profile`; tested via
  `launcher/test_launcher.py` + 18 detector/test files):
  `"--disable-blink-features=AutomationControlled,WebAudioRustFft"`
  — appended to the same comma-separated value, NOT a duplicate switch
  (Hermes' warning). Harmless no-op on 159; active only on a 152 kernel.
- Kernel **CfT 152.0.7977.82 installed via the kernel manager** (normal
  CfT URL download — worked this time, no gateway truncation):
  `kernels/152.0.7977.82/chrome-linux64/chrome`, binary reports
  `Google Chrome for Testing 152.0.7977.82`; registry entry
  `chromium-152.0.7977.82`.
- **F11 independent verification: DONE — PASSED** (`tests/f11_audio_verify152.py`,
  rerun9, output `tests/live-reports/detector-2026-11-08-rerun9-152audio/rtx4090/`):
  raw audio sum in the page (exact CreepJS render) = **`124.04347527516074`**,
  `match PFFFT: True`; full CreepJS page: **bold-fail=0, rejected=0, lies=0**
  (regex count on creepjs.html, read by F11: 21 clean `hash` spans, Audio
  section `sum: 124.04347527516074`). This is the FIRST fully-clean CreepJS
  run in the project (159-kernel runs all had 9 Audio bold-fail). Mechanism
  confirmed from code: `sync_identity_chrome_version` (launcher.py:109)
  forces `ident["chrome_ver"]` = the real kernel version, so the 152 profile
  reports Chrome/152.0.0.0 consistently everywhere (UA, userAgentData,
  Features 113-115+) — NO 152-vs-159 mismatch exists to flag. The trade-off
  is therefore ONLY the kernel age (below), not an internal inconsistency.

**Kernel trade-off (for Gil's decision — NOT silently swapped):** the fix
only works on the 152 kernel, which is 7 versions behind 159 (older
security patches; sites see Chrome 152). The default kernel STAYS 159
unless Gil decides otherwise. The 152 kernel is now AVAILABLE as a
per-profile choice (kernel manager / UI) for profiles that need Audio-clean.
Per-profile choice means: a profile created/launched on 152 is Audio-clean
AND fully self-consistent; a profile on 159 keeps current patches but shows
the 9 Audio digits (which CreepJS itself does not count as a rejection —
every genuine Chrome 152+ user shows them).

## 4. WEBGPU ARCH — 14 models VERIFIED from Dawn source (class ii, fixed)

Source (fetched 2026-11-08, authoritative — Dawn is what Chrome ships):
- `src/dawn/gpu_info.json` (Dawn HEAD): device-ID -> architecture table.
- `generator/dawn_gpu_info_generator.py` `js_enum_case()`: lowercase,
  hyphen inserted between chunks EXCEPT when the previous chunk ends in a
  digit. This CONFIRMS the existing values: "Gen 12 LP" -> `gen-12lp`
  (not `gen-12-lp`), "Gen 9" -> `gen-9`.
- `src/dawn/native/metal/PhysicalDeviceMTL.mm`: macOS 13+/iOS 16+ with
  Metal3 family -> `metal-3`. Confirms Apple value.
- `src/dawn/common/GPUInfo.cpp`: `IrisPlus655 = {0x3EA5, 0x3EA8}` in the
  gen9 section (Mesa iris_pci_ids.h). Confirms Iris Plus 655 -> `gen-9`
  (was "family inference" in F10B; now source-confirmed).

Mapping applied (mask: AMD 0xFFF0, Intel 0xFF00, NVIDIA 0xFFFFFF00;
PCI IDs from `fingerprint/devices.py` PCI_IDS):
- RX 580 / RX 590 (0x67DF -> 0x67D0, GCN 4) = `gcn-4`
- RX 9060 XT (0x7590), RX 9070 / RX 9070 XT (0x7550, RDNA 4) = `rdna-4`
- 8060S (0x1586 -> 0x1580, RDNA 3) = `rdna-3` — Dawn has NO "RDNA 3.5"
  entry; the 0x158x range maps to RDNA 3. The marketing name is not what
  Dawn reports.
- Arc 130V / 140V (0x64A0 -> 0x6400, Xe 2 LPG) = `xe-2lpg`
- Arc A380 / A580 / A750 / A770 (0x56A5/A2/A1/A0 -> 0x5600, Gen 12 HP)
  = `gen-12hp`
- Arc B580 / B570 (0xE20B/E20C -> 0xE200, Xe 2 HPG) = `xe-2hpg`

Also re-verified against Dawn: NVIDIA turing/ampere/lovelace/blackwell,
AMD rdna-1/2/3, Intel gen-9/gen-12lp, Apple metal-3 — all correct already.

Change: `fingerprint/canvas_audio.py` `section_webgpu()` — 6 new branches
+ comment documenting the Dawn source. CodeGraph: `explore section_webgpu`
+ `impact section_webgpu` before edit (blast radius: caller
`fingerprint/_core.py`; tested via `tests/test_f10_multi_gpu.py`).
Verification (no live browser needed): the JS regex chain replicated in
Python against all 82 `_wDesc` strings from `_mk()` vs the Dawn-derived
expected map — **82 models, 0 mismatches**. Live verification: F10B
all-82 probe re-run (see §9).

## 5. FONTS — real MS core fonts installed (class i, fixed)

Legitimate route only: `apt` (Ubuntu noble multiverse) +
`ttf-mscorefonts-installer` 3.8.1ubuntu1, which downloads the fonts from
SourceForge (the package's own sanctioned source) and installs them with
cabextract. EULA pre-accepted via debconf (required, non-interactive).
No pirated bundles, no third-party font packs.

- `apt-get update` finished 2026-11-08 (71.1 MB in 12min 34s, proxy
  ~94 kB/s; one mirror hit "Connection failed" then retried OK).
- Install attempt 1 FAILED on dpkg lock (another apt-get, pid 41086,
  `apt-get install -y scrot`, was running — NOT killed; waited ~90 s
  until the lock freed). Attempt 2 succeeded.
- Packages (dpkg `ii` verified): ttf-mscorefonts-installer 3.8.1ubuntu1,
  fonts-crosextra-caladea 20200211-2 (metric-compatible Cambria),
  fonts-crosextra-carlito 20230309-2 (metric-compatible Calibri).
- Installed to `/usr/share/fonts/truetype/msttcorefonts/` (real Microsoft
  fonts, fc-list verified): Andale Mono, Arial (+Bold/Italic),
  Arial Black, Comic Sans MS, Courier New, Georgia, Impact,
  Times New Roman, Trebuchet MS, Verdana, Webdings.
  (Tahoma is NOT in the core-fonts package — it never was; still absent.)
- fc-list total: 1,884 -> 2,053 fonts.

Expected effect (measured in rerun8, §9): browserleaks Windows-present
6 -> ~13 (Arial Black, Comic Sans MS, Impact, Times New Roman,
Trebuchet MS, Verdana, +Andale Mono/Webdings if in the test list).

## 6. FONTCONFIG RESTRICTION — experiment (class i, pending decision)

Config: `fingerprint/fonts-windows-only.conf` (written, NOT yet wired
into the launcher). It includes the system fonts.conf and rejects
(<rejectfont> by file glob) every Linux-only font directory:
noto/* (1,812 files incl. Noto Color Emoji), dejavu/*, droid/*,
liberation/*, libreoffice/*, lyx/*, opentype/noto/*,
opentype/urw-base35/*, X11/*, type1/*. Kept: msttcorefonts/* (real MS)
+ crosextra/* (Carlito/Caladea).

Intended effect: browserleaks /fonts goes from 229 detected (199 Linux)
to ~15 Windows-only fonts — the font list of a minimal Windows install.
Applies ONLY to the browser process (FONTCONFIG_FILE env, set next to
the LANG/LC_ALL/TZ block in launcher.py). System fonts outside the
browser are untouched.

KNOWN trade-off (documented in the config, not hidden): CJK and emoji
have NO font left in the browser process -> render as tofu boxes. A real
Windows machine has MS Gothic/Meiryo/Yu Gothic + Segoe UI Emoji; those
font files are NOT available free, so there is no real replacement.
Generic sans-serif/serif/monospace fall back to Arial/Times/Courier
(Windows-like behaviour).

Decision: measure first (experiment run vs rerun8), then decide with
evidence. If the list is clean AND normal pages still render, wire it
into the launcher; if CJK/emoji breakage is unacceptable, leave it
unwired and report the trade-off to Gil.

**MEASURED — experiment COMPLETE (`tests/f11_fontconfig_test.py` + retest
`tests/f11_fontconfig_retest.py`, output `tests/live-reports/f11-fontconfig-test/`):**
- browserleaks /fonts: **27 fonts / 12 unique metrics** (was 247/129
  without restriction; 229/112 before the MS fonts install). Fingerprint
  `AB5265DB344524CC07E2A7E6D0641CE9`. The restriction WORKS — Linux/Noto
  fonts are hidden from the browser process.
- CreepJS on the restricted profile: bold-fail 10 (9 Audio + 1 Worker
  `id` — the intermittent flake, 2nd occurrence in 13 runs, unrelated to
  fonts). NO new font-related flag; Fonts section stayed clean.
- First screenshot came back BLANK — investigated, NOT a rendering break:
  the `data:` URL page never painted (harness artifact). Retest served the
  SAME content over HTTP: innerText len 266, Arial div height 32 — the
  page renders.
- Retest screenshot VIEWED by F11 (R50): Latin renders perfectly (Arial,
  Times, Segoe UI fallback, symbols €£¥©®™→ ∞≠ all fine). **CJK renders
  as tofu boxes** (Chinese/Japanese/Korean all □) and **emoji renders as
  tofu boxes** (all 6 □) — exactly the documented trade-off, now seen,
  not assumed.

**DECISION: NOT wired into the launcher (default OFF).** Wiring it in
trades one tell for another: it hides the Linux font set but makes CJK +
emoji visibly broken — a real Windows machine renders both fine, so tofu
everywhere is itself a detectable tell AND a UX break for real browsing.
The mechanism is proven and ready as a PER-PROFILE opt-in (config file +
FONTCONFIG_FILE env, launcher inherits os.environ) for profiles that
never need CJK/emoji — Gil decides. A full fix would need real MS CJK
fonts (MS Gothic/Meiryo/Yu Gothic) + Segoe UI Emoji, which are NOT
freely available — class (iii), no free source.

## 7. test_p13 VACUOUS PASS — fixed (drive-by)

`tests/test_p13.py` step 4 ran `dpkg-deb -c <deb>` and asserted only
`not in out` on stdout. With the .deb absent, dpkg-deb fails, stdout is
empty, and every `not in ""` assert passes — a vacuous PASS.
Fix (CodeGraph explore/impact: blast radius only `tests/test_p13.py`):
assert the .deb file exists, assert `dpkg-deb` returncode == 0, assert
stdout non-empty, then the content asserts.
Verified both ways (read the output, not the status):
- .deb present: `ALL P-13 TESTS PASS`, exit 0.
- .deb temporarily moved away: FAILS at step 4 with
  `AssertionError: .deb tidak ada: ... — langkah 4 tidak boleh lolos
  vacuous`, exit 1; .deb restored afterwards (153,856 bytes, in place).

## 8. CLASS (iii) — CHROMIUM REBUILD COSTS (Gil decides; NOT started)

Official requirements (Chromium docs, `docs/linux/build_instructions.md`):
- RAM: 8 GB minimum, **16+ GB highly recommended** (link step peaks
  ~16-24 GB).
- Disk: **100 GB free minimum** (checkout ~30 GB git cache + build
  output ~50-80 GB).
- Fetch: ~30 minutes on a fast connection.
- Build: 2-8 hours on good hardware (16 vCPU ~2 h for `chrome`;
  36 vCPU ~50 min).

This VM: **4 vCPU, 7 GB RAM, 115 GB free disk.**
- RAM is BELOW the 8 GB minimum and far below 16 GB recommended — the
  `chrome` link step would almost certainly OOM/fail or thrash.
- Fetch at this VM's proxy speed (~94 kB/s measured during apt update):
  ~30 GB would take ~3.7 DAYS.
- Build time on 4 vCPU: 8-16+ hours IF it completes at all.
Verdict: a Chromium rebuild is NOT feasible on this VM. It would need a
bigger machine (e.g. cloud VM 16+ vCPU / 32+ GB RAM / 200 GB disk;
one public report: 2 h for ~$2 on a GCP n2-standard-32 spot VM).
No purchase/rental was made — this is a cost report only.

What a rebuild would NOT fix (honest scope):
- Audio sum: SUPERSEDED — the fix is CfT 152 + `--disable-blink-features=
  WebAudioRustFft` (F11 §3, independently verified: 0 bold-fail). A rebuild
  is NOT needed for Audio. (The interim "machine-dependent" theory was
  wrong; the cause was the PFFFT→RustFFT backend change in Chrome 152.)
- WebGL base (SwiftShader): a rebuild cannot create a GPU. The 5
  `getExtension()` nulls are SwiftShader not implementing those
  extensions; adding them means implementing them in SwiftShader (a
  large task, not a flag). Real GPU hardware (or a GPU cloud VM with
  passthrough) is the fix. The Mille approach (privately modified
  Chromium/SwiftShader reproducing NVIDIA rendering) has its source
  withheld and is unverified — not actionable.
- Nothing else remaining needs a rebuild: Canvas is fixed by a flag (F9),
  fonts by real files (F11 §5-6), WebGPU arch by verified data (F11 §4).

## 9. AFTER-measurement

### rerun8 (after real MS fonts installed — §5)
CreepJS: 9 bold-fail (Audio only) on rtx4090 + rx6800; uhd630 = 10
(9 Audio + 1 Worker `id` span — see retest below). WebGL hash `014a71b6`
unchanged, Canvas clean, Worker clean otherwise. browserleaks /fonts:
247 fonts / 129 unique metrics (was 229/112); Windows PRESENT 10/50
(was 6: +Comic Sans MS, Impact, Trebuchet MS, Verdana). /canvas signature
changed (text rendering uses the new fonts — expected, not a regression).
/webgl Report Hash unchanged `BFE591DF15C190775E628F3F83194049`.

### uhd630 worker "id" flag — RETEST (3 fresh launches, `tests/f11_retest_uhd630.py`)
**Result: 0/3 recurs** (all three tries bold-fail total = 9, Audio only,
id-flag = 0). Across all runs the flag appeared 1/12 times (rerun6 0/3,
rerun7 0/3, rerun8 1/3, retest 0/3) — an INTERMITTENT FLAKE in the F7B
shared-worker Intl normalization (timing-dependent), not a regression and
not reproducible. No code change (spoof-level, outside F11 base scope;
1-attempt investigation cap not spent on a non-reproducible flake).
Documented as a known intermittent for follow-up.

### rerun9 (Audio fix — CfT 152 + WebAudioRustFft flag, §3)
RTX 4090 frozen identity on kernel 152.0.7977.82:
**CreepJS bold-fail=0, rejected=0, lies=0 — 21/21 sections clean.**
Raw audio sum (exact CreepJS render, evaluated in the page):
`124.04347527516074` = PFFFT allowlist value. First fully-clean CreepJS
run in the project. The 152 profile reports Chrome/152.0.0.0 consistently
(UA, userAgentData, Features 113-115+) — no new flags anywhere.

### fontconfig experiment (§6)
browserleaks /fonts with restriction: **27 fonts / 12 unique metrics**
(was 247/129). Latin + symbols render fine; CJK + emoji render as tofu
(verified by VIEWING the screenshot). Decision: NOT wired in by default
— per-profile opt-in only, Gil decides.

[F10B all-82 probe re-run — pending below]

## 10. LEAK % BEFORE vs AFTER — TERISI (2026-11-09, F11 finish)

BEFORE = rerun7 (§1, kernel CfT 159, sebelum fix F11). AFTER = rerun8/rerun9
(§9) + verifikasi live F11 finish 2026-11-09 (probe 6 model + arch check).

| Area | BEFORE | AFTER |
|---|---|---|
| CreepJS sections clean | 20/21 (Audio 9 bold digits, sum `124.04347…`) | **21/21 clean, bold-fail 0, rejected 0, lies 0** (rerun9, kernel 152 + flag WebAudioRustFft; sum `124.04347527516074` = nilai allowlist PFFFT) |
| browserleaks /fonts — Windows PRESENT | 6/50 | **10/50** (rerun8: +Comic Sans MS, Impact, Trebuchet MS, Verdana — font MS asli) |
| browserleaks /fonts — total terdeteksi | 229 font / 112 metrik unik (199 Linux) | 247 font / 129 metrik (font MS menambah hitungan); **27 font / 12 metrik dengan fontconfig restriction — TIDAK di-wire default** (trade-off CJK/emoji tofu, opt-in per-profil, keputusan Gil) |
| WebGPU `architecture` terverifikasi Dawn | 68/82 (14 fallback belum terverifikasi) | **82/82 live** — arch check `tests/f11_arch_check.py` pada JSON F11 lengkap: checked=82, mismatch=0, no_branch=0, no_data=0 → PASS (2026-11-09) |
| WebGL probe 82 model | 82/82 PASS (kode F10, run 7) | **82/82 PASS (kode F11)** — JSON F11 lengkap 2026-11-09 10:35 WIB: 82 entry, 82 pass; CreepJS webglWouldPass 70/82 main + worker |
| test_p13 step 4 | lolos vacuous bila .deb tidak ada | **gagal dengan benar** bila .deb tidak ada (assert file + returncode + stdout non-empty) |
| Live-stealth mingguan (V-01/V-02) | — (belum ada run) | 2026-11-09 09:00: 10/11 (V-01 FAIL false alarm, script hardcode 156); sesudah fix V-01 (versi UA dari kernel default): **11/11 PASS** 10:03 WIB |

### Bukti F11 finish (2026-11-09, dibaca sendiri — R50)

Probe 6 model tersisa (F11 JSON sebelumnya 80 entry / 76 pass):
- `geforce-gtx-1650`, `geforce-rtx-5060`, `geforce-rtx-5060-ti`,
  `radeon-rx-5500-xt` — pass=False di JSON 8 Nov 13:34 karena **worker
  TIDAK ter-spoof** (nilai SwiftShader mentah: MAX_TEXTURE_SIZE 8192,
  37 param mismatch, unmasked_ok False; main thread 0 mismatch,
  WebGPU ok). Akarnya SAMA dengan F10B Bug 2: race injeksi worker sekali
  jalan (bukan bug per-model — keempatnya lolos di F10B run 7).
  Re-probe 2026-11-09 (74 detik, kode sama, tanpa perubahan):
  **keempatnya PASS** (main 0/77 + worker 0/77 mismatch, WebGPU ok,
  creepjs True/True). Flake terkonfirmasi, bukan regresi.
- `apple-m4-pro`, `apple-m4-max` — MISSING di JSON 8 Nov (run mati
  sebelum mencapai 2 model terakhir Apple; `.tmp` 0 byte = save
  terputus fault). Re-probe 2026-11-09: **keduanya PASS** (metal-3,
  device '', 0 mismatch main+worker; creepjs False/False = batas daftar
  CreepJS era D3D11, sama seperti Mac asli — BUKAN gagal spoof).
- JSON akhir: `tests/live-reports/f10-probes/f10-webgl-probe-all82-F11.json`
  (6.045.637 byte, 82 entry, 82 pass). Distribusi arch live: turing 7,
  ampere 8, lovelace 8, blackwell 6, gcn-4 2, rdna-1 3, rdna-2 9, rdna-3 10,
  rdna-4 3, gen-9 3, gen-12lp 3, xe-2lpg 2, gen-12hp 4, xe-2hpg 2,
  metal-3 12 (= 82; rdna-3 10 = 9 terverifikasi + 8060S).

### Sisa jujur (TIDAK diklaim selesai)

- 12 Apple `webglWouldPass` False — batas daftar hash CreepJS (Metal
  tidak ada di daftar); Mac asli pun sama. Bukan gagal spoof.
- 40 font Windows masih ABSENT (Tahoma, Segoe UI, Consolas, Candara,
  Corbel, Constantia, CJK MS Gothic/Meiryo/Yu Gothic, Segoe UI Emoji,
  dll.) — tidak ada sumber gratis yang sah (kelas iii).
- WebGL base = SwiftShader (5 `getExtension()` null, §2 item 10) —
  butuh GPU asli; rebuild tidak bisa menciptakan GPU.
- Worker `id` Intl flake: 1/12 run (intermittent, tidak tereproduksi).
- Worker-injection race flake: 1 kejadian di F10B run 1 + 4 kejadian di
  run F11 8 Nov — semua lolos saat re-launch; flakiness diketahui,
  bukan bug per-model.
- Real creepjs.org / IP / WebRTC tidak pernah dites (gateway VM blokir
  TLS Chromium; butuh server) — di luar cakupan F11.

## 11. SUITE + COMMIT — SELESAI (2026-11-09, F11 finish)

### Suite — 880 PASS, 0 FAIL (run 4, 2026-11-09 ~11:41 WIB, 509 detik)

- Baseline F10: `tests/live-reports/f10_suite_final.log` — 880/0 (30 file).
- Run 4 (pasca-reboot VM, log `tests/live-reports/f11-suite-run4.log`):
  `=== TOTAL: 880 PASS, 0 FAIL ===`, exit 0. Hitungan per-file IDENTIK
  dengan baseline F10: f10_multi_gpu 58, f3_api 86, f3_backup 49,
  f3_batch 49, f3_extensions 57, f3_freeze 21, f3_kernels 58, f3_login 63,
  f3_sync 55, f4_design 17, f5_rpa 120, p01 4, p02 4, p03 3, p04 6, p05 7,
  p06 6, p07 14, p08 6, p09 25, p10 20, p11 9, p12 15, p13 5, p14 11,
  p15 20, p16_api 19, p16_consistency 11, p17 19, p18 43.

### Jalan ke 880/0 — tiga run sebelum run 4 (dicatat, bukan disembunyikan)

1. Run 1 (`f11-suite-run.log`, 583 dtk): **874 PASS, 1 FAIL** —
   test_p06 step 5. Akar: test mock `find_chrome`, tapi launch kini
   resolve chrome via kernel manager (`resolve_kernel_chrome`, F3-4)
   duluan dan `find_chrome` hanya fallback — mock tidak pernah
   terpanggil, hasil step 5 bergantung pada sukses/gagalnya launch
   Chromium beneran (suite: launch sukses -> "did NOT proceed past
   gate"; standalone: "Chromium did not open debug port in time").
   BUKAN regresi F11 — terbukti pre-existing via git stash control:
   di kode baseline a77ae65 (perubahan F11 di-stash) test_p06 gagal
   dengan error IDENTIK. Di run baseline F10 p06 lolos 6/0 —
   kemungkinan karena fault saat itu membuat resolve gagal lalu jatuh
   ke find_chrome (mock kena). Fix (test-only, `tests/test_p06.py`):
   mock juga `kernels.resolve_kernel_chrome` -> None supaya jatuh ke
   find_chrome yang di-mock; premis test (gate lolos -> launch) tidak
   berubah. Verifikasi: standalone `python3 tests/test_p06.py` ->
   6/6 PASS, "ALL P-06 TESTS PASS". CodeGraph explore `_session_alive`
   sebelum edit (blast radius: 4 caller di launcher/launcher.py;
   edit hanya file test).
2. Run 2 (`f11-suite-run2.log`, 1246 dtk, load avg sempat 22,6):
   **878 PASS, 2 FAIL** — test_p07_locking.py step [2] (8 proses x 25
   create_profile: dapat 178/200, created 175). BUKAN regresi F11:
   F11 tidak menyentuh profiles.py / json_store.py / locking; step [5]
   (sessions.json, mekanisme lock yang sama) lolos 180/180 di run yang
   sama; run 1 p07 lolos 14/0. Verifikasi: standalone
   `python3 tests/test_p07_locking.py` -> 14 PASS, 0 FAIL. Flake
   beban/fault, bukan bug kode.
3. Run 3 (`f11-suite-run3.log`, 0 byte): MATI di tengah jalan karena
   **VM REBOOT ~11:33 WIB 2026-11-09** (uptime 1 menit saat dicek
   11:34 WIB; semua sesi proses hilang; log kosong karena stdout
   ter-buffer). Bukan kegagalan tes. Probe tulis pasca-reboot 5/5 OK.
   (Catatan: restart VM -> cek sesi browser, cron aktif, SSH VPS per
   aturan recovery pasca-restart.)

### Commit

- Hash: tidak ditulis di dalam file ini (hash commit bergantung pada
  isi file ini sendiri — self-referential); identifikasi commit via
  subjek + parent di bawah, hash lengkap di `git log -1 --format=%H`.
- HEAD sebelum: a77ae65 ("F10B: probe all 82 GPU models — 82/82 PASS").
- Isi: 5 file diubah (canvas_audio.py: 6 cabang arch baru + komentar
  Dawn; launcher.py: flag WebAudioRustFft + koreksi komentar — kernel
  152 SUDAH default sejak 2026-11-09 02:50; live_stealth_check.py: fix
  V-01 — versi UA dari kernel default; test_p13.py: fix vacuous-pass;
  test_p06.py: fix mock kernel manager) + file baru F11 (fix log ini,
  fonts-windows-only.conf, hermes-audio-2026-11-08.md, 8 script
  tests/f11_*.py).
- TIDAK ikut commit: `.kernel152-default-done` (marker runtime),
  dokumen non-F11 (ADSPOWER-*, DETECTOR-*, FIX-LOG-F5, FIX-LOG-FASE5,
  VERIFY-LOCAL, VPS-SUITE-REPORT, hermes-canvas/webgl), `tests/f7b-probe-site/`,
  `tools/`, `tests/live-reports/` (gitignored — bukti JSON + log suite
  tetap di disk, bukan di repo).

### Status akhir F11

- Audio: SOLVED (CreepJS 21/21 bersih). WebGPU arch: 82/82 live.
  Font MS: 10/50 (40 Windows masih absent — kelas iii). Fontconfig
  restriction: bekerja, TIDAK di-wire default (keputusan Gil pending).
  Kernel default: 152 (diterapkan 2026-11-09 02:50 WIB). Live-stealth
  mingguan: 11/11 PASS. Probe 82 model: 82/82 PASS. Suite: 880/0.
- Sisa jujur: lihat §10 (12 Apple webglWouldPass False, 40 font
  absent, SwiftShader base, flake worker, real creepjs.org/IP/WebRTC
  belum dites).
