import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import aiohttp
import json
import shutil
from collections import Counter
from typing import Dict


class LogicChangeTest:
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
        self, session: aiohttp.ClientSession, request_id: int
    ) -> Dict:
        url = f"{self.base_url}/api/rpc/best"

        payload = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": request_id,
        }

        try:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return await response.json()
        except Exception as e:
            print(f" Request {request_id} failed: {e}")
            return {"error": str(e), "bliply": {"selected_provider": "ERROR"}}


async def test_scenario_1_two_free_one_paid():

    #     Test Scenario 1: 2 Free + 1 Paid Provider

    #     Configuration:
    #     - PAID_PROVIDERS=chainstack (in .env)
    #     - Alchemy: FREE tier, Priority 1, 200 CU limit (20 requests @ 10 CU each)
    #     - QuickNode: FREE tier, Priority 1, 200 credits (10 requests @ 20 credits each)
    #     - Chainstack: PAID tier, Priority 2, 200 requests limit

    #     Expected:
    #     - First ~30 requests: Use Alchemy + QuickNode (free)
    #     - Remaining requests: Use Chainstack (paid spillover)
    #
    print("\n" + "=" * 70)
    print("SCENARIO 1: 2 Free Providers + 1 Paid Provider")
    print("=" * 70)

    tester = LogicChangeTest()

    tester.backup_usage_data()
    tester.reset_usage_data()

    try:
        provider_usage = Counter()
        total_requests = 50

        print(f"\n Making {total_requests} requests...\n")

        async with aiohttp.ClientSession() as session:
            for i in range(total_requests):
                response = await tester.make_request(session, i + 1)

                bliply = response.get("bliply", {})
                selected_provider = bliply.get("selected_provider", "UNKNOWN")
                latency = bliply.get("latency_ms", 0)

                provider_usage[selected_provider] += 1

                if (i + 1) in [1, 10, 20, 21, 30, 31, 40, 50]:
                    usage = tester.get_current_usage()
                    print(
                        f"#{i+1:3d}: {selected_provider:10s} ({latency:5.0f}ms) | "
                        f"Alchemy={usage.get('Alchemy', 0):3d}, "
                        f"QuickNode={usage.get('QuickNode', 0):3d}, "
                        f"Chainstack={usage.get('Chainstack', 0):3d}"
                    )

                await asyncio.sleep(0.05)

        print(f"\nFinal Results:")
        for provider, count in provider_usage.most_common():
            print(f"   {provider}: {count} requests")

        final_usage = tester.get_current_usage()
        print(f"\n Quota Usage:")
        for provider, usage in final_usage.items():
            print(f"   {provider}: {usage} units")

        free_count = provider_usage.get("Alchemy", 0) + provider_usage.get(
            "QuickNode", 0
        )
        paid_count = provider_usage.get("Chainstack", 0)

        print(f"\n Analysis:")
        print(f"   Free tier: {free_count} requests")
        print(f"   Paid tier: {paid_count} requests")

        assert free_count >= 25, f"Expected ≥25 free requests, got {free_count}"
        assert paid_count >= 15, f"Expected ≥15 paid requests, got {paid_count}"

        print(f"\n TEST PASSED: Spillover occurred correctly")

    finally:
        tester.restore_usage_data()



async def test_scenario_2_one_free_one_paid():
    # Test Scenario 2: 1 Free + 2 Paid Providers

    # Configuration:
    # - PAID_PROVIDERS=chainstack,alchemy (in .env)
    # - QuickNode: FREE tier, Priority 1, 200 credits (~10 requests)
    # - Chainstack: PAID tier, Priority 2
    # - Alchemy: PAID tier, Priority 2

    # Expected:
    # - First ~10 requests: Use QuickNode (free)
    # - Remaining requests: Use Chainstack/Alchemy (paid spillover)

    print("\n" + "=" * 70)
    print("SCENARIO 2: 1 Free Provider + 2 Paid Providers")
    print("=" * 70)

    tester = LogicChangeTest()

    print(
        "\nNeed to change config, now for secnario 2 we need 1 paid so we club 2 free to make 1 paid and 1 free single\n, so in env we pass 2 paid providers we can change this and restart the server in other terminal and press enter here"
    )

    try:
        input()
    except KeyboardInterrupt:
        print("\nTest skipped")
        return

    tester.backup_usage_data()
    tester.reset_usage_data()

    try:
        input()
    except KeyboardInterrupt:
        print("\nTest aborted")
        tester.restore_usage_data()
        return

    try:
        provider_usage = Counter()
        total_requests = 250

        print(f"\n Making {total_requests} requests...\n")

        async with aiohttp.ClientSession() as session:
            for i in range(total_requests):
                response = await tester.make_request(session, i + 1)

                bliply = response.get("bliply", {})
                selected_provider = bliply.get("selected_provider", "UNKNOWN")
                latency = bliply.get("latency_ms", 0)

                provider_usage[selected_provider] += 1

                if (i + 1) in [1, 10, 20, 50, 100, 150, 200, 250]:
                    usage = tester.get_current_usage()
                    print(
                        f"#{i+1:3d}: {selected_provider:10s} ({latency:5.0f}ms) | "
                        f"QuickNode={usage.get('QuickNode', 0):3d}, "
                        f"Chainstack={usage.get('Chainstack', 0):3d}, "
                        f"Alchemy={usage.get('Alchemy', 0):3d}"
                    )

                await asyncio.sleep(0.5)

        print(f"\n Final Results:")
        for provider, count in provider_usage.most_common():
            print(f"   {provider}: {count} requests")

        free_count = provider_usage.get("QuickNode", 0)
        paid_count = provider_usage.get("Alchemy", 0) + provider_usage.get(
            "Chainstack", 0
        )

        print(f"\n Analysis:")
        print(f"   Free tier (QuickNode): {free_count} requests")
        print(f"   Paid tier (Chainstack+Alchemy): {paid_count} requests")

        assert free_count >= 8, f"Expected ~10 free requests, got {free_count}"
        assert paid_count >= 230, f"Expected ~240 paid requests, got {paid_count}"

        print(f"\n TEST PASSED")

    finally:
        tester.restore_usage_data()


async def main():

    try:
        await test_scenario_1_two_free_one_paid()
        await test_scenario_2_one_free_one_paid()

        print("\n" + "=" * 70)
        print(" ALL TESTS PASSED!")

    except AssertionError as e:
        print(f"\n TEST FAILED: {e}\n")
        raise
    except KeyboardInterrupt:
        print("\n\n  Tests cancelled\n")
    except Exception as e:
        print(f"\n ERROR: {e}\n")
        raise


if __name__ == "__main__":
    asyncio.run(main())
