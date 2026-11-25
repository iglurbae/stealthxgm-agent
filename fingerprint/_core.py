"""Core orchestrator for fingerprint JS generation.

Calls layer section builders in the original order.
Extracted from fingerprint.py — logic unchanged.
"""
import json
import random

from ._common import _fon
from . import navigator
from . import canvas_audio
from . import screen
from . import network
from . import behavioral


# K2 fix (Gil 2026-11-03): locale OTOMATIS dari timezone kalau tidak diisi!
# Jangan default id-ID — kita pakai proxy beda-beda negara!
# Dipakai spoof_js (main thread) DAN spoof_js_worker (F6: worker crash
# bila LOCALE null — new Intl.DateTimeFormat(null) melempar TypeError
# "Cannot convert undefined or null to object" via ToObject(null)).
_TZ_TO_LOCALE = {
    "Asia/Singapore": "en-SG", "Asia/Kuala_Lumpur": "ms-MY",
    "Asia/Jakarta": "id-ID", "Asia/Bangkok": "th-TH",
    "Asia/Manila": "en-PH", "Asia/Ho_Chi_Minh": "vi-VN",
    "Asia/Tokyo": "ja-JP", "Asia/Seoul": "ko-KR",
    "Asia/Hong_Kong": "zh-HK", "Asia/Taipei": "zh-TW",
    "Asia/Dubai": "ar-AE", "Asia/Riyadh": "ar-SA",
    "Asia/Kolkata": "en-IN",
    "America/New_York": "en-US", "America/Toronto": "en-CA",
    "America/Mexico_City": "es-MX", "America/Sao_Paulo": "pt-BR",
    "Europe/London": "en-GB", "Europe/Berlin": "de-DE",
    "Europe/Paris": "fr-FR", "Europe/Amsterdam": "nl-NL",
    "Europe/Madrid": "es-ES", "Europe/Rome": "it-IT",
    "Europe/Lisbon": "pt-PT", "Europe/Stockholm": "sv-SE",
    "Australia/Sydney": "en-AU", "Pacific/Auckland": "en-NZ",
    "Africa/Johannesburg": "en-ZA",
}


