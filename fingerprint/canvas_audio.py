"""Canvas, audio, WebGL, GPU spoofing sections.

Extracted from fingerprint.py — logic unchanged.
"""
import json
import os

_WEBGL_TABLES = None
_WEBGL_TABLES_LOADED = False

# F10 (2026-11-08): satu tabel TERUKUR per tier (bukan per model — nilai
# tier adalah per-vendor/backend; per-model hanya string renderer + PCI ID).
_TIER_FILES = (
    ("nvidia", "webgl-nvidia-d3d11.json"),
    ("amd", "webgl-amd-d3d11.json"),
    ("intel", "webgl-intel-gen9-d3d11.json"),
    ("apple", "webgl-apple-metal.json"),
)


def webgl_tables():
    """dict tier -> slim table (None bila file tak ada). Dibaca sekali/proses."""
    global _WEBGL_TABLES, _WEBGL_TABLES_LOADED
    if _WEBGL_TABLES_LOADED:
        return _WEBGL_TABLES
    _WEBGL_TABLES_LOADED = True
    _WEBGL_TABLES = {}
    _here = os.path.dirname(os.path.abspath(__file__))
    for _tier, _fname in _TIER_FILES:
        try:
            with open(os.path.join(_here, "data", _fname)) as _f:
                _WEBGL_TABLES[_tier] = json.load(_f)
        except Exception:
            _WEBGL_TABLES[_tier] = None
    return _WEBGL_TABLES


def webgl_tier_for_renderer(renderer):
    """'nvidia'|'amd'|'intel'|'apple'|None dari string renderer identitas.

    Dipakai header spoof_js (main + worker) untuk memilih tabel tier.
    APU AMD sudah membangun "ANGLE (AMD, ..." (F10 devices.py) jadi
    terpetakan ke tier AMD dengan benar.
    """
    if not renderer:
        return None
    if renderer.startswith("ANGLE (NVIDIA,"):
        return "nvidia"
    if renderer.startswith("ANGLE (AMD,"):
        return "amd"
    if renderer.startswith("ANGLE (Intel,"):
        return "intel"
    if renderer.startswith("ANGLE (Apple,"):
        return "apple"
    return None


def webgl_table_js_literal_for(renderer):
    """JS literal tabel tier identitas ini (atau 'null' bila tak ter-cover)."""
    tier = webgl_tier_for_renderer(renderer)
    if tier is None:
        return "null"
    table = webgl_tables().get(tier)
    if table is None:
        return "null"
    return json.dumps(table, separators=(",", ":"))


def webgl_table_js_literal():
    """Kompat F8: JS literal tabel NVIDIA (atau 'null' bila file tak ada).

    Dipakai header spoof_js (main) dan spoof_js_worker — keduanya
    mendefinisikan const _WEBGL_TABLE dari literal ini. (F10: header kini
    memakai webgl_table_js_literal_for() per identitas; fungsi ini
    dipertahankan untuk kompatibilitas.)
    """
    table = webgl_tables().get("nvidia")
    if table is None:
        return "null"
    return json.dumps(table, separators=(",", ":"))


