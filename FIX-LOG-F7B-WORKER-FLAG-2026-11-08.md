# FIX-LOG-F7B-WORKER-FLAG-2026-11-08.md

**Tanggal:** 2026-11-08. **Perintah Gil (15:26 WIB, tap opsi):** "Perbaiki flag worker dulu"
— perbaiki dulu 2 flag Worker kecil dari verifikasi merra atas bukti Fase 7,
sebelum packaging/beta. **Percobaan fix: 1 dari maks 3** (Attempt 1 berhasil —
tidak perlu Attempt 2/3). Hermes TIDAK dipakai (tidak mentok).

**Hasil singkat:** KEDUA flag Worker HILANG di CreepJS re-run #3 (rerun3).
bold-fail total 13 (rerun2) → 11 (rerun3) — tepat 2 span Worker yang hilang,
tanpa flag baru. Section Worker: `id-ID (1 Dolar Amerika Serikat)` +
baris locale kosong + `Asia/Jakarta (-420)`, 0 `rejected`.

---

## Flag 1 — Worker currency USD ("1 US dollar")

**Gejala (rerun2 `creepjs.html` baris 223):**
`id-ID (<span class="bold-fail">1 US dollar</span>)` — bahasa worker klaim id-ID
tapi Intl currency-nya USD. Kontrol Chromium polos: `en-US (1 US dollar)`
tanpa flag (konsisten).

**Kode CreepJS (dibaca langsung, `creep.js` baris 1880-1899):**
- `systemCurrencyLocale = (1).toLocaleString(lang, {style:'currency',
  currency:'USD', currencyDisplay:'name', ...})` — `lang` = item pertama
  `navigator.language` ('id-ID') → "1 Dolar Amerika Serikat".
- `engineCurrencyLocale = (1).toLocaleString(undefined, {...})` — default
  native browser.
- `localeEntropyIsTrusty = engineCurrencyLocale == systemCurrencyLocale`;
  render (baris 2187-2188): kalau tidak trusty →
  `language (<span class="bold-fail">engineCurrencyLocale</span>)`.

**Root cause (terbukti, bukan dugaan):** `Number.prototype.toLocaleString`
TIDAK pernah di-patch di mana pun (grep `toLocaleString` di `fingerprint/`:
hanya pemakaian dengan locale eksplisit di `behavioral.py:105-106` dan
`_core.py:422-423`). Panggilan tanpa argumen memakai default V8 — dan
default V8 di Chrome Linux ini adalah `en-US` (VM UTC, tanpa locale) →
engine "1 US dollar" vs system "1 Dolar Amerika Serikat" → tidak trusty.

**Jalur yang GAGAL (terbukti probe, bukan asumsi):** `--lang=id-ID` sebagai
flag Chrome TIDAK mengubah apa pun — probe `tests/f7b_lang_probe.py`
(plain CfT 159, tanpa spoof): dengan dan tanpa `--lang=id-ID`, semua 7 ctor
Intl tetap `en-US`, `navigator.language` tetap `en-US`, currency tetap
"1 US dollar" (main + dedicated worker).
**Jalur yang BERHASIL:** env `LANG=id_ID.UTF-8` (+ `LC_ALL` sama) pada proses
browser → default V8 jadi `id` → semua 7 ctor `id`, currency engine
"1 Dolar Amerika Serikat" = system → trusty. Bukti:
`tests/live-reports/f7-probes/f7b-lang-probe.json`, run `withEnvLang`:
main + worker `getLocaleList: ['id']`, `currencyTrusty: true`,
`currencyEngine: "1 Dolar Amerika Serikat"`.
(Catatan: `navigator.language` di run itu ikut jadi `id-ID` +
`languages: ["id-ID","id","en-US","en"]` — sama persis dengan nilai spoof.)

**Fix (perbaikan nyata, bukan fake API):** browser benar-benar berjalan di
locale identitas — `launcher/launcher.py` `_launch_profile_inner`
(± baris 1306, tepat sesudah blok TZ F7): set `LANG` + `LC_ALL` =
locale efektif profil dalam bentuk POSIX (`id-ID` → `id_ID.UTF-8`).
Derivasi locale SAMA seperti `spoof_js` (locale profil, else timezone →
`_TZ_TO_LOCALE`). Berlaku untuk semua situs, bukan khusus detector.

## Flag 2 — Worker "languages" 2 vs 4 ("id-ID,id")

**Gejala (rerun2 `creepjs.html` baris 224):**
`<span class="bold-fail">id-ID,id</span>` — sementara Navigator main thread
menunjukkan 4 item ("id-ID, id, en-US, en") dan probe worker F7 mengklaim
languages 4 item.

