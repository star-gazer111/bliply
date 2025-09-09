import os
from dotenv import load_dotenv

# Load .env file from parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

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
        "method_cus": {
            "eth_blockNumber": 10,
            "eth_call": 20,
            "eth_getBalance": 10,
            "eth_sendTransaction": 40,
            "eth_estimateGas": 20
        }
    }
]
