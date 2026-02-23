import asyncio
from unittest.mock import MagicMock, AsyncMock
from core.router import RPCOptimizer
from providers.base import RPCProvider

async def test_exploration_mode():
    """
    Test that exploration mode randomly selects from priority 1 providers
    while respecting quota and rate limits.
    """
    print("\n=== Testing Exploration Mode ===\n")
    
    # Setup Providers
    p1 = RPCProvider({
        "name": "AlchemyFree", 
        "base_url": "http://alchemy", 
        "limit_rps": 100, 
        "limit_monthly": 1000, 
        "priority": 1
    })
    p2 = RPCProvider({
        "name": "QuickNodeFree", 
        "base_url": "http://quicknode", 
        "limit_rps": 100, 
        "limit_monthly": 1000, 
        "priority": 1
    })
    p3 = RPCProvider({
        "name": "ChainstackPaid", 
        "base_url": "http://chainstack", 
        "limit_rps": 1000, 
        "limit_monthly": 999999, 
        "priority": 2
    })
    
    # Test with exploration enabled
    optimizer = RPCOptimizer([p1, p2, p3], enable_exploration=True, exploration_rate=1.0)  # 100% exploration for testing
    
    # Reset quota
    optimizer.quota_manager.data_file = "test_data/test_exploration.json"
    optimizer.quota_manager.usage_data = {}
    optimizer.quota_manager._save_data()
    
    # Mock latencies (Alchemy faster)
    optimizer.metric_collector.get_provider_latency = MagicMock(side_effect=lambda p, m, default: {
        "AlchemyFree": 50.0,
        "QuickNodeFree": 200.0,
        "ChainstackPaid": 100.0
    }.get(p.name, 100.0))
    
    # Mock RPC Client
    optimizer.rpc_client.send_request = AsyncMock(return_value=({"result": "ok"}, 50.0))
    
    # Test 1: Exploration should randomly pick from free tier
    print("Test 1: Exploration mode should randomly select from priority 1 providers")
    selections = {"AlchemyFree": 0, "QuickNodeFree": 0, "ChainstackPaid": 0}
    
    for i in range(20):
        req = {"method": "eth_blockNumber", "id": i, "jsonrpc": "2.0", "params": []}
        resp = await optimizer.optimize_request(req)
        selected = resp["bliply"]["selected_provider"]
        selections[selected] = selections.get(selected, 0) + 1
    
    print(f"Results after 20 requests (100% exploration):")
    print(f"  AlchemyFree: {selections['AlchemyFree']}")
    print(f"  QuickNodeFree: {selections['QuickNodeFree']}")
    print(f"  ChainstackPaid: {selections['ChainstackPaid']}")
    
    # Both free tier providers should have been selected
    assert selections["AlchemyFree"] > 0, "AlchemyFree should be selected at least once"
    assert selections["QuickNodeFree"] > 0, "QuickNodeFree should be selected at least once"
    assert selections["ChainstackPaid"] == 0, "ChainstackPaid should NOT be selected (free tier available)"
    print("✅ Test 1 passed: Both free tier providers were selected\n")
    
    # Test 2: Exploration with quota exhaustion
    print("Test 2: Exploration should fall back to paid when free tier exhausted")
    optimizer.quota_manager.usage_data["AlchemyFree"] = 1000  # Exhausted
    optimizer.quota_manager.usage_data["QuickNodeFree"] = 1000  # Exhausted
    
    req = {"method": "eth_blockNumber", "id": 100, "jsonrpc": "2.0", "params": []}
    resp = await optimizer.optimize_request(req)
    selected = resp["bliply"]["selected_provider"]
    
    print(f"Selected provider: {selected}")
    assert selected == "ChainstackPaid", "Should fall back to paid provider when free tier exhausted"
    print("✅ Test 2 passed: Fell back to paid provider\n")
    
    # Test 3: 10% exploration rate
    print("Test 3: Testing 10% exploration rate")
    optimizer2 = RPCOptimizer([p1, p2, p3], enable_exploration=True, exploration_rate=0.1)
    optimizer2.quota_manager.data_file = "test_data/test_exploration2.json"
    optimizer2.quota_manager.usage_data = {}
    optimizer2.quota_manager._save_data()
    optimizer2.metric_collector.get_provider_latency = optimizer.metric_collector.get_provider_latency
    optimizer2.rpc_client.send_request = AsyncMock(return_value=({"result": "ok"}, 50.0))
    
    selections2 = {"AlchemyFree": 0, "QuickNodeFree": 0}
    for i in range(100):
        req = {"method": "eth_blockNumber", "id": i, "jsonrpc": "2.0", "params": []}
        resp = await optimizer2.optimize_request(req)
        selected = resp["bliply"]["selected_provider"]
        selections2[selected] = selections2.get(selected, 0) + 1
    
    print(f"Results after 100 requests (10% exploration):")
    print(f"  AlchemyFree: {selections2['AlchemyFree']}")
    print(f"  QuickNodeFree: {selections2['QuickNodeFree']}")
    
    # With 10% exploration, AlchemyFree should dominate (it's faster)
    # But QuickNode should still get some requests from exploration
    assert selections2["AlchemyFree"] > selections2["QuickNodeFree"], "Faster provider should be selected more often"
    assert selections2["QuickNodeFree"] > 0, "Slower provider should still be explored occasionally"
    print("✅ Test 3 passed: 10% exploration working correctly\n")
    
    print("=== All Exploration Tests Passed! ===")

if __name__ == "__main__":
    asyncio.run(test_exploration_mode())
