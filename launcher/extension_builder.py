#!/usr/bin/env python3
"""
Build the per-profile fingerprint extension.

MV3 content script with "world": "MAIN" + run_at document_start:
the fingerprint JS executes in the page's MAIN world before any page
script — the extension equivalent of CDP Page.addScriptToEvaluateOnNewDocument,
but persistent (no CDP session lifetime issues).

P-17: wired as the SECOND injection layer (headful only) in
launcher.launch_profile(); the injector daemon stays primary because
it also works in --headless=new. Both layers inject the SAME JS;
build_fingerprint_js() once-guard makes double execution a no-op.
"""
import json
import os

MANIFEST = {
    "manifest_version": 3,
    "name": "StealthXGM Fingerprint",
    "version": "1.0.0",
    "description": "Per-profile fingerprint injection (document_start, MAIN world)",
    "content_scripts": [
        {
            "matches": ["<all_urls>"],
            "js": ["inject.js"],
            "run_at": "document_start",
            "all_frames": True,
            "match_about_blank": True,
            "world": "MAIN",
        }
    ],
}


def build_extension(profile_dir, fingerprint_js, profile_name="profile"):
    """Write fp_ext/{manifest.json,inject.js} under the profile dir. Returns ext path."""
    ext_dir = os.path.join(profile_dir, "fp_ext")
    os.makedirs(ext_dir, exist_ok=True)
    manifest = dict(MANIFEST)
    manifest["name"] = f"StealthXGM Fingerprint [{profile_name}]"
    with open(os.path.join(ext_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    with open(os.path.join(ext_dir, "inject.js"), "w") as f:
        f.write(fingerprint_js)
    return ext_dir


# ── P-09: proxy-auth extension ───────────────────────────────────────────
# Chromium modern mengabaikan user:pass di --proxy-server dan memunculkan
# dialog auth yang tidak ada yang mengisinya. Extension MV3 ini menjawab
# challenge proxy (HTTP 407) via webRequest.onAuthRequired. Kredensial
# tinggal di background.js (chmod 600) di dalam user-data-dir profil —
# TIDAK PERNAH di argv / /proc/cmdline.
PROXY_AUTH_MANIFEST = {
    "manifest_version": 3,
    "name": "StealthXGM Proxy Auth",
    "version": "1.0.0",
    "description": "Answers proxy auth challenges (407) for this profile",
    "permissions": ["webRequest", "webRequestAuthProvider"],
    "host_permissions": ["<all_urls>"],
    "background": {"service_worker": "background.js"},
}


def build_proxy_auth_extension(profile_dir, username, password):
    """Write proxy_auth_ext/{manifest.json,background.js} under the profile
    dir. Returns ext path, atau None bila username kosong.

    background.js hanya menjawab bila details.isProxy — kredensial proxy
    TIDAK PERNAH dikirim ke origin server yang minta HTTP auth biasa."""
    if not (username or "").strip():
        return None
    ext_dir = os.path.join(profile_dir, "proxy_auth_ext")
    os.makedirs(ext_dir, exist_ok=True)
    with open(os.path.join(ext_dir, "manifest.json"), "w") as f:
        json.dump(PROXY_AUTH_MANIFEST, f, indent=1)
    # json.dumps untuk escape kredensial yang aman di dalam string JS.
    # Listener SINKRON + ["blocking"]: pola MV3 yang didokumentasikan
    # untuk onAuthRequired (async + "blocking" tidak valid; async butuh
    # "asyncBlocking"). Registrasi dibungkus try/catch + flag diagnostik
    # di globalThis supaya bisa diperiksa dari luar bila auth gagal.
    bg_js = (
        "// StealthXGM proxy auth (P-09) — menjawab 407 dari PROXY saja.\n"
        "const PROXY_USER = " + json.dumps(username) + ";\n"
        "const PROXY_PASS = " + json.dumps(password or "") + ";\n"
        "globalThis.__sxg_proxy_auth_ready = false;\n"
        "globalThis.__sxg_proxy_auth_error = null;\n"
        "try {\n"
        "  chrome.webRequest.onAuthRequired.addListener(\n"
        "    (details) => {\n"
        "      if (!details.isProxy) return {};\n"
        "      return {authCredentials: {username: PROXY_USER, password: PROXY_PASS}};\n"
        "    },\n"
        "    {urls: [\"<all_urls>\"]},\n"
        "    [\"blocking\"]\n"
        "  );\n"
        "  globalThis.__sxg_proxy_auth_ready = true;\n"
        "} catch (e) {\n"
        "  globalThis.__sxg_proxy_auth_error = String(e && e.message || e);\n"
        "}\n"
    )
    bg_path = os.path.join(ext_dir, "background.js")
    with open(bg_path, "w") as f:
        f.write(bg_js)
    try:
        os.chmod(bg_path, 0o600)
    except OSError:
        pass
    return ext_dir
