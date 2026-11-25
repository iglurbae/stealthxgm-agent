# FIX LOG — FASE 5: Alur Lengkap (RPA ala AdsPower)

Tanggal: 2026-11-08. Perintah Gil (10:06 WIB): "Owhh gtu sok lengkapi"
(setelah tanya apa itu Alur/RPA dan apakah AdsPower punya RPA — ada,
pembeda terbesarnya). Sebelumnya Alur hanya RPA sederhana (P-18):
langkah JSON + jalankan di 1 profil.

## Yang dibangun (4 fitur, 5 commit)

| Fitur | Commit | Isi |
|---|---|---|
| F5-2 Rekam & replay | `a24eaba` | Perekam CDP di `launcher/rpa.py` (init-script + thread panen), route record GUI, `gui/rpa_loader.py` (cache modul — state perekam bertahan antar request) |
| F5-3 Template 7 platform | `70c4009` | `TEMPLATES` di `launcher/rpa.py` + route install GUI & Local API v1 |
| F5-4 Multi-profil | `a419737` | `gui/rpa_jobs.py` (job async + progres + cancel, pola F3-6) + route run-multi/jobs GUI & v1 |
| F5-1 Builder visual | `fc1c2f6` | Builder langkah di panel Alur + panel Rekam & Multi-profil di `gui/templates/index.html`, route GET template tunggal |
| F5-1 fix | `64763b9` | Builder sinkron JSON saat ketik (oninput) + screenshot `docs/design/alur-builder.png` |

## F5-2 — Rekam & replay (bukti live)

- Cara kerja: init-script disuntik ke semua halaman profil yang jalan
  (`context.add_init_script` — berlaku untuk halaman baru + sesudah
  navigasi); listener DOM menangkap klik / ketik / tombol / gulir /
  navigasi ke `window.__alur_rec` (+ sessionStorage supaya tidak hilang
  saat navigasi se-origin). Thread perekam memanen tiap 0,3 detik.
- Live E2E (test): klik `#b`, ketik "hello" di `#i`, gulir 500 —
  terekam jadi 5 langkah (`goto` + klik + klik + scroll + type);
  replay lewat `run_steps` semua langkah ok; efek DOM terbukti
  (`out='clicked'`, input terisi "hello").
- API: `POST /api/profiles/<pid>/rpa/record/start|stop`,
  `GET .../record/status` (GUI saja — state tinggal di proses GUI).

## F5-3 — Template 7 platform

YouTube, Facebook, TikTok, Instagram, Amazon, LinkedIn, Discord.
Isinya HANYA buka beranda + tunggu + gulir (navigasi umum yang aman).
TIDAK ADA login, TIDAK ADA isi kredensial, TIDAK ADA klik aksi.
Install via `POST /api/rpa/templates/<key>/install` (+ v1);
alur hasil install ditandai `template: <key>`.

## F5-4 — Multi-profil (bukti live)

- `POST /api/rpa/run-multi` `{flow|steps, profile_ids[]}` → job async;
  `GET /api/rpa/jobs[/<id>]`, `POST .../cancel` (GUI + v1).
- Worker berurutan per profil; profil yang belum jalan di-launch
  headless lalu di-stop lagi; yang sudah jalan dibiarkan jalan.
- Live E2E: 2 profil headless, alur goto + wait — keduanya ok
  (2/2 langkah ok per profil), job state done, profil di-stop lagi.
- Batas: maks 50 profil per job.

## F5-1 — Builder visual (bukti live GUI)

- Baris langkah: pilih tipe (goto/klik/isi/tunggu/gulir/tombol),
  field muncul sesuai tipe, tambah / hapus / geser ↑ ↓, sinkron ke
  textarea JSON (saat ketik maupun saat ganti tipe), "Terapkan JSON",
  "Muat ke builder", "Pakai template".
