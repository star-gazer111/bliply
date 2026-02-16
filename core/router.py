from typing import Dict, Any, List, Optional
import time
from typing import NamedTuple

from services.request_parser import RequestParser
from services.metric_collector import MetricCollector
from services.response_handler import ResponseHandler
from core.quota_manager import QuotaManager
from core.rate_limiter import RateLimiter
from infra.rpc_client import RPCClient
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
            potential_providers = self._get_potential_providers(method)
            
            if not potential_providers:
                 return self.response_handler.build_error_response(
                    error_message="No providers available with remaining quota",
                    request_id=request_id,
                    error_code=-32000
                )

            # 2. Prepare order of providers to try
            # By default: Priority (asc), then Latency (asc)
            providers_to_try = [p_score.provider for p_score in potential_providers]
            
            # Exploration: If triggered, move a random free provider to the front
            if self.enable_exploration:
                import random
                if random.random() < self.exploration_rate:
                    free_tier = [p for p in providers_to_try if p.priority == 1]
                    if free_tier:
                        r_provider = random.choice(free_tier)
                        # Move randomly selected provider to front
                        providers_to_try.remove(r_provider)
                        providers_to_try.insert(0, r_provider)
                        print(f"[RPCOptimizer] 🎲 Exploration: trying {r_provider.name} first")

            # 3. Iterate and Try until Success
            last_error = None
            
            for provider in providers_to_try:
                # Check Rate Limit
                if not self.rate_limiter.is_allowed(provider.name, provider.limit_rps):
                    # print(f"[RPCOptimizer] Rate limited: {provider.name}")
                    continue

                print(f"[RPCOptimizer] Selected {provider.name} (Priority {provider.priority})")
                
                # Try to Reserve Quota
                estimated_cost = provider.get_cost(method)
                if not self.quota_manager.try_reserve(provider.name, estimated_cost, provider.limit_monthly):
                    # print(f"[RPCOptimizer] Quote Reservation Failed: {provider.name}")
                    continue

                try:
                    # Execute Request
                    start_time = time.time()
                    raw_response, actual_latency = await self.rpc_client.send_request(
                        provider_url=provider.base_url,
                        payload=payload,
                        timeout=5 # fast failover
                    )
                    
                    # Success Handling
                    self._record_metrics(provider, method, actual_latency, success=True)
                    
                    # Note: Quota already incremented by try_reserve!
                    
                    return self.response_handler.build_response(
                        raw_response=raw_response,
                        selected_provider=provider.name,
                        score=1.0,
                        weights={"Latency": 1.0, "Price": 0.0},
                        latency_ms=actual_latency,
                        price_usd=provider.price_per_call(method),
                        all_provider_scores=None 
                    )
                except Exception as e:
                    print(f"[RPCOptimizer] Error from {provider.name}: {e}")
                    last_error = e
                    # Record metric even on failure
                    self._record_metrics(provider, method, 5000.0, success=False)
                    # Rollback Quota Reservation
                    self.quota_manager.decrement(provider.name, estimated_cost)
                    continue # Try next provider

            # If we reach here, all providers failed or were rate limited
            error_msg = f"All eligible providers failed or were rate limited. Last error: {last_error}" if last_error else "All eligible providers are rate limited"
            return self.response_handler.build_error_response(
                error_message=error_msg,
                request_id=request_id,
                error_code=-32000
            )

        except Exception as e:
            print(f"[RPCOptimizer] Critical Error: {e}")
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
                # print(f"[RPCOptimizer] Monthly Quota Exceeded: {p.name} (Limit {p.limit_monthly})")
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
