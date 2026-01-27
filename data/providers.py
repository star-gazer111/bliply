"""
This file has providers
"""

import time
from typing import Dict, Any, List, Optional
from core.config import (
    PROVIDERS,
    PRICING_CONFIG,
    ALCHEMY_COMPUTE_UNITS,
    QUICKNODE_CREDITS,
)
from .metrics import MetricsStore


class Provider:
    """
    Base class for RPC providers.
    Now focuses only on pricing logic - HTTP calls delegated to RPCClient.
    """

    def __init__(self, config: dict):
        self.name = config["name"]
        self.base_url = config["base_url"]
        self.config = config
        self.metrics = MetricsStore()

    def price_per_call(self, method: str = None) -> float:
        """
        Calculate price per call for this provider.
        Override in subclasses for provider-specific pricing.

        Args:
            method: RPC method name

        Returns:
            Price in USD per request
        """
        return 0.0

    def calculate_marginal_price(self, current_usage: int, method: str = None) -> float:
        """
        Calculate marginal price based on current usage.
        Used by metric_collector to determine if free tier is exhausted.

        Args:
            current_usage: Total requests so far
            method: RPC method name (needed for method-specific pricing)

        Returns:
            Current price per request (0.0 if in free tier)
        """
        return self.price_per_call(method)

    def call(
        self,
        payload: Dict[str, Any],
        all_providers: Optional[List["Provider"]] = None,
        rpc_client=None,
    ) -> Dict[str, Any]:
        """
        Legacy method for backward compatibility.
        Now uses RPCClient if provided, otherwise falls back to direct HTTP.

        DEPRECATED: New code should use RPCOptimizer instead.

        Args:
            payload: JSON-RPC request
            all_providers: List of all providers (for scoring)
            rpc_client: Optional RPCClient instance

        Returns:
            Response with metadata
        """
        method = payload.get("method", "")

        # Use RPCClient if provided
        if rpc_client is not None:
            try:
                result, latency_ms = rpc_client.send_request(
                    provider_url=self.base_url, payload=payload, timeout=10
                )
            except Exception as e:
                result = {"error": str(e)}
                latency_ms = 10000.0  # Max timeout
        else:
            # Fallback to direct HTTP (for backward compatibility)
            import requests

            start = time.time()
            try:
                response = requests.post(self.base_url, json=payload, timeout=10)
                response.raise_for_status()
                result = response.json()
            except Exception as e:
                result = {"error": str(e)}
            finally:
                latency_ms = (time.time() - start) * 1000

        # Calculate price
        price = self.price_per_call(method)

        # Update metrics
        self.metrics.add_record(
            provider=self.name, method=method, latency_ms=latency_ms, price=price
        )

        # Calculate score (legacy - kept for backward compatibility)
        score = 0.5
        weights = [0.5, 0.5]

        if all_providers:
            try:
                from strategy.scoring_engine import calculate_dynamic_scores

                scored_df, calc_weights = calculate_dynamic_scores(
                    all_providers, method=method
                )
                provider_row = scored_df[scored_df["Provider"] == self.name]
                if not provider_row.empty:
                    score = float(provider_row["Score"].iloc[0])
                    weights = calc_weights
            except Exception:
                pass

        return {
            "response": result,
            "latency_ms": latency_ms,
            "price_usd": price,
            "weights": {"Latency": weights[0], "Price": weights[1]},
            "score": score,
        }

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name}>"


class ChainstackProvider(Provider):
    """
    Chainstack pricing: volume-based tiers
    Low volume: $0.00005 per request
    High volume: $0.00003 per request (after 10M requests)
    """

    def price_per_call(self, method: str = None) -> float:
        total_requests = self.metrics.get_request_count(self.name, method)

        if total_requests > PRICING_CONFIG["chainstack"]["threshold"]:
            return PRICING_CONFIG["chainstack"]["high_volume_price"]

        return PRICING_CONFIG["chainstack"]["low_volume_price"]


class AlchemyProvider(Provider):
    """
    Alchemy pricing: compute unit based
    Each method consumes different compute units
    Low volume: $0.000001 per CU
    High volume: $0.0000005 per CU (after 100M CU)
    """

    def price_per_call(self, method: str = None) -> float:
        compute_units = ALCHEMY_COMPUTE_UNITS.get(method, 0)
        total_requests = self.metrics.get_request_count(self.name, method)
        total_cu = total_requests * compute_units

        if total_cu > PRICING_CONFIG["alchemy"]["threshold"]:
            return PRICING_CONFIG["alchemy"]["high_volume_price"] * compute_units

        return PRICING_CONFIG["alchemy"]["low_volume_price"] * compute_units


class QuickNodeProvider(Provider):
    """
    QuickNode pricing: credit based
    Each method consumes different credits
    Low volume: $0.000005 per credit
    High volume: $0.000003 per credit (after 50M credits)
    """

    def price_per_call(self, method: str = None) -> float:
        credits = QUICKNODE_CREDITS.get(method, 20)
        total_requests = self.metrics.get_request_count(self.name, method)
        total_credits = total_requests * credits

        if total_credits > PRICING_CONFIG["quicknode"]["threshold"]:
            return PRICING_CONFIG["quicknode"]["high_volume_price"] * credits

        return PRICING_CONFIG["quicknode"]["low_volume_price"] * credits


class BestProvider(Provider):
    """
    Virtual provider that represents the "best" choice.
    Does not make actual RPC calls - routing handled by RPCOptimizer.
    """

    def __init__(self):
        super().__init__({"name": "Best", "base_url": ""})
        self.name = "Best"

    def price_per_call(self, method: str = None) -> float:
        """Best provider price is the price of the selected provider."""
        return 0.0

    def call(
        self,
        payload: Dict[str, Any],
        all_providers: Optional[List[Provider]] = None,
        rpc_client=None,
    ) -> Dict[str, Any]:
        """
        Best provider cannot call directly.
        Must use RPCOptimizer or /rpc/best endpoint.
        """
        return {
            "error": {
                "code": -32601,
                "message": "BestProvider cannot call directly. Use RPCOptimizer or /rpc/best endpoint.",
            }
        }


def load_providers() -> List[Provider]:
    """
    Load all configured providers.

    Returns:
        List of Provider instances
    """
    instances = []

    for p in PROVIDERS:
        name = p["name"].lower()

        if name == "chainstack":
            instances.append(ChainstackProvider(p))
        elif name == "alchemy":
            instances.append(AlchemyProvider(p))
        elif name == "quicknode":
            instances.append(QuickNodeProvider(p))
        else:
            # Generic provider for unknown types
            instances.append(Provider(p))

    # Add virtual "Best" provider
    instances.append(BestProvider())

    return instances


# Utility functions for external use
def get_alchemy_compute_units(method: str) -> int:
    """Get compute units for Alchemy API method."""
    return ALCHEMY_COMPUTE_UNITS.get(method, 0)


def get_quicknode_credits(method: str) -> int:
    """Get credits for QuickNode API method."""
    return QUICKNODE_CREDITS.get(method, 20)