**KOREKSI terhadap brief tugas (dibuktikan dari kode CreepJS):** baris itu
BUKAN `navigator.languages`. Render (`creep.js` baris 2174, 2189-2190):
`languages` di-COMMENT-OUT dari destructure; yang dirender adalah `locale`
= hasil `getLocale()` — `new Intl[<7 ctor>]()` TANPA argumen, ambil
`resolvedOptions().locale`, dedupe (`creep.js` baris 1828-1852). Kondisi
flag: `locale === language` → kosong; else `localeIntlEntropyIsTrusty`
(`new Set(language.split(',')).has('' + locale)`) → tampil polos; else
bold-fail. Jadi "id-ID,id" = daftar locale Intl hasil 7 ctor, bukan
daftar bahasa.

**Root cause (terbukti Node 24 + Chrome):** wrapper `_wrapIntl`
(`fingerprint/_core.py` main ±218, worker ±390) mengubah panggilan tanpa
argumen menjadi eksplisit `LOCALE` ('id-ID'). ICU menyelesaikan
`PluralRules('id-ID')` → `'id'` (data plural hanya terdaftar di bahasa
dasar), sementara 6 ctor lain → `'id-ID'`. Node 24: eksplisit `'id-ID'` →
PluralRules `'id'`, ctor lain `'id-ID'`; tanpa argumen + `LANG=id_ID.UTF-8`
→ semua `'id-ID'` (default path). Akibat: `getLocale()` =
`['id-ID','id']` → string `"id-ID,id"` ≠ `'id-ID'` dan tidak ada di
`{'id-ID'}` → bold-fail. `navigator.languages` 4 item di probe F7 memang
benar — tapi itu bukan yang ditampilkan/dicek di baris ini.

**Fix:** normalisasi `resolvedOptions()` pada instance yang dibuat wrapper
— bila hasil ICU adalah bahasa dasar LOCALE, laporkan LOCALE
(`_core.py`, di kedua `_wrapIntl`, main + worker). Alasan ini BUKAN
gaming-the-test: mesin id-ID asli melaporkan `'id-ID'` untuk panggilan
tanpa argumen (default path); wrapper-lah yang mengubah panggilan itu
menjadi eksplisit sehingga ICU menyelesaikan ke `'id'`. Normalisasi
mengembalikan nilai yang dilaporkan mesin asli, berlaku untuk semua situs,
tanpa mendeteksi CreepJS. Implementasi memakai `_nf` (class method) supaya
`toString` tetap native-format (queryLies) — pola yang sama dengan semua
getter lain di file ini; berlaku untuk SEMUA ctor (kondisi generik:
`r.locale === LOCALE.split('-')[0]`), bukan hanya PluralRules.

## Bukti probe worker (sesudah fix)

`tests/f7b_worker_probe.py` (+ situs probe `tests/f7b-probe-site/`:
`f7b-worker-probe.html`, `f7b-worker.js`, `f7b-sw.js`) — menjalankan
cek yang SAMA dengan logika CreepJS (getLocale 7 ctor no-arg +
currency trusty + kondisi render) di main + dedicated + shared + service
worker, via `launcher.launch_profile` (profil `f7b-worker-probe`).
Hasil `tests/live-reports/f7-probes/f7b-worker-probe.json` — KEEMPAT scope
identik:

| scope | spoofed | locale | language | currency engine = system | line1Flag | line2Flag |
|---|---|---|---|---|---|---|
| main | — | id-ID | id-ID | 1 Dolar Amerika Serikat | false | false |
| dedicated | true | id-ID | id-ID | 1 Dolar Amerika Serikat | false | false |
| shared | true | id-ID | id-ID | 1 Dolar Amerika Serikat | false | false |
| service | true | id-ID | id-ID | 1 Dolar Amerika Serikat | false | false |

Detail per scope: `getLocale` 6 ctor (DisplayNames di-skip seperti CreepJS
— ctor itu throw tanpa `{type}`) semuanya `id-ID`; `pluralNoArg` dan
`pluralExplicitIdID` keduanya `id-ID`; `languages`
`["id-ID","id","en-US","en"]`; `tzOffset -420`, `tz Asia/Jakarta`.
Log injector: `tests/live-reports/f7-probes/f7b-worker-probe-injector.log`
(worker + shared_worker + service_worker injected).

Dua bug probe yang ditemukan & diperbaiki selama kerja (BUKAN bug produk):
(1) `getLocale` probe awal mencatat error DisplayNames sebagai nilai
(`"ERR:invalid_argument"`) — CreepJS men-SKIP ctor yang throw; probe
diperbaiki mengikuti CreepJS. (2) Shared worker tidak menjawab karena
probe memakai `self.onmessage` — shared worker menerima pesan lewat port
`connect` (pola yang sama dipakai CreepJS); diperbaiki. (3) Service
worker run pertama menampilkan hasil STALE (script SW lama ter-cache di
profil) — runner sekarang menghapus direktori profil sebelum launch.

