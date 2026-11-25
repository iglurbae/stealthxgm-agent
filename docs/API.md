# 🔌 Local API — StealthXGM

Kontrol browser dari cmd / termux / script. Kompatibel **AdsPower Local API**,
jadi script AdsPower yang sudah ada tetap jalan.

Base URL default: `http://127.0.0.1:50325`

## Setting dari GUI

Buka GUI → tombol **🔌 API**:
- **Start / Stop** API kapan aja
- **Port** — default 50325, bisa diganti (1024–65535)
- **API Key** — opsional. Kalau diisi, semua request (kecuali `/status`)
  wajib kirim header `X-API-Key: KEY` atau param `?api_key=KEY`
- **Auto-start** — API ikut nyala bareng GUI (default ON)
- Contoh curl + CLI otomatis ngikutin port yang di-setting

Setting tersimpan di `gui/data/api_config.json` (chmod 600).

## Endpoint (AdsPower-compatible)

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/api/v1/status` | status API (tanpa auth) |
| GET | `/api/v1/browser/start?user_id=ID` | launch browser profil |
| GET | `/api/v1/browser/stop?user_id=ID` | stop browser profil |
| GET | `/api/v1/browser/active?user_id=ID` | cek browser jalan / tidak |
| POST | `/api/v1/user/create` | bikin profil `{"name":"x","group":"y"}` |
| POST | `/api/v1/user/update` | update profil `{"user_id":"ID",...}` |
| GET | `/api/v1/user/list?page_size=100` | list profil |
| POST | `/api/v1/user/delete` | hapus → Trash `{"user_id":"ID"}` |

## Ekstensi kita (AdsPower nggak punya)

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/api/v1/features` | daftar 47 teknik fingerprint |
| GET | `/api/v1/user/ID/preview` | preview fingerprint tanpa launch |
| POST | `/api/profiles/<id>/sync-geo` | auto-set timezone+locale dari negara IP pool |
| GET | `/api/profiles/<id>/geo-check` | cek mismatch timezone vs negara IP pool |

### Geo-sync (RND 2026-11-04)

Sinkronkan timezone/locale profil dengan negara IP proxy-nya.
Mencegah mismatch "IP Singapore tapi timezone Jakarta" yang mudah dideteksi.

```bash
G=http://127.0.0.1:5200  # GUI port

# Cek apakah ada mismatch
curl -s $G/api/profiles/<id>/geo-check | python3 -m json.tool
# {"ok": false, "warning": {"message": "Timezone profil (Asia/Jakarta) tidak match..."}}

# Auto-sync timezone+locale dari pool (syarat: pool sudah di-test)
curl -s -X POST $G/api/profiles/<id>/sync-geo | python3 -m json.tool
# {"ok": true, "timezone": "Asia/Singapore", "locale": "en-SG", "country_code": "sg"}
```

### Behavioral helpers (RND 2026-11-04)

Human-like interaction untuk automation — mouse bezier + jitter,
typing rhythm + typo occasional, scroll momentum. Via `launcher`:

```python
from launcher import human_move, human_type, human_scroll, human_click
# human_move(page, x1, y1, x2, y2)  — gerak mouse natural (bezier + jitter)
# human_click(page, x, y)           — move + klik dengan delay manusiawi
# human_type(page, "teks")          — ketik dengan rhythm + typo 2%
# human_scroll(page, delta_y)       — scroll dengan momentum
```

### TLS/Version consistency (RND 2026-11-04)

Fingerprint otomatis sinkronkan `chrome_ver` dengan versi Chromium binary
yang aktual dipakai (`--version`). Mencegah mismatch klaim "155.0.0.0"
padahal binary jalan 156.x. Otomatis di `build_fingerprint_js()` —
tidak perlu setting manual.

## Contoh curl

```bash
P=http://127.0.0.1:50325
KEY=""  # isi kalau API key aktif: KEY="SECRET"

# Status
curl -s $P/api/v1/status ${KEY:+-H "X-API-Key: $KEY"}

# List
curl -s "$P/api/v1/user/list?page_size=100" ${KEY:+-H "X-API-Key: $KEY"} | python3 -m json.tool

# Bikin profil → ambil ID
ID=$(curl -s -X POST $P/api/v1/user/create ${KEY:+-H "X-API-Key: $KEY"} \
  -H "Content-Type: application/json" \
  -d '{"name":"tokped1","group":"bugbounty"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['user_id'])")
echo "ID: $ID"

# Launch
curl -s "$P/api/v1/browser/start?user_id=$ID" ${KEY:+-H "X-API-Key: $KEY"}

# Stop
curl -s "$P/api/v1/browser/stop?user_id=$ID" ${KEY:+-H "X-API-Key: $KEY"}

# Hapus (ke Trash)
curl -s -X POST $P/api/v1/user/delete ${KEY:+-H "X-API-Key: $KEY"} \
  -H "Content-Type: application/json" -d "{\"user_id\":\"$ID\"}"
```

## CLI helper (`antibrowser-cli.py`)

Stdlib saja — jalan di termux / cmd tanpa install apa-apa.
Otomatis baca port + key dari `gui/data/api_config.json`.

```bash
cd ~/workspace/antibrowser   # sesuaikan path

python3 antibrowser-cli.py list
python3 antibrowser-cli.py create --name "tokped1" --group "bugbounty"
python3 antibrowser-cli.py launch <ID>
python3 antibrowser-cli.py stop <ID>
python3 antibrowser-cli.py delete <ID>
python3 antibrowser-cli.py status
python3 antibrowser-cli.py api-start
python3 antibrowser-cli.py api-stop

# override manual
python3 antibrowser-cli.py --port 50325 --key SECRET list
python3 antibrowser-cli.py --json list   # output JSON mentah
```

## Script termux: bikin N akun sekaligus

```bash
#!/data/data/com.termux/files/usr/bin/bash
# bikin-akun.sh — bikin N profil + launch satu-satu
CLI="python3 $HOME/antibrowser/antibrowser-cli.py"
N=${1:-5}
for i in $(seq 1 $N); do
  ID=$($CLI create --name "akun$i" --group "mass" --json | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['user_id'])")
  echo "[$i/$N] $ID"
  sleep 2
done
```

## Catatan

- `browser/start` membuka browser **di mesin yang jalanin API** (VPS),
  bukan di HP. Termux/HP cuma ngirim perintah.
- API key disimpan server-side; GUI tidak pernah menampilkan ulang key lama
  (cuma badge "tersimpan"). Generate key baru kalau lupa.
- Kalau port diganti saat API jalan, GUI otomatis restart API.
