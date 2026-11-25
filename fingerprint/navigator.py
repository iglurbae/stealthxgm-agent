"""Navigator/browser identity spoofing sections.

Extracted from fingerprint.py — logic unchanged.
"""


def section_tostring_trap() -> str:
    """JS section for feature flag fp_tostring_trap."""
    return """
  // --- 1A (RND 2026-11-03): ANTI ma() — toString trap, HARUS PALING AWAL! ---
  // Turnstile cek Function.toString.call(fn).indexOf("[native code]")
  // Semua fungsi yang kita patch harus return "[native code]"
  // F6 (2026-11-08): trap = CLASS METHOD (bukan Proxy, bukan plain fn).
  // Plain fn gagal: .arguments/.caller tidak throw -> 'failed at toString
  // incompatible proxy error' di SEMUA fungsi (termasuk native).
  // Proxy gagal 3 cek (terbukti /tmp/f6_lies.py): 'failed object toString
  // error' (stack jadi 'at Object.toString'), 'failed at too much
  // recursion error' (setPrototypeOf cycle tidak terdeteksi -> RangeError),
  // 'failed at reflect set proto' (RAND in proxy -> recursion).
  // Class method lulus semuanya (terbukti /tmp/f6_method.py): tidak punya
  // 'prototype', tidak constructible, SELALU strict (.arguments throw),
  // fungsi ASLI (stack & cycle detection sama persis dengan native),
  // dan `this` dinamis (bisa cek _patched.has(this)).
  // F7 (2026-11-08): CROSS-REALM delegation. CreepJS menguji fungsi main
  // window lewat toString milik IFRAME phantom/behemoth (scope). Trap di
  // iframe tidak bisa melihat _patched WeakSet realm utama, jadi jatuh ke
  // native toString dan membocorkan source fungsi yang di-patch (terbukti:
  // 1505 "failed toString" di halaman prototype, semua section pink yang
  // berbasis lieProps di halaman utama). Perbaikan: tanya toString milik
  // realm-nya fungsi itu sendiri — Object.getPrototypeOf(fn) adalah
  // Function.prototype realm asal, yang .toString-nya adalah trap realm
  // itu (atau native bila realm itu tidak di-patch). Dijaga: hanya bila
  // `this` berupa function, hanya bila home toString BUKAN trap ini
  // sendiri (tanpa self-recursion), dan throw apa pun jatuh ke native.
  // Fungsi user TIDAK disentuh: realm yang tidak di-patch mengembalikan
  // source asli lewat native toString-nya.
  (() => {
    const _origToString = Function.prototype.toString;
    const _patched = new WeakSet();
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
      return Reflect.apply(_origToString, this, args);
    } };
    const _tTrap = _trapCls.prototype.toString;
    Function.prototype.toString = _tTrap;
    window.__markPatched = (fn) => { try { _patched.add(fn); } catch(e) {} };
    if (window.__markPatched) window.__markPatched(Function.prototype.toString);
  })();
  // AUDIT 2026-11-04 P0#2: REASSIGN (bukan redeclare!) _mp dari header _core.py.
  // Header sudah deklarasikan `let _mp` fallback — `const _mp` di sini =
  // SyntaxError (redeclaration). Assignment ini mengaktifkan marker asli.
  _mp = (fn) => { try { if (window.__markPatched) window.__markPatched(fn); } catch(e) {} };

"""


def section_useragent() -> str:
    """JS section for feature flag fp_useragent."""
    return """
  // --- M4 (RND 2026-11-03): navigator.userAgent match UA (di prototype!) ---
  // F6 (2026-11-08): def() — getter di prototype + _nf + receiver check
  // (dulu plain named function; queryLies 'failed illegal error' karena
  // getter tidak throw saat diakses lewat prototype).
  def(Navigator.prototype, 'userAgent', ident._ua, Navigator);

"""


def section_webdriver_remove() -> str:
    """JS section for feature flag fp_webdriver_remove."""
    return """
  // --- H3 (RND 2026-11-03): webdriver accessor di prototype, BUKAN own property ---
  // F6 (2026-11-08): def() — getter di prototype + _nf + receiver check.
  try {
    try { delete navigator.webdriver; } catch(e) {}
    def(Navigator.prototype, 'webdriver', false, Navigator);
  } catch(e) {}

"""


