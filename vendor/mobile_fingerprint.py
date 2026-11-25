from __future__ import annotations

"""
MOBILE_FINGERPRINT.PY — generate mobile fingerprint LENGKAP untuk Gmail signup.

Google kasih risk score LEBIH RINGAN untuk mobile browser.
iPhone Safari = paling dipercaya. Android Chrome = kedua.

Setiap fingerprint = 1 DEVICE PROFILE yang KONSISTEN:
  iPhone  → UA iOS + viewport iPhone + platform "iPhone" + dpr 3 + 6 core + Apple chipset
  Android → UA Android + viewport Android + platform "Linux armv8l" + Snapdragon/MTK/Exynos/Tensor

67 DEVICE PROFILE → 451 DEVICE PROFILE (database 416-device Gil)
  - iOS: 15.x → 18.x  (11, X, SE 2022, 12 series, 13 series, 14 series, 15 series)
  - Android phone: 11 → 15  (Redmi Note 10 → Pixel 8 Pro)
  - Tablet: 2 iPad + 22 Android (Tab S9/S8/A9+/A8, Xiaomi Pad 6/6 Pro/5,
    Lenovo P12/P11, Realme Pad 2/Pad, MatePad 11.5/Pro 13.2,
    Honor Pad 9/X9, Nokia T21, TCL Tab 11/NXTPAPER 11)
    → UA tablet TANPA token "Mobile", touch 10 titik
  - RAM: 3 / 4 / 6 / 8 / 12 / 16 GB (sesuai tier device)
  - iOS: 15.x → 18.x  (11, X, SE 2022, 12 series, 13 series, 14 series, 15 series)
  - Android: 11 → 15  (Redmi Note 10 → Pixel 8 Pro)
  - RAM: 3 / 4 / 6 / 8 / 12 / 16 GB (sesuai tier device)
  - Chipset EXACT per device (A11→A17 Pro, SD 665→8 Gen 3, Helio, Dimensity, Exynos, Tensor)
  - Pasar Indonesia: OPPO, Vivo, Realme, Infinix WAJIB ada ✅

Pakai `fake-useragent` kalau ada (326K+ real UA).
Fallback ke built-in list kalau tidak ada (tetap real UA, hanya lebih sedikit).
"""

import random
import re

# ── Coba pakai fake-useragent, fallback ke built-in ──
try:
    from fake_useragent import UserAgent as _RealUA
    _HAS_FAKE_UA = True
except ImportError:
    _HAS_FAKE_UA = False


# ═══════════════════════════════════════════════════════════════
# CHIPSET WHITELIST — dipakai check_consistency() untuk validasi.
# iPhone TIDAK BOLEH pakai Snapdragon, Android TIDAK BOLEH pakai Apple.
# ═══════════════════════════════════════════════════════════════
_APPLE_CHIPSETS = {
    "A10 Fusion", "A10X Fusion", "A11 Bionic", "A12 Bionic",
    "A12X Bionic", "A12Z Bionic", "A13 Bionic", "A14 Bionic",
    "A15 Bionic", "A16 Bionic", "A17 Pro", "A18", "A18 Pro", "A9", "M1",
    "M2",
}


_ANDROID_CHIPSETS = {
    "Dimensity 1080", "Dimensity 1100", "Dimensity 1300",
    "Dimensity 6020", "Dimensity 6080", "Dimensity 6100",
    "Dimensity 700", "Dimensity 7020", "Dimensity 7050",
    "Dimensity 7200", "Dimensity 800U", "Dimensity 810",
    "Dimensity 8100", "Dimensity 8200", "Dimensity 8300",
    "Dimensity 900", "Dimensity 9000", "Dimensity 920", "Dimensity 9200",
    "Dimensity 9300", "Exynos 1080", "Exynos 1280", "Exynos 1330",
    "Exynos 1380", "Exynos 1480", "Exynos 2100", "Exynos 2200",
    "Exynos 2400", "Exynos 7885", "Exynos 850", "Exynos 8895",
    "Exynos 9610", "Exynos 9611", "Exynos 9810", "Exynos 9820",
    "Exynos 9825", "Exynos 990", "Helio G25", "Helio G35", "Helio G36",
    "Helio G37", "Helio G80", "Helio G85", "Helio G88", "Helio G90",
    "Helio G95", "Helio G96", "Helio G99", "Helio P22", "Helio P22T",
    "Helio P35", "Helio P60", "Helio P60T", "Helio P70", "JLQ JR510",
    "Kirin 710", "Kirin 710A", "Kirin 810", "Kirin 9000", "Kirin 9000E",
    "Kirin 9000S", "Kirin 9010", "Kirin 970", "Kirin 980", "Kirin 985",
    "Kirin 990", "Snapdragon 429", "Snapdragon 450", "Snapdragon 480+",
    "Snapdragon 6 Gen 1", "Snapdragon 626", "Snapdragon 660",
    "Snapdragon 662", "Snapdragon 665", "Snapdragon 670",
    "Snapdragon 680", "Snapdragon 685", "Snapdragon 695",
    "Snapdragon 7 Gen 1", "Snapdragon 7 Gen 3", "Snapdragon 7+ Gen 2",
    "Snapdragon 720G", "Snapdragon 730", "Snapdragon 730G",
    "Snapdragon 732G", "Snapdragon 765G", "Snapdragon 778G",
    "Snapdragon 782G", "Snapdragon 7s Gen 2", "Snapdragon 8 Elite",
    "Snapdragon 8 Gen 1", "Snapdragon 8 Gen 2", "Snapdragon 8 Gen 3",
    "Snapdragon 8+ Gen 1", "Snapdragon 820", "Snapdragon 821",
    "Snapdragon 835", "Snapdragon 845", "Snapdragon 855",
    "Snapdragon 860", "Snapdragon 865", "Snapdragon 870",
    "Snapdragon 888", "Snapdragon 8s Gen 3", "Tensor G1", "Tensor G2",
    "Tensor G3", "Tensor G4", "Unisoc SC9863A", "Unisoc T606",
    "Unisoc T610", "Unisoc T612", "Unisoc T616", "Unisoc T618",
}


# RAM nyata → bucket navigator.deviceMemory (nearest power of 2, Chrome)
_RAM_TO_DEVICE_MEMORY = {3: 2, 4: 4, 6: 4, 8: 8, 12: 8, 16: 8}


# ═══════════════════════════════════════════════════════════════
# DEVICE PROFILES — data REAL per device, semua field KONSISTEN.
# viewport = CSS pixel (yang dilihat JS via window.innerWidth).
# physical = viewport * dpr (resolusi layar sebenarnya).
# ═══════════════════════════════════════════════════════════════

