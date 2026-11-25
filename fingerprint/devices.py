"""Device specs, GPU pools, identity generation.

Extracted from fingerprint.py — logic unchanged.
"""
import json
import random

_NVIDIA_MID = ['GeForce GTX 1650', 'GeForce GTX 1660', 'GeForce GTX 1660 SUPER',
               'GeForce RTX 2060', 'GeForce RTX 2060 SUPER', 'GeForce RTX 2070',
               'GeForce RTX 3050', 'GeForce RTX 3060', 'GeForce RTX 3060 Ti',
               'GeForce RTX 4060', 'GeForce RTX 4060 Ti',
               'GeForce RTX 5060', 'GeForce RTX 5060 Ti']
_NVIDIA_HIGH = ['GeForce RTX 2080', 'GeForce RTX 3070', 'GeForce RTX 3070 Ti',
                'GeForce RTX 3080', 'GeForce RTX 3080 Ti', 'GeForce RTX 3090',
                'GeForce RTX 4070', 'GeForce RTX 4070 Ti', 'GeForce RTX 4070 Ti SUPER',
                'GeForce RTX 4080', 'GeForce RTX 4080 SUPER', 'GeForce RTX 4090',
                'GeForce RTX 5070', 'GeForce RTX 5070 Ti', 'GeForce RTX 5080',
                'GeForce RTX 5090']
_AMD_MID = ['Radeon RX 580', 'Radeon RX 590', 'Radeon RX 5500 XT', 'Radeon RX 5600 XT',
            'Radeon RX 5700 XT', 'Radeon RX 6600', 'Radeon RX 6600 XT', 'Radeon RX 6650 XT',
            'Radeon RX 6700 XT', 'Radeon RX 7600', 'Radeon RX 7700 XT',
            'Radeon RX 9060 XT']
_AMD_HIGH = ['Radeon RX 6750 XT', 'Radeon RX 6800', 'Radeon RX 6800 XT', 'Radeon RX 6900 XT',
             'Radeon RX 6950 XT', 'Radeon RX 7800 XT', 'Radeon RX 7900 GRE',
             'Radeon RX 7900 XT', 'Radeon RX 7900 XTX',
             'Radeon RX 9070', 'Radeon RX 9070 XT']
_INTEL_IGPU = ['Intel(R) UHD Graphics 620', 'Intel(R) UHD Graphics 630', 'Intel(R) UHD Graphics 730',
               'Intel(R) UHD Graphics 770', 'Intel(R) Iris(R) Xe Graphics',
               # F10 (2026-11-08): nama generik "Iris(R) Plus Graphics" TIDAK
               # punya string renderer nyata (Chrome selalu lapor varian
               # spesifik 640/645/655). Dipilih 655 (0x3ea5, CoffeeLake-U
               # GT3e — varian paling umum, pci.ids v2026.11.08).
               'Intel(R) Iris(R) Plus Graphics 655',
               'Intel(R) Arc(TM) 130V GPU', 'Intel(R) Arc(TM) 140V GPU']
# F10 (2026-11-08): APU AMD JANGAN di daftar Intel lagi — sebelumnya _mk
# membangunnya sebagai "ANGLE (Intel, AMD Radeon 780M ...)" dengan vendor
# "Google Inc. (Intel)" = tell instan (GPU AMD di bawah vendor Intel).
# Nama display = string renderer nyata (pci.ids + checkproxy.org):
# "AMD Radeon(TM) 780M Graphics (0x000015BF)" dst.
_AMD_APU = ['AMD Radeon(TM) 780M Graphics', 'AMD Radeon(TM) 880M Graphics',
            'AMD Radeon(TM) 890M Graphics', 'AMD Radeon 8060S Graphics']
_INTEL_MID = ['Intel(R) Arc(TM) A380 Graphics', 'Intel(R) Arc(TM) A580 Graphics',
              'Intel(R) Arc(TM) A750 Graphics', 'Intel(R) Arc(TM) A770 Graphics',
              'Intel(R) Arc(TM) B580 Graphics', 'Intel(R) Arc(TM) B570 Graphics']
_APPLE_SILICON = ['Apple M1', 'Apple M1 Pro', 'Apple M1 Max',
                  'Apple M2', 'Apple M2 Pro', 'Apple M2 Max',
                  'Apple M3', 'Apple M3 Pro', 'Apple M3 Max',
                  'Apple M4', 'Apple M4 Pro', 'Apple M4 Max']


