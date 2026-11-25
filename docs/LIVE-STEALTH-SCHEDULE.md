# Jadwal Uji Stealth Live — V-01–V-04 (P-16)

Definisi V-01–V-04 dari `AUDIT-STEALTHXGM-2026-11-06.md` baris 279–282.
Sebagian bisa otomatis (lokal), sebagian HANYA manual — Chromium di VM ini
tidak bisa navigasi ke situs eksternal (blokir lingkungan sandbox, lihat
temuan P-09) dan tidak ada perangkat mobile nyata di sini.

## Bagian otomatis (lokal, bisa cron)

**Skrip:** `python3 tests/live_stealth_check.py`
**Laporan:** `tests/live-reports/live-stealth-<timestamp>.json`
**Isi:** V-01 lokal (fingerprint-check live 12 field + canvas hash stabil +
vendor/languages/plugins/chrome.runtime/UA) dan V-02
(`navigator.webdriver` false, tanpa own property, getter prototype bernama
native). Catatan: `'webdriver' in navigator` = True BY DESIGN (getter di
`Navigator.prototype`, H3) — dilaporkan INFO, bukan gagal.

**Jadwal yang diusulkan (BELUM dipasang sebagai cron — butuh kata Gil):**

```cron
# Senin 09:00 WIB — live stealth check lokal
0 9 * * 1  cd /home/hatch/workspace/antibrowser && python3 tests/live_stealth_check.py >> tests/live-reports/cron.log 2>&1
```

Selain mingguan, jalankan juga: (1) setiap kali kode fingerprint
(`fingerprint/`, `launcher/injector_daemon.py`, `launcher/launcher.py`
bagian spoof) berubah; (2) sebelum tiap rilis `.deb`.

**Ambang lolos:** semua vektor keras PASS (exit 0). Satu vektor FAIL =
laporan dibaca, field yang bocor dicatat, fix diprioritaskan sebelum rilis.

## Bagian manual (tidak bisa cron — butuh browser task / perangkat nyata)

| Uji | Pertanyaan audit | Prosedur | Kapan | Lolos bila |
| --- | --- | --- | --- | --- |
| V-01 eksternal | Apakah detector nyata (CreepJS, browserleaks, amiunique) mendeteksi StealthXGM? | Browser task: launch 1 profil, buka creepjs.com + browserleaks.com + amiunique.org, catat skor + field yang bocor | Tiap rilis + bulanan | Tidak ada field kritis bocor (skor CreepJS tidak merah di UA/webdriver/canvas/WebGL) |
| V-02 (CreepJS) | Apakah `webdriver` di prototype terdeteksi? | Di CreepJS yang sama: cek `'webdriver' in navigator` + descriptor `Navigator.prototype.webdriver` | Bersama V-01 eksternal | CreepJS tidak menandai webdriver sebagai bot |
| V-03 | Apakah iframe patch (M-10) merusak reCAPTCHA/hCaptcha/iframe payment? | Buka halaman uji reCAPTCHA + iframe payment, flag `fp_iframe_patch` ON vs OFF, bandingkan fungsi | Tiap kali `fp_iframe_patch` berubah + tiap rilis | CAPTCHA tampil & bisa diselesaikan manual; iframe payment muat normal |
| V-04 | Apakah string renderer GPU mobile cocok perangkat nyata? | Bandingkan `UNMASKED_RENDERER_WEBGL` hasil spoof (profil mobile) dengan perangkat Android/iOS nyata (HP Gil) | Tiap kali data GPU mobile di `fingerprint_gen.py` berubah | String renderer sesuai format + model perangkat nyata |

## Yang sudah terbukti (2026-11-07, laporan di `tests/live-reports/`)

- 2026-11-07 12:06 WIB: 11/11 vektor lokal lolos (10 PASS + 1 INFO),
  fingerprint-check live 12/12 field cocok, canvas hash stabil.
- Batasan jujur: skor CreepJS/browserleaks BELUM pernah diukur (butuh
  browser task + internet) — jangan klaim "lolos CreepJS" sebelum V-01
  eksternal dijalankan.
