from typing import Dict, Any, Optional, Tuple
import time
from requests.adapters import HTTPAdapter
import requests
import aiohttp
from urllib3.util.retry import Retry

class RPCClient:
    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 2,
        pool_connections: int = 10,
        pool_maxsize: int = 20
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,  # Wait 1s, 2s, 4s between retries
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
            allowed_methods=["POST"]
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Bliply-RPC-Router/1.0"
        })
    
    def send_request(
        self, 
        provider_url: str, 
        payload: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> Tuple[Dict[str, Any], float]:
        start_time = time.time()
        
        try:
            response = self.session.post(
                provider_url,
                json=payload,
                timeout=timeout or self.timeout
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            response.raise_for_status()
            
            response_data = response.json()
            
            return response_data, latency_ms
        
        except requests.exceptions.Timeout as e:
            latency_ms = (time.time() - start_time) * 1000
            raise TimeoutError(
                f"Request to {provider_url} timed out after {latency_ms:.0f}ms"
            ) from e
        
        except requests.exceptions.HTTPError as e:
            latency_ms = (time.time() - start_time) * 1000
            raise ConnectionError(
                f"HTTP error from {provider_url}: {e.response.status_code}"
            ) from e
        
        except requests.exceptions.RequestException as e:
            latency_ms = (time.time() - start_time) * 1000
            raise ConnectionError(
                f"Failed to connect to {provider_url}: {str(e)}"
            ) from e
    
    def send_request_safe(
        self, 
        provider_url: str, 
        payload: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            response_data, latency_ms = self.send_request(
                provider_url, 
                payload, 
                timeout
            )
            
            if "error" in response_data:
                return {
                    "error": response_data["error"],
                    "latency_ms": latency_ms,
                    "success": False
                }
            
            return {
                "result": response_data.get("result"),
                "jsonrpc": response_data.get("jsonrpc"),
                "id": response_data.get("id"),
                "latency_ms": latency_ms,
                "success": True
            }
        
        except TimeoutError as e:
            return {
                "error": str(e),
                "latency_ms": self.timeout * 1000,  # Max timeout
                "success": False,
                "error_type": "timeout"
            }
        
        except ConnectionError as e:
            return {
                "error": str(e),
                "latency_ms": 0.0,
                "success": False,
                "error_type": "connection"
            }
        
        except Exception as e:
            return {
                "error": f"Unexpected error: {str(e)}",
                "latency_ms": 0.0,
                "success": False,
                "error_type": "unknown"
            }
    
    def close(self):
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