# F10 (2026-11-08): PCI device ID per model (desktop, non-Mobile/Max-Q).
# Sumber: pci.ids v2026.11.08 (https://pci-ids.ucw.cz/v2.2/pci.ids) —
# diverifikasi baris-per-baris; string renderer liar dikonfirmasi lewat
# checkproxy.org/gpu-list + chrome-fingerprints 10k dataset (Chrome 114-119).
# Bila satu model punya beberapa ID (revisi silikon), dipilih varian desktop
# paling umum (tercatat di FIX-LOG-F10). ID keluarga AMD dibagi beberapa
# model (mis. RX 6800/6800 XT/6900 XT = 0x73bf Navi 21) — itu fakta
# hardware, bukan tebakan. Apple Silicon tidak punya PCI ID (format Metal
# tidak punya field device-id).
PCI_IDS = {
    # NVIDIA (10de) — format (0x%08X), huruf besar, 8 digit.
    'GeForce GTX 1650': 0x1F82, 'GeForce GTX 1660': 0x2184,
    'GeForce GTX 1660 SUPER': 0x21C4, 'GeForce RTX 2060': 0x1F08,
    'GeForce RTX 2060 SUPER': 0x1F06, 'GeForce RTX 2070': 0x1F02,
    'GeForce RTX 3050': 0x2507, 'GeForce RTX 3060': 0x2503,
    'GeForce RTX 3060 Ti': 0x2486, 'GeForce RTX 4060': 0x2882,
    'GeForce RTX 4060 Ti': 0x2803, 'GeForce RTX 5060': 0x2F06,
    'GeForce RTX 5060 Ti': 0x2D04, 'GeForce RTX 2080': 0x1E82,
    'GeForce RTX 3070': 0x2484, 'GeForce RTX 3070 Ti': 0x2482,
    'GeForce RTX 3080': 0x2206, 'GeForce RTX 3080 Ti': 0x2208,
    'GeForce RTX 3090': 0x2204, 'GeForce RTX 4070': 0x2786,
    'GeForce RTX 4070 Ti': 0x2782, 'GeForce RTX 4070 Ti SUPER': 0x2705,
    'GeForce RTX 4080': 0x2704, 'GeForce RTX 4080 SUPER': 0x2703,
    'GeForce RTX 4090': 0x2684, 'GeForce RTX 5070': 0x2F04,
    'GeForce RTX 5070 Ti': 0x2C05, 'GeForce RTX 5080': 0x2C02,
    'GeForce RTX 5090': 0x2B85,
    # AMD discrete (1002) — ID dibagi per keluarga Navi.
    'Radeon RX 580': 0x67DF, 'Radeon RX 590': 0x67DF,
    'Radeon RX 5500 XT': 0x7340, 'Radeon RX 5600 XT': 0x731F,
    'Radeon RX 5700 XT': 0x731F, 'Radeon RX 6600': 0x73FF,
    'Radeon RX 6600 XT': 0x73FF, 'Radeon RX 6650 XT': 0x73EF,
    'Radeon RX 6700 XT': 0x73DF, 'Radeon RX 7600': 0x7480,
    'Radeon RX 7700 XT': 0x747E, 'Radeon RX 9060 XT': 0x7590,
    'Radeon RX 6750 XT': 0x73DF, 'Radeon RX 6800': 0x73BF,
    'Radeon RX 6800 XT': 0x73BF, 'Radeon RX 6900 XT': 0x73AF,
    'Radeon RX 6950 XT': 0x73A5, 'Radeon RX 7800 XT': 0x747E,
    'Radeon RX 7900 GRE': 0x744C, 'Radeon RX 7900 XT': 0x744C,
    'Radeon RX 7900 XTX': 0x744C, 'Radeon RX 9070': 0x7550,
    'Radeon RX 9070 XT': 0x7550,
    # AMD APU (1002).
    'AMD Radeon(TM) 780M Graphics': 0x15BF,
    'AMD Radeon(TM) 880M Graphics': 0x150E,
    'AMD Radeon(TM) 890M Graphics': 0x150E,
    'AMD Radeon 8060S Graphics': 0x1586,
    # Intel (8086).
    'Intel(R) UHD Graphics 620': 0x5917, 'Intel(R) UHD Graphics 630': 0x3E98,
    'Intel(R) UHD Graphics 730': 0x4692, 'Intel(R) UHD Graphics 770': 0x4690,
    'Intel(R) Iris(R) Xe Graphics': 0x46A6,
    'Intel(R) Iris(R) Plus Graphics 655': 0x3EA5,
    'Intel(R) Arc(TM) 130V GPU': 0x64A0, 'Intel(R) Arc(TM) 140V GPU': 0x64A0,
    'Intel(R) Arc(TM) A380 Graphics': 0x56A5,
    'Intel(R) Arc(TM) A580 Graphics': 0x56A2,
    'Intel(R) Arc(TM) A750 Graphics': 0x56A1,
    'Intel(R) Arc(TM) A770 Graphics': 0x56A0,
    'Intel(R) Arc(TM) B580 Graphics': 0xE20B,
    'Intel(R) Arc(TM) B570 Graphics': 0xE20C,
}


