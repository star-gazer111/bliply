from typing import Dict, Any, List, Optional
import time
from typing import NamedTuple

from services.request_parser import RequestParser
from services.metric_collector import MetricCollector
from services.response_handler import ResponseHandler
from core.quota_manager import QuotaManager
from core.rate_limiter import RateLimiter
from services.rpc_client import RPCClient
from providers.base import RPCProvider

class ProviderScore(NamedTuple):
    provider: RPCProvider
    latency: float
    score: float = 0.0

class RPCOptimizer:
    def __init__(
        self,
        providers: List[RPCProvider],
        enable_exploration: bool = True,
        exploration_rate: float = 0.1,
    ):
        self.providers = providers
        self.provider_dict = {p.name.lower(): p for p in providers}

        self.parser = RequestParser()
        self.metric_collector = MetricCollector()
        self.rpc_client = RPCClient(timeout=30, max_retries=1) # Lower retries for faster failover
        self.response_handler = ResponseHandler()
        
        # New Core Logic Components
        self.rate_limiter = RateLimiter(window_size_seconds=1)
        self.quota_manager = QuotaManager()
        
        # Exploration settings
        self.enable_exploration = enable_exploration
        self.exploration_rate = exploration_rate
        
        print(f"[RPCOptimizer] Initialized with {len(providers)} providers using Spillover Strategy")
        if enable_exploration:
            print(f"[RPCOptimizer] Exploration enabled: {exploration_rate*100}% random selection from free tier")

    async def optimize_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            parsed_request = self.parser.parse_rpc_request(payload)
            method = parsed_request["method"]
            request_id = parsed_request["id"]
            
            # 1. Get List of Potential Providers (Filtered by Quota only first)
            # this will return those providers whose MONTHLY quota hasnt been exceeded - and in the list returned providers will be sorted in 2 ways : 
            # 1. Priority (ascending)
            # 2. Latency (ascending)
            potential_providers = self._get_potential_providers(method)
            
            if not potential_providers:
                 return self.response_handler.build_error_response(
                    error_message="No providers available with remaining quota",
                    request_id=request_id,
                    error_code=-32000
                )

            # 2. Select Provider (with optional exploration)
            best_provider = None
            
            # Exploration Mode: Randomly select from priority 1 providers
            if self.enable_exploration:
                import random
                if random.random() < self.exploration_rate:
                    # Try random selection from free tier (priority 1)
                    free_tier_providers = [p for p in potential_providers if p.provider.priority == 1]
                    
                    if free_tier_providers:
                        print(f"[RPCOptimizer] 🎲 Exploration mode: randomly selecting from {len(free_tier_providers)} free tier providers")
                        random.shuffle(free_tier_providers)
                        
                        # Try each random free tier provider
                        for p_score in free_tier_providers:
                            p = p_score.provider
                            if self.rate_limiter.is_allowed(p.name, p.limit_rps):
                                best_provider = p
                                print(f"[RPCOptimizer] 🎲 Exploration selected: {p.name}")
                                break
            
            # Deterministic Selection: Use priority + latency sorted list
            if not best_provider:
                for p_score in potential_providers:
                    p = p_score.provider
                    # Try to acquire rate limit token
                    if self.rate_limiter.is_allowed(p.name, p.limit_rps):
                        best_provider = p
                        break

            # the following point is expected to be hit very rarely because the paid plan usually has a high RPS limit
            if not best_provider:
                 return self.response_handler.build_error_response(
                    error_message="All eligible providers are rate limited",
                    request_id=request_id,
                    error_code=-32000 # Server error or 429
                )

            print(f"[RPCOptimizer] Selected {best_provider.name} (Priority {best_provider.priority})")
            
            # 3. Execute Request
            start_time = time.time()
            raw_response, actual_latency = await self.rpc_client.send_request(
                provider_url=best_provider.base_url,
                payload=payload,
                timeout=10
            )
            
            # 4. Success Handling
            self._record_metrics(best_provider, method, actual_latency, success=True)
            
            # Calculate cost (CU or Request count)
            cost = best_provider.get_cost(method)
            self.quota_manager.increment(best_provider.name, count=cost)
            
            return self.response_handler.build_response(
                raw_response=raw_response,
                selected_provider=best_provider.name,
                score=1.0,
                weights={"Latency": 1.0, "Price": 0.0},
                latency_ms=actual_latency,
                price_usd=best_provider.price_per_call(method),
                all_provider_scores=None 
            )

        except Exception as e:
            print(f"[RPCOptimizer] Error: {e}")
            return self.response_handler.build_error_response(
                error_message=str(e),
                request_id=payload.get("id", 1),
                error_code=-32603
            )

    def _get_potential_providers(self, method: str) -> List[ProviderScore]:
        """
        Get all providers with Quota, sorted by Priority then Latency.
        Does NOT check Rate Limits yet.
        """
        candidates = []
        
        for p in self.providers:
            # Check Monthly Quota
            if not self.quota_manager.check_allowance(p.name, p.limit_monthly):
                continue
            
            # Get Latency
            latency = self.metric_collector.get_provider_latency(p, method, default=500.0)
            candidates.append(ProviderScore(provider=p, latency=latency))
            
        # Sort by Priority (Ascending), then Latency (Ascending)
        candidates.sort(key=lambda x: (x.provider.priority, x.latency))
        
        return candidates

    def _record_metrics(self, provider: RPCProvider, method: str, latency: float, success: bool):
        price = provider.price_per_call(method)
        provider.metrics.add_record(
            provider=provider.name,
            method=method,
            latency_ms=latency,
            price=price
        )
        # Note: Quota increment happens in main flow on success

    async def close(self):
        await self.rpc_client.close()
