import aiohttp
import time
from typing import Dict, Any, List, Optional
from metrics import MetricsStore


class RPCProvider:
    def __init__(self, config: dict):
        self.name = config["name"]
        self.base_url = config["base_url"]
        self.config = config
        
        # New fields for Spillover Strategy
        self.limit_rps = config.get("limit_rps", 1000)
        self.limit_monthly = config.get("limit_monthly", 1000000000)
        self.priority = config.get("priority", 2)  # 1=Free, 2=Paid
        self.pricing_model = config.get("pricing_model", "request") # request | cu
        
        self.metrics = MetricsStore()

    def get_cost(self, method: str) -> int:
        """
        Calculate the cost of the request in 'units' (requests or CUs).
        """
        if self.pricing_model == "cu":
            from config.compute_units import ALCHEMY_COMPUTE_UNITS
            # Default to 26 (eth_call cost) if unknown, to be safe? Or 10?
            # Using 10 as a safe default for read ops
            return ALCHEMY_COMPUTE_UNITS.get(method, 10)
        return 1

    def price_per_call(self, method: str = None) -> float:
        return 0.0

    def calculate_marginal_price(self, current_usage: int, method: str = None) -> float:
        return self.price_per_call(method)

    async def call(
        self,
        payload: Dict[str, Any],
        all_providers: Optional[List["RPCProvider"]] = None,
        rpc_client=None,
    ) -> Dict[str, Any]:
        method = payload.get("method", "")

        if not method or not isinstance(method, str) or not method.strip():
            return {
                "response": {
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request: method is required and cannot be empty",
                    }
                },
                "latency_ms": 0.0,
                "price_usd": 0.0,
                "score": 0.0,
            }

        result = None
        latency_ms = 0.0
        
        if rpc_client is not None:
            try:
                result, latency_ms = await rpc_client.send_request(
                    provider_url=self.base_url, payload=payload, timeout=10
                )
            except Exception as e:
                result = {"error": str(e)}
                latency_ms = 10000.0
        else:
            async with aiohttp.ClientSession() as session:
                start = time.time()
                try:
                    response = await session.post(self.base_url, json=payload, timeout=10)
                    result = await response.json()
                except Exception as e:
                    result = {"error": str(e)}
                finally:
                    latency_ms = (time.time() - start) * 1000

        price = self.price_per_call(method)

        self.metrics.add_record(
            provider=self.name, method=method, latency_ms=latency_ms, price=price
        )

        return {
            "response": result,
            "latency_ms": latency_ms,
            "price_usd": price,
            "score": 0.0, # Deprecated
        }

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name} Priority={self.priority}>"
