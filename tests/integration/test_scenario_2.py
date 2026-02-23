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
        
        # Add minimal params for certain methods
        if method == "eth_estimateGas":
             payload["params"] = [{
                "to": "0x0000000000000000000000000000000000000000",
                "data": "0x"
            }]
        elif method == "eth_getTransactionCount":
             payload["params"] = ["0x0000000000000000000000000000000000000000", "latest"]


        try:
            start_t = time.time()
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=40)
            ) as response:
                res_data = await response.json()
                return res_data
        except Exception as e:
            # print(f" Request {request_id} failed: {e}")
            return {"error": str(e), "bliply": {"selected_provider": "ERROR"}}


async def test_large_concurrent_load():
    
    #     Test Scenario 2 (Isolated): Large Concurrent Batch
    #     Burst of 100 requests. 
    #     QuickNode limit 3, Alchemy limit 50. Chainstack limit 100.
    
    print("\n" + "=" * 70)
    print("SCENARIO 2: Large Concurrent Batch (100 concurrent requests)")
    print("=" * 70)

    tester = ConcurrentLoadTest()
    tester.backup_usage_data()
    tester.reset_usage_data()

    try:
        provider_usage = Counter()
        batch_size = 100
        
        print(f"\n Sending burst of {batch_size} concurrent requests (eth_blockNumber)...\n")
        
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

        qn_count = provider_usage.get("QuickNode", 0)
        alch_count = provider_usage.get("Alchemy", 0)
        cs_count = provider_usage.get("Chainstack", 0)
        
        # Expected:
        # QuickNode: ~3-10 max (due to rate limit)
        # Alchemy: ~50 max (due to rate limit)
        # Chainstack: The rest (~40+)
        
        print(f"\n Analysis:")
        print(f"   QuickNode (Limit 3 RPS): {qn_count}")
        print(f"   Alchemy (Limit 50 RPS): {alch_count}")
        print(f"   Chainstack (Limit 100 RPS): {cs_count}")
        
        assert qn_count <= 8, f"QuickNode exceeded rate limit (got {qn_count})"
        assert alch_count >= 10, f"Alchemy underutilized (got {alch_count})"
        
        if duration < 1.5:
             assert alch_count <= 60, f"Alchemy exceeded rate limit (got {alch_count}) in < 1.5s"
             assert cs_count >= 30, f"Chainstack should have picked up load (got {cs_count})"

        print(f"\n TEST PASSED: Spillover to paid tier under high concurrency confirmed.")
        
    except AssertionError as e:
        print(f"\n TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n ERROR: {e}\n")
        raise
    finally:
        tester.restore_usage_data()

if __name__ == "__main__":
    asyncio.run(test_large_concurrent_load())
