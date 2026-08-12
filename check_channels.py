#!/usr/bin/env python3
"""Check available US channels at different bandwidths to improve link quality."""
import asyncio
import asyncssh

async def main():
    async with asyncssh.connect(
        "192.168.1.111", port=22, username="root", password="root",
        known_hosts=None, login_timeout=10
    ) as c:
        # Read channels.csv to find US channels at different BWs
        r = await c.run(
            "grep '^US,' /usr/share/morse/channels.csv 2>/dev/null || "
            "grep '^US,' /etc/morse/channels.csv 2>/dev/null || "
            "find / -name channels.csv -exec grep '^US,' {} \\; 2>/dev/null | head -50",
            timeout=20
        )
        print("US channels available:")
        print("Country,BW,Chan,OpClass,Freq,MaxTxPower...\n")
        lines = r.stdout.strip().split('\n')
        # Group by BW
        bw_groups = {}
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 6:
                bw = parts[1].strip()
                if bw not in bw_groups:
                    bw_groups[bw] = []
                bw_groups[bw].append(line.strip())
        
        for bw in sorted(bw_groups.keys()):
            print(f"\n=== {bw} MHz Bandwidth ===")
            for line in bw_groups[bw]:
                print(f"  {line}")
        
        # Also check Tube's available channels
        print("\n\n--- Tube BCF capabilities ---")
    
    async with asyncssh.connect(
        "192.168.1.103", port=22, username="root", password="root",
        known_hosts=None, login_timeout=10
    ) as c:
        r = await c.run(
            "grep '^US,' /usr/share/morse/channels.csv 2>/dev/null || "
            "grep '^US,' /etc/morse/channels.csv 2>/dev/null | head -50",
            timeout=20
        )
        lines = r.stdout.strip().split('\n')
        bw_groups = {}
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 6:
                bw = parts[1].strip()
                if bw not in bw_groups:
                    bw_groups[bw] = []
                bw_groups[bw].append(line.strip())
        
        for bw in sorted(bw_groups.keys()):
            print(f"\n=== {bw} MHz Bandwidth (Tube) ===")
            for line in bw_groups[bw]:
                print(f"  {line}")

asyncio.run(main())
