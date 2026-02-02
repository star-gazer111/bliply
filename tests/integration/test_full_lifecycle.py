import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
from core.router import RPCOptimizer
from providers.base import RPCProvider

async def run_lifecycle_demo():
    print("\nXXX === STARTING RPC OPTIMIZER LIFECYCLE DEMO === XXX\n")

    # 1. Setup Providers
    # FastFree: 5 RPS, 50 Quota
    # SlowFree: 5 RPS, 100 Quota
    # Paid: Unlimited
    providers = [
        RPCProvider({"name": "FastFree", "base_url": "http://fast", "limit_rps": 5, "limit_monthly": 50, "priority": 1}),
        RPCProvider({"name": "SlowFree", "base_url": "http://slow", "limit_rps": 5, "limit_monthly": 100, "priority": 1}),
        RPCProvider({"name": "PaidNode", "base_url": "http://paid", "limit_rps": 1000, "limit_monthly": 10**9, "priority": 2}),
    ]
    
    optimizer = RPCOptimizer(providers)
    
    # 2. Reset Quota & Mock Internals
    optimizer.quota_manager.data_file = "test_data/lifecycle_usage.json"
    optimizer.quota_manager.usage_data = {}
    optimizer.quota_manager._save_data()
    
    # Mock Latency: Fast=50ms, Slow=200ms, Paid=100ms
    optimizer.metric_collector.get_provider_latency = MagicMock(side_effect=lambda p, m, default=None: {
        "FastFree": 50.0, "SlowFree": 200.0, "PaidNode": 100.0
    }.get(p.name, 100.0))
    
    # Mock Network Call (Always succeeds)
    optimizer.rpc_client.send_request = AsyncMock(return_value=({"result": "ok"}, 50.0))

    # Helper to send batch requests
    async def send_batch(count, delay=0):
        print(f"--- Sending Batch of {count} Requests ---")
        for i in range(count):
            req = {"method": "eth_blockNumber", "id": i, "jsonrpc": "2.0", "params": []}
            resp = await optimizer.optimize_request(req)
            selected = resp["bliply"]["selected_provider"]
            
            # Print status directly
            q_usage = optimizer.quota_manager.get_usage(selected)
            print(f"Req {i+1}: Selected [{selected}] | Quota Used: {q_usage}/{optimizer.provider_dict[selected.lower()].limit_monthly}")
            
            if delay:
                await asyncio.sleep(delay)
        print("------------------------------------------\n")

    # === SCENARIO 1: HAPPY PATH ===
    print(">>> PHASE 1: Normal Traffic (Should use FastFree)")
    await send_batch(3) # 3 requests. FastFree (5 RPS) is fine.
    
    # === SCENARIO 2: RATE LIMIT SPIKE ===
    print(">>> PHASE 2: RPS Spike (Should spill to SlowFree)")
    # We send 8 requests quickly. 
    # FastFree handles 2 more (Total 5 in this sec).
    # Then it blocks. Logic should assume spill to SlowFree.
    # Note: Our RateLimiter is sliding window.
    await send_batch(8) 
    
    # === SCENARIO 3: RECOVERY ===
    print(">>> PHASE 3: Cooling Down (Waiting 1.1s for Rate Limits to reset)")
    await asyncio.sleep(1.1)
    print(">>> Resuming Traffic (Should return to FastFree)")
    await send_batch(2)

    # === SCENARIO 4: QUOTA EXHAUSTION ===
    print(">>> PHASE 4: Burning FastFree Quota")
    # FastFree Limit is 50. We used ~13 so far.
    # Let's burn the rest. To avoid RPS limits, we assume we just hack the quota manager directly for the demo
    # or we simulate "days passing". For this test, let's manually act like 40 requests happened.
    print("[!] Manually forwarding quota usage for FastFree to 50/50")
    optimizer.quota_manager.usage_data["FastFree"] = 50 
    
    print(">>> Sending Request (FastFree is now Empty. Should PERMANENTLY switch to SlowFree)")
    await send_batch(2)
    
    # === SCENARIO 5: TOTAL MELTDOWN ===
    print(">>> PHASE 5: Burning SlowFree Quota")
    print("[!] Manually forwarding quota usage for SlowFree to 100/100")
    optimizer.quota_manager.usage_data["SlowFree"] = 100
    
    print(">>> Sending Request (Both Free Tiers Empty. Should switch to PaidNode)")
    await send_batch(2)

    print("\nXXX === DEMO COMPLETE === XXX")

if __name__ == "__main__":
    asyncio.run(run_lifecycle_demo())