def spoof_js(ident, timezone="Asia/Jakarta", locale=None, features=None, seed=None):
    """JavaScript spoofing lengkap — inject via add_init_script SEBELUM page load.

    Gil's original: hardwareConcurrency, deviceMemory, screen, devicePixelRatio,
    WebGL vendor/renderer (WebGL1+WebGL2), canvas/audio noise (AnalyserNode).
    Ditambah: webdriver=false, chrome.runtime, plugins, permissions,
    timezone/locale konsisten ID.

    Args:
        seed: int untuk canvas/audio noise. None -> diturunkan STABIL dari
            hash identitas (P0#3, AUDIT 2026-11-04): noise konsisten per profil,
            beda antar profil. JANGAN random per launch!
    """
    # K2 fix (Gil 2026-11-03): locale OTOMATIS dari timezone kalau tidak diisi!
    # Jangan default id-ID — kita pakai proxy beda-beda negara!
    if locale is None:
        locale = _TZ_TO_LOCALE.get(timezone, "en-US")
    # P0#3 (AUDIT 2026-11-04): seed STABIL per identitas, bukan random per launch.
    # Kalau tidak, canvas hash beda tiap sesi = "device baru tiap sesi" (tell!).
    if seed is None:
        try:
            import hashlib
            _h = hashlib.md5(json.dumps(ident, sort_keys=True, default=str).encode()).hexdigest()
            seed = int(_h[:8], 16)
        except Exception:
            seed = random.randint(1, 2**31)
    _F = lambda fid: _fon(features, fid)
    _parts = []
    _parts.append("""
(() => {
  const ident = %s;
  const TZ = %s;
  const LOCALE = %s;
  // F10 (2026-11-08): tabel WebGL tier identitas ini (null bila tak
  // ter-cover) — satu tabel terukur per tier (nvidia/amd/intel/apple).
  const _WEBGL_TABLE = %s;
  // AUDIT 2026-11-04 P0#1: seed/rnd/noise SELALU didefinisikan di header,
  // BUKAN di section fp_canvas_todataurl. Section lain (battery, perf_memory,
  // audio_buffer, canvas_getimagedata) pakai rnd()/seed — kalau flag canvas
  // OFF mereka ReferenceError. Sekarang aman apa pun kombinasi flag-nya.
  const seed = %d;
  let s = seed;
  const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return (s / 4294967296) - 0.5; };
  const noise = (arr, eps) => { for (let i = 0; i < arr.length; i++) arr[i] += rnd() * eps; };
  // F6 (2026-11-08): _mp fallback kalau fp_tostring_trap OFF.
  // Section tostring_trap akan REASSIGN ini ke marker asli (bukan redeclare —
  // redeclare const = SyntaxError). Tanpa fallback, _mp() = ReferenceError.
  let _mp = (fn) => { try { if (window.__markPatched) window.__markPatched(fn); } catch(e) {} };
  // F6 (2026-11-08): _nf — native-look function wrapper.
  // CreepJS queryLies membedakan fungsi JS biasa vs native lewat:
  //  'prototype' in fn, descriptor keys (harus persis length,name),
  //  new fn() harus throw TypeError, class extends fn harus throw,
  //  setPrototypeOf(fn,null).toString() harus throw TypeError,
  //  fn.arguments / fn.caller harus throw TypeError,
  //  Object.create(fn).toString() stack harus 'at Function.toString',
  //  Object.setPrototypeOf(fn, Object.create(fn)) harus throw (cycle).
  // Fungsi JS BIASA gagal: punya prototype, constructible, .arguments
  // tidak throw. PROXY di atas arrow gagal 2 cek: stack Object.create
  // jadi 'at Object.toString' (bukan 'at Function.toString') karena
  // lookup properti lewat Proxy, dan setPrototypeOf cycle tidak
  // terdeteksi (malah RangeError recursion).
  // CLASS METHOD lulus SEMUANYA (terbukti /tmp/f6_method.py, 0 lie):
  // method tidak punya 'prototype', tidak constructible, SELALU strict
  // (.arguments/.caller throw), punya `this` dinamis (bisa forward
  // receiver ke impl — tidak seperti arrow function), dan merupakan
  // fungsi ASLI (bukan Proxy) sehingga stack & cycle detection sama
  // persis dengan native. Nama method = dispName (computed method name).
  // checkThis (opsional): validator receiver — getter native throw
  // 'Illegal invocation' bila this bukan instance interface yang benar
  // (mis. Navigator.prototype.userAgent). Tanpa ini, queryLies menandai
  // 'failed illegal error'.
  const _nf = (impl, dispName, length, checkThis) => {
    const _name = dispName || impl.name || '';
    const _cls = class { [_name](...args) {
      if (checkThis && !checkThis(this)) throw new TypeError('Illegal invocation');
      return impl.apply(this, args);
    } };
    const _m = _cls.prototype[_name];
    try { Object.defineProperty(_m, 'length', { value: (length === undefined ? (impl.length || 0) : length), configurable: true }); } catch(e) {}
    _mp(_m);
    return _m;
  };
  // F6 (2026-11-08): def() — getter di PROTOTYPE (bukan instance!) + _nf.
  // Sebelumnya def(navigator/screen/window, ...) bikin own property di
  // instance — queryLies 'failed undefined properties' (navigator/screen
  // HARUS accessor di prototype, bukan own property). Sekarang caller
  // WAJIB passing prototype + interface untuk receiver check.
  //   def(Navigator.prototype, 'platform', ident.platform, Navigator)
  const def = (obj, prop, val, iface) => {
    try {
      const _check = iface ? ((t) => { try { return t instanceof iface; } catch(e) { return false; } }) : null;
      const _g = _nf(function() { return val; }, 'get ' + prop, 0, _check);
      Object.defineProperty(obj, prop, { get: _g, configurable: true });
    } catch(e) {}
  };
  // F6 (2026-11-08): offset teks canvas per profil (deterministik dari seed).
  // Dipakai fillText/strokeText — noise piksel di toDataURL/getImageData
  // DIHAPUS (read-back harus eksak; CreepJS getPixelMods mendeteksi noise
  // sebagai '6 persen rgba noise'). Offset mengubah raster anti-alias
  // secara konsisten (toDataURL/getImageData/round-trip sama), beda antar
  // profil, stabil dalam satu profil (seed sama -> offset sama, termasuk
  // di worker — worker pakai seed yang sama).
  // F6-rev (2026-11-08): offset 0.3px TIDAK ANDAL — hash canvas fungsi
  // diskrit, geseran <0.3px sering tidak melewati ambang kuantisasi
  // (bukti: p16-cons-b1 vs b2 hash identik edb69da0). Offset +-1px:
  // tetap rendering asli (bukan noise read-back — CreepJS tidak memeriksa
  // posisi absolut teks; measureText tidak di-offset jadi konsisten),
  // dan geseran 1px andal mengubah banyak piksel -> hash beda antar profil.
  const _textDX = rnd() * 2.0;
  const _textDY = rnd() * 2.0;
""")
    # ── Sections in original order ──
    if _F("fp_tostring_trap"):
        _parts.append(navigator.section_tostring_trap())
    if _F("fp_useragent"):
        _parts.append(navigator.section_useragent())
    if _F("fp_webdriver_remove"):
        _parts.append(navigator.section_webdriver_remove())
    if _F("fp_cpu_cores"):
        _parts.append(screen.section_cpu_cores())
    if _F("fp_platform"):
        _parts.append(navigator.section_platform())
    if _F("fp_gpu_vendor"):
        _parts.append(canvas_audio.section_gpu_vendor())
    if _F("fp_canvas_todataurl"):
        _parts.append(canvas_audio.section_canvas_todataurl())
    if _F("fp_chrome_runtime"):
        _parts.append(navigator.section_chrome_runtime())
    if _F("fp_languages"):
        _parts.append(navigator.section_languages())
    if _F("fp_storage"):
        _parts.append(navigator.section_storage())
    if _F("fp_battery"):
        _parts.append(navigator.section_battery())
    if _F("fp_network_info"):
        _parts.append(network.section_network_info())
    if _F("fp_enumerate_devices"):
        _parts.append(navigator.section_enumerate_devices())
    if _F("fp_client_hints"):
        _parts.append(navigator.section_client_hints())
    if _F("fp_audio_buffer"):
        _parts.append(canvas_audio.section_audio_buffer())
    if _F("fp_plugins"):
        _parts.append(navigator.section_plugins())
    if _F("fp_fonts"):
        _parts.append(behavioral.section_fonts())
    if _F("fp_webgl_extensions"):
        _parts.append(canvas_audio.section_webgl_extensions())
    if _F("fp_canvas_getimagedata"):
        _parts.append(canvas_audio.section_canvas_getimagedata())
    if _F("fp_audio_samplerate"):
        _parts.append(canvas_audio.section_audio_samplerate())
    if _F("fp_voices"):
        _parts.append(navigator.section_voices())
    if _F("fp_webgl_shader"):
        _parts.append(canvas_audio.section_webgl_shader())
    if _F("fp_perf_memory"):
        _parts.append(navigator.section_perf_memory())
    if _F("fp_timezone_offset"):
        _parts.append(behavioral.section_timezone_offset())
    if _F("fp_geolocation"):
        _parts.append(network.section_geolocation())
    if _F("fp_datetostring"):
        _parts.append(navigator.section_datetostring())
    if _F("fp_webgpu"):
        _parts.append(canvas_audio.section_webgpu())
    # AUDIT 2026-11-04 P0#1: Intl timezone/locale spoof SELALU ON.
    # Dulu nempel di section fp_webgpu — kalau flag OFF, timezone ikut mati
    # = Date().toString vs getTimezoneOffset inkonsisten (tell!).
    # F6 (2026-11-08): SEMUA constructor Intl di-wrap — sebelumnya hanya
    # DateTimeFormat; NumberFormat/Collator/PluralRules/ListFormat/
    # RelativeTimeFormat/DisplayNames/Segmenter masih mengembalikan locale
    # default 'en-US' padahal navigator.language = LOCALE (mis. id-ID)
    # -> CreepJS Intl pink. Wrapper constructor TIDAK di-_nf (harus bisa
    # di-new); constructor Intl tidak diuji queryLies — hanya method
    # instance-nya yang diuji, dan wrapper mengembalikan instance ASLI
    # jadi method-nya native. _mp supaya toString-nya native-format.
    _parts.append("""
  // --- K4 (decoupled dari fp_webgpu): Intl pakai LOCALE + TZ spoof ---
  try {
    const _wrapIntl = (RealCtor, fixOpts) => {
      const _f = function() {
        const args = Array.prototype.slice.call(arguments);
        let loc = args.length > 0 ? args[0] : undefined;
        let opts = (args.length > 1 && args[1] && typeof args[1] === 'object') ? Object.assign({}, args[1]) : {};
        if (!loc) loc = LOCALE;
        opts = fixOpts(opts);
        const _inst = new RealCtor(loc, opts);
        // F7B (2026-11-08): ICU menyelesaikan LOCALE ke bahasa dasar untuk
        // sebagian ctor (terbukti: PluralRules('id-ID') -> 'id', ctor lain
        // -> 'id-ID'); mesin id-ID asli melaporkan 'id-ID' untuk panggilan
        // tanpa argumen (default path). Normalisasi resolvedOptions()
        // instance ini ke LOCALE bila hasilnya bahasa dasar LOCALE, supaya
        // semua ctor sepakat pada satu locale (CreepJS getLocale()).
        // _nf supaya toString tetap native (queryLies) — sama seperti
        // getter lain di file ini.
        try {
          const _base = LOCALE.split('-')[0];
          const _realRO = _inst.resolvedOptions.bind(_inst);
          _inst.resolvedOptions = _nf(function() {
            const _r = _realRO();
            if (_r && _r.locale === _base) _r.locale = LOCALE;
            return _r;
          }, 'resolvedOptions', 0);
        } catch(e) {}
        return _inst;
      };
      try { Object.defineProperty(_f, 'name', { value: RealCtor.name, configurable: true }); } catch(e) {}
      _mp(_f);
      _f.prototype = RealCtor.prototype;
      try { _f.supportedLocalesOf = RealCtor.supportedLocalesOf.bind(RealCtor); } catch(e) {}
      return _f;
    };
    if (typeof Intl !== 'undefined') {
      if (Intl.DateTimeFormat) Intl.DateTimeFormat = _wrapIntl(Intl.DateTimeFormat, function(o) { if (!o.timeZone) o.timeZone = TZ; return o; });
      if (Intl.NumberFormat) Intl.NumberFormat = _wrapIntl(Intl.NumberFormat, function(o) { return o; });
      if (Intl.Collator) Intl.Collator = _wrapIntl(Intl.Collator, function(o) { return o; });
      if (Intl.PluralRules) Intl.PluralRules = _wrapIntl(Intl.PluralRules, function(o) { return o; });
      if (Intl.ListFormat) Intl.ListFormat = _wrapIntl(Intl.ListFormat, function(o) { return o; });
      if (Intl.RelativeTimeFormat) Intl.RelativeTimeFormat = _wrapIntl(Intl.RelativeTimeFormat, function(o) { return o; });
      if (Intl.DisplayNames) Intl.DisplayNames = _wrapIntl(Intl.DisplayNames, function(o) { return o; });
      if (Intl.Segmenter) Intl.Segmenter = _wrapIntl(Intl.Segmenter, function(o) { return o; });
    }
  } catch(e) {}
""")
    # AUDIT 2026-11-04 P0#1: penutup IIFE SELALU ada di sini.
    # Dulu penutup `})();` nempel di ujung section fp_webgpu — kalau flag OFF,
    # IIFE tidak pernah ditutup -> SyntaxError -> SELURUH fingerprint mati!
    _parts.append("""
})();
""")
    _js = "\n".join(_parts)
    # Urutan placeholder header: ident, TZ, LOCALE, _WEBGL_TABLE, seed.
    _args = [json.dumps(ident), json.dumps(timezone), json.dumps(locale),
             canvas_audio.webgl_table_js_literal_for(
                 (ident or {}).get("gpu_renderer", "")), seed]
    return _js % tuple(_args)


