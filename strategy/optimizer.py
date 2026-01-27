from typing import Dict, Any, List, Optional
import pandas as pd

# Phase 1 services
from services.request_parser import RequestParser
from services.metric_collector import MetricCollector
from services.eligibility_filter import EligibilityFilter
from infra.http_client import RPCClient
from services.response_handler import ResponseHandler

# Existing strategy modules
from strategy.scoring_engine import calculate_dynamic_scores

# Data layer
from data.providers import Provider


class RPCOptimizer:
    """
    Main orchestrator that implements the 11-step flow from spec:

    1. Incoming Request (handled by Flask)
    2. Parse & Identify Context
    3. Collect Current Provider Metrics
    4. Normalization
    5. Compute CRITIC Weights
    6. Score Providers
    7. Eligibility Filter
    8. Provider Selection
    9. Forward Request
    10. Receive Response
    11. Update Metrics
    """

    def __init__(
        self,
        providers: List[Provider],
        enable_exploration: bool = False,
        exploration_rate: float = 0.1,
    ):
        """
        Args:
            providers: List of all Provider objects
            enable_exploration: Enable epsilon-greedy exploration
            exploration_rate: Probability of exploring (0.0 to 1.0)
        """
        self.providers = providers
        self.provider_dict = {p.name.lower(): p for p in providers}

        # Initializing all the services from Phase 1
        self.parser = RequestParser()
        self.metric_collector = MetricCollector()
        self.eligibility_filter = EligibilityFilter()
        self.rpc_client = RPCClient(timeout=30, max_retries=2)
        self.response_handler = ResponseHandler()

        # Exploration settings
        self.enable_exploration = enable_exploration
        self.exploration_rate = exploration_rate

        print(f"[RPCOptimizer] Initialized with {len(providers)} providers")
        print(f"[RPCOptimizer] Providers: {[p.name for p in providers]}")

    def optimize_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main optimization flow - implements all 11 steps.

        Args:
            payload: Raw JSON-RPC request

        Returns:
            Complete response with optimization metadata

        Raises:
            ValueError: If request is invalid
            Exception: If optimization fails
        """
        try:

            # STEP 1: Incoming Request (received by Flask)

            # STEP 2: Parse & Identify Context
            parsed_request = self.parser.parse_rpc_request(payload)
            method = parsed_request["method"]
            request_id = parsed_request["id"]

            print(f"\n[RPCOptimizer] Request: method={method}, id={request_id}")

            # STEP 3: Collecting Current Provider Metrics
            metrics = self.metric_collector.collect_current_metrics(
                self.providers, method
            )

            if not metrics["has_data"]:
                print(f"[RPCOptimizer] No metrics data for {method}, using fallback")
                return self._fallback_routing(payload, parsed_request)

            print(
                f"[RPCOptimizer] Collected metrics for {len(metrics['providers'])} providers"
            )

            # STEP 4: Normalization
            # STEP 5: Compute CRITIC Weights
            # STEP 6: Score Providers
            # Note: The calculate_dynamic_scores() function does steps 4, 5, 6 together

            scored_df, weights = calculate_dynamic_scores(self.providers, method=method)

            print(
                f"[RPCOptimizer] CRITIC Weights: Latency={weights[0]:.3f}, Price={weights[1]:.3f}"
            )

            # STEP 7: Eligibility Filter

            eligible_df = self.eligibility_filter.filter_dataframe(
                scored_df, allow_fallback=True
            )

            if eligible_df.empty:
                print(f"[RPCOptimizer] No eligible providers for {method}")
                return self.response_handler.build_no_providers_response(
                    method=method, request_id=request_id
                )

            # STEP 8: Provider Selection
            
            best_row = self._select_provider(eligible_df)
            best_provider_name = best_row["Provider"]
            best_provider = self.provider_dict[best_provider_name.lower()]

            print(
                f"[RPCOptimizer] Selected: {best_provider_name} (Score={best_row['Score']:.4f})"
            )

            # STEP 9: Forward the Request
            
            raw_response, actual_latency = self.rpc_client.send_request(
                provider_url=best_provider.base_url, payload=payload, timeout=30
            )

            print(f"[RPCOptimizer] Response received in {actual_latency:.2f}ms")

            # STEP 10: Receive Response & Build Final Response
            
            final_response = self.response_handler.build_response(
                raw_response=raw_response,
                selected_provider=best_provider_name,
                score=float(best_row["Score"]),
                weights={"Latency": float(weights[0]), "Price": float(weights[1])},
                all_provider_scores=scored_df,
                latency_ms=actual_latency,
                price_usd=float(best_row["Price"]),
            )

            # STEP 11: Update Metrics
            
            self._update_metrics(
                provider=best_provider,
                method=method,
                latency_ms=actual_latency,
                price_usd=float(best_row["Price"]),
                success=True,
            )

            # Also update "Best" virtual provider metrics
            self._update_best_provider_metrics(
                method=method,
                latency_ms=actual_latency,
                price_usd=float(best_row["Price"]),
            )

            return final_response

        except ValueError as e:
            # Invalid request format
            print(f"[RPCOptimizer] Validation error: {e}")
            return self.response_handler.build_error_response(
                error_message=str(e),
                request_id=payload.get("id", 1),
                error_code=-32600,  # Invalid Request
            )

        except TimeoutError as e:
            # Provider timeout
            print(f"[RPCOptimizer] Timeout error: {e}")
            return self.response_handler.build_error_response(
                error_message=f"Request timed out: {str(e)}",
                request_id=payload.get("id", 1),
                error_code=-32603,  # Internal error
            )

        except Exception as e:
            # Unexpected error
            print(f"[RPCOptimizer] Unexpected error: {e}")
            import traceback

            traceback.print_exc()

            return self.response_handler.build_error_response(
                error_message=f"Optimization failed: {str(e)}",
                request_id=payload.get("id", 1),
                error_code=-32603,  # Internal error
            )

    def _select_provider(self, eligible_df: pd.DataFrame) -> pd.Series:
        """
        Select best provider from eligible candidates.
        Implements epsilon-greedy exploration if enabled.

        Args:
            eligible_df: DataFrame of eligible providers with scores

        Returns:
            Row (Series) of selected provider
        """
        if eligible_df.empty:
            raise ValueError("No eligible providers")

        # Exploitation: pick highest score
        if not self.enable_exploration:
            return eligible_df.loc[eligible_df["Score"].idxmax()]

        # Epsilon-greedy: explore with probability epsilon
        import random

        if random.random() < self.exploration_rate:
            # Exploration: pick random provider
            random_idx = random.choice(eligible_df.index.tolist())
            print(f"[RPCOptimizer] 🎲 Exploring: random selection")
            return eligible_df.loc[random_idx]
        else:
            # Exploitation: pick best
            return eligible_df.loc[eligible_df["Score"].idxmax()]

    def _fallback_routing(
        self, payload: Dict[str, Any], parsed_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fallback when no metrics available (cold start).
        Routes to first non-Best provider.
        """
        method = parsed_request["method"]

        # Find first real provider (not Best)
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

        # Make request
        try:
            raw_response, latency_ms = self.rpc_client.send_request(
                provider_url=fallback_provider.base_url, payload=payload, timeout=30
            )

            price_usd = fallback_provider.price_per_call(method)

            # Update metrics for cold start
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
        provider: Provider,
        method: str,
        latency_ms: float,
        price_usd: float,
        success: bool,
    ):
        """
        Step 11: Update metrics after request completion.
        """
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
        """
        Update metrics for virtual "Best" provider.
        """
        best_provider = self.provider_dict.get("best")
        if best_provider:
            best_provider.metrics.add_record(
                provider="Best", method=method, latency_ms=latency_ms, price=price_usd
            )

    def get_provider_by_name(self, name: str) -> Optional[Provider]:
        """
        Get provider by name (case-insensitive).
        """
        return self.provider_dict.get(name.lower())

    def get_all_providers(self) -> List[Provider]:
        """
        Get list of all providers (excluding Best).
        """
        return [p for p in self.providers if p.name.lower() != "best"]

    def close(self):
        """
        Cleanup: close RPC client connections.
        """
        self.rpc_client.close()
        print("[RPCOptimizer] Closed RPC client connections")
