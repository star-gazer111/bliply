import os
from dotenv import load_dotenv

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

ALCHEMY_COMPUTE_UNITS = {
    'net_version': 0,
    'eth_chainId': 0,
    'eth_syncing': 0,
    'eth_protocolVersion': 0,
    'net_listening': 0,
    'eth_uninstallFilter': 10,
    'eth_accounts': 10,
    'eth_blockNumber': 10,
    'eth_subscribe': 10,
    'eth_unsubscribe': 10,
    'eth_feeHistory': 10,
    'eth_maxPriorityFeePerGas': 10,
    'eth_createAccessList': 10,
    'eth_getTransactionReceipt': 20,
    'eth_getUncleByBlockHashAndIndex': 20,
    'eth_getUncleByBlockNumberAndIndex': 20,
    'eth_getTransactionByBlockHashAndIndex': 20,
    'eth_getTransactionByBlockNumberAndIndex': 20,
    'eth_getUncleCountByBlockHash': 20,
    'eth_getUncleCountByBlockNumber': 20,
    'web3_clientVersion': 20,
    'web3_sha3': 20,
    'eth_getBlockByNumber': 20,
    'eth_getStorageAt': 20,
    'eth_getTransactionByHash': 20,
    'eth_gasPrice': 20,
    'eth_getBalance': 20,
    'eth_getCode': 20,
    'eth_getFilterChanges': 20,
    'eth_newBlockFilter': 20,
    'eth_newFilter': 20,
    'eth_simulateV1': 40,
    'eth_newPendingTransactionFilter': 20,
    'eth_getBlockTransactionCountByHash': 20,
    'eth_getBlockTransactionCountByNumber': 20,
    'eth_getProof': 20,
    'eth_getBlockByHash': 20,
    'erigon_forks': 20,
    'erigon_getHeaderByHash': 20,
    'erigon_getHeaderByNumber': 20,
    'erigon_getLogsByHash': 20,
    'erigon_issuance': 20,
    'eth_getTransactionCount': 20,
    'eth_call': 26,
    'eth_getFilterLogs': 60,
    'eth_getLogs': 60,
    'eth_estimateGas': 20,
    'eth_sendRawTransaction': 40,
}

QUICKNODE_CREDITS = {
    'trace_call': 40,
    'default': 20
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
