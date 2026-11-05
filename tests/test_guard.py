#!/usr/bin/env python3
"""Guard tests: the public URL is bounded.  python3 tests/test_guard.py"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from api.guard import Guard  # noqa: E402

results = []


def check(name, fn):
    try:
        fn()
        results.append((name, None))
        print(f"  ok    {name}")
    except Exception as exc:  # noqa: BLE001
        results.append((name, exc))
        print(f"  FAIL  {name}: {exc}")


def test_rate_limit_per_ip():
    g = Guard(per_hour=2, max_concurrent=10)
    assert g.check("1.1.1.1").allowed
    assert g.check("1.1.1.1").allowed
    third = g.check("1.1.1.1")
    assert not third.allowed and "rate limit" in third.reason, third.reason
    assert third.retry_after > 0
    assert g.check("2.2.2.2").allowed, "a different ip must not be punished"


def test_concurrency_cap():
    g = Guard(per_hour=10, max_concurrent=1)
    assert g.check("1.1.1.1").allowed
    g.begin()
    second = g.check("2.2.2.2")
    assert not second.allowed and "in progress" in second.reason, second.reason
    g.end()
    assert g.check("2.2.2.2").allowed


def test_daily_cap():
    g = Guard(per_hour=100, max_concurrent=100, daily_cap=2)
    for _ in range(2):
        assert g.check("1.1.1.1").allowed
        g.begin()
        g.end()
    blocked = g.check("1.1.1.1")
    assert not blocked.allowed and "daily" in blocked.reason, blocked.reason


def test_token_required_when_configured():
    g = Guard(per_hour=10, max_concurrent=2, token="s3cret")
    assert not g.check("1.1.1.1", "").allowed
    assert not g.check("1.1.1.1", "wrong").allowed
    assert g.check("1.1.1.1", "s3cret").allowed


def test_no_token_means_open_but_bounded():
    g = Guard(per_hour=1, max_concurrent=2)
    assert g.check("1.1.1.1", "").allowed
    assert not g.check("1.1.1.1", "").allowed


def test_snapshot():
    g = Guard(per_hour=5, max_concurrent=1, daily_cap=9)
    snap = g.snapshot()
    assert snap["per_hour"] == 5 and snap["daily_cap"] == 9
    assert snap["token_required"] is False


def main() -> int:
    print("guard")
    check("per-ip rate limit", test_rate_limit_per_ip)
    check("concurrency cap", test_concurrency_cap)
    check("daily cap", test_daily_cap)
    check("token when configured", test_token_required_when_configured)
    check("open but bounded without token", test_no_token_means_open_but_bounded)
    check("snapshot", test_snapshot)
    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
