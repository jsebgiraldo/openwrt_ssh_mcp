import asyncio, asyncssh

ROUTER = {"host": "192.168.1.103", "user": "root", "password": "root"}
EDGE = {"host": "192.168.1.111", "user": "root", "password": "root"}

async def main():
    # First, confirm Edge AP channel
    print("=== Verificar canal del Edge AP ===")
    async with asyncssh.connect(EDGE["host"], 22, username="root", password="root", known_hosts=None) as conn:
        r = await conn.run("iwinfo wlan0 info", timeout=10)
        print(r.stdout.strip())
        r = await conn.run("uci show wireless.radio0.channel; uci show wireless.radio0.s1g_chanbw", timeout=10)
        print(f"UCI: {r.stdout.strip()}")

    # Try different configs on the Tube-AHM
    # The AP is on ch12, HT20. For S1G, HT20 = 4 MHz BW.
    # Try matching with explicit ch=12 and different BWs
    configs = [
        # ch=12 (match AP), different BWs
        ("12", "4"),   # exact match: ch12, 4MHz (HT20)
        ("12", "2"),   # ch12, 2MHz
        ("12", "1"),   # ch12, 1MHz
        ("12", "8"),   # ch12, 8MHz - STA should negotiate down
        ("auto", "4"), # auto channel, 4MHz (match HT20)
        ("auto", "2"), # auto channel, 2MHz
        ("auto", "1"), # auto channel, 1MHz
    ]

    for ch, bw in configs:
        print(f"\n{'='*50}")
        print(f"  Probando Tube-AHM STA con ch={ch} bw={bw}")
        print("=" * 50)

        async with asyncssh.connect(ROUTER["host"], 22, username="root", password="root", known_hosts=None) as conn:
            cmds = [
                f"uci set wireless.radio0.channel='{ch}'",
                f"uci set wireless.radio0.s1g_chanbw='{bw}'",
                "uci commit wireless",
                "wifi down; sleep 2; wifi up",
            ]
            for cmd in cmds:
                await conn.run(cmd, timeout=20)

        # Wait for STA to scan and associate
        print("  Esperando 20s...")
        await asyncio.sleep(20)

        # Check
        async with asyncssh.connect(ROUTER["host"], 22, username="root", password="root", known_hosts=None) as conn:
            r = await conn.run("cat /sys/class/net/wlan0/operstate 2>/dev/null", timeout=10)
            operstate = r.stdout.strip()

            r = await conn.run("iwinfo wlan0 info 2>/dev/null", timeout=10)
            info = r.stdout.strip()

            r = await conn.run("iw dev wlan0 link 2>/dev/null", timeout=10)
            link = r.stdout.strip()

            # Check for regulatory errors
            r = await conn.run("logread | grep -E 'regulatory|Couldn' | tail -3", timeout=10)
            reg = r.stdout.strip()

            r = await conn.run("logread | grep -E 'wpa_supplicant|CTRL-EVENT' | tail -5", timeout=10)
            wpa = r.stdout.strip()

            print(f"  operstate: {operstate}")
            if "Channel:" in info:
                for line in info.split('\n'):
                    if any(k in line for k in ['Channel:', 'Mode:', 'ESSID:', 'Signal:']):
                        print(f"  {line.strip()}")
            print(f"  iw link: {link[:100]}")
            if reg:
                print(f"  reg errors: {reg[:200]}")
            if wpa:
                print(f"  wpa_supplicant: ")
                for line in wpa.split('\n')[-3:]:
                    print(f"    {line.strip()}")

            if operstate == "up" or "Connected" in link:
                print(f"\n  ✅ ¡CONECTADO! ch={ch} bw={bw}")
                # Full info
                print(f"\n{info}")

                # Check Edge assoclist
                async with asyncssh.connect(EDGE["host"], 22, username="root", password="root", known_hosts=None) as econn:
                    r2 = await econn.run("iwinfo wlan0 assoclist", timeout=10)
                    print(f"\nEdge assoclist: {r2.stdout.strip()}")
                return

            print(f"  ❌ No conectado")

    print("\n❌ Ninguna configuración funcionó.")
    # Get more debug info
    async with asyncssh.connect(ROUTER["host"], 22, username="root", password="root", known_hosts=None) as conn:
        r = await conn.run("logread | tail -40", timeout=10)
        print(f"\nÚltimas líneas del log:")
        print(r.stdout.strip())

asyncio.run(main())
