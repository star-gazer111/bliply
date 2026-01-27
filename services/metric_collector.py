from typing import List, Dict, Any
import pandas as pd
from data.providers import Provider
from data.metrics import get_latest_provider_snapshot

class MetricCollector:
    """
    Step 3: Collect Current Provider Metrics
    Fetches latency (Li) and price (Pi) for each provider for a specific method.
    """
    
    def __init__(self):
        self.cache = {}  # caching recent metrics
        self.cache_ttl = 5  # in seconds
    
    def collect_current_metrics(
        self, 
        providers: List[Provider], 
        method: str
    ) -> Dict[str, Any]:
        """
        Collect current metrics for all providers for a specific method.
        
        Args:
            providers: List of Provider objects
            method: RPC method name (e.g., "eth_blockNumber")
            
        Returns:
            {
                "method": str,
                "providers": {
                    "alchemy": {
                        "latency_ms": float,
                        "price_usd": float,
                        "eligible": bool,
                        "record_count": int
                    },
                    ...
                },
                "has_data": bool
            }
        """
        # Getting latest snapshot using existing function
        latest_df = get_latest_provider_snapshot(providers, method=method)
        
        # Checking if we have any data
        if latest_df.empty:
            return {
                "method": method,
                "providers": {},
                "has_data": False
            }
        
        # Build structured metrics dict
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
        provider: Provider, 
        method: str, 
        default: float = 1000.0
    ) -> float:
        """
        Get current latency for a specific provider/method.
        
        Args:
            provider: Provider object
            method: RPC method
            default: Default latency if no data
            
        Returns:
            Average latency in milliseconds
        """
        records = provider.metrics.get_all_records(method)
        
        if records.empty:
            return default
        
        return float(records["Latency"].mean())
    
    def get_provider_price(
        self, 
        provider: Provider, 
        method: str
    ) -> float:
        """
        Get current marginal price for a specific provider/method.
        
        Returns 0.0 if still in free tier, otherwise current price per request.
        
        Args:
            provider: Provider object
            method: RPC method
            
        Returns:
            Price in USD per request
        """
        
        # Here we are calling the provider's internal calculate_price() method which is pre-existing
        current_usage = provider.metrics.get_request_count(method)
        price = provider.calculate_marginal_price(current_usage)
        
        return float(price)
    
    def get_min_max_values(
        self,
        metrics: Dict[str, Any]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate min/max for latency and price across all providers.
        Needed for normalization (Lmin, Lmax, Pmin, Pmax).
        
        Args:
            metrics: Output from collect_current_metrics()
            
        Returns:
            {
                "latency": {"min": float, "max": float},
                "price": {"min": float, "max": float}
            }
        """
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
        providers: List[Provider], 
        method: str
    ) -> pd.DataFrame:
        """
        Get metrics as pandas DataFrame (for compatibility with existing code).
        
        Returns same format as get_latest_provider_snapshot().
        """
        return get_latest_provider_snapshot(providers, method=method)