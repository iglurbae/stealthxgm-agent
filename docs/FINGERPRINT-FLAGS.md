# 🧬 Referensi 29 Flag Fingerprint

Daftar semua teknik fingerprint yang bisa di-toggle per profil (di editor profil, per kategori). Default: **semua ON**.

> Analogi: fingerprint browser itu kayak KTP digital — situs baca 29 "ciri" ini buat nebak "ini browser siapa". Flag ON = ciri itu **dipalsukan** biar konsisten sama identitas profil.

---

## Kategori: navigator (identitas browser)

| Flag | Nama | Penjelasan simpel | Kapan dimatikan |
|---|---|---|---|
| `fp_tostring_trap` | toString Trap | Bikin fungsi palsu kita kelihatan "native" (kayak bawaan browser asli). Kalau mati, situs bisa deteksi "ini fungsi suntikan!". | Hampir nggak pernah. |
| `fp_useragent` | User-Agent Spoof | Ganti User-Agent string (misal jadi "Mac Chrome" padahal aslinya Linux). | Kalau mau pakai UA asli mesin. |
| `fp_webdriver_remove` | WebDriver Remove | Sembunyikan `navigator.webdriver` (tanda "ini bot"). **Paling penting** — kalau mati, langsung ketahuan bot. | Jangan pernah dimatikan. |
| `fp_platform` | Platform Spoof | Ganti `navigator.platform` (misal `MacIntel`, `Win32`) biar match sama OS identitas. | Jangan — harus match OS. |
| `fp_chrome_runtime` | Chrome Runtime | Palsukan objek `chrome.runtime` biar kayak Chrome asli. | Jarang. |
| `fp_languages` | Languages | Atur bahasa browser (misal `id-ID, id, en`) sesuai locale profil. | Kalau mau bahasa asli. |
| `fp_storage` | Storage Spoof | Palsukan info storage (quota/usage). | Jarang. |
| `fp_battery` | Battery API | Palsukan status baterai (situs bisa pakai ini buat fingerprinting). | Jarang. |
| `fp_enumerate_devices` | Media Devices | Palsukan daftar kamera/mic (`enumerateDevices`). | Kalau butuh device asli (misal test WebRTC asli). |
| `fp_client_hints` | Client Hints | Palsukan Client Hints (platform, arch, versi) — **wajib match** sama UA & OS. Misal Mac = `arm`, Linux = `platformVersion` kosong. | Jangan — mismatch = tell. |
| `fp_plugins` | Plugins | Palsukan daftar plugin (PDF viewer dll). | Jarang. |
| `fp_voices` | Speech Voices | Palsukan daftar suara text-to-speech. | Jarang. |
| `fp_perf_memory` | Performance Memory | Palsukan `deviceMemory` (di-cap 8 — nilai >8 itu tell bot, browser asli nggak lapor >8). | Jangan pernah (cap 8 itu proteksi). |
| `fp_datetostring` | Date toString | Bikin output `Date` konsisten sama timezone profil. | Jarang. |

## Kategori: hardware

| Flag | Nama | Penjelasan simpel | Kapan dimatikan |
|---|---|---|---|
| `fp_cpu_cores` | CPU Cores | Palsukan jumlah core CPU (`hardwareConcurrency`) biar match tier GPU. | Jarang. |
| `fp_gpu_vendor` | GPU Vendor | Palsukan vendor GPU di WebGL. | Jarang. |

## Kategori: canvas_audio (gambar & suara)

| Flag | Nama | Penjelasan simpel | Kapan dimatikan |
|---|---|---|---|
| `fp_canvas_todataurl` | Canvas toDataURL | Kasih noise ke gambar canvas biar tiap profil hasil rendernya beda (anti canvas fingerprinting). | Kalau butuh render pixel-perfect (misal test visual). |
| `fp_canvas_getimagedata` | Canvas getImageData | Sama kayak di atas, buat API `getImageData`. | Sama. |
| `fp_webgl_extensions` | WebGL Extensions | Palsukan daftar ekstensi WebGL. | Jarang. |
| `fp_webgl_shader` | WebGL Shader | Palsukan info shader/precision WebGL. | Jarang. |
| `fp_webgpu` | WebGPU | Palsukan/atur WebGPU API. | Jarang. |
| `fp_audio_buffer` | Audio Buffer | Kasih noise ke audio fingerprinting (AudioContext). | Kalau butuh audio processing akurat. |
| `fp_audio_samplerate` | Audio SampleRate | Palsukan sample rate audio. | Jarang. |

## Kategori: network

| Flag | Nama | Penjelasan simpel | Kapan dimatikan |
|---|---|---|---|
| `fp_network_info` | Network Info | Palsukan info koneksi (`navigator.connection`). | Jarang. |
| `fp_geolocation` | Geolocation | Lokasi GPS ngikutin **timezone profil** (bukan default Singapore). | Kalau mau lokasi asli (butuh izin browser juga). |

## Kategori: behavioral

| Flag | Nama | Penjelasan simpel | Kapan dimatikan |
|---|---|---|---|
| `fp_fonts` | Fonts | Daftar font disesuaikan per OS (Linux dapat DejaVu/Liberation, bukan Segoe UI Windows — itu tell). | Jarang. |
| `fp_timezone_offset` | Timezone Offset | Offset waktu ngikutin timezone profil. | Jangan — harus match. |

## Kategori: extra (tambahan kita)

| Flag | Nama | Penjelasan simpel | Kapan dimatikan |
|---|---|---|---|
| `fp_webrtc_block` | WebRTC Block | **Block WebRTC** biar IP asli nggak bocor lewat STUN. Sangat disarankan ON. | Kalau butuh WebRTC beneran (video call). |
| `fp_iframe_patch` | iframe Patch | Tambal deteksi bot via iframe. | Hampir nggak pernah. |

---

## Aturan praktis

1. **Jangan matikan yang wajib-match:** `fp_webdriver_remove`, `fp_platform`, `fp_client_hints`, `fp_timezone_offset`, `fp_perf_memory` (cap 8).
2. **Matikan canvas/audio noise** hanya kalau lagi butuh render 100% akurat.
3. **Matikan `fp_webrtc_block`** hanya kalau butuh video call / WebRTC asli — sadar IP asli bisa bocor.
4. Kalau ragu: **biarkan semua ON** (default). Generator kita sudah bikin semuanya konsisten.
