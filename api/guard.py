"""Bounds on a deliberately public demo.

An unauthenticated endpoint that starts Docker containers is the exact failure this
project exists to prevent, so the public URL is bounded rather than trusted:

  - per-IP rate limit      (a juror clicking twice must still work)
  - global concurrency cap (one run at a time on a 1-vCPU box)
  - daily run cap          (bounds token spend and container churn)
  - optional bearer token  (switch: after judging, or if the URL leaks)

The token is optional on purpose. A demo that requires credentials the jury does not
have is not a demo. Limits are the protection; the token is the off switch.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque


class Decision:
    def __init__(self, allowed, reason="", retry_after=0):
        self.allowed = allowed
        self.reason = reason
        self.retry_after = retry_after

    def as_dict(self):
        return {"allowed": self.allowed, "reason": self.reason}


class Guard:
    def __init__(self, per_hour=12, max_concurrent=1, daily_cap=150, token="",
                 ip_daily_cap=20):
        self.per_hour = per_hour
        self.max_concurrent = max_concurrent
        self.daily_cap = daily_cap
        self.ip_daily_cap = ip_daily_cap
        self.token = token.strip()
        self._lock = threading.Lock()
        self._hits = defaultdict(deque)
        self._active = 0
        self._day = time.strftime("%Y-%m-%d", time.gmtime())
        self._runs_today = 0
        self._per_ip_day = {}

    @classmethod
    def from_env(cls):
        return cls(
            per_hour=int(os.environ.get("AR_RATE_PER_HOUR", "12")),
            max_concurrent=int(os.environ.get("AR_MAX_CONCURRENT", "1")),
            daily_cap=int(os.environ.get("AR_DAILY_RUNS", "150")),
            token=os.environ.get("AR_API_TOKEN", ""),
            ip_daily_cap=int(os.environ.get("AR_IP_DAILY", "20")),
        )

    def _roll_day(self):
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if today != self._day:
            self._day = today
            self._runs_today = 0
            self._hits.clear()
            self._per_ip_day.clear()

    def check(self, ip, provided_token=""):
        """Decide whether this request may start a run. Never raises."""
        with self._lock:
            self._roll_day()

            if self.token and provided_token != self.token:
                return Decision(False, "missing or invalid token", 0)

            if self._runs_today >= self.daily_cap:
                return Decision(False, "daily run cap reached", 3600)

            # One visitor must not be able to eat the day. The hourly limit alone
            # allows 12 * 24 runs; this is the actual budget per address.
            if self._per_ip_day.get(ip, 0) >= self.ip_daily_cap:
                return Decision(False, "your daily quota for this demo is used up", 3600)

            now = time.monotonic()
            window = self._hits[ip]
            while window and now - window[0] > 3600:
                window.popleft()
            if len(window) >= self.per_hour:
                retry = int(3600 - (now - window[0])) + 1
                return Decision(False, "rate limit reached", retry)

            if self._active >= self.max_concurrent:
                return Decision(False, "a run is already in progress", 5)

            window.append(now)
            return Decision(True)

    def begin(self, ip="unknown"):
        with self._lock:
            self._active += 1
            self._runs_today += 1
            self._per_ip_day[ip] = self._per_ip_day.get(ip, 0) + 1

    def end(self):
        with self._lock:
            self._active = max(0, self._active - 1)

    def snapshot(self):
        with self._lock:
            return {
                "per_hour": self.per_hour,
                "max_concurrent": self.max_concurrent,
                "daily_cap": self.daily_cap,
                "runs_today": self._runs_today,
                "ip_daily_cap": self.ip_daily_cap,
                "active": self._active,
                "token_required": bool(self.token),
            }
