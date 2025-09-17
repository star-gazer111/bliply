import pandas as pd

def normalize(series: pd.Series) -> pd.Series:
    """Normalize values to 0-1, lower values → higher score."""
    vmin, vmax = series.min(), series.max()
    if vmax == vmin:  # constant column → all equal score
        return pd.Series([1.0] * len(series), index=series.index)
    normed = 1 - (series - vmin) / (vmax - vmin)
    return normed.fillna(0.0)  # just in case
