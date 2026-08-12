#!/usr/bin/env python3
"""
Diagnose and try to improve HaLow link quality.
The Edge→Tube direction has -78 dBm / SNR 4, causing 40-60% packet loss.
"""
import asyncio
import asyncssh


async def ssh_run(host, cmd, timeout=30):
    async with asyncssh.connect(
        host, port=22, username="root", password="root",
        known_hosts=None, login_timeout=10
    ) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()


async def main():
    EDGE = "192.168.1.111"
    TUBE = "192.168.1.103"

    print("=" * 60)
    print("  HALOW LINK QUALITY DIAGNOSIS")
    print("=" * 60)

    # 1. Current station dump from both sides
    print("\n[1] Edge station dump (detailed)...")
    out = await ssh_run(EDGE, "iw dev wlan0 station dump 2>/dev/null")
    print(out)

    print("\n[2] Tube station dump (Edge as seen by AP)...")
    out = await ssh_run(TUBE, "iw dev wlan0 station dump 2>/dev/null")
    print(out)

    # 3. Edge TX power details
    print("\n[3] Edge TX power and morse_cli stats...")
    out = await ssh_run(EDGE, 
        "morse_cli -i wlan0 channel; echo ===; "
        "morse_cli -i wlan0 stats 2>/dev/null; echo ===; "
        "iw dev wlan0 get power_save 2>/dev/null; echo ===; "
        "cat /sys/kernel/debug/ieee80211/phy0/morse/survey 2>/dev/null || echo nosurvey"
    )
    print(out)

    # 4. Try to boost Edge TX power to max
    print("\n[4] Boosting Edge TX power to max (22 dBm = 2200 mbm)...")
    out = await ssh_run(EDGE,
        "iw dev wlan0 set txpower fixed 2200 2>/dev/null; echo RC=$?; "
        "morse_cli -i wlan0 set_txpower 2200 2>/dev/null; echo RC=$?; "
        "iwinfo wlan0 info 2>/dev/null | grep 'Tx-Power'"
    )
    print(f"    {out}")

    # 5. Disable power save on Edge (can cause latency/loss)
    print("\n[5] Disabling power save on Edge wlan0...")
    out = await ssh_run(EDGE,
        "iw dev wlan0 set power_save off 2>/dev/null; echo RC=$?; "
        "iw dev wlan0 get power_save 2>/dev/null"
    )
    print(f"    {out}")

    # 6. Check Edge antenna and driver info
    print("\n[6] Edge wlan0 driver/phy info...")
    out = await ssh_run(EDGE,
        "iw phy phy0 info 2>/dev/null | grep -E 'max TX|Capabilities|Band' | head -10; echo ===; "
        "dmesg | grep -i 'morse\|mf08\|power\|antenna' | tail -10"
    )
    print(out)

    # 7. Tube power settings
    print("\n[7] Tube TX power...")
    out = await ssh_run(TUBE,
        "iwinfo wlan0 info 2>/dev/null | grep 'Tx-Power'; echo ===; "
        "morse_cli -i wlan0 channel 2>/dev/null"
    )
    print(f"    {out}")

    # 8. Re-test ping after optimizations
    print("\n[8] Re-testing Edge → Tube ping via HaLow after optimizations...")
    out = await ssh_run(EDGE,
        "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196; "
        "ping -c 10 -W 5 -i 1 192.168.1.103 2>&1",
        timeout=60
    )
    for line in out.split('\n'):
        if 'transmitted' in line or 'rtt' in line or 'bytes from' in line:
            print(f"    {line.strip()}")

    # 9. Check signal after pings (link should be warmed up)
    print("\n[9] Updated signal levels after activity...")
    out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
    print(f"    Edge: {out}")
    out = await ssh_run(TUBE, "iwinfo wlan0 assoclist 2>/dev/null")
    print(f"    Tube assoclist: {out}")

    print("\n" + "=" * 60)
    print("  DIAGNOSIS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
