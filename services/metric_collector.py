from typing import List, Dict, Any
import pandas as pd
from providers.base import RPCProvider
from metrics import get_latest_provider_snapshot

class MetricCollector:
    def __init__(self):
        self.cache = {}  # caching recent metrics
        self.cache_ttl = 5  # in seconds
    
    def collect_current_metrics(
        self, 
        providers: List[RPCProvider], 
        method: str
    ) -> Dict[str, Any]:
        latest_df = get_latest_provider_snapshot(providers, method=method)
        
        if latest_df.empty:
            return {
                "method": method,
                "providers": {},
                "has_data": False
            }
        
        metrics = {
            "method": method,
            "providers": {},
            "has_data": True
        }
        
        for _, row in latest_df.iterrows():
            provider_name = row["Provider"].lower()
            
            metrics["providers"][provider_name] = {
                "latency_ms": float(row["Latency"]),
                "price_usd": float(row["Price"]),
                "eligible": bool(row["Eligible"]),
                "record_count": int(row.get("Count", 0))
            }
        
        return metrics
    
    def get_provider_latency(
        self, 
        provider: RPCProvider, 
        method: str, 
        default: float = 1000.0
    ) -> float:
        """
        Get the median latency of the last 10 requests to avoid outliers.
        """
        records = provider.metrics.get_all_records(method)
        
        if records.empty:
            return default
        
        # Take the last 10 records for this method
        recent = records.tail(10)
        return float(recent["Latency"].median())
    
    def get_provider_price(
        self, 
        provider: RPCProvider, 
        method: str
    ) -> float:
        current_usage = provider.metrics.get_request_count(method)
        price = provider.calculate_marginal_price(current_usage)
        
        return float(price)
    
    def get_min_max_values(
        self,
        metrics: Dict[str, Any]
    ) -> Dict[str, Dict[str, float]]:
        if not metrics["has_data"]:
            return {
                "latency": {"min": 0.0, "max": 1.0},
                "price": {"min": 0.0, "max": 1.0}
            }
        
        latencies = [p["latency_ms"] for p in metrics["providers"].values()]
        prices = [p["price_usd"] for p in metrics["providers"].values()]
        
        return {
            "latency": {
                "min": min(latencies) if latencies else 0.0,
                "max": max(latencies) if latencies else 1.0
            },
            "price": {
                "min": min(prices) if prices else 0.0,
                "max": max(prices) if prices else 1.0
            }
        }
    
    def get_dataframe(
        self, 
        providers: List[RPCProvider], 
        method: str
    ) -> pd.DataFrame:
        return get_latest_provider_snapshot(providers, method=method)
