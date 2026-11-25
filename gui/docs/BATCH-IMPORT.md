# Batch Import — Format File

Import banyak profil sekaligus dari CSV atau JSON.

## Cara pakai (GUI)
1. Klik **📥 Batch** di toolbar
2. Download template (link Template CSV / Template JSON di modal)
3. Isi file, upload, klik **👁 Preview** untuk validasi
4. Klik **⬇ Import Sekarang**

## Format CSV

Header wajib (case-insensitive), kolom pertama harus `name`:

```
name,group,pool,platform,timezone,notes,warp_fallback,mobile
```

| Kolom | Wajib | Keterangan |
|---|---|---|
| `name` | YA | Nama profil, harus unik (duplikat ditolak) |
| `group` | - | Grup organisasi (default: `default`) |
| `pool` | - | Nama proxy pool persis seperti di 🌐 Pools; kosong = pool default |
| `platform` | - | `windows` \| `macos` \| `linux` \| `android` (default: `windows`) |
| `timezone` | - | cth: `Asia/Jakarta` (default: `Asia/Jakarta`) |
| `notes` | - | Catatan bebas |
| `warp_fallback` | - | `true`/`false` (default: `true`) |
| `mobile` | - | `true`/`false` (default: `false`) |

Contoh:
```csv
name,group,pool,platform,timezone,notes,warp_fallback,mobile
Tokopedia Akun 1,marketplace,DataImpulse (proxy-bot),windows,Asia/Jakarta,akun utama,true,true,false
Shopee Akun 2,marketplace,,android,Asia/Jakarta,,true,true,true
```

## Format JSON

Array of objects — shape sama dengan `POST /api/profiles`, plus shortcut `pool` (nama pool):

```json
[
  {
    "name": "Tokopedia Akun 1",
    "group": "marketplace",
    "pool": "DataImpulse (proxy-bot)",
    "notes": "akun utama",
    "fingerprint": {"platform": "windows", "timezone": "Asia/Jakarta", "mobile": false},
    "warp_fallback": true
  }
]
```

Tanpa field `proxy`/`pool` → dipakai pool default. Field `fingerprint.features`
opsional — default semua 29 teknik ON.

## Validasi

- Nama kosong → ditolak (per baris, dilaporkan)
- Nama duplikat (sudah ada di DB atau duplikat dalam file) → ditolak
- Pool tidak ditemukan → ditolak
- Platform tidak valid → ditolak
- Baris kosong → dilewati diam-diam

Hasil import: `{created: [...], failed: [{line, name, error}], summary: {success, failed}}`

## API

- `POST /api/profiles/import` — multipart `file` atau JSON body `{"content","format"}`; `?preview=1` untuk preview tanpa import
- `GET /api/profiles/template/csv` — download template CSV
- `GET /api/profiles/template/json` — download template JSON
