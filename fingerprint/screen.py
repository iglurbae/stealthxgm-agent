"""Screen, CPU, memory spoofing sections.

Extracted from fingerprint.py — logic unchanged.
"""


def section_cpu_cores() -> str:
    """JS section for feature flag fp_cpu_cores."""
    return r"""
  // --- Gil: hardware + screen ---
  // F6 (2026-11-08): def() di PROTOTYPE (dulu instance -> queryLies
  // 'failed undefined properties') — KECUALI devicePixelRatio.
  // F6-rev (2026-11-08): devicePixelRatio HARUS di instance `window`,
  // BUKAN Window.prototype — Chrome asli menaruhnya sebagai OWN property
  // di tiap window (terbukti: Chromium polos hasOwn=true, protoHasGet=null).
  // Patch prototype terbayangi own property Chrome -> baca selalu 1 (asli),
  // fp-check gagal (expected 1.5 live 1). Def di instance = perilaku Chrome
  // asli, jadi bukan lie; tetap pakai _nf + receiver check (Window).
  def(Navigator.prototype, 'hardwareConcurrency', ident.hw, Navigator);
  def(Navigator.prototype, 'deviceMemory', ident.mem, Navigator);
  def(Screen.prototype, 'width', ident.screen_w, Screen);
  def(Screen.prototype, 'height', ident.screen_h, Screen);
  def(Screen.prototype, 'availWidth', ident.screen_w, Screen);
  def(Screen.prototype, 'availHeight', ident.screen_h - 40, Screen);
  def(window, 'devicePixelRatio', ident.dpr, Window);
  // F7 (2026-11-08): window.matchMedia menjawab dari IDENTITAS.
  // CreepJS: lied bila matchMedia('(device-width: Wpx) and
  // (device-height: Hpx)') atau '(resolution: DPRdppx)' tidak match.
  // Tampilan asli xvfb 1600x900@dpr1, identitas bisa 2560x1440@dpr1.25
  // -> tanpa patch ini Screen selalu pink. Patch umum (bukan khusus
  // CreepJS): semua query device-width/device-height/resolution dijawab
  // konsisten dengan screen_w/screen_h/dpr identitas; query lain
  // diteruskan ke native apa adanya. MediaQueryList yang dikembalikan
  // adalah objek ASLI dari native (prototype + .media + listener utuh),
  // hanya getter `matches`-nya yang di-override di instance.
  try {
    const _origMM = window.matchMedia;
    const _mm = _nf(function(query) {
      const mql = _origMM.call(window, query);
      try {
        const q = String(query);
        const _num = (re) => { const m = q.match(re); return m ? parseFloat(m[1]) : null; };
        const parts = [];
        const _dw = _num(/\(\s*device-width\s*:\s*([\d.]+)\s*px\s*\)/i);
        const _dh = _num(/\(\s*device-height\s*:\s*([\d.]+)\s*px\s*\)/i);
        const _minDw = _num(/\(\s*min-device-width\s*:\s*([\d.]+)\s*px\s*\)/i);
        const _maxDw = _num(/\(\s*max-device-width\s*:\s*([\d.]+)\s*px\s*\)/i);
        const _minDh = _num(/\(\s*min-device-height\s*:\s*([\d.]+)\s*px\s*\)/i);
        const _maxDh = _num(/\(\s*max-device-height\s*:\s*([\d.]+)\s*px\s*\)/i);
        const _res = _num(/\(\s*resolution\s*:\s*([\d.]+)\s*dppx\s*\)/i);
        const _minRes = _num(/\(\s*min-resolution\s*:\s*([\d.]+)\s*dppx\s*\)/i);
        const _maxRes = _num(/\(\s*max-resolution\s*:\s*([\d.]+)\s*dppx\s*\)/i);
        if (_dw !== null) parts.push(ident.screen_w === _dw);
        if (_dh !== null) parts.push(ident.screen_h === _dh);
        if (_minDw !== null) parts.push(ident.screen_w >= _minDw);
        if (_maxDw !== null) parts.push(ident.screen_w <= _maxDw);
        if (_minDh !== null) parts.push(ident.screen_h >= _minDh);
        if (_maxDh !== null) parts.push(ident.screen_h <= _maxDh);
        if (_res !== null) parts.push(ident.dpr === _res);
        if (_minRes !== null) parts.push(ident.dpr >= _minRes);
        if (_maxRes !== null) parts.push(ident.dpr <= _maxRes);
        if (parts.length && q.indexOf(',') === -1) {
          let ans = parts.every(Boolean);
          if (/^\s*not\b/i.test(q)) ans = !ans;
          const _g = _nf(function() { return ans; }, 'get matches', 0);
          try { Object.defineProperty(mql, 'matches', { get: _g, configurable: true }); } catch(e) {}
        }
      } catch(e) {}
      return mql;
    }, 'matchMedia', 1);
    try { Object.defineProperty(window, 'matchMedia', { value: _mm, configurable: true, writable: true }); } catch(e) { window.matchMedia = _mm; }
  } catch(e) {}

"""


