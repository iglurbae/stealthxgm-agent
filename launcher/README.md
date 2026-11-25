# StealthXGM Launcher

Launch real Chromium per profile with fingerprint injection — AdsPower-style.

## Architecture

```
launcher.py  ──subprocess──▶ chromium --user-data-dir=<pid> --remote-debugging-port=<port>
     │                              │
     └──spawn──▶ injector_daemon.py ─┘
                       │
                       ▼
              playwright connect_over_cdp
              ctx.add_init_script(fingerprint_js)   ← BEFORE any page script
              (holds session open forever)
```

This mirrors AdsPower's **inject engine** (RND): the launcher owns the browser
process, exposes a CDP debug port, and injects the fingerprint before page load.

## Why a daemon? (RND findings 2026-11-04)

1. **patchright 1.64.3 `add_init_script` is BROKEN** — scripts never execute.
   Real `playwright` 1.64.1 works. The launcher uses real playwright.
2. **CDP `Page.addScriptToEvaluateOnNewDocument` registrations die with the
   registering session.** Disconnect → injection silently stops. The daemon
   holds the session open for the browser's lifetime.
3. **MV3 extension content scripts don't run in `--headless=new`.**
   (P-17: extension is the SECOND injection layer for headful only —
   wired in `launch_profile()` via `extension_builder.build_extension()`.
   The daemon stays the primary layer because it works headless too.)

## Files

| File | Purpose |
|---|---|
| `launcher.py` | `launch_profile()` / `stop_profile()` / CLI / session registry |
| `injector_daemon.py` | Persistent CDP session + init script (spawned per browser) |
| `extension_builder.py` | MV3 extension builder — 2nd injection layer, headful only (P-17) |
| `test_launcher.py` | 9 automated tests |
| `sessions.json` | Shared running-session registry (CLI ↔ GUI) |

## Profile isolation

`~/workspace/antibrowser/browser_profiles/<pid>/` — dedicated
`--user-data-dir` per profile (cookies, history, extensions persist).

## Proxy per profile

| GUI type | Chromium arg |
|---|---|
| `sticky` | `--proxy-server=http://127.0.0.1:18080` (proxy-bot) |
| `warp` | `--proxy-server=socks5://127.0.0.1:40000` (Cloudflare WARP) |
| `http` / `socks5` | `--proxy-server=<scheme>://<host>:<port>` |
| `env` | inherit `HTTP_PROXY`/`HTTPS_PROXY` from environment |
| `none` | `--no-proxy-server` (blocks env-var leakage) |

`--proxy-bypass-list=localhost,127.0.0.1` keeps CDP reachable when proxied.
Proxy auth (user/pass) is not supported via Chromium CLI — documented limitation.

## Launch flags (from AdsPower RND)

- `--disable-backgrounding-occluded-windows`
- `--disable-background-timer-throttling`
- `--disable-renderer-backgrounding`
- `--disable-blink-features=AutomationControlled`
- `--no-sandbox` (required as root)
- `--no-first-run --no-default-browser-check`

## Custom window title

Injected JS prefixes `document.title` with `[Profile Name]` via MutationObserver
(headful mode — identify windows at a glance).

## Headful without display

If `headful` is requested but no `$DISPLAY`, the launcher auto-wraps with
`xvfb-run` (available on this VM).

## GUI integration

- GUI `POST /api/profiles/<pid>/launch` → real browser (headful)
- GUI `POST /api/profiles/<pid>/stop` → kills browser + daemon
- Local API `GET /api/v1/browser/start?user_id=` → AdsPower-compatible shape
  (`debug_port`, `ws.puppeteer`, `ws.selenium`)
- Local API `GET /api/v1/browser/stop?user_id=`

## CLI

```bash
python3 launcher.py --profile <id> [--url URL] [--headful] [--no-proxy]
python3 launcher.py --profile <id> --stop
python3 launcher.py --list
```

## Test results (2026-11-04)

9/9 pass, 3 skipped (VM egress proxy blocks the test site — environment
limitation, documented in test):

- launch ok, debug_port assigned, user-data-dir isolated
- `navigator.webdriver === false` (live browser)
- `navigator.userAgent` spoofed (e.g. Mac/Windows Chrome, no HeadlessChrome)
- `navigator.platform` consistent with spoofed UA
- stop kills browser + daemon, session removed

## Does NOT touch

`~/workspace/tools/bugbounty-hunt/stealth_browser/` (original) — the separate
project only READS the copied fingerprint package under `~/workspace/antibrowser/`.