def spoof_js_worker(ident, timezone="Asia/Jakarta", locale=None, seed=None):
    """JavaScript spoof untuk WORKER scope (dedicated/shared/service worker).

    F6 (2026-11-08): leak #1 — worker TIDAK ikut di-spoof. Main thread:
    Windows/Jakarta/id-ID/12 core/4 GB; worker: Linux X11/UTC/en-US/4 core/
    8 GB. CreepJS menjalankan tes yang sama di worker dan membandingkan.
    JS ini di-inject via CDP Runtime.evaluate ke setiap worker target
    (Target.setAutoAttach + waitForDebuggerOnStart) oleh worker_injector.js.

    Self-contained: IIFE dengan guard Symbol.for('sxgw') (idempotent),
    infrastruktur sendiri (_mp/_nf/def/trap — sama seperti main thread),
    seed SAMA dengan main thread supaya offset teks canvas & noise
    deterministik identik (paintURI main == paintCpuURI worker).
    WorkerNavigator TIDAK punya webdriver/plugins/storage/gpu/connection —
    yang di-patch hanya yang ada: userAgent, platform, languages, language,
    hardwareConcurrency, deviceMemory, appVersion, vendor, userAgentData.
    """
    # K2 fix — SAMA seperti spoof_js: locale dari timezone bila None.
    # Tanpa ini LOCALE=null dan new Intl.DateTimeFormat() di worker melempar
    # TypeError "Cannot convert undefined or null to object" (ToObject(null)).
    if locale is None:
        locale = _TZ_TO_LOCALE.get(timezone, "en-US")
    # F10 (2026-11-08): seed STABIL per identitas bila caller tak pass
    # (SAMA seperti spoof_js) — sebelumnya spoof_js_worker(ident) tanpa
    # seed melempar TypeError "%d format" (ditemukan test F10); produksi
    # selama ini selalu pass seed eksplisit (launcher.py:1203) jadi
    # perilaku produksi tak berubah.
    if seed is None:
        try:
            import hashlib
            _h = hashlib.md5(json.dumps(ident, sort_keys=True, default=str).encode()).hexdigest()
            seed = int(_h[:8], 16)
        except Exception:
            seed = random.randint(1, 2**31)
    _js = r"""
(() => {
  try { if (self[Symbol.for('sxgw')]) return; self[Symbol.for('sxgw')] = true; } catch(e) {}
  const ident = %s;
  const TZ = %s;
  const LOCALE = %s;
  const seed = %d;
  // F10 (2026-11-08): tabel WebGL tier identitas ini (null bila tak ter-cover).
  const _WEBGL_TABLE = %s;
  let s = seed;
  const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return (s / 4294967296) - 0.5; };
  let _mp = (fn) => {};
  // toString trap — CLASS METHOD (lihat navigator.py section_tostring_trap).
  // F7 (2026-11-08): CROSS-REALM delegation, sama seperti main thread —
  // plus _mp(_tTrap): trap worker SEBELUMNYA tidak menandai dirinya sendiri
  // (tidak ada _mp(_tTrap)), sehingga toString milik trap worker dibocorkan
  // native toString -> semua fungsi worker "failed toString" -> Worker pink.
  try {
    const _patched = new WeakSet();
    const _nativeToString = Function.prototype.toString;
    const _trapCls = class { toString(...args) {
      try {
        if (_patched.has(this)) {
          const _n = this.name || '';
          return _n ? ('function ' + _n + '() { [native code] }') : 'function () { [native code] }';
        }
      } catch(e) {}
      try {
        if (typeof this === 'function') {
          const _home = Object.getPrototypeOf(this);
          const _homeToString = _home && _home.toString;
          if (typeof _homeToString === 'function' && _homeToString !== _trapCls.prototype.toString) {
            return Reflect.apply(_homeToString, this, args);
          }
        }
      } catch(e) {}
      return Reflect.apply(_nativeToString, this, args);
    } };
    const _tTrap = _trapCls.prototype.toString;
    Function.prototype.toString = _tTrap;
    _mp = (fn) => { try { _patched.add(fn); } catch(e) {} };
    _mp(_tTrap);
  } catch(e) {}
  const _nf = (impl, dispName, length, checkThis) => {
    const _name = dispName || impl.name || '';
    const _cls = class { [_name](...args) {
      if (checkThis && !checkThis(this)) throw new TypeError('Illegal invocation');
      return impl.apply(this, args);
    } };
    const _m = _cls.prototype[_name];
    try { Object.defineProperty(_m, 'length', { value: (length === undefined ? (impl.length || 0) : length), configurable: true }); } catch(e) {}
    _mp(_m);
    return _m;
  };
  const def = (obj, prop, val, iface) => {
    try {
      const _check = iface ? ((t) => { try { return t instanceof iface; } catch(e) { return false; } }) : null;
      const _g = _nf(function() { return val; }, 'get ' + prop, 0, _check);
      Object.defineProperty(obj, prop, { get: _g, configurable: true });
    } catch(e) {}
  };
  // F6-rev (2026-11-08): +-1px — sama seperti main thread (offset 0.3px
  // tidak andal membedakan hash antar profil; lihat komentar di spoof_js).
  const _textDX = rnd() * 2.0;
  const _textDY = rnd() * 2.0;
  // --- WorkerNavigator (prototype via getPrototypeOf — paling robust) ---
  try {
    const _WNProto = Object.getPrototypeOf(self.navigator);
    const _WN = _WNProto ? _WNProto.constructor : null;
    if (_WNProto) {
      def(_WNProto, 'userAgent', ident._ua, _WN);
      def(_WNProto, 'appVersion', ident.app_ver, _WN);
      def(_WNProto, 'platform', ident.platform, _WN);
      def(_WNProto, 'vendor', ident.vendor || 'Google Inc.', _WN);
      def(_WNProto, 'languages', (function() {
        // Sama seperti main thread (navigator.py section_languages):
        // [locale, base, en-US, en] — mis. id-ID -> [id-ID, id, en-US, en].
        if (ident.languages && ident.languages.length) return ident.languages.slice();
        const _lang = LOCALE || 'id-ID';
        const _base = _lang.split('-')[0];
        const _l = [_lang];
        if (_base !== _lang) _l.push(_base);
        if (_l.indexOf('en-US') === -1) _l.push('en-US');
        if (_l.indexOf('en') === -1) _l.push('en');
        return _l;
      })(), _WN);
      def(_WNProto, 'language', LOCALE, _WN);
      def(_WNProto, 'hardwareConcurrency', ident.hw, _WN);
      def(_WNProto, 'deviceMemory', ident.mem, _WN);
      def(_WNProto, 'onLine', true, _WN);
      // userAgentData (WorkerNavigator, Chrome baru).
      // F7 (2026-11-08): definisikan TANPA gate 'userAgentData' in _WNProto —
      // gate lama melewatkan definisi bila native tidak ada, padahal Chrome
      // 159 asli PUNYA userAgentData di worker; dan samakan platformVersion
      // Windows dengan main thread ('15.0.0', dulu worker '10.0.0' —
      // inkonsisten main vs worker).
      try {
        if (_WNProto) {
          const _origGetHE = (self.navigator.userAgentData && self.navigator.userAgentData.getHighEntropyValues) ? self.navigator.userAgentData.getHighEntropyValues.bind(self.navigator.userAgentData) : null;
          const _uad = {
            brands: [{ brand: 'Google Chrome', version: String(ident.chrome_ver || '') }, { brand: 'Chromium', version: String(ident.chrome_ver || '') }, { brand: 'Not-A.Brand', version: '99' }],
            mobile: false,
            platform: (ident.platform === 'Win32' ? 'Windows' : (ident.platform === 'MacIntel' ? 'macOS' : 'Linux')),
            getHighEntropyValues: _nf(function() {
              return Promise.resolve({ architecture: 'x86', bitness: '64', brands: _uad.brands, fullVersionList: _uad.brands, mobile: false, model: '', platform: _uad.platform, platformVersion: (ident.platform === 'Win32' ? '15.0.0' : ''), uaFullVersion: String(ident.chrome_ver || ''), wow64: false });
            }, 'getHighEntropyValues', 1)
          };
          def(_WNProto, 'userAgentData', _uad, _WN);
        }
      } catch(e) {}
    }
  } catch(e) {}
  // --- Intl: semua constructor pakai LOCALE + TZ ---
  try {
    const _wrapIntl = (RealCtor, fixOpts) => {
      const _f = function() {
        const args = Array.prototype.slice.call(arguments);
        let loc = args.length > 0 ? args[0] : undefined;
        let opts = (args.length > 1 && args[1] && typeof args[1] === 'object') ? Object.assign({}, args[1]) : {};
        if (!loc) loc = LOCALE;
        opts = fixOpts(opts);
        const _inst = new RealCtor(loc, opts);
        // F7B (2026-11-08): sama seperti main thread — ICU menyelesaikan
        // LOCALE ke bahasa dasar untuk sebagian ctor (PluralRules('id-ID')
        // -> 'id'); normalisasi resolvedOptions() instance ini ke LOCALE
        // bila hasilnya bahasa dasar LOCALE, supaya getLocale() worker
        // sepakat satu locale ('id-ID') dan cocok dengan navigator.language.
        try {
          const _base = LOCALE.split('-')[0];
          const _realRO = _inst.resolvedOptions.bind(_inst);
          _inst.resolvedOptions = _nf(function() {
            const _r = _realRO();
            if (_r && _r.locale === _base) _r.locale = LOCALE;
            return _r;
          }, 'resolvedOptions', 0);
        } catch(e) {}
        return _inst;
      };
      try { Object.defineProperty(_f, 'name', { value: RealCtor.name, configurable: true }); } catch(e) {}
      _mp(_f);
      _f.prototype = RealCtor.prototype;
      try { _f.supportedLocalesOf = RealCtor.supportedLocalesOf.bind(RealCtor); } catch(e) {}
      return _f;
    };
    if (typeof Intl !== 'undefined') {
      if (Intl.DateTimeFormat) Intl.DateTimeFormat = _wrapIntl(Intl.DateTimeFormat, function(o) { if (!o.timeZone) o.timeZone = TZ; return o; });
      if (Intl.NumberFormat) Intl.NumberFormat = _wrapIntl(Intl.NumberFormat, function(o) { return o; });
      if (Intl.Collator) Intl.Collator = _wrapIntl(Intl.Collator, function(o) { return o; });
      if (Intl.PluralRules) Intl.PluralRules = _wrapIntl(Intl.PluralRules, function(o) { return o; });
      if (Intl.ListFormat) Intl.ListFormat = _wrapIntl(Intl.ListFormat, function(o) { return o; });
      if (Intl.RelativeTimeFormat) Intl.RelativeTimeFormat = _wrapIntl(Intl.RelativeTimeFormat, function(o) { return o; });
      if (Intl.DisplayNames) Intl.DisplayNames = _wrapIntl(Intl.DisplayNames, function(o) { return o; });
      if (Intl.Segmenter) Intl.Segmenter = _wrapIntl(Intl.Segmenter, function(o) { return o; });
    }
  } catch(e) {}
  // --- Date.getTimezoneOffset ---
  try {
    const _origGTO = Date.prototype.getTimezoneOffset;
    const _fGTO = _nf(function() {
      try {
        const _local = new Date(this.getTime());
        const _tzDate = new Date(_local.toLocaleString('en-US', { timeZone: TZ }));
        const _utcDate = new Date(_local.toLocaleString('en-US', { timeZone: 'UTC' }));
        const _offsetMin = Math.round((_tzDate - _utcDate) / 60000);
        return -_offsetMin;
      } catch(e) { return _origGTO.call(this); }
    }, 'getTimezoneOffset', 0);
    Date.prototype.getTimezoneOffset = _fGTO;
  } catch(e) {}
  // --- OffscreenCanvas 2D: offset teks (seed sama -> sama dengan main) ---
  try {
    const _OC2D = self.OffscreenCanvasRenderingContext2D;
    if (_OC2D) {
      const _origFill = _OC2D.prototype.fillText;
      const _origStroke = _OC2D.prototype.strokeText;
      if (_origFill) {
        _OC2D.prototype.fillText = _nf(function(text, x, y, maxWidth) {
          return _origFill.call(this, text, x + _textDX, y + _textDY, maxWidth);
        }, 'fillText', 4);
      }
      if (_origStroke) {
        _OC2D.prototype.strokeText = _nf(function(text, x, y, maxWidth) {
          return _origStroke.call(this, text, x + _textDX, y + _textDY, maxWidth);
        }, 'strokeText', 4);
      }
    }
  } catch(e) {}
  // --- WebGL getParameter (OffscreenCanvas webgl) ---
  // F8 (2026-11-08): SAMA seperti main thread — tabel RTX 4090 terukur
  // (fingerprint/data/webgl-rtx4090-d3d11.json) bila identitas klaim
  // RTX 4090; bila tidak, perilaku lama (hanya 0x9245/0x9246). Nilai STATE
  // tidak di-spoof (native).
  // F10 (2026-11-08): SAMA seperti main thread — tabel tier identitas
  // (_WEBGL_TABLE, null bila tak ter-cover). 0x9245/0x9246 mengembalikan
  // string identitas (_gv/_gr — devices.py sudah per-model + PCI ID).
  // getSupportedExtensions / getShaderPrecisionFormat juga memakai tabel
  // bila aktif, else pass-through native (dulu sudah di-wrap _nf untuk
  // kebersihan toString — dipertahankan).
  try {
    const _gv = ident.gpu_vendor || null;
    const _gr = ident.gpu_renderer || null;
    const _wTableOn = () => { try { return !!_WEBGL_TABLE; } catch(e) { return false; } };
    const _wTableParam = (isGL2, p) => {
      try {
        const _m = isGL2 ? _WEBGL_TABLE.webgl2.params : _WEBGL_TABLE.webgl1.params;
        if (Object.prototype.hasOwnProperty.call(_m, p)) {
          const _v = _m[p];
          if (Array.isArray(_v)) return { hit: true, value: new (p === 0x0D3A ? Int32Array : Float32Array)(_v) };
          return { hit: true, value: _v };
        }
        if (p === 0x84FF) return { hit: true, value: _WEBGL_TABLE.extra.MAX_TEXTURE_MAX_ANISOTROPY_EXT };
        if (p === 0x8824) return { hit: true, value: _WEBGL_TABLE.extra.MAX_DRAW_BUFFERS_WEBGL };
        if (p === 0x9245) return { hit: true, value: _gv || 'Google Inc.' };
        if (p === 0x9246) return { hit: true, value: _gr || 'ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)' };
      } catch(e) {}
      return { hit: false };
    };
    const _patchGL = (Ctor, isGL2) => {
      if (!Ctor) return;
      try {
        const _orig = Ctor.prototype.getParameter;
        if (!_orig) return;
        const _f = _nf(function(p) {
          if (_wTableOn()) {
            const _r = _wTableParam(isGL2, p);
            if (_r.hit) return _r.value;
          }
          try {
            if (p === 37445) return _gv || 'Google Inc.';
            if (p === 37446) return _gr || 'ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)';
          } catch(e) {}
          return _orig.call(this, p);
        }, 'getParameter', 1);
        Ctor.prototype.getParameter = _f;
      } catch(e) {}
      try {
        const _origGSE = Ctor.prototype.getSupportedExtensions;
        if (_origGSE) {
          const _f2 = _nf(function() {
            try {
              if (_wTableOn()) return (isGL2 ? _WEBGL_TABLE.webgl2.extensions : _WEBGL_TABLE.webgl1.extensions).slice();
            } catch(e) {}
            try { const r = _origGSE.call(this); return r ? r.slice() : r; } catch(e) { return _origGSE.call(this); }
          }, 'getSupportedExtensions', 0);
          Ctor.prototype.getSupportedExtensions = _f2;
        }
      } catch(e) {}
      try {
        const _origGSPF = Ctor.prototype.getShaderPrecisionFormat;
        if (_origGSPF) {
          const _f3 = _nf(function(sh, pt) {
            try {
              if (_wTableOn()) {
                const _e = _WEBGL_TABLE.precision[sh + ',' + pt];
                if (_e) return { rangeMin: _e[0], rangeMax: _e[1], precision: _e[2] };
              }
            } catch(e) {}
            return _origGSPF.apply(this, arguments);
          }, 'getShaderPrecisionFormat', 2);
          Ctor.prototype.getShaderPrecisionFormat = _f3;
        }
      } catch(e) {}
    };
    _patchGL(self.WebGLRenderingContext, false);
    _patchGL(self.WebGL2RenderingContext, true);
  } catch(e) {}
  // --- FontFace.load (font klaim OS harus resolve) ---
  try {
    const WIN_FONTS = new Set([
      'Arial','Arial Black','Arial Narrow','Calibri','Cambria','Candara','Comic Sans MS',
      'Consolas','Constantia','Corbel','Courier New','Georgia','Impact','Lucida Console',
      'Lucida Sans Unicode','Microsoft Sans Serif','Palatino Linotype','Segoe UI',
      'Segoe UI Symbol','Tahoma','Times New Roman','Trebuchet MS','Verdana',
      'Segoe MDL2 Assets','Segoe UI Emoji','Segoe UI Historic',
      'MS Gothic','MS PGothic','Meiryo','Meiryo UI','Malgun Gothic','Microsoft YaHei',
      'Microsoft JhengHei','SimSun','PMingLiU','Yu Gothic','Yu Gothic UI',
      // F7 (2026-11-08): font penanda versi Windows (CreepJS FONT_LIST hanya
      // berisi font ini). Mesin Win11 asli MEMILIKI semuanya. Sinkron dengan
      // behavioral.section_fonts().
      'Cambria Math','Aldhabi','Gadugi','Myanmar Text','Nirmala UI',
      'Leelawadee UI','Javanese Text','HoloLens MDL2 Assets','Bahnschrift',
      'Ink Free','Segoe Fluent Icons'
    ]);
    const MAC_FONTS = new Set([
      'Helvetica','Helvetica Neue','Arial','Times','Times New Roman','Courier',
      'Courier New','Verdana','Georgia','Palatino','Garamond','Bookman',
      'Comic Sans MS','Trebuchet MS','Arial Black','Impact','Lucida Grande',
      'Geneva','Monaco','Andale Mono','San Francisco','SF Pro Text','SF Pro Display',
      'Apple Color Emoji','Apple SD Gothic Neo','PingFang SC','Hiragino Sans GB'
    ]);
    const LINUX_FONTS = new Set([
      'DejaVu Sans','DejaVu Serif','DejaVu Sans Mono','Liberation Sans',
      'Liberation Serif','Liberation Mono','Noto Sans','Noto Serif',
      'Noto Sans Mono','Ubuntu','Ubuntu Mono','Cantarell','Droid Sans',
      'Droid Serif','Droid Sans Mono','Roboto','Arial','Times New Roman',
      'Courier New','Verdana','Georgia','Trebuchet MS','Comic Sans MS',
      'Impact','Tahoma','Helvetica'
    ]);
    const FONT_SET = (ident.platform === 'MacIntel') ? MAC_FONTS
      : ((ident.platform || '').indexOf('Linux') === 0 ? LINUX_FONTS : WIN_FONTS);
    if (self.FontFace && self.FontFace.prototype && self.FontFace.prototype.load) {
      const _origLoad = self.FontFace.prototype.load;
      const _fLoad = _nf(function() {
        try {
          const fam = String(this.family || '').replace(/^['"]|['"]$/g, '');
          if (fam && FONT_SET.has(fam)) return Promise.resolve(this);
        } catch(e) {}
        return _origLoad.call(this);
      }, 'load', 0);
      self.FontFace.prototype.load = _fLoad;
    }
  } catch(e) {}
})();
"""
    _args = [json.dumps(ident), json.dumps(timezone), json.dumps(locale), seed,
             canvas_audio.webgl_table_js_literal_for(
                 (ident or {}).get("gpu_renderer", ""))]
    return _js % tuple(_args)
