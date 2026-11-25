# FIX-LOG — Fase 4: Desain Fresh GUI StealthXGM

**Tanggal:** 2026-11-07 (selesai ~20:40 WIB)
**Perintah Gil:** "Kita tiru adspower" + "Tapi design kita harus fresh" (17:49 WIB); "Okay lu tuntasin ya" (18:14 WIB)
**Baseline:** P0 9/9 + P1 9/9 + Fase 3 8 fitur — suite 685 PASS, 0 FAIL, 27 file
**Hasil akhir:** suite **702 PASS, 0 FAIL, 28 file** (685 baseline + 17 cek desain baru)
**Backup:** `.fix-backups/fase4/` (index.html + login.html sebelum diubah)
**Screenshot:** `docs/design/` (5 PNG, diambil dari GUI live port 5200 via CfT Chromium 159 headless)

---

## 1. Identitas baru: "Bara"

Tema gelap modern, identitas visual sendiri — bukan jiplak AdsPower:

- **Warna:** tinta gelap `#0d0f14` / `#171b25` + amber `#f5a524` (aksen utama, tombol CTA, item nav aktif). Bukan biru/ungu AdsPower.
- **Marka:** logo SVG bertumpuk (3 persegi + 3 titik + garis) — dibuat sendiri, bukan logo AdsPower.
- **Nama fitur sendiri:** Synchronizer → **Cermin**, RPA → **Alur**, kernel manager → **Kernel**, backup → **Cadangan**. Nama AdsPower (SunBrowser, FlowerBrowser, RPA Plus, AI Plus, Cookie Robot, Synchronizer) TIDAK ADA di template manapun — dikunci test.
- **Yang TIDAK ditiru:** layout AdsPower, warnanya, nama-namanya. `contextIsolation` tetap NYALA (AdsPower mematikannya — jangan ditiru).

## 2. Struktur baru (index.html)

| Sebelum | Sesudah |
|---|---|
| Header sempit di atas, semua section menumpuk vertikal | **Sidebar kiri** (KELOLA: Profil, Cermin, Alur, Kernel, Cadangan; SISTEM: Ekstensi, Pool Proxy, API Lokal, Sampah) + area konten |
| Judul + tombol tersebar | **Header view** (judul + subjudul per view) + **strip statistik** (Total profil / Sedang jalan / Grup) di view Profil |
| Sampah/Pool/Ekstensi/API section biasa | Semua jadi **view** (satu layar satu fokus), navigasi via `showView(name)` + hash URL (`#/cermin` dst — bisa di-bookmark) |
| Kartu profil baris sederhana | **Kartu grid 2 kolom**: avatar inisial warna per platform (🟢 android, 🔵 macos, 🟠 windows, 🟣 linux), chip grup/teknik/platform/sticky/WARP, tombol Launch/Edit/Duplikat/Cookie/Cadangkan + 🗑 |
| Toolbar lama | Tetap: Cari, filter grup, + Baru, Batch, Fingerprint, bar batch — semua fungsi lama jalan |
| Login di header | Tombol **Keluar** di sidebar bawah (hanya muncul bila GUI pakai password) |
| Editor profil di bawah halaman | Editor jadi **view** sendiri (`#view-editor`) |

## 3. Panel fitur baru (sebelumnya cuma API, tanpa UI)

- **Cermin** (`#view-cermin`): status badge jalan/mati, pemimpin + pengikut (dari profil yang sedang jalan), jeda buka, cakupan; kontrol Mulai/Berhenti/Refresh, buka URL di semua jendela, ketik teks di semua jendela, jalankan alur di semua jendela, tab pemimpin, log terakhir.
- **Kernel** (`#view-kernel`): daftar kernel (sistem + terdaftar, badge default), unduh versi baru (job + progress), daftarkan binary manual (path/nama/engine), jadikan default, hapus dari registry.
- **Cadangan** (`#view-cadangan`): buat cadangan per profil (saklar ikut cache), daftar file cadangan (ukuran, tanggal, badge rusak), restore jadi profil baru, hapus file.
- **Alur** (`#view-alur`): simpan alur (nama + langkah JSON, validasi JSON), daftar alur (jalankan ke profil jalan / hapus), **Cek Sidik** — pilih profil yang sedang jalan, tabel PASS/FAIL/INFO (harapan vs live).
- **Job Batch** (di modal Batch): daftar 8 job terakhir (progress, batalkan, unduh hasil ekspor), tombol ekspor CSV.

## 4. login.html

