#!/usr/bin/env python3
"""Run only Tests 4 (Stability) and 5 (Wireless Stats) with the same timestamp as existing data."""
import asyncio
import sys
import os

# Patch the TIMESTAMP to match existing data files before importing
# Find the timestamp from existing TCP file
thesis_data_dir = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_data")
# Find the LATEST timestamp from existing TCP files
timestamps = []
for f in os.listdir(thesis_data_dir):
    if f.startswith("tcp_throughput_") and f.endswith(".json"):
        timestamps.append(f.replace("tcp_throughput_", "").replace(".json", ""))
if not timestamps:
    print("ERROR: No existing tcp_throughput file found")
    sys.exit(1)
ts = sorted(timestamps)[-1]  # Use the latest

print(f"Using existing timestamp: {ts}")

# Import and patch
import thesis_tests
thesis_tests.TIMESTAMP = ts

async def main():
    print("=" * 60)
    print(f"  TESTS 4+5 ONLY (using timestamp {ts})")
    print("=" * 60)

    # Test 4: Stability
    stability = await thesis_tests.test_stability()

    # Test 5: Wireless stats
    wireless = await thesis_tests.test_wireless_stats()

    # Load existing all_tests file if it exists, otherwise create new
    import json
    all_file = os.path.join(thesis_data_dir, f"all_tests_{ts}.json")
    if os.path.exists(all_file):
        with open(all_file) as f:
            all_results = json.load(f)
    else:
        all_results = {}

    all_results["stability"] = stability
    all_results["wireless_stats"] = wireless

    with open(all_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  -> Updated: {all_file}")

    print("\n" + "=" * 60)
    print("  TESTS 4+5 COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
