#!/usr/bin/env python3
"""
Injector daemon — holds a persistent CDP connection and keeps the
fingerprint init script registered for a launched Chromium.

Why a daemon? RND findings (2026-11-04):
  1. patchright 1.64.3's add_init_script is BROKEN (scripts never execute).
     Real playwright 1.64.1 works.
  2. CDP Page.addScriptToEvaluateOnNewDocument registrations are tied to the
     registering session's lifetime — they VANISH on disconnect.
  3. MV3 extension content scripts do not run in --headless=new.

So: this daemon connects via real playwright, registers the fingerprint JS
with add_init_script on the persistent default context (fires BEFORE any
page script, every tab, exactly like AdsPower's inject engine), and stays
alive until killed. stop_profile() kills this daemon + the browser together.

P-10 watchdog: the daemon checks the CDP connection every few seconds
(--check-interval, default 5s) and EXITS by itself when the browser dies,
so it never lingers as an orphan. The launcher respawns it (re-inject)
when the browser is still alive. Stdout goes to
browser_profiles/<pid>/injector_daemon.log (not DEVNULL) so crashes
can be read back.

Usage (spawned by launcher.py, not run manually):
    python3 injector_daemon.py --port 19222 --js-file /path/inject.js \
        --ready-file /path/ready.json
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _validate_cookie(c):
    """P-15: validasi satu cookie sebelum inject. Return (ok, reason).
    Playwright add_cookies(list) GAGAL TOTAL bila 1 item invalid — jadi
    yang jelek di-skip per item, bukan menggagalkan semua."""
    if not isinstance(c, dict):
        return False, "bukan dict"
    name = c.get("name")
    if not name or not isinstance(name, str):
        return False, "tanpa name"
    if c.get("value") is None:
        return False, "tanpa value"
    if not c.get("domain") and not c.get("url"):
        return False, "tanpa domain/url"
    exp = c.get("expires")
    if exp is not None:
        try:
            exp = float(exp)
        except (TypeError, ValueError):
            return False, "expires bukan angka"
        if 0 < exp < time.time():
            return False, "expired"
    ss = c.get("sameSite")
    if ss is not None and ss not in ("Strict", "Lax", "None"):
        return False, f"sameSite tidak dikenal: {ss}"
    return True, ""


def _norm_domain(d):
    return (d or "").lstrip(".").lower()


def _cookie_expected_domain(c):
    """Domain tempat cookie seharusnya tersimpan (untuk verifikasi
    baca-balik). Cookie berbasis url (tanpa domain) tersimpan di host url."""
    if c.get("domain"):
        return _norm_domain(c["domain"])
    try:
        from urllib.parse import urlparse
        return _norm_domain(urlparse(c.get("url", "")).hostname or "")
    except Exception:
        return ""


async def _inject_cookies(ctx, cookies):
    """P-15: inject per-cookie + verifikasi baca-balik. Return laporan:
    {"total", "ok", "failed", "results": [{name, domain, status, reason}]}.
    status: "ok" | "skipped" (validasi gagal) | "failed" (add gagal /
    browser menolak diam-diam). Satu cookie jelek tidak menggagalkan
    yang lain. Verifikasi perlu karena Chromium MENOLAK DIAM-DIAM
    cookie expired / SameSite=None tanpa Secure / domain tak cocok."""
    report = {"total": len(cookies), "ok": 0, "failed": 0, "results": []}
    for c in cookies:
        name = c.get("name") if isinstance(c, dict) else None
        domain = c.get("domain", "") if isinstance(c, dict) else ""
        ok, reason = _validate_cookie(c)
        if not ok:
            report["failed"] += 1
            report["results"].append({"name": name, "domain": domain,
                                      "status": "skipped", "reason": reason})
            _log(f"cookie skip: {name}@{domain or '?'} — {reason}")
            continue
        try:
            await ctx.add_cookies([c])
        except Exception as e:
            report["failed"] += 1
            report["results"].append({"name": name, "domain": domain,
                                      "status": "failed",
                                      "reason": str(e)[:120]})
            _log(f"cookie gagal: {name}@{domain or '?'} — {e}")
            continue
        # verifikasi baca-balik: cookie benar-benar tersimpan?
        try:
            stored = await ctx.cookies()
            want_dom = _cookie_expected_domain(c)
            want_path = c.get("path", "/")
            found = any(s.get("name") == c.get("name")
                        and _norm_domain(s.get("domain", "")) == want_dom
                        and s.get("path", "/") == want_path
                        for s in stored)
        except Exception:
            found = False
        if found:
            report["ok"] += 1
            report["results"].append({"name": name, "domain": domain,
                                      "status": "ok", "reason": ""})
        else:
            report["failed"] += 1
            report["results"].append({"name": name, "domain": domain,
                                      "status": "failed",
                                      "reason": "ditolak browser (tidak tersimpan)"})
            _log(f"cookie ditolak browser: {name}@{domain or '?'} "
                 "(cek expires / SameSite=None tanpa Secure)")
    return report


async def _run(port, js_file, ready_file, cookies_file=None, check_interval=5):
    from playwright.async_api import async_playwright
    with open(js_file) as f:
        js = f.read()
    cookies = []
    if cookies_file and os.path.exists(cookies_file):
        try:
            with open(cookies_file) as f:
                data = json.load(f)
            if isinstance(data, list):
                cookies = [c for c in data
                           if isinstance(c, dict) and c.get("name") and c.get("value") is not None]
        except Exception:
            cookies = []
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        # P-15: inject per-cookie + laporan (dulu: satu add_cookies() buta,
        # gagal total bila 1 item invalid, dan ready.json menghitung jumlah
        # yang DICOBA — bukan yang benar-benar masuk).
        cookie_report = {"total": len(cookies), "ok": 0, "failed": 0,
                         "results": []}
        if cookies:
            cookie_report = await _inject_cookies(ctx, cookies)
            report_file = os.path.join(os.path.dirname(ready_file),
                                       "cookie_inject_report.json")
            try:
                with open(report_file, "w") as f:
                    json.dump(cookie_report, f, indent=1)
            except Exception as e:
                _log(f"laporan cookie gagal ditulis: {e}")
        await ctx.add_init_script(js)
        with open(ready_file, "w") as f:
            json.dump({"ready": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "js_length": len(js),
                       "cookies_injected": cookie_report["ok"],
                       "cookies_total": cookie_report["total"],
                       "cookies_failed": cookie_report["failed"]}, f)
        _log(f"ready: init script terdaftar ({len(js)} char, "
             f"{cookie_report['ok']}/{cookie_report['total']} cookies ok"
             + (f", {cookie_report['failed']} gagal" if cookie_report["failed"] else "")
             + f"), port {port}")
        # P-10 watchdog: periksa koneksi CDP berkala. Bila browser mati,
        # koneksi putus -> daemon KELUAR SENDIRI (jangan jadi proses yatim
        # yang hidup selamanya). Launcher mendeteksi kematian ini lewat
        # daemon_pid + me-respawn daemon (re-inject) bila browser masih
        # hidup; bila browser juga mati, sesi di-prune seperti biasa.
        # Tanpa ini, daemon yang mati = fingerprint hilang DIAM-DIAM.
        # Heartbeat hanya dicatat tiap 12x cek (~1/menit) supaya log
        # tidak banjir; kegagalan selalu dicatat.
        tick = 0
        while True:
            await asyncio.sleep(check_interval)
            tick += 1
            try:
                alive = browser.is_connected()
            except Exception as e:
                _log(f"health check error: {e} — keluar")
                return 1
            if not alive:
                _log("browser terputus (mati/crash) — daemon keluar")
                return 0
            if tick % 12 == 0:
                _log("health ok (browser terhubung)")


def _log(msg):
    """Satu baris log timestamp ke stdout (launcher mengarahkan stdout
    daemon ke browser_profiles/<pid>/injector_daemon.log, P-10 — bukan
    DEVNULL, supaya crash daemon bisa dibaca)."""
    try:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [daemon] {msg}",
              flush=True)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--js-file", required=True)
    ap.add_argument("--ready-file", required=True)
    ap.add_argument("--cookies-file", default=None)
    ap.add_argument("--check-interval", type=float, default=5,
                    help="detik antar health check CDP (P-10 watchdog)")
    args = ap.parse_args()
    # wait for the debug port to come up (launcher usually already waited)
    for _ in range(100):
        import socket
        s = socket.socket()
        try:
            s.connect(("127.0.0.1", args.port))
            s.close()
            break
        except OSError:
            time.sleep(0.3)
    # P-10: exit code dibedakan — 0 = browser mati (shutdown normal,
    # bukan error), 1 = error tak terduga. Launcher membaca ini dari
    # daemon.poll() saat startup/respawn.
    sys.exit(asyncio.run(_run(args.port, args.js_file, args.ready_file,
                              args.cookies_file, args.check_interval)))


if __name__ == "__main__":
    main()
