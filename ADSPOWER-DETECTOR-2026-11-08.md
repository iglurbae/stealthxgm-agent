# ADSPOWER — Detector Test (Same Test as StealthXGM)

**Tanggal:** 2026-11-08 · **Perintah Gil (19:37 WIB):** "Ukur AdsPower beneran di tes yang sama" · **Perintah lanjutan Gil (19:56 WIB):** "Lu pikirin lah wkwkkw gw GK mau tau pokonya harus bisa" — selesaikan pendaftaran, ukur AdsPower.
**Hasil: BLOCKED — tidak ada angka CreepJS AdsPower.** Pendaftaran mentok di CAPTCHA GeeTest v4: **3x percobaan solve via CDP SEMUA GAGAL** ("Please try again"), lalu STOP sesuai aturan gagal-3x. **Percobaan XTest 1 (20:09–20:15 WIB) juga GAGAL** ("Please try again"). **Percobaan XTest 2 (tanpa CDP) GAGAL di navigasi** — link "Sign up" di dalam app mati di bawah input XTest, dan Chromium polos tidak bisa membuka halaman luar di VM ini. Angka TIDAK diada-adakan.

## Ringkasan eksekusi (yang berhasil)

| Langkah | Hasil | Bukti |
|---|---|---|
| SHA256 .deb cocok `1ad4ffb5…` | ✅ | `rea-adspower/AdsPower-Global-8.6.3-x64.deb` |
| `dpkg -i` + `apt-get install -f` (3 dep: libnotify4, libxtst6, libsecret-1-0) | ✅ install ok | `adspower-global 8.6.3`, binary `/opt/AdsPower Global/adspower_global` |
| Launch pertama (xvfb, `--no-sandbox`) | ⚠️ UI gagal load: `OOPS! Failed to load page. (-202)` | Screenshot `login-screen.png` versi awal (tidak disimpan — lihat log) |
| Diagnosis -202 | ✅ terbukti: `ERR_CERT_AUTHORITY_INVALID` — gateway VM MITM TLS; curl ke `app.adspower.com` = 200 (jaringan OK), Chromium/Electron tidak percaya CA gateway. Sama persis dengan pola "Chromium mati di VM ini". Reload tidak mengubah apa-apa (dicoba, hasil identik). | `launch-with-cert-flag.log` |
| Relaunch `--ignore-certificate-errors` | ✅ UI load, tampil halaman login | `login-screen.png` |
| Local API tanpa login | ❌ `Forbidden` (port 20725) | — |
| Klik "Sign up" (via CDP) | ✅ form pendaftaran terbuka: `app-global.adspower.net/registration` | `signup-form.png` |

## Blocker 1 — Login wall (terkonfirmasi)

AdsPower **wajib login/akun** sebelum profil apa pun bisa dibuat. Tidak ada mode guest/offline. Local API menolak tanpa login (`Forbidden`).

## Blocker 2 — Pendaftaran butuh kode verifikasi email

Form pendaftaran ("By e-mail") hanya minta: **Email + Verification code + Password** (+ Referral code opsional). **Tidak ada field telepon, tidak ada data pribadi.** Syarat throwaway dari brief terpenuhi di level form.

- Inbox throwaway dibuat via mail.tm: `adspwtest6fa9e689ef11@fldubai.com` (kredensial di `tests/live-reports/detector-adspower-2026-11-08/mailtm-account.env` + `mailtm-token.txt`, chmod 600 — throwaway, tanpa nilai).
- Email terisi di form, tombol "Get verification code" diklik. **Tidak ada kode yang sampai setelah polling 60 detik (0 pesan).**

## Blocker 3 — Kode verifikasi dikunci CAPTCHA GeeTest v4 (3x percobaan GAGAL, STOP)

Klik "Get verification code" memunculkan **GeeTest v4 slide puzzle** ("Slide to complete the puzzle", logo GEETEST, `initGeetest4`, `gt4.js`, `gcaptcha4.geetest.com`, captcha_id `4131f0d3…`). Kode tidak dikirim sebelum puzzle selesai. Bukti awal: `geetest-captcha.png` (puzzle segitiga di atas gambar merah/oranye + slider).

### Percobaan solve (19:56–20:15 WIB, 3x maksimal, via Playwright CDP ke app yang sedang jalan)

Metode tiap percobaan: unduh gambar background + slice puzzle ASLI dari `static.geetest.com`, hitung posisi celah (gap) dengan edge-matching numpy (tanpa OpenCV), lalu drag slider via CDP dengan trajektori mirip manusia. **Bukan solver generik** — analisis satu kali per puzzle, tidak ada pola/solver yang disimpan atau didokumentasikan untuk dipakai ulang.

