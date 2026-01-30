from typing import Dict, Any, List, Optional
import pandas as pd

from services.request_parser import RequestParser
from services.metric_collector import MetricCollector
from services.eligibility_filter import EligibilityFilter
from services.response_handler import ResponseHandler
from infra.http_client import RPCClient

from strategy.scoring_engine import calculate_dynamic_scores

from providers.base import RPCProvider


class RPCOptimizer:
    def __init__(
        self,
        providers: List[RPCProvider],
        enable_exploration: bool = False,
        exploration_rate: float = 0.1,
    ):
        self.providers = providers
        self.provider_dict = {p.name.lower(): p for p in providers}

        self.parser = RequestParser()
        self.metric_collector = MetricCollector()
        self.eligibility_filter = EligibilityFilter()
        self.rpc_client = RPCClient(timeout=30, max_retries=2)
        self.response_handler = ResponseHandler()

        self.enable_exploration = enable_exploration
        self.exploration_rate = exploration_rate

        print(f"[RPCOptimizer] Initialized with {len(providers)} providers")
        print(f"[RPCOptimizer] Providers: {[p.name for p in providers]}")

    async def optimize_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:

            parsed_request = self.parser.parse_rpc_request(payload)
            method = parsed_request["method"]
            request_id = parsed_request["id"]

            print(f"\n[RPCOptimizer] Request: method={method}, id={request_id}")

            metrics = self.metric_collector.collect_current_metrics(
                self.providers, method
            )

            if not metrics["has_data"]:
                print(f"[RPCOptimizer] No metrics data for {method}, initializing all providers")
                return await self._initialize_providers(payload, parsed_request)

            print(
                f"[RPCOptimizer] Collected metrics for {len(metrics['providers'])} providers"
            )

            scored_df, weights = calculate_dynamic_scores(self.providers, method=method)

            print(
                f"[RPCOptimizer] CRITIC Weights: Latency={weights[0]:.3f}, Price={weights[1]:.3f}"
            )

            eligible_df = self.eligibility_filter.filter_dataframe(
                scored_df, allow_fallback=True
            )

            if eligible_df.empty:
                print(f"[RPCOptimizer] No eligible providers for {method}")
                return self.response_handler.build_no_providers_response(
                    method=method, request_id=request_id
                )

            best_row = self._select_provider(eligible_df)
            best_provider_name = best_row["Provider"]
            best_provider = self.provider_dict[best_provider_name.lower()]

            print(
                f"[RPCOptimizer] Selected: {best_provider_name} (Score={best_row['Score']:.4f})"
            )

            raw_response, actual_latency = await self.rpc_client.send_request(
                provider_url=best_provider.base_url, payload=payload, timeout=30
            )

            print(f"[RPCOptimizer] Response received in {actual_latency:.2f}ms")

            final_response = self.response_handler.build_response(
                raw_response=raw_response,
                selected_provider=best_provider_name,
                score=float(best_row["Score"]),
                weights={"Latency": float(weights[0]), "Price": float(weights[1])},
                all_provider_scores=scored_df,
                latency_ms=actual_latency,
                price_usd=float(best_row["Price"]),
            )

            self._update_metrics(
                provider=best_provider,
                method=method,
                latency_ms=actual_latency,
                price_usd=float(best_row["Price"]),
                success=True,
            )


            return final_response

        except ValueError as e:
            print(f"[RPCOptimizer] Validation error: {e}")
            return self.response_handler.build_error_response(
                error_message=str(e),
                request_id=payload.get("id", 1),
                error_code=-32600,  # Invalid Request
            )

        except TimeoutError as e:
            print(f"[RPCOptimizer] Timeout error: {e}")
            return self.response_handler.build_error_response(
                error_message=f"Request timed out: {str(e)}",
                request_id=payload.get("id", 1),
                error_code=-32603,  # Internal error
            )

        except Exception as e:
            print(f"[RPCOptimizer] Unexpected error: {e}")
            import traceback

            traceback.print_exc()

            return self.response_handler.build_error_response(
                error_message=f"Optimization failed: {str(e)}",
                request_id=payload.get("id", 1),
                error_code=-32603,  # Internal error
            )

    def _select_provider(self, eligible_df: pd.DataFrame) -> pd.Series:
        if eligible_df.empty:
            raise ValueError("No eligible providers")

        if not self.enable_exploration:
            return eligible_df.loc[eligible_df["Score"].idxmax()]

        import random

        if random.random() < self.exploration_rate:
            random_idx = random.choice(eligible_df.index.tolist())
            print(f"[RPCOptimizer] 🎲 Exploring: random selection")
            return eligible_df.loc[random_idx]
        else:
            return eligible_df.loc[eligible_df["Score"].idxmax()]

    async def _initialize_providers(
        self, payload: Dict[str, Any], parsed_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Initialize all providers by calling them in parallel to collect first metrics"""
        method = parsed_request["method"]
        import asyncio
        
        # Get all eligible providers (excluding "Best")
        eligible_providers = [p for p in self.providers if p.name.lower() != "best"]
        
        if not eligible_providers:
            return self.response_handler.build_error_response(
                error_message="No providers available",
                request_id=parsed_request["id"],
                error_code=-32603,
            )
        
        print(f"[RPCOptimizer] Initializing {len(eligible_providers)} providers in parallel")
        
        # Call all providers in parallel
        tasks = []
        for provider in eligible_providers:
            task = self.rpc_client.send_request(
                provider_url=provider.base_url, payload=payload, timeout=10
            )
            tasks.append((provider, task))
        
        # Wait for all responses
        results = []
        for provider, task in tasks:
            try:
                raw_response, latency_ms = await task
                price_usd = provider.price_per_call(method)
                results.append({
                    "provider": provider,
                    "response": raw_response,
                    "latency_ms": latency_ms,
                    "price_usd": price_usd,
                    "success": True
                })
                # Update metrics immediately
                self._update_metrics(
                    provider=provider,
                    method=method,
                    latency_ms=latency_ms,
                    price_usd=price_usd,
                    success=True,
                )
            except Exception as e:
                print(f"[RPCOptimizer] {provider.name} initialization failed: {e}")
                results.append({
                    "provider": provider,
                    "success": False
                })
        
        # Select the fastest successful provider
        successful = [r for r in results if r["success"]]
        if not successful:
            return self.response_handler.build_error_response(
                error_message="All providers failed",
                request_id=parsed_request["id"],
                error_code=-32603,
            )
        
        best_result = min(successful, key=lambda x: x["latency_ms"])
        
        print(f"[RPCOptimizer] Initialized all providers, selected fastest: {best_result['provider'].name} ({best_result['latency_ms']:.2f}ms)")
        
        return self.response_handler.build_response(
            raw_response=best_result["response"],
            selected_provider=best_result["provider"].name,
            score=1.0,  # Perfect score for fastest on cold start
            weights={"Latency": 0.5, "Price": 0.5},
            latency_ms=best_result["latency_ms"],
            price_usd=best_result["price_usd"],
        )

    async def _fallback_routing(
        self, payload: Dict[str, Any], parsed_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        method = parsed_request["method"]

        fallback_provider = None
        for provider in self.providers:
            if provider.name.lower() != "best":
                fallback_provider = provider
                break

        if not fallback_provider:
            return self.response_handler.build_error_response(
                error_message="No providers available",
                request_id=parsed_request["id"],
                error_code=-32603,
            )

        print(f"[RPCOptimizer] Fallback routing to {fallback_provider.name}")

        try:
            raw_response, latency_ms = await self.rpc_client.send_request(
                provider_url=fallback_provider.base_url, payload=payload, timeout=30
            )

            price_usd = fallback_provider.price_per_call(method)

            self._update_metrics(
                provider=fallback_provider,
                method=method,
                latency_ms=latency_ms,
                price_usd=price_usd,
                success=True,
            )

            return self.response_handler.build_response(
                raw_response=raw_response,
                selected_provider=fallback_provider.name,
                score=0.5,  # Neutral score for cold start
                weights={"Latency": 0.5, "Price": 0.5},
                latency_ms=latency_ms,
                price_usd=price_usd,
            )

        except Exception as e:
            print(f"[RPCOptimizer] Fallback failed: {e}")
            return self.response_handler.build_error_response(
                error_message=f"Fallback routing failed: {str(e)}",
                request_id=parsed_request["id"],
                error_code=-32603,
            )

    def _update_metrics(
        self,
        provider: RPCProvider,
        method: str,
        latency_ms: float,
        price_usd: float,
        success: bool,
    ):
        provider.metrics.add_record(
            provider=provider.name,
            method=method,
            latency_ms=latency_ms,
            price=price_usd,
        )

        print(
            f"[RPCOptimizer] Metrics updated: {provider.name} | "
            f"{method} | {latency_ms:.2f}ms | ${price_usd:.6f}"
        )

    def _update_best_provider_metrics(
        self, method: str, latency_ms: float, price_usd: float
    ):
        best_provider = self.provider_dict.get("best")
        if best_provider:
            best_provider.metrics.add_record(
                provider="Best", method=method, latency_ms=latency_ms, price=price_usd
            )

    def get_provider_by_name(self, name: str) -> Optional[RPCProvider]:
        return self.provider_dict.get(name.lower())

    def get_all_providers(self) -> List[RPCProvider]:
        return [p for p in self.providers if p.name.lower() != "best"]

    async def close(self):
        await self.rpc_client.close()
        print("[RPCOptimizer] Closed RPC client connections")
