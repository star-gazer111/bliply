#!/usr/bin/env python3
"""
Unit tests for ScoreCache class.
"""

import pytest
import asyncio
import time
import pandas as pd
import numpy as np
from scoring.cache import ScoreCache


@pytest.mark.asyncio
async def test_cache_initialization():
    """Test that cache initializes with correct TTL."""
    cache = ScoreCache(ttl_seconds=10.0)
    assert cache.ttl_seconds == 10.0
    assert cache._hits == 0
    assert cache._misses == 0


@pytest.mark.asyncio
async def test_cache_miss_on_empty():
    """Test that cache returns None when empty."""
    cache = ScoreCache(ttl_seconds=5.0)
    result = await cache.get_cached_scores("eth_blockNumber")
    assert result is None
    
    stats = cache.get_stats()
    assert stats['misses'] == 1
    assert stats['hits'] == 0


@pytest.mark.asyncio
async def test_cache_set_and_get():
    """Test that cache stores and retrieves values correctly."""
    cache = ScoreCache(ttl_seconds=5.0)
    
    # Create test data
    test_df = pd.DataFrame({
        'Provider': ['alchemy', 'quicknode'],
        'Score': [0.8, 0.6]
    })
    test_weights = np.array([0.7, 0.3])
    
    # Store in cache
    await cache.set_cached_scores("eth_blockNumber", test_df, test_weights)
    
    # Retrieve from cache
    result = await cache.get_cached_scores("eth_blockNumber")
    assert result is not None
    
    cached_df, cached_weights = result
    assert cached_df.equals(test_df)
    assert np.array_equal(cached_weights, test_weights)
    
    stats = cache.get_stats()
    assert stats['hits'] == 1
    assert stats['misses'] == 0


@pytest.mark.asyncio
async def test_cache_expiration():
    """Test that cache expires after TTL."""
    cache = ScoreCache(ttl_seconds=0.5)  # 500ms TTL
    
    test_df = pd.DataFrame({'Provider': ['alchemy'], 'Score': [0.8]})
    test_weights = np.array([0.5, 0.5])
    
    # Store in cache
    await cache.set_cached_scores("eth_blockNumber", test_df, test_weights)
    
    # Should hit immediately
    result = await cache.get_cached_scores("eth_blockNumber")
    assert result is not None
    
    # Wait for expiration
    await asyncio.sleep(0.6)
    
    # Should miss after expiration
    result = await cache.get_cached_scores("eth_blockNumber")
    assert result is None
    
    stats = cache.get_stats()
    assert stats['hits'] == 1
    assert stats['misses'] == 1


@pytest.mark.asyncio
async def test_cache_per_method():
    """Test that cache stores different methods separately."""
    cache = ScoreCache(ttl_seconds=5.0)
    
    df1 = pd.DataFrame({'Provider': ['alchemy'], 'Score': [0.8]})
    df2 = pd.DataFrame({'Provider': ['quicknode'], 'Score': [0.9]})
    weights1 = np.array([0.6, 0.4])
    weights2 = np.array([0.7, 0.3])
    
    # Store different methods
    await cache.set_cached_scores("eth_blockNumber", df1, weights1)
    await cache.set_cached_scores("eth_getBalance", df2, weights2)
    
    # Retrieve each method
    result1 = await cache.get_cached_scores("eth_blockNumber")
    result2 = await cache.get_cached_scores("eth_getBalance")
    
    assert result1 is not None
    assert result2 is not None
    
    cached_df1, cached_weights1 = result1
    cached_df2, cached_weights2 = result2
    
    assert cached_df1.equals(df1)
    assert cached_df2.equals(df2)
    assert np.array_equal(cached_weights1, weights1)
    assert np.array_equal(cached_weights2, weights2)


