#!/usr/bin/env python3
"""Check available US channels at different bandwidths."""
import asyncio
import asyncssh

async def ssh_run(host, cmd, timeout=15):
    async with asyncssh.connect(
        host, port=22, username="root", password="root",
        known_hosts=None, login_timeout=10
    ) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()

async def main():
    EDGE = "192.168.1.111"
    TUBE = "192.168.1.103"

    for name, host in [("Edge", EDGE), ("Tube", TUBE)]:
        print(f"\n{'='*50}")
        print(f"  {name} ({host}) - US Channels")
        print(f"{'='*50}")
        try:
            out = await ssh_run(host,
                "cat /usr/share/morse/channels.csv | head -1; "
                "cat /usr/share/morse/channels.csv | grep '^US,'",
                timeout=10
            )
            print(out)
        except Exception as e:
            print(f"  ERROR: {e}")
            try:
                out = await ssh_run(host, "find /usr/share /etc -name channels.csv 2>/dev/null", timeout=10)
                print(f"  Found at: {out}")
            except:
                pass

asyncio.run(main())
