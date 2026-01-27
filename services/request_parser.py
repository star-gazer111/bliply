from typing import Dict, Any, Optional
import json

class RequestParser:
    REQUIRED_FIELDS = ["jsonrpc", "method", "id"]
    SUPPORTED_JSONRPC_VERSION = "2.0"
    
    def __init__(self):
        pass
    
    def parse_rpc_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        for field in self.REQUIRED_FIELDS:
            if field not in payload:
                raise ValueError(f"Missing required field: {field}")
        
        if payload.get("jsonrpc") != self.SUPPORTED_JSONRPC_VERSION:
            raise ValueError(f"Unsupported JSON-RPC version: {payload.get('jsonrpc')}")
        
        method = payload.get("method", "").strip()
        if not method:
            raise ValueError("Method cannot be empty")
        
        params = payload.get("params", [])
        if not isinstance(params, list):
            raise ValueError("Params must be a list")
        
        request_id = payload.get("id")
        if not isinstance(request_id, (int, str)):
            raise ValueError("ID must be an integer or string")
        
        chain = payload.get("chain", "")
        network = payload.get("network", "")
        
        parsed_request = {
            "method": method,
            "params": params,
            "id": request_id,
            "jsonrpc": payload.get("jsonrpc"),
            "chain": chain,
            "network": network,
            "raw_payload": payload  # Keeping original payload for forwarding
        }
        
        return parsed_request
    
    
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
