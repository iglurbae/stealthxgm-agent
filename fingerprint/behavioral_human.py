"""Behavioral layer — human-like interaction helpers (RND 2026-11-04).

Masalah: bot modern cek behavioral biometrics (mouse path, typing rhythm,
scroll pattern). Gerakan linear/robotik = tell instan.

Pendekatan: Python-side via CDP Input.dispatchMouseEvent / Input.insertText.
Input via CDP masuk pipeline input asli Chromium -> event mousemove/keydown
yang dihasilkan TIDAK BISA dibedakan dari input manusia di level JS
(detector hanya lihat event, bukan sumbernya).

Fungsi utama (dipakai launcher / automation):
  human_move(page_or_cdp, x1, y1, x2, y2)  — gerak mouse bezier + jitter
  human_type(page_or_cdp, text)            — ketik dengan rhythm manusia
  human_scroll(page_or_cdp, delta_y)       — scroll dengan momentum
  human_click(page_or_cdp, x, y)           — move + click natural

Dua mode operasi:
  1. Playwright Page (sync_api): pakai page.mouse.move/step
  2. CDP session dict: pakai cdp.send("Input.dispatchMouseEvent", ...)

Tidak ada credential di file ini. Hanya teknik simulasi input.
"""
import math
import random
import time


# ── Bezier curve untuk mouse path ────────────────────────────────────────
def _bezier_point(p0, p1, p2, p3, t):
    """Cubic bezier point. p0=start, p3=end, p1/p2=control points."""
    u = 1 - t
    x = (u**3 * p0[0] + 3*u*u*t * p1[0] + 3*u*t*t * p2[0] + t**3 * p3[0])
    y = (u**3 * p0[1] + 3*u*u*t * p1[1] + 3*u*t*t * p2[1] + t**3 * p3[1])
    return (x, y)


def _human_path(x1, y1, x2, y2, steps=None):
    """Generate human-like mouse path: bezier + micro-jitter + overshoot.

    - Control points acak -> path melengkung natural (bukan garis lurus)
    - Micro-jitter: manusia tidak pernah gerak pixel-perfect
    - Overshoot: kadang mouse lewat target dikit lalu koreksi balik
    """
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 2:
        return [(x2, y2)]

    # Control points: offset perpendicular acak (semakin jauh, semakin melengkung)
    curve = random.uniform(-0.25, 0.25) * dist
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    # perpendicular direction
    px, py = -dy / dist, dx / dist
    p1 = (x1 + dx * 0.25 + px * curve * random.uniform(0.3, 1.0),
          y1 + dy * 0.25 + py * curve * random.uniform(0.3, 1.0))
    p2 = (x1 + dx * 0.75 + px * curve * random.uniform(-1.0, -0.3),
          y1 + dy * 0.75 + py * curve * random.uniform(-1.0, -0.3))

    if steps is None:
        # manusia: ~60-120 px per step, min 8 steps, max 60
        steps = max(8, min(60, int(dist / random.uniform(60, 120))))

    points = []
    for i in range(steps + 1):
        t = i / steps
        # easing: accelerasi di awal, deselerasi di akhir (manusia tidak linear!)
        # pakai ease-in-out cubic
        te = t * t * (3 - 2 * t)
        x, y = _bezier_point((x1, y1), p1, p2, (x2, y2), te)
        # micro-jitter: ±1.5px acak (tangan manusia bergetar)
        if 0 < i < steps:
            x += random.gauss(0, 1.2)
            y += random.gauss(0, 1.2)
        points.append((x, y))

    # overshoot: 30% chance mouse lewat target lalu balik
    if random.random() < 0.3 and dist > 50:
        ox = x2 + random.uniform(-8, 8)
        oy = y2 + random.uniform(-8, 8)
        points.append((ox, oy))
        # koreksi balik dengan 2-3 step kecil
        for j in range(1, 4):
            t = j / 3
            points.append((ox + (x2 - ox) * t, oy + (y2 - oy) * t))

    return points


def _human_delays(n, base_ms=8, variance=0.6):
    """Delay antar mouse event: tidak konstan (manusia tidak metronom)."""
    return [max(1, random.gauss(base_ms, base_ms * variance)) / 1000.0
            for _ in range(n)]


# ── Public API: Playwright Page mode ─────────────────────────────────────
def human_move_page(page, x1, y1, x2, y2):
    """Gerakkan mouse di Playwright page dengan path manusiawi.

    Return jumlah step yang dieksekusi.
    """
    points = _human_path(x1, y1, x2, y2)
    delays = _human_delays(len(points))
    for (x, y), d in zip(points, delays):
        try:
            page.mouse.move(x, y)
        except Exception:
            break
        time.sleep(d)
    return len(points)


