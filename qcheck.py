"""Quick check: did the morse.sh patch produce S1G params in wpa_supplicant config?"""
import asyncio, asyncssh
async def main():
    e = await asyncio.wait_for(asyncssh.connect('192.168.1.111', username='root', password='root', known_hosts=None), timeout=20)
    # Check wpa_supplicant config
    r = await e.run('cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null', timeout=5)
    print("WPA CONFIG:"); print(r.stdout.strip())
    # Verify morse.sh patch
    r = await e.run('grep -B2 -A3 "re-read S1G" /lib/netifd/wireless/morse.sh 2>/dev/null', timeout=5)
    print("\nMORSE.SH PATCH:"); print(r.stdout.strip())
    # Check what iwinfo says
    r = await e.run('iwinfo wlan0 info 2>/dev/null | head -5', timeout=5)
    print("\nIWINFO:"); print(r.stdout.strip())
    e.close()
asyncio.run(main())
