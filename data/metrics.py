import pandas as pd


class MetricsStore:
    def __init__(self):
        self.df = pd.DataFrame(
            columns=["Provider", "Method", "Latency", "Price", "Eligible", "RequestCount"]
        )
        self.request_counts = {}
        
    def add_record(self, provider: str, method: str, latency_ms: float, price: float):
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
        return self.df.copy()

    def get_latest(self, method: str) -> pd.DataFrame:
        df_method = self.df[self.df["Method"] == method]
        latest_records = []
        for provider in df_method["Provider"].unique():
            df_provider = df_method[df_method["Provider"] == provider]
            latest_records.append(df_provider.iloc[-1])
        return pd.DataFrame(latest_records)

    def get_all_records(self, method: str = None) -> pd.DataFrame:
        if method:
            return self.df[self.df["Method"] == method].copy()
        return self.df.copy()

    def get_request_count(self, provider: str, method: str) -> int:
        return self.request_counts.get((provider, method), 0)

    def get_all_request_counts(self) -> dict:
        return self.request_counts.copy()



def get_latest_provider_snapshot(providers: list, method: str) -> pd.DataFrame:
    latest = pd.concat([p.metrics.get_latest(method) for p in providers], ignore_index=True)
    return latest


def get_all_historical_data(providers: list, method: str) -> pd.DataFrame:
    all_records = pd.concat([p.metrics.get_all_records(method) for p in providers], ignore_index=True)
    return all_records if not all_records.empty else pd.DataFrame()