def _mk(vendor_tag, models, cls, backend='d3d11'):
    """Build GPU entries dengan renderer format sesuai platform.

    backend: 'd3d11' (Windows), 'metal' (macOS), 'gl' (Linux/ChromeOS)
    RND 2026-11-03: D3D11 di Mac/Linux = tell instan!
    """
    out = []
    for m in models:
        if backend == 'metal':
            # Apple Silicon / Mac — format Metal
            gv = 'Google Inc. (Apple)'
            gr = 'ANGLE (Apple, ANGLE Metal Renderer: %s, Unspecified Version)' % m
        elif backend == 'gl':
            # Linux — format OpenGL
            gv = 'Google Inc. (%s)' % vendor_tag
            gr = 'ANGLE (%s, %s, OpenGL 4.6)' % (vendor_tag, m)
        else:
            # Windows — format D3D11
            # F10 (2026-11-08): Chrome 150+ menyertakan PCI device ID di
            # string renderer — tanpanya = tell (dulu semua model tanpa ID).
            gv = 'Google Inc. (%s)' % vendor_tag
            _pid = PCI_IDS.get(m)
            _id = ' (0x%08X)' % _pid if _pid is not None else ''
            if vendor_tag != 'Intel':
                # Model APU sudah mengandung "AMD" ("AMD Radeon(TM) ...") —
                # jangan prepend vendor dua kali.
                _name = m if m.startswith(vendor_tag) else ('%s %s' % (vendor_tag, m))
                gr = 'ANGLE (%s, %s%s Direct3D11 vs_5_0 ps_5_0, D3D11)' % (vendor_tag, _name, _id)
            else:
                gr = 'ANGLE (Intel, %s%s Direct3D11 vs_5_0 ps_5_0, D3D11)' % (m, _id)
        out.append((gv, gr, cls))
    return out


GPUS = (_mk('NVIDIA', _NVIDIA_MID, 'mid') + _mk('NVIDIA', _NVIDIA_HIGH, 'high')
        + _mk('AMD', _AMD_MID, 'mid') + _mk('AMD', _AMD_HIGH, 'high')
        + _mk('Intel', _INTEL_IGPU, 'igpu') + _mk('Intel', _INTEL_MID, 'mid')
        + _mk('AMD', _AMD_APU, 'igpu')
        + _mk('Apple', _APPLE_SILICON, 'apple', backend='metal'))

# layar per kelas: iGPU/laptop kecil, mid desktop FHD/QHD, high sampai 4K/ultrawide
SCREENS = {
    'igpu': [(1366, 768, 1), (1536, 864, 1.25), (1600, 900, 1.25), (1280, 800, 1),
             (1440, 900, 1), (1280, 1024, 1), (1680, 1050, 1), (1920, 1080, 1),
             (1920, 1080, 1.25), (1920, 1200, 1), (1280, 720, 1)],
    'mid': [(1600, 900, 1), (1920, 1080, 1), (1920, 1080, 1.25), (2560, 1080, 1),
            (2560, 1440, 1), (1920, 1200, 1), (1680, 1050, 1), (2560, 1440, 1.25),
            (1920, 1080, 1.5)],
    'high': [(1920, 1080, 1), (2560, 1440, 1), (2560, 1440, 1.25), (3440, 1440, 1),
             (3840, 2160, 1), (3840, 2160, 1.5), (2560, 1440, 1.5), (1920, 1080, 1.25),
             (5120, 1440, 1), (3840, 1600, 1)],
    'apple': [(1512, 982, 2), (1728, 1117, 2), (1440, 900, 2), (1920, 1080, 1),
              (2560, 1600, 2), (2048, 1152, 1)],
}
HWS = {'igpu': [4, 6, 8], 'mid': [6, 8, 12, 16], 'high': [8, 12, 16, 20, 24],
       'apple': [8, 10, 12, 14, 16]}
