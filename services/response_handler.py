from typing import Dict, Any, Optional
import pandas as pd

class ResponseHandler:
    """
    Step 10: Receive Response & Build Final Response
    Formats provider responses with Bliply optimization metadata.
    """
    
    def __init__(self):
        pass
    
    def build_response(
        self,
        raw_response: Dict[str, Any],
        selected_provider: str,
        score: float,
        weights: Dict[str, float],
        all_provider_scores: Optional[pd.DataFrame] = None,
        latency_ms: Optional[float] = None,
        price_usd: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Build final response with optimization metadata.
        
        Args:
            raw_response: Raw JSON-RPC response from provider
            selected_provider: Name of provider that was selected
            score: Final score of selected provider
            weights: CRITIC weights used {"Latency": float, "Price": float}
            all_provider_scores: Optional DataFrame with all provider scores
            latency_ms: Request latency in milliseconds
            price_usd: Request price in USD
            
        Returns:
            Complete response dictionary with Bliply metadata
        """
        # Start with the raw JSON-RPC response
        response = {
            "jsonrpc": raw_response.get("jsonrpc", "2.0"),
            "id": raw_response.get("id"),
        }
        
        # Add result or error from provider
        if "result" in raw_response:
            response["result"] = raw_response["result"]
        elif "error" in raw_response:
            response["error"] = raw_response["error"]
        else:
            response["error"] = {"code": -32603, "message": "Invalid response from provider"}
        
        # Add Bliply optimization metadata
        response["bliply"] = {
            "selected_provider": selected_provider,
            "score": round(score, 4),
            "weights": {
                "latency": round(weights.get("Latency", 0.5), 3),
                "price": round(weights.get("Price", 0.5), 3)
            }
        }
        
        # Add performance metrics
        if latency_ms is not None:
            response["bliply"]["latency_ms"] = round(latency_ms, 2)
        
        if price_usd is not None:
            response["bliply"]["price_usd"] = round(price_usd, 6)
        
        # Add all provider scores if available
        if all_provider_scores is not None and not all_provider_scores.empty:
            response["bliply"]["all_providers"] = self._format_provider_scores(
                all_provider_scores
            )
        
        return response
    
    def build_error_response(
        self,
        error_message: str,
        request_id: Any = 1,
        error_code: int = -32603,
        method: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build JSON-RPC error response.
        
        Args:
            error_message: Human-readable error message
            request_id: Request ID from original request
            error_code: JSON-RPC error code
            method: Optional method name for context
            
        Returns:
            JSON-RPC error response
        """
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": error_code,
                "message": error_message
            }
        }
        
        if method:
            response["error"]["data"] = {"method": method}
        
        return response
    
    def build_no_providers_response(
        self,
        method: str,
        request_id: Any = 1
    ) -> Dict[str, Any]:
        """
        Build response when no eligible providers are available.
        """
        return self.build_error_response(
            error_message=f"No eligible providers available for method: {method}",
            request_id=request_id,
            error_code=-32000,  # Server error
            method=method
        )
    
    def _format_provider_scores(
        self, 
        scores_df: pd.DataFrame
    ) -> Dict[str, Dict[str, float]]:
        """
        Format DataFrame of provider scores into dict for response.
        
        Args:
            scores_df: DataFrame with Provider, Score, Latency, Price columns
            
        Returns:
            {
                "alchemy": {
                    "score": 0.85,
                    "latency_ms": 120.5,
                    "price_usd": 0.0001
                },
                ...
            }
        """
        formatted = {}
        
        for _, row in scores_df.iterrows():
            provider_name = row["Provider"].lower()
            
            formatted[provider_name] = {
                "score": round(float(row.get("Score", 0.0)), 4),
                "latency_ms": round(float(row.get("Latency", 0.0)), 2),
                "price_usd": round(float(row.get("Price", 0.0)), 6)
            }
        
        return formatted
    
    def merge_response_with_metadata(
        self,
        provider_response: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge provider response with existing metadata.
        Useful when response comes from provider.call() which already has some metadata.
        
        Args:
            provider_response: Response from provider (may have score, latency, etc.)
            metadata: Additional metadata to merge in
            
        Returns:
            Merged response
        """
        # Start with provider response
        response = provider_response.copy()
        
        # Ensure bliply metadata section exists
        if "bliply" not in response:
            response["bliply"] = {}
        
        # Merge in additional metadata
        response["bliply"].update(metadata)
        
        # Also add legacy top-level fields for backward compatibility
        if "score" in metadata:
            response["score"] = metadata["score"]
        if "weights" in metadata:
            response["weights"] = metadata["weights"]
        if "selected_provider" in metadata:
            response["selected_provider"] = metadata["selected_provider"]
        if "latency_ms" in metadata:
            response["latency_ms"] = metadata["latency_ms"]
        if "price_usd" in metadata:
            response["price_usd"] = metadata["price_usd"]
        
        return response