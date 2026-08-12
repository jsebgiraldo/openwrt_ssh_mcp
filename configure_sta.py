import asyncio, asyncssh

ROUTER = {"host": "192.168.1.103", "user": "root", "password": "root"}
EDGE = {"host": "192.168.1.111", "user": "root", "password": "root"}

SSID = "UNAL-HaLow-Tesis"
KEY = "banano2026"

async def main():
    print("=== Configurar Tube-AHM como STA bridge ===\n")
    
    # Step 1: Configure Tube-AHM as STA
    print("Paso 1: Configurar Tube-AHM como STA...")
    async with asyncssh.connect(
        ROUTER["host"], 22, username=ROUTER["user"],
        password=ROUTER["password"], known_hosts=None
    ) as conn:
        cmds = [
            # Remove extra interfaces
            "uci delete wireless.meshap_radio0 2>/dev/null; echo ok",
            # Radio config - auto channel, bw=8
            "uci set wireless.radio0.channel='auto'",
            "uci set wireless.radio0.s1g_chanbw='8'",
            "uci set wireless.radio0.country='US'",
            "uci set wireless.radio0.disabled='0'",
            # STA interface
            "uci set wireless.default_radio0.mode='sta'",
            f"uci set wireless.default_radio0.ssid='{SSID}'",
            "uci set wireless.default_radio0.encryption='sae'",
            f"uci set wireless.default_radio0.key='{KEY}'",
            "uci set wireless.default_radio0.device='radio0'",
            "uci set wireless.default_radio0.network='ahwlan'",
            "uci set wireless.default_radio0.wds='1'",
            # Remove mesh-specific settings
            "uci delete wireless.default_radio0.mesh_id 2>/dev/null; echo ok",
            "uci delete wireless.default_radio0.ifname 2>/dev/null; echo ok",
            "uci delete wireless.default_radio0.beacon_int 2>/dev/null; echo ok",
            # Commit
            "uci commit wireless",
            # Restart wifi
            "wifi down; sleep 2; wifi up",
        ]
        for cmd in cmds:
            r = await conn.run(cmd, timeout=20)
            print(f"  {cmd}: {r.stdout.strip()}" if r.stdout.strip() else f"  {cmd}")
    
    print("\n  Esperando 25s para asociación STA...")
    await asyncio.sleep(25)
    
    # Step 2: Verify both sides
    print("\n=== Verificación ===\n")
    
    # Check Edge AP
    print("--- Edge AP (192.168.1.111) ---")
    async with asyncssh.connect(
        EDGE["host"], 22, username=EDGE["user"],
        password=EDGE["password"], known_hosts=None
    ) as conn:
        r = await conn.run("iwinfo wlan0 info", timeout=10)
        print(r.stdout.strip())
        print()
        r = await conn.run("iwinfo wlan0 assoclist", timeout=10)
        assoc = r.stdout.strip()
        print(f"Estaciones conectadas: {assoc if assoc else '(ninguna)'}")
    
    print()
    
    # Check Tube-AHM STA
    print("--- Tube-AHM STA (192.168.1.103) ---")
    async with asyncssh.connect(
        ROUTER["host"], 22, username=ROUTER["user"],
        password=ROUTER["password"], known_hosts=None
    ) as conn:
        r = await conn.run("iwinfo wlan0 info", timeout=10)
        info = r.stdout.strip()
        print(info)
        print()
        
        r = await conn.run("cat /sys/class/net/wlan0/operstate", timeout=10)
        operstate = r.stdout.strip()
        print(f"operstate: {operstate}")
        
        r = await conn.run("iw dev wlan0 link", timeout=10)
        link = r.stdout.strip()
        print(f"iw link: {link}")
        
        r = await conn.run("logread | grep -iE 'regulatory|channel|assoc|connect|wpa_s' | tail -15", timeout=10)
        print(f"\nLogs relevantes:")
        print(r.stdout.strip())
        
        # Ping test
        print("\n--- Pings ---")
        r = await conn.run("ping -c 3 -W 3 192.168.1.111", timeout=15)
        print(f"Tube-AHM -> Edge: {r.stdout.strip()}")
        
        r = await conn.run("ping -c 3 -W 3 192.168.1.1", timeout=15)
        print(f"Tube-AHM -> WAN: {r.stdout.strip()}")
    
    if "Connected" in link or operstate == "up":
        print("\n✅ Enlace HaLow establecido!")
    else:
        print("\n⚠️  Enlace no establecido aún. Verificando scan...")
        async with asyncssh.connect(
            ROUTER["host"], 22, username=ROUTER["user"],
            password=ROUTER["password"], known_hosts=None
        ) as conn:
            # Try scanning
            r = await conn.run("iw dev wlan0 scan 2>/dev/null | grep -A5 'SSID\\|freq\\|signal'", timeout=30)
            print(f"Scan results: {r.stdout.strip() if r.stdout.strip() else '(vacío)'}")
            
            r = await conn.run("iwinfo wlan0 scan 2>/dev/null | head -30", timeout=30)
            print(f"iwinfo scan: {r.stdout.strip() if r.stdout.strip() else '(vacío)'}")

asyncio.run(main())