MEMS = [4, 8]  # Chrome navigator.deviceMemory di-cap 8 — nilai 16 = tell bot



def new_identity():
    """Generate satu identitas fingerprint yang PLAUSIBLE (teknik Gil).

    LENGKAP (Gil 2026-11-02 15:59): termasuk browser detail, platform,
    screen detail! Semua konsisten!
    """
    gv, gr, cls = random.choice(GPUS)
    sw, sh, dpr = random.choice(SCREENS[cls])
    hw = random.choice(HWS[cls])
    mem = random.choices(MEMS, weights=[1, 4])[0]  # mayoritas device nyata report 8
    vw = random.randint(int(sw * 0.6), sw - 40)
    vh = random.randint(int(sh * 0.6), sh - 80)
    # browser detail (lengkap!)
    # GLM P4: file harus bisa membuktikan dirinya sendiri — jalanin langsung
    # (python3 fingerprint/devices.py) harus tetap jalan, bukan cuma sebagai modul.
    try:
        from .geo import BROWSER_DETAILS, SCREEN_DETAILS, USER_AGENTS
    except ImportError:  # dijalankan langsung sebagai script
        from geo import BROWSER_DETAILS, SCREEN_DETAILS, USER_AGENTS
    browser = random.choice(BROWSER_DETAILS)
    screen_det = random.choice(SCREEN_DETAILS)
    # M4 (RND 2026-11-03): _ua konsisten dengan platform browser
    _ua_platform_map = {
        'Win32': [u for u in USER_AGENTS if 'Windows NT' in u],
        'MacIntel': [u for u in USER_AGENTS if 'Macintosh' in u],
        'Linux x86_64': [u for u in USER_AGENTS if 'Linux x86_64' in u and 'CrOS' not in u],
    }
    _ua_candidates = _ua_platform_map.get(browser["platform"], USER_AGENTS)
    _ua = random.choice(_ua_candidates) if _ua_candidates else random.choice(USER_AGENTS)
    return dict(gpu_vendor=gv, gpu_renderer=gr, gpu_class=cls,
                screen_w=sw, screen_h=sh, dpr=dpr,
                hw=hw, mem=mem, vp=(vw, vh),
                # baru: browser lengkap!
                platform=browser["platform"],
                oscpu=browser["oscpu"],
                chrome_ver=browser["chrome_ver"],
                vendor=browser["vendor"],
                app_ver=browser["app_ver"],
                color_depth=screen_det["color_depth"],
                pixel_depth=screen_det["pixel_depth"],
                _ua=_ua)


