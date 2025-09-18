import pandas as pd

def select_best_provider(df: pd.DataFrame) -> str:
    """
    Select best provider after applying filters.
    Example filter: drop providers with exhausted quota or unhealthy.
    """
    eligible = df[df["Eligible"] == True]
    if eligible.empty:
        return None
    return eligible.loc[eligible["Score"].idxmax(), "Provider"]