_IOS_PROFILES = [
    # ── iPhone 15 series (iOS 18) ──
    {
        "model": "iPhone 15 Pro Max",
        "os": "iOS 18.1",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 430, "height": 932},
        "dpr": 3.0, "cores": 6, "ram_gb": 8,
        "chipset": "A17 Pro", "platform_str": "iPhone", "browser": "safari",
    },
    {
        "model": "iPhone 15 Pro",
        "os": "iOS 18.1",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 393, "height": 852},
        "dpr": 3.0, "cores": 6, "ram_gb": 8,
        "chipset": "A17 Pro", "platform_str": "iPhone", "browser": "safari",
    },
    {
        "model": "iPhone 15",
        "os": "iOS 18.0",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 393, "height": 852},
        "dpr": 3.0, "cores": 6, "ram_gb": 6,
        "chipset": "A16 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    # ── iPhone 14 series (iOS 17) ──
    {
        "model": "iPhone 14 Pro Max",
        "os": "iOS 17.6.1",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_6_1 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 430, "height": 932},
        "dpr": 3.0, "cores": 6, "ram_gb": 6,
        "chipset": "A16 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    {
        "model": "iPhone 14 Pro",
        "os": "iOS 17.6",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 393, "height": 852},
        "dpr": 3.0, "cores": 6, "ram_gb": 6,
        "chipset": "A16 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    {
        "model": "iPhone 14",
        "os": "iOS 17.6.1",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_6_1 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 390, "height": 844},
        "dpr": 3.0, "cores": 6, "ram_gb": 6,
        "chipset": "A15 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    # ── iPhone 13 series (iOS 16/17) ──
    {
        "model": "iPhone 13 Pro Max",
        "os": "iOS 16.7",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 428, "height": 926},
        "dpr": 3.0, "cores": 6, "ram_gb": 6,
        "chipset": "A15 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    {
        "model": "iPhone 13 Pro",
        "os": "iOS 16.7",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 390, "height": 844},
        "dpr": 3.0, "cores": 6, "ram_gb": 6,
        "chipset": "A15 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    {
        "model": "iPhone 13",
        "os": "iOS 17.0",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0.6778.73 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 390, "height": 844},
        "dpr": 3.0, "cores": 6, "ram_gb": 4,
        "chipset": "A15 Bionic", "platform_str": "iPhone", "browser": "chrome_ios",
    },
    {
        "model": "iPhone 13 Mini",
        "os": "iOS 16.5",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 375, "height": 812},
        "dpr": 3.0, "cores": 6, "ram_gb": 4,
        "chipset": "A15 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    # ── iPhone 12 series (iOS 15/16) ──
    {
        "model": "iPhone 12 Pro Max",
        "os": "iOS 16.6",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 428, "height": 926},
        "dpr": 3.0, "cores": 6, "ram_gb": 6,
        "chipset": "A14 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    {
        "model": "iPhone 12",
        "os": "iOS 16.6",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 390, "height": 844},
        "dpr": 3.0, "cores": 6, "ram_gb": 4,
        "chipset": "A14 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    {
        "model": "iPhone 12 Mini",
        "os": "iOS 15.7",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 15_7 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6.1 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 375, "height": 812},
        "dpr": 3.0, "cores": 6, "ram_gb": 4,
        "chipset": "A14 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    # ── iPhone 11 series + X + SE (iOS 15/16/17) ──
    {
        "model": "iPhone 11 Pro Max",
        "os": "iOS 16.0",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 414, "height": 896},
        "dpr": 3.0, "cores": 6, "ram_gb": 4,
        "chipset": "A13 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    {
        "model": "iPhone 11",
        "os": "iOS 15.6",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 414, "height": 896},
        "dpr": 2.0, "cores": 6, "ram_gb": 4,
        "chipset": "A13 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    {
        "model": "iPhone X",
        "os": "iOS 17.0",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 375, "height": 812},
        "dpr": 3.0, "cores": 6, "ram_gb": 3,
        "chipset": "A11 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    {
        "model": "iPhone SE 2022",
        "os": "iOS 17.4",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 375, "height": 667},
        "dpr": 2.0, "cores": 6, "ram_gb": 4,
        "chipset": "A15 Bionic", "platform_str": "iPhone", "browser": "safari",
    },
    # ── BATCH-2: 7 iPhone baru dari database 416 ──
    {
        "model": "iPhone 16 Pro Max",
        "os": "iOS 18",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 18 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 430, "height": 934},
        "dpr": 3.0, "cores": 6, "ram_gb": 8,
        "chipset": "A18 Pro", "platform_str": "iPhone",
        "browser": "safari",
    },
    {
        "model": "iPhone 16 Pro",
        "os": "iOS 18",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 18 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 393, "height": 854},
        "dpr": 3.0, "cores": 6, "ram_gb": 8,
        "chipset": "A18 Pro", "platform_str": "iPhone",
        "browser": "safari",
    },
    {
        "model": "iPhone 16",
        "os": "iOS 18",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 18 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 393, "height": 852},
        "dpr": 3.0, "cores": 6, "ram_gb": 8,
        "chipset": "A18", "platform_str": "iPhone",
        "browser": "safari",
    },
    {
        "model": "iPhone XS Max",
        "os": "iOS 12",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 12 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 414, "height": 896},
        "dpr": 3.0, "cores": 6, "ram_gb": 4,
        "chipset": "A12 Bionic", "platform_str": "iPhone",
        "browser": "safari",
    },
    {
        "model": "iPhone XS",
        "os": "iOS 12",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 12 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 375, "height": 812},
        "dpr": 3.0, "cores": 6, "ram_gb": 4,
        "chipset": "A12 Bionic", "platform_str": "iPhone",
        "browser": "safari",
    },
    {
        "model": "iPhone XR",
        "os": "iOS 12",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 12 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 414, "height": 896},
        "dpr": 2.0, "cores": 6, "ram_gb": 3,
        "chipset": "A12 Bionic", "platform_str": "iPhone",
        "browser": "safari",
    },
    {
        "model": "iPhone 11 Pro",
        "os": "iOS 13",
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 13 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 375, "height": 812},
        "dpr": 3.0, "cores": 6, "ram_gb": 4,
        "chipset": "A13 Bionic", "platform_str": "iPhone",
        "browser": "safari",
    },
]

# iPad — tablet (device_type = "tablet")
_IPAD_PROFILES = [
    {
        "model": "iPad 9th gen",
        "os": "iPadOS 17.0",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 810, "height": 1080},
        "dpr": 2.0, "cores": 6, "ram_gb": 3,
        "chipset": "A13 Bionic", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad Air 4",
        "os": "iPadOS 16.0",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
               "Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 820, "height": 1180},
        "dpr": 2.0, "cores": 6, "ram_gb": 4,
        "chipset": "A14 Bionic", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    # ── BATCH-2: 17 iPad baru dari database 416 ──
    {
        "model": "iPad 5 (2017)",
        "os": "iPadOS 10.3.1",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 10_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/10.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 924, "height": 693},
        "dpr": 2.0, "cores": 6, "ram_gb": 2,
        "touch": 10,
        "chipset": "A9", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad 6 (2018)",
        "os": "iPadOS 11.3",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 11_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/11.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 924, "height": 693},
        "dpr": 2.0, "cores": 6, "ram_gb": 2,
        "touch": 10,
        "chipset": "A10 Fusion", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad 7 (2019)",
        "os": "iPadOS 13.1",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 13_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 924, "height": 693},
        "dpr": 2.0, "cores": 6, "ram_gb": 3,
        "touch": 10,
        "chipset": "A10 Fusion", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad 8 (2020)",
        "os": "iPadOS 14",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 14 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 924, "height": 693},
        "dpr": 2.0, "cores": 6, "ram_gb": 3,
        "touch": 10,
        "chipset": "A12 Bionic", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad 10 (2022)",
        "os": "iPadOS 16.1",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 820, "height": 1180},
        "dpr": 2.0, "cores": 6, "ram_gb": 4,
        "touch": 10,
        "chipset": "A14 Bionic", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad Pro 10.5 (2017)",
        "os": "iPadOS 10.3.2",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 10_3_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/10.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 820, "height": 1093},
        "dpr": 2.0, "cores": 6, "ram_gb": 4,
        "touch": 10,
        "chipset": "A10X Fusion", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad Pro 12.9 (2017)",
        "os": "iPadOS 10.3.2",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 10_3_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/10.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 924, "height": 693},
        "dpr": 2.0, "cores": 6, "ram_gb": 4,
        "touch": 10,
        "chipset": "A10X Fusion", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad Pro 11 (2018)",
        "os": "iPadOS 12",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 12 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 820, "height": 1174},
        "dpr": 2.0, "cores": 6, "ram_gb": 6,
        "touch": 10,
        "chipset": "A12X Bionic", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad Pro 11 (2020)",
        "os": "iPadOS 13.4",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 13_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 820, "height": 1174},
        "dpr": 2.0, "cores": 6, "ram_gb": 6,
        "touch": 10,
        "chipset": "A12Z Bionic", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad Pro 11 (2021)",
        "os": "iPadOS 14.5.1",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 14_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 820, "height": 1174},
        "dpr": 2.0, "cores": 6, "ram_gb": 16,
        "touch": 10,
        "chipset": "M1", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad Pro 11 (2022)",
        "os": "iPadOS 16.1",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 820, "height": 1174},
        "dpr": 2.0, "cores": 6, "ram_gb": 16,
        "touch": 10,
        "chipset": "M2", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad Pro 12.9 (2020)",
        "os": "iPadOS 13.4",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 13_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 924, "height": 1233},
        "dpr": 2.0, "cores": 6, "ram_gb": 6,
        "touch": 10,
        "chipset": "A12Z Bionic", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad Pro 12.9 (2021)",
        "os": "iPadOS 14.5.1",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 14_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 924, "height": 1233},
        "dpr": 2.0, "cores": 6, "ram_gb": 16,
        "touch": 10,
        "chipset": "M1", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad Air 3 (2019)",
        "os": "iPadOS 12.2",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 820, "height": 1093},
        "dpr": 2.0, "cores": 6, "ram_gb": 3,
        "touch": 10,
        "chipset": "A12 Bionic", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad Air 5 (2022)",
        "os": "iPadOS 15.4",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 15_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 820, "height": 1180},
        "dpr": 2.0, "cores": 6, "ram_gb": 8,
        "touch": 10,
        "chipset": "M1", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad mini 5 (2019)",
        "os": "iPadOS 12.2",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 924, "height": 693},
        "dpr": 2.0, "cores": 6, "ram_gb": 3,
        "touch": 10,
        "chipset": "A12 Bionic", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
    {
        "model": "iPad mini 6 (2021)",
        "os": "iPadOS 15",
        "ua": ("Mozilla/5.0 (iPad; CPU OS 15 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"),
        "viewport": {"width": 744, "height": 1133},
        "dpr": 2.0, "cores": 6, "ram_gb": 4,
        "touch": 10,
        "chipset": "A15 Bionic", "platform_str": "iPad",
        "browser": "safari", "device_type": "tablet",
    },
]

