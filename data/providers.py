import random
import time
import requests
from .metrics import MetricsStore
from strategy.scoring_engine import calculate_dynamic_scores
from core.config import PROVIDERS

class RPCProvider:
    def __init__(self, config: dict):
        self.name = config["name"]
        self.base_url = config["base_url"]
        self.config = config
        self.metrics = MetricsStore()
    
    def price_per_call(self, method: str = None) -> float:
        return 0.0

    def call(self, payload: dict, all_providers=None) -> dict:
        start = time.time()
        method = payload.get("method", "")
        
        try:
            response = requests.post(self.base_url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            result = {"error": str(e)}
        finally:
            latency_ms = (time.time() - start) * 1000
            price = self.price_per_call(method)
            self.metrics.add_record(self.name, latency_ms, price)
            
            if all_providers is None:
                all_providers = [self]

            try:
                latest_df, weights = calculate_dynamic_scores(all_providers)
                provider_row = latest_df[latest_df["Provider"] == self.name]
                last_score = float(provider_row["Score"].iloc[0]) if not provider_row.empty else 0.5
            except:
                last_score = 0.5
                weights = [0.5, 0.5]

        return {
            "response": result,
            "latency_ms": latency_ms,
            "price_usd": price,
            "weights": {"Latency": weights[0], "Price": weights[1]},
            "score": last_score
        }


class ChainstackProvider(RPCProvider):
    def price_per_call(self, method: str = None) -> float:
        return 10.0 * random.uniform(0.8, 1.2)

class AlchemyProvider(RPCProvider):
    def price_per_call(self, method: str = None) -> float:
        return 12.0 * random.uniform(0.8, 1.2)

def load_providers():
    instances = []
    for p in PROVIDERS:
        name = p["name"].lower()
        if name == "chainstack":
            instances.append(ChainstackProvider(p))
        elif name == "alchemy":
            instances.append(AlchemyProvider(p))
    return instances
