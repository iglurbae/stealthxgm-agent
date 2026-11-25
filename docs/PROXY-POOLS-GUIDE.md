# 🌐 Panduan Proxy Pools — StealthXGM

## Apa itu Proxy Pool?

Pool = **kumpulan proxy** yang bisa dipilih per profil. Tiap profil ambil 1 proxy dari pool-nya, dan proxy itu **sticky**: profil yang sama selalu dapat IP yang sama setiap dibuka.

Analogi: pool itu kayak parkiran. Tiap mobil (profil) dapat 1 slot parkir (IP) yang tetap — mobil A selalu parkir di slot X, mobil B di slot Y.

---

## Pool Bawaan

| Pool | Tipe | Fungsi |
|---|---|---|
| **DataImpulse (proxy-bot)** ⭐ default | sticky | IP residential, 195 negara. Via proxy-bot lokal `127.0.0.1:18080`. |
| **Cloudflare WARP** | warp | Gratis. Cadangan otomatis kalau proxy utama mati. `127.0.0.1:40000`. |
| **Direct (no proxy)** | none | Tanpa proxy. IP asli kelihatan — jangan buat akun penting. |

---

## Cara Tambah Pool Baru

1. Buka GUI → klik **🌐 Pools**.
2. Klik **➕ Tambah Pool**, isi:
   - **Nama** — misal `Proxy US Pribadi`
   - **Tipe** — `http` / `socks5` / `sticky` / `warp` / `none`
   - **Host & Port** — misal `192.168.1.10`, `8080`
   - **Username & Password** — kalau proxy butuh auth (opsional)
   - **Negara** — label aja, misal `US` (opsional)
   - **Aktif** — ON/OFF
   - **Catatan** — bebas
3. Klik **Test** → muncul IP, negara, latency (kecepatan).
4. Pool **bawaan (system)** nggak bisa dihapus, cuma bisa di-disable.

### Tipe pool

| Tipe | Artinya |
|---|---|
| `http` | Proxy HTTP biasa (host:port + auth opsional) |
| `socks5` | Proxy SOCKS5 |
| `sticky` | Proxy-bot DataImpulse lokal (session sticky otomatis per profil) |
| `warp` | Cloudflare WARP lokal |
| `none` | Langsung, tanpa proxy |

---

## Sticky vs WARP vs Manual

- **Sticky (disarankan):** 1 profil = 1 IP selamanya. IP beda tiap profil. Ini yang bikin akun-akunmu nggak ke-link.
- **WARP fallback:** kalau di profil `warp_fallback` ON dan proxy utama mati → otomatis pindah ke WARP. Kalau WARP juga mati → **tetap pakai proxy utama** (gagal terlihat, nggak pernah bocor ke direct/IP asli diam-diam).
- **Manual (http/socks5):** kamu supply proxy sendiri. Cocok kalau punya langganan proxy pribadi.

---

## Test Koneksi

Di daftar pool, klik **Test** per pool. Hasilnya:

- **online** — IP, negara, latency (ms). Makin kecil latency makin cepat.
- **offline** — ada error-nya (proxy mati / auth salah / network block).

Hasil test terakhir tersimpan di pool (`last_check`) jadi bisa lihat kapan terakhir dicek.

---

## Assign Pool ke Profil

1. Buka editor profil → dropdown **Proxy Pool**.
2. Pilih pool. Profil baru otomatis pakai **pool default** (⭐).
3. Pool default bisa diganti: di daftar pool, set salah satu jadi default.

---

## Best Practices

1. **1 profil = 1 proxy.** Jangan 1 proxy dipakai rame-rame 100 akun — itu pola yang gampang ke-detect.
2. **Negara proxy ≈ timezone profil.** Kalau proxy US tapi timezone Asia/Jakarta → aneh. Samakan.
3. **Test sebelum dipakai massal.** Pool baru → test dulu, pastikan online & latency wajar (< 3000ms).
4. **WARP itu cadangan, bukan utama.** IP WARP itu datacenter Cloudflare — bagus buat fallback, tapi residential (DataImpulse) lebih "manusiawi" buat daftar akun.
5. **Jangan pakai Direct buat akun penting.** IP aslimu kelihatan dan gampang di-link ke semua akun.
6. **Ganti pool yang bermasalah.** IP kena flag 2x → ganti pool/proxy, jangan dipaksa.

---

## Penyimpanan

Config pool di `gui/data/proxy_pools.json` (**chmod 600** — password proxy cuma di file lokal, nggak dikirim ke mana-mana).
