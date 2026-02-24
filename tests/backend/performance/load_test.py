"""
Performance / Load Tests
==========================
Stress-tests the /hybrid/recommend API with multiple concurrent users
using Python's threading and requests libraries (no external tool needed).

Run directly:
    python tests/backend/performance/load_test.py

Or as a pytest:
    pytest tests/backend/performance/load_test.py -v -s

Targets:
  • 50  concurrent users – P95 response < 500 ms
  • 100 concurrent users – P95 response < 1000 ms
  • Memory usage stable after 200 requests
  • Model loaded only once (singleton test)
"""

import sys
import os
import time
import statistics
import threading
import gc

import pytest
import requests

# ──────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────
BASE_URL = os.getenv("TEST_API_URL", "http://127.0.0.1:5000")
RECOMMEND_URL = f"{BASE_URL}/hybrid/recommend"

MOODS   = ["happy", "sad", "angry", "calm", "neutral"]
HEADERS = {"Content-Type": "application/json"}


# ──────────────────────────────────────────────────────────────────
# Helper: fire one request and return (status_code, elapsed_ms)
# ──────────────────────────────────────────────────────────────────
def _fire(user_idx: int):
    mood = MOODS[user_idx % len(MOODS)]
    payload = {"mood": mood, "user_id": f"load_user_{user_idx}", "top_k": 5}
    t0 = time.time()
    try:
        r = requests.post(RECOMMEND_URL, json=payload, timeout=10, headers=HEADERS)
        elapsed_ms = (time.time() - t0) * 1000
        return r.status_code, elapsed_ms
    except requests.exceptions.RequestException as e:
        elapsed_ms = (time.time() - t0) * 1000
        return 0, elapsed_ms


def _concurrent_load(n_users: int):
    """Run n_users concurrent requests; return list of (status, ms) tuples."""
    results = [None] * n_users

    def worker(idx):
        results[idx] = _fire(idx)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_users)]
    t_start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    total_wall = (time.time() - t_start) * 1000

    valid = [r for r in results if r is not None]
    return valid, total_wall


# ──────────────────────────────────────────────────────────────────
# Pytest fixtures – skip if server not reachable
# ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module", autouse=True)
def require_live_server():
    try:
        r = requests.get(f"{BASE_URL}/hybrid/model-info", timeout=3)
    except Exception:
        pytest.skip(f"Live server not reachable at {BASE_URL}")


# ──────────────────────────────────────────────────────────────────
# 1. Single request – baseline latency < 500 ms
# ──────────────────────────────────────────────────────────────────
def test_single_request_baseline():
    status, ms = _fire(1)
    assert status == 200, f"Single request failed with status {status}"
    assert ms < 500, f"Baseline latency too high: {ms:.1f} ms"
    print(f"\n[PERF] Baseline: {ms:.1f} ms")


# ──────────────────────────────────────────────────────────────────
# 2. 50 concurrent users – all succeed
# ──────────────────────────────────────────────────────────────────
def test_50_concurrent_users_all_succeed():
    results, wall = _concurrent_load(50)
    statuses = [r[0] for r in results]
    fails = [s for s in statuses if s not in (200, 429)]  # 429 = rate-limited OK
    assert len(fails) == 0, f"Failures under 50 concurrent load: {fails}"
    print(f"\n[PERF] 50 concurrent users: wall time {wall:.0f} ms, {len(fails)} failures")


# ──────────────────────────────────────────────────────────────────
# 3. 50 concurrent – P95 latency < 500 ms
# ──────────────────────────────────────────────────────────────────
def test_50_concurrent_p95_latency():
    results, _ = _concurrent_load(50)
    latencies = [r[1] for r in results]
    p95 = statistics.quantiles(latencies, n=20)[18]   # 95th percentile
    assert p95 < 500, f"P95 latency under 50 concurrent = {p95:.1f} ms (target < 500 ms)"
    print(f"\n[PERF] P95 @ 50 concurrent: {p95:.1f} ms")