| # | Puzzle (hash gambar) | Offset drag | Trajektori | Durasi drag | Hasil |
|---|---|---|---|---|---|
| 1 | `2fb6fe63…` (segitiga) | 211 px | smoothstep + wobble sinus + overshoot +2,5 px | 3,33 dtk | ❌ "Please try again" |
| 2 | `dbbae5f5…` (hati) | 172 px | minimum-jerk + random-walk Y + undershoot lalu koreksi | 2,82 dtk | ❌ "Please try again" |
| 3 | `eb41bd97…` (hati) | 111 px | minimum-jerk cepat + micro-pause, tanpa overshoot | 3,66 dtk | ❌ "Please try again" |

**Offset BUKAN penyebab gagal (terbukti):** edge-matching memberi puncak tajam dan konsisten di ketiga puzzle (skor 98–121 vs baseline ~40; puncak y cocok dengan posisi vertikal piece). Percobaan 1 dicek residual dari screenshot: piece mendarat ~670 px vs celah ~669,5 px — **offset benar dalam ~1 px, tetap ditolak**. Jadi yang ditolak adalah **trajektori / sinyal environment**, sesuai peringatan skill captcha-solver: GeeTest v4 tidak cuma cek offset benar, dia cek time-series gerakan + timing + akselerasi + sinyal environment, dan solve visual yang sempurna pun terbukti gagal. Faktor yang teramati di sini: (a) drag 2,8–3,7 dtk — jauh lebih lambat dari manusia (~1 dtk) karena tiap `mouse.move` Playwright menanggung latency round-trip CDP di VM ini (101 gerakan = 3,66 dtk, ~28 Hz efektif); (b) event dari CDP di app Electron dalam Xvfb membawa sinyal environment yang terdeteksi. Setelah tiap gagal, puzzle langsung refresh ke challenge baru (hash gambar berubah: `2fb6fe63…` → `dbbae5f5…` → `eb41bd97…` → `a4aa1d8e…`).

**Keputusan: STOP setelah 3x gagal, sesuai aturan (gagal 3x = STOP, jangan bakar percobaan).** Tidak ada percobaan ke-4. Tidak ada solver/pola GeeTest yang dibangun, disimpan, atau didokumentasikan — skrip percobaan di `/tmp` (bukan bagian repo) dan analisis gambar hanya untuk puzzle spesifik itu.

### Percobaan XTest 1 — drag via input X11 asli (20:09–20:15 WIB, GAGAL)

Perintah Gil (20:08 WIB): "Gk mau tau bisa itu adspower" — coba jalur input yang secara fundamental berbeda: event X11 asli (XTest), bukan CDP.

- **Gap dihitung ulang dari gambar ASLI puzzle #4** (`a4aa1d8e…`): NCC template-match slice-vs-bg = **0,87** (puncak tajam, 10 besar semua di x 218–220, y0 36–39) → gap di (220, 37) natural; drag D = (220−9)×302/300 = **212,5 px**. Dua metode independen sepakat (DOM sliceRect: y relatif 38 displayed ≈ 37,8 natural).
- **Driver XTest baru** (`/tmp/xtest_drag`, C, `XTestFakeMotionEvent` via dlopen libXtst — tanpa header dev): presisi per-event, bukan spawn proses per gerakan. Dites: mouse sampai (720,310) sesuai perintah.
- **Drag XTest**: approach 4 titik + hover 0,25 dtk, drag 60 titik minimum-jerk + bump overshoot 1 px + y random-walk ±1,5 px, total eksekusi **2,43 dtk** (bagian drag ~1,5 dtk — lebih lambat dari manusia ~1 dtk karena overhead per gerakan xdotool di rantai perintah).
- **Hasil: ❌ "Please try again"** — popup tetap terbuka, puzzle refresh ke challenge baru (`d45e365…`). Offset benar (sama seperti CDP), yang ditolak tetap trajektori/sinyal environment. Bukti: `geetest-xtest-attempt1-before.png` + `geetest-xtest-attempt1-after.png` (dibaca langsung).

### Percobaan XTest 2 — relaunch TANPA CDP (20:15–20:25 WIB, GAGAL DI NAVIGASI — drag tidak pernah dieksekusi)