def section_gpu_vendor() -> str:
    """JS section for feature flag fp_gpu_vendor."""
    return """
  // --- Gil: WebGL vendor/renderer spoof (WebGL1 + WebGL2) ---
  // F6 (2026-11-08): _nf (dulu plain named function -> queryLies 9 lie).
  // F8 (2026-11-08): tabel parameter RTX 4090 TERUKUR (zendriver-stealth
  // 0.12.7, probed Chrome 150 / Windows 10 / ANGLE D3D11 — lihat
  // fingerprint/data/webgl-rtx4090-d3d11.json).
  // F10 (2026-11-08): SATU tabel terukur per TIER (nvidia/amd/intel/apple,
  // zendriver-stealth 0.12.7 data/gpu-tiers/*.json). Header memilih tabel
  // tier identitas ini ke const _WEBGL_TABLE (null bila tak ter-cover).
  // getParameter mengembalikan nilai tabel bila _WEBGL_TABLE ada; bila
  // tidak, perilaku lama (hanya vendor/renderer). Nilai STATE (stencil
  // mask, blend, viewport, ...) TIDAK di-spoof — native, karena itu state
  // konteks bukan kemampuan hardware. Enum 0x84FF (anisotropy, 16) dan
  // 0x8824 (MAX_DRAW_BUFFERS_WEBGL, 8) dari tabel — native SwiftShader
  // masing-masing 16 dan 6 (bukti: detector rerun3 + probe f8).
  // 0x9245/0x9246 mengembalikan string identitas (devices.py sudah
  // membangun string renderer per-model DENGAN PCI ID — tabel hanya
  // menyimpan string mesin probe-nya sebagai provenance, bukan untuk
  // dipakai di sini: mesin probe AMD adalah APU 0x164E, bukan RX 6800).
  const _webglTableOn = () => {
    try { return !!_WEBGL_TABLE; } catch(e) { return false; }
  };
  const _webglTableParam = (isGL2, p) => {
    try {
      const _m = isGL2 ? _WEBGL_TABLE.webgl2.params : _WEBGL_TABLE.webgl1.params;
      if (Object.prototype.hasOwnProperty.call(_m, p)) {
        const _v = _m[p];
        // Native mengembalikan typed array segar tiap panggil — jangan
        // kembalikan objek yang sama (bisa dimutasi situs).
        if (Array.isArray(_v)) return { hit: true, value: new (p === 0x0D3A ? Int32Array : Float32Array)(_v) };
        return { hit: true, value: _v };
      }
      if (p === 0x84FF) return { hit: true, value: _WEBGL_TABLE.extra.MAX_TEXTURE_MAX_ANISOTROPY_EXT };
      if (p === 0x8824) return { hit: true, value: _WEBGL_TABLE.extra.MAX_DRAW_BUFFERS_WEBGL };
      if (p === 0x9245) return { hit: true, value: ident.gpu_vendor };
      if (p === 0x9246) return { hit: true, value: ident.gpu_renderer };
    } catch(e) {}
    return { hit: false };
  };
  const spoofParam = (proto, isGL2) => {
    const orig = proto.prototype.getParameter;
    const _fGP = _nf(function(p) {
      if (_webglTableOn()) {
        const _r = _webglTableParam(isGL2, p);
        if (_r.hit) return _r.value;
      }
      if (p === 0x9245) return ident.gpu_vendor;
      if (p === 0x9246) return ident.gpu_renderer;
      if (p === 0x1F00) return 'WebKit';
      if (p === 0x1F01) return 'WebKit WebGL';
      return orig.call(this, p);
    }, 'getParameter', 1);
    proto.prototype.getParameter = _fGP;
  };
  if (window.WebGLRenderingContext) spoofParam(WebGLRenderingContext, false);
  if (window.WebGL2RenderingContext) spoofParam(WebGL2RenderingContext, true);

"""


