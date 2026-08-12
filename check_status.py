import asyncio, asyncssh
async def main():
    edge = await asyncio.wait_for(asyncssh.connect('192.168.1.111', username='root', password='root', known_hosts=None, login_timeout=15), timeout=20)
    tube = await asyncio.wait_for(asyncssh.connect('192.168.1.103', username='root', password='root', known_hosts=None, login_timeout=15), timeout=20)
    for conn, name in [(edge,'EDGE'),(tube,'TUBE')]:
        r = await conn.run('iwinfo wlan0 info | head -8', timeout=10)
        print(f'\n=== {name} iwinfo ==='); print(r.stdout.strip())
        r = await conn.run('morse_cli -i wlan0 channel', timeout=10)
        print(r.stdout.strip())
        r = await conn.run('iwinfo wlan0 assoclist', timeout=10)
        print(r.stdout.strip() or 'No station connected')
    r = await edge.run("logread | grep -iE 'auth|assoc|SAE|connected' | tail -15", timeout=10)
    print('\n=== EDGE LOGS ==='); print(r.stdout.strip())
    r = await edge.run('ps | grep wpa_supplicant', timeout=10)
    print('\n=== WPA PROC ==='); print(r.stdout.strip())
    r = await edge.run('cat /tmp/run/wpa_supplicant-wlan0.conf', timeout=10)
    print('\n=== WPA CONFIG ==='); print(r.stdout.strip())
    edge.close(); tube.close()
asyncio.run(main())
