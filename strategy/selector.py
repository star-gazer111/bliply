import pandas as pd

def select_best_provider(df: pd.DataFrame) -> str:
    eligible = df[df["Eligible"] == True]
    if eligible.empty:
        return None
    return eligible.loc[eligible["Score"].idxmax(), "Provider"]