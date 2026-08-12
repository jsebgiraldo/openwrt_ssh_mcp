import asyncio, asyncssh
async def m():
    e = await asyncio.wait_for(asyncssh.connect('192.168.1.111', username='root', password='root', known_hosts=None), timeout=20)
    r = await e.run('cat /tmp/debug_sta.log 2>/dev/null || echo "empty"', timeout=5)
    print("DEBUG:", r.stdout.strip())
    r = await e.run('cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null', timeout=5)
    print("\nCONFIG:", r.stdout.strip())
    e.close()
asyncio.run(m())