def section_platform() -> str:
    """JS section for feature flag fp_platform."""
    return """
  // --- BARU (Gil 2026-11-02 15:59): browser + platform lengkap! ---
  // F6 (2026-11-08): def() di PROTOTYPE (dulu di instance navigator/screen
  // -> queryLies 'failed undefined properties').
  def(Navigator.prototype, 'platform', ident.platform, Navigator);
  def(Navigator.prototype, 'vendor', ident.vendor, Navigator);
  def(Navigator.prototype, 'appVersion', ident.app_ver, Navigator);
  def(Screen.prototype, 'colorDepth', ident.color_depth, Screen);
  def(Screen.prototype, 'pixelDepth', ident.pixel_depth, Screen);

"""


def section_chrome_runtime() -> str:
    """JS section for feature flag fp_chrome_runtime."""
    return """
  // --- tambahan anti-detection ---
  // webdriver: sudah di prototype (H3) — jangan own property!
"""


def section_languages() -> str:
    """JS section for feature flag fp_languages."""
    return """
  // --- K2 (RND 2026-11-03): languages dari locale proxy, BUKAN hardcoded! ---
  // F6 (2026-11-08): def() di PROTOTYPE (dulu instance -> 'failed undefined
  // properties'). navigator.share/canShare stub (F6 leak #3): Chrome
  // Windows ASLI punya Web Share API; headless Linux tidak — tanpa stub,
  // CreepJS menghitung noWebShare sebagai sinyal headless. share() reject
  // (tanpa user gesture Chrome asli juga reject); canShare true hanya
  // untuk text/title/url. ContentIndex/ContactsManager/downlinkMax TIDAK
  // dipalsukan — Chrome Windows asli memang tidak punya ketiganya.
  (() => {
    const _lang = LOCALE || 'id-ID';
    const _base = _lang.split('-')[0];
    const _langs = [_lang];
    if (_base !== _lang) _langs.push(_base);
    if (!_langs.includes('en-US')) _langs.push('en-US');
    if (!_langs.includes('en')) _langs.push('en');
    def(Navigator.prototype, 'languages', _langs, Navigator);
    def(Navigator.prototype, 'language', _lang, Navigator);
  })();
  // platform SUDAH di-set dari ident di atas (jangan override!)
  def(Navigator.prototype, 'maxTouchPoints', 0, Navigator);
  // BARU (Gil 2026-11-02 16:01): lengkap!
  def(Navigator.prototype, 'cookieEnabled', true, Navigator);
  def(Navigator.prototype, 'doNotTrack', null, Navigator);
  def(Navigator.prototype, 'onLine', true, Navigator);
  // screen orientation
  try {
    def(Screen.prototype, 'orientation', {
      angle: 0, type: 'landscape-primary',
      onchange: null,
      addEventListener: function(){}, removeEventListener: function(){}
    }, Screen);
  } catch(e) {}
  // Web Share API stub (lihat komentar di atas)
  try {
    if (!('share' in Navigator.prototype)) {
      const _fShare = _nf(function(shareData) {
        return Promise.reject(new DOMException('Share canceled', 'AbortError'));
      }, 'share', 1);
      const _fCanShare = _nf(function(shareData) {
        try {
          if (!shareData || typeof shareData !== 'object') return false;
          if (shareData.files) return false;
          return !!(shareData.title || shareData.text || shareData.url);
        } catch(e) { return false; }
      }, 'canShare', 1);
      Object.defineProperty(Navigator.prototype, 'share', { value: _fShare, configurable: true, writable: true });
      Object.defineProperty(Navigator.prototype, 'canShare', { value: _fCanShare, configurable: true, writable: true });
    }
  } catch(e) {}

"""