_ANDROID_PROFILES = [
    # ── Pixel (Tensor) ──
    {
        "model": "Pixel 8 Pro",
        "os": "Android 15",
        "ua": ("Mozilla/5.0 (Linux; Android 15; Pixel 8 Pro) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 892},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Tensor G3", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Pixel 8",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 915},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Tensor G3", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Pixel 7",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 915},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Tensor G2", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Pixel 6",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 915},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Tensor G1", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    # ── Samsung Galaxy S (Snapdragon flagship) ──
    {
        "model": "Galaxy S24 Ultra",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 915},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Galaxy S23",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 780},
        "dpr": 3.0, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Galaxy S22",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 780},
        "dpr": 3.0, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    # ── Samsung Fold / Flip ──
    {
        "model": "Galaxy Z Fold 5",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; SM-F946B) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 384, "height": 832},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Galaxy Z Flip 5",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; SM-F731B) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 780},
        "dpr": 3.0, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    # ── Samsung Galaxy A (mid-range: Exynos / Snapdragon) ──
    {
        "model": "Galaxy A54",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.75, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 1380", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Galaxy A53",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; SM-A536B) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Exynos 1280", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Galaxy A52",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; SM-A525F) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 720G", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    # ── Xiaomi Redmi Note (Indonesia best-seller) ──
    {
        "model": "Redmi Note 13",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; 2312DRA50G) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Redmi Note 12",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; 22111317G) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Redmi Note 11",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Redmi Note 11) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Redmi Note 10",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Redmi Note 10) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Snapdragon 665", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    # ── Realme (Indonesia) ──
    {
        "model": "Realme 11 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; RMX3771) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 7050", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Realme C55",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; RMX3710) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G88", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    # ── Infinix (Indonesia) ──
    {
        "model": "Infinix Note 30",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; X6716B) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G99", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Infinix Hot 30",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; X6831) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Helio G88", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    # ── OPPO (Indonesia) ──
    {
        "model": "OPPO Reno 10",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; CPH2531) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.75, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 7050", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "OPPO A78",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; CPH2565) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    # ADOPSI GLM 2026-11-05 (RND-GLM53): OPPO A78 5G (CPH2483/CPH2495) —
    # varian 5G dari A78, BUKAN A78 4G (CPH2565) di atas. Laporan GLM
    # menyebut "OPPO A78 (CPH2495)" tanpa membedakan varian — kode itu
    # milik 5G (Dimensity 700, Mali-G57, LCD 6.56" 1612x720).
    # Sumber: GSMArena (Models CPH2483, CPH2495), OPPO specs.
    # Viewport 360x800 @2.0 = turunan dari 720/2.0 (bukan dari spec sheet).
    {
        "model": "OPPO A78 5G",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; CPH2495) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 700", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    # ── Vivo (Indonesia) ──
    {
        "model": "Vivo Y36",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; V2247) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Vivo V27",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; V2231) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.75, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 8200", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    # ── OnePlus ──
    {
        "model": "OnePlus 11",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; CPH2449) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 915},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "OnePlus Nord 3",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; CPH2493) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 8200", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    # ── BATCH-2: 314 Android baru dari database 416 ──
    {
        "model": "Galaxy S24+",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Galaxy S24) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 932},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S24",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Galaxy S24) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 2400", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S23 Ultra",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy S23 Ultra) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 922},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S22 Ultra",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy S22 Ultra) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 922},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A55",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Galaxy A55) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Exynos 1480", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A34",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy A34) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 1080", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A14",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy A14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 919},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Exynos 1330", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy M34",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy M34) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 1280", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Xiaomi 14",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Xiaomi 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 393, "height": 874},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Xiaomi 13",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Xiaomi 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    # ADOPSI GLM 2026-11-05 (RND-GLM53): Redmi Note 13 Pro 4G — model yang
    # disebut laporan GLM tapi belum ada di DB ini (yang ada: Note 13, Pro+,
    # Pro 5G). Spek terverifikasi via pencarian web 2026-11-05:
    # Helio G99 Ultra, Mali-G57 MC2, AMOLED 6.67" 1080x2400 120Hz, 8GB RAM,
    # Android 13, Jan 2024 (priceinkenya/phonebunch).
    # KOREKSI PENTING: BUKAN Snapdragon 732G — itu milik Note 10 Pro/Note 12
    # Pro 4G. Viewport 412x916 @2.625 = konvensi DB ini untuk 1080x2400
    # (412x2.625=1081, 916x2.625=2404). UA pakai nama marketing (konvensi
    # seri Pro di DB ini) — kode model 2312DRA50G TIDAK dicantumkan karena
    # belum terverifikasi dari sumber yang dibaca.
    {
        "model": "Redmi Note 13 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi Note 13 Pro) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G99 Ultra", "platform_str": "Linux armv8l", "browser": "chrome",
    },
    {
        "model": "Redmi Note 13 Pro+",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi Note 13 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 7200", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 13 Pro (5G)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi Note 13 Pro 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 7s Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 13 Pro (4G)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi Note 13 Pro 4G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 13 (5G)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi Note 13 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 6080", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 13 (4G)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi Note 13 4G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 685", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 12 Pro",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Redmi Note 12 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 1080", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi 13C",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi 13C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G85", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi 12",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G88", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO X6 Pro",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; POCO X6 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 8300", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO X6",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; POCO X6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 7s Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO F5",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; POCO F5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 7+ Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO M6 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; POCO M6 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Find X7 Ultra",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Find X7 Ultra) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 946},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Reno 11 Pro",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Reno 11 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 920},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 8200", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Reno 10 Pro+ (China)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Reno 10 Pro China) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 414, "height": 925},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8+ Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Reno 10 Pro (China)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Reno 10 Pro China) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 414, "height": 925},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Dimensity 8200", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Reno 10 Pro (Global)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Reno 10 Pro Global) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 358},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Reno 10 (China)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Reno 10 China) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 358},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Reno 8 Pro",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Reno 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 920},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 8100", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "A78 (4G)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; A78 4G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "A78 (5G)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; A78 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 700", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "A58",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; A58) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G85", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "X100 Pro",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; X100 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 414, "height": 920},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Dimensity 9300", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "V30",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; V30) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 414, "height": 920},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 7 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "V29",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; V29) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 414, "height": 920},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "V27",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; V27) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 7200", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Y36 (4G)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Y36 4G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 911},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Y36 (5G)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Y36 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 911},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 6020", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Y27",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Y27) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 911},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G85", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Y17s",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Y17s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G85", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "GT 5 Pro",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; GT 5 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 428, "height": 941},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "12 Pro+",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; 12 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 920},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 7s Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "11 Pro+",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; 11 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 920},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 7050", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "11 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; 11 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 920},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 7050", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "C67",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; C67) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 685", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "C55",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; C55) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G88", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "C53",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; C53) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Unisoc T612", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Note 40 Pro",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Note 40 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 929},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Note 30 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Note 30 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Note 30",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Note 30) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Hot 40 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Hot 40 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Hot 40i",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Hot 40i) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Unisoc T606", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Hot 30",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Hot 30) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G88", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 9 Pro XL",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 957},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Tensor G4", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 9 Pro",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 1034},
        "dpr": 2.0, "cores": 8, "ram_gb": 16,
        "chipset": "Tensor G4", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 8a",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Pixel 8a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Tensor G3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 7 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 932},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Tensor G2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 6 Pro",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Pixel 6 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 932},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Tensor G1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OnePlus 12",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; OnePlus 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 946},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OnePlus Nord CE 3",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; OnePlus Nord CE 3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 920},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 782G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Z Fold 6",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Galaxy Z Fold 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 931},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Z Fold 4",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy Z Fold 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 516},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8+ Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Z Fold 3",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Galaxy Z Fold 3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 537},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Z Flip 6",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Galaxy Z Flip 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 1007},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Z Flip 4",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy Z Flip 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 1007},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 8+ Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Z Flip 3",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Galaxy Z Flip 3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 1007},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OnePlus Open",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; OnePlus Open) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 861},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor Magic V2",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Honor Magic V2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 870},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor Magic Vs2",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Honor Magic Vs2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 736},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Vivo X Fold 3",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Vivo X Fold 3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 902},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Xiaomi Mix Fold 3",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Xiaomi Mix Fold 3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 902},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO Find N3",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; OPPO Find N3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 861},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO Find N3 Flip",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; OPPO Find N3 Flip) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 961},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 9200", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO Find N2 Flip",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; OPPO Find N2 Flip) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 961},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Dimensity 9000", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "ASUS ROG Phone 8 Pro",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; ASUS ROG Phone 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 24,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "ASUS ROG Phone 7",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; ASUS ROG Phone 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 934},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Nubia Red Magic 9 Pro",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Nubia Red Magic 9 Pr) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 428, "height": 951},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Nubia Red Magic 8 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Nubia Red Magic 8 Pr) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 428, "height": 951},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Black Shark 5 Pro",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Black Shark 5 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Black Shark 5",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Black Shark 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 870", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Black Shark 4 Pro",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Black Shark 4 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 870", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S20",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy S20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 956},
        "dpr": 3.0, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 990", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S21 Ultra",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Galaxy S21 Ultra) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 956},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Exynos 2100", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 5",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 765G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 5a",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Pixel 5a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 765G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 4a",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Pixel 4a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 730G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A05s",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy A05s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A05",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy A05) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G85", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A04",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy A04) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Helio P35", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A04s",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy A04s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Exynos 850", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi A3",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi A3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G36", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi A2",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi A2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 3,
        "chipset": "Helio G36", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi A2+",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi A2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 3,
        "chipset": "Helio G36", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Infinix Smart 8",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Infinix Smart 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Helio G36", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Infinix Smart 8 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Infinix Smart 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G36", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Tecno Spark 20",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Tecno Spark 20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G85", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Tecno Spark 20 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Tecno Spark 20 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Tecno Spark 10",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Tecno Spark 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G37", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Tecno Spark 10 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Tecno Spark 10 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G88", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Tecno Spark Go 2024",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Tecno Spark Go 2024) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Unisoc T606", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Itel S23",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Itel S23) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Unisoc T606", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Itel S23+",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Itel S23) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Unisoc T616", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Itel P55",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Itel P55) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Unisoc T606", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Tecno Camon 20 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Tecno Camon 20 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Nokia G42 5G",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Nokia G42 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 480+", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Nokia C32",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Nokia C32) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Unisoc SC9863A", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Motorola Moto G84",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Motorola Moto G84) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 695", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Motorola Moto G54",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Motorola Moto G54) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 7020", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Motorola Moto G34",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Motorola Moto G34) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 695", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Sony Xperia 1 V",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Sony Xperia 1 V) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 1004},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Sony Xperia 10 V",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Sony Xperia 10 V) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 961},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 695", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S8",
        "os": "Android 7.0",
        "ua": ("Mozilla/5.0 (Linux; Android 7.0; Galaxy S8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 884},
        "dpr": 3.0, "cores": 8, "ram_gb": 4,
        "chipset": "Exynos 8895", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S8+",
        "os": "Android 7.0",
        "ua": ("Mozilla/5.0 (Linux; Android 7.0; Galaxy S8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 884},
        "dpr": 3.0, "cores": 8, "ram_gb": 4,
        "chipset": "Exynos 8895", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S9",
        "os": "Android 8.0",
        "ua": ("Mozilla/5.0 (Linux; Android 8.0; Galaxy S9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 884},
        "dpr": 3.0, "cores": 8, "ram_gb": 4,
        "chipset": "Exynos 9810", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S9+",
        "os": "Android 8.0",
        "ua": ("Mozilla/5.0 (Linux; Android 8.0; Galaxy S9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 884},
        "dpr": 3.0, "cores": 8, "ram_gb": 6,
        "chipset": "Exynos 9810", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S10e",
        "os": "Android 9.0",
        "ua": ("Mozilla/5.0 (Linux; Android 9.0; Galaxy S10e) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 870},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 9820", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S10",
        "os": "Android 9.0",
        "ua": ("Mozilla/5.0 (Linux; Android 9.0; Galaxy S10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 908},
        "dpr": 3.0, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 9820", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S10+",
        "os": "Android 9.0",
        "ua": ("Mozilla/5.0 (Linux; Android 9.0; Galaxy S10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 908},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Exynos 9820", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S20+",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy S20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 956},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Exynos 990", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S20 Ultra",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy S20 Ultra) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 956},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Exynos 990", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S21",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Galaxy S21) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 2100", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S21+",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Galaxy S21) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 2100", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy S21 FE",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy S21 FE) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Note 8",
        "os": "Android 7.0",
        "ua": ("Mozilla/5.0 (Linux; Android 7.0; Galaxy Note 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 884},
        "dpr": 3.0, "cores": 8, "ram_gb": 6,
        "chipset": "Exynos 8895", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Note 9",
        "os": "Android 8.0",
        "ua": ("Mozilla/5.0 (Linux; Android 8.0; Galaxy Note 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 884},
        "dpr": 3.0, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 9810", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Note 10",
        "os": "Android 9.0",
        "ua": ("Mozilla/5.0 (Linux; Android 9.0; Galaxy Note 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 870},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 9825", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Note 10+",
        "os": "Android 9.0",
        "ua": ("Mozilla/5.0 (Linux; Android 9.0; Galaxy Note 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 908},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Exynos 9825", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Note 20",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy Note 20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 990", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy Note 20 Ultra",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy Note 20 Ultra) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 922},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Exynos 990", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A8 (2018)",
        "os": "Android 7.1.1",
        "ua": ("Mozilla/5.0 (Linux; Android 7.1.1; Galaxy A8 2018) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 847},
        "dpr": 2.625, "cores": 8, "ram_gb": 4,
        "chipset": "Exynos 7885", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A6+ (2018)",
        "os": "Android 8.0",
        "ua": ("Mozilla/5.0 (Linux; Android 8.0; Galaxy A6 2018) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 847},
        "dpr": 2.625, "cores": 8, "ram_gb": 4,
        "chipset": "Snapdragon 450", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A7 (2018)",
        "os": "Android 8.0",
        "ua": ("Mozilla/5.0 (Linux; Android 8.0; Galaxy A7 2018) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 847},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Exynos 7885", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A50",
        "os": "Android 9.0",
        "ua": ("Mozilla/5.0 (Linux; Android 9.0; Galaxy A50) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Exynos 9610", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A51",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy A51) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 9611", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A71",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy A71) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 730", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A72",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Galaxy A72) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 720G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A33 5G",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy A33 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 1280", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A13",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy A13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 919},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Exynos 850", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A23",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy A23) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 919},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A24",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy A24) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A15",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Galaxy A15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A25 5G",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Galaxy A25 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 1280", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A12",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy A12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Exynos 850", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy A04e",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy A04e) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Helio P35", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy M12",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Galaxy M12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Exynos 850", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy M21",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy M21) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Exynos 9611", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy M51",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy M51) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 730G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy M52 5G",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Galaxy M52 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy M53 5G",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy M53 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 900", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Galaxy M54 5G",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy M54 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Exynos 1380", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei P20",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Huawei P20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 855},
        "dpr": 2.625, "cores": 8, "ram_gb": 4,
        "chipset": "Kirin 970", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei P20 Pro",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Huawei P20 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 855},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Kirin 970", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei P30",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Huawei P30) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 980", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei P30 Pro",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Huawei P30 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 980", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei P40",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Huawei P40) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 990", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei P40 Pro",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Huawei P40 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 393, "height": 865},
        "dpr": 3.0, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 990", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Mate 20",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Huawei Mate 20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 856},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 980", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Mate 20 Pro",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Huawei Mate 20 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 932},
        "dpr": 3.0, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 980", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Mate 30",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Huawei Mate 30) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 990", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Mate 30 Pro",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Huawei Mate 30 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 878},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 990", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Mate 40 Pro",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Huawei Mate 40 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 887},
        "dpr": 3.0, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 9000", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Nova 5T",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Huawei Nova 5T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 980", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Nova 7",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Huawei Nova 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 985", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Nova 9",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei Nova 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Nova 10",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei Nova 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Nova 11",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei Nova 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 917},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Pura 70",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei Pura 70) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 414, "height": 910},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Kirin 9010", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Pura 70 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei Pura 70 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 414, "height": 934},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Kirin 9010", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Mate X3",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei Mate X3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 898},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8+ Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Nova Y61",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Huawei Nova Y61) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 710", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Nova Y91",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei Nova Y91) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 906},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Huawei Enjoy 60",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei Enjoy 60) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 710A", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor 8X",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Honor 8X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Kirin 710", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor 9X",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Honor 9X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 810", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor View 20",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Honor View 20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 881},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Kirin 980", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor 50",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Honor 50) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor 50 Lite",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Honor 50 Lite) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 906},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 662", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor 70",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Honor 70) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor 90",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Honor 90) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 393, "height": 872},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 7 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor 90 Lite",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Honor 90 Lite) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 911},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 6020", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor Magic 5 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Honor Magic 5 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 933},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor Magic 6 Pro",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Honor Magic 6 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 428, "height": 936},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor X8",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Honor X8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 911},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor X9a",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Honor X9a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 695", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor X9b",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Honor X9b) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 896},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 6 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor 200",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Honor 200) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 393, "height": 872},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 7 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor 200 Pro",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Honor 200 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 909},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8s Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Honor Magic Vs",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Honor Magic Vs) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 916},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8+ Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Mi 8",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Mi 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 858},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 845", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Mi 8 Lite",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Mi 8 Lite) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 870},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 660", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Mi 9",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Mi 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 855", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Mi 9T",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Mi 9T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 730", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Mi 10",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Mi 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 865", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Mi 10T",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Mi 10T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 865", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Mi 10T Pro",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Mi 10T Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 865", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Mi 11",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Mi 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 956},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Mi 11 Lite",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Mi 11 Lite) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 732G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Xiaomi 12",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Xiaomi 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Xiaomi 12 Lite",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Xiaomi 12 Lite) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Xiaomi 12T",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Xiaomi 12T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 3.0, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 8100", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Xiaomi 13T",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Xiaomi 13T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 8200", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Xiaomi 13T Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Xiaomi 13T Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Dimensity 9200", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 7",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Redmi Note 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 660", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 8",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Redmi Note 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 665", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 8 Pro",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Redmi Note 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G90", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 9",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Redmi Note 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G85", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 9 Pro",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Redmi Note 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 720G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 10S",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Redmi Note 10S) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G95", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 10 Pro",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Redmi Note 10 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 732G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 11 Pro",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Redmi Note 11 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G96", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 12 Pro+",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Redmi Note 12 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 1080", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi Note 12 Turbo",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi Note 12 Turbo) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 7+ Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi 9",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Redmi 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G80", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi 9A",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Redmi 9A) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G25", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi 9C",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Redmi 9C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Helio G35", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi 10",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Redmi 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G88", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi 10A",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Redmi 10A) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G25", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi 10C",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Redmi 10C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 825},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi 12C",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Redmi 12C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 825},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G85", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Redmi K40",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Redmi K40) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 870", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pocophone F1",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Pocophone F1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 857},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 845", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO F2 Pro",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; POCO F2 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 865", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO F3",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; POCO F3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 870", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO F4",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; POCO F4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 870", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO F4 GT",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; POCO F4 GT) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO X3 NFC",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; POCO X3 NFC) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 732G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO X3 Pro",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; POCO X3 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 860", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO X3 GT",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; POCO X3 GT) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 1100", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO X4 GT",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; POCO X4 GT) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 8100", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO X4 Pro 5G",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; POCO X4 Pro 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 695", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO X5",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; POCO X5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 695", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO X5 Pro",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; POCO X5 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO M3",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; POCO M3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 662", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO M4 Pro",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; POCO M4 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G96", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO M5",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; POCO M5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 919},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO C40",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; POCO C40) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 825},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "JLQ JR510", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO C55",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; POCO C55) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 825},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Helio G85", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "POCO C65",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; POCO C65) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G85", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO F7",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; OPPO F7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 870},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Helio P60", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO F9",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; OPPO F9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Helio P60", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO F11",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; OPPO F11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Helio P70", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO Reno2",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; OPPO Reno2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 730G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO Reno5 4G",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; OPPO Reno5 4G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 720G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO Reno6 5G",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; OPPO Reno6 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 900", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO Reno8 (China)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; OPPO Reno8 China) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 1300", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO Find X2 Pro",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; OPPO Find X2 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 946},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 865", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO Find X5 Pro",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; OPPO Find X5 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 960},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO A3s",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; OPPO A3s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 760},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Snapdragon 450", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO A16",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; OPPO A16) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Helio G35", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO A57 (2022)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; OPPO A57 2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 806},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Helio G35", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OPPO A96",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; OPPO A96) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 920},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Vivo V9",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Vivo V9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 870},
        "dpr": 2.625, "cores": 8, "ram_gb": 4,
        "chipset": "Snapdragon 626", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Vivo V11",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Vivo V11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 660", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Vivo V15",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Vivo V15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Helio P70", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Vivo V20",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Vivo V20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 720G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Vivo V21 5G",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Vivo V21 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 800U", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Vivo V23 5G",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Vivo V23 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 920", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Vivo X60 (China)",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Vivo X60 China) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 906},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Exynos 1080", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Vivo Y21 (2021)",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Vivo Y21 2021) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Helio P35", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "iQOO 7 5G (India)",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; iQOO 7 5G India) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 870", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "iQOO 9 5G (India)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; iQOO 9 5G India) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 906},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "iQOO 11 5G",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; iQOO 11 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 956},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "iQOO 12 5G",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; iQOO 12 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 414, "height": 920},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "iQOO Neo 7 (China)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; iQOO Neo 7 China) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 9000", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "iQOO Z9 (China)",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; iQOO Z9 China) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 414, "height": 920},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 7 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Realme 6",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Realme 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G90", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Realme 7 Pro",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Realme 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 720G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Realme 8 Pro",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Realme 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 720G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Realme 9 Pro+",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Realme 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 920", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Realme 10 (4G)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Realme 10 4G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Realme 10 Pro+",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Realme 10 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 920},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 1080", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Realme GT Master Edition",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Realme GT Master Edi) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 778G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Realme GT 2 5G",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Realme GT 2 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Realme C21",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Realme C21) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "chipset": "Helio G35", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Realme 12 5G",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Realme 12 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Dimensity 6100", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 3",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Pixel 3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 824},
        "dpr": 2.625, "cores": 8, "ram_gb": 4,
        "chipset": "Snapdragon 845", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 4",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 870},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 855", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 4a 5G",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Pixel 4a 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 765G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 6a",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Pixel 6a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 6,
        "chipset": "Tensor G1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 7a",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Pixel 7a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Tensor G2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 9",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 925},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Tensor G4", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Pixel 9 Pro Fold",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro Fold) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 800, "height": 829},
        "dpr": 3.0, "cores": 8, "ram_gb": 16,
        "chipset": "Tensor G4", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OnePlus 6T",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; OnePlus 6T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 845", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OnePlus 7 Pro",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; OnePlus 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 932},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 855", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OnePlus 9 Pro",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; OnePlus 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 960},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OnePlus Nord",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; OnePlus Nord) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 765G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "OnePlus 10 Pro",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; OnePlus 10 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 960},
        "dpr": 3.0, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "ZenFone 8",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; ZenFone 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "ZenFone 10",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; ZenFone 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "ROG Phone 5",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; ROG Phone 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 934},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "ROG Phone 9",
        "os": "Android 15",
        "ua": ("Mozilla/5.0 (Linux; Android 15; ROG Phone 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Elite", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Xperia 1 II",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Xperia 1 II) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 1004},
        "dpr": 3.0, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 865", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Xperia 5 III",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Xperia 5 III) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 961},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Xperia 1 VI",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Xperia 1 VI) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 3", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Nokia 7 Plus",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Nokia 7 Plus) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 824},
        "dpr": 2.625, "cores": 8, "ram_gb": 4,
        "chipset": "Snapdragon 660", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "LG G6",
        "os": "Android 7.0",
        "ua": ("Mozilla/5.0 (Linux; Android 7.0; LG G6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 860},
        "dpr": 3.0, "cores": 8, "ram_gb": 4,
        "chipset": "Snapdragon 821", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "LG Wing 5G",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; LG Wing 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 765G", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "HTC U12+",
        "os": "Android 8.0",
        "ua": ("Mozilla/5.0 (Linux; Android 8.0; HTC U12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 860},
        "dpr": 3.0, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 845", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Lenovo Legion Phone Duel 2",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Lenovo Legion Phone) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Lenovo Legion Y90",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Lenovo Legion Y90) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 938},
        "dpr": 2.625, "cores": 8, "ram_gb": 18,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Nothing Phone (2a)",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Nothing Phone 2a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 920},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Dimensity 7200", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Meizu 16th",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Meizu 16th) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 824},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 845", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Meizu 17",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Meizu 17) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 865", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Meizu 20",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Meizu 20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "ZTE Axon 10 Pro",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; ZTE Axon 10 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 12,
        "chipset": "Snapdragon 855", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "ZTE Axon 40 Ultra",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; ZTE Axon 40 Ultra) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 428, "height": 951},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Nubia Z50",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Nubia Z50) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 916},
        "dpr": 2.625, "cores": 8, "ram_gb": 16,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Sharp Aquos R3",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Sharp Aquos R3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 430, "height": 932},
        "dpr": 3.0, "cores": 8, "ram_gb": 6,
        "chipset": "Snapdragon 855", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Sharp Aquos R8s",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Sharp Aquos R8s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 412, "height": 893},
        "dpr": 2.625, "cores": 8, "ram_gb": 8,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Advan G9 Pro",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Advan G9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 800},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Unisoc SC9863A", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Advan GX",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Advan GX) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 360, "height": 820},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "chipset": "Unisoc T618", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Evercoss Xtream 1",
        "os": "Android 7.0",
        "ua": ("Mozilla/5.0 (Linux; Android 7.0; Evercoss Xtream 1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 320, "height": 569},
        "dpr": 1.5, "cores": 8, "ram_gb": 1,
        "chipset": "Unisoc SC9863A", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Nokia T20 (2021)",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Nokia T20 2021) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 393, "height": 655},
        "dpr": 3.0, "cores": 8, "ram_gb": 4,
        "chipset": "Unisoc T610", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
    {
        "model": "Nokia T21 (2022)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Nokia T21 2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"),
        "viewport": {"width": 393, "height": 655},
        "dpr": 3.0, "cores": 8, "ram_gb": 4,
        "chipset": "Unisoc T612", "platform_str": "Linux armv8l",
        "browser": "chrome",
    },
]


