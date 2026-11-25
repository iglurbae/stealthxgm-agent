"""Muat launcher/rpa.py SEKALI dan pakai ulang (F5-2).

Alasan: app.py/local_api.py lama men-exec ulang rpa.py di tiap request
(importlib.util.spec_from_file_location + exec_module) — modul baru tiap
panggil, jadi state modul (mis. _RECORDERS perekam Alur) hilang antar
request. Loader ini meng-cache satu objek modul per proses.
"""
import importlib.util
import os

_MOD = None


def load_rpa():
    """Return modul launcher/rpa.py (di-cache per proses)."""
    global _MOD
    if _MOD is None:
        rpa_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "launcher", "rpa.py")
        spec = importlib.util.spec_from_file_location("antibrowser_rpa",
                                                      rpa_path)
        _MOD = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_MOD)
    return _MOD
