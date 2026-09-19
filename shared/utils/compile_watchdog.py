"""
Watchdog against silent stalls of torch Inductor's async-compile sidecar.

Background (see ../inductor-quiesce-refork-deadlock.md):
  With the default torch._inductor.config.worker_start_method="subprocess", Triton
  kernels are compiled by a sidecar process that owns its own pool of worker
  processes. That pool is quiesced (torn down) 60 s after the last compile job and
  re-forked for the next one. When a re-fork happens while the main process carries
  a heavy live CUDA state (large model on the GPUs, generation running), one of the
  freshly forked workers can deadlock at birth. Inductor has no liveness check for
  such a worker, so the submitted job never completes and the main process blocks
  forever in concurrent.futures.Future.result() -- a silent hang with the GPU idle.

  This watchdog polls the live pools once a minute. If a job submitted to the
  sidecar stays pending longer than WGP_COMPILE_STALL_SECONDS (default 600; set to
  0 to disable) while the sidecar process is alive but unresponsive, it SIGKILLs
  the sidecar. That makes Inductor's own "unclean exit" path run, turning the
  forever-pending futures into a hard InductorError ("SubprocPool closed") that
  propagates to the user with actionable guidance, instead of a multi-hour freeze.

  It never mutates Inductor state: it only reads pool bookkeeping (under the
  pool's own lock) and, as a last resort, kills the sidecar Popen. Every step is
  exception-guarded so a bug or API change here can never break a generation.
"""

import logging
import os
import threading
import time

log = logging.getLogger(__name__)

_STALL_SECONDS = float(os.environ.get("WGP_COMPILE_STALL_SECONDS", "600"))
_CHECK_INTERVAL = 30.0
_DISABLED = _STALL_SECONDS <= 0

_lock = threading.Lock()
_started = False
_thread = None

# SubprocPool -> { job_id -> monotonic time the job was first observed pending }
_first_seen = {}
# SubprocPool -> True once the stall has been reported and the sidecar killed
_action_taken = set()


def _iter_subproc_pools():
    try:
        from torch._inductor import async_compile
        from torch._inductor.compile_worker.subproc_pool import SubprocPool
    except Exception:
        return
    for pool in list(getattr(async_compile, "_pool_set", ()) or ()):
        try:
            if isinstance(pool, SubprocPool):
                yield pool
        except Exception:
            continue


def _check_pool(pool, now) -> None:
    try:
        if not getattr(pool, "running", True):
            return
        with pool.futures_lock:
            pending = list(pool.pending_futures.keys())
    except Exception:
        return
    if not pending:
        with _lock:
            _first_seen.pop(pool, None)
        return

    with _lock:
        seen = _first_seen.setdefault(pool, {})
        for job_id in list(seen):
            if job_id not in pending:
                seen.pop(job_id, None)
        for job_id in pending:
            seen.setdefault(job_id, now)
        oldest = min(seen.values())
        stalled = (now - oldest) >= _STALL_SECONDS
        acted = pool in _action_taken
    if not stalled:
        return

    proc = getattr(pool, "process", None)
    alive = True
    if proc is not None:
        try:
            alive = proc.poll() is None
        except Exception:
            alive = True

    if not acted:
        if alive:
            log.critical(
                "Wan2GP: torch Inductor compile worker stalled for >%ss "
                "(a kernel-compile job submitted to the sidecar has not completed and the "
                "sidecar process %s is alive but unresponsive -- the known quiesce/re-fork "
                "deadlock, see shared/utils/compile_watchdog.py). Killing the sidecar so the "
                "error surfaces instead of hanging the server.",
                int(_STALL_SECONDS),
                getattr(proc, "pid", "?"),
            )
            with _lock:
                _action_taken.add(pool)
                _first_seen.pop(pool, None)
            try:
                proc.kill()
            except Exception:
                log.debug("compile watchdog: sidecar kill failed", exc_info=True)
        else:
            log.critical(
                "Wan2GP: torch Inductor compile worker stalled for >%ss and the sidecar "
                "process is already gone without answering its jobs. The compile cannot "
                "complete in this process; restart the server to recover. If this recurs, "
                "run with TORCHINDUCTOR_WORKER_START=spawn or TORCHINDUCTOR_COMPILE_THREADS=1.",
                int(_STALL_SECONDS),
            )
            with _lock:
                _action_taken.add(pool)
                _first_seen.pop(pool, None)
    elif log.isEnabledFor(logging.DEBUG):
        log.debug("compile watchdog: stall already handled for sidecar %s", getattr(proc, "pid", "?"))


def _check_once() -> None:
    now = time.monotonic()
    try:
        pools = list(_iter_subproc_pools())
    except Exception:
        return
    live = set(pools)
    with _lock:
        for pool in list(_first_seen):
            if pool not in live:
                _first_seen.pop(pool, None)
        for pool in list(_action_taken):
            if pool not in live:
                _action_taken.discard(pool)
    for pool in pools:
        try:
            _check_pool(pool, now)
        except Exception:
            log.debug("compile watchdog: pool check failed", exc_info=True)


def _loop() -> None:
    while True:
        time.sleep(_CHECK_INTERVAL)
        _check_once()


def start_compile_watchdog() -> None:
    """Start the daemon watchdog once; safe to call multiple times."""
    global _started, _thread
    if _DISABLED:
        return
    with _lock:
        if _started:
            return
        _started = True
    _thread = threading.Thread(target=_loop, name="WgpCompileWatchdog", daemon=True)
    _thread.start()
