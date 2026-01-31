import time
import asyncio
from typing import Dict, Tuple, Optional
import pandas as pd
import numpy as np


class ScoreCache:
    """
    Thread-safe cache for provider scores and CRITIC weights.
    
    Caches scores per RPC method to avoid expensive DataFrame operations
    and CRITIC weight calculations on every request.
    """
    
    def __init__(self, ttl_seconds: float = 5.0):
        """
        Initialize the score cache.
        
        Args:
            ttl_seconds: Time-to-live for cached entries in seconds (default: 5.0)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
        
        # Metrics for monitoring
        self._hits = 0
        self._misses = 0
    
    async def get_cached_scores(
        self, method: str
    ) -> Optional[Tuple[pd.DataFrame, np.ndarray]]:
        """
        Get cached scores and weights for a method if still valid.
        
        Args:
            method: RPC method name
            
        Returns:
            Tuple of (scores_df, weights) if cache is valid, None otherwise
        """
        async with self._lock:
            if method not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[method]
            age = time.time() - entry['timestamp']
            
            if age > self.ttl_seconds:
                # Cache expired
                del self._cache[method]
                self._misses += 1
                return None
            
            # Cache hit
            self._hits += 1
            return entry['scores_df'].copy(), entry['weights'].copy()
    
    async def set_cached_scores(
        self, method: str, scores_df: pd.DataFrame, weights: np.ndarray
    ):
        """
        Store scores and weights in cache with current timestamp.
        
        Args:
            method: RPC method name
            scores_df: DataFrame with provider scores
            weights: CRITIC weights array
        """
        async with self._lock:
            self._cache[method] = {
                'scores_df': scores_df.copy(),
                'weights': weights.copy(),
                'timestamp': time.time()
            }
    
    async def invalidate(self, method: Optional[str] = None):
        """
        Invalidate cache entries.
        
        Args:
            method: Specific method to invalidate, or None to clear all
        """
        async with self._lock:
            if method is None:
                self._cache.clear()
            elif method in self._cache:
                del self._cache[method]
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with hits, misses, and hit rate
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        
        return {
            'hits': self._hits,
            'misses': self._misses,
            'total': total,
            'hit_rate_percent': round(hit_rate, 2),
            'cached_methods': len(self._cache)
        }
    
    def reset_stats(self):
        """Reset cache statistics."""
        self._hits = 0
        self._misses = 0