def section_storage() -> str:
    """JS section for feature flag fp_storage."""
    return """
  // --- OBSCURE (Gil 2026-11-02 16:03): lengkap banget! ---
  // F6 (2026-11-08): _nf + def() di Navigator.prototype (dulu plain fn di
  // instance -> queryLies 9-12 lie + 'failed undefined properties').
  // navigator.storage
  try {
    const _fEst = _nf(function() { return Promise.resolve({quota: 10737418240, usage: 0}); }, 'estimate', 0);
    const _fPer = _nf(function() { return Promise.resolve(true); }, 'persist', 0);
    const _fPed = _nf(function() { return Promise.resolve(true); }, 'persisted', 0);
    def(Navigator.prototype, 'storage', { estimate: _fEst, persist: _fPer, persisted: _fPed }, Navigator);
  } catch(e) {}
  // navigator.mediaCapabilities
  try {
    const _fDec = _nf(function() { return Promise.resolve({supported: true, smooth: true, powerEfficient: true}); }, 'decodingInfo', 1);
    const _fEnc = _nf(function() { return Promise.resolve({supported: true, smooth: true, powerEfficient: true}); }, 'encodingInfo', 1);
    def(Navigator.prototype, 'mediaCapabilities', { decodingInfo: _fDec, encodingInfo: _fEnc }, Navigator);
  } catch(e) {}

"""


def section_battery() -> str:
    """JS section for feature flag fp_battery."""
    return """
  // --- Battery API spoof (charging, plausible levels) ---
  // F6 (2026-11-08): _nf + definisi di Navigator.prototype (dulu own
  // property di instance navigator -> 'failed undefined properties').
  // seed dari header (selalu ada).
  try {
    const battLevel = 0.65 + (seed %% 30) / 100;
    const _fBat = _nf(function() { return Promise.resolve({
      charging: true, chargingTime: 0,
      dischargingTime: Infinity, level: battLevel,
      onchargingchange: null, onlevelchange: null,
      addEventListener: function(){}, removeEventListener: function(){}
    }); }, 'getBattery', 0);
    Navigator.prototype.getBattery = _fBat;
  } catch(e) {}

"""


def section_enumerate_devices() -> str:
    """JS section for feature flag fp_enumerate_devices."""
    return """
  // --- Media devices (plausible desktop: no camera/mic labels leaked) ---
  // F6 (2026-11-08): _nf + definisi di MediaDevices.prototype (dulu own
  // property di instance mediaDevices).
  try {
    if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
      const origEnum = navigator.mediaDevices.enumerateDevices;
      const _fED = _nf(async function() {
        const devices = await origEnum.call(this);
        return devices.map(d => ({ deviceId: d.deviceId, kind: d.kind, label: '', groupId: d.groupId,
                                   toJSON: d.toJSON ? d.toJSON.bind(d) : undefined }));
      }, 'enumerateDevices', 0);
      MediaDevices.prototype.enumerateDevices = _fED;
    }
  } catch(e) {}

"""


def section_client_hints() -> str:
    """JS section for feature flag fp_client_hints."""
    return """
  // --- Client Hints (navigator.userAgentData) — consistent with UA ---
  // PERBAIKAN (RND 2026-11-02): versi + platform DIAMBIL dari ident,
  // JANGAN hardcode! Inkonsistensi UA vs userAgentData = sinyal bot!
  try {
    const isMobile = false;
    const _chromeMajor = (ident.chrome_ver || '156.0.0.0').split('.')[0];
    const _plat = ident.platform || '';
    const _chPlatform = _plat === 'MacIntel' ? 'macOS'
      : _plat.indexOf('Linux') === 0 ? 'Linux' : 'Windows';
    const _chFullVer = ident.chrome_ver || '156.0.0.0';
    // AUDIT 2026-11-04: architecture/platformVersion per OS, bukan hardcode!
    // - Mac = Apple Silicon semua -> architecture 'arm' (real M1+ Chrome lapor 'arm',
    //   sementara navigator.platform tetap 'MacIntel' untuk kompat)
    // - Linux -> platformVersion '' (real Chrome Linux return string kosong!)
    // - Windows -> '15.0.0' (Win11; UA tetap NT 10.0 seperti Chrome asli)
    const _arch = _plat === 'MacIntel' ? 'arm' : 'x86';
    const _pv = _plat === 'MacIntel' ? '14.5.0'
      : (_plat.indexOf('Linux') === 0 ? '' : '15.0.0');
    // F6 (2026-11-08): _nf + def() di Navigator.prototype (dulu plain fn
    // di instance -> queryLies 12 lie + 'failed undefined properties').
    const _fGHE = _nf(function(hints) { return Promise.resolve({
        architecture: _arch, bitness: '64', model: '',
        platform: _chPlatform,
        platformVersion: _pv, uaFullVersion: _chFullVer,
        fullVersionList: [
          { brand: 'Chromium', version: _chFullVer },
          { brand: 'Google Chrome', version: _chFullVer }
        ]
      }); }, 'getHighEntropyValues', 1);
    def(Navigator.prototype, 'userAgentData', {
      brands: [
        { brand: 'Chromium', version: _chromeMajor },
        { brand: 'Google Chrome', version: _chromeMajor },
        { brand: 'Not_A Brand', version: '24' }
      ],
      mobile: isMobile,
      platform: _chPlatform,
      getHighEntropyValues: _fGHE
    }, Navigator);
  } catch(e) {}

"""


