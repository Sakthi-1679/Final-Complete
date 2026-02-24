"""
Weekly Best-Interaction Retrain Scheduler
==========================================
- Runs in a background daemon thread.
- Retrains on BEST interactions (high rating / long watch / liked = True).
- Fires once every 7 days from the last successful retrain.
- Never blocks live recommendation requests.
- Saves versioned model checkpoint after each run.
- Logs metrics to pipeline_logs/retrain_log.jsonl.
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Optional

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR       = os.path.join(BASE_DIR, 'pipeline_logs')
RETRAIN_LOG   = os.path.join(LOG_DIR, 'retrain_log.jsonl')
METADATA_FILE = os.path.join(BASE_DIR, 'recommender_metadata.json')

os.makedirs(LOG_DIR, exist_ok=True)

# ── How often to retrain (seconds) ────────────────────────────────
RETRAIN_INTERVAL_DAYS = 7
RETRAIN_INTERVAL_SECS = RETRAIN_INTERVAL_DAYS * 24 * 60 * 60   # 604 800 s

# How often the background thread *checks* if retrain is due (every hour)
CHECK_INTERVAL_SECS = 3600


def _log(record: dict):
    """Append a JSON record to the retrain log file."""
    record['logged_at'] = datetime.now().isoformat()
    try:
        with open(RETRAIN_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')
    except Exception as e:
        print(f"[RetainScheduler] Log write error: {e}")


def _load_metadata() -> dict:
    if not os.path.exists(METADATA_FILE):
        return {}
    try:
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _seconds_since_last_retrain() -> float:
    """Return seconds elapsed since the last successful retrain (inf if never)."""
    meta = _load_metadata()
    last_ts = meta.get('last_retrain_ts', 0)
    if not last_ts:
        return float('inf')
    return time.time() - float(last_ts)


def _is_retrain_due() -> bool:
    return _seconds_since_last_retrain() >= RETRAIN_INTERVAL_SECS


def _next_retrain_in() -> str:
    """Human-readable string: how long until next scheduled retrain."""
    elapsed = _seconds_since_last_retrain()
    remaining = max(0.0, RETRAIN_INTERVAL_SECS - elapsed)
    d = int(remaining // 86400)
    h = int((remaining % 86400) // 3600)
    m = int((remaining % 3600) // 60)
    return f"{d}d {h}h {m}m"


# ── Background thread ─────────────────────────────────────────────

class WeeklyRetrainScheduler:
    """
    Starts a single daemon thread that checks every hour whether
    7 days have passed since the last retrain. If yes, it retrains
    on weak interactions only.
    """

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name='WeeklyRetrainScheduler',
            daemon=True,          # dies with the main process
        )
        self._thread.start()
        print(f"[RetainScheduler] ✓ Started — retrains every {RETRAIN_INTERVAL_DAYS} days on best interactions.")
        print(f"[RetainScheduler]   Next retrain in: {_next_retrain_in()}")

    def stop(self):
        self._stop_event.set()
        self._running = False
        print("[RetainScheduler] Stopped.")

    def _loop(self):
        """Hourly check loop. Sleeps in small increments so stop() is responsive."""
        while not self._stop_event.is_set():
            try:
                if _is_retrain_due():
                    self._do_retrain()
            except Exception as e:
                print(f"[RetainScheduler] Unexpected error: {e}")
                _log({'event': 'error', 'error': str(e)})

            # Sleep CHECK_INTERVAL_SECS but wake up every 30 s to check stop flag
            slept = 0
            while slept < CHECK_INTERVAL_SECS and not self._stop_event.is_set():
                time.sleep(30)
                slept += 30

    def _do_retrain(self):
        """Run weak-interaction retraining on a background thread (this IS the background thread)."""
        print(f"\n[RetainScheduler] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"[RetainScheduler] Weekly retrain triggered at {datetime.now().isoformat()}")
        print(f"[RetainScheduler] Mode: BEST interactions only (high-rated / liked / well-watched)")
        print(f"[RetainScheduler] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        _log({'event': 'retrain_started', 'trigger': 'weekly_schedule'})

        try:
            from services.hybrid_recommender_service import get_hybrid_recommender
            svc = get_hybrid_recommender()

            # Collect best samples first so we can skip if none exist
            best = svc.collect_best_interactions()
            if not best:
                print("[RetainScheduler] No best interactions found yet — skipping retrain.")
                _log({'event': 'retrain_skipped', 'reason': 'no_best_interactions'})
                # Still update timestamp so we don't hammer every hour
                self._bump_timestamp()
                return

            print(f"[RetainScheduler] Found {len(best)} best interactions → retraining …")
            result = svc.retrain_on_best(epochs=2)

            if result.get('status') == 'ok':
                print(f"[RetainScheduler] ✓ Retrain complete — model v{result.get('version')}")
                print(f"[RetainScheduler]   best samples used : {result.get('best_samples_used')}")
                print(f"[RetainScheduler]   training loss     : {result.get('training_loss')}")
                _log({'event': 'retrain_success', **result})
            else:
                print(f"[RetainScheduler] Retrain skipped/failed: {result}")
                _log({'event': 'retrain_result', **result})

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[RetainScheduler] Retrain error: {e}")
            _log({'event': 'retrain_error', 'error': str(e)})

    def _bump_timestamp(self):
        """Update last_retrain_ts so we wait another 7 days even when there's nothing to train."""
        try:
            meta = _load_metadata()
            meta['last_retrain_ts']   = int(time.time())
            meta['last_retrain_date'] = datetime.now().isoformat()
            with open(METADATA_FILE, 'w') as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass

    # ── status API (called from /retrain/status route) ──────────

    def status(self) -> dict:
        meta = _load_metadata()
        return {
            'scheduler_running':     self._running,
            'retrain_interval_days': RETRAIN_INTERVAL_DAYS,
            'next_retrain_in':       _next_retrain_in(),
            'last_retrain_date':     meta.get('last_retrain_date', 'Never'),
            'model_version':         meta.get('model_version', 1),
            'best_samples_trained':  meta.get('best_samples_trained', 0),
            'last_training_loss':    meta.get('training_loss', None),
        }

    def trigger_now(self) -> dict:
        """Force an immediate retrain (admin endpoint). Runs in a separate thread."""
        def _bg():
            self._do_retrain()

        t = threading.Thread(target=_bg, name='ManualRetrain', daemon=True)
        t.start()
        return {
            'triggered': True,
            'message': 'Manual retrain started in background — check /retrain/status for progress.',
            'timestamp': datetime.now().isoformat(),
        }


# ── Singleton ─────────────────────────────────────────────────────
_scheduler: Optional[WeeklyRetrainScheduler] = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> WeeklyRetrainScheduler:
    global _scheduler
    if _scheduler is None:
        with _scheduler_lock:
            if _scheduler is None:
                _scheduler = WeeklyRetrainScheduler()
    return _scheduler


def start_scheduler():
    """Call once at server startup."""
    get_scheduler().start()


def scheduler_status() -> dict:
    return get_scheduler().status()


def trigger_retrain_now() -> dict:
    return get_scheduler().trigger_now()
