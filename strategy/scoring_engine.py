import numpy as np
import pandas as pd
from .normalizer import normalize
from .critic_weights import compute_critic_weights
from data.metrics import get_latest_provider_snapshot, get_all_historical_data

def calculate_dynamic_scores(providers: list, method: str = None):
    """
    Compute CRITIC-based weights from historical data for a given RPC method
    and apply them on the latest record of each provider.

    Args:
        providers (list): List of provider objects
        method (str, optional): RPC method to filter by. If None, use all data.

    Returns:
        (pd.DataFrame, np.ndarray): DataFrame with scores, and weight vector [Latency, Price]
    """
    # Step 1: Historical data
    historical_df = get_all_historical_data(providers, method=method)
    if historical_df.empty:
        weights = np.array([0.5, 0.5])  # fallback equal weights
    else:
        historical_df["Lnorm"] = normalize(historical_df["Latency"])
        historical_df["Pnorm"] = normalize(historical_df["Price"])
        weights = compute_critic_weights(historical_df, ["Lnorm", "Pnorm"])

    # Step 2: Latest snapshot
    latest_df = get_latest_provider_snapshot(providers, method=method)
    if latest_df.empty:
        return latest_df, weights

    latest_df["Lnorm"] = normalize(latest_df["Latency"])
    latest_df["Pnorm"] = normalize(latest_df["Price"])
    latest_df["Score"] = np.dot(latest_df[["Lnorm", "Pnorm"]], weights)

    # Replace NaNs if still appear
    latest_df["Score"] = latest_df["Score"].fillna(0.0)

    return latest_df, weights