def section_plugins() -> str:
    """JS section for feature flag fp_plugins."""
    return """
  // --- 1B (RND 2026-11-03): plugins + mimeTypes — BENTUK ASLI (F7 rewrite) ---
  // Chromium polos (terbukti f7_plugin_probe.py): Plugin/MimeType HANYA
  // punya indexed + named props (non-enumerable); name/filename/
  // description/length/type/suffixes/enabledPlugin adalah GETTER di
  // prototype, BUKAN own property. Versi lama menaruh semuanya sebagai
  // own enumerable -> getPluginLies CreepJS: 'missing mimetype'
  // (plugin[0] undefined) + 'invalid mimetype' (Object.values berisi
  // string/function, .type undefined) -> Navigator lied.
  // Perbaikan: MimeType tanpa own property (getter di proto turunan
  // MimeType.prototype); Plugin dengan indexed [0]=pdf,[1]=text +
  // named non-enumerable; PluginArray/MimeTypeArray dengan named
  // non-enumerable; item/namedItem/refresh non-enumerable own (fungsional,
  // aslinya di prototype — native-nya mengembalikan null di objek palsu).
  (() => {
    const _mkMimeProto = (type, suffixes, description, enabledPlugin) => {
      const _proto = Object.create(MimeType.prototype);
      def(_proto, 'type', type, MimeType);
      def(_proto, 'suffixes', suffixes, MimeType);
      def(_proto, 'description', description, MimeType);
      def(_proto, 'enabledPlugin', enabledPlugin, MimeType);
      return _proto;
    };
    const _plugins = [
      { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
      { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
      { name: 'Chromium PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
      { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: '' },
      { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: '' },
    ];
    const _parr = [];
    const _pProtos = _plugins.map((p) => {
      const _proto = Object.create(Plugin.prototype);
      def(_proto, 'name', p.name, Plugin);
      def(_proto, 'filename', p.filename, Plugin);
      def(_proto, 'description', p.description, Plugin);
      def(_proto, 'length', 2, Plugin);
      return _proto;
    });
    _plugins.forEach((p, i) => {
      const o = {};
      Object.setPrototypeOf(o, _pProtos[i]);
      _parr.push(o);
    });
    // enabledPlugin mime = PDF Viewer (plugin pertama), seperti Chrome asli.
    const _pdfMime = {};
    Object.setPrototypeOf(_pdfMime, _mkMimeProto('application/pdf', 'pdf', 'Portable Document Format', _parr[0]));
    const _textMime = {};
    Object.setPrototypeOf(_textMime, _mkMimeProto('text/pdf', 'pdf', 'Portable Document Format', _parr[0]));
    _parr.forEach((o) => {
      o[0] = _pdfMime;
      o[1] = _textMime;
      try { Object.defineProperty(o, 'application/pdf', { value: _pdfMime, configurable: true }); } catch(e) {}
      try { Object.defineProperty(o, 'text/pdf', { value: _textMime, configurable: true }); } catch(e) {}
      try { Object.defineProperty(o, 'item', { value: _nf(function(i) { return o[i] || null; }, 'item', 1), configurable: true }); } catch(e) {}
      try { Object.defineProperty(o, 'namedItem', { value: _nf(function(n) { return (n === 'application/pdf' ? _pdfMime : (n === 'text/pdf' ? _textMime : null)); }, 'namedItem', 1), configurable: true }); } catch(e) {}
    });
    // PluginArray: indexed + named (non-enumerable) + item/namedItem/refresh.
    // URUTAN PENTING: forEach HARUS sebelum setPrototypeOf — PluginArray.
    // prototype tidak punya forEach, jadi _parr.forEach setelahnya throw
    // (PAGEERROR di konsol, def() plugins/mimeTypes tidak jalan, yang
    // tampil malah plugin ASLI kernel — jumlahnya sama sehingga tertutup).
    _parr.forEach((o) => {
      try { Object.defineProperty(_parr, o.name, { value: o, configurable: true }); } catch(e) {}
    });
    try { if (window.PluginArray) Object.setPrototypeOf(_parr, PluginArray.prototype); } catch(e) {}
    try { Object.defineProperty(_parr, 'item', { value: _nf(function(i) { return _parr[i] || null; }, 'item', 1), configurable: true }); } catch(e) {}
    try { Object.defineProperty(_parr, 'namedItem', { value: _nf(function(n) { for (let i = 0; i < _parr.length; i++) { if (_parr[i].name === n) return _parr[i]; } return null; }, 'namedItem', 1), configurable: true }); } catch(e) {} // manual loop: _parr.find hilang setelah setPrototypeOf(PluginArray.prototype)
    try { Object.defineProperty(_parr, 'refresh', { value: _nf(function() {}, 'refresh', 0), configurable: true }); } catch(e) {}
    const _marr = [_pdfMime, _textMime];
    try { if (window.MimeTypeArray) Object.setPrototypeOf(_marr, MimeTypeArray.prototype); } catch(e) {}
    try { Object.defineProperty(_marr, 'application/pdf', { value: _pdfMime, configurable: true }); } catch(e) {}
    try { Object.defineProperty(_marr, 'text/pdf', { value: _textMime, configurable: true }); } catch(e) {}
    try { Object.defineProperty(_marr, 'item', { value: _nf(function(i) { return _marr[i] || null; }, 'item', 1), configurable: true }); } catch(e) {}
    try { Object.defineProperty(_marr, 'namedItem', { value: _nf(function(n) { return (n === 'application/pdf' ? _pdfMime : (n === 'text/pdf' ? _textMime : null)); }, 'namedItem', 1), configurable: true }); } catch(e) {}
    // F6 (2026-11-08): def() — getter di prototype + _nf + receiver check
    def(Navigator.prototype, 'plugins', _parr, Navigator);
    def(Navigator.prototype, 'mimeTypes', _marr, Navigator);
    def(Navigator.prototype, 'pdfViewerEnabled', true, Navigator);
  })();

"""


