import asyncio, asyncssh, time

ROUTER = {"host": "192.168.1.103", "user": "root", "password": "root"}
EDGE = {"host": "192.168.1.111", "user": "root", "password": "root"}

async def main():
    print("=== Reconfigurar Tube-AHM y reboot completo ===\n")
    
    # Step 1: Set Tube-AHM config and reboot
    print("Paso 1: Configurar Tube-AHM (ch=12, bw=8, mode=sta) y reboot...")
    async with asyncssh.connect(
        ROUTER["host"], 22, username="root", password="root", known_hosts=None
    ) as conn:
        cmds = [
            # Clean up ALL extra interfaces
            "uci delete wireless.meshap_radio0 2>/dev/null; echo ok",
            "uci delete wireless.sta_radio0 2>/dev/null; echo ok",
            # Radio config - ch=12 to match Edge AP, bw=8 (factory BCF value)
            "uci set wireless.radio0.channel='12'",
            "uci set wireless.radio0.s1g_chanbw='8'",
            "uci set wireless.radio0.country='US'",
            "uci set wireless.radio0.disabled='0'",
            # STA mode
            "uci set wireless.default_radio0.mode='sta'",
            "uci set wireless.default_radio0.ssid='UNAL-HaLow-Tesis'",
            "uci set wireless.default_radio0.encryption='sae'",
            "uci set wireless.default_radio0.key='banano2026'",
            "uci set wireless.default_radio0.device='radio0'",
            "uci set wireless.default_radio0.network='ahwlan'",
            "uci set wireless.default_radio0.wds='1'",
            # Remove ALL mesh leftovers
            "uci delete wireless.default_radio0.mesh_id 2>/dev/null; echo ok",
            "uci delete wireless.default_radio0.ifname 2>/dev/null; echo ok",
            "uci delete wireless.default_radio0.beacon_int 2>/dev/null; echo ok",
            # Commit
            "uci commit wireless",
            "uci commit system",
        ]
        for cmd in cmds:
            r = await conn.run(cmd, timeout=15)
            print(f"  {cmd}")
        
        # Show final config
        r = await conn.run("cat /etc/config/wireless", timeout=10)
        print(f"\n  Config guardada:\n{r.stdout.strip()}")
        
        # Reboot
        print("\n  Reiniciando Tube-AHM...")
        try:
            await conn.run("reboot", timeout=5)
        except:
            pass
    
    # Wait for reboot
    print("  Esperando 60s para reboot completo...")
    await asyncio.sleep(60)
    
    # Wait for SSH to come back
    print("  Intentando reconectar SSH...")
    for attempt in range(10):
        try:
            async with asyncssh.connect(
                ROUTER["host"], 22, username="root", password="root",
                known_hosts=None
            ) as conn:
                r = await conn.run("uptime", timeout=10)
                print(f"  ✅ Tube-AHM online: {r.stdout.strip()}")
                break
        except Exception:
            print(f"  Intento {attempt+1}/10 - esperando 10s...")
            await asyncio.sleep(10)
    else:
        print("  ❌ No se pudo reconectar al Tube-AHM")
        return
    
    # Wait for wifi to stabilize after boot
    print("\n  Esperando 30s adicionales para estabilización wifi...")
    await asyncio.sleep(30)
    
    # Step 2: Check link status
    print("\n=== Verificación post-reboot ===\n")
    
    print("--- Tube-AHM STA ---")
    async with asyncssh.connect(
        ROUTER["host"], 22, username="root", password="root", known_hosts=None
    ) as conn:
        for cmd in [
            "iwinfo wlan0 info",
            "cat /sys/class/net/wlan0/operstate",
            "iw dev wlan0 link",
            "logread | grep -iE 'radio0|wpa_supplicant|morse|regulatory|range|channel|assoc|scan' | tail -20",
        ]:
            r = await conn.run(cmd, timeout=15)
            print(f"\n  [{cmd}]")
            print(f"  {r.stdout.strip()}")
    
    print("\n--- Edge AP ---")
    async with asyncssh.connect(
        EDGE["host"], 22, username="root", password="root", known_hosts=None
    ) as conn:
        for cmd in [
            "iwinfo wlan0 info",
            "iwinfo wlan0 assoclist",
        ]:
            r = await conn.run(cmd, timeout=15)
            print(f"\n  [{cmd}]")
            print(f"  {r.stdout.strip() if r.stdout.strip() else '(vacío)'}")

asyncio.run(main())
