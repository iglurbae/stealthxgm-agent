"""Behavioral spoofing sections (timezone, fonts).

Extracted from fingerprint.py — logic unchanged.
"""


def section_fonts() -> str:
    """JS section for feature flag fp_fonts."""
    return """
  // --- H1 (RND 2026-11-03): Font spoof via document.fonts.check ---
  (() => {
    const WIN_FONTS = new Set([
      'Arial','Arial Black','Arial Narrow','Calibri','Cambria','Candara','Comic Sans MS',
      'Consolas','Constantia','Corbel','Courier New','Georgia','Impact','Lucida Console',
      'Lucida Sans Unicode','Microsoft Sans Serif','Palatino Linotype','Segoe UI',
      'Segoe UI Symbol','Tahoma','Times New Roman','Trebuchet MS','Verdana',
      'Segoe MDL2 Assets','Segoe UI Emoji','Segoe UI Historic',
      'MS Gothic','MS PGothic','Meiryo','Meiryo UI','Malgun Gothic','Microsoft YaHei',
      'Microsoft JhengHei','SimSun','PMingLiU','Yu Gothic','Yu Gothic UI',
      // F7 (2026-11-08): font penanda versi Windows (CreepJS FONT_LIST hanya
      // berisi font ini — font umum seperti Calibri TIDAK dites). Mesin Win11
      // asli MEMILIKI semuanya (font terakumulasi antar versi), jadi klaim
      // ini benar untuk identitas Windows 11; tanpanya CreepJS hanya
      // melihat 8/51 dan platformVersion = undefined.
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
    // AUDIT 2026-11-04: Linux pakai font Linux, bukan Windows!
    // (sebelumnya Linux dapat WIN_FONTS -> document.fonts.check('Segoe UI')=true
    //  di Linux = tell)
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
    try {
      const _origCheck = FontFaceSet.prototype.check;
      const _f = _nf(function(font, text) {
        try {
          const m = /\"([^\"]+)\"|'([^']+)'/.exec(font || '');
          const name = m ? (m[1] || m[2]) : String(font || '').split(',')[0].trim();
          if (name && FONT_SET.has(name)) return true;
          if (/^(serif|sans-serif|monospace|cursive|fantasy|system-ui)$/i.test(name)) return true;
        } catch(e) {}
        return _origCheck.call(this, font, text);
      }, 'check', 1);
      FontFaceSet.prototype.check = _f;
    } catch(e) {}
    // F6 (2026-11-08): FontFace.prototype.load — CreepJS TIDAK pakai
    // document.fonts.check (guard-nya selalu gagal karena check() native
    // return true bahkan untuk font acak) — CreepJS pakai FontFace.load()
    // dan hanya percaya promise status 'fulfilled' + family. Jadi load()
    // untuk font di FONT_SET (klaim OS) HARUS resolve. Tanpa ini CreepJS
    // hanya melihat 8/51 font (yang benar-benar terinstall di Linux).
    try {
      const _origLoad = FontFace.prototype.load;
      const _fLoad = _nf(function() {
        try {
          const fam = String(this.family || '').replace(/^['"]|['"]$/g, '');
          if (fam && FONT_SET.has(fam)) return Promise.resolve(this);
        } catch(e) {}
        return _origLoad.call(this);
      }, 'load', 0);
      FontFace.prototype.load = _fLoad;
    } catch(e) {}
  })();

"""


def section_timezone_offset() -> str:
    """JS section for feature flag fp_timezone_offset."""
    return """
  // --- K3 (RND 2026-11-03): Date.getTimezoneOffset() harus match timezone! ---
  // Kalau tidak di-spoof: return 0 (UTC) padahal resolvedOptions bilang Singapore
  // AUDIT 2026-11-04 P0#2: fungsi BERNAMA + _mp.
  (() => {
    try {
      // Hitung offset dari TZ (dalam menit, negatif untuk UTC+)
      // Kita pakai pendekatan: override getTimezoneOffset untuk return offset TZ
      const _origGTO = Date.prototype.getTimezoneOffset;
      // F6 (2026-11-08): _nf (dulu plain named function -> queryLies 9 lie).
      const _fGTO = _nf(function() {
        try {
          // Dapatkan offset via Intl untuk tanggal ini
          const _dtf = new Intl.DateTimeFormat('en-US', {
            timeZone: TZ, hour: 'numeric', hourCycle: 'h23'
          });
          const _local = new Date(this.getTime());
          // Simplified: gunakan offset yang dihitung dari TZ
          // Untuk implementasi penuh, hitung via Date di TZ vs UTC
          const _tzDate = new Date(_local.toLocaleString('en-US', { timeZone: TZ }));
          const _utcDate = new Date(_local.toLocaleString('en-US', { timeZone: 'UTC' }));
          const _offsetMin = Math.round((_tzDate - _utcDate) / 60000);
          return -_offsetMin; // getTimezoneOffset return -(UTC+X)
        } catch(e) {
          return _origGTO.call(this);
        }
      }, 'getTimezoneOffset', 0);
      Date.prototype.getTimezoneOffset = _fGTO;
    } catch(e) {}
  })();

"""


