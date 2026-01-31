from typing import Dict, Any, Optional
import pandas as pd

class ResponseHandler:
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
        response = {
            "jsonrpc": raw_response.get("jsonrpc", "2.0"),
            "id": raw_response.get("id"),
        }
        
        if "result" in raw_response:
            response["result"] = raw_response["result"]
        elif "error" in raw_response:
            response["error"] = raw_response["error"]
        else:
            response["error"] = {"code": -32603, "message": "Invalid response from provider"}
        
        response["bliply"] = {
            "selected_provider": selected_provider,
            "score": round(score, 4),
            "weights": {
                "latency": round(weights.get("Latency", 0.5), 3),
                "price": round(weights.get("Price", 0.5), 3)
            }
        }
        
        if latency_ms is not None:
            response["bliply"]["latency_ms"] = round(latency_ms, 2)
        
        if price_usd is not None:
            response["bliply"]["price_usd"] = round(price_usd, 6)
        
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
        response = provider_response.copy()
        
        if "bliply" not in response:
            response["bliply"] = {}
        
        response["bliply"].update(metadata)
        
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
