import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import aiohttp
import json
import shutil
import random
from collections import Counter
from typing import Dict


class MixedWorkloadTest:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.project_root = project_root
        self.usage_file = self.project_root / "data" / "usage_counters.json"
        self.usage_backup = self.usage_file.with_suffix(".json.backup")

    def backup_usage_data(self):
        if self.usage_file.exists():
            shutil.copy(self.usage_file, self.usage_backup)
            print(f" Backed up usage data")

    def restore_usage_data(self):
        if self.usage_backup.exists():
            shutil.copy(self.usage_backup, self.usage_file)
            self.usage_backup.unlink()
            print(f" Restored usage data")

    def reset_usage_data(self):
        with open(self.usage_file, "w") as f:
            json.dump({}, f)
        print(f" Reset usage counters")

    def get_current_usage(self) -> Dict[str, int]:
        if self.usage_file.exists():
            with open(self.usage_file, "r") as f:
                return json.load(f)
        return {}

    async def make_request(
        self, session: aiohttp.ClientSession, request_id: int, method: str
    ) -> Dict:
        url = f"{self.base_url}/api/rpc/best"

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": [], # params don't matter for cost calculation in this mock setup usually
            "id": request_id,
        }
        
        # Add dummy params for eth_call if needed by real nodes, 
        # but for cost calc we rely on method name
        if method == "eth_call":
             payload["params"] = [{
                "to": "0x0000000000000000000000000000000000000000",
                "data": "0x"
            }, "latest"]
        elif method == "eth_getBalance":
             payload["params"] = ["0x0000000000000000000000000000000000000000", "latest"]


        try:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return await response.json()
        except Exception as e:
            print(f" Request {request_id} failed: {e}")
            return {"error": str(e), "bliply": {"selected_provider": "ERROR"}}


async def test_mixed_workload_spillover():

    #     Test Scenario: Mixed Workload (1 Paid + 2 Free)
    
    #     Configuration:
    #     - PAID_PROVIDERS=chainstack (should be set in .env)
    #     - Alchemy: FREE, 200 CU limit. Costs: blockNumber=10, call=26, getBalance=20
    #     - QuickNode: FREE, 200 Credit limit. Costs: default=20
    #     - Chainstack: PAID, 200 requests limit
    
    print("\n" + "=" * 70)
    print("SCENARIO: Mixed Workload Spillover (2 Free -> 1 Paid)")
    print("=" * 70)

    tester = MixedWorkloadTest()

    tester.backup_usage_data()
    tester.reset_usage_data()

    try:
        provider_usage = Counter()
        # We will send a mix of requests.
        # Let's say we send 60 requests total.
        # Mix:
        # 1. eth_blockNumber (Low cost Alchemy)
        # 2. eth_call (High cost Alchemy)
        # 3. eth_getBalance (Medium cost Alchemy)
        
        methods = ["eth_blockNumber", "eth_call", "eth_getBalance"]
        total_requests = 60
        
        print(f"\n Making {total_requests} mixed requests...\n")

        async with aiohttp.ClientSession() as session:
            for i in range(total_requests):
                # Cycle through methods: 0, 1, 2, 0, 1, 2...
                method = methods[i % 3] 
                
                response = await tester.make_request(session, i + 1, method)

                bliply = response.get("bliply", {})
                selected_provider = bliply.get("selected_provider", "UNKNOWN")
                latency = bliply.get("latency_ms", 0)

                provider_usage[selected_provider] += 1
                
                # Check usage periodically
                if (i + 1) % 10 == 0:
                    usage = tester.get_current_usage()
                    print(
                        f"#{i+1:3d}: {method:15s} -> {selected_provider:10s} | "
                        f"Alch={usage.get('Alchemy', 0):3d}, "
                        f"QN={usage.get('QuickNode', 0):3d}, "
                        f"CS={usage.get('Chainstack', 0):3d}"
                    )

                await asyncio.sleep(0.1) # Small delay to avoid rate limiting issues obscuring quota logic

        print(f"\nFinal Results:")
        for provider, count in provider_usage.most_common():
            print(f"   {provider}: {count} requests")

        final_usage = tester.get_current_usage()
        print(f"\n Quota Usage:")
        for provider, usage in final_usage.items():
            print(f"   {provider}: {usage} units")
            
        print(f"\n Analysis:")
        
        # Expected Logic:
        # Alchemy Limit 200.
        # Avg cost per request ~ (10+26+20)/3 = ~18.6 CU
        # Max requests ~ 200 / 18.6 = ~10-11 requests.
        
        # QuickNode Limit 200.
        # Cost per request = 20.
        # Max requests = 200 / 20 = 10 requests.
        
        # Total Free Capacity = ~20-22 requests.
        # Total Requests = 60.
        # Expected Paid Requests = ~38-40.
        
        free_count = provider_usage.get("Alchemy", 0) + provider_usage.get("QuickNode", 0)
        paid_count = provider_usage.get("Chainstack", 0)
        
        print(f"   Free tier: {free_count} requests")
        print(f"   Paid tier: {paid_count} requests")

        # Assertions
        # Allow some buffer for initial state or slight variations
        assert free_count <= 30, f"Too many free requests ({free_count}), expected shutdown around 20-25"
        assert paid_count >= 30, f"Too few paid requests ({paid_count}), expected spillover around 20-25"
        
        print(f"\n TEST PASSED: Spillover occurred correctly with mixed workload")

    except AssertionError as e:
        print(f"\n TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n ERROR: {e}\n")
        raise
    finally:
        tester.restore_usage_data()


if __name__ == "__main__":
    asyncio.run(test_mixed_workload_spillover())
