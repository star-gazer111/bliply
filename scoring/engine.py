import numpy as np
import pandas as pd
from typing import Optional
from scoring.utils import normalize
from scoring.weights import compute_critic_weights
from metrics import get_latest_provider_snapshot, get_all_historical_data


async def calculate_dynamic_scores(
    providers: list, 
    method: str = None, 
    cache: Optional['ScoreCache'] = None
):
    """
    Calculate dynamic scores for providers using CRITIC weights.
    
    Args:
        providers: List of RPC providers
        method: RPC method name
        cache: Optional ScoreCache instance for caching results
        
    Returns:
        Tuple of (scores_df, weights)
    """
    # Check cache first if provided
    if cache is not None:
        cached_result = await cache.get_cached_scores(method)
        if cached_result is not None:
            print(f"[Scoring] ✅ Cache HIT for method={method}")
            return cached_result
        print(f"[Scoring] ❌ Cache MISS for method={method}")
    
    # Filter out "Best" provider from scoring
    actual_providers = [p for p in providers if p.name.lower() != "best"]
    
    historical_df = get_all_historical_data(actual_providers, method=method)
    if historical_df.empty:
        weights = np.array([0.5, 0.5])  # fallback equal weights
    else:
        historical_df["Lnorm"] = normalize(historical_df["Latency"])
        historical_df["Pnorm"] = normalize(historical_df["Price"])
        weights = compute_critic_weights(historical_df, ["Lnorm", "Pnorm"])

    latest_df = get_latest_provider_snapshot(actual_providers, method=method)
    if latest_df.empty:
        result = (latest_df, weights)
        if cache is not None:
            await cache.set_cached_scores(method, latest_df, weights)
        return result

    latest_df["Lnorm"] = normalize(latest_df["Latency"])
    latest_df["Pnorm"] = normalize(latest_df["Price"])
    latest_df["Score"] = np.dot(latest_df[["Lnorm", "Pnorm"]], weights)

    latest_df["Score"] = latest_df["Score"].fillna(0.0)

    # Cache the result if cache is provided
    if cache is not None:
        await cache.set_cached_scores(method, latest_df, weights)
        print(f"[Scoring] 💾 Cached scores for method={method}")

    return latest_df, weights
