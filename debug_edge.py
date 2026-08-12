import asyncio, asyncssh

async def debug_edge():
    h = "192.168.1.111"
    print(f"=== EDGE ({h}) - Debug por qué wlan0 no sube ===\n")
    try:
        async with asyncssh.connect(h, 22, username="root", password="root", known_hosts=None) as conn:
            cmds = [
                "ip link show | grep -E 'wlan|mesh|morse|phy'",
                "ls /sys/class/net/",
                "iw dev",
                "iw phy",
                "dmesg | grep -iE 'morse|wlan|error|fail|firmware' | tail -30",
                "logread | grep -iE 'radio0|morse|wlan|hostapd|wireless|netifd' | tail -30",
                "ps | grep -E 'hostapd|wpa_supplicant|netifd'",
                "wifi status",
                "cat /etc/config/wireless",
            ]
            for cmd in cmds:
                r = await conn.run(cmd, timeout=15)
                out = r.stdout.strip()
                err = r.stderr.strip()
                print(f"--- {cmd} ---")
                if out:
                    print(out)
                if err:
                    print(f"  STDERR: {err}")
                if not out and not err:
                    print("(vacío)")
                print()
    except Exception as e:
        print(f"ERROR: {e}")

asyncio.run(debug_edge())