# ═══════════════════════════════════════════════════════════════
# ANDROID TABLETS — device_type = "tablet".
# UA tablet TIDAK mengandung token "Mobile" (sinyal tablet ke Google!).
# Viewport = CSS pixel portrait; physical = viewport × dpr = resolusi asli.
# ═══════════════════════════════════════════════════════════════
_ANDROID_TABLET_PROFILES = [
    # ── Samsung Galaxy Tab S9 series (Android 14) ──
    {
        "model": "Galaxy Tab S9 Ultra",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; SM-X910) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 1480},
        "dpr": 2.0, "cores": 8, "ram_gb": 12, "touch": 10,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S9+",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; SM-X810) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 876, "height": 1400},
        "dpr": 2.0, "cores": 8, "ram_gb": 12, "touch": 10,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S9",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 8, "touch": 10,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    # ── Samsung Galaxy Tab S8 series (Android 13) ──
    {
        "model": "Galaxy Tab S8 Ultra",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; SM-X900) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 1480},
        "dpr": 2.0, "cores": 8, "ram_gb": 8, "touch": 10,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S8+",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; SM-X800) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"),
        "viewport": {"width": 876, "height": 1400},
        "dpr": 2.0, "cores": 8, "ram_gb": 8, "touch": 10,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S8",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; SM-X700) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 8, "touch": 10,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    # ── Samsung Galaxy Tab A series (mid/low) ──
    {
        "model": "Galaxy Tab A9+",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; SM-X210) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 1.5, "cores": 8, "ram_gb": 8, "touch": 10,
        "chipset": "Snapdragon 695", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab A8",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; SM-X200) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 1.5, "cores": 8, "ram_gb": 4, "touch": 10,
        "chipset": "Unisoc T618", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    # ── Xiaomi Pad ──
    {
        "model": "Xiaomi Pad 6",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; 23043RP34G) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 900, "height": 1440},
        "dpr": 2.0, "cores": 8, "ram_gb": 6, "touch": 10,
        "chipset": "Snapdragon 870", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Xiaomi Pad 6 Pro",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; 23043RP34C) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 900, "height": 1440},
        "dpr": 2.0, "cores": 8, "ram_gb": 8, "touch": 10,
        "chipset": "Snapdragon 8+ Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Xiaomi Pad 5",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; 21051182G) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 6, "touch": 10,
        "chipset": "Snapdragon 860", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    # ── Lenovo Tab ──
    {
        "model": "Lenovo Tab P12",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; TB370FU) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 920, "height": 1472},
        "dpr": 2.0, "cores": 8, "ram_gb": 8, "touch": 10,
        "chipset": "Dimensity 7050", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Lenovo Tab P11 2nd Gen",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; TB350FU) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 4, "touch": 10,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    # ── Realme Pad ──
    {
        "model": "Realme Pad 2",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; RMP2204) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 8, "touch": 10,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Realme Pad",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; RMP2102) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 4, "touch": 10,
        "chipset": "Helio G80", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    # ── Huawei MatePad ──
    {
        "model": "Huawei MatePad 11.5",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; BTK-W09) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 720, "height": 1100},
        "dpr": 2.0, "cores": 8, "ram_gb": 8, "touch": 10,
        "chipset": "Snapdragon 7 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Huawei MatePad Pro 13.2",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; PCE-W10) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 960, "height": 1440},
        "dpr": 2.0, "cores": 8, "ram_gb": 12, "touch": 10,
        "chipset": "Kirin 9000S", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    # ── Honor Pad ──
    {
        "model": "Honor Pad 9",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; ROL-W00) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 8, "touch": 10,
        "chipset": "Snapdragon 6 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Honor Pad X9",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; ELN-W09) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 4, "touch": 10,
        "chipset": "Snapdragon 685", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    # ── Nokia / TCL ──
    {
        "model": "Nokia T21",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; TA-1487) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 4, "touch": 10,
        "chipset": "Unisoc T612", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "TCL Tab 11",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; 9166G) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 1.5, "cores": 8, "ram_gb": 4, "touch": 10,
        "chipset": "Helio P22T", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "TCL NXTPAPER 11",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; 9466X) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 4, "touch": 10,
        "chipset": "Helio P60T", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    # ── BATCH-2: 46 tablet Android baru dari database 416 ──
    {
        "model": "Galaxy Tab S3 (2017)",
        "os": "Android 7.0",
        "ua": ("Mozilla/5.0 (Linux; Android 7.0; Galaxy Tab S3 2017) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 1232},
        "dpr": 1.5, "cores": 8, "ram_gb": 4,
        "touch": 10,
        "chipset": "Snapdragon 820", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S4 (2018)",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Galaxy Tab S4 2018) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "touch": 10,
        "chipset": "Snapdragon 835", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S5e (2019)",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Galaxy Tab S5e 2019) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "touch": 10,
        "chipset": "Snapdragon 670", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S6 (2019)",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Galaxy Tab S6 2019) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Snapdragon 855", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S6 Lite (2020)",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy Tab S6 Lite 2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 4,
        "touch": 10,
        "chipset": "Exynos 9611", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S7 (2020)",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy Tab S7 2020) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Snapdragon 865", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S7+ (2020)",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy Tab S7 2020) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 876, "height": 1400},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Snapdragon 865", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S8 (2022)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy Tab S8 2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 12,
        "touch": 10,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S8+ (2022)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy Tab S8 2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        "viewport": {"width": 876, "height": 1400},
        "dpr": 2.0, "cores": 8, "ram_gb": 16,
        "touch": 10,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S8 Ultra (2022)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Galaxy Tab S8 Ultra) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 1480},
        "dpr": 2.0, "cores": 8, "ram_gb": 16,
        "touch": 10,
        "chipset": "Snapdragon 8 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S9 (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy Tab S9 2023) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 12,
        "touch": 10,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S9+ (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy Tab S9 2023) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 876, "height": 1400},
        "dpr": 2.0, "cores": 8, "ram_gb": 12,
        "touch": 10,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab S9 Ultra (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy Tab S9 Ultra) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 1480},
        "dpr": 2.0, "cores": 8, "ram_gb": 16,
        "touch": 10,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab A 8.0 (2019)",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Galaxy Tab A 80 2019) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"),
        "viewport": {"width": 430, "height": 688},
        "dpr": 1.5, "cores": 8, "ram_gb": 2,
        "touch": 10,
        "chipset": "Snapdragon 429", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab A7 (2020)",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Galaxy Tab A7 2020) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 4,
        "touch": 10,
        "chipset": "Snapdragon 662", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab A8 (2022)",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Galaxy Tab A8 2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 1.5, "cores": 8, "ram_gb": 4,
        "touch": 10,
        "chipset": "Unisoc T618", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab A9 (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy Tab A9 2023) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 430, "height": 720},
        "dpr": 1.5, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Galaxy Tab A9+ (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Galaxy Tab A9 2023) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 578},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Snapdragon 695", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Mi Pad 4 (2018)",
        "os": "Android 8.1",
        "ua": ("Mozilla/5.0 (Linux; Android 8.1; Mi Pad 4 2018) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 1.5, "cores": 8, "ram_gb": 4,
        "touch": 10,
        "chipset": "Snapdragon 660", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Xiaomi Pad 5 (2021)",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Xiaomi Pad 5 2021) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "touch": 10,
        "chipset": "Snapdragon 860", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Xiaomi Pad 6 (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Xiaomi Pad 6 2023) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 900, "height": 1440},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Snapdragon 870", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Xiaomi Pad 6S Pro (2024)",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Xiaomi Pad 6S Pro 20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 1386},
        "dpr": 2.0, "cores": 8, "ram_gb": 16,
        "touch": 10,
        "chipset": "Snapdragon 8 Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Redmi Pad (2022)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Redmi Pad 2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 6,
        "touch": 10,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Redmi Pad SE (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Redmi Pad SE 2023) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 1.5, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "POCO Pad (2024)",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; POCO Pad 2024) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Snapdragon 7s Gen 2", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Lenovo Tab M10 (2019)",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Lenovo Tab M10 2019) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"),
        "viewport": {"width": 876, "height": 548},
        "dpr": 1.5, "cores": 8, "ram_gb": 3,
        "touch": 10,
        "chipset": "Snapdragon 429", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Lenovo Tab M10 Plus (2020)",
        "os": "Android 9",
        "ua": ("Mozilla/5.0 (Linux; Android 9; Lenovo Tab M10 Plus) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 578},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "touch": 10,
        "chipset": "Helio P22", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Lenovo Tab M11 (2024)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Lenovo Tab M11 2024) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 578},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Helio G88", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Lenovo Tab P11 (2021)",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Lenovo Tab P11 2021) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 554},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "touch": 10,
        "chipset": "Snapdragon 662", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Lenovo Tab P11 Plus (2021)",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Lenovo Tab P11 Plus) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 554},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "touch": 10,
        "chipset": "Helio G90", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Lenovo Tab P12 (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Lenovo Tab P12 2023) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 1478},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Dimensity 7050", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Lenovo Tab Plus (2024)",
        "os": "Android 14",
        "ua": ("Mozilla/5.0 (Linux; Android 14; Lenovo Tab Plus 2024) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 554},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Helio G99", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Lenovo Legion Tab Y700 (2022)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Lenovo Legion Tab Y7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 12,
        "touch": 10,
        "chipset": "Snapdragon 870", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Huawei MatePad 11 (2021)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei MatePad 11 20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 578},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Snapdragon 865", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Huawei MatePad 11.5 (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei MatePad 115 2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 605},
        "dpr": 2.0, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Snapdragon 7 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Huawei MatePad Pro 11 (2022)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei MatePad Pro 1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 578},
        "dpr": 2.0, "cores": 8, "ram_gb": 12,
        "touch": 10,
        "chipset": "Snapdragon 870", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Huawei MatePad SE (2022)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei MatePad SE 20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 578},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "touch": 10,
        "chipset": "Kirin 710A", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Huawei MatePad Air (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Huawei MatePad Air 2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 607},
        "dpr": 2.0, "cores": 8, "ram_gb": 12,
        "touch": 10,
        "chipset": "Snapdragon 888", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Honor Pad 8 (2022)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Honor Pad 8 2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 8,
        "touch": 10,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Honor Pad 9 (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Honor Pad 9 2023) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1280},
        "dpr": 2.0, "cores": 8, "ram_gb": 12,
        "touch": 10,
        "chipset": "Snapdragon 6 Gen 1", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Honor Pad X8 (2022)",
        "os": "Android 10",
        "ua": ("Mozilla/5.0 (Linux; Android 10; Honor Pad X8 2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 578},
        "dpr": 2.0, "cores": 8, "ram_gb": 6,
        "touch": 10,
        "chipset": "Helio G80", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Honor Pad X9 (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; Honor Pad X9 2023) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 554},
        "dpr": 2.0, "cores": 8, "ram_gb": 4,
        "touch": 10,
        "chipset": "Snapdragon 685", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Realme Pad (2021)",
        "os": "Android 11",
        "ua": ("Mozilla/5.0 (Linux; Android 11; Realme Pad 2021) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 6,
        "touch": 10,
        "chipset": "Helio G80", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "Realme Pad X (2022)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; Realme Pad X 2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 6,
        "touch": 10,
        "chipset": "Snapdragon 695", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "OPPO Pad Air (2022)",
        "os": "Android 12",
        "ua": ("Mozilla/5.0 (Linux; Android 12; OPPO Pad Air 2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        "viewport": {"width": 800, "height": 1333},
        "dpr": 1.5, "cores": 8, "ram_gb": 6,
        "touch": 10,
        "chipset": "Snapdragon 680", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
    {
        "model": "OnePlus Pad (2023)",
        "os": "Android 13",
        "ua": ("Mozilla/5.0 (Linux; Android 13; OnePlus Pad 2023) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        "viewport": {"width": 924, "height": 1294},
        "dpr": 2.0, "cores": 8, "ram_gb": 12,
        "touch": 10,
        "chipset": "Dimensity 9000", "platform_str": "Linux armv8l",
        "browser": "chrome", "device_type": "tablet",
    },
]


def _all_profiles() -> list:
    return (_IOS_PROFILES + _IPAD_PROFILES + _ANDROID_PROFILES
            + _ANDROID_TABLET_PROFILES)


def _pick_profile(platform: str) -> dict:
    """Ambil 1 device profile acak yang KONSISTEN untuk platform.

    platform: "ios" (iPhone) | "android" (HP Android) |
              "tablet" (iPad + tablet Android) | "android_tablet" | "random"
    """
    platform = platform.lower()
    if platform == "random":
        platform = random.choice(["ios", "android"])
    if platform == "ios":
        # phone saja untuk signup (iPad jarang dipakai daftar Gmail)
        return dict(random.choice(_IOS_PROFILES))
    if platform == "tablet":
        return dict(random.choice(_IPAD_PROFILES + _ANDROID_TABLET_PROFILES))
    if platform == "android_tablet":
        return dict(random.choice(_ANDROID_TABLET_PROFILES))
    return dict(random.choice(_ANDROID_PROFILES))


def get_mobile_ua(platform: str = "random") -> str:
    """Generate 1 mobile user-agent.

    platform: "ios" | "android" | "random" | "tablet"
    """
    platform = platform.lower()
    if platform == "random":
        platform = random.choice(["ios", "android"])

    # fake-useragent untuk phone saja — tablet pakai built-in (UA tablet
    # harus TANPA token "Mobile", handling fake-UA untuk tablet tidak pasti)
    if _HAS_FAKE_UA and platform != "tablet" and platform != "android_tablet":
        try:
            ua = _RealUA()
            if platform == "ios":
                return ua.getRandom(os="iOS", device_type="mobile")
            return ua.getRandom(os="Android", device_type="mobile")
        except Exception:
            pass  # jatuh ke built-in

    return _pick_profile(platform)["ua"]


def get_mobile_viewport(platform: str = "random") -> dict:
    """Generate 1 mobile viewport {width, height}.

    platform: "ios" | "android" | "random" | "tablet"
    """
    return dict(_pick_profile(platform)["viewport"])


def _user_agent_data(profile: dict) -> dict:
    """navigator.userAgentData — mobile WAJIB true (sinyal mobile ke Google)."""
    m = re.search(r"Chrome/(\d+)", profile["ua"])
    ver = m.group(1) if m else "131"
    if profile["browser"] == "safari":
        # Safari iOS tidak punya userAgentData → kosongkan (realistis!)
        return {}
    return {
        "brands": [
            {"brand": "Chromium", "version": ver},
            {"brand": "Google Chrome", "version": ver},
            {"brand": "Not-A.Brand", "version": "99"},
        ],
        "mobile": True,
        "platform": "iOS" if profile["platform_str"] == "iPhone" else "Android",
    }


class MobileFingerprint:
    """1 fingerprint mobile LENGKAP untuk 1 akun Gmail.

    Semua field KONSISTEN satu sama lain (device profile tunggal):
      - model + os_version + chipset + ram_gb + user_agent + viewport + dpr
      - cores + device_memory (bucket) + platform
      - touch support (maxTouchPoints=5, ontouchstart=True)
      - screen orientation portrait-primary
      - userAgentData.mobile = True (kecuali Safari iOS)
      - color_depth = 24
    """

    def __init__(self, platform: str = "random"):
        platform = platform.lower()
        if platform == "random":
            platform = random.choice(["ios", "android"])
        self.platform = platform  # "ios" | "android" | "tablet"

        profile = _pick_profile(platform)
        self.model = profile["model"]
        self.os_version = profile["os"]
        self.chipset = profile["chipset"]
        self.ram_gb = profile["ram_gb"]
        self.user_agent = profile["ua"]
        self.viewport = dict(profile["viewport"])
        self.device_pixel_ratio = profile["dpr"]
        self.hardware_concurrency = profile["cores"]
        self.device_memory = _RAM_TO_DEVICE_MEMORY.get(profile["ram_gb"], 4)
        self.platform_str = profile["platform_str"]  # "iPhone" | "iPad" | "Linux armv8l"
        self.browser = profile["browser"]
        self.device_type = profile.get("device_type", "phone")

        # ── Touch (mobile WAJIB punya! tablet = 10 titik) ──
        self.max_touch_points = profile.get("touch", 5)
        self.touch_support = True  # ontouchstart in window

        # ── Screen orientation (HP = portrait default) ──
        self.screen_orientation = "portrait-primary"
        self.orientation_angle = 0

        # ── Color depth (mobile modern = 24) ──
        self.color_depth = 24
        self.pixel_depth = 24

        # ── Resolusi fisik (viewport CSS × DPR) ──
        self.screen_width_px = int(self.viewport["width"] * self.device_pixel_ratio)
        self.screen_height_px = int(self.viewport["height"] * self.device_pixel_ratio)
        # Mobile: tidak ada taskbar → avail = full
        self.screen_avail_width = self.viewport["width"]
        self.screen_avail_height = self.viewport["height"]

        # ── Client hints ──
        self.user_agent_data = _user_agent_data(profile)

        # Camoufox OS param — dari platform_str biar tablet Android
        # tidak salah dapat "ios" (platform "tablet" bisa iPad ATAU Android)
        self.camoufox_os = "ios" if self.platform_str in ("iPhone", "iPad") else "android"
        # Locale konsisten ID (aturan: IP ID → locale id-ID)
        self.locale = "id-ID"
        self.timezone = "Asia/Jakarta"

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "model": self.model,
            "os_version": self.os_version,
            "chipset": self.chipset,
            "ram_gb": self.ram_gb,
            "user_agent": self.user_agent,
            "viewport": self.viewport,
            "device_pixel_ratio": self.device_pixel_ratio,
            "hardware_concurrency": self.hardware_concurrency,
            "device_memory": self.device_memory,
            "platform_str": self.platform_str,
            "device_type": self.device_type,
            "max_touch_points": self.max_touch_points,
            "touch_support": self.touch_support,
            "screen_orientation": self.screen_orientation,
            "orientation_angle": self.orientation_angle,
            "color_depth": self.color_depth,
            "pixel_depth": self.pixel_depth,
            "screen_width_px": self.screen_width_px,
            "screen_height_px": self.screen_height_px,
            "screen_avail_width": self.screen_avail_width,
            "screen_avail_height": self.screen_avail_height,
            "user_agent_data": self.user_agent_data,
            "camoufox_os": self.camoufox_os,
            "locale": self.locale,
            "timezone": self.timezone,
            "fake_ua_lib": _HAS_FAKE_UA,
        }

    def spoof_js(self) -> str:
        """JS snippet untuk override navigator/screen via add_init_script.

        Dipakai kalau Camoufox os=... saja tidak cukup.
        """
        import json
        d = self.to_dict()
        return f"""
// ── Mobile fingerprint spoof (model: {self.model}, {self.os_version}, {self.chipset}) ──
Object.defineProperty(navigator, 'maxTouchPoints', {{get: () => {d['max_touch_points']}}});
Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {d['hardware_concurrency']}}});
Object.defineProperty(navigator, 'deviceMemory', {{get: () => {d['device_memory']}}});
Object.defineProperty(navigator, 'platform', {{get: () => {json.dumps(d['platform_str'])}}});
window.ontouchstart = null;  // touch support terdeteksi
Object.defineProperty(screen, 'width', {{get: () => {d['viewport']['width']}}});
Object.defineProperty(screen, 'height', {{get: () => {d['viewport']['height']}}});
Object.defineProperty(screen, 'availWidth', {{get: () => {d['screen_avail_width']}}});
Object.defineProperty(screen, 'availHeight', {{get: () => {d['screen_avail_height']}}});
Object.defineProperty(screen, 'colorDepth', {{get: () => {d['color_depth']}}});
Object.defineProperty(screen, 'pixelDepth', {{get: () => {d['pixel_depth']}}});
Object.defineProperty(window, 'devicePixelRatio', {{get: () => {d['device_pixel_ratio']}}});
if (screen.orientation) {{
    try {{
        Object.defineProperty(screen.orientation, 'type', {{get: () => {json.dumps(d['screen_orientation'])}}});
        Object.defineProperty(screen.orientation, 'angle', {{get: () => {d['orientation_angle']}}});
    }} catch (e) {{}}
}}
"""

    def __repr__(self):
        vp = self.viewport
        return (f"MobileFingerprint({self.model}, {self.os_version}, {self.chipset}, "
                f"{vp['width']}x{vp['height']}@{self.device_pixel_ratio}x, "
                f"{self.hardware_concurrency}c/{self.ram_gb}GB, "
                f"touch={self.max_touch_points})")


def check_consistency(fp: MobileFingerprint) -> list:
    """Validasi konsistensi fingerprint. Return list masalah (kosong = OK)."""
    issues = []
    d = fp.to_dict()
    ua = d["user_agent"]
    chipset = d["chipset"]
    # Branching berdasarkan platform_str (bukan argumen platform),
    # karena "tablet" bisa iPad ATAU tablet Android.
    is_apple = d["platform_str"] in ("iPhone", "iPad")
    is_tablet = d.get("device_type") == "tablet"

    if is_apple:
        if d["platform_str"] == "iPhone":
            if "iPhone" not in ua:
                issues.append("iOS tapi UA tidak mengandung 'iPhone'")
        else:
            if "iPad" not in ua:
                issues.append("tablet tapi UA tidak mengandung 'iPad'")
        if d["hardware_concurrency"] != 6:
            issues.append(f"Apple tapi cores={d['hardware_concurrency']} (harus 6)")
        if chipset not in _APPLE_CHIPSETS:
            issues.append(f"iOS tapi chipset '{chipset}' bukan Apple! JANGAN iPhone pakai Snapdragon!")
        if d["device_pixel_ratio"] not in (2.0, 3.0):
            issues.append(f"Apple tapi dpr={d['device_pixel_ratio']}")
    else:
        # Android: phone ATAU tablet
        if "Android" not in ua:
            issues.append("Android tapi UA tidak mengandung 'Android'")
        if "Linux" not in d["platform_str"]:
            issues.append("Android tapi platform_str bukan Linux*")
        if d["hardware_concurrency"] not in (6, 8):
            issues.append(f"Android tapi cores={d['hardware_concurrency']} (umumnya 8)")
        if is_tablet:
            # UA tablet TIDAK mengandung token "Mobile" — itu sinyal tablet!
            if "Mobile" in ua:
                issues.append("tablet Android tapi UA mengandung 'Mobile' (tablet tidak pakai token Mobile!)")
            if d["max_touch_points"] < 10:
                issues.append(f"tablet tapi maxTouchPoints={d['max_touch_points']} (tablet umumnya 10)")
        else:
            if "Mobile" not in ua:
                issues.append("Android tapi UA tidak mengandung 'Mobile'")
        if chipset not in _ANDROID_CHIPSETS:
            issues.append(f"Android tapi chipset '{chipset}' tidak dikenal / bukan Android!")
        if chipset in _APPLE_CHIPSETS:
            issues.append(f"Android tapi chipset '{chipset}' = Apple! JANGAN!")

    # RAM → deviceMemory bucket harus cocok
    expected_dm = _RAM_TO_DEVICE_MEMORY.get(d["ram_gb"])
    if expected_dm is not None and d["device_memory"] != expected_dm:
        issues.append(f"RAM {d['ram_gb']}GB → deviceMemory harus {expected_dm}, dapat {d['device_memory']}")

    if d["max_touch_points"] < 1:
        issues.append("mobile tanpa touch = mustahil")
    if d["device_pixel_ratio"] < 1.5:
        issues.append(f"dpr={d['device_pixel_ratio']} terlalu rendah untuk HP modern")
    if d["screen_orientation"] != "portrait-primary":
        issues.append("HP default harus portrait-primary")
    if d["color_depth"] != 24:
        issues.append(f"color_depth={d['color_depth']} (umumnya 24)")
    # Fisik = CSS × DPR
    if d["screen_width_px"] != int(d["viewport"]["width"] * d["device_pixel_ratio"]):
        issues.append("screen_width_px tidak = viewport × dpr")
    return issues


if __name__ == "__main__":
    total = len(_all_profiles())
    print(f"=== {total} device profile ===")
    ios_n = len(_IOS_PROFILES); ipad_n = len(_IPAD_PROFILES)
    and_n = len(_ANDROID_PROFILES); tab_n = len(_ANDROID_TABLET_PROFILES)
    print(f"iPhone: {ios_n} | iPad: {ipad_n} | Android phone: {and_n} | Android tablet: {tab_n}")

    # Cakupan versi OS
    ios_vers = sorted({p["os"] for p in _IOS_PROFILES})
    and_vers = sorted({p["os"] for p in _ANDROID_PROFILES})
    print(f"iOS versions: {', '.join(ios_vers)}")
    print(f"Android versions: {', '.join(and_vers)}")

    # Viewport unik
    vps = sorted({(p['viewport']['width'], p['viewport']['height']) for p in _all_profiles()})
    print(f"Viewport unik: {len(vps)} → {vps}")

    # RAM variants
    rams = sorted({p['ram_gb'] for p in _all_profiles()})
    print(f"RAM variants: {rams} GB")

    # Chipset unik
    chips = sorted({p['chipset'] for p in _all_profiles()})
    print(f"Chipset unik ({len(chips)}): {', '.join(chips)}")

    print()
    print("=== Generate 10 fingerprint + cek konsistensi ===")
    all_ok = True
    for i in range(10):
        fp = MobileFingerprint("random")
        issues = check_consistency(fp)
        status = "OK" if not issues else f"MASALAH: {issues}"
        if issues:
            all_ok = False
        print(f"[{i+1}] {fp} → {status}")

    print()
    print("=== Generate 5 tablet + cek konsistensi ===")
    for i in range(5):
        fp = MobileFingerprint("tablet")
        issues = check_consistency(fp)
        status = "OK" if not issues else f"MASALAH: {issues}"
        if issues:
            all_ok = False
        d = fp.to_dict()
        print(f"[T{i+1}] {fp.model} | touch={d['max_touch_points']} | "
              f"camoufox_os={d['camoufox_os']} | "
              f"'Mobile' in UA: {'Mobile' in d['user_agent']} → {status}")
    print()
    print("fake-useragent tersedia:", _HAS_FAKE_UA)
    print("HASIL:", "SEMUA KONSISTEN ✅" if all_ok else "ADA YANG INKONSISTEN ❌")
