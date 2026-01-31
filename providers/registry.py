from typing import Dict, Any, List, Optional
from config import (
    PROVIDERS,
    PRICING_CONFIG,
    ALCHEMY_COMPUTE_UNITS,
    QUICKNODE_CREDITS,
)
from providers.base import RPCProvider


class ChainstackProvider(RPCProvider):
    def price_per_call(self, method: str = None) -> float:
        total_requests = self.metrics.get_request_count(self.name, method) + 1

        if total_requests > PRICING_CONFIG["chainstack"]["threshold"]:
            return PRICING_CONFIG["chainstack"]["high_volume_price"]

        return PRICING_CONFIG["chainstack"]["low_volume_price"]


class AlchemyProvider(RPCProvider):
    def price_per_call(self, method: str = None) -> float:
        compute_units = ALCHEMY_COMPUTE_UNITS.get(method, 0)
        all_counts = self.metrics.get_all_request_counts()
        total_cu = sum(
            count * ALCHEMY_COMPUTE_UNITS.get(m, 0)
            for (provider, m), count in all_counts.items()
            if provider == self.name
        )

        total_cu += compute_units

        if total_cu > PRICING_CONFIG["alchemy"]["threshold"]:
            return PRICING_CONFIG["alchemy"]["high_volume_price"] * compute_units
        return PRICING_CONFIG["alchemy"]["low_volume_price"] * compute_units


class QuickNodeProvider(RPCProvider):
    def price_per_call(self, method: str = None) -> float:
        credits = QUICKNODE_CREDITS.get(method, 20)
        all_counts = self.metrics.get_all_request_counts()
        total_credits = sum(
            count * QUICKNODE_CREDITS.get(m, 20)
            for (provider, m), count in all_counts.items()
            if provider == self.name
        )

        total_credits += credits

        if total_credits > PRICING_CONFIG["quicknode"]["threshold"]:
            return PRICING_CONFIG["quicknode"]["high_volume_price"] * credits

        return PRICING_CONFIG["quicknode"]["low_volume_price"] * credits


class BestProvider(RPCProvider):
    def __init__(self):
        super().__init__({"name": "Best", "base_url": ""})
        self.name = "Best"

    def price_per_call(self, method: str = None) -> float:
        return 0.0

    async def call(
        self,
        payload: Dict[str, Any],
        all_providers: Optional[List[RPCProvider]] = None,
        rpc_client=None,
    ) -> Dict[str, Any]:
        return {
            "error": {
                "code": -32601,
                "message": "BestProvider cannot call directly. Use RPCOptimizer or /rpc/best endpoint.",
            }
        }


def load_providers() -> List[RPCProvider]:
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
            instances.append(RPCProvider(p))

    instances.append(BestProvider())

    return instances


def get_alchemy_compute_units(method: str) -> int:
    return ALCHEMY_COMPUTE_UNITS.get(method, 0)


def get_quicknode_credits(method: str) -> int:
    return QUICKNODE_CREDITS.get(method, 20)
