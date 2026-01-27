from typing import Dict, Any, Optional, Tuple
import time
from requests.adapters import HTTPAdapter
import requests
from urllib3.util.retry import Retry

class RPCClient:
    """
    Step 9: Forward the Request
    Handles HTTP communication with RPC providers.
    Maintains persistent connection pools for low overhead.
    """
    
    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 2,
        pool_connections: int = 10,
        pool_maxsize: int = 20
    ):
        """
        Args:
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts on failure
            pool_connections: Number of connection pools to cache
            pool_maxsize: Max connections per pool
        """
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Create session with connection pooling
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,  # Wait 1s, 2s, 4s between retries
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
            allowed_methods=["POST"]
        )
        
        # Mount adapter with retry strategy
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
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
        """
        Send JSON-RPC request to provider.
        
        Args:
            provider_url: Provider's RPC endpoint URL
            payload: JSON-RPC request payload
            timeout: Optional custom timeout (uses default if None)
            
        Returns:
            Tuple of (response_dict, latency_ms)
            
        Raises:
            requests.exceptions.Timeout: If request times out
            requests.exceptions.RequestException: On network errors
        """
        start_time = time.time()
        
        try:
            response = self.session.post(
                provider_url,
                json=payload,
                timeout=timeout or self.timeout
            )
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Raise for HTTP errors (4xx, 5xx)
            response.raise_for_status()
            
            # Parse JSON response
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
        """
        Send request with error handling that returns structured error response.
        Does not raise exceptions - returns error in response dict.
        
        Args:
            provider_url: Provider's RPC endpoint URL
            payload: JSON-RPC request payload
            timeout: Optional custom timeout
            
        Returns:
            Dict with either success or error response:
            Success: {"result": ..., "latency_ms": float}
            Error: {"error": str, "latency_ms": float}
        """
        try:
            response_data, latency_ms = self.send_request(
                provider_url, 
                payload, 
                timeout
            )
            
            # Check if response contains JSON-RPC error
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
        """
        Close the session and release connections.
        Call this when shutting down the application.
        """
        self.session.close()
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support."""
        self.close()