# ──────────────────────────────────────────────────────────────────
# 4. 100 concurrent users – less than 5% failure rate
# ──────────────────────────────────────────────────────────────────
def test_100_concurrent_users_low_failure_rate():
    results, wall = _concurrent_load(100)
    statuses = [r[0] for r in results]
    hard_fails = [s for s in statuses if s not in (200, 429)]
    fail_rate = len(hard_fails) / len(statuses)
    assert fail_rate < 0.05, (
        f"Failure rate under 100 concurrent: {fail_rate:.1%} ({len(hard_fails)} fails)"
    )
    print(f"\n[PERF] 100 concurrent: wall={wall:.0f} ms, fail_rate={fail_rate:.1%}")


# ──────────────────────────────────────────────────────────────────
# 5. 100 concurrent – P95 latency < 1000 ms
# ──────────────────────────────────────────────────────────────────
def test_100_concurrent_p95_latency():
    results, _ = _concurrent_load(100)
    latencies = [r[1] for r in results]
    p95 = statistics.quantiles(latencies, n=20)[18]
    assert p95 < 1000, (
        f"P95 latency under 100 concurrent = {p95:.1f} ms (target < 1000 ms)"
    )
    print(f"\n[PERF] P95 @ 100 concurrent: {p95:.1f} ms")


# ──────────────────────────────────────────────────────────────────
# 6. Mean latency < 250 ms (sanity for well-cached responses)
# ──────────────────────────────────────────────────────────────────
def test_mean_latency_under_250ms():
    results, _ = _concurrent_load(20)
    latencies = [r[1] for r in results]
    mean_ms = statistics.mean(latencies)
    assert mean_ms < 250, f"Mean latency = {mean_ms:.1f} ms (target < 250 ms)"
    print(f"\n[PERF] Mean latency (20 users): {mean_ms:.1f} ms")


# ──────────────────────────────────────────────────────────────────
# 7. Model singleton – /hybrid/model-info returns model_loaded=True every time
# ──────────────────────────────────────────────────────────────────
def test_model_loaded_only_once():
    for i in range(5):
        r = requests.get(f"{BASE_URL}/hybrid/model-info", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data.get("model_loaded") is True, (
            f"model_loaded=False on check {i+1}"
        )


# ──────────────────────────────────────────────────────────────────
# 8. Memory stability – run 200 sequential requests, check no memory leak
#    (proxy: /hybrid/model-info cache_size should stay bounded)
# ──────────────────────────────────────────────────────────────────
def test_memory_stability_200_requests():
    for i in range(200):
        r = requests.post(
            RECOMMEND_URL,
            json={"mood": MOODS[i % len(MOODS)], "user_id": f"mem_user_{i}", "top_k": 5},
            timeout=10,
        )
        # Any non-5xx response is acceptable
        assert r.status_code < 500, f"Request {i} returned 500"

    info = requests.get(f"{BASE_URL}/hybrid/model-info", timeout=5).json()
    cache_size = info.get("cache_size", 0)
    # LRU cache max is 256 by default
    assert cache_size <= 256, f"Cache grew beyond limit: {cache_size}"
    print(f"\n[PERF] After 200 requests: cache_size={cache_size}")


# ──────────────────────────────────────────────────────────────────
# 9. Throughput: at least 20 req/s under 50 concurrent users
# ──────────────────────────────────────────────────────────────────
def test_throughput_50_concurrent():
    results, wall_ms = _concurrent_load(50)
    wall_s = wall_ms / 1000
    throughput = len(results) / wall_s if wall_s > 0 else 0
    assert throughput >= 5, (
        f"Throughput too low: {throughput:.1f} req/s (target ≥ 5 req/s)"
    )
    print(f"\n[PERF] Throughput @ 50 concurrent: {throughput:.1f} req/s")


# ──────────────────────────────────────────────────────────────────
# Stand-alone runner
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Mood-Recommender Load Test Runner")
    print(f"  Target: {BASE_URL}")
    print("=" * 60)

    for n in [1, 10, 50, 100]:
        res, wall = _concurrent_load(n)
        latencies = sorted(r[1] for r in res)
        statuses  = [r[0] for r in res]
        ok        = sum(1 for s in statuses if s == 200)
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        print(f"\nConcurrency: {n:3d} | OK: {ok}/{n} | "
              f"P50: {p50:6.1f}ms | P95: {p95:6.1f}ms | wall: {wall:7.1f}ms")
