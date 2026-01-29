from typing import Dict, Any, List, Optional
from core.config import (
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
        total_requests = self.metrics.get_request_count(self.name, method) + 1
        total_cu = total_requests * compute_units

        if total_cu > PRICING_CONFIG["alchemy"]["threshold"]:
            return PRICING_CONFIG["alchemy"]["high_volume_price"] * compute_units

        return PRICING_CONFIG["alchemy"]["low_volume_price"] * compute_units


class QuickNodeProvider(RPCProvider):
    def price_per_call(self, method: str = None) -> float:
        credits = QUICKNODE_CREDITS.get(method, 20)
        total_requests = self.metrics.get_request_count(self.name, method) + 1
        total_credits = total_requests * credits

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
            "response": {
                "error": {
                    "code": -32601,
                    "message": "BestProvider cannot call directly. Use RPCOptimizer or /rpc/best endpoint.",
                }
            },
            "latency_ms": 0.0,
            "price_usd": 0.0,
            "weights": {"Latency": 0.5, "Price": 0.5},
            "score": 0.0,
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
