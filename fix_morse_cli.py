"""After native wifi up, set morse_cli channel and check if that helps"""
import asyncio, asyncssh

async def main():
    e = await asyncio.wait_for(asyncssh.connect('192.168.1.111', username='root', password='root', known_hosts=None), timeout=20)
    
    # Check current state
    print("=== Current state ===")
    r = await e.run('iwinfo wlan0 info 2>/dev/null | head -8', timeout=5)
    print(r.stdout.strip())
    r = await e.run('morse_cli -i wlan0 channel', timeout=5)
    print(r.stdout.strip())
    
    # Set channel via morse_cli
    print("\n=== Setting morse_cli channel ===")
    r = await e.run('morse_cli -i wlan0 channel -c 908000 -o 8 -p 2 -n 3', timeout=10)
    print(r.stdout.strip())
    print(r.stderr.strip())
    
    # Verify
    print("\n=== After morse_cli ===")
    r = await e.run('morse_cli -i wlan0 channel', timeout=5)
    print(r.stdout.strip())
    r = await e.run('iwinfo wlan0 info 2>/dev/null | head -8', timeout=5)
    print(r.stdout.strip())
    
    # Now restart wpa_supplicant_s1g (kill and let netifd restart it... or restart manually)
    print("\n=== Restarting wpa_supplicant_s1g ===")
    # Get the current PID and config file
    r = await e.run('ps | grep wpa_supplicant_s1g | grep -v grep', timeout=5)
    print(f"Current process: {r.stdout.strip()}")
    
    # Kill it
    await e.run('killall wpa_supplicant_s1g', timeout=5)
    await asyncio.sleep(1)
    
    # Restart with same config
    r = await e.run('/usr/sbin/wpa_supplicant_s1g -t -D nl80211 -s -i wlan0 -c /var/run/wpa_supplicant-wlan0.conf -B', timeout=10)
    print(f"Started: {r.stdout.strip()} {r.stderr.strip()}")
    
    # Wait for association
    print("\n=== Waiting for association ===")
    for i in range(12):
        await asyncio.sleep(5)
        elapsed = (i + 1) * 5
        
        r = await e.run('iwinfo wlan0 info 2>/dev/null | head -5', timeout=5)
        info = r.stdout.strip()
        
        if 'UNAL-HaLow' in info:
            print(f"\n*** ASSOCIATED after {elapsed}s! ***")
            print(info)
            
            # Full status
            r = await e.run('iwinfo wlan0 info', timeout=5)
            print(r.stdout.strip())
            r = await e.run('morse_cli -i wlan0 channel', timeout=5)
            print(r.stdout.strip())
            r = await e.run('ping -c 3 -W 2 192.168.1.103', timeout=15)
            print(r.stdout.strip())
            r = await e.run('iwinfo wlan0 assoclist', timeout=5)
            print(r.stdout.strip())
            break
        
        r = await e.run("logread | grep -E 'auth|CTRL-EVENT' | tail -2", timeout=5)
        log = r.stdout.strip()
        print(f"  [{elapsed}s] {log[:150] if log else 'waiting...'}")
    
    e.close()

asyncio.run(main())
