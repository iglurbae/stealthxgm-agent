"""Extra stealth patches (WebRTC block, iframe patch).

Extracted from fingerprint.py — logic unchanged.
"""
from ._common import _fon
from .network import spoof_js_webrtc_block


def spoof_js_iframe_patch() -> str:
    """Patch iframe detection — bot sering kedetect lewat cross-origin iframe.

    Diadopsi dari identity_kit/layers/stealth_extra.py generate_iframe_patch_js().
    Feature flag: fp_iframe_patch (default ON).
    """
    return """
(() => {
    // Patch window.length (jumlah iframe) — website ngecek ini buat deteksi embed
    try {
        Object.defineProperty(window, 'length', {get: () => 0, configurable: true});
    } catch(e) {}
    // Patch frameElement — harus null buat cross-origin
    try {
        Object.defineProperty(window, 'frameElement', {get: () => null, configurable: true});
    } catch(e) {}
    // Patch window.top === window.self (harus true untuk top-level)
    try {
        Object.defineProperty(window, 'top', {get: () => window, configurable: true});
        Object.defineProperty(window, 'parent', {get: () => window, configurable: true});
    } catch(e) {}
})();
"""




def spoof_js_extra(features=None) -> str:
    """Generate JS patch tambahan (WebRTC block + iframe patch).

    Args:
        features: dict feature flags. None → semua ON (backward compatible).
            - fp_webrtc_block: block RTCPeerConnection (default True)
            - fp_iframe_patch: patch iframe detection (default True)

    Returns:
        str JS siap inject via add_init_script (SETELAH spoof_js utama).
    """
    _F = lambda fid: _fon(features, fid)
    parts = []
    if _F("fp_webrtc_block"):
        parts.append(spoof_js_webrtc_block())
    if _F("fp_iframe_patch"):
        parts.append(spoof_js_iframe_patch())
    return "\n".join(parts)


