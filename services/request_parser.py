from typing import Dict, Any, Optional
import json
from data.schemas.rpc import RPCRequest
from pydantic import ValidationError

class RequestParser:
    REQUIRED_FIELDS = ["jsonrpc", "method", "id"]
    SUPPORTED_JSONRPC_VERSION = "2.0"
    
    def __init__(self):
        pass
    
    def parse_rpc_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            rpc_req = RPCRequest(**payload)
            return {
                "method": rpc_req.method,
                "params": rpc_req.params,
                "id": rpc_req.id,
                "jsonrpc": rpc_req.jsonrpc,
                "chain": payload.get("chain", ""),
                "network": payload.get("network", ""),
                "raw_payload": payload
            }
        except ValidationError as e:
            raise ValueError(f"Invalid RPC request: {e}")
    
    
    def validate_method(self, method: str, supported_methods: Optional[list] = None) -> bool:
        if supported_methods is None:
            return True  # Allowing all methods if no restriction
        
        return method in supported_methods
    
    def extract_method_category(self, method: str) -> str:
        if method.startswith("eth_get"):
            return "read"
        elif method.startswith("eth_send"):
            return "write"
        elif method in ["eth_call", "eth_estimateGas"]:
            return "call"
        elif method in ["eth_blockNumber", "eth_gasPrice"]:
            return "info"
        else:
            return "other"
