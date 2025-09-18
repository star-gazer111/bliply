import numpy as np
import pandas as pd
from .normalizer import normalize
from .critic_weights import compute_critic_weights
from data.metrics import get_latest_provider_snapshot, get_all_historical_data

def calculate_dynamic_scores(providers: list, method: str = None):
 
    historical_df = get_all_historical_data(providers, method=method)
    if historical_df.empty:
        weights = np.array([0.5, 0.5])  # fallback equal weights
    else:
        historical_df["Lnorm"] = normalize(historical_df["Latency"])
        historical_df["Pnorm"] = normalize(historical_df["Price"])
        weights = compute_critic_weights(historical_df, ["Lnorm", "Pnorm"])

    latest_df = get_latest_provider_snapshot(providers, method=method)
    if latest_df.empty:
        return latest_df, weights

    latest_df["Lnorm"] = normalize(latest_df["Latency"])
    latest_df["Pnorm"] = normalize(latest_df["Price"])
    latest_df["Score"] = np.dot(latest_df[["Lnorm", "Pnorm"]], weights)
    latest_df["Score"] = latest_df["Score"].fillna(0.0)

    return latest_df, weights
