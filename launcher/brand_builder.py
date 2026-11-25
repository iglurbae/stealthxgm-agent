#!/usr/bin/env python3
"""StealthXGM brand extension builder.

Generates a per-profile MV3 extension (in <user-data-dir>/brand_ext/) that
overrides the new tab page with StealthXGM branding + active profile info.

profile_info.json is written at launch time so the new tab always shows the
current profile's identity (name, OS, proxy, fingerprint summary).
"""
import json
import os
import shutil

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brand")
TEMPLATE_FILES = ("manifest.json", "newtab.html", "newtab.css", "newtab.js",
                  "icon16.png", "icon48.png", "icon128.png", "icon.svg")


def _summarize_identity(ident):
    """Extract a JSON-safe fingerprint summary from the runtime identity dict."""
    ident = ident or {}
    gpu = ident.get("gpu") or ident.get("gpu_renderer") or ""
    if isinstance(gpu, dict):
        gpu = gpu.get("renderer", "")
    screen = ident.get("screen") or ""
    if isinstance(screen, dict):
        screen = f"{screen.get('width', '?')}x{screen.get('height', '?')}"
    return {
        "os": ident.get("os") or ident.get("os_name") or "",
        "user_agent": ident.get("user_agent") or ident.get("userAgent") or "",
        "platform": ident.get("platform") or ident.get("navigator_platform") or "",
        "gpu": gpu,
        "screen": screen,
        "timezone": ident.get("timezone") or "",
    }


def build_brand_extension(profile_dir, profile, identity=None, proxy_note=""):
    """Write brand_ext/ under the profile dir. Returns ext path."""
    ext_dir = os.path.join(profile_dir, "brand_ext")
    os.makedirs(ext_dir, exist_ok=True)
    for fname in TEMPLATE_FILES:
        src = os.path.join(TEMPLATE_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(ext_dir, fname))
    info = {
        "brand": "StealthXGM",
        "version": "1.0.0",
        "profile": {
            "id": profile.get("id", ""),
            "name": profile.get("name", "profile"),
            "group": profile.get("group", ""),
            "proxy": proxy_note,
        },
        "fingerprint": _summarize_identity(identity),
        "exit_ip": "",
    }
    with open(os.path.join(ext_dir, "profile_info.json"), "w") as f:
        json.dump(info, f, indent=1, ensure_ascii=False)
    return ext_dir