## Bukti detector CreepJS re-run #3 (rerun3)

Metode SAMA seperti F6/F7: kode detector asli di-serve lokal
(`http://127.0.0.1:18083/`, `tests/live-reports/detector-site-creepjs/`),
profil `detector-test2`, kernel CfT 159, xvfb headful, viewport 1600×900.
Runner: `tests/f7b_detector_run.py`.
Bukti: `tests/live-reports/detector-2026-11-08-rerun3/` (`creepjs.html`,
`creepjs.txt`, `creepjs.png`, `identity.json`).

- Worker section (`creepjs.html` baris 207-222, scope
  `SharedWorkerGlobalScope`, hash `abf6973f`):
  `id-ID (1 Dolar Amerika Serikat)` + baris locale KOSONG +
  `Asia/Jakarta (-420)` — **kedua span bold-fail HILANG**.
  Versi teks (`creepjs.txt` baris 47-51) sama: `id-ID (1 Dolar Amerika Serikat)`.
- `rejected` div: 0 (rerun2 juga 0).
- bold-fail total: **13 (rerun2) → 11 (rerun3)**. Sisa di rerun3 hanya
  baris 277 (WebGL), 536 (Canvas 2d), 878 (Audio digit) — ketiganya SUDAH
  ada di rerun2; **tidak ada flag baru**. Audio baris 878 identik nilainya
  di rerun2 dan rerun3 (`sum: 124.04347776696522`); Canvas hash identik
  (`9e04b0c4`). Hash WebGL berubah (`407e6a4e` → `93caa855`) HANYA karena
  identitas ad-hoc profil `detector-test2` ter-generate ulang dengan GPU
  berbeda (RTX 4090 → Intel Arc B570, layar 2560×1440 → 1600×900) —
  perilaku lama: profil ad-hoc tanpa identity tersimpan digenerate ulang
  tiap launch (`_consistent_fallback_identity` tanpa seed); section WebGL
  tetap kategori yang sama (SwiftShader, sudah dinyatakan tak-fixable di F7
  tanpa GPU fisik). Bukan efek fix ini.

## Suite

**822 PASS, 0 FAIL (29 file), exit 0** — sama persis dengan baseline F7.
Log: `/tmp/f7b_suite_final.log`, salinan di
`~/workspace/antibrowser/tests/live-reports/f7b-suite-final-2026-11-08.log`
(dibaca langsung: semua 29 baris status PASS, baris akhir
`=== TOTAL: 822 PASS, 0 FAIL ===`, `SUITE EXIT: 0`).
Per-file yang paling relevan: `test_f5_rpa.py` 120/0, `test_p18_rpa.py`
43/0, `test_p09_proxy_auth.py` 25/0, `test_p17_injection.py` 19/0,
`test_p16_consistency.py` 11/0 — tidak ada regresi dari perubahan LANG env
maupun normalisasi `resolvedOptions`. Durasi total ±7 menit (mulai
08:43 WIB, selesai ~08:50 WIB).

## File yang diubah (git diff: 2 file, +55/−2)

- `fingerprint/_core.py` — normalisasi `resolvedOptions()` di `_wrapIntl`
  main (komentar F7B baris 226) dan worker (komentar F7B baris 416).
- `launcher/launcher.py` — env `LANG` + `LC_ALL` di `_launch_profile_inner`
  (komentar F7B baris 1306).

File baru (probe + bukti, tidak mengubah produk):
- `tests/f7b_lang_probe.py`, `tests/f7b_worker_probe.py`,
  `tests/f7b_detector_run.py`, `tests/f7b-probe-site/` (3 file),
  `tests/live-reports/f7-probes/f7b-lang-probe.json`,
  `tests/live-reports/f7-probes/f7b-worker-probe.json`,
  `tests/live-reports/f7-probes/f7b-worker-probe-injector.log`,
  `tests/live-reports/detector-2026-11-08-rerun3/` (4 file).

## Catatan jujur / sisa

- WebGL + Canvas 2d masih bold-fail (sama seperti rerun2, artefak
  SwiftShader) — di luar scope F7B, sudah dinyatakan tak-fixable di F7
  tanpa GPU fisik.
- Audio digit bold-fail identik dengan kontrol Chromium polos (artefak
  environment, bukan leak spoof) — sama seperti temuan F7.
- `--lang` sebagai flag Chrome terbukti TIDAK berpengaruh pada Intl di
  setup ini; yang berpengaruh adalah env `LANG`/`LC_ALL`.
- CodeGraph: `status` OK, `sync` dijalankan (27 referensi resolved),
  `explore spoof_js_worker` + `build_launch_args`, `impact launch_profile`
  dibaca sebelum edit. `explore _wrapIntl` hasilnya noisy (cocok ke
  banyak simbol `wrapper`) — sumber yang dipakai adalah pembacaan langsung
  file (R50).
