import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import aiohttp
import json
import shutil
import time
from collections import Counter
from typing import Dict, List


class ConcurrentLoadTest:
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

        try:
            start_t = time.time()
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                res_data = await response.json()
                # print(f"Req {request_id} finished in {time.time()-start_t:.3f}s")
                return res_data
        except Exception as e:
            print(f" Request {request_id} failed: {e}")
            return {"error": str(e), "bliply": {"selected_provider": "ERROR"}}


async def test_concurrent_rps_limit():

    #     Test Scenario: Concurrent RPS Limit Check
    
    #     Configuration:
    #     - PAID_PROVIDERS=chainstack
    #     - QuickNode: FREE, RPS Limit = 3. 200 Credit limit.
    #     - Alchemy: FREE, RPS Limit = 50. 200 CU limit.
    #     - Chainstack: PAID, RPS Limit = 100.
    
    #     Goal:
    #     - Send a burst of requests > 3 RPS to trigger QuickNode's rate limiter locally.
    #     - Verify that requests failover to Alchemy or Chainstack when QuickNode is rate-limited.
    
    #     Note: We rely on the local RateLimiter class in router.py enforcing these limits.

    print("\n" + "=" * 70)
    print("SCENARIO: Concurrent Stress Test (RPS Limit Check)")
    print("=" * 70)

    tester = ConcurrentLoadTest()
    tester.backup_usage_data()
    tester.reset_usage_data()

    try:
        provider_usage = Counter()
        
        # Send a burst of 20 requests concurrently
        # QuickNode limit is 3 RPS.
        # We expect at most ~3-4 requests to hit QuickNode in the first second.
        # The rest should go to Alchemy (Limit 50).
        
        batch_size = 20
        print(f"\n Sending burst of {batch_size} concurrent requests...\n")
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            start_time = time.time()
            
            for i in range(batch_size):
                tasks.append(tester.make_request(session, i + 1, "eth_blockNumber"))
            
            results = await asyncio.gather(*tasks)
            duration = time.time() - start_time
            
        print(f"\n Batch finished in {duration:.3f} seconds ({batch_size/duration:.1f} RPS)\n")

        for res in results:
            bliply = res.get("bliply", {})
            selected_provider = bliply.get("selected_provider", "UNKNOWN")
            provider_usage[selected_provider] += 1
            
        print(f"Results Breakdown:")
        for provider, count in provider_usage.most_common():
            print(f"   {provider}: {count} requests")

        # Analysis
        qn_count = provider_usage.get("QuickNode", 0)
        alch_count = provider_usage.get("Alchemy", 0)
        
        print(f"\n Analysis:")
        print(f"   QuickNode (Limit 3 RPS): {qn_count}")
        print(f"   Alchemy (Limit 50 RPS): {alch_count}")
        
        # We expect QuickNode to handle only a few requests (around 3-5 due to sliding window timing)
        # The rest must failover to Alchemy.
        
        assert qn_count <= 6, f"QuickNode Rate Limit Failed. Processed {qn_count} requests in {duration:.2f}s (Limit is 3 RPS)"
        assert alch_count >= 14, f"Failover did not occur correctly. Alchemy processed only {alch_count}"
        
        print(f"\n TEST PASSED: High concurrency triggered rate limiting and failover correctly.")

    except AssertionError as e:
        print(f"\n TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n ERROR: {e}\n")
        raise
    finally:
        tester.restore_usage_data()


if __name__ == "__main__":
    asyncio.run(test_concurrent_rps_limit())