Tulis ulang dengan identitas "Bara" (marka + amber + kartu gelap). **Logika JS byte-identik**: id `f/pw/btn/err/sub` sama, endpoint `/api/auth/status`, `/api/auth/setup`, `/api/auth/login` sama, mode setup (belum ada password) tetap terdeteksi. Proteksi login (F3-8: hash password, sesi 12 jam, rate-limit) TIDAK dilemahkan — backend `gui/auth.py` tidak disentuh.

## 5. Yang TETAP (kontrak, dikunci test)

- Semua id elemen lama + semua nama fungsi JS lama ada (test `test_f4_design.py` memeriksa ~90 id dan ~80 fungsi).
- Kontrak lama: `"Izin:"` + `host_permissions` (P-05), `storageWarn` + `checkStorageHealth` (P-11), tanpa `[StealthXGM]` (P-03).
- Semua rute API yang dipanggil panel baru sudah ada di `gui/app.py` — **backend TIDAK diubah sama sekali** (0 baris Python berubah).
- `dist/` tidak disentuh. Remote view SKIP (sesuai tugas). Captcha solver TIDAK dibangun. Tanpa tool/service berbayar.

## 6. Test baru: tests/test_f4_design.py (17 cek)

1. Semua id elemen lama ada · 2. Semua fungsi JS lama ada · 3. Kontrak P-05 · 4. Kontrak P-11 · 5. Kontrak P-03 · 6. Tanpa nama produk AdsPower · 7. Semua id view/panel baru ada · 8. Semua fungsi JS panel baru ada · 9. Rute panel baru ada di app.py · 10. Id form login tetap · 11. Endpoint auth di login tetap · 12. Section view seimbang · 13. main + shell ditutup · 14. Identitas baru dipakai (`#f5a524`) · 15. Sidebar ada · 16. GET / 200 + judul · 17. GET /login 200.

Suite penuh: **702 PASS, 0 FAIL, 28 file** (~197 detik). Per file: test_f3_api 86, test_f3_backup 49, test_f3_batch 49, test_f3_extensions 57, test_f3_freeze 21, test_f3_kernels 58, test_f3_login 63, test_f3_sync 55, **test_f4_design 17**, test_p01 4, test_p02 4, test_p03 3, test_p04 6, test_p05 7, test_p06 6, test_p07_locking 14, test_p08 6, test_p09_proxy_auth 25, test_p10_watchdog 20, test_p11 9, test_p12_registry 15, test_p13 5, test_p14_headless 11, test_p15_cookies 20, test_p16_api_contract 19, test_p16_consistency 11, test_p17_injection 19, test_p18_rpa 43.

## 7. Screenshot (docs/design/, 1280×900, CfT Chromium 159 headless)

| File | Isi |
|---|---|
| `utama.png` | Halaman utama, state kosong (0 profil) |
| `profil.png` | Daftar profil — 3 profil demo (kartu + avatar + chip + tombol) |
| `cermin.png` | View Cermin (status mati — tidak ada browser jalan) |
| `kernel.png` | View Kernel (Chromium sistem 156 + CfT 159.0.8148.0 terdaftar) |
| `login.png` | Halaman login, mode setup (belum ada password) |

**Kendala screenshot (diperbaiki):** CfT Chromium crash exit 133 — `chrome_crashpad_handler: Permission denied`. Perbaikan: `chmod +x kernels/159.0.8148.0/chrome-linux64/chrome_crashpad_handler` (+ `chrome_sandbox`). kernels/ di-gitignore, jadi perubahan mode tidak masuk commit.

**Data demo:** 3 profil demo (Tokopedia Akun 1 / Shopee Akun 2 / IG Akun 3) dibuat via API hanya untuk screenshot `profil.png`, lalu dihapus permanen (trash → permanent). Data kembali persis seperti semula: 0 profil aktif, 2 profil di sampah (sisa test 2026-11-04). GUI live port 5200 dimatikan setelah screenshot.

## 8. Catatan jujur

- Panel Cermin/Alur/Cek Sidik di screenshot tampil "tidak ada browser jalan" — itu data nyata dari API, bukan mock; panelnya baru terisi saat ada profil yang di-launch.
- Hermes: **0 call** di fase ini — desain dikerjakan langsung (Hermes hanya untuk tugas kecil spesifik; tidak ada subtugas yang cocok).
- Commit: `F4: desain fresh GUI "Bara" — sidebar, kartu profil, view Cermin/Kernel/Cadangan/Alur` (template + test), `F4: screenshot desain baru` (docs/design), log ini.

## 9. Di luar scope (tunggu kata Gil)

Versi berbayar/lisensi, cloud sync/tim. Sisa P2 (identity belum dibekukan antar launch, window sync, login GUI penuh — login GUI sudah selesai di F3-8, tersisa dari P1) tetap di antrean.