def human_click_page(page, x, y, button="left"):
    """Move natural ke (x,y) lalu klik dengan delay manusiawi."""
    # dari posisi sekarang (tidak diketahui -> pakai acak dekat)
    cx = x + random.uniform(-300, 300)
    cy = y + random.uniform(-200, 200)
    human_move_page(page, cx, cy, x, y)
    time.sleep(random.uniform(0.05, 0.25))  # jeda sebelum klik
    try:
        page.mouse.click(x, y, button=button)
    except Exception:
        pass
    time.sleep(random.uniform(0.05, 0.15))


def human_type_page(page, text, wpm=None):
    """Ketik dengan rhythm manusia: variable delay + occasional typo.

    wpm: words per minute (default 40-80 acak = kecepatan manusia normal).
    Typo: 2% chance per karakter -> backspace + betulkan (sangat manusiawi!).
    """
    if wpm is None:
        wpm = random.uniform(40, 80)
    # ms per karakter dari WPM (rata-rata 5 char per word)
    base_ms = (60_000 / wpm) / 5
    for ch in text:
        # delay: distribusi normal (bukan fixed!) + kadang jeda mikir
        if random.random() < 0.05:
            time.sleep(random.uniform(0.3, 0.8))  # jeda mikir
        else:
            time.sleep(max(5, random.gauss(base_ms, base_ms * 0.5)) / 1000.0)
        # typo: 2% -> ketik salah, backspace, betulkan
        if ch.isalpha() and random.random() < 0.02:
            wrong = random.choice("abcdefghijklmnopqrstuvwxyz")
            try:
                page.keyboard.type(wrong)
            except Exception:
                pass
            time.sleep(random.uniform(0.1, 0.3))
            try:
                page.keyboard.press("Backspace")
            except Exception:
                pass
            time.sleep(random.uniform(0.05, 0.2))
        try:
            page.keyboard.type(ch)
        except Exception:
            break


def human_scroll_page(page, delta_y, steps=None):
    """Scroll dengan momentum: cepat di awal, melambat di akhir."""
    total = abs(delta_y)
    direction = 1 if delta_y > 0 else -1
    if steps is None:
        steps = max(3, min(15, int(total / 100)))
    remaining = total
    for i in range(steps):
        # momentum: fraksi mengecil (ease-out)
        frac = (1 - i / steps) ** 1.5
        chunk = max(10, int(remaining * frac * random.uniform(0.3, 0.6)))
        chunk = min(chunk, remaining)
        try:
            page.mouse.wheel(0, chunk * direction)
        except Exception:
            break
        remaining -= chunk
        time.sleep(random.uniform(0.03, 0.12))
        if remaining <= 0:
            break


# ── Public API: CDP session mode ─────────────────────────────────────────
# Untuk injector_daemon / automation yang pegang CDP session langsung.
def human_move_cdp(cdp_send, x1, y1, x2, y2):
    """CDP version: cdp_send(method, params) callable."""
    points = _human_path(x1, y1, x2, y2)
    delays = _human_delays(len(points))
    for (x, y), d in zip(points, delays):
        try:
            cdp_send("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": round(x, 1), "y": round(y, 1),
            })
        except Exception:
            break
        time.sleep(d)
    return len(points)


def human_click_cdp(cdp_send, x, y, button="left"):
    cx = x + random.uniform(-300, 300)
    cy = y + random.uniform(-200, 200)
    human_move_cdp(cdp_send, cx, cy, x, y)
    time.sleep(random.uniform(0.05, 0.25))
    try:
        cdp_send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y, "button": button,
            "clickCount": 1,
        })
        time.sleep(random.uniform(0.03, 0.08))
        cdp_send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": button,
            "clickCount": 1,
        })
    except Exception:
        pass
    time.sleep(random.uniform(0.05, 0.15))


