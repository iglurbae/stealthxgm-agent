# 💻 CLI Reference — antibrowser-cli.py

Kontrol StealthXGM dari **cmd / termux** tanpa buka GUI. Murni Python stdlib — nggak perlu install apa-apa.

File: `~/workspace/antibrowser/antibrowser-cli.py`

> CLI ngomong ke **Local API** (default port 50325). Pastikan API jalan — bisa dinyalakan dari GUI (tombol 🔌 API) atau via `api-start`.

---

## Global options

```
python3 antibrowser-cli.py [--port PORT] [--key KEY] [--gui GUI] [--json] <command>
```

| Option | Fungsi |
|---|---|
| `--port PORT` | Port Local API (default 50325, ngikutin config kalau nggak diisi) |
| `--key KEY` | API key (kalau API pakai key) |
| `--gui GUI` | Base URL GUI (default http://127.0.0.1:5200) |
| `--json` | Output mentah JSON (buat script) |

---

## Commands

### `status` — cek API jalan / tidak

```bash
python3 antibrowser-cli.py status
```

### `list` — list profil

```bash
python3 antibrowser-cli.py list
python3 antibrowser-cli.py list --json   # buat di-parse script
```

### `create` — bikin profil

```bash
python3 antibrowser-cli.py create --name tokped1
python3 antibrowser-cli.py create --name tokped2 --group bugbounty
```

Output: ID profil baru (dipakai buat launch/stop/delete).

### `launch` — buka browser profil

```bash
python3 antibrowser-cli.py launch <ID>
```

Browser Chromium kebuka dengan fingerprint + proxy profil itu.

### `stop` — tutup browser profil

```bash
python3 antibrowser-cli.py stop <ID>
```

### `delete` — hapus profil (masuk Trash, bisa di-restore)

```bash
python3 antibrowser-cli.py delete <ID>
```

### `api-start` / `api-stop` — nyalain/matiin Local API

```bash
python3 antibrowser-cli.py api-start
python3 antibrowser-cli.py api-stop
```

---

## Contoh termux: bikin 10 akun sekaligus

```bash
cd ~/workspace/antibrowser

# 1. Pastikan API jalan
python3 antibrowser-cli.py api-start
python3 antibrowser-cli.py status

# 2. Bikin 10 profil, kasih jeda 5 detik biar nggak barengan
for i in $(seq 1 10); do
  ID=$(python3 antibrowser-cli.py create --name "akun$i" --group "batch1" --json \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['user_id'])")
  echo "bikin akun$i -> $ID"
  sleep 5
done

# 3. Lihat hasilnya
python3 antibrowser-cli.py list
```

> **Best practice:** kasih jeda antar pembuatan akun (jangan 100 akun dalam 1 menit), dan pastikan tiap profil dapat proxy beda (default sticky pool sudah 1:1).

---

## Contoh: launch → kerja → stop (1 profil)

```bash
ID=$(python3 antibrowser-cli.py create --name "kerja1" --json \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['user_id'])")

python3 antibrowser-cli.py launch $ID
# ... kerja manual di browser yang kebuka ...
python3 antibrowser-cli.py stop $ID
```

---

## Kalau API pakai key

```bash
# Semua command tinggal tambah --key
python3 antibrowser-cli.py --key "SECRETKAMU" list
```

Key di-setting dari GUI → 🔌 API → API Key (atau generate otomatis).

---

## Troubleshooting

| Masalah | Solusi |
|---|---|
| `connection refused` | API belum jalan → `api-start` dulu, atau cek port di GUI |
| `401 unauthorized` | API pakai key → tambah `--key` |
| Command nggak dikenal | `python3 antibrowser-cli.py --help` |
