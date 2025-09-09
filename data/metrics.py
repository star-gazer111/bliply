import pandas as pd

class MetricsStore:
    """Stores metrics for providers."""
    def __init__(self):
        self.df = pd.DataFrame(columns=["Provider", "Latency", "Price", "Eligible"])

    def add_record(self, provider: str, latency_ms: float, price: float):
        row = {
            "Provider": provider,
            "Latency": latency_ms,
            "Price": price,
            "Eligible": True
        }
        self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)

    def get_df(self) -> pd.DataFrame:
        return self.df.copy()

    def get_latest(self) -> pd.DataFrame:
        """Return latest record per provider."""
        latest_records = []
        for provider in self.df["Provider"].unique():
            df_provider = self.df[self.df["Provider"] == provider]
            latest_records.append(df_provider.iloc[-1])
        return pd.DataFrame(latest_records)

    def get_all_records(self) -> pd.DataFrame:
        return self.df.copy()


def get_latest_provider_snapshot(providers: list) -> pd.DataFrame:
    """Return latest record per provider instance."""
    latest = pd.concat([p.metrics.get_latest() for p in providers], ignore_index=True)
    return latest

def get_all_historical_data(providers: list) -> pd.DataFrame:
    """Return all historical records across providers."""
    all_records = pd.concat([p.metrics.get_all_records() for p in providers], ignore_index=True)
    return all_records if not all_records.empty else pd.DataFrame()
