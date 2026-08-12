"""Quick status check - Edge seems to be associated!"""
import asyncio, asyncssh

async def main():
    edge = await asyncio.wait_for(asyncssh.connect('192.168.1.111', username='root', password='root', known_hosts=None, login_timeout=15), timeout=20)
    tube = await asyncio.wait_for(asyncssh.connect('192.168.1.103', username='root', password='root', known_hosts=None, login_timeout=15), timeout=20)
    
    print("=== EDGE iwinfo ===")
    r = await edge.run('iwinfo wlan0 info', timeout=10)
    print(r.stdout.strip())
    
    print("\n=== EDGE morse_cli channel ===")
    r = await edge.run('morse_cli -i wlan0 channel', timeout=10)
    print(r.stdout.strip())
    
    print("\n=== TUBE iwinfo ===")
    r = await tube.run('iwinfo wlan0 info', timeout=10)
    print(r.stdout.strip())
    
    print("\n=== TUBE assoclist ===")
    r = await tube.run('iwinfo wlan0 assoclist', timeout=10)
    print(r.stdout.strip() or 'No stations')
    
    print("\n=== EDGE ping to Tube via HaLow ===")
    # First check if .196 IP is up
    r = await edge.run('ip addr show wlan0', timeout=10)
    print(r.stdout.strip())
    
    # Try ping from Edge to Tube
    r = await edge.run('ping -c 5 -W 2 192.168.1.103', timeout=15)
    print(r.stdout.strip())
    
    print("\n=== EDGE wpa_supplicant config ===")
    r = await edge.run('cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || cat /tmp/run/wpa_supplicant-wlan0.conf 2>/dev/null', timeout=10)
    print(r.stdout.strip())
    
    print("\n=== EDGE signal from Tube ===")
    r = await edge.run('iwinfo wlan0 assoclist', timeout=10)
    print(r.stdout.strip() or 'No assoclist entry')
    
    # Check processes
    print("\n=== wpa_supplicant processes ===")
    r = await edge.run('ps | grep wpa_supplicant', timeout=10)
    print(r.stdout.strip())
    
    edge.close(); tube.close()

asyncio.run(main())