# ── JS helper (di-inject ke page untuk automation via evaluate) ──────────
def human_helpers_js():
    """JS snippet: sediakan window.__human = {move, type, scroll} untuk
    automation yang jalan via page.evaluate. Mouse via dispatchEvent
    (synthetic tapi dengan path bezier + timing manusiawi)."""
    return """
;(() => {
  if (window.__human) return;
  const _sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const _gauss = () => (Math.random() + Math.random() + Math.random() - 1.5) * 2;
  function _bez(x1,y1,cx1,cy1,cx2,cy2,x2,y2,t) {
    const u = 1 - t;
    return [
      u*u*u*x1 + 3*u*u*t*cx1 + 3*u*t*t*cx2 + t*t*t*x2,
      u*u*u*y1 + 3*u*u*t*cy1 + 3*u*t*t*cy2 + t*t*t*y2
    ];
  }
  window.__human = {
    // Gerak mouse bezier + jitter. Dispatch mousemove per step.
    async move(x1, y1, x2, y2) {
      const dx = x2-x1, dy = y2-y1;
      const dist = Math.hypot(dx,dy);
      if (dist < 2) return 1;
      const curve = (Math.random()-0.5) * 0.5 * dist;
      const px = -dy/dist, py = dx/dist;
      const c1x = x1+dx*0.25+px*curve*Math.random(), c1y = y1+dy*0.25+py*curve*Math.random();
      const c2x = x1+dx*0.75-px*curve*Math.random(), c2y = y1+dy*0.75-py*curve*Math.random();
      const steps = Math.max(8, Math.min(60, Math.floor(dist / (60+Math.random()*60))));
      let n = 0;
      for (let i = 0; i <= steps; i++) {
        const t = i/steps, te = t*t*(3-2*t);
        let [x,y] = _bez(x1,y1,c1x,c1y,c2x,c2y,x2,y2,te);
        if (i>0 && i<steps) { x += _gauss()*1.2; y += _gauss()*1.2; }
        const el = document.elementFromPoint(x,y) || document.body;
        el.dispatchEvent(new MouseEvent('mousemove', {clientX:x, clientY:y, bubbles:true}));
        n++;
        await _sleep(Math.max(1, 8 + _gauss()*5));
      }
      return n;
    },
    // Ketik dengan delay variable
    async type(el, text) {
      el = el || document.activeElement || document.body;
      if (el.focus) el.focus();
      const wpm = 40 + Math.random()*40;
      const base = (60000/wpm)/5;
      for (const ch of text) {
        if (Math.random() < 0.05) await _sleep(300+Math.random()*500);
        else await _sleep(Math.max(5, base + _gauss()*base*0.5));
        el.dispatchEvent(new KeyboardEvent('keydown', {key:ch, bubbles:true}));
        el.dispatchEvent(new KeyboardEvent('keypress', {key:ch, bubbles:true}));
        if ('value' in el) el.value += ch;
        else el.textContent += ch;
        el.dispatchEvent(new InputEvent('input', {data:ch, bubbles:true}));
        el.dispatchEvent(new KeyboardEvent('keyup', {key:ch, bubbles:true}));
      }
      return text.length;
    },
    // Scroll dengan momentum
    async scroll(deltaY) {
      const total = Math.abs(deltaY), dir = deltaY>0?1:-1;
      const steps = Math.max(3, Math.min(15, Math.floor(total/100)));
      let rem = total;
      for (let i=0; i<steps && rem>0; i++) {
        const frac = Math.pow(1-i/steps, 1.5);
        const chunk = Math.min(rem, Math.max(10, Math.floor(rem*frac*(0.3+Math.random()*0.3))));
        window.scrollBy(0, chunk*dir);
        rem -= chunk;
        await _sleep(30+Math.random()*90);
      }
      return total - rem;
    }
  };
})();
"""


# ── Self-test ────────────────────────────────────────────────────────────
def self_test():
    """Verifikasi path tidak linear/robotik (tanpa browser)."""
    random.seed(42)
    pts = _human_path(100, 100, 500, 300, steps=20)
    assert len(pts) >= 20, "path terlalu pendek"
    # cek tidak semua titik segaris (linear = robotik!)
    # hitung deviasi dari garis lurus
    x1, y1, x2, y2 = 100, 100, 500, 300
    max_dev = 0
    for (x, y) in pts:
        # jarak titik ke garis
        num = abs((y2-y1)*x - (x2-x1)*y + x2*y1 - y2*x1)
        den = math.hypot(y2-y1, x2-x1)
        max_dev = max(max_dev, num / den if den else 0)
    assert max_dev > 3, f"path terlalu lurus (deviasi {max_dev:.1f}px) = robotik!"
    # cek delays tidak konstan
    ds = _human_delays(20)
    assert len(set(round(d, 4) for d in ds)) > 15, "delays terlalu konstan!"
    # cek typing delay variable
    return {
        "points": len(pts),
        "max_deviation_px": round(max_dev, 1),
        "unique_delays": len(set(round(d, 4) for d in ds)),
        "non_linear": True,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
    print("BEHAVIORAL SELF-TEST: PASS")
