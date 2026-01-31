from typing import List, Dict, Any
import pandas as pd
from providers.base import RPCProvider


WINDOW_SIZE = (
    10  # Using a constant for loading the recent records as per suggestion in first PR
)


class EligibilityFilter:
    def __init__(
        self,
        health_threshold: float = 0.95,  # 95% success rate minimum
        consecutive_failure_limit: int = 3,
    ):
        self.health_threshold = health_threshold
        self.consecutive_failure_limit = consecutive_failure_limit
        self.provider_health_status = {}  # Track health per provider

    def filter_providers(
        self, providers: List[RPCProvider], method: str, metrics_df: pd.DataFrame = None
    ) -> List[RPCProvider]:
        eligible_providers = []
        filtered_reasons = {}

        for provider in providers:
            if provider.name.lower() == "best":
                filtered_reasons[provider.name] = "Virtual provider"
                continue

            if not self._check_quota(provider, method):
                filtered_reasons[provider.name] = "Quota exhausted"
                continue

            if not self._check_health(provider, method):
                filtered_reasons[provider.name] = "Unhealthy (high error rate)"
                continue

            if not self._has_sufficient_data(provider, method):
                if self._is_new_provider(provider, method):
                    # New provider: allow it to collect initial data
                    eligible_providers.append(provider)
                else:
                    # Has some data but not enough: filter out
                    filtered_reasons[provider.name] = "Insufficient data"
                continue

            eligible_providers.append(provider)

        if filtered_reasons:
            print(f"[EligibilityFilter] Method: {method}")
            for prov, reason in filtered_reasons.items():
                print(f"  ✗ {prov}: {reason}")

        print(
            f"[EligibilityFilter] {len(eligible_providers)}/{len(providers)} providers eligible"
        )

        return eligible_providers

    def filter_dataframe(
        self, df: pd.DataFrame, allow_fallback: bool = True
    ) -> pd.DataFrame:
        if df.empty:
            return df

        eligible_df = df[df["Eligible"] == True]

        eligible_df = eligible_df[eligible_df["Provider"].str.lower() != "best"]

        if eligible_df.empty and allow_fallback:
            print("[EligibilityFilter] No eligible providers, using all as fallback")
            eligible_df = df[df["Provider"].str.lower() != "best"]

        return eligible_df

    def _check_quota(self, provider: RPCProvider, method: str) -> bool:
        if hasattr(provider, "quota_manager"):
            return provider.quota_manager.has_quota(method)

        return True

    def _check_health(self, provider: RPCProvider, method: str) -> bool:
        records = provider.metrics.get_all_records(method)

        if records.empty:
            return True

        recent_records = records.tail(WINDOW_SIZE)  # Last 10 requests

        return True  # Always healthy for now

    def _has_sufficient_data(self, provider: RPCProvider, method: str) -> bool:
        records = provider.metrics.get_all_records(method)

        return len(records) > 0

    def _is_new_provider(self, provider: RPCProvider, method: str) -> bool:
        records = provider.metrics.get_all_records(method)
        return len(records) == 0

    def mark_unhealthy(self, provider_name: str, reason: str):
        self.provider_health_status[provider_name] = {
            "healthy": False,
            "reason": reason,
        }
        print(f"[EligibilityFilter] Marked {provider_name} as unhealthy: {reason}")

    def mark_healthy(self, provider_name: str):
        self.provider_health_status[provider_name] = {
            "healthy": True,
            "reason": "Recovered",
        }
        print(f"[EligibilityFilter] Marked {provider_name} as healthy")

    def get_health_status(self) -> Dict[str, Any]:
        return self.provider_health_status.copy()