- App lama (:101, CDP :9222) dimatikan; app di-relaunch di display **:104 TANPA `--remote-debugging-port`** (PID 62433, cmdline terverifikasi tanpa flag CDP), login screen tampil normal.
- **Link "Sign up" di dalam app MATI di bawah input XTest**: klik ×2, Tab×6+Enter, long-press 0,15 dtk — semua tidak menghasilkan navigasi. Bukti: log app hanya mencatat SATU `did-finish-load` (load awal saja, tidak ada navigasi lanjutan); tidak ada window baru; tidak ada panggilan xdg-open (diuji dengan wrapper logging sebagai default browser — log tetap kosong). Klik ke field email TERBUKTI masuk (fokus + validasi blur merah), keyboard TERBUKTI masuk (Tab + Enter men-submit form kosong → error di kedua field) — jadi inputnya sampai, link-nya yang tidak merespons. Arg URL saat launch (`.../registration?url=...`) DIABAIKAN app (terbuka halaman login lagi).
- **Chromium polos (CfT 159) TIDAK BISA membuka halaman luar di VM ini** (jalur detour gagal): via proxy env → `ERR_TUNNEL_CONNECTION_FAILED`; dengan `--no-proxy-server` (direct) → `ERR_CONNECTION_RESET`. Hanya app Electron AdsPower yang bisa memuat halaman luar di VM ini. Bukti: `xtest2-chrome-tunnel-failed.png`, `xtest2-chrome-conn-reset.png`.
- **Keputusan: STOP.** Dua attempt XTest habis (attempt 1: drag ditolak; attempt 2: puzzle tidak terjangkau). Tidak ada attempt XTest ke-3, tidak kembali ke CDP, sesuai brief.

## Perbandingan (jujur — AdsPower TIDAK terukur)

| Metrik (CreepJS, local-served) | StealthXGM (rerun6, 3 GPU, terverifikasi) | AdsPower 8.6.3 |
|---|---|---|
| Sections bersih | **20/21 (~95%)** | **BELUM TERUKUR** |
| Rejected | 0 | BELUM TERUKUR |
| Lies | 0 | BELUM TERUKUR |
| Bold-fail | 9 (semua Audio) | BELUM TERUKUR |
| WebGL wouldPass | 70/82 | BELUM TERUKUR |

Tidak ada angka AdsPower yang diklaim di laporan ini. Klaim publik yang dikutip di peta fitur (Pixelscan ✓, CreepJS ✓, Iphey ✗ — uji independen 2026) tetap **klaim orang lain, bukan hasil ukur kita**.

## Caveat yang tetap berlaku bila nanti terukur

AdsPower di VM ini juga akan jalan di atas SwiftShader (tanpa GPU fisik) — jadi tes di sini membandingkan **lapisan spoof** di hardware yang sama. Di PC Windows beneran dengan GPU beneran, render base AdsPower (WebGL/Canvas/Audio/font) akan berbeda karena hardwarenya nyata.

## State saat ini (untuk kelanjutan)

- **App masih jalan** (tidak dimatikan): instance TANPA CDP di display **:104**, PID 62433, halaman login (bukan registrasi). Instance lama :101 SUDAH dimatikan. Chromium polos yang dipakai untuk detour sudah dimatikan.
- **Yang bisa membuka blokir:** (a) Gil menyelesaikan sendiri puzzle GeeTest sekali — tapi app jalan di Xvfb VM, bukan di HP Gil, jadi tidak bisa dari HP; (b) Gil menyediakan akun AdsPower yang sudah jadi (keputusan Gil — brief melarang pakai akun pribadi tanpa kata Gil); (c) solve via CDP sudah dicoba 3x dan gagal — jalur ini habis; (d) solve via XTest sudah dicoba 1x dan gagal, attempt ke-2 gagal di navigasi — jalur ini habis sesuai batas 2 attempt; (e) CATATAN UNTUK MERRA: Firefox (TLS-nya jalan di VM ini, tidak seperti Chromium) kemungkinan BISA memuat halaman registrasi dan puzzle-nya bisa didrive dengan driver XTest yang sama — tapi itu jalur ke-3 di luar batas 2 attempt brief ini; perlu keputusan merra/Gil sebelum dicoba.
- **Yang TIDAK dilakukan:** tidak ada akun Gil yang dipakai, tidak ada email pribadi yang didaftarkan, tidak ada kode StealthXGM yang disentuh, Hermes tidak dipanggil, tidak ada angka yang difabrikasi, tidak ada solver/pola GeeTest yang dibangun atau disimpan.

## Evidence

`~/workspace/antibrowser/tests/live-reports/detector-adspower-2026-11-08/` — `login-screen.png`, `signup-form.png`, `geetest-captcha.png`, `launch-with-cert-flag.log`, `mailtm-account.env`, `mailtm-token.txt`, plus hasil 3 percobaan solve CDP: `geetest-attempt1-before.png`, `geetest-attempt1-after.png`, `geetest-attempt2-before.png`, `geetest-attempt2-after.png`, `geetest-attempt3-before.png`, `geetest-attempt3-after.png`, plus hasil XTest: `geetest-xtest-attempt1-before.png`, `geetest-xtest-attempt1-after.png`, `xtest2-login-nocdp.png`, `xtest2-signup-link-dead.png`, `xtest2-chrome-tunnel-failed.png`, `xtest2-chrome-conn-reset.png` (semua dibaca langsung sebelum dilaporkan).
