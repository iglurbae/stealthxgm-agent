"""
MOBILE_DEVICES.PY — SoC→GPU mapping + weighted mobile device selection.

Diadopsi dari identity_kit (GLM 5.3) Hermes VPS — keunggulan utama:
1. SoC→GPU mapping: GPU WebGL HARUS match dengan chipset device
   (Snapdragon→Adreno, Dimensity/Helio→Mali-G, Exynos→Mali-G, Apple→Apple GPU)
   Tanpa ini, kombinasi "Snapdragon + Mali GPU" = tell instan!
2. Weighted tier selection: budget 40% / mid 40% / flagship 20%
   (distribusi realistis pasar Indonesia)

Menggunakan database 451 device dari gmail/mobile_fingerprint.py (lebih besar
dari DB 58-device identity_kit). File ini menambah layer konsistensi di atasnya.

PENTING: hanya teknik spoofing. Tidak ada credential di file ini.
"""

import random
from typing import Tuple, Optional

# ── GLM_KEY_DEVICES — cross-check vs devices.py GLM 5.3 (RND-GLM53) ──
# Model-model yang disebut eksplisit di laporan bedah identity_kit GLM.
# Tiap entri: nama model, chipset yang BENAR (terverifikasi), token UA, dan
# vendor GPU yang diharapkan dari soc_to_gpu(). verify_glm_devices()
# memastikan semuanya ada di database vendor (451 → 453 profil setelah
# adopsi 2026-11-05) dengan chipset yang cocok.
# KOREKSI DATA (terverifikasi web 2026-11-05, BUKAN dari laporan GLM saja):
# - "OPPO A78 (CPH2495)" di laporan GLM = A78 5G (Dimensity 700), bukan A78
#   4G (CPH2565, Snapdragon 680). Keduanya ada di DB sebagai entri terpisah.
# - Redmi Note 13 Pro 4G = Helio G99 Ultra (BUKAN Snapdragon 732G — itu
#   milik Note 10 Pro / Note 12 Pro 4G).
GLM_KEY_DEVICES = [
    {"model": "Galaxy S24 Ultra", "chipset": "Snapdragon 8 Gen 3",
     "ua_token": "SM-S928B", "gpu_vendor": "Qualcomm"},
    {"model": "OPPO A78", "chipset": "Snapdragon 680",
     "ua_token": "CPH2565", "gpu_vendor": "Qualcomm"},
    {"model": "OPPO A78 5G", "chipset": "Dimensity 700",
     "ua_token": "CPH2495", "gpu_vendor": "ARM"},
    {"model": "Redmi Note 13 Pro", "chipset": "Helio G99 Ultra",
     "ua_token": "Redmi Note 13 Pro", "gpu_vendor": "ARM"},
]


