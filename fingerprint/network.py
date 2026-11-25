"""Network info, geolocation spoofing sections.

Extracted from fingerprint.py — logic unchanged.
"""


def section_network_info() -> str:
    """JS section for feature flag fp_network_info."""
    return """
  // --- Network Information API (consistent with desktop) ---
  // F6 (2026-11-08): def() di NetworkInformation.prototype / Navigator.
  // prototype (dulu di instance conn/navigator).
  try {
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (conn) {
      const _NIProto = Object.getPrototypeOf(conn);
      const _NI = _NIProto ? _NIProto.constructor : null;
      def(_NIProto, 'effectiveType', '4g', _NI);
      def(_NIProto, 'downlink', 10, _NI);
      def(_NIProto, 'rtt', 50, _NI);
      def(_NIProto, 'saveData', false, _NI);
    } else {
      def(Navigator.prototype, 'connection', {
        effectiveType: '4g', downlink: 10, rtt: 50, saveData: false,
        onchange: null, addEventListener: function(){}, removeEventListener: function(){}
      }, Navigator);
    }
  } catch(e) {}

"""


def section_geolocation() -> str:
    """JS section for feature flag fp_geolocation."""
    return """
  // --- H1 (RND 2026-11-03): Geolocation spoof ---
  // F6 (2026-11-08): _nf + definisi di Geolocation.prototype (dulu own
  // property di instance geolocation).
  (() => {
    try {
      if (navigator.geolocation) {
        const _fGC = _nf(function(success, error, options) {
          // Default ke Singapore kalau tidak ada info geo
          // (caller bisa override via ident jika ada lat/lon)
          const _lat = ident.geo_lat || 1.3521;
          const _lon = ident.geo_lon || 103.8198;
          const _pos = {
            coords: {
              latitude: _lat, longitude: _lon, accuracy: 100,
              altitude: null, altitudeAccuracy: null,
              heading: null, speed: null
            },
            timestamp: Date.now()
          };
          if (success) success(_pos);
        }, 'getCurrentPosition', 3);
        Geolocation.prototype.getCurrentPosition = _fGC;
      }
    } catch(e) {}
  })();

"""




def spoof_js_webrtc_block() -> str:
    """Block WebRTC IP leak — website bisa baca IP asli via RTCPeerConnection.

    Diadopsi dari identity_kit/layers/stealth_extra.py generate_webrtc_block_js().
    Feature flag: fp_webrtc_block (default ON).
    """
    return """
(() => {
    // Blokir total RTCPeerConnection biar IP asli gak bocor
    if (window.RTCPeerConnection) {
        const _blocked = function() {
            throw new Error('RTCPeerConnection is not supported');
        };
        window.RTCPeerConnection = _blocked;
        if (window.__markPatched) window.__markPatched(_blocked);
    }
    if (window.webkitRTCPeerConnection) {
        const _blocked2 = function() {
            throw new Error('RTCPeerConnection is not supported');
        };
        window.webkitRTCPeerConnection = _blocked2;
        if (window.__markPatched) window.__markPatched(_blocked2);
    }
    // Blokir getUserMedia yang bisa expose device info
    try {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia = function() {
                return Promise.reject(new Error('Permission denied'));
            };
        }
    } catch(e) {}
})();
"""


if __name__ == "__main__":
    # File ini tanpa import relatif — jalan langsung tanpa bootstrap (GLM P4).
    print("=== TEST network.py (GLM P4: self-test) ===")
    _net = section_network_info()
    for _need in ("effectiveType", "'4g'", "downlink", "rtt", "saveData"):
        assert _need in _net, f"section_network_info kehilangan: {_need}"
    print(f"  section_network_info: {len(_net)} karakter, 4g/downlink/rtt/saveData ada")
    _geo = section_geolocation()
    for _need in ("getCurrentPosition", "geo_lat", "geo_lon", "coords"):
        assert _need in _geo, f"section_geolocation kehilangan: {_need}"
    print(f"  section_geolocation: {len(_geo)} karakter, getCurrentPosition + geo ada")
    _rtc = spoof_js_webrtc_block()
    for _need in ("RTCPeerConnection", "webkitRTCPeerConnection",
                  "getUserMedia", "__markPatched"):
        assert _need in _rtc, f"spoof_js_webrtc_block kehilangan: {_need}"
    print(f"  spoof_js_webrtc_block: {len(_rtc)} karakter, RTC + getUserMedia + trap ada")
    print("\n✅ network.py OK")


