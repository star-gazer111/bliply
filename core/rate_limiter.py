import time
from collections import defaultdict, deque

class RateLimiter:
    def __init__(self, window_size_seconds: int = 1):
        self.window_size = window_size_seconds
        # Dictionary to store request timestamps for each provider
        # provider_name -> deque of timestamps
        self.requests = defaultdict(deque)

    def is_allowed(self, provider_name: str, limit_rps: int) -> bool:
        """
        Check if a request is allowed for the given provider based on RPS limit.
        Uses a sliding window approach.
        """
        if limit_rps <= 0:
            return True # No limit

        current_time = time.time()
        timestamps = self.requests[provider_name]

        # Remove timestamps outside the window
        while timestamps and timestamps[0] < current_time - self.window_size:
            timestamps.popleft()

        # Check if we are within the limit
        if len(timestamps) < limit_rps:
            timestamps.append(current_time)
            return True
        
        return False