@pytest.mark.asyncio
async def test_cache_invalidation_specific():
    """Test invalidating a specific method."""
    cache = ScoreCache(ttl_seconds=5.0)
    
    df = pd.DataFrame({'Provider': ['alchemy'], 'Score': [0.8]})
    weights = np.array([0.5, 0.5])
    
    await cache.set_cached_scores("eth_blockNumber", df, weights)
    await cache.set_cached_scores("eth_getBalance", df, weights)
    
    # Invalidate one method
    await cache.invalidate("eth_blockNumber")
    
    # Should miss on invalidated method
    result1 = await cache.get_cached_scores("eth_blockNumber")
    assert result1 is None
    
    # Should still hit on other method
    result2 = await cache.get_cached_scores("eth_getBalance")
    assert result2 is not None


@pytest.mark.asyncio
async def test_cache_invalidation_all():
    """Test invalidating all cached methods."""
    cache = ScoreCache(ttl_seconds=5.0)
    
    df = pd.DataFrame({'Provider': ['alchemy'], 'Score': [0.8]})
    weights = np.array([0.5, 0.5])
    
    await cache.set_cached_scores("eth_blockNumber", df, weights)
    await cache.set_cached_scores("eth_getBalance", df, weights)
    
    # Invalidate all
    await cache.invalidate()
    
    # Both should miss
    result1 = await cache.get_cached_scores("eth_blockNumber")
    result2 = await cache.get_cached_scores("eth_getBalance")
    
    assert result1 is None
    assert result2 is None


@pytest.mark.asyncio
async def test_cache_stats():
    """Test cache statistics tracking."""
    cache = ScoreCache(ttl_seconds=5.0)
    
    df = pd.DataFrame({'Provider': ['alchemy'], 'Score': [0.8]})
    weights = np.array([0.5, 0.5])
    
    # Initial stats
    stats = cache.get_stats()
    assert stats['hits'] == 0
    assert stats['misses'] == 0
    assert stats['total'] == 0
    assert stats['hit_rate_percent'] == 0.0
    
    # One miss
    await cache.get_cached_scores("eth_blockNumber")
    stats = cache.get_stats()
    assert stats['misses'] == 1
    assert stats['hit_rate_percent'] == 0.0
    
    # Store and hit
    await cache.set_cached_scores("eth_blockNumber", df, weights)
    await cache.get_cached_scores("eth_blockNumber")
    
    stats = cache.get_stats()
    assert stats['hits'] == 1
    assert stats['misses'] == 1
    assert stats['total'] == 2
    assert stats['hit_rate_percent'] == 50.0


@pytest.mark.asyncio
async def test_cache_reset_stats():
    """Test resetting cache statistics."""
    cache = ScoreCache(ttl_seconds=5.0)
    
    df = pd.DataFrame({'Provider': ['alchemy'], 'Score': [0.8]})
    weights = np.array([0.5, 0.5])
    
    await cache.set_cached_scores("eth_blockNumber", df, weights)
    await cache.get_cached_scores("eth_blockNumber")
    
    # Reset stats
    cache.reset_stats()
    
    stats = cache.get_stats()
    assert stats['hits'] == 0
    assert stats['misses'] == 0


@pytest.mark.asyncio
async def test_cache_concurrent_access():
    """Test that cache handles concurrent access correctly."""
    cache = ScoreCache(ttl_seconds=5.0)
    
    df = pd.DataFrame({'Provider': ['alchemy'], 'Score': [0.8]})
    weights = np.array([0.5, 0.5])
    
    await cache.set_cached_scores("eth_blockNumber", df, weights)
    
    # Concurrent reads
    results = await asyncio.gather(
        cache.get_cached_scores("eth_blockNumber"),
        cache.get_cached_scores("eth_blockNumber"),
        cache.get_cached_scores("eth_blockNumber"),
    )
    
    # All should succeed
    for result in results:
        assert result is not None
        cached_df, cached_weights = result
        assert cached_df.equals(df)
        assert np.array_equal(cached_weights, weights)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
