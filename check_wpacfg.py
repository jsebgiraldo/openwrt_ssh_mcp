"""Quick check: is wpa_supplicant config generated with S1G params by native flow?"""
import asyncio, asyncssh

async def main():
    edge = await asyncio.wait_for(asyncssh.connect('192.168.1.111', username='root', password='root', known_hosts=None, login_timeout=15), timeout=20)
    
    print("=== Current wpa_supplicant config ===")
    r = await edge.run('cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || cat /tmp/run/wpa_supplicant-wlan0.conf 2>/dev/null || echo "not found"', timeout=10)
    print(r.stdout.strip())
    
    print("\n=== Processes ===")
    r = await edge.run('ps | grep -E "wpa_supplicant|morse" | grep -v grep', timeout=10)
    print(r.stdout.strip())
    
    print("\n=== iwinfo ===")
    r = await edge.run('iwinfo wlan0 info 2>/dev/null | head -5', timeout=10)
    print(r.stdout.strip())
    
    print("\n=== Last auth logs ===")
    r = await edge.run("logread | grep -E 'auth|assoc|CTRL-EVENT|op_class|s1g_prim' | tail -10", timeout=10)
    print(r.stdout.strip())

    # Also check if my patch was duplicated
    print("\n=== Check for duplicate patches ===")
    r = await edge.run('grep -c "Fix: Add S1G channel params" /lib/netifd/morse/morse_overrides.sh', timeout=10)
    print(f"  Patch count: {r.stdout.strip()}")
    
    edge.close()

asyncio.run(main())
