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
    def __init__(self, config: dict):
        self.name = config["name"]
        self.base_url = config["base_url"]
        self.config = config
        self.metrics = MetricsStore()

    def price_per_call(self, method: str = None) -> float:
        return 0.0

    def calculate_marginal_price(self, current_usage: int, method: str = None) -> float:
        return self.price_per_call(method)

    def call(
        self,
        payload: Dict[str, Any],
        all_providers: Optional[List["Provider"]] = None,
        rpc_client=None,
    ) -> Dict[str, Any]:
        method = payload.get("method", "")

        if rpc_client is not None:
            try:
                result, latency_ms = rpc_client.send_request(
                    provider_url=self.base_url, payload=payload, timeout=10
                )
            except Exception as e:
                result = {"error": str(e)}
                latency_ms = 10000.0  # Max timeout
        else:
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

        price = self.price_per_call(method)

        self.metrics.add_record(
            provider=self.name, method=method, latency_ms=latency_ms, price=price
        )

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
    def price_per_call(self, method: str = None) -> float:
        total_requests = self.metrics.get_request_count(self.name, method)

        if total_requests > PRICING_CONFIG["chainstack"]["threshold"]:
            return PRICING_CONFIG["chainstack"]["high_volume_price"]

        return PRICING_CONFIG["chainstack"]["low_volume_price"]


class AlchemyProvider(Provider):
    def price_per_call(self, method: str = None) -> float:
        compute_units = ALCHEMY_COMPUTE_UNITS.get(method, 0)
        total_requests = self.metrics.get_request_count(self.name, method)
        total_cu = total_requests * compute_units

        if total_cu > PRICING_CONFIG["alchemy"]["threshold"]:
            return PRICING_CONFIG["alchemy"]["high_volume_price"] * compute_units

        return PRICING_CONFIG["alchemy"]["low_volume_price"] * compute_units


class QuickNodeProvider(Provider):
    def price_per_call(self, method: str = None) -> float:
        credits = QUICKNODE_CREDITS.get(method, 20)
        total_requests = self.metrics.get_request_count(self.name, method)
        total_credits = total_requests * credits

        if total_credits > PRICING_CONFIG["quicknode"]["threshold"]:
            return PRICING_CONFIG["quicknode"]["high_volume_price"] * credits

        return PRICING_CONFIG["quicknode"]["low_volume_price"] * credits


class BestProvider(Provider):
    def __init__(self):
        super().__init__({"name": "Best", "base_url": ""})
        self.name = "Best"

    def price_per_call(self, method: str = None) -> float:
        return 0.0

    def call(
        self,
        payload: Dict[str, Any],
        all_providers: Optional[List[Provider]] = None,
        rpc_client=None,
    ) -> Dict[str, Any]:
        return {
            "error": {
                "code": -32601,
                "message": "BestProvider cannot call directly. Use RPCOptimizer or /rpc/best endpoint.",
            }
        }


def load_providers() -> List[Provider]:
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
            instances.append(Provider(p))

    instances.append(BestProvider())

    return instances


def get_alchemy_compute_units(method: str) -> int:
    return ALCHEMY_COMPUTE_UNITS.get(method, 0)


def get_quicknode_credits(method: str) -> int:
    return QUICKNODE_CREDITS.get(method, 20)
