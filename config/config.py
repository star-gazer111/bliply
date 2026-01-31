import os
from dotenv import load_dotenv
from config.compute_units import ALCHEMY_COMPUTE_UNITS, QUICKNODE_CREDITS

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

PRICING_CONFIG = {
    "chainstack": {
        "threshold": 20_000_000,
        "high_volume_price": 0.0000024875,
        "low_volume_price": 0.00000245
    },
    "alchemy": {
        "threshold": 300_000_000,
        "high_volume_price": 0.00000040,
        "low_volume_price": 0.00000045
    },
    "quicknode": {
        "threshold": 80_000_000,
        "high_volume_price": 0.00000055,
        "low_volume_price": 0.00000062
    }
}

PROVIDERS = [
    {
        "name": "Chainstack",
        "base_url": os.getenv("CHAINSTACK_URL"),
        "type": "flat",
        "price_per_million": 0.25,
        "variable_price": True
    },
    {
        "name": "Alchemy",
        "base_url": os.getenv("ALCHEMY_URL"),
        "type": "cu",
        "cu_tiers": [
            {"limit": 300_000_000, "price_per_million": 0.45},
            {"limit": float("inf"), "price_per_million": 0.40}
        ],
        "method_cus": ALCHEMY_COMPUTE_UNITS
    },
    {
        "name": "QuickNode",
        "base_url": os.getenv("QUICKNODE_URL"),
        "type": "credit",
        "credit_tiers": [
            {"limit": 80_000_000, "price_per_million": 0.62},
            {"limit": float("inf"), "price_per_million": 0.525}
        ],
        "method_credits": QUICKNODE_CREDITS
    }
]

# Cache Configuration
# Controls the score and weights caching mechanism to reduce CPU overhead
CACHE_CONFIG = {
    # Enable/disable score caching (set to False to disable caching entirely)
    "enabled": True,
    
    # Time-to-live for cached scores and weights in seconds
    # Lower values = more frequent recalculation, more accurate scores
    # Higher values = less CPU usage, potentially stale scores
    # Recommended: 5.0 for production (balances performance and accuracy)
    "score_cache_ttl_seconds": 5.0,
}
