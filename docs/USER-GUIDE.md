# 📖 User Guide — StealthXGM

Panduan lengkap buat pemula. Bahasa santai, langkah demi langkah.

## Apa itu StealthXGM?

Browser kayak AdsPower tapi gratis & unlimited: tiap profil punya **identitas beda** (fingerprint), **IP beda** (proxy), dan **data terpisah** (cookies, history). Cocok buat manage banyak akun tanpa ketahuan "ini orang yang sama".

---

## 1. Cara Install & Jalanin

### Syarat

- Python 3.10+
- Chromium (otomatis ke-install via playwright pas pertama launch)

### Jalanin

```bash
cd ~/workspace/antibrowser/gui

# GUI + Local API (disarankan)
python3 gui_launcher.py
```

Terus buka di browser/HP:

- **GUI:** http://127.0.0.1:5200
- **Local API:** http://127.0.0.1:50325

> GUI mobile-friendly, jadi bisa dibuka dari HP di jaringan yang sama.

Opsi lain:

```bash
python3 gui_launcher.py --gui-only   # cuma GUI (port 5200)
python3 gui_launcher.py --api-only   # cuma API (port 50325)
```

---

## 2. Bikin Profil Pertama

1. Buka GUI → klik **➕ Profil Baru**.
2. Isi:
   - **Nama** — misal `tokped1` (wajib, nggak boleh kembar)
   - **Grup** — misal `bugbounty` (opsional, buat ngelompokin)
   - **Proxy Pool** — pilih pool (default: DataImpulse). Lihat [PROXY-POOLS-GUIDE.md](PROXY-POOLS-GUIDE.md).
   - **Catatan** — bebas, misal "akun test Tokopedia".
3. Klik **Simpan**. Profil langsung dapat fingerprint otomatis yang konsisten.

### Duplicate profil

Klik ikon **📋** di kartu profil → jadi profil baru dengan setting sama (fingerprint di-generate ulang biar beda, cookies dikosongkan — dua profil tidak pernah berbagi identitas atau sesi login).

---

## 3. Fingerprint Generator 🎲

Klik tombol **🎲 Fingerprint** di toolbar. Ada 2 mode:

### Mode Random (disarankan)

1. Pilih OS: **Windows / macOS / Linux / Android / iOS**.
2. Klik **Generate**.
3. Identitas yang keluar **dijamin ngotak** (konsisten):
   - Windows → GPU NVIDIA/AMD/Intel, platform Win32
   - macOS → GPU Apple, platform MacIntel, layar Retina
   - Android → chipset Snapdragon → GPU Adreno (otomatis mapping)
4. Klik **🧪 Test di browser** buat lihat hasilnya di browserleaks.com.
5. Klik **💾 Simpan ke profil** kalau cocok.

### Mode Manual

Atur sendiri: versi Chrome, GPU, layar, CPU, RAM, timezone, bahasa. Ada **validasi live** — kalau kombinasinya nggak masuk akal (misal MacIntel + GPU NVIDIA), muncul warning.

Detail 29 teknik: [FINGERPRINT-FLAGS.md](FINGERPRINT-FLAGS.md).

---

## 4. Setting Proxy

Tiap profil **wajib** punya proxy biar IP-nya beda. Baca panduan lengkap: [PROXY-POOLS-GUIDE.md](PROXY-POOLS-GUIDE.md).

Versi singkat:

1. Klik **🌐 Pools** di toolbar.
2. Pool bawaan yang langsung bisa dipakai:
   - **DataImpulse (proxy-bot)** — IP residential, ganti-ganti tapi sticky per profil. Default.
   - **Cloudflare WARP** — gratis, cadangan kalau proxy-bot mati.
   - **Direct** — tanpa proxy (jangan dipakai buat akun penting).
3. Klik **Test** di tiap pool buat cek: IP, negara, kecepatan.
4. Di editor profil, pilih pool dari dropdown.

**Aturan emas:** 1 profil = 1 proxy = 1 fingerprint. Jangan pakai 1 proxy buat 100 akun.

---

## 5. Launch Browser

1. Di kartu profil, klik **▶ Launch**.
2. Browser Chromium kebuka dengan:
   - Fingerprint profil ter-inject (situs nggak bisa deteksi ini bot)
   - Proxy profil terpasang
   - Data terpisah (`--user-data-dir` sendiri per profil)
3. Judul window: `[Nama Profil]` biar nggak ketuker.
4. Selesai → klik **⏹ Stop**.

### Cek fingerprint beneran jalan

Buka https://browserleaks.com/javascript di browser profil → pastikan:

- `navigator.webdriver` = **false**
- User Agent & platform sesuai identitas profil

---

## 6. Fitur Lain

| Fitur | Cara pakai |
|---|---|
| **Batch import** | Tombol **📥 Batch** → upload CSV/JSON → preview → import. Template bisa di-download dari modal. |
| **Extensions** | **🧩 Extensions** → upload `.crx`/`.zip` atau paste URL Web Store → centang di editor profil. |
| **Trash bin** | Hapus profil → masuk 🗑 Trash (bisa di-restore). Kosongkan trash buat hapus permanen. |
| **Batch ops** | Centang beberapa profil → hapus/pindah grup/ganti pool sekaligus. |
| **Cookies** | API simpan/ambil cookies; otomatis di-inject pas launch. |
| **Local API** | Tombol **🔌 API** → setting port/key → kontrol dari cmd/termux. Lihat [CLI-REFERENCE.md](CLI-REFERENCE.md). |

---

## FAQ

**Q: Bedanya sama Chrome biasa?**
A: Chrome biasa = 1 identitas. StealthXGM = tiap profil identitas beda (fingerprint + IP + data terpisah), jadi situs nggak bisa ngelink akun-akunmu.

**Q: Aman buat bikin banyak akun?**
A: Fingerprint kita solid (500/500 test konsisten), tapi keamanan juga tergantung **perilaku**: kasih jeda waktu antar pendaftaran, jangan pola klik yang sama persis, 1 proxy per akun.

**Q: WebRTC bocor IP asli?**
A: Default `fp_webrtc_block` ON — WebRTC di-block biar IP asli nggak bocor.

**Q: Profil kehapus nggak sengaja?**
A: Masuk Trash dulu, bisa di-restore. Baru hilang permanen kalau trash dikosongkan.

**Q: Bisa dipakai bareng script?**
A: Bisa, via Local API (port 50325) atau CLI. Lihat [API.md](API.md) dan [CLI-REFERENCE.md](CLI-REFERENCE.md).

**Q: Data profil disimpan di mana?**
A: `gui/data/` (profil, pool, extension — chmod 600) dan `browser_profiles/<id>/` (data Chromium per profil).

**Q: iOS beneran jalan?**
A: Identitas iOS konsisten (UA iPhone, Apple GPU), tapi engine tetap Chromium/Blink — spoof level JS, bukan engine WebKit asli.
