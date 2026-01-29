import time
from typing import Dict, Any, List, Optional
from data.metrics import MetricsStore
import aiohttp


class RPCProvider:
    def __init__(self, config: dict):
        self.name = config["name"]
        self.base_url = config["base_url"]
        self.config = config
        self.metrics = MetricsStore()

    def price_per_call(self, method: str = None) -> float:
        return 0.0

    def calculate_marginal_price(self, current_usage: int, method: str = None) -> float:
        return self.price_per_call(method)

    async def call(
        self,
        payload: Dict[str, Any],
        all_providers: Optional[List["Provider"]] = None,
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
                "weights": {"Latency": 0.5, "Price": 0.5},
                "score": 0.0,
            }

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
