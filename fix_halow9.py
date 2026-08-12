"""
fix_halow9.py - Exact replication of fix_halow5.py's working sequence
but using the native-generated config (which now has S1G params)

Key differences to test:
1. Add txpower to UCI
2. wifi up first, then kill+reconfigure
3. Same sequence as fix_halow5.py: kill → morse_cli → wait → start wpa_supplicant
"""
import asyncio, asyncssh

EDGE_IP = '192.168.1.111'
TUBE_IP = '192.168.1.103'
SSH_USER = 'root'
SSH_PASS = 'root'


async def main():
    e = await asyncio.wait_for(asyncssh.connect(EDGE_IP, username=SSH_USER, password=SSH_PASS, known_hosts=None), timeout=20)
    
    print("=" * 60)
    print("FIX HALOW 9: Replicate fix_halow5.py sequence")
    print("=" * 60)
    
    # Step 1: Set txpower in UCI
    print("\n[1] Setting UCI txpower='21'...")
    await e.run("uci set wireless.radio0.txpower='21'", timeout=5)
    await e.run("uci commit wireless", timeout=5)
    
    # Step 2: Full wifi restart to get native config with S1G params
    print("[2] wifi down + wifi up...")
    await e.run("wifi down", timeout=10)
    await asyncio.sleep(3)
    await e.run("wifi up", timeout=10)  
    await asyncio.sleep(5)  # Let it settle
    
    # Step 3: Check native-generated config  
    print("[3] Native config check:")
    r = await e.run("cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null", timeout=5)
    cfg = r.stdout.strip()
    has_s1g = 'op_class=71' in cfg
    print(f"  Has S1G params: {has_s1g}")
    if has_s1g:
        for line in cfg.split('\n'):
            if 'op_class' in line or 's1g_prim' in line:
                print(f"  ✓ {line.strip()}")
    
    print(f"\n  Full config:\n{cfg}")
    
    # Step 4: Kill wpa_supplicant_s1g (like fix_halow5.py)
    print("\n[4] Killing wpa_supplicant_s1g...")
    await e.run("killall wpa_supplicant_s1g 2>/dev/null", timeout=5)
    await asyncio.sleep(2)
    
    # Step 5: Set morse_cli channel (like fix_halow5.py)
    print("[5] Setting morse_cli channel -c 908000 -o 8 -p 2 -n 3...")
    r = await e.run("morse_cli -i wlan0 channel -c 908000 -o 8 -p 2 -n 3", timeout=10)
    print(f"  {r.stdout.strip()}")
    
    # Verify channel
    r = await e.run("morse_cli -i wlan0 channel", timeout=5)
    print(f"  {r.stdout.strip()}")
    
    # Step 6: Set TX power explicitly
    print("[6] Setting iwconfig txpower...")
    await e.run("iw dev wlan0 set txpower fixed 2100 2>/dev/null", timeout=5)  # 21 dBm = 2100 hundredths
    
    # Step 7: Wait (like fix_halow5.py)
    print("[7] Waiting 3s...")
    await asyncio.sleep(3)
    
    # Step 8: Start wpa_supplicant_s1g (like fix_halow5.py)  
    print("[8] Starting wpa_supplicant_s1g...")
    cfg_path = "/var/run/wpa_supplicant-wlan0.conf"
    r = await e.run(f"/usr/sbin/wpa_supplicant_s1g -t -D nl80211 -s -i wlan0 -c {cfg_path} -B", timeout=10)
    print(f"  Started: {r.stdout.strip()} {r.stderr.strip()}")
    
    # Step 9: Wait for association
    print("\n[9] Waiting for association...")
    associated = False
    for i in range(15):
        await asyncio.sleep(5)
        elapsed = (i + 1) * 5
        
        r = await e.run("iwinfo wlan0 info 2>/dev/null | head -5", timeout=5)
        info = r.stdout.strip()
        
        if 'UNAL-HaLow' in info:
            print(f"\n  *** ASSOCIATED after {elapsed}s! ***")
            associated = True
            break
        
        # Check TX power
        # Check last log
        r = await e.run("logread | grep -E 'auth|CTRL-EVENT' | tail -2", timeout=5)
        log = r.stdout.strip()
        
        # Get TX power
        r2 = await e.run("iwinfo wlan0 info 2>/dev/null | grep Tx-Power", timeout=5)
        txp = r2.stdout.strip()
        
        print(f"  [{elapsed}s] {txp} | {log[:100] if log else 'waiting...'}")
    
    # Final status
    print("\n" + "=" * 60)
    print("FINAL STATUS")
    print("=" * 60)
    
    r = await e.run("iwinfo wlan0 info", timeout=5)
    print(r.stdout.strip())
    
    r = await e.run("morse_cli -i wlan0 channel", timeout=5)
    print(r.stdout.strip())
    
    if associated:
        print("\n--- Ping ---")
        r = await e.run("ping -c 5 -W 2 192.168.1.103", timeout=15)
        print(r.stdout.strip())
        
        print("\n--- Edge → AP signal ---")
        r = await e.run("iwinfo wlan0 assoclist", timeout=5)
        print(r.stdout.strip())
        
        try:
            t = await asyncio.wait_for(asyncssh.connect(TUBE_IP, username=SSH_USER, password=SSH_PASS, known_hosts=None), timeout=20)
            print("\n--- Tube → Edge signal ---")
            r = await t.run("iwinfo wlan0 assoclist", timeout=5)
            print(r.stdout.strip())
            t.close()
        except Exception as ex:
            print(f"  Tube: {ex}")
    
    e.close()
    print("\nDone!")

asyncio.run(main())