def section_canvas_todataurl() -> str:
    """JS section for feature flag fp_canvas_todataurl."""
    return """
  // --- Gil: canvas/audio noise (seeded) ---
  // AUDIT 2026-11-04 P0#1: seed/rnd/noise PINDAH ke header _core.py (selalu ada).
  // Section ini cuma pakai — tidak definisikan lagi.
  // F6 (2026-11-08): AnalyserNode _nf (dulu plain named fn -> queryLies).
  // Noise AnalyserNode DIPERTAHANKAN (CreepJS tidak membandingkan output
  // AnalyserNode dengan nilai eksak — tidak ada read-back trap seperti
  // getChannelData).
  if (window.AnalyserNode) {
    const g = AnalyserNode.prototype.getFloatFrequencyData;
    const _f1 = _nf(function(arr) { g.call(this, arr); noise(arr, 0.01); }, 'getFloatFrequencyData', 1);
    AnalyserNode.prototype.getFloatFrequencyData = _f1;
    const t = AnalyserNode.prototype.getByteTimeDomainData;
    const _f2 = _nf(function(arr) {
      t.call(this, arr);
      for (let i = 0; i < arr.length; i++)
        arr[i] = Math.max(0, Math.min(255, arr[i] + Math.round(rnd() * 1.5)));
    }, 'getByteTimeDomainData', 1);
    AnalyserNode.prototype.getByteTimeDomainData = _f2;
  }
  // F6 (2026-11-08): noise PIKSEL toDataURL DIHAPUS — CreepJS getPixelMods
  // membandingkan piksel hasil paint vs read-back; noise ±1 membuat 6 persen
  // piksel berbeda (hash 9342d82a) = terdeteksi sebagai 'rgba noise'.
  // Pengganti: offset SUB-PIKSEL pada fillText/strokeText (_textDX/_textDY,
  // deterministik dari seed di header). Offset mengubah raster anti-alias
  // secara KONSISTEN (toDataURL/getImageData/round-trip semua melihat
  // raster yang sama), beda antar profil, stabil dalam satu profil
  // (seed sama -> offset sama, termasuk di worker).
  try {
    const _origFill = CanvasRenderingContext2D.prototype.fillText;
    const _origStroke = CanvasRenderingContext2D.prototype.strokeText;
    if (_origFill) {
      CanvasRenderingContext2D.prototype.fillText = _nf(function(text, x, y, maxWidth) {
        return _origFill.call(this, text, x + _textDX, y + _textDY, maxWidth);
      }, 'fillText', 4);
    }
    if (_origStroke) {
      CanvasRenderingContext2D.prototype.strokeText = _nf(function(text, x, y, maxWidth) {
        return _origStroke.call(this, text, x + _textDX, y + _textDY, maxWidth);
      }, 'strokeText', 4);
    }
  } catch(e) {}

"""


def section_audio_buffer() -> str:
    """JS section for feature flag fp_audio_buffer."""
    return """
  // --- AudioContext fingerprint noise (beyond AnalyserNode) ---
  // F6 (2026-11-08): noise getChannelData DIHAPUS — CreepJS membandingkan
  // getChannelData vs copyFromChannel/copyToChannel; noise pada getChannelData
  // saja membuat ketiganya tidak konsisten = terdeteksi sebagai 'trap'.
  // (Men-noise ketiganya secara konsisten butuh patch buffer-level —
  // di luar scope F6; audio hash kini stabil per mesin, seperti canvas
  // shape. Variasi per profil tetap ada via offset teks canvas.)
  // getChannelData TIDAK di-patch lagi (native = clean, read-back eksak).

  // chrome.runtime presence (real Chrome punya ini)
  // F6 (2026-11-08): arrow function (bukan plain function) + _nf — arrow
  // tidak punya prototype & tidak constructible (new/class extends throw
  // seperti native). onMessage/onConnect.addListener juga _nf.
  try {
    if (!window.chrome) window.chrome = {};
    if (!window.chrome.runtime) {
      window.chrome.runtime = {
        connect: _nf(function() { return { postMessage: function(){}, onMessage: { addListener: _nf(function(){}, 'addListener', 1) } }; }, 'connect', 0),
        sendMessage: _nf(function() { return undefined; }, 'sendMessage', 1),
        onMessage: { addListener: _nf(function(){}, 'addListener', 1) },
        onConnect: { addListener: _nf(function(){}, 'addListener', 1) }
      };
    }
  } catch(e) {}

  // permissions spoof
  // F6 (2026-11-08): _nf + definisi di Permissions.prototype (dulu own
  // property di instance permissions).
  try {
    const origQuery = navigator.permissions.query;
    const _fPQ = _nf(function(params) {
      if (params && params.name === 'notifications')
        return Promise.resolve({ state: 'default', onchange: null });
      return origQuery.apply(this, arguments);
    }, 'query', 1);
    Permissions.prototype.query = _fPQ;
  } catch(e) {}

"""