- Bukti GUI live (port 5221, headless): tambah 2 baris → JSON
  tersinkron (`ms:1500` setelah ketik); template YouTube dimuat →
  5 baris; 0 JS pageerror. Screenshot:
  `docs/design/alur-builder.png`.
- Id lama (rpaFlowName/rpaFlowSteps/rpaFlowList) + fungsi JS lama
  (rpaSaveFlow/rpaRunFlow/rpaDeleteFlow/loadRpaFlows) tetap ada.
  Tanpa nama AdsPower (RPA Plus, Synchronizer, Cookie Robot,
  SunBrowser, FlowerBrowser, AI Plus).

## Test

- Baru: `tests/test_f5_rpa.py` — **120 PASS, 0 FAIL** (unit + live +
  API + DOM + `node --check` JS Alur).
- Suite penuh lokal: **822 PASS, 0 FAIL** (29 file, ~4,5 menit),
  log `/tmp/f5_suite_final.log`. Baseline lokal sebelum Fase 5: 702 —
  selisih +120 = test F5 baru. `test_p18_rpa.py` tetap 43/0,
  `test_f3_sync.py` tetap hijau (kontrak `run_steps`/`save_flow`
  tidak berubah — hanya tambah fungsi + param opsional `extra`).
- CodeGraph dipakai sebelum edit: `explore run_steps` (77 simbol,
  3 caller, test p18 + f3_sync), `impact run_steps`/`save_flow`,
  index 73 file / 2.068 node (tidak stale).

## Bug yang ketemu & diperbaiki selama Fase 5

1. **Panen perekam yatim (closure):** poller mengganti
   `window.__alur_rec = []` (array baru) sementara listener menutup
   array `rec` lama — event menumpuk di array tak terbaca. Perbaikan:
   panen pakai `splice(0)` (in-place).
2. **Navigasi tak terekam:** listener `load` di halaman tidak bisa
   mendeteksi navigasi (init-script jalan sesudah navigasi).
   Perbaikan: poller membandingkan URL tiap halaman tiap 0,3 detik,
   termasuk halaman baru yang muncul saat merekam.
3. **Klik/ketik gagal sesudah gulir:** `bounding_box()` tanpa
   scroll-into-view memberi koordinat di luar viewport. Perbaikan:
   `scroll_into_view_if_needed()` sebelum ambil kotak di `_run_one`
   (klik + ketik).

## Catatan jujur / batasan

- Rekam hanya lewat API GUI (proses GUI). Local API v1 punya template
  + run-multi + jobs, tapi TIDAK punya record (state perekam tidak
  bisa lintas proses).
- Perekam mendeteksi navigasi penuh saja; navigasi SPA (tanpa load
  ulang halaman) tidak terekam sebagai goto.
- sessionStorage tidak tersedia di URL `data:` — perekam tetap jalan
  (try/catch), tapi pemulihan antar navigasi hanya untuk http(s).
- Multi-profil jalan BERURUTAN (bukan paralel); maks 50 profil/job.
- Template hanya starter (goto/wait/scroll) — langkah sensitif
  (login, isi kredensial) TIDAK disediakan.
- Suite lokal 822 vs VPS 692: selisih murni lingkungan (test headful
  xvfb p09/p17 di-skip di VPS) — sudah dicatat di MEMORY.md.
- Di luar scope (tetap): captcha solver, cloud sync/team, remote
  view, versi berbayar, packaging, tes detektor.

## File diubah

- `launcher/rpa.py` (perekam, template, `save_flow(extra)`,
  `scroll_into_view_if_needed`)
- `gui/rpa_loader.py` (baru — cache modul rpa)
- `gui/rpa_jobs.py` (baru — job multi-profil)
- `gui/app.py`, `gui/local_api.py` (route record/template/run-multi/jobs)
- `gui/templates/index.html` (builder + panel rekam & multi-profil)
- `tests/test_f5_rpa.py` (baru — 120 cek)
- `docs/design/alur-builder.png` (baru — screenshot bukti)
