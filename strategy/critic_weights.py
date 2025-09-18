import numpy as np
import pandas as pd

def compute_critic_weights(df: pd.DataFrame, criteria: list[str]) -> np.ndarray:
    norm_matrix = df[criteria].to_numpy(dtype=float)

    if norm_matrix.shape[0] < 2:  
        return np.array([1 / len(criteria)] * len(criteria))

    stds = np.std(norm_matrix, axis=0, ddof=1)
    corr_matrix = np.corrcoef(norm_matrix.T)
    corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)

    C = []
    for j in range(len(criteria)):
        if stds[j] < 1e-9:  # constant or nearly constant metric
            C.append(0.0)
            continue

        corr_sum = np.sum(np.abs(corr_matrix[j])) - 1  # exclude self-corr
        Cj = stds[j] * (1 - (corr_sum / (len(criteria) - 1)))
        C.append(max(Cj, 0.0))

    C = np.array(C)

    if np.sum(C) == 0:
        return np.array([1 / len(criteria)] * len(criteria))
    weights = C / np.sum(C)
    return weights
