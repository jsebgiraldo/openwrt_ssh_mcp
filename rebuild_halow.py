#!/usr/bin/env python3
"""
Reconstruir red HaLow desde cero en ambos dispositivos.
Canal 14, 2 MHz BW (probado que funciona), WPA3-SAE.
"""
import asyncio, asyncssh, time

TUBE = {"host": "192.168.1.103", "username": "root", "password": "root"}
EDGE = {"host": "192.168.1.111", "username": "root", "password": "root"}

SSID = "UNAL-HaLow-Tesis"
KEY = "banano2026"
CHANNEL = "14"
S1G_CHANBW = "2"  # 2 MHz — probado funcional, SNR mejor que 8 MHz

async def run(conn, cmd, label=None, timeout=10):
    if label:
        print(f"  [{label}]", flush=True)
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=timeout), timeout=timeout+5)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        result = out or err or "(empty)"
        if label:
            for line in result.split('\n')[:25]:
                print(f"    {line}", flush=True)
        return result
    except Exception as e:
        if label:
            print(f"    ERROR: {e}", flush=True)
        return f"ERROR: {e}"

async def connect(dev):
    return await asyncio.wait_for(
        asyncssh.connect(dev["host"], username=dev["username"],
                       password=dev["password"], known_hosts=None, login_timeout=15),
        timeout=20)

