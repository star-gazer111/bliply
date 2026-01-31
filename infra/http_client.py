from typing import Dict, Any, Optional, Tuple
import time
import aiohttp
import asyncio


class RPCClient:
    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 2,
        pool_connections: int = 10,
        pool_maxsize: int = 20,
    ):
        self.timeout = timeout
        self.max_retries = max_retries

        self.session = aiohttp.ClientSession()

    async def send_request(
        self, provider_url: str, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Tuple[Dict[str, Any], float]:
        start_time = time.time()

        try:
            response = await self.session.post(
                provider_url, json=payload, timeout=timeout or self.timeout
            )

            latency_ms = (time.time() - start_time) * 1000

            response_data = await response.json()

            return response_data, latency_ms

        except asyncio.TimeoutError as e:
            latency_ms = (time.time() - start_time) * 1000
            raise TimeoutError(
                f"Request to {provider_url} timed out after {latency_ms:.0f}ms"
            ) from e

        except aiohttp.ClientError as e:
            latency_ms = (time.time() - start_time) * 1000
            raise ConnectionError(
                f"Failed to connect to {provider_url}: {str(e)}"
            ) from e

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            raise ConnectionError(
                f"Unexpected error from {provider_url}: {str(e)}"
            ) from e

    async def send_request_safe(
        self, provider_url: str, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            response_data, latency_ms = await self.send_request(
                provider_url, payload, timeout
            )

            if "error" in response_data:
                return {
                    "error": response_data["error"],
                    "latency_ms": latency_ms,
                    "success": False,
                }

            return {
                "result": response_data.get("result"),
                "jsonrpc": response_data.get("jsonrpc"),
                "id": response_data.get("id"),
                "latency_ms": latency_ms,
                "success": True,
            }

        except TimeoutError as e:
            return {
                "error": str(e),
                "latency_ms": self.timeout * 1000,  # Max timeout
                "success": False,
                "error_type": "timeout",
            }

        except ConnectionError as e:
            return {
                "error": str(e),
                "latency_ms": 0.0,
                "success": False,
                "error_type": "connection",
            }

        except Exception as e:
            return {
                "error": f"Unexpected error: {str(e)}",
                "latency_ms": 0.0,
                "success": False,
                "error_type": "unknown",
            }

    async def close(self):
        await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
