import asyncio, asyncssh

ROUTER = {"host": "192.168.1.103", "user": "root", "password": "root"}
EDGE = {"host": "192.168.1.111", "user": "root", "password": "root"}

async def main():
    print("=== Debug profundo del Tube-AHM STA ===\n")
    
    async with asyncssh.connect(
        ROUTER["host"], 22, username="root", password="root", known_hosts=None
    ) as conn:
        cmds = [
            # Check wpa_supplicant config
            "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || find /var/run -name '*wpa*' -o -name '*supplicant*' 2>/dev/null",
            # Check wpa_cli with different control paths
            "wpa_cli -p /var/run/wpa_supplicant -i wlan0 status 2>&1",
            "wpa_cli -p /var/run/wpa_supplicant_s1g -i wlan0 status 2>&1",
            "find /var/run -name '*s1g*' -o -name '*wpa*' -o -name '*supplicant*' 2>/dev/null",
            # Check what wpa_supplicant process uses
            "ps w | grep wpa",
            # Check network config (ahwlan bridge)
            "uci show network.ahwlan",
            "brctl show",
            "ip addr show br-ahwlan",
            "ip route show",
            # Check logread more detailed
            "logread | grep -iE 'wpa_supplicant|scan|assoc|auth|reject|fail|error.*wlan|morse.*error' | tail -20",
            # Check morse driver status
            "dmesg | tail -20",
        ]
        for cmd in cmds:
            r = await conn.run(cmd, timeout=15)
            print(f"--- {cmd} ---")
            out = r.stdout.strip()
            err = r.stderr.strip()
            if out: print(out)
            if err: print(f"STDERR: {err}")
            if not out and not err: print("(vacío)")
            print()

    # Also check if Edge AP is really broadcasting
    print("\n=== Edge AP scan test ===")
    async with asyncssh.connect(
        EDGE["host"], 22, username="root", password="root", known_hosts=None
    ) as conn:
        r = await conn.run("iwinfo wlan0 info", timeout=10)
        print(r.stdout.strip())
        # Check hostapd
        r = await conn.run("ps w | grep hostapd", timeout=10)
        print(f"\nhostapd process: {r.stdout.strip()}")
        r = await conn.run("find /var/run -name '*hostapd*' 2>/dev/null", timeout=10)
        print(f"hostapd files: {r.stdout.strip()}")
        # Self-scan (check if AP can see itself)
        r = await conn.run("logread | grep -i 'hostapd\\|AP-ENABLED\\|DPP' | tail -10", timeout=10)
        print(f"\nhostapd logs:\n{r.stdout.strip()}")

asyncio.run(main())
