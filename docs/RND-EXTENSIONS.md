# RND: Extension Management untuk StealthXGM

Tanggal: 2026-11-04

## 1. Bagaimana Chromium load extension per profil?

Chromium menerima flag CLI:

```
--load-extension=/path/ext-a,/path/ext-b      # unpacked dirs, comma-separated
--disable-extensions-except=/path/ext-a,/path/ext-b
```

- `--load-extension` memuat extension unpacked (developer mode) tanpa interaksi UI.
- `--disable-extensions-except` membatasi HANYA extension yang terdaftar — wajib
  digabung (comma-separated) bila ada lebih dari satu.
- Alternatif: install ke `<user-data-dir>/Extensions/` + state di `Secure Preferences`,
  TAPI file itu punya checksum proteksi — edit manual bikin Chrome reset. **Ditolak.**
- Keputusan: kelola daftar extension per profil di DB kita sendiri, pass ke
  `--load-extension` saat launch. Enable/disable = masuk/keluar dari daftar.

## 2. Install .crx

Format CRX = header + ZIP:
- CRX3: magic `Cr24`, version=3 (u32 LE), header_len (u32 LE) → zip mulai di offset `12 + header_len`
- CRX2: magic `Cr24`, version=2 (u32 LE), key_len (u32 LE), sig_len (u32 LE) → zip mulai di offset `16 + key_len + sig_len`

Alur: parse header → potong → unzip ke `extensions/<id>/` → baca `manifest.json`
(nama, version, description). Signature tidak pernah diverifikasi untuk unpacked load,
jadi CRX self-signed/test tetap bisa dipasang.

## 3. Chrome Web Store

Download programmatic tanpa login untuk extension publik:

```
https://clients2.google.com/service/update2/crx?response=redirect
  &prodversion=131.0.0.0
  &x=id%3D<32-char-ext-id>%26installsource%3Dondemand%26uc
```

→ 302 redirect ke file .crx → perlakukan seperti .crx biasa.
ID extension = 32 char lowercase dari URL CWS
(`chromewebstore.google.com/detail/<slug>/<32-char-id>`).

**Batasan lingkungan:** di VM ini request tersebut return **403 Forbidden**
(egress proxy). Fitur tetap diimplementasikan — jalan di network normal.

## 4. Enable/disable per profil

- Enabled → path extension masuk `--load-extension` saat launch.
- Disabled → tidak masuk daftar (tidak dimuat sama sekali).
- Tidak perlu sentuh Chrome UI / Preferences.

## 5. Batasan headless

Dari RND sebelumnya: MV3 content script TIDAK jalan di `--headless=new`.
Background service worker TETAP dimuat. Extension user paling berguna di mode
headful (Xvfb) — didokumentasikan di EXTENSIONS.md.

## 6. Keamanan

- Extension hanya dari sumber yang user pilih (upload .crx/.zip, folder, CWS URL).
- File DB `extensions.json` chmod 600 (konsisten dengan proxy_pools.json).
- Validasi: `manifest.json` wajib ada; nama/version dibaca dari manifest.
