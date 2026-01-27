from typing import Dict, Any, Optional
import json

class RequestParser:
    """
    Step 2: Parse & Identify Context
    Extracts method, chain/network, and validates JSON-RPC format.
    """
    
    REQUIRED_FIELDS = ["jsonrpc", "method", "id"]
    SUPPORTED_JSONRPC_VERSION = "2.0"
    
    def __init__(self):
        pass
    
    def parse_rpc_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and validate incoming JSON-RPC request.
        
        Args:
            payload: Raw request dictionary
            
        Returns:
            Parsed request with structure:
            {
                "method": str,
                "params": list,
                "id": int,
                "jsonrpc": str,
                "chain": str (default: "ethereum"),
                "network": str (default: "mainnet")
            }
            
        Raises:
            ValueError: If request format is invalid
        """
        # Validating if all the required fields are present else raising error
        for field in self.REQUIRED_FIELDS:
            if field not in payload:
                raise ValueError(f"Missing required field: {field}")
        
        # Validating the JSON-RPC version if it is supported or not
        if payload.get("jsonrpc") != self.SUPPORTED_JSONRPC_VERSION:
            raise ValueError(f"Unsupported JSON-RPC version: {payload.get('jsonrpc')}")
        
        # Checking the method is not empty
        method = payload.get("method", "").strip()
        if not method:
            raise ValueError("Method cannot be empty")
        
        # Extracting all the provided params and default to empty array if not provided
        params = payload.get("params", [])
        if not isinstance(params, list):
            raise ValueError("Params must be a list")
        
        # Extracting id
        request_id = payload.get("id")
        if not isinstance(request_id, (int, str)):
            raise ValueError("ID must be an integer or string")
        
        # Extracting chain/network info
        chain = payload.get("chain", "")
        network = payload.get("network", "")
        
        # Collecting all and making and returning a parsed request object
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
    
    #  Validating if the requested method is allowed, i.e in the supported_methods 
    
    def validate_method(self, method: str, supported_methods: Optional[list] = None) -> bool:
        """
        Check if method is in supported list (optional validation).
        
        Args:
            method: RPC method name
            supported_methods: List of allowed methods (None = allow all)
            
        Returns:
            True if valid, False otherwise
        """
        if supported_methods is None:
            return True  # Allowing all methods if no restriction
        
        return method in supported_methods
    
    def extract_method_category(self, method: str) -> str:
        """
        Categorize method for future analytics/routing.
        
        Examples:
            eth_call -> "call"
            eth_getBalance -> "read"
            eth_sendRawTransaction -> "write"
        """
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