def section_webgl_extensions() -> str:
    """JS section for feature flag fp_webgl_extensions."""
    return """
  // --- H2 (RND 2026-11-03): WebGL extensions list ---
  // F6 (2026-11-08): _nf (dulu plain named function -> queryLies 9 lie).
  // F8 (2026-11-08): bila identitas klaim RTX 4090, kembalikan daftar
  // ekstensi TERUKUR dari tabel (webgl1 35 / webgl2 32 — beda per konteks);
  // bila tidak, daftar umum lama.
  // F10 (2026-11-08): bila _WEBGL_TABLE ada (identitas ter-cover tier),
  // kembalikan daftar ekstensi TERUKUR tier itu (D3D11: webgl1 35 /
  // webgl2 32; Metal: webgl1 39 / webgl2 36); bila tidak, daftar umum lama.
  // CATATAN JUJUR: getExtension() tetap native — ekstensi yang tidak
  // didukung SwiftShader di Chrome 159 mengembalikan null walau ada di
  // daftar. Itu inkonsistensi yang diketahui; memalsukan objek ekstensi
  // lengkap (dengan method-nya) di luar scope F8/F10.
  (() => {
    const EXT_COMMON = [
      'ANGLE_instanced_arrays','EXT_blend_minmax','EXT_color_buffer_half_float',
      'EXT_disjoint_timer_query','EXT_float_blend','EXT_frag_depth',
      'EXT_shader_texture_lod','EXT_texture_compression_bptc','EXT_texture_compression_rgtc',
      'EXT_texture_filter_anisotropic','KHR_parallel_shader_compile',
      'OES_element_index_uint','OES_fbo_render_mipmap','OES_standard_derivatives',
      'OES_texture_float','OES_texture_float_linear','OES_texture_half_float',
      'OES_texture_half_float_linear','OES_vertex_array_object','WEBGL_color_buffer_float',
      'WEBGL_compressed_texture_s3tc','WEBGL_compressed_texture_s3tc_srgb',
      'WEBGL_debug_renderer_info','WEBGL_debug_shaders','WEBGL_depth_texture',
      'WEBGL_draw_buffers','WEBGL_lose_context','WEBGL_multi_draw'
    ];
    const _patchExt = (proto, isGL2) => {
      const _fExt = _nf(function() {
        try {
          if (_WEBGL_TABLE) {
            return (isGL2 ? _WEBGL_TABLE.webgl2.extensions : _WEBGL_TABLE.webgl1.extensions).slice();
          }
        } catch(e) {}
        return EXT_COMMON.slice();
      }, 'getSupportedExtensions', 0);
      proto.prototype.getSupportedExtensions = _fExt;
    };
    if (window.WebGLRenderingContext) _patchExt(WebGLRenderingContext, false);
    if (window.WebGL2RenderingContext) _patchExt(WebGL2RenderingContext, true);
  })();

"""


def section_canvas_getimagedata() -> str:
    """JS section for feature flag fp_canvas_getimagedata.

    F6 (2026-11-08): SEMUA patch noise di section ini DIHAPUS.
    - getImageData: noise +-1 per piksel membuat paint -> read-back tidak
      eksak; CreepJS getPixelMods mendeteksi 6% piksel berbeda (hash
      9342d82a). Native getImageData = clean + eksak.
    - toBlob: dulu me-reimplement via toDataURL (agar noise toDataURL ikut);
      noise toDataURL sudah dihapus, jadi toBlob native sudah konsisten
      dengan raster (offset teks canvas tetap terbawa).
    - WebGL readPixels: noise sparse (tiap 997 byte) sama-sama terdeteksi
      oleh read-back comparison; native = clean + eksak.
    Section dipertahankan (flag + urutan section) sebagai no-op dengan
    penjelasan — menghapus section-nya akan mengubah urutan/nomor flag.
    """
    return """
  // --- H4 (RND 2026-11-03): Canvas getImageData + toBlob + WebGL readPixels ---
  // F6 (2026-11-08): noise DIHAPUS (lihat docstring section ini di Python).
  // Read-back HARUS eksak seperti rendering asli; variasi per profil kini
  // dari offset sub-piksel fillText/strokeText (section_canvas_todataurl).
  // (no-op — getImageData/toBlob/readPixels dibiarkan native.)
"""


