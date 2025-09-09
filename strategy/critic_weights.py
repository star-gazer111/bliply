import numpy as np

def compute_critic_weights(df, criteria: list[str]) -> np.ndarray:
    """
    Compute CRITIC weights from historical data.
    """
    norm_matrix = df[criteria].to_numpy()
    
    if norm_matrix.shape[0] < 2:
        return np.array([0.5] * len(criteria))

    # Standard deviation
    stds = np.std(norm_matrix, axis=0, ddof=1)
    
    # Correlation matrix
    corr_matrix = np.corrcoef(norm_matrix.T)
    
    # Information content Cj
    C = []
    for j in range(len(criteria)):
        corr_sum = np.sum(np.abs(corr_matrix[j])) - 1  # exclude self-corr
        Cj = stds[j] * (1 - (corr_sum / (len(criteria) - 1)))
        C.append(max(Cj, 1e-10))
    C = np.array(C)

    # Normalize
    weights = C / np.sum(C)
    return weights