async def main():
    # ═══════════════════════════════════
    #  PASO 1: Configurar AP (Tube-AHM)
    # ═══════════════════════════════════
    print("="*60, flush=True)
    print("  PASO 1: Configurar AP (Tube-AHM)", flush=True)
    print("="*60, flush=True)
    
    conn = await connect(TUBE)
    async with conn:
        # Limpiar config wireless existente
        await run(conn, "wifi down 2>/dev/null; sleep 1", "wifi down")
        
        # Verificar que NO hay wifi-iface
        await run(conn, "uci show wireless", "Config actual")
        
        # Crear wifi-iface si no existe
        iface_check = await run(conn, "uci get wireless.wifinet0 2>/dev/null || echo MISSING")
        if "MISSING" in iface_check:
            print("\n  ⚠ wifi-iface FALTA en Tube — creándolo...", flush=True)
            cmds = [
                "uci set wireless.wifinet0=wifi-iface",
                f"uci set wireless.wifinet0.device='radio0'",
                f"uci set wireless.wifinet0.mode='ap'",
                f"uci set wireless.wifinet0.ssid='{SSID}'",
                f"uci set wireless.wifinet0.encryption='sae'",
                f"uci set wireless.wifinet0.sae_pwe='1'",
                f"uci set wireless.wifinet0.key='{KEY}'",
                f"uci set wireless.wifinet0.network='ahwlan'",
                f"uci set wireless.wifinet0.wds='1'",
            ]
            for c in cmds:
                await run(conn, c)
        else:
            print("  wifi-iface existe, actualizando...", flush=True)
            cmds = [
                f"uci set wireless.wifinet0.ssid='{SSID}'",
                f"uci set wireless.wifinet0.encryption='sae'",
                f"uci set wireless.wifinet0.sae_pwe='1'",
                f"uci set wireless.wifinet0.key='{KEY}'",
                f"uci set wireless.wifinet0.network='ahwlan'",
                f"uci set wireless.wifinet0.wds='1'",
            ]
            for c in cmds:
                await run(conn, c)
        
        # Configurar radio
        radio_cmds = [
            f"uci set wireless.radio0.channel='{CHANNEL}'",
            f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
            "uci set wireless.radio0.disabled='0'",
            "uci set wireless.radio0.country='US'",
        ]
        for c in radio_cmds:
            await run(conn, c)
        
        # Commit y mostrar
        await run(conn, "uci commit wireless", "commit")
        await run(conn, "cat /etc/config/wireless", "Config final AP")
        
        # Aplicar
        print("\n  Reiniciando wifi en Tube...", flush=True)
        await run(conn, "wifi up", "wifi up", timeout=20)
    
    # Esperar a que el AP arranque
    print("  Esperando 12s para que el AP inicialice...", flush=True)
    await asyncio.sleep(12)
    
    # Verificar AP
    conn = await connect(TUBE)
    async with conn:
        ap_info = await run(conn, "iwinfo wlan0 info 2>/dev/null", "AP iwinfo")
        if "ESSID" not in ap_info:
            print("  ⚠ AP aún no tiene wlan0. Esperando 10s más...", flush=True)
            await asyncio.sleep(10)
            ap_info = await run(conn, "iwinfo wlan0 info 2>/dev/null", "AP iwinfo retry")
        
        await run(conn, "morse_cli -i wlan0 channel 2>/dev/null", "AP morse_cli channel")
        await run(conn, "brctl show 2>/dev/null", "AP bridges")
        
        if "ESSID" not in ap_info:
            print("\n  ✗ AP NO arrancó. Revisando logs...", flush=True)
            await run(conn, "logread | grep -iE 'wlan|morse|hostapd|error' | tail -20", "AP logread")
            await run(conn, "dmesg | grep -iE 'morse|error|fail' | tail -15", "AP dmesg")
            return
        
        print("\n  ✓ AP activo!", flush=True)
    
    # ═══════════════════════════════════
    #  PASO 2: Configurar STA (Edge)
    # ═══════════════════════════════════
    print(f"\n{'='*60}", flush=True)
    print("  PASO 2: Configurar STA (Edge Gateway)", flush=True)
    print("="*60, flush=True)
    
    conn = await connect(EDGE)
    async with conn:
        await run(conn, "wifi down 2>/dev/null; sleep 1", "wifi down")
        
        # Configurar radio
        radio_cmds = [
            f"uci set wireless.radio0.channel='{CHANNEL}'",
            f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
            "uci set wireless.radio0.txpower='21'",
            "uci set wireless.radio0.disabled='0'",
            "uci set wireless.radio0.country='US'",
        ]
        for c in radio_cmds:
            await run(conn, c)
        
        # Configurar STA interface
        sta_cmds = [
            f"uci set wireless.wifinet0.ssid='{SSID}'",
            f"uci set wireless.wifinet0.encryption='sae'",
            f"uci set wireless.wifinet0.sae_pwe='1'",
            f"uci set wireless.wifinet0.key='{KEY}'",
            "uci set wireless.wifinet0.network='wwan'",
        ]
        for c in sta_cmds:
            await run(conn, c)
        
        # Asegurar network.wwan con IP estática
        net_cmds = [
            "uci set network.wwan=interface",
            "uci set network.wwan.proto='static'",
            "uci set network.wwan.ipaddr='192.168.1.196'",
            "uci set network.wwan.netmask='255.255.255.0'",
            "uci set network.wwan.gateway='192.168.1.1'",
            "uci set network.wwan.dns='192.168.1.1'",
            "uci set network.wwan.metric='600'",
            "uci commit network",
        ]
        for c in net_cmds:
            await run(conn, c)
        
        await run(conn, "uci commit wireless", "commit")
        await run(conn, "cat /etc/config/wireless", "Config final STA")
        
        # Aplicar
        print("\n  Reiniciando wifi en Edge...", flush=True)
        await run(conn, "wifi up", "wifi up", timeout=20)
    
    # ═══════════════════════════════════
    #  PASO 3: Esperar asociación
    # ═══════════════════════════════════
    print(f"\n{'='*60}", flush=True)
    print("  PASO 3: Esperando asociación STA→AP...", flush=True)
    print("="*60, flush=True)
    
    await asyncio.sleep(10)
    
    for attempt in range(20):  # hasta 100s
        await asyncio.sleep(5)
        elapsed = (attempt + 1) * 5 + 10
        try:
            conn = await connect(EDGE)
            async with conn:
                result = await run(conn, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Bit Rate|Channel'")
                if SSID in result and "Signal" in result:
                    print(f"  ✓ ASOCIADO después de {elapsed}s!", flush=True)
                    print(f"    {result}", flush=True)
                    break
                print(f"  [{elapsed}s] Aún no asociado...", flush=True)
        except Exception as e:
            print(f"  [{elapsed}s] Error: {e}", flush=True)
    else:
        print("  ✗ Timeout! Revisando logs...", flush=True)
        conn = await connect(EDGE)
        async with conn:
            await run(conn, "logread | grep -iE 'wlan|morse|wpa_supplicant|assoc|auth|sae' | tail -25", "Edge logread")
            await run(conn, "iwinfo wlan0 info 2>/dev/null", "Edge iwinfo")
        return
    
    # ═══════════════════════════════════
    #  PASO 4: Verificación completa
    # ═══════════════════════════════════
    print(f"\n{'='*60}", flush=True)
    print("  PASO 4: Verificación completa", flush=True)
    print("="*60, flush=True)
    
    # --- AP ---
    print("\n  --- Tube-AHM (AP) ---", flush=True)
    conn = await connect(TUBE)
    async with conn:
        await run(conn, "iwinfo wlan0 info", "AP iwinfo")
        await run(conn, "iwinfo wlan0 assoclist", "AP assoclist")
        await run(conn, "morse_cli -i wlan0 channel", "AP morse_cli channel")
        await run(conn, "brctl show", "AP bridges")
        await run(conn, "ping -c 5 -W 3 192.168.1.196", "AP→Edge ping HaLow", timeout=25)
    
    # --- STA ---
    print("\n  --- Edge Gateway (STA) ---", flush=True)
    conn = await connect(EDGE)
    async with conn:
        await run(conn, "iwinfo wlan0 info", "STA iwinfo")
        await run(conn, "iwinfo wlan0 assoclist", "STA assoclist")
        await run(conn, "morse_cli -i wlan0 channel", "STA morse_cli channel")
        await run(conn, "ip addr show wlan0 | grep inet", "STA wlan0 IP")
        await run(conn, "ip route show", "STA routes")
        # Ping VIA HALOW (force wlan0)
        await run(conn, "ping -c 5 -W 3 -I wlan0 192.168.1.103", "STA→Tube ping via HaLow", timeout=25)
    
    print(f"\n{'='*60}", flush=True)
    print("  CONFIGURACIÓN HALOW COMPLETA", flush=True)
    print("="*60, flush=True)

asyncio.run(main())
