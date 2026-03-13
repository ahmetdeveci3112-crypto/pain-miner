# scrapers/rate_limiter.py — Simple rolling window rate limiter

import time
from datetime import datetime, timezone


class RateLimiter:
    """Simple rolling window limiter — allows up to N requests per 60 seconds."""

    def __init__(self, requests_per_minute: int = 60):
        self.limit = requests_per_minute
        self.window_start = datetime.now(timezone.utc)
        self.request_count = 0

    def wait(self):
        now = datetime.now(timezone.utc)
        elapsed = (now - self.window_start).total_seconds()

        if elapsed > 60:
            self.window_start = now
            self.request_count = 1
            return

        if self.request_count >= self.limit:
            wait_time = max(0.1, 60 - elapsed)
            time.sleep(wait_time)
            self.window_start = datetime.now(timezone.utc)
            self.request_count = 1
            return

        self.request_count += 1