def section_voices() -> str:
    """JS section for feature flag fp_voices."""
    return """
  // --- M2 (RND 2026-11-03): Speech voices ---
  // AUDIT 2026-11-04 P0#2: fungsi BERNAMA + _mp.
  (() => {
    const VOICES = [
      { name: 'Google US English', lang: 'en-US' },
      { name: 'Google UK English Female', lang: 'en-GB' },
      { name: 'Google UK English Male', lang: 'en-GB' },
      { name: 'Microsoft David - English (United States)', lang: 'en-US' },
      { name: 'Microsoft Zira - English (United States)', lang: 'en-US' },
    ];
    try {
      // F6 (2026-11-08): _nf + definisi di SpeechSynthesis.prototype
      // (dulu own property di instance speechSynthesis).
      const _fV = _nf(function() {
        return VOICES.map(v => ({ ...v, default: v.lang === 'en-US',
          localService: true, voiceURI: v.name }));
      }, 'getVoices', 0);
      SpeechSynthesis.prototype.getVoices = _fV;
    } catch(e) {}
  })();

"""


def section_perf_memory() -> str:
    """JS section for feature flag fp_perf_memory."""
    return """
  // --- M5 (RND 2026-11-03): performance.memory ---
  // F6 (2026-11-08): getter _nf + di Performance.prototype (dulu own
  // property di instance performance). Receiver check: this instanceof
  // Performance. Nilai tetap fresh per akses (seperti Chrome asli).
  (() => {
    try {
      if (performance.memory) {
        const _fPM = _nf(function() { return {
          jsHeapSizeLimit: 4294705152,
          totalJSHeapSize: 30000000 + ((rnd() * 20000000) | 0),
          usedJSHeapSize: 20000000 + ((rnd() * 10000000) | 0)
        }; }, 'get memory', 0, (t) => { try { return t instanceof Performance; } catch(e) { return false; } });
        Object.defineProperty(Performance.prototype, 'memory', { get: _fPM, configurable: true });
      }
    } catch(e) {}
  })();

"""


