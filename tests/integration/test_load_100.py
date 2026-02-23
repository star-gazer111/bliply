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


class LoadTest100:
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
            "params": [], 
            "id": request_id,
        }
        
        # Add dummy params if needed
        if method == "eth_estimateGas":
             payload["params"] = [{
                "to": "0x0000000000000000000000000000000000000000",
                "data": "0x"
            }]
        elif method == "eth_gasPrice":
             # No params needed
             pass
        elif method == "eth_getTransactionCount":
             payload["params"] = ["0x0000000000000000000000000000000000000000", "latest"]


        try:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return await response.json()
        except Exception as e:
            print(f" Request {request_id} failed: {e}")
            return {"error": str(e), "bliply": {"selected_provider": "ERROR"}}


async def test_load_100_spillover():

    #     Test Scenario: High Load 100 Requests (1 Paid + 2 Free)
    
    #     Configuration:
    #     - PAID_PROVIDERS=chainstack
    #     - Alchemy: FREE, 200 CU limit. Default cost 10. Max ~20 requests.
    #     - QuickNode: FREE, 200 Credit limit. Default cost 20. Max ~10 requests.
    #     - Chainstack: PAID, 200 requests limit
    
    #     Expected:
    #     - Combined free capacity: ~30 requests.
    #     - Remaining ~70 requests spill over to Chainstack.

    print("\n" + "=" * 70)
    print("SCENARIO: Load Test 100 Requests (Spillover Check)")
    print("=" * 70)

    tester = LoadTest100()

    tester.backup_usage_data()
    tester.reset_usage_data()

    try:
        provider_usage = Counter()
        
        # Use new methods that fall back to default costs
        methods = ["eth_gasPrice", "eth_getTransactionCount", "eth_estimateGas"]
        total_requests = 100
        
        print(f"\n Making {total_requests} mixed requests...\n")

        async with aiohttp.ClientSession() as session:
            for i in range(total_requests):
                method = methods[i % 3] 
                
                response = await tester.make_request(session, i + 1, method)

                bliply = response.get("bliply", {})
                selected_provider = bliply.get("selected_provider", "UNKNOWN")
                
                # Treat ERROR as failing to find provider (should use paid if working correctly)
                # But if everything fails, we count as ERROR
                
                provider_usage[selected_provider] += 1
                
                if (i + 1) % 10 == 0:
                    usage = tester.get_current_usage()
                    print(
                        f"#{i+1:3d}: {method:25s} -> {selected_provider:10s} | "
                        f"Alch={usage.get('Alchemy', 0):3d}, "
                        f"QN={usage.get('QuickNode', 0):3d}, "
                        f"CS={usage.get('Chainstack', 0):3d}"
                    )

                # 10 reqs/sec approximately
                await asyncio.sleep(0.1) 

        print(f"\nFinal Results:")
        for provider, count in provider_usage.most_common():
            print(f"   {provider}: {count} requests")

        final_usage = tester.get_current_usage()
        print(f"\n Quota Usage:")
        for provider, usage in final_usage.items():
            print(f"   {provider}: {usage} units")
            
        print(f"\n Analysis:")
        
        free_count = provider_usage.get("Alchemy", 0) + provider_usage.get("QuickNode", 0)
        paid_count = provider_usage.get("Chainstack", 0)
        
        print(f"   Free tier: {free_count} requests")
        print(f"   Paid tier: {paid_count} requests")
        print(f"   Errors:    {provider_usage.get('ERROR', 0)} requests")

        # Expected: Free ~30-35, Paid ~65-70
        # Assert free count is depleted (should be around 30, allow buffer to 40)
        # Assert paid count picked up the slack
        
        assert free_count <= 45, f"Too many free requests ({free_count}), expected < 45"
        assert paid_count >= 55, f"Too few paid requests ({paid_count}), expected > 55"
        
        print(f"\n TEST PASSED: Spillover occurred correctly under 100 request load")

    except AssertionError as e:
        print(f"\n TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n ERROR: {e}\n")
        raise
    finally:
        tester.restore_usage_data()


if __name__ == "__main__":
    asyncio.run(test_load_100_spillover())
