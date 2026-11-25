# 🎲 Fingerprint Generator

Konfigurator sidik jari visual — 2 mode: **Random (ngotak)** dan **Manual**.

## Mode Random

Pilih OS → Generate. Identitas yang dihasilkan **dijamin konsisten**:

| OS | Aturan konsistensi |
|---|---|
| Windows | GPU NVIDIA/AMD/Intel + renderer Direct3D11, platform Win32, UA Windows NT |
| macOS | GPU Apple Silicon + ANGLE Metal Renderer, platform MacIntel, layar Retina dpr=2 |
| Linux | GPU NVIDIA/AMD/Intel + renderer OpenGL, platform Linux x86_64 |
| Android | Chipset → GPU mapping (Snapdragon→Adreno, Dimensity/Helio→Mali-G, dst), UA Android + token Mobile |
| iOS | Chipset Apple A/M → Apple GPU, platform iPhone, UA iPhone |

CPU tier selalu match GPU tier (budget/mid/flagship); `deviceMemory` di-cap 8
(nilai >8 = tell bot); locale otomatis dari timezone.

## Mode Manual

Pilih per-field: versi Chrome, GPU, layar, CPU core, RAM, timezone, locale.
Tombol **Preview Manual** menjalankan validasi — warning muncul kalau tidak
konsisten, misal:

- MacIntel + renderer Direct3D11 → "Mac harus pakai ANGLE Metal Renderer"
- Win32 + GPU Apple → "tidak masuk akal"
- deviceMemory > 8 → "tell bot"

Untuk mobile, GPU otomatis dari SoC (tidak bisa manual) — pakai mode Random.

## Aksi

- **🧪 Test di browser** — launch profil target dengan identitas ini (sekali pakai,
  tidak disimpan), buka `browserleaks.com/javascript`.
- **💾 Simpan ke profil** — identitas tersimpan di `profil.fingerprint.identity`;
  launch berikutnya pakai identitas yang sama (stabil, tidak acak tiap launch).
- **📋 Copy JSON** — copy config identitas.

Hapus identitas tersimpan: `DELETE /api/profiles/<pid>/fingerprint`
→ kembali ke generate acak tiap launch.

## API

| Endpoint | Fungsi |
|---|---|
| `GET /api/fingerprint/options?os=` | Opsi dropdown mode manual |
| `POST /api/fingerprint/generate` | `{os, timezone, locale, chrome_ver, country}` → `{identity}` |
| `POST /api/fingerprint/validate` | `{identity}` → `{consistent, warnings[]}` |
| `POST /api/fingerprint/preview` | `{identity, features?}` → `{preview}` |
| `POST /api/profiles/<pid>/fingerprint` | Simpan identitas ke profil |
| `DELETE /api/profiles/<pid>/fingerprint` | Hapus identitas tersimpan |
| `POST /api/profiles/<pid>/launch` | Body opsional `{identity, url}` untuk test sekali |

## File

- `gui/fingerprint_gen.py` — logic generate/validate/preview/options
- `fingerprint/mobile.py::mobile_spoof_js_from_dict` — spoof JS dari dict
  tersimpan (objek MobileFingerprint tidak bisa di-serialize)
- `vendor/mobile_fingerprint.py` — vendored device DB (451 device),
  agar StealthXGM tidak bergantung ke stealth_browser
- `launcher/launcher.py::build_fingerprint_js` — prioritas:
  override → identity tersimpan → generate baru
