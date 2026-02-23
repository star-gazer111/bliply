import asyncio
from unittest.mock import MagicMock, AsyncMock
from core.router import RPCOptimizer
from providers.base import RPCProvider

async def test_spillover_logic():
    # Setup Providers
    p1 = RPCProvider({"name": "FreeFast", "base_url": "http://p1", "limit_rps": 2, "limit_monthly": 100, "priority": 1})
    p2 = RPCProvider({"name": "FreeSlow", "base_url": "http://p2", "limit_rps": 2, "limit_monthly": 100, "priority": 1})
    p3 = RPCProvider({"name": "Paid", "base_url": "http://p3", "limit_rps": 10, "limit_monthly": 1000, "priority": 2})
    
    optimizer = RPCOptimizer([p1, p2, p3])
    
    # Use a clean memory-based QuotaManager or isolated file
    optimizer.quota_manager.data_file = "test_data/test_usage.json"
    optimizer.quota_manager.usage_data = {} # Reset in memory
    optimizer.quota_manager._save_data() # Clear file
    
    # Mock MetricCollector to return latencies
    optimizer.metric_collector.get_provider_latency = MagicMock(side_effect=lambda p, m, default: {
        "FreeFast": 50.0,
        "FreeSlow": 200.0,
        "Paid": 100.0
    }.get(p.name, 1000.0))
    
    # Mock RPC Client to avoid actual network calls
    optimizer.rpc_client.send_request = AsyncMock(return_value=({"result": "ok"}, 50.0))
    
    req = {"method": "eth_blockNumber", "id": 1, "jsonrpc": "2.0", "params": []}
    resp = await optimizer.optimize_request(req)
    assert resp["bliply"]["selected_provider"] == "FreeFast"
    
    # Test 2: Hit RPS limit on FreeFast (Limit=2). 
    # We already did 1 request. Do 1 more.
    await optimizer.optimize_request(req)
    # Now FreeFast should be capped (2 requests in window). Next request should spill to FreeSlow.
    
    resp = await optimizer.optimize_request(req)
    assert resp["bliply"]["selected_provider"] == "FreeSlow"
    
    # Test 3: Fill up FreeSlow (Limit=2)
    await optimizer.optimize_request(req) # 2nd request for FreeSlow
    
    # Check Quota Usage (assuming default cost 10 for unknown/default methods)
    # FreeFast used 2x. Cost depends on pricing model. Mocked providers default to "request" (1).
    # But if we updated config, we should check.
    # For this test, providers are created manually in line 8, so they have default pricing_model="request" -> cost=1.
    
    # Now both FreeFast and FreeSlow are full (RPS wise). Should spill to Paid.
    resp = await optimizer.optimize_request(req)
    assert resp["bliply"]["selected_provider"] == "Paid"
    
    print("Spillover logic verified!")

if __name__ == "__main__":
    asyncio.run(test_spillover_logic())
