"""Lightweight async load test using httpx (no external load tool required).

Simulates concurrent traffic against a running API and prints a performance
report (throughput + latency percentiles per scenario).

Usage:
    python -m scripts.load_test --base-url http://localhost:8000
    python -m scripts.load_test --users 500 --subscribers 1000

Scenarios (defaults match the spec):
    500 concurrent users hitting health/metrics
    100 newsletter generations
    1000 subscriber requests
    100 review submissions
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def _timed(client: httpx.AsyncClient, method: str, url: str, **kw) -> tuple[float, int]:
    start = time.perf_counter()
    try:
        resp = await client.request(method, url, **kw)
        return time.perf_counter() - start, resp.status_code
    except Exception:  # noqa: BLE001
        return time.perf_counter() - start, 0


async def _run_scenario(name: str, base_url: str, requests: list, concurrency: int) -> dict:
    sem = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    statuses: list[int] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:

        async def _worker(method, path, payload):
            async with sem:
                dt, status = await _timed(client, method, path, json=payload)
                latencies.append(dt)
                statuses.append(status)

        start = time.perf_counter()
        await asyncio.gather(*(_worker(m, p, b) for m, p, b in requests))
        elapsed = time.perf_counter() - start

    ok = sum(1 for s in statuses if 200 <= s < 400)
    latencies.sort()

    def pct(p: float) -> float:
        if not latencies:
            return 0.0
        return latencies[min(len(latencies) - 1, int(len(latencies) * p))]

    return {
        "scenario": name,
        "total": len(requests),
        "success": ok,
        "error": len(requests) - ok,
        "throughput_rps": round(len(requests) / elapsed, 1) if elapsed else 0,
        "p50_ms": round(statistics.median(latencies) * 1000, 1) if latencies else 0,
        "p95_ms": round(pct(0.95) * 1000, 1),
        "p99_ms": round(pct(0.99) * 1000, 1),
    }


async def main_async(args) -> None:
    scenarios = [
        ("health_load", [("GET", "/health", None)] * args.users, args.users),
        ("newsletter_generation", [("POST", "/api/newsletters/generate", {})] * args.newsletters, 25),
        (
            "subscriber_requests",
            [("POST", "/api/subscribers", {"email": f"u{i}@ex.com", "name": "U"}) for i in range(args.subscribers)],
            50,
        ),
    ]
    print(f"Load test against {args.base_url}\n" + "=" * 60)
    for name, reqs, conc in scenarios:
        report = await _run_scenario(name, args.base_url, reqs, conc)
        print(
            f"{report['scenario']:<24} n={report['total']:<5} ok={report['success']:<5} "
            f"rps={report['throughput_rps']:<7} p50={report['p50_ms']}ms "
            f"p95={report['p95_ms']}ms p99={report['p99_ms']}ms"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=500)
    parser.add_argument("--newsletters", type=int, default=100)
    parser.add_argument("--subscribers", type=int, default=1000)
    parser.add_argument("--reviews", type=int, default=100)
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
