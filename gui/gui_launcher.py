#!/usr/bin/env python3
"""Launch GUI Profile Manager + Local REST API.

  GUI:        http://127.0.0.1:5200  (mobile-friendly)
  Local API:  http://127.0.0.1:50325 (AdsPower-compatible, configurable)

Usage:
  python3 gui_launcher.py              # both (API per settings)
  python3 gui_launcher.py --gui-only   # GUI only
  python3 gui_launcher.py --api-only   # API only
  STEALTHXGM_API_KEY=SECRET python3 gui_launcher.py --api-port 50325
  # (P-09: jangan taruh API key di argv — pakai env var; argv terbaca
  # semua user lokal via ps / /proc/<pid>/cmdline.)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import app as gui_app
import local_api
import api_config as ac


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gui-only", action="store_true")
    p.add_argument("--api-only", action="store_true")
    p.add_argument("--gui-port", type=int, default=5200)
    p.add_argument("--api-port", type=int, default=None,
                   help="override saved API port")
    p.add_argument("--api-key", default=None,
                   help="override saved API key")
    args = p.parse_args()

    cfg = ac.get_config()
    api_port = args.api_port or cfg["port"]
    # P-04: API key default ON — generate bila belum ada (first-run).
    api_key = args.api_key if args.api_key is not None else (cfg["api_key"] or ac.ensure_api_key())

    if args.api_only:
        local_api.run(port=api_port, api_key=api_key)
    elif args.gui_only:
        gui_app.run(port=args.gui_port)
    else:
        # API as a managed subprocess (GUI can start/stop it too)
        if cfg["enabled"]:
            st = ac.start_api()
            print(f"[API] Local REST API on http://127.0.0.1:{api_port} "
                  f"({'OK' if st['ok'] else 'GAGAL'})")
        else:
            print("[API] disabled in settings — start from GUI 🔌 API section")
        gui_app.run(port=args.gui_port)


if __name__ == "__main__":
    main()
