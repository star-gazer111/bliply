from typing import List, Dict, Any
import pandas as pd
from data.providers import Provider

class EligibilityFilter:
    """
    Step 7: Eligibility Filter
    Removes providers that:
    - Have exhausted quota for method/chain
    - Are currently unhealthy (timeouts, error spikes)
    """
    
    def __init__(
        self, 
        health_threshold: float = 0.95,  # 95% success rate minimum
        consecutive_failure_limit: int = 3
    ):
        """
        Args:
            health_threshold: Minimum success rate (0.0 to 1.0)
            consecutive_failure_limit: Max consecutive failures before marking unhealthy
        """
        self.health_threshold = health_threshold
        self.consecutive_failure_limit = consecutive_failure_limit
        self.provider_health_status = {}  # Track health per provider
    
    def filter_providers(
        self, 
        providers: List[Provider], 
        method: str,
        metrics_df: pd.DataFrame = None
    ) -> List[Provider]:
        """
        Filter providers to only eligible ones for a specific method.
        
        Args:
            providers: List of all Provider objects
            method: RPC method name
            metrics_df: Optional DataFrame with current metrics
            
        Returns:
            List of eligible Provider objects
        """
        eligible_providers = []
        filtered_reasons = {}
        
        for provider in providers:
            # Skip the "Best" virtual provider (avoid recursion)
            if provider.name.lower() == "best":
                filtered_reasons[provider.name] = "Virtual provider"
                continue
            
            # Check 1: Quota exhausted?
            if not self._check_quota(provider, method):
                filtered_reasons[provider.name] = "Quota exhausted"
                continue
            
            # Check 2: Provider healthy?
            if not self._check_health(provider, method):
                filtered_reasons[provider.name] = "Unhealthy (high error rate)"
                continue
            
            # Check 3: Has any data? (can't route if no metrics)
            if not self._has_sufficient_data(provider, method):
                filtered_reasons[provider.name] = "Insufficient data"
                # Allow if it's a new provider (give it a chance)
                if self._is_new_provider(provider, method):
                    eligible_providers.append(provider)
                continue
            
            # Passed all checks
            eligible_providers.append(provider)
        
        # Log filtering decisions
        if filtered_reasons:
            print(f"[EligibilityFilter] Method: {method}")
            for prov, reason in filtered_reasons.items():
                print(f"  ✗ {prov}: {reason}")
        
        print(f"[EligibilityFilter] {len(eligible_providers)}/{len(providers)} providers eligible")
        
        return eligible_providers
    
    def filter_dataframe(
        self, 
        df: pd.DataFrame, 
        allow_fallback: bool = True
    ) -> pd.DataFrame:
        """
        Filter a metrics DataFrame to only eligible providers.
        Compatible with existing main.py code.
        
        Args:
            df: DataFrame with "Provider" and "Eligible" columns
            allow_fallback: If True and no eligible found, return all
            
        Returns:
            Filtered DataFrame
        """
        if df.empty:
            return df
        
        # Filter by Eligible column (existing logic)
        eligible_df = df[df["Eligible"] == True]
        
        # Also filter out "Best" provider to avoid recursion
        eligible_df = eligible_df[eligible_df["Provider"].str.lower() != "best"]
        
        # Fallback: if no eligible, return all except Best
        if eligible_df.empty and allow_fallback:
            print("[EligibilityFilter] No eligible providers, using all as fallback")
            eligible_df = df[df["Provider"].str.lower() != "best"]
        
        return eligible_df
    
    def _check_quota(self, provider: Provider, method: str) -> bool:
        """
        Check if provider has quota remaining for this method.
        
        For now, always returns True (quota management not implemented yet).
        Will be enhanced when services/quota_manager.py is built.
        """
        # TODO: Integrate with QuotaManager when implemented
        # For now, use basic check from provider's metrics
        
        # Check if provider tracks quota
        if hasattr(provider, 'quota_manager'):
            return provider.quota_manager.has_quota(method)
        
        # Default: assume quota available
        return True
    
    def _check_health(self, provider: Provider, method: str) -> bool:
        """
        Check if provider is healthy based on recent success rate.
        
        For now, simple check based on recent records.
        Will be enhanced when services/health_checker.py is built.
        """
        # TODO: Integrate with HealthChecker when implemented
        
        # Get recent records for this method
        records = provider.metrics.get_all_records(method)
        
        if records.empty:
            # No data yet, assume healthy (give it a chance)
            return True
        
        # Simple health check: look at last N records
        recent_records = records.tail(10)  # Last 10 requests
        
        # Count successes (assuming we track success/failure)
        # For now, assume all records are successes (no error tracking yet)
        # This will be enhanced with proper error tracking
        
        return True  # Always healthy for now
    
    def _has_sufficient_data(self, provider: Provider, method: str) -> bool:
        """
        Check if provider has enough data points for reliable scoring.
        """
        records = provider.metrics.get_all_records(method)
        
        # Need at least 1 record to calculate metrics
        return len(records) > 0
    
    def _is_new_provider(self, provider: Provider, method: str) -> bool:
        """
        Check if this is a new provider with no data yet.
        New providers should be given a chance (exploration).
        """
        records = provider.metrics.get_all_records(method)
        return len(records) == 0
    
    def mark_unhealthy(self, provider_name: str, reason: str):
        """
        Manually mark a provider as unhealthy.
        Used when a provider times out or returns errors.
        """
        self.provider_health_status[provider_name] = {
            "healthy": False,
            "reason": reason
        }
        print(f"[EligibilityFilter] Marked {provider_name} as unhealthy: {reason}")
    
    def mark_healthy(self, provider_name: str):
        """
        Mark a provider as healthy (recovered from issues).
        """
        self.provider_health_status[provider_name] = {
            "healthy": True,
            "reason": "Recovered"
        }
        print(f"[EligibilityFilter] Marked {provider_name} as healthy")
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of all tracked providers.
        """
        return self.provider_health_status.copy()