# PROMPT UNTUK GEMINI / ChatGPT / Claude — Review Kritis StealthXGM

Copy-paste prompt di bawah ini ke Gemini/ChatGPT/Claude:

---

Saya sedang membangun **StealthXGM** — anti-detect browser open-source (alternatif AdsPower/Multilogin) untuk kebutuhan multi-account yang legitimate (testing, QA, riset keamanan). Saya butuh review yang **BRUTAL JUJUR**, bukan pujian.

**Konteks teknis:**
- Base: Chromium via Playwright, fingerprint di-inject via CDP `Page.addScriptToEvaluateOnNewDocument` sebelum page load
- 29 teknik fingerprint spoofing (navigator, canvas, WebGL, audio, screen, fonts, timezone, dll)
- Baru saja fix 5 bug P0 kritis: webgpu SyntaxError bomb, getter .toString() leak, canvas noise random per launch, plugins identity, Date timezone mismatch
- Klaim saat ini: 500/500 generate konsisten, 9/9 launcher test PASS, webdriver=false

**Yang saya mau dari kamu:**

1. **Cari lubang yang belum ketemu.** Jangan percaya klaim saya. Anggap saya overconfident. Apa teknik deteksi bot modern (DataDome, PerimeterX, Kasada, Cloudflare Bot Management) yang BISA menembus pendekatan inject-JS ini?

2. **Kritik arsitektur.** Apakah inject-JS via CDP adalah pendekatan yang tepat, atau ada yang fundamental salah? Apa yang kompetitor (Multilogin, AdsPower, GoLogin) lakukan yang saya tidak lakukan?

3. **Cari bug logika.** Dari deskripsi di atas, apa yang terdengar "too good to be true"? Di mana kemungkinan saya salah paham tentang cara kerja browser fingerprinting?

4. **Prioritaskan.** Dari semua masalah yang kamu temukan, mana 3 yang PALING kritis — yang kalau tidak di-fix, produk ini tidak layak disebut "anti-detect"?

**Aturan main:**
- Jangan kasih saran generik ("gunakan best practices", "lakukan testing menyeluruh")
- Kasih spesifik: nama API, nama properti, baris kode konseptual, atau teknik deteksi yang konkret
- Kalau ada yang kamu tidak yakin, bilang tidak yakin — jangan ngarang
- Saya lebih butuh 3 temuan tajam daripada 20 temuan dangkal

**Pertanyaan pembuka untuk kamu jawab dulu:**
Apakah pendekatan "spoof fingerprint via JavaScript injection" secara fundamental bisa menahan deteksi bot tingkat enterprise, atau ini cuma "security theater" yang terlihat meyakinkan di browserleaks.com tapi rontok di DataDome?

---

## LAMPIRAN TEKNIS (opsional, untuk deep dive)

**File kunci untuk direview:**
1. `fingerprint/_core.py` — framework inject (IIFE, seed management, tostring trap)
2. `fingerprint/navigator.py` — spoof navigator.* (userAgent, platform, plugins, webdriver)
3. `fingerprint/canvas_audio.py` — canvas/WebGL/audio noise
4. `fingerprint/behavioral.py` — fonts, timezone, Date
5. `launcher/launcher.py` — launch flow, proxy resolve, cookie inject
6. `launcher/injector_daemon.py` — persistent CDP injection

**Yang sudah di-fix (jangan lapor ulang):**
- webgpu flag OFF → SyntaxError (fixed: IIFE dipindah ke core)
- getter .toString() bocor "() => ident._ua" (fixed: named getters + tostring trap)
- canvas seed random per launch (fixed: seed dari MD5 profile-id)
- navigator.plugins identity (fixed: stable array + proper prototype)
- Date.toString() vs getTimezoneOffset() mismatch (fixed)

**Known limitation (sudah diakui):**
- TLS/JA3 fingerprint tidak bisa di-spoof via JS (butuh network-level)
- iOS = spoof JS di engine Blink (bukan WebKit asli)
