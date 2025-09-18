import pandas as pd


class MetricsStore:
    """Stores metrics for providers, separated by method."""

    def __init__(self):
        self.df = pd.DataFrame(
            columns=["Provider", "Method", "Latency", "Price", "Eligible", "RequestCount"]
        )
        # Track total requests per (provider, method)
        self.request_counts = {}
        
    def add_record(self, provider: str, method: str, latency_ms: float, price: float):
        """Add a new metric record for a provider & method."""
        key = (provider, method)
        self.request_counts[key] = self.request_counts.get(key, 0) + 1

        row = {
            "Provider": provider,
            "Method": method,
            "Latency": latency_ms,
            "Price": price,
            "Eligible": True,
            "RequestCount": self.request_counts[key],
        }
        self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)

    def get_df(self) -> pd.DataFrame:
        """Return full copy of all records."""
        return self.df.copy()

    def get_latest(self, method: str) -> pd.DataFrame:
        """Return latest record per provider for a given method."""
        df_method = self.df[self.df["Method"] == method]
        latest_records = []
        for provider in df_method["Provider"].unique():
            df_provider = df_method[df_method["Provider"] == provider]
            latest_records.append(df_provider.iloc[-1])
        return pd.DataFrame(latest_records)

    def get_all_records(self, method: str = None) -> pd.DataFrame:
        """Return all records, optionally filtered by method."""
        if method:
            return self.df[self.df["Method"] == method].copy()
        return self.df.copy()

    def get_request_count(self, provider: str, method: str) -> int:
        """Get total number of requests made for a specific provider & method."""
        return self.request_counts.get((provider, method), 0)

    def get_all_request_counts(self) -> dict:
        """Get request counts for all (provider, method) pairs."""
        return self.request_counts.copy()

def get_latest_provider_snapshot(providers: list, method: str) -> pd.DataFrame:
    """Return latest record per provider for a given method."""
    latest = pd.concat([p.metrics.get_latest(method) for p in providers], ignore_index=True)
    return latest


def get_all_historical_data(providers: list, method: str) -> pd.DataFrame:
    """Return all historical records across providers for a given method."""
    all_records = pd.concat([p.metrics.get_all_records(method) for p in providers], ignore_index=True)
    return all_records if not all_records.empty else pd.DataFrame()