def _load_vendor_profiles():
    """Load daftar profil device dari vendor/mobile_fingerprint.py.

    Pakai importlib berdasarkan path file (bukan nama paket) supaya jalan
    baik sebagai modul paket maupun script langsung.
    """
    import importlib.util
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "vendor", "mobile_fingerprint.py")
    path = os.path.normpath(path)
    spec = importlib.util.spec_from_file_location("vendor_mobile_fingerprint", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._all_profiles()


def verify_glm_devices():
    """Assert semua GLM_KEY_DEVICES ada di DB vendor dengan chipset + UA
    yang cocok, dan soc_to_gpu() mengembalikan vendor GPU yang diharapkan.
    Raise AssertionError kalau ada yang hilang/bertabrakan.
    """
    profiles = _load_vendor_profiles()
    by_model = {}
    for d in profiles:
        by_model.setdefault(d.get("model"), []).append(d)
    for want in GLM_KEY_DEVICES:
        hits = by_model.get(want["model"], [])
        assert hits, f"GLM device hilang dari DB vendor: {want['model']}"
        d = hits[0]
        assert d.get("chipset") == want["chipset"], \
            f"{want['model']}: chipset DB '{d.get('chipset')}' != '{want['chipset']}'"
        assert want["ua_token"] in str(d.get("ua", "")), \
            f"{want['model']}: UA tidak mengandung token '{want['ua_token']}'"
        vendor, _renderer = soc_to_gpu(d["chipset"])
        assert vendor == want["gpu_vendor"], \
            f"{want['model']}: soc_to_gpu({d['chipset']}) = {vendor}, harusnya {want['gpu_vendor']}"
    return len(profiles)

# ── SoC → GPU mapping (dari identity_kit inject_mobile_js) ──
# Prinsip: GPU renderer HARUS konsisten dengan chipset!
# Snapdragon tanpa Adreno = tell. Dimensity tanpa Mali = tell.


def soc_to_gpu(soc: str) -> Tuple[str, str]:
    """Map chipset → (gpu_vendor, gpu_renderer) yang konsisten.

    Args:
        soc: nama chipset, mis. "Snapdragon 8 Gen 3", "Dimensity 8200"

    Returns:
        (vendor, renderer) untuk WebGL getParameter spoofing.
    """
    soc = (soc or "").strip()
    if "Snapdragon" in soc:
        return ("Qualcomm", f"Adreno (Qualcomm, {soc})")
    elif "Dimensity" in soc or "Helio" in soc:
        return ("ARM", f"Mali-G (ARM, {soc})")
    elif "Exynos" in soc:
        return ("ARM", f"Mali-G (Samsung, {soc})")
    elif "Unisoc" in soc:
        return ("ARM", f"Mali-G (Unisoc, {soc})")
    elif "Tensor" in soc:
        return ("ARM", f"Mali-G (Google, {soc})")
    elif "Kirin" in soc:
        return ("ARM", f"Mali-G (HiSilicon, {soc})")
    # Apple: A11-A18, M1-M4
    elif any(soc.startswith(p) for p in ("A1", "A2")) or soc.startswith("M"):
        return ("Apple", f"Apple GPU ({soc})")
    else:
        return ("ARM", f"Mali-G ({soc})")


def mobile_gpu_spoof_js(soc: str) -> str:
    """Generate JS patch WebGL GPU yang match dengan SoC device.

    Args:
        soc: nama chipset dari mobile fingerprint.

    Returns:
        str JS untuk inject — patch getParameter WebGL1 + WebGL2.
    """
    vendor, renderer = soc_to_gpu(soc)
    # Escape untuk JS string
    vendor_esc = vendor.replace("'", "\\'")
    renderer_esc = renderer.replace("'", "\\'")
    return """
(() => {
    const _gv = '%s';
    const _gr = '%s';
    const spoofParam = (proto) => {
        try {
            const orig = proto.prototype.getParameter;
            proto.prototype.getParameter = function(p) {
                if (p === 0x9245) return 'Google Inc. (' + _gv + ')';
                if (p === 0x9246) return _gr;
                if (p === 0x1F00) return 'WebKit';
                if (p === 0x1F01) return 'WebKit WebGL';
                return orig.call(this, p);
            };
            if (window.__markPatched) window.__markPatched(proto.prototype.getParameter);
        } catch(e) {}
    };
    if (window.WebGLRenderingContext) spoofParam(WebGLRenderingContext);
    if (window.WebGL2RenderingContext) spoofParam(WebGL2RenderingContext);
})();
""" % (vendor_esc, renderer_esc)


# ── Weighted tier selection ──
# Distribusi realistis pasar Indonesia: budget 40%, mid 40%, flagship 20%


def weighted_tier() -> str:
    """Pilih tier dengan distribusi realistis pasar Indonesia."""
    return random.choices(
        ["budget", "mid", "flagship"],
        weights=[40, 40, 20],
    )[0]


def pick_mobile_platform(tier: Optional[str] = None) -> str:
    """Pilih platform mobile dengan weighted tier.

    Args:
        tier: None (weighted random) / "budget" / "mid" / "flagship"

    Returns:
        "android" | "ios" | "tablet" — dengan bobot realistis.
    """
    chosen_tier = tier or weighted_tier()
    # iOS lebih banyak di flagship, Android dominan di budget/mid
    if chosen_tier == "flagship":
        return random.choices(["ios", "android", "tablet"], weights=[45, 45, 10])[0]
    elif chosen_tier == "mid":
        return random.choices(["ios", "android", "tablet"], weights=[15, 75, 10])[0]
    else:  # budget
        return random.choices(["android", "ios", "tablet"], weights=[85, 10, 5])[0]


def new_mobile_identity_soc_gpu(platform: str = "random", country: str = "sg",
                                tier: Optional[str] = None) -> dict:
    """Generate mobile identity + SoC→GPU consistency.

    Wrapper di atas fingerprint.new_mobile_identity() yang menambah:
    - weighted tier selection (kalau tier=None)
    - gpu_vendor/gpu_renderer yang match dengan chipset
    - gpu_spoof_js siap inject

    Args:
        platform: "random" | "ios" | "android" | "tablet"
        country: kode negara untuk geo
        tier: None (weighted) | "budget" | "mid" | "flagship"

    Returns:
        dict identitas mobile + field tambahan:
        - gpu_vendor, gpu_renderer (SoC-matched)
        - gpu_spoof_js (str JS siap inject)
        - device_tier (tier yang dipakai)
    """
    try:
        from .mobile import new_mobile_identity
    except ImportError:
        from fingerprint.mobile import new_mobile_identity

    chosen_tier = tier or weighted_tier()
    if platform == "random":
        platform = pick_mobile_platform(chosen_tier)

    ident = new_mobile_identity(platform=platform, country=country)

    # Tambah SoC→GPU consistency
    chipset = ident.get("chipset", "")
    gpu_vendor, gpu_renderer = soc_to_gpu(chipset)
    ident["gpu_vendor"] = gpu_vendor
    ident["gpu_renderer"] = gpu_renderer
    ident["gpu_spoof_js"] = mobile_gpu_spoof_js(chipset)
    ident["device_tier"] = chosen_tier

    return ident


if __name__ == "__main__":
    if not __package__:
        # Dijalankan langsung: jalankan ulang sebagai modul paket (GLM P4).
        import os as _os, sys as _sys, runpy as _runpy, warnings as _warnings
        _warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")
        _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        _runpy.run_module("fingerprint.mobile_devices", run_name="__main__")
        raise SystemExit(0)
    print("=== TEST SoC→GPU MAPPING ===")
    test_socs = [
        "Snapdragon 8 Gen 3", "Snapdragon 680",
        "Dimensity 8200", "Helio G99",
        "Exynos 1480", "Tensor G3",
        "A17 Pro", "M2",
        "Unisoc T606",
    ]
    for soc in test_socs:
        v, r = soc_to_gpu(soc)
        print(f"  {soc:22} → {v:10} | {r}")

    print("\n=== TEST WEIGHTED TIER (20x) ===")
    from collections import Counter
    tiers = Counter(weighted_tier() for _ in range(20))
    print(f"  {dict(tiers)}")

    print("\n=== TEST GLM_KEY_DEVICES (adopsi GLM P1: data dunia nyata) ===")
    total = verify_glm_devices()
    print(f"  {len(GLM_KEY_DEVICES)} model kunci GLM terverifikasi di DB vendor "
          f"({total} profil total):")
    for d in GLM_KEY_DEVICES:
        print(f"    ✅ {d['model']:20} | {d['chipset']:20} | UA token {d['ua_token']} "
              f"| GPU {d['gpu_vendor']}")

    print("\n=== TEST GENERATE 5 MOBILE IDENTITIES ===")
    for i in range(5):
        ident = new_mobile_identity_soc_gpu()
        ok_gpu = "Adreno" in ident["gpu_renderer"] or "Mali" in ident["gpu_renderer"] or "Apple GPU" in ident["gpu_renderer"]
        print(f"  {i+1}. {ident.get('model', '?'):25} | {ident.get('chipset', '?'):20} | "
              f"tier={ident['device_tier']:8} | GPU_match={'✅' if ok_gpu else '❌'}")

    print("\n✅ mobile_devices.py OK")