# ── Consistency asserts (adopsi GLM 5.3 P2: tegakkan, bukan harapkan) ──
def check_consistency():
    """Assert invarian database GPU/layar/hardware. Raise AssertionError
    kalau ada nilai yang bertabrakan — tangkap sebelum jalan, bukan pas
    ketahuan anti-bot. Dipanggil dari __main__ dan dari fingerprint_gen.
    """
    # MEMS: Chrome deviceMemory di-cap 8 — nilai >8 = tell bot.
    assert all(isinstance(m, int) and 1 <= m <= 8 for m in MEMS), \
        f"MEMS mengandung nilai >8: {MEMS}"
    # iGPU = laptop kecil, layar max 1920 lebar (GLM P2).
    assert max(w for w, _h, _d in SCREENS["igpu"]) <= 1920, \
        f"SCREENS igpu ada yang >1920: {SCREENS['igpu']}"
    # high-end harus punya opsi 4K; mid tidak boleh punya 4K.
    assert any(w >= 3840 for w, _h, _d in SCREENS["high"]), \
        "SCREENS high tidak punya opsi 4K"
    assert all(w < 3840 for w, _h, _d in SCREENS["mid"]), \
        f"SCREENS mid ada yang 4K: {SCREENS['mid']}"
    # cores: igpu max 8, high min 8 (GLM P2).
    assert max(HWS["igpu"]) <= 8, f"HWS igpu >8: {HWS['igpu']}"
    assert min(HWS["high"]) >= 8, f"HWS high <8: {HWS['high']}"
    # format renderer per backend: D3D11 (Windows) / Metal (Mac) / OpenGL (Linux).
    for gv, gr, cls in _mk("NVIDIA", _NVIDIA_HIGH, "high"):
        assert "Direct3D11" in gr and "D3D11" in gr, f"D3D11 hilang: {gr}"
    # F10 (2026-11-08): SEMUA model D3D11 wajib punya PCI device ID di
    # string renderer (format Chrome 150+: "(0x%08X)"); APU AMD wajib
    # vendor AMD (bukan Intel); semua model D3D11 wajib ada di PCI_IDS.
    for _lst in (_NVIDIA_MID, _NVIDIA_HIGH, _AMD_MID, _AMD_HIGH,
                _INTEL_IGPU, _INTEL_MID, _AMD_APU):
        for _m in _lst:
            assert _m in PCI_IDS, f"model D3D11 tanpa PCI ID: {_m}"
    for gv, gr, cls in GPUS:
        if "Direct3D11" in gr:
            assert "(0x" in gr, f"renderer D3D11 tanpa PCI ID: {gr}"
            assert "AMD Radeon" not in gr or "ANGLE (AMD," in gr, \
                f"GPU AMD di bawah vendor bukan-AMD: {gr}"
    for gv, gr, cls in _mk("AMD", _AMD_APU, "igpu"):
        assert gv == "Google Inc. (AMD)", f"APU AMD vendor salah: {gv}"
        assert "ANGLE (AMD," in gr, f"APU AMD renderer salah: {gr}"
    for gv, gr, cls in _mk("Apple", _APPLE_SILICON, "apple", backend="metal"):
        assert "Metal Renderer" in gr, f"Metal hilang: {gr}"
        assert "Apple" in gv, f"vendor Mac bukan Apple: {gv}"
    for gv, gr, cls in _mk("AMD", _AMD_MID, "mid", backend="gl"):
        assert "OpenGL" in gr, f"OpenGL hilang: {gr}"
    # setiap kelas GPU punya layar + cores.
    for cls in ("igpu", "mid", "high", "apple"):
        assert SCREENS.get(cls), f"SCREENS kosong untuk kelas {cls}"
        assert HWS.get(cls), f"HWS kosong untuk kelas {cls}"
    # viewport selalu lebih kecil dari layar (ada chrome browser + taskbar).
    for _ in range(200):
        ident = new_identity()
        vw, vh = ident["vp"]
        assert vw < ident["screen_w"] and vh < ident["screen_h"], \
            f"viewport {ident['vp']} >= layar {ident['screen_w']}x{ident['screen_h']}"
        assert ident["mem"] <= 8 and ident["hw"] >= 1, \
            f"mem/hw aneh: {ident}"
    return True


if __name__ == "__main__":
    if not __package__:
        # Dijalankan langsung (python3 fingerprint/devices.py): jalankan ulang
        # sebagai modul paket supaya relative import (.geo) tetap jalan.
        import os as _os, sys as _sys, runpy as _runpy, warnings as _warnings
        _warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")
        _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        _runpy.run_module("fingerprint.devices", run_name="__main__")
        raise SystemExit(0)
    print("=== TEST devices.py (GLM P2/P4: asserts + self-test) ===")
    print(f"  GPU pool: {len(GPUS)} entri "
          f"(NVIDIA mid {len(_NVIDIA_MID)} / high {len(_NVIDIA_HIGH)}, "
          f"AMD mid {len(_AMD_MID)} / high {len(_AMD_HIGH)} / APU {len(_AMD_APU)}, "
          f"Intel iGPU {len(_INTEL_IGPU)} / mid {len(_INTEL_MID)}, "
          f"Apple {len(_APPLE_SILICON)})")
    print(f"  SCREENS: " + ", ".join(
        f"{c}={len(s)} (max {max(w for w, _, _ in s)}px)" for c, s in SCREENS.items()))
    print(f"  HWS: {HWS}")
    print(f"  MEMS: {MEMS} (Chrome cap 8)")
    check_consistency()
    print("  check_consistency(): 200 identitas acak lolos semua assert")
    print("\n✅ devices.py OK")


