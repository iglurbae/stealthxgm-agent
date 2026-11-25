# Canvas 2D findings — 2026-11-08

VERDICT: METHOD `--disable-accelerated-2d-canvas`. This legitimately fixes the specified CreepJS Blink-allowlist mismatch on this GPU-less VM by selecting native Skia CPU Canvas2D. Full Windows/NVIDIA rendering equivalence is a different, unverified requirement.

## Verified on this VM

I independently launched unmodified Chrome for Testing **159.0.8148.0** and **156.0.8078.4**, headful under an isolated Xvfb, with fresh profiles and no spoof extensions. The drawing operations and Blink samples were extracted from the project's actual `creep.js`, lines 3221–3265. Both binaries produced the same results:

| Canvas path | Four grayscale pixels, row-major; alpha always 255 | Blink allowlist |
| --- | --- | --- |
| Current SwANGLE flags, default Canvas2D | 255, 128, 191, 0 | Outside |
| Same flags + `--disable-accelerated-2d-canvas` | 255, 192, 244, 53 | Inside |

The CPU result's exact native `ImageData.data.join('')` is:

`255255255255192192192255244244244255535353255`

Repeated readbacks were stable. An independent `willReadFrequently: true` context also produced those CPU bytes without the launch flag. **WebGL remained ANGLE/SwiftShader in both launch variants.** Keep the existing `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader` and add only the Canvas2D flag. No pixel replacement, API override, detector recognition, or draw-operation replay is involved.

Raw independent evidence: `/home/hatch/.hermes/cache/scratch/hermes-canvas-backend-results.json`. This research did not modify the launcher or spoof code.

## Other approaches

- **Fonts/Skia settings:** this check resets the canvas and draws rectangles plus an arc, not text. Font files, hinting and DirectWrite/FreeType settings cannot explain or fix this particular mismatch. Selecting the software rasterizer already works with its normal antialiasing.
- **Mesa llvmpipe:** a real CPU rasterizer, not a documented NVIDIA/Windows emulator. It is unnecessary here. The existing project's `f9-canvas-variants.json` trial labelled llvmpipe returned null WebGL; that is not proof Mesa actually rendered the canvas. Likewise, its `--disable-gpu` trial passed the pixel check but lost WebGL. Prefer the Canvas-only flag.

## Published Windows/NVIDIA emulation

**Yes:** [Raphaël Mille describes modified Chromium/SwiftShader](https://raphaelmille.com/blog/emulating-nvidia-canvas/) reproducing Windows NVIDIA Canvas2D against an RTX 3090 reference. The described mechanisms alter sampling/MSAA, numeric conversion, blending/shader behavior and platform text rendering—not fixed detector pixels. However, the author explicitly withholds source. These are published author claims, not an independently verified public implementation or an established RTX 4090 solution.

Being inside an engine allowlist does **not** establish arbitrary Windows/NVIDIA pixel equivalence. No verified public drop-in configuration for that broader goal was established. That does not make custom emulation impossible in principle.

References: [Chromium's Canvas2D switch definition](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/content/public/common/content_switches.cc), [SwiftShader driver versus WebGL-only fallback](https://chromium.googlesource.com/chromium/src/+/main/docs/gpu/swiftshader.md), [Mesa llvmpipe](https://docs.mesa3d.org/drivers/llvmpipe.html).

For the remaining specified flag, the verified legitimate method is **Skia CPU Canvas2D via `--disable-accelerated-2d-canvas`**, while retaining SwiftShader WebGL.
