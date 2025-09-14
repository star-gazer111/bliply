import numpy as np
import pandas as pd
from .normalizer import normalize
from .critic_weights import compute_critic_weights
from data.metrics import get_latest_provider_snapshot, get_all_historical_data

def calculate_dynamic_scores(providers: list):
    """
    Compute CRITIC-based weights from all historical data and
    apply them on the latest record of each provider.
    """
    # Step 1: Get all historical data for weights
    historical_df = get_all_historical_data(providers)
    if historical_df.empty:
        weights = np.array([0.5, 0.5])
    else:
        historical_df["Lnorm"] = normalize(historical_df["Latency"])
        historical_df["Pnorm"] = normalize(historical_df["Price"])
        weights = compute_critic_weights(historical_df, ["Lnorm", "Pnorm"])

    # Step 2: Latest snapshot for scoring
    latest_df = get_latest_provider_snapshot(providers)
    if latest_df.empty:
        return latest_df, weights

    latest_df["Lnorm"] = normalize(latest_df["Latency"])
    latest_df["Pnorm"] = normalize(latest_df["Price"])
    latest_df["Score"] = np.dot(latest_df[["Lnorm", "Pnorm"]], weights)

    return latest_df, weights