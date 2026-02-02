import os
from dotenv import load_dotenv
from config.compute_units import ALCHEMY_COMPUTE_UNITS, QUICKNODE_CREDITS

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

PRICING_CONFIG = {
    "chainstack": {
        "threshold": 20_000_000,
        "high_volume_price": 0.000015,
        "low_volume_price": 0.00000245
    },
    "alchemy": {
        "threshold": 300_000_000,
        "high_volume_price": 0.00000040,
        "low_volume_price": 0.00000045
    },
    "quicknode": {
        "threshold": 80_000_000,
        "high_volume_price": 0.00000062,
        "low_volume_price": 0.000000525
    }
}

import json

def load_providers_config():
    config_path = os.path.join(os.path.dirname(__file__), "providers.json")
    if not os.path.exists(config_path):
        # Fallback if file missing
        return []
        
    with open(config_path, "r") as f:
        providers = json.load(f)
        
    # Inject Env Vars for URLs and other config
    for p in providers:
        if p["name"] == "Alchemy":
            p["base_url"] = os.getenv("ALCHEMY_URL")
            p["type"] = "cu"
            p["method_cus"] = ALCHEMY_COMPUTE_UNITS
        elif p["name"] == "QuickNode":
            p["base_url"] = os.getenv("QUICKNODE_URL")
            p["type"] = "credit"
            p["method_credits"] = QUICKNODE_CREDITS
        elif p["name"] == "Chainstack":
            p["base_url"] = os.getenv("CHAINSTACK_URL")
            p["type"] = "flat"
    
    return providers

PROVIDERS = load_providers_config()
