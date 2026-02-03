import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

PRICING_CONFIG = {
    "chainstack": {
        "threshold": 20_000_000,
        "high_volume_price": 0.0000024875,
        "low_volume_price": 0.00000245,
    },
    "alchemy": {
        "threshold": 300_000_000,
        "high_volume_price": 0.00000040,
        "low_volume_price": 0.00000045,
    },
    "quicknode": {
        "threshold": 80_000_000,
        "high_volume_price": 0.00000055,
        "low_volume_price": 0.00000062,
    },
}


