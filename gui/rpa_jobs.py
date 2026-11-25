"""Job jalankan satu Alur di banyak profil (F5-4).

Pola yang sama dengan job impor/ekspor F3-6 (gui/batch_import.py):
job tersimpan di file JSON (sumber kebenaran), progres + cancel dicek
antar profil. Worker jalan di thread daemon; tiap profil yang belum
jalan di-launch headless dulu lalu di-stop lagi (profil yang sudah
jalan sebelumnya dibiarkan jalan).
"""
import datetime
import json
import os
import secrets
import threading

_JOBS_LOCK = threading.Lock()
_JOBS = {}  # job_id -> dict (cache memori; sumber kebenaran = file JSON)
_JOBS_FILE_OVERRIDE = None  # test: arahkan ke file tmp


def _data_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "data")


def _jobs_file():
    if _JOBS_FILE_OVERRIDE:
        return _JOBS_FILE_OVERRIDE
    return os.path.join(_data_dir(), "rpa_jobs.json")


def _load_jobs():
    try:
        with open(_jobs_file()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_jobs(jobs):
    os.makedirs(os.path.dirname(_jobs_file()), exist_ok=True)
    tmp = _jobs_file() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(jobs, f)
    os.replace(tmp, _jobs_file())


def _update_job(job_id, **fields):
    with _JOBS_LOCK:
        jobs = _load_jobs()
        job = jobs.get(job_id)
        if not job:
            return None
        job.update(fields)
        jobs[job_id] = job
        _JOBS[job_id] = job
        _save_jobs(jobs)
        return job


def _new_job(kind, total, meta=None):
    job_id = "rj_" + secrets.token_hex(6)
    job = {"job_id": job_id, "kind": kind, "state": "running",
           "total": total, "done": 0,
           "results": [],
           "cancel_requested": False,
           "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "finished_at": None}
    if meta:
        job.update(meta)
    with _JOBS_LOCK:
        jobs = _load_jobs()
        jobs[job_id] = job
        _JOBS[job_id] = job
        _save_jobs(jobs)
    return job


def get_job(job_id):
    """Ambil satu job (file JSON sumber kebenaran)."""
    return _load_jobs().get(job_id)


def list_jobs():
    """Daftar job, terbaru dulu."""
    jobs = _load_jobs()
    return sorted(jobs.values(), key=lambda j: j.get("started_at", ""),
                  reverse=True)


def cancel_job(job_id):
    """Minta job berhenti. Worker memeriksa flag antar profil; job yang
    sudah selesai tidak bisa dibatalkan. Return job atau None."""
    job = get_job(job_id)
    if not job:
        return None
    if job["state"] in ("done", "cancelled", "error"):
        return job
    return _update_job(job_id, cancel_requested=True)


def _run_multi_job(job_id, flow_name, steps, profile_ids,
                   launcher_mod, rpa_mod, pm):
    """Worker: jalankan alur di tiap profil berurutan. Profil yang belum
    jalan di-launch headless lalu di-stop lagi; yang sudah jalan dibiarkan."""
    results = []
    cancelled = False
    for pid in profile_ids:
        job = get_job(job_id)
        if job and job.get("cancel_requested"):
            cancelled = True
            break
        prof = pm.get_profile(pid)
        if not prof:
            results.append({"profile_id": pid, "ok": False,
                            "error": "profil tidak ditemukan"})
            _update_job(job_id, done=len(results), results=results)
            continue
        launched_by_job = False
        try:
            sess = launcher_mod.list_running().get(pid)
        except Exception:
            sess = None
        if not sess:
            try:
                res = launcher_mod.launch_profile(prof, headless=True)
            except Exception as e:
                res = {"ok": False, "error": str(e)}
            if not res.get("ok"):
                results.append({"profile_id": pid,
                                "name": prof.get("name"), "ok": False,
                                "error": res.get("error", "launch gagal")})
                _update_job(job_id, done=len(results), results=results)
                continue
            launched_by_job = True
            sess = res
        try:
            out = rpa_mod.run_steps(sess["debug_port"], steps, timeout=120)
            ok_steps = [s for s in out.get("steps", []) if s.get("ok")]
            bad_steps = [s for s in out.get("steps", []) if not s.get("ok")]
            results.append({"profile_id": pid, "name": prof.get("name"),
                            "ok": bool(out.get("ok")),
                            "steps_ok": len(ok_steps),
                            "steps_failed": len(bad_steps),
                            "failed_detail": [s.get("detail", "")[:120]
                                            for s in bad_steps]})
        except Exception as e:
            results.append({"profile_id": pid, "name": prof.get("name"),
                            "ok": False, "error": str(e)[:200]})
        finally:
            if launched_by_job:
                try:
                    launcher_mod.stop_profile(pid)
                except Exception:
                    pass
        _update_job(job_id, done=len(results), results=results)
    _update_job(job_id,
                state="cancelled" if cancelled else "done",
                done=len(results), results=results,
                finished_at=datetime.datetime.now().isoformat(timespec="seconds"))


def start_multi_job(flow_name, steps, profile_ids,
                    launcher_mod, rpa_mod, pm):
    """Mulai job multi-profil asinkron. Return job (state running).
    steps sudah tervalidasi pemanggil (rpa_mod.validate_steps)."""
    job = _new_job("rpa-multi", len(profile_ids),
                   meta={"flow": flow_name, "profile_ids": list(profile_ids)})
    t = threading.Thread(
        target=_run_multi_job,
        args=(job["job_id"], flow_name, steps, list(profile_ids),
              launcher_mod, rpa_mod, pm),
        daemon=True, name=f"alur-multi-{job['job_id']}")
    t.start()
    return job