def section_audio_samplerate() -> str:
    """JS section for feature flag fp_audio_samplerate."""
    return """
  // --- M1 (RND 2026-11-03): AudioContext sampleRate ---
  // F6 (2026-11-08): getter _nf (dulu plain anonymous fn -> toString bocor).
  (() => {
    try {
      const _fSR = _nf(function() { return 48000; }, 'get sampleRate', 0, (t) => { try { return t instanceof AudioContext; } catch(e) { return false; } });
      Object.defineProperty(AudioContext.prototype, 'sampleRate', { get: _fSR, configurable: true });
    } catch(e) {}
    try {
      if ('baseLatency' in AudioContext.prototype) {
        const _fBL = _nf(function() { return 0.005333333333333333; }, 'get baseLatency', 0, (t) => { try { return t instanceof AudioContext; } catch(e) { return false; } });
        Object.defineProperty(AudioContext.prototype, 'baseLatency', { get: _fBL, configurable: true });
      }
    } catch(e) {}
  })();

"""


def section_webgl_shader() -> str:
    """JS section for feature flag fp_webgl_shader."""
    return """
  // --- M3 (RND 2026-11-03): WebGL shader precision ---
  // F6 (2026-11-08): _nf (dulu plain named function -> queryLies 9 lie).
  // F8 (2026-11-08): tabel presisi LENGKAP dari capture RTX 4090
  // (12 kombinasi shader x presisi; nilai [rangeMin, rangeMax, precision]).
  // Memperbaiki bug lama: HIGH_FLOAT rangeMin dulu 23 (salah), kini 127.
  // F10 (2026-11-08): presisi dari tabel tier identitas (_WEBGL_TABLE);
  // bila identitas tak ter-cover, fallback ke native.
  (() => {
    const _patch = (proto) => {
      const _orig = proto.prototype.getShaderPrecisionFormat;
      const _fSPF = _nf(function(sh, pt) {
        try {
          if (_WEBGL_TABLE) {
            const _e = _WEBGL_TABLE.precision[sh + ',' + pt];
            if (_e) return { rangeMin: _e[0], rangeMax: _e[1], precision: _e[2] };
          }
        } catch(e) {}
        return _orig.call(this, sh, pt);
      }, 'getShaderPrecisionFormat', 2);
      proto.prototype.getShaderPrecisionFormat = _fSPF;
    };
    if (window.WebGLRenderingContext) _patch(WebGLRenderingContext);
    if (window.WebGL2RenderingContext) _patch(WebGL2RenderingContext);
  })();

"""


