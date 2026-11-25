"""Shared helpers for fingerprint layers.

Extracted from fingerprint.py — logic unchanged.
"""

def _fon(features, fid):
    """True kalau fitur ON. features=None → semua ON (backward compatible)."""
    if features is None:
        return True
    v = features.get(fid, True)
    # dukung AntiAbuseContext juga
    if hasattr(v, "is_enabled"):
        try:
            return v.is_enabled(fid)
        except Exception:
            return True
    return bool(v)


