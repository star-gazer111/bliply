from typing import Dict, Any, List, Optional
import os
import yaml
from config import PRICING_CONFIG
from providers.base import RPCProvider


class ChainstackProvider(RPCProvider):
    def price_per_call(self, method: str = None) -> float:
        total_requests = self.metrics.get_request_count(self.name, method) + 1

        if total_requests > PRICING_CONFIG["chainstack"]["threshold"]:
            return PRICING_CONFIG["chainstack"]["high_volume_price"]

        return PRICING_CONFIG["chainstack"]["low_volume_price"]


class AlchemyProvider(RPCProvider):
    def price_per_call(self, method: str = None) -> float:
        compute_units = self.method_costs.get(method, 0)
        all_counts = self.metrics.get_all_request_counts()
        total_cu = sum(
            count * self.method_costs.get(m, 0)
            for (provider, m), count in all_counts.items()
            if provider == self.name
        )

        total_cu += compute_units

        if total_cu > PRICING_CONFIG["alchemy"]["threshold"]:
            return PRICING_CONFIG["alchemy"]["high_volume_price"] * compute_units
        return PRICING_CONFIG["alchemy"]["low_volume_price"] * compute_units


class QuickNodeProvider(RPCProvider):
    def price_per_call(self, method: str = None) -> float:
        credits = self.method_costs.get(method, self.method_costs.get('default', 20))
        all_counts = self.metrics.get_all_request_counts()
        total_credits = sum(
            count * self.method_costs.get(m, self.method_costs.get('default', 20))
            for (provider, m), count in all_counts.items()
            if provider == self.name
        )

        total_credits += credits

        if total_credits > PRICING_CONFIG["quicknode"]["threshold"]:
            return PRICING_CONFIG["quicknode"]["high_volume_price"] * credits

        return PRICING_CONFIG["quicknode"]["low_volume_price"] * credits
    


def load_providers() -> List[RPCProvider]:
    
    paid_providers_str = os.getenv("PAID_PROVIDERS", "")
    print(f"[Registry] DEBUG: RAW PAID_PROVIDERS from env: '{paid_providers_str}'")
    
    paid_providers_str = paid_providers_str.strip().lower()
    paid_provider_set = set(
        p.strip() for p in paid_providers_str.split(",") if p.strip()
    )
    
    print(f"[Registry] Paid providers from env: {paid_provider_set if paid_provider_set else 'None (all free)'}")
    
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        "config", 
        "config_data.yaml"
    )
    
    print(f"[Registry] DEBUG: Loading config from {config_path}")
    
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    instances = []
    
    for provider_key, provider_config in config_data["providers"].items():
        provider_name_lower = provider_key.lower()
        
        if provider_name_lower in paid_provider_set:
            tier = provider_config["tiers"]["paid"]
            priority = 2
            tier_name = "PAID"
        else:
            tier = provider_config["tiers"]["free"]
            priority = 1  
            tier_name = "FREE"
        
        env_key = f"{provider_config['name'].upper()}_URL"
        base_url = os.getenv(env_key)
        
        if not base_url:
            print(f"[Registry] Warning: {env_key} not found in environment, skipping {provider_config['name']}")
            continue
        
        # Clean up URL to avoid SSL/path issues
        base_url = base_url.strip().rstrip("/")
        
        provider_dict = {
            "name": provider_config["name"],
            "base_url": base_url,
            "limit_rps": tier["limit_rps"],
            "limit_monthly": tier["limit_monthly"],
            "priority": priority,
            "pricing_model": provider_config["pricing_model"],
            "method_costs": provider_config.get("costs", {})
        }
        
        if provider_name_lower == "alchemy":
            instance = AlchemyProvider(provider_dict)
        elif provider_name_lower == "quicknode":
            instance = QuickNodeProvider(provider_dict)
        elif provider_name_lower == "chainstack":
            instance = ChainstackProvider(provider_dict)
        else:
            instance = RPCProvider(provider_dict)
        
        instances.append(instance)
        
        print(f"[Registry] Loaded {provider_config['name']} - Tier: {tier_name}, Priority: {priority}, RPS: {tier['limit_rps']}, Monthly: {tier['limit_monthly']:,}")
    
    
    return instances
