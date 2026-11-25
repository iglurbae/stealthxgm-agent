# StealthXGM — GUI Profile Manager

**Tanggal:** 2026-11-04
**Status:** ✅ MVP selesai, semua test PASS

## Cara Jalan

```bash
cd ~/workspace/tools/bugbounty-hunt/stealth_browser/gui

# Keduanya (GUI + API)
python3 gui_launcher.py

# GUI saja (port 5200)
python3 gui_launcher.py --gui-only

# API saja (port 50325, AdsPower-compatible)
python3 gui_launcher.py --api-only
```

- **GUI:** http://127.0.0.1:5200 (mobile-friendly, buka dari HP)
- **Local API:** http://127.0.0.1:50325 (AdsPower-compatible)

## Fitur MVP

| Fitur | Status |
|---|---|
| Profile CRUD (buat/edit/hapus/duplicate) | ✅ |
| Fingerprint picker (29 teknik, toggle per kategori) | ✅ |
| Fingerprint preview (generate JS tanpa launch browser) | ✅ |
| Proxy assign per profil (sticky/warp/http/socks5/none) | ✅ |
| Launch/Stop 1-klik | ✅ (status tracking; real CDP launch v1.1) |
| Group/Tag/Search | ✅ |
| Local REST API (AdsPower-compatible) | ✅ |
| Cookie import/export (JSON) | ✅ |
| CAPTCHA solver toggle per profil | ✅ (unggulan kita) |
| WARP fallback toggle per profil | ✅ (unggulan kita) |

## API Endpoints

### GUI Backend (port 5200)
| Method | Endpoint | Deskripsi |
|---|---|---|
| GET | `/api/profiles` | List (query: search, group) |
| POST | `/api/profiles` | Buat baru |
| GET | `/api/profiles/<id>` | Detail |
| PUT | `/api/profiles/<id>` | Update |
| DELETE | `/api/profiles/<id>` | Hapus |
| POST | `/api/profiles/<id>/duplicate` | Duplikat |
| GET | `/api/groups` | List grup |
| GET | `/api/flags` | 29 feature flags per kategori |
| GET | `/api/profiles/<id>/preview` | Preview fingerprint JS |
| GET/POST | `/api/profiles/<id>/cookies` | Cookie import/export |
| POST | `/api/profiles/<id>/launch` | Launch |
| POST | `/api/profiles/<id>/stop` | Stop |

### Local REST API (port 50325, AdsPower-compatible)
| Method | Endpoint | Deskripsi |
|---|---|---|
| GET | `/api/v1/status` | Status server |
| GET | `/api/v1/browser/start?user_id=X` | Buka browser |
| GET | `/api/v1/browser/stop?user_id=X` | Tutup browser |
| GET | `/api/v1/browser/active?user_id=X` | Cek status |
| POST | `/api/v1/user/create` | Buat profil |
| POST | `/api/v1/user/update` | Update profil |
| GET | `/api/v1/user/list` | List profil |
| POST | `/api/v1/user/delete` | Hapus profil |
| GET | `/api/v1/features` | **(kita saja)** 29 teknik |
| GET | `/api/v1/user/<id>/preview` | **(kita saja)** Preview fingerprint |

## Struktur File

```
gui/
  __init__.py        — package (lazy Flask import)
  profiles.py        — profile CRUD + 29 feature flags (no Flask dep)
  app.py             — Flask GUI (port 5200)
  local_api.py       — Flask REST API (port 50325)
  gui_launcher.py    — launcher keduanya
  templates/index.html — mobile-friendly GUI
  data/profiles.json — storage (auto-created)
```

## Test Results

**Profile manager:** 7/7 PASS (create/get/update/duplicate/list/groups/delete)
**GUI API:** 11/11 PASS (flags/groups/CRUD/preview/cookies/launch/stop/HTML)
**Local API:** 9/9 PASS (status/user CRUD/browser start/active/stop/features/preview)

**Total: 27/27 PASS**

## Keunggulan vs AdsPower

| | AdsPower | Kita |
|---|---|---|
| Harga | $0 (2 profil) – $61+/bln | $0 unlimited selamanya |
| CAPTCHA solver | ❌ | ✅ per-profil toggle |
| WARP fallback | ❌ | ✅ per-profil toggle |
| Fingerprint preview | ❌ | ✅ tanpa launch |
| RAM | Boros (Electron) | Ringan (Flask) |
| Keamanan | Breach $4.7M (2025) | 100% lokal |

## Roadmap v1.1

- [ ] Real browser launch via patchright (CDP WebSocket URL)
- [ ] Cookie auto-save saat browser ditutup
- [ ] Batch import profil dari CSV
- [ ] Proxy test button (cek IP/lokasi)
