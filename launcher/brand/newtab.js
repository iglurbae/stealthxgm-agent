// StealthXGM new tab — renders per-profile info from profile_info.json
// (written by the launcher at startup), plus clock / search / theme.
(function () {
  'use strict';
  function esc(s) {
    return String(s == null || s === '' ? '-' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function row(k, v, cls) {
    return '<div class="prow"><span class="k">' + k + '</span>' +
      '<span class="v' + (cls ? ' ' + cls : '') + '">' + v + '</span></div>';
  }
  function shortUA(ua) {
    var m = String(ua || '').match(/Chrome\/(\d+)/);
    return m ? 'Chrome ' + m[1] : String(ua || '-').slice(0, 34);
  }
  function shortGPU(g) {
    g = String(g || '').trim();
    var m = g.match(/^ANGLE\s*\(([^)]+)\)/i);
    if (m) { // "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 ...)" -> last part
      var parts = m[1].split(',');
      g = parts[parts.length - 1].trim();
    } else {
      g = g.replace(/\s*\([^)]*\)/g, '').trim(); // drop "(TM)"-style remarks
    }
    var cut = g.search(/[;(]/);
    if (cut > 0) g = g.slice(0, cut);
    g = g.replace(/^ANGLE\s*/i, '').trim();
    return g ? g.slice(0, 40) : '-';
  }

  /* ---- profile info ---- */
  fetch('profile_info.json').then(function (r) { return r.json(); }).then(function (info) {
    var p = info.profile || {}, fp = info.fingerprint || {};
    var nm = esc(p.name || 'Profil');
    var chip = document.getElementById('chip-name');
    if (chip) chip.textContent = p.name || 'Profil';
    document.getElementById('profile').innerHTML =
      row('Nama', nm) +
      row('Grup', esc(p.group)) +
      row('Proxy', esc(p.proxy)) +
      row('IP keluar', esc(info.exit_ip || 'lihat Cek IP'));
    document.getElementById('fp').innerHTML =
      row('Sistem', esc(fp.os)) +
      row('Peramban', esc(shortUA(fp.user_agent))) +
      row('Platform', esc(fp.platform)) +
      row('Grafis', esc(shortGPU(fp.gpu))) +
      row('Layar', esc(fp.screen)) +
      row('Zona waktu', esc(fp.timezone)) +
      row('Mode', '<svg><use href="#i-check"/></svg>Standar', 'ok');
  }).catch(function () {
    document.getElementById('profile').innerHTML = row('Info', 'tidak tersedia');
    document.getElementById('fp').innerHTML = row('Info', 'tidak tersedia');
  });

  /* ---- clock ---- */
  function tick() {
    var d = new Date(), t = document.getElementById('time'), dt = document.getElementById('date');
    if (t) t.textContent = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
    if (dt) dt.textContent = d.toLocaleDateString('id-ID', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  }
  tick(); setInterval(tick, 15000);

  /* ---- search ---- */
  var engine = 'google', input = document.getElementById('q');
  var urls = { google: 'https://www.google.com/search?q=', ddg: 'https://duckduckgo.com/?q=' };
  var ph = { google: 'Cari di Google', ddg: 'Cari di DuckDuckGo' };
  document.querySelectorAll('.eng button').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('.eng button').forEach(function (x) { x.classList.remove('on'); });
      b.classList.add('on'); engine = b.getAttribute('data-e');
      if (input) input.placeholder = ph[engine] || ph.google;
    });
  });
  document.getElementById('search-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var q = input ? input.value.trim() : '';
    if (q) window.location.href = (urls[engine] || urls.google) + encodeURIComponent(q);
  });

  /* ---- theme ---- */
  function applyTheme(light) { document.body.classList.toggle('light', !!light); }
  try {
    if (localStorage.getItem('sxgm-theme') === 'light') applyTheme(true);
  } catch (e) { /* storage unavailable */ }
  document.getElementById('theme-btn').addEventListener('click', function () {
    var light = !document.body.classList.contains('light');
    applyTheme(light);
    try { localStorage.setItem('sxgm-theme', light ? 'light' : 'dark'); } catch (e) {}
  });
})();
