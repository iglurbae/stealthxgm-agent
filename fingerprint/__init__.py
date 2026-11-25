"""Fingerprint package — modular layers.

Public API (backward compatible with fingerprint.py):
  spoof_js, new_identity, _fon, _mk,
  GPUS, SCREENS, HWS, MEMS,
  USER_AGENTS, BROWSER_DETAILS, SCREEN_DETAILS,
  auto_identity, auto_spoof_js,
  new_mobile_identity, mobile_spoof_js, auto_mobile_identity,
  spoof_js_webrtc_block, spoof_js_iframe_patch, spoof_js_extra

Layers:
  devices/      - GPU pools, device specs, identity generation
  navigator/    - navigator/browser identity sections
  canvas_audio/ - canvas, audio, WebGL sections
  screen/       - screen/CPU/memory sections
  network/      - network info, geolocation sections
  behavioral/   - behavioral sections (timezone, fonts)
  stealth_extra/- extra patches (WebRTC block, iframe)
  geo/          - geo data, user agents, auto identity
  mobile/       - mobile identity generation
"""
from ._common import _fon
from ._core import spoof_js, spoof_js_worker
from .devices import _mk, GPUS, SCREENS, HWS, MEMS, new_identity
from .geo import USER_AGENTS, BROWSER_DETAILS, SCREEN_DETAILS, _COUNTRY_GEO, auto_identity, auto_spoof_js
from .mobile import (new_mobile_identity, mobile_spoof_js, auto_mobile_identity,
                      mobile_spoof_js_from_dict)
from .network import spoof_js_webrtc_block
from .stealth_extra import spoof_js_iframe_patch, spoof_js_extra

__all__ = [
    "spoof_js", "spoof_js_worker", "new_identity", "_fon", "_mk",
    "GPUS", "SCREENS", "HWS", "MEMS",
    "USER_AGENTS", "BROWSER_DETAILS", "SCREEN_DETAILS", "_COUNTRY_GEO",
    "auto_identity", "auto_spoof_js",
    "new_mobile_identity", "mobile_spoof_js", "auto_mobile_identity",
    "mobile_spoof_js_from_dict",
    "spoof_js_webrtc_block", "spoof_js_iframe_patch", "spoof_js_extra",
]
