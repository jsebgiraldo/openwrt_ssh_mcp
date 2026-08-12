import asyncio, asyncssh

EDGE = {"host": "192.168.1.111", "user": "root", "password": "root"}

async def try_channel(ch, bw):
    """Try a channel/bw combo on the Edge and see if AP comes up."""
    async with asyncssh.connect(
        EDGE["host"], 22, username=EDGE["user"],
        password=EDGE["password"], known_hosts=None
    ) as conn:
        # Set channel and bandwidth
        cmds = [
            f"uci set wireless.radio0.channel='{ch}'",
            f"uci set wireless.radio0.s1g_chanbw='{bw}'",
            "uci commit wireless",
            "wifi down; sleep 1; wifi up",
        ]
        for cmd in cmds:
            await conn.run(cmd, timeout=15)
        
        # Wait for AP to start
        await asyncio.sleep(12)
        
        # Check if wlan0 is up
        r = await conn.run("iwinfo wlan0 info 2>/dev/null", timeout=10)
        info = r.stdout.strip()
        
        # Check logread for errors
        r2 = await conn.run("logread | grep 'Couldn.t find regulatory' | tail -1", timeout=10)
        reg_err = r2.stdout.strip()
        
        if "Master" in info or "AP" in info:
            return True, info
        else:
            return False, reg_err or "(wlan0 not up)"

async def main():
    print("=== Buscando canal/BW válido para Edge (bcf_mf15457.bin) en modo AP ===\n")
    
    # Try combinations: channel auto, then specific channels at different BWs
    combos = [
        ("auto", "8"),
        ("auto", "4"),
        ("auto", "2"),
        ("auto", "1"),
        # 8 MHz channels (common Morse Micro US): 10, 26, 42
        ("10", "8"),
        ("26", "8"),
        ("42", "8"),
        # 4 MHz channels: 6, 14, 22, 30, 38, 46
        ("6", "4"),
        ("14", "4"),
        ("22", "4"),
        ("30", "4"),
        ("38", "4"),
        # 2 MHz channels:
        ("3", "2"),
        ("7", "2"),
        ("11", "2"),
        ("15", "2"),
        ("35", "2"),
        # 1 MHz channels:
        ("5", "1"),
        ("15", "1"),
        ("35", "1"),
    ]
    
    found = []
    for ch, bw in combos:
        print(f"  Probando ch={ch} bw={bw}...", end=" ", flush=True)
        try:
            ok, info = await try_channel(ch, bw)
            if ok:
                print(f"OK!")
                # Extract channel/HT info
                for line in info.split('\n'):
                    if 'Channel:' in line or 'HT Mode' in line:
                        print(f"    {line.strip()}")
                found.append((ch, bw, info))
                # Found one! Stop searching
                break
            else:
                print(f"FAIL - {info[:80]}")
        except Exception as e:
            print(f"ERROR - {e}")
    
    if found:
        ch, bw, info = found[0]
        print(f"\n✅ Configuración válida encontrada: ch={ch} bw={bw}")
        print(f"\n{info}")
    else:
        print("\n❌ No se encontró ninguna combinación válida")
        # Try listing regulatory data
        async with asyncssh.connect(
            EDGE["host"], 22, username=EDGE["user"],
            password=EDGE["password"], known_hosts=None
        ) as conn:
            r = await conn.run("ls /lib/firmware/morse/ 2>/dev/null", timeout=10)
            print(f"\nFirmware files: {r.stdout.strip()}")
            r = await conn.run("cat /etc/morse/reg_rules* 2>/dev/null || find / -name 'reg*' -path '*morse*' 2>/dev/null | head -10", timeout=10)
            print(f"Reg data: {r.stdout.strip()}")

asyncio.run(main())