def section_datetostring() -> str:
    """JS section for feature flag fp_datetostring."""
    return """
  // --- H3 (RND 2026-11-03): Date.toString() jangan bocorkan timezone asli ---
  // AUDIT 2026-11-04 P0#5: implementasi BENERAN (sebelumnya no-op!).
  // Masalah: getTimezoneOffset() bilang -420 (Jakarta) tapi
  // new Date().toString() bilang "GMT+0000 (Coordinated Universal Time)" = mismatch.
  // Sekarang toString() diformat ulang pakai TZ spoof + offset dari getTimezoneOffset().
  (() => {
    try {
      const _origDTS = Date.prototype.toString;
      const _TZ_DISP = {
        'Asia/Jakarta': 'Western Indonesia Time',
        'Asia/Singapore': 'Singapore Standard Time',
        'Asia/Kuala_Lumpur': 'Malaysia Time',
        'Asia/Bangkok': 'Indochina Time',
        'Asia/Manila': 'Philippine Standard Time',
        'Asia/Ho_Chi_Minh': 'Indochina Time',
        'Asia/Tokyo': 'Japan Standard Time',
        'Asia/Seoul': 'Korea Standard Time',
        'Asia/Hong_Kong': 'Hong Kong Standard Time',
        'Asia/Taipei': 'Taipei Standard Time',
        'Asia/Dubai': 'Gulf Standard Time',
        'Asia/Riyadh': 'Arabian Standard Time',
        'Asia/Kolkata': 'India Standard Time',
        'America/New_York': 'Eastern Standard Time',
        'America/Toronto': 'Eastern Standard Time',
        'America/Mexico_City': 'Central Standard Time',
        'America/Sao_Paulo': 'Brasilia Standard Time',
        'Europe/London': 'Greenwich Mean Time',
        'Europe/Berlin': 'Central European Standard Time',
        'Europe/Paris': 'Central European Standard Time',
        'Europe/Amsterdam': 'Central European Standard Time',
        'Europe/Madrid': 'Central European Standard Time',
        'Europe/Rome': 'Central European Standard Time',
        'Europe/Lisbon': 'Western European Standard Time',
        'Europe/Stockholm': 'Central European Standard Time',
        'Australia/Sydney': 'Australian Eastern Standard Time',
        'Pacific/Auckland': 'New Zealand Standard Time',
        'Africa/Johannesburg': 'South Africa Standard Time',
        'UTC': 'Coordinated Universal Time'
      };
      // F6 (2026-11-08): _nf (dulu plain named function -> queryLies 10 lie,
      // termasuk 'failed at instanceof check error' — _nf arrow target
      // membuat `fn instanceof fn` throw TypeError seperti native).
      const _fDTS = _nf(function() {
        try {
          if (isNaN(this.getTime())) return 'Invalid Date';
          const _parts = new Intl.DateTimeFormat('en-US', {
            timeZone: TZ, weekday: 'short', year: 'numeric', month: 'short',
            day: '2-digit', hour: '2-digit', minute: '2-digit',
            second: '2-digit', hourCycle: 'h23'
          }).formatToParts(this);
          const _p = {};
          for (const _x of _parts) _p[_x.type] = _x.value;
          // offset dari getTimezoneOffset() (sudah di-spoof K3) — konsisten!
          const _offMin = -this.getTimezoneOffset();
          const _sign = _offMin < 0 ? '-' : '+';
          const _a = Math.abs(_offMin);
          const _hh = String(Math.floor(_a / 60)).padStart(2, '0');
          const _mm = String(_a %% 60).padStart(2, '0');
          const _tzName = _TZ_DISP[TZ] || TZ;
          return _p.weekday + ' ' + _p.month + ' ' + _p.day + ' ' + _p.year +
            ' ' + _p.hour + ':' + _p.minute + ':' + _p.second +
            ' GMT' + _sign + _hh + _mm + ' (' + _tzName + ')';
        } catch(e) {
          return _origDTS.call(this);
        }
      }, 'toString', 0);
      Date.prototype.toString = _fDTS;
    } catch(e) {}
  })();

"""


