#!/usr/bin/env python3
"""Generate the slim WebGL tables shipped with StealthXGM (F10 multi-GPU).

Sources: zendriver-stealth 0.12.7 crate, data/gpu-tiers/*.json
(each file: one MEASURED probe, Chrome 150, see provenance per file).
Download: https://crates.io/api/v1/crates/zendriver-stealth/0.12.7/download
(or docs.rs source view of the same files). Full sources are also kept
in this directory (d3d11-fl11*.json, metal-macos.json, ...).

Output (one slim table per tier — enum->value maps for WebGL1/WebGL2,
extension lists, shader precision, probed unmasked strings):
  webgl-nvidia-d3d11.json       <- d3d11-fl11-nvidia.json  (probed RTX 4090)
  webgl-amd-d3d11.json          <- d3d11-fl11.json         (probed AMD Radeon(TM) Graphics 0x164E, RDNA2 APU)
  webgl-intel-gen9-d3d11.json   <- d3d11-fl11-intel-gen9.json (probed HD Graphics 520 0x1916)
  webgl-apple-metal.json        <- metal-macos.json        (probed Apple M4 Pro)

One tier covers MANY GPU models: the tier values are per-vendor/backend,
not per-model — verified against 8,743 modern Chrome 114-119 D3D11 records
(chrome-fingerprints 10k dataset): 153 param comparisons (51 keys x 3
vendors) = 0 real mismatches; precision digits 12/12 per vendor; extension
lists are a subset of the tier lists (Chrome 150 added 6 webgl1 + 13 webgl2
extensions since 119). See tests/live-reports/tier-vs-dataset-2026-11-08.txt.
The per-MODEL part is the renderer string (PCI device ID), built by
fingerprint/devices.py from pci.ids v2026.11.08 (+ checkproxy.org wild
strings) — NOT from these tables.

Only CAPABILITY/LIMIT params are kept. Mutable GL STATE params are
deliberately EXCLUDED (they must reflect the live context, not a snapshot):
blend/cull/depth/stencil state, viewport/scissor, pack/unpack state,
SAMPLES/SAMPLE_BUFFERS (drawing-buffer state), COMPRESSED_TEXTURE_FORMATS
(the probe serialised it as [] — a real GPU reports S3TC formats;
native returns the real list, so leave it native).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# tier key -> (source file in this dir, slim output file in this dir)
TIERS = {
    "nvidia": ("d3d11-fl11-nvidia.json", "webgl-nvidia-d3d11.json"),
    "amd": ("d3d11-fl11.json", "webgl-amd-d3d11.json"),
    "intel": ("d3d11-fl11-intel-gen9.json", "webgl-intel-gen9-d3d11.json"),
    "apple": ("metal-macos.json", "webgl-apple-metal.json"),
}

# Param names that are mutable GL state (or canvas-size dependent) — never spoof.
STATE_PARAMS = {
    # enable/disable + mode state
    "ACTIVE_TEXTURE", "BLEND", "CULL_FACE", "DEPTH_TEST", "SCISSOR_TEST",
    "STENCIL_TEST", "POLYGON_OFFSET_FILL", "DITHER", "SAMPLE_ALPHA_TO_COVERAGE",
    "SAMPLE_COVERAGE", "RASTERIZER_DISCARD", "TRANSFORM_FEEDBACK_ACTIVE",
    "TRANSFORM_FEEDBACK_PAUSED",
    # value state
    "BLEND_COLOR", "BLEND_DST_ALPHA", "BLEND_DST_RGB", "BLEND_EQUATION",
    "BLEND_EQUATION_ALPHA", "BLEND_EQUATION_RGB", "BLEND_SRC_ALPHA",
    "BLEND_SRC_RGB", "COLOR_CLEAR_VALUE", "CULL_FACE_MODE", "DEPTH_CLEAR_VALUE",
    "DEPTH_FUNC", "DEPTH_RANGE", "DEPTH_WRITEMASK", "FRONT_FACE",
    "GENERATE_MIPMAP_HINT", "LINE_WIDTH", "PACK_ALIGNMENT", "PACK_ROW_LENGTH",
    "PACK_SKIP_PIXELS", "PACK_SKIP_ROWS", "POLYGON_OFFSET_FACTOR",
    "POLYGON_OFFSET_UNITS", "SAMPLE_COVERAGE_INVERT", "SAMPLE_COVERAGE_VALUE",
    "SCISSOR_BOX", "VIEWPORT", "UNPACK_ALIGNMENT",
    "UNPACK_COLORSPACE_CONVERSION_WEBGL", "UNPACK_FLIP_Y_WEBGL",
    "UNPACK_IMAGE_HEIGHT", "UNPACK_PREMULTIPLY_ALPHA_WEBGL",
    "UNPACK_ROW_LENGTH", "UNPACK_SKIP_IMAGES", "UNPACK_SKIP_PIXELS",
    "UNPACK_SKIP_ROWS",
    # stencil state
    "STENCIL_BACK_FAIL", "STENCIL_BACK_FUNC", "STENCIL_BACK_PASS_DEPTH_FAIL",
    "STENCIL_BACK_PASS_DEPTH_PASS", "STENCIL_BACK_REF", "STENCIL_BACK_VALUE_MASK",
    "STENCIL_BACK_WRITEMASK", "STENCIL_CLEAR_VALUE", "STENCIL_FAIL",
    "STENCIL_FUNC", "STENCIL_PASS_DEPTH_FAIL", "STENCIL_PASS_DEPTH_PASS",
    "STENCIL_REF", "STENCIL_VALUE_MASK", "STENCIL_WRITEMASK",
    # draw-buffer / read state
    "DRAW_BUFFER0", "DRAW_BUFFER1", "DRAW_BUFFER2", "DRAW_BUFFER3",
    "DRAW_BUFFER4", "DRAW_BUFFER5", "DRAW_BUFFER6", "DRAW_BUFFER7",
    "READ_BUFFER", "SAMPLES", "SAMPLE_BUFFERS",
    # misc state / hints
    "FRAGMENT_SHADER_DERIVATIVE_HINT", "IMPLEMENTATION_COLOR_READ_FORMAT",
    "IMPLEMENTATION_COLOR_READ_TYPE",
    # probe serialisation artifact (real GPU reports formats; native is right)
    "COMPRESSED_TEXTURE_FORMATS",
}


def build(src_path):
    with open(src_path) as f:
        d = json.load(f)
    cap = d["capture"]
    # F10: provenance lives at TOP level of the tier JSON (F8 read it from
    # inside "capture" and got an empty string — fixed here).
    out = {
        "provenance": d.get("provenance", "")
        + " — zendriver-stealth 0.12.7, data/gpu-tiers/"
        + os.path.basename(src_path),
        "tier": d.get("tier", ""),
        "gpu": {
            "vendor": cap["webgl1"]["unmaskedVendor"],
            "renderer": cap["webgl1"]["unmaskedRenderer"],
        },
    }
    for ver in ("webgl1", "webgl2"):
        w = cap[ver]
        params = {}
        for name, val in w["params"].items():
            if name in STATE_PARAMS:
                continue
            enum = w["enums"][name]
            params[str(enum)] = val
        out[ver] = {"params": params, "extensions": list(w["extensions"])}
    # precision: "SHADER,PRECISION_ENUM" -> [rangeMin, rangeMax, precision]
    shader_enum = {"VERTEX_SHADER": 35633, "FRAGMENT_SHADER": 35632}
    prec_enum = {"LOW_FLOAT": 36336, "MEDIUM_FLOAT": 36337, "HIGH_FLOAT": 36338,
                 "LOW_INT": 36339, "MEDIUM_INT": 36340, "HIGH_INT": 36341}
    prec = {}
    for key, (rmin, rmax, p) in cap["webgl1"]["precision"].items():
        shader, kind = key.split("/")
        prec[f"{shader_enum[shader]},{prec_enum[kind]}"] = [rmin, rmax, p]
    out["precision"] = prec
    # Extension-enum values NOT in the probed params (measured, not guessed):
    # MAX_TEXTURE_MAX_ANISOTROPY_EXT = 16 — mode of 8,743 D3D11 records
    # (all 3 vendors) AND native SwiftShader returns 16.
    # MAX_DRAW_BUFFERS_WEBGL = probed webgl2 MAX_DRAW_BUFFERS of THIS tier
    # (8 in all 4 tiers — read from the tier, not hardcoded).
    out["extra"] = {"MAX_TEXTURE_MAX_ANISOTROPY_EXT": 16,
                    "MAX_DRAW_BUFFERS_WEBGL":
                        cap["webgl2"]["params"]["MAX_DRAW_BUFFERS"]}
    return out


def generate_one(tier_key):
    src_name, dst_name = TIERS[tier_key]
    src = os.path.join(HERE, src_name)
    out = build(src)
    dst = os.path.join(HERE, dst_name)
    with open(dst, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    n1 = len(out["webgl1"]["params"])
    n2 = len(out["webgl2"]["params"])
    print(f"wrote {dst}: webgl1 {n1} params / {len(out['webgl1']['extensions'])} exts, "
          f"webgl2 {n2} params / {len(out['webgl2']['extensions'])} exts, "
          f"precision {len(out['precision'])}")
    print(f"  tier={out['tier']} | probed gpu: {out['gpu']['renderer']}")
    return out


def main():
    if len(sys.argv) > 1 and sys.argv[1] in TIERS:
        generate_one(sys.argv[1])
        return
    if len(sys.argv) > 1:
        print(f"unknown tier {sys.argv[1]!r}; known: {sorted(TIERS)}")
        sys.exit(2)
    for tier_key in TIERS:
        generate_one(tier_key)


if __name__ == "__main__":
    main()
