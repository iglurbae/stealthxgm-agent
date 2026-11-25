# Extension Manager — StealthXGM

Install & kelola extension Chromium per profil, kayak AdsPower.

## Cara pakai (GUI)

1. Klik **🧩 Extensions** di toolbar.
2. Tambah extension ke library:
   - **Upload** file `.crx` atau `.zip` (berisi extension unpacked)
   - **Dari Web Store**: paste URL Chrome Web Store atau 32-char extension ID
3. Buka editor profil → section **🧩 Extensions** → centang extension yang mau
   dipasang, atur ON/OFF per extension.
4. Launch profil — extension ikut ke-load.

## Sumber yang didukung

| Sumber | Keterangan |
|---|---|
| `.crx` file | Header CRX2/CRX3 di-parse, isi di-extract otomatis |
| `.zip` file | Harus berisi `manifest.json` (top-level atau 1 subfolder) |
| Chrome Web Store | Download otomatis dari URL/ID publik, tanpa login |
| Folder unpacked | Via API/backend (parameter `unpacked_path` belum ada di GUI) |

**Catatan:** download Web Store butuh koneksi langsung ke Google. Di network yang
memblokir (mis. proxy tertentu) bisa gagal dengan pesan error yang jelas.

## Enable / Disable

- **ON** → extension dimuat saat profil di-launch.
- **OFF** → tidak dimuat (tapi tetap ter-assign, tinggal nyalakan lagi).
- Uncentang → assignment dihapus dari profil.

Teknis: daftar extension per profil disimpan di `gui/data/profile_extensions.json`,
di-pass ke Chromium sebagai `--load-extension=a,b,c` +
`--disable-extensions-except=a,b,c` saat launch. Tidak menyentuh
`Secure Preferences` Chrome (fragile).

## Batasan

- Extension unpacked jalan dalam "developer mode" — normal untuk StealthXGM.
- **Mode headless**: MV3 content script tidak jalan di `--headless=new`
  (background service worker tetap dimuat). Untuk extension yang butuh content
  script, launch headful (otomatis pakai Xvfb di server tanpa display).
- Hapus extension dari library → assignment di semua profil ikut terhapus.

## API

```
GET    /api/extensions                        # library
POST   /api/extensions                        # multipart file= | json {cws_url}
GET    /api/extensions/<eid>
DELETE /api/extensions/<eid>
GET    /api/profiles/<pid>/extensions         # assignment + info
POST   /api/profiles/<pid>/extensions         # {ext_id, enabled?}
PUT    /api/profiles/<pid>/extensions/<eid>   # {enabled}
DELETE /api/profiles/<pid>/extensions/<eid>
```

## File

- `gui/extension_manager.py` — backend (library + assignment + CRX/CWS logic)
- `extensions/<ext_id>/` — unpacked extension per library entry
- `gui/data/extensions.json` — metadata library (chmod 600)
- `gui/data/profile_extensions.json` — assignment per profil (chmod 600)
- `docs/RND-EXTENSIONS.md` — hasil RND
