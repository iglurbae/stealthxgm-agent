# StealthXGM Agent

Browser anti-detect **headless untuk AI agent** — jalan di VPS Linux tanpa
GPU, tanpa GUI. Dikendalikan lewat **Local API** (kompatibel AdsPower) +
**CDP (Chrome DevTools Protocol)**. Setiap profil punya fingerprint sendiri
yang konsisten: WebGL, canvas, audio, navigator, layar, timezone, locale,
dan geo mengikuti proxy-nya.

> Ini versi **agent** (headless/API). Versi desktop (GUI) ada di repo
> terpisah dan tidak dibutuhkan untuk otomasi.

---

## Daftar isi

1. [Arsitektur](#arsitektur)
2. [Install cepat](#install-cepat)
3. [Install manual](#install-manual)
4. [Konsep inti](#konsep-inti)
5. [Local API](#local-api)
6. [Mengendalikan browser via CDP](#mengendalikan-browser-via-cdp)
7. [Fingerprint engine](#fingerprint-engine)
8. [Proxy](#proxy)
9. [Contoh lengkap (Python)](#contoh-lengkap-python)
10. [Operasional](#operasional)
11. [Troubleshooting](#troubleshooting)
12. [Struktur repo](#struktur-repo)

---

## Arsitektur

```
Agent / script kamu
        │  HTTP (Local API :50325)          WebSocket (CDP)
        ▼                                        ▼
┌──────────────────┐   start/stop    ┌────────────────────────┐
│  gui/local_api.py │ ──────────────► │ Chromium 152 (kernel)  │
│  (Flask)          │                 │  di Xvfb :99 (headless)│
└────────┬─────────┘                 └───────────┬────────────┘
         │ profil + fingerprint                  │ halaman web
         ▼                                       ▼
┌──────────────────┐                 ┌────────────────────────┐
│ gui/data/        │                 │ fingerprint/ (injeksi) │
│ profiles.json    │                 │ WebGL · canvas · audio │
│ browser_profiles/│                 │ navigator · screen ·   │
└──────────────────┘                 │ geo/tz/locale · WebRTC │
                                     └────────────────────────┘
```

- **Kernel**: Chromium 152.0.7977.82 (Chrome for Testing). Dipilih karena
  fingerprint audio-nya bersih; kernel lain bisa ditambah lewat registry.
- **Display**: Xvfb `:99` (layar virtual 1280×800). Tidak butuh GPU fisik —
  WebGL dirender software (SwiftShader) lalu **di-spoof** ke renderer yang
  wajar per profil.
- **API key**: dibuat otomatis saat API pertama jalan, disimpan di
  `gui/data/api_config.json` (chmod 600). Semua endpoint kecuali
  `/api/v1/status` wajib header `X-API-Key` bila key terkonfigurasi.

## Install cepat

Di VPS Ubuntu 20.04/22.04 (root):

```bash
git clone https://github.com/iglurbae/stealthxgm-agent.git
cd stealthxgm-agent
sudo bash install.sh            # default target: /root/stealthxgm
# atau: sudo bash install.sh /opt/stealthxgm
```

Installer akan: install paket sistem (Python 3.9, Xvfb, library Chromium),
salin kode, install dependensi Python, unduh kernel Chromium 152, tulis
registry kernel, buat + enable systemd units (`xvfb`, `stealthxgm-api`),
start keduanya, lalu verifikasi `GET /api/v1/status`.

## Install manual

1. Paket sistem:
   ```bash
   apt-get install -y python3.9 python3.9-venv python3-pip xvfb unzip curl \
     libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
     libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
     libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 fonts-liberation
   ```
2. Dependensi Python: `python3.9 -m pip install -r requirements.txt`
   (Flask, playwright, websocket-client, requests).
3. Kernel: unduh Chrome for Testing 152.0.7977.82
   (`https://storage.googleapis.com/chrome-for-testing-public/152.0.7977.82/linux64/chrome-linux64.zip`),
   ekstrak ke `kernels/152.0.7977.82/`, dan tulis `gui/data/kernels.json`
   (format: lihat `install.sh` langkah 4).
4. Jalankan Xvfb + API (atau pakai systemd units dari `install.sh`):
   ```bash
   Xvfb :99 -screen 0 1280x800x24 &
   DISPLAY=:99 python3.9 gui/local_api.py --port 50325
   ```

## Konsep inti

| Istilah | Arti |
|---|---|
| **Profil** (`user_id`) | Satu identitas browser: fingerprint + proxy + cookies + storage, persisten di `browser_profiles/<user_id>/` |
| **Fingerprint** | Kumpulan sinyal perangkat (WebGL, canvas, audio, navigator, layar, font, geo) yang diinjeksikan ke setiap halaman |
| **Kernel** | Binary Chromium yang dipakai semua profil |
| **debug_port** | Port CDP per browser yang sedang jalan — pintu agent mengendalikan halaman |

Aturan main yang terbukti penting:

- **1 profil = 1 identitas = 1 proxy sticky.** Ganti IP di tengah sesi
  membuat banyak situs menolak.
- **Fingerprint harus konsisten dengan proxy**: timezone, locale, dan
  koordinat geo mengikuti kota/negara IP keluar.
- **Jangan pakai ulang fingerprint yang sama** untuk banyak akun — generator
  sudah memvariasikan; cek tabrakan dengan 10 identitas terakhir.

## Local API

Base URL: `http://127.0.0.1:50325`. Kompatibel AdsPower Local API, jadi
script AdsPower yang sudah ada tetap jalan. Referensi lengkap:
[`docs/API.md`](docs/API.md).

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/api/v1/status` | status API (tanpa auth) |
| GET | `/api/v1/browser/start?user_id=ID` | launch browser profil → `data.debug_port` |
| GET | `/api/v1/browser/stop?user_id=ID` | stop browser profil |
| GET | `/api/v1/browser/active?user_id=ID` | cek browser jalan / tidak |
| GET | `/api/v1/browser/fingerprint-check?user_id=ID` | audit fingerprint profil |
| POST | `/api/v1/user/create` | bikin profil `{"name":"x","group":"y"}` |
| POST | `/api/v1/user/update` | update profil `{"user_id":"ID", ...}` (proxy, fingerprint) |
| GET | `/api/v1/user/list?page_size=100` | list profil |
| POST | `/api/v1/user/delete` | hapus profil |
| GET | `/api/v1/user/<id>/preview` | preview fingerprint |
| POST | `/api/v1/user/<id>/cookies` | import cookies |
| GET | `/api/v1/features` | daftar teknik fingerprint |
| POST | `/api/v1/rpa/run` | jalankan flow RPA |
| GET/POST | `/api/v1/rpa/flows` | kelola flow RPA |

Catatan penting:

- Root `/` balas **404 — itu normal**, bukan error.
- `browser/start` dan `browser/stop` pakai **GET** (POST = 405).
- `user/delete` menghapus registry profil, **bukan** folder
  `browser_profiles/<user_id>/` — hapus manual bila ingin bersih total.
- API key (bila aktif) dikirim sebagai header `X-API-Key: <key>`.

## Mengendalikan browser via CDP

Setelah `browser/start`, sambung ke `http://127.0.0.1:<debug_port>/json`
untuk dapat `webSocketDebuggerUrl` halaman, lalu kirim perintah CDP
(`Page.navigate`, `Runtime.evaluate`, `Input.dispatchMouseEvent`, dll).
Tunggu ±12 detik sesudah start sebelum CDP stabil.

Pola yang dipakai di produksi:

- Baca state halaman dengan `Runtime.evaluate` (URL, teks tombol, isi form)
  — **verifikasi halaman cocok dengan langkah** sebelum lanjut; jangan
  percaya klik "OK" begitu saja.
- Klik penting pakai mouse asli (`Input.dispatchMouseEvent`), bukan
  `element.click()` — beberapa gerbang anti-bot membedakan keduanya.
- Screenshot via `Page.captureScreenshot` untuk verifikasi visual.

## Fingerprint engine

Folder `fingerprint/` menginjeksi override **sebelum** script halaman jalan:

- **WebGL**: `getParameter` di-override — `UNMASKED_VENDOR_WEBGL` (37445)
  dan `UNMASKED_RENDERER_WEBGL` (37446) mengembalikan nilai per profil dari
  daftar GPU nyata; parameter lain dari tabel per perangkat. Divalidasi
  konsisten per platform (Windows = Direct3D11, macOS = ANGLE Metal,
  Linux = OpenGL). Halaman tidak pernah melihat WebGL mati walau mesin
  tanpa GPU.
- **Canvas/Audio**: noise deterministik per profil (hash stabil per profil,
  beda antar profil).
- **Navigator**: platform, hardwareConcurrency, deviceMemory, languages.
- **Screen**: resolusi, DPR, viewport, colorDepth.
- **Geo**: timezone + locale + koordinat mengikuti kota proxy
  (`fingerprint/geo.py`).
- **WebRTC**: diblokir/dibatasi agar IP asli tidak bocor lewat ICE.

Detail flag: [`docs/FINGERPRINT-FLAGS.md`](docs/FINGERPRINT-FLAGS.md).

## Proxy

Set per profil lewat `user/update`:

```json
{
  "user_id": "<id>",
  "proxy": {
    "type": "http",
    "host": "127.0.0.1",
    "port": 18085
  }
}
```

Pola produksi: satu relay lokal per slot yang meneruskan ke proxy
residensial sticky — ganti IP cukup ganti sesi di relay, profil tidak
perlu diubah. Panduan pool: [`docs/PROXY-POOLS-GUIDE.md`](docs/PROXY-POOLS-GUIDE.md).

## Contoh lengkap (Python)

```python
import json, time, urllib.request
import websocket

API = "http://127.0.0.1:50325"

def req(url, data=None):
    r = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())

# 1) Bikin profil
uid = req(f"{API}/api/v1/user/create", {"name": "agent-1"})["data"]["id"]

# 2) Set proxy + fingerprint (sesuaikan field dengan docs/API.md)
req(f"{API}/api/v1/user/update", {
    "user_id": uid,
    "proxy": {"type": "http", "host": "127.0.0.1", "port": 18085},
})

# 3) Start browser -> debug_port
port = req(f"{API}/api/v1/browser/start?user_id={uid}")["data"]["debug_port"]
time.sleep(12)

# 4) Sambung CDP, buka halaman, baca WebGL renderer
targets = req(f"http://127.0.0.1:{port}/json")
ws_url = next(t for t in targets if t["type"] == "page")["webSocketDebuggerUrl"]
ws = websocket.create_connection(ws_url, timeout=30)

_id = 0
def cdp(method, params=None):
    global _id
    _id += 1
    ws.send(json.dumps({"id": _id, "method": method, "params": params or {}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == _id:
            return m

cdp("Page.enable")
cdp("Runtime.enable")
cdp("Page.navigate", {"url": "https://example.com"})
time.sleep(5)
r = cdp("Runtime.evaluate", {
    "expression": "(()=>{const c=document.createElement('canvas');"
                  "const g=c.getContext('webgl');"
                  "return g?g.getParameter(g.getExtension('WEBGL_debug_renderer_info')"
                  ".UNMASKED_RENDERER_WEBGL):'TIDAK ADA WEBGL'})()",
    "returnByValue": True,
})
print("Renderer:", r["result"]["result"].get("value"))
ws.close()

# 5) Stop browser
req(f"{API}/api/v1/browser/stop?user_id={uid}")
```

## Operasional

```bash
systemctl status xvfb stealthxgm-api     # status
journalctl -u stealthxgm-api -n 50       # log API
curl -s http://127.0.0.1:50325/api/v1/status
```

- API key: `gui/data/api_config.json` (dibuat otomatis; chmod 600).
- Registry profil: `gui/data/profiles.json`; folder profil:
  `browser_profiles/<user_id>/`. **Backup dua-duanya** untuk memindahkan
  instalasi — sesi login tinggal di folder profil.
- Satu VPS 2 vCPU / 7 GB RAM realistis menjalankan 3–4 browser paralel.

## Troubleshooting

| Gejala | Penyebab umum | Solusi |
|---|---|---|
| API root 404 | normal | pakai `/api/v1/status` |
| `browser/start` gagal | Xvfb mati / kernel tidak ada | cek `systemctl status xvfb`, path di `gui/data/kernels.json` |
| CDP tidak nyambung | browser belum siap | tunggu ±12 dtk sesudah start |
| Halaman lihat WebGL mati | fingerprint tidak terinjeksi | cek `browser/fingerprint-check` |
| IP bocor di WebRTC | WebRTC tidak diblokir di profil | aktifkan blokir WebRTC di fingerprint profil |
| Situs menolak di tengah flow | IP berubah di tengah sesi | pakai proxy sticky, 1 profil = 1 IP |

## Struktur repo

```
fingerprint/   engine fingerprint (WebGL, canvas, audio, geo, navigator)
launcher/      launcher kernel + registry kernel
gui/           Local API (local_api.py), manajemen profil, RPA
network/       util jaringan
vendor/        fingerprint mobile
captcha/       helper captcha
docs/          API.md, CLI-REFERENCE.md, FINGERPRINT-FLAGS.md, dll
install.sh     installer VPS (Ubuntu headless)
requirements.txt
```

Data runtime (profil, sesi, API key, kernel binary) **tidak** ikut repo —
lihat `.gitignore`. Installer mengunduh kernel saat install.

---

Dokumentasi lanjutan: [`docs/API.md`](docs/API.md) ·
[`docs/CLI-REFERENCE.md`](docs/CLI-REFERENCE.md) ·
[`docs/USER-GUIDE.md`](docs/USER-GUIDE.md) ·
[`docs/PROXY-POOLS-GUIDE.md`](docs/PROXY-POOLS-GUIDE.md)