def section_webgpu() -> str:
    """JS section for feature flag fp_webgpu."""
    return r"""
  // --- W1 (RND 2026-11-03): WebGPU spoof — navigator.gpu ---
  // Emerging threat 2026: adapter.info (vendor/arch/device/description) + limits
  // HARUS konsisten dengan WebGL spoof (ident.gpu_vendor/gpu_renderer/gpu_class)
  (() => {
    try {
      if (!('gpu' in navigator)) return;
      // Map vendor dari ident ke WebGPU vendor string
      const _gv = (ident.gpu_vendor || '').toLowerCase();
      let _wVendor = 'nvidia', _wArch = 'ada', _wDevice = '0x2704', _wDesc = '';
      if (_gv.includes('apple')) {
        _wVendor = 'apple'; _wArch = 'apple-m1'; _wDevice = '';
        _wDesc = 'Apple M1';
      } else if (_gv.includes('amd') || _gv.includes('ati')) {
        _wVendor = 'amd'; _wArch = 'rdna-3'; _wDevice = '0x744c';
        _wDesc = 'AMD Radeon RX 7800 XT';
      } else if (_gv.includes('intel')) {
        _wVendor = 'intel'; _wArch = 'xe'; _wDevice = '0x9bc5';
        _wDesc = 'Intel(R) UHD Graphics 770';
      } else {
        // architecture by class
        const _cls = ident.gpu_class || 'mid';
        _wArch = _cls === 'high' ? 'ada' : (_cls === 'igpu' ? 'turing' : 'ampere');
      }
      // F10B (2026-11-08): device + description HARUS cocok dengan model.
      // Turunkan keduanya dari ident.gpu_renderer — string itu sudah
      // membawa nama model + PCI ID terverifikasi (devices.py PCI_IDS):
      // D3D11: 'ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 (0x00002684) ...)'
      //   -> desc 'NVIDIA GeForce RTX 4090', device '0x2684'.
      // Metal: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Pro, ...)'
      //   -> desc 'Apple M4 Pro', device ''.
      // Sebelumnya device hardcode per vendor (0x2704/0x744c/0x9bc5) dan
      // description hardcode satu model — probe 82 model (F10B) menemukan
      // 79/82 gagal di device/description karenanya. Regex D3D11 memakai
      // (.+?) agar nama dengan '(TM)'/'(R)' (mis. 'AMD Radeon(TM) 780M
      // Graphics') tidak terpotong. Bila parse gagal, fallback ke nilai
      // lama di atas (bukan crash); format GL (tanpa PCI ID) hanya
      // mengambil description, device tetap fallback.
      try {
        const _gr = ident.gpu_renderer || '';
        let _m = _gr.match(/^ANGLE \([^,]+, (.+?) \(0x([0-9A-F]{8})\)/);
        if (_m) {
          _wDesc = _m[1].trim();
          _wDevice = '0x' + _m[2].slice(4).toLowerCase();
        } else {
          _m = _gr.match(/ANGLE Metal Renderer: ([^,]+)/);
          if (_m) { _wDesc = _m[1].trim(); _wDevice = ''; }
          else {
            _m = _gr.match(/^ANGLE \([^,]+, (.+?), OpenGL/);
            if (_m) _wDesc = _m[1].trim();
          }
        }
      } catch(e) {}
      // F10B-ARCH (2026-11-08): architecture HARUS cocok dengan generasi
      // model di _wDesc. Nilai terverifikasi dari data dunia nyata
      // (Web3D Survey adapter.info + spider-rs + zendriver capture):
      // NVIDIA turing/ampere/lovelace/blackwell; AMD rdna-1/2/3;
      // Intel gen-9/gen-12lp; Apple metal-3 (semua M1-M5).
      // F11 (2026-11-08): 14 model terakhir TERVERIFIKASI dari sumber
      // otoritatif Dawn sendiri — src/dawn/gpu_info.json (HEAD, diambil
      // 2026-11-08) + generator js_enum_case() (huruf kecil, spasi jadi
      // '-' KECUALI bila chunk sebelumnya berakhiran digit: "Gen 12 LP"
      // -> "gen-12lp", "Xe 2 HPG" -> "xe-2hpg") + PhysicalDeviceMTL.mm
      // (Apple: Metal3 -> "metal-3") + GPUInfo.cpp (Iris Plus 655 di
      // daftar gen9 -> "gen-9", bukan inferensi lagi). Pemetaan PCI ID
      // (devices.py) lewat mask Dawn: AMD 0xFFF0, Intel 0xFF00,
      // NVIDIA 0xFFFFFF00. Hasil: RX 580/590 (0x67DF->0x67D0) = gcn-4;
      // RX 9060 XT/9070/9070 XT (0x7590/0x7550) = rdna-4; 8060S
      // (0x1586->0x1580) = rdna-3 (Dawn TIDAK punya entri "RDNA 3.5");
      // Arc 130V/140V (0x64A0->0x6400) = xe-2lpg; Arc A380/A580/A750/
      // A770 (0x56A5/A2/A1/A0->0x5600) = gen-12hp; Arc B580/B570
      // (0xE20B/E20C->0xE200) = xe-2hpg. 82/82 model kini punya arch
      // terverifikasi; tidak ada lagi fallback arch. Bila _wDesc kosong
      // (parse gagal), regex tidak cocok dan _wArch lama dipertahankan.
      if (/RTX 5\d{3}/.test(_wDesc)) _wArch = 'blackwell';
      else if (/RTX 4\d{3}/.test(_wDesc)) _wArch = 'lovelace';
      else if (/RTX 3\d{3}/.test(_wDesc)) _wArch = 'ampere';
      else if (/RTX 2\d{3}|GTX 16\d{2}/.test(_wDesc)) _wArch = 'turing';
      else if (/RX 580|RX 590/.test(_wDesc)) _wArch = 'gcn-4';
      else if (/RX 9060|RX 9070/.test(_wDesc)) _wArch = 'rdna-4';
      else if (/8060S/.test(_wDesc)) _wArch = 'rdna-3';
      else if (/RX 5\d{3}/.test(_wDesc)) _wArch = 'rdna-1';
      else if (/RX 6\d{3}/.test(_wDesc)) _wArch = 'rdna-2';
      else if (/RX 7\d{3}|780M|880M|890M/.test(_wDesc)) _wArch = 'rdna-3';
      else if (/UHD Graphics 6[23]0|Iris\(R\) Plus Graphics 655/.test(_wDesc)) _wArch = 'gen-9';
      else if (/UHD Graphics 7[37]0|Iris\(R\) Xe Graphics/.test(_wDesc)) _wArch = 'gen-12lp';
      else if (/Arc\(TM\) 1[34]0V/.test(_wDesc)) _wArch = 'xe-2lpg';
      else if (/Arc\(TM\) A(380|580|750|770)/.test(_wDesc)) _wArch = 'gen-12hp';
      else if (/Arc\(TM\) B(580|570)/.test(_wDesc)) _wArch = 'xe-2hpg';
      else if (/^Apple M[1-5]/.test(_wDesc)) _wArch = 'metal-3';
      // Limits per kelas — plausible, bukan max semua (max semua = tell)
      const _cls2 = ident.gpu_class || 'mid';
      const _limits = _cls2 === 'high'
        ? { maxTextureDimension2D: 16384, maxTextureDimension3D: 2048,
            maxTextureArrayLayers: 2048, maxBindGroups: 4,
            maxBufferSize: 268435456, maxComputeWorkgroupSizeX: 1024,
            maxComputeInvocationsPerWorkgroup: 1024 }
        : _cls2 === 'apple'
        ? { maxTextureDimension2D: 16384, maxTextureDimension3D: 2048,
            maxTextureArrayLayers: 2048, maxBindGroups: 4,
            maxBufferSize: 268435456, maxComputeWorkgroupSizeX: 1024,
            maxComputeInvocationsPerWorkgroup: 1024 }
        : _cls2 === 'igpu'
        ? { maxTextureDimension2D: 8192, maxTextureDimension3D: 2048,
            maxTextureArrayLayers: 256, maxBindGroups: 4,
            maxBufferSize: 134217728, maxComputeWorkgroupSizeX: 256,
            maxComputeInvocationsPerWorkgroup: 256 }
        : { maxTextureDimension2D: 8192, maxTextureDimension3D: 2048,
            maxTextureArrayLayers: 2048, maxBindGroups: 4,
            maxBufferSize: 268435456, maxComputeWorkgroupSizeX: 1024,
            maxComputeInvocationsPerWorkgroup: 1024 };
      const _info = { vendor: _wVendor, architecture: _wArch,
                      device: _wDevice, description: _wDesc };
      const _features = ['depth-clip-control', 'texture-compression-bc',
                         'indirect-first-instance', 'shader-f16'];
      const _mkAdapter = () => ({
        info: _info,
        limits: _limits,
        // F7 (2026-11-08): HARUS Set asli — CreepJS handleInfo memanggil
        // [...features.values()]; objek {has} lama melempar TypeError,
        // Promise.all Navigator reject, userAgentData + permissions +
        // webgpu ikut hilang ("unsupported"). Set punya .values()/.has()/
        // .size seperti GPUSupportedFeatures asli.
        features: new Set(_features),
        requestDevice: function(desc) {
          return Promise.resolve({
            queue: { submit: function() {}, onSubmittedWorkDone: function() { return Promise.resolve(); } },
            limits: _limits, features: this.features,
            destroy: function() {},
          });
        },
      });
      const _f = _nf(function(options) { return Promise.resolve(_mkAdapter()); }, 'requestAdapter', 1);
      // F6 (2026-11-08): def() — getter di Navigator.prototype (dulu own
      // property di instance navigator).
      def(Navigator.prototype, 'gpu', { requestAdapter: _f }, Navigator);
    } catch(e) {}
  })();
"""


