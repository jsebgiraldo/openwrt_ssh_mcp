import asyncio, asyncssh

async def main():
    edge = await asyncio.wait_for(
        asyncssh.connect('192.168.1.111', username='root', password='root', known_hosts=None, login_timeout=15),
        timeout=20
    )
    
    # Find morse_setup_sta and morse_wpa_supplicant_add in morse.sh
    print("=== morse_setup_sta function ===")
    r = await edge.run("grep -n 'morse_setup_sta\\|wpa_supplicant_add\\|op_class\\|s1g_prim\\|s1g_freq' /lib/netifd/wireless/morse.sh | head -40", timeout=10)
    print(r.stdout)
    
    # Read morse_setup_sta function
    r = await edge.run("grep -n 'morse_setup_sta' /lib/netifd/wireless/morse.sh", timeout=10)
    lines = r.stdout.strip()
    print(f"\n=== morse_setup_sta lines: {lines}")
    
    # Read around the first occurrence
    r = await edge.run("awk '/^morse_setup_sta/,/^}/' /lib/netifd/wireless/morse.sh | head -60", timeout=10)
    print(r.stdout)
    
    # Find morse_wpa_supplicant_add
    print("\n=== morse_wpa_supplicant_add function ===")
    r = await edge.run("awk '/^morse_wpa_supplicant_add/,/^}/' /lib/netifd/wireless/morse.sh | head -80", timeout=10)
    print(r.stdout)
    
    # Also check where op_class, s1g_prim_chwidth are SET
    print("\n=== Where op_class is SET ===")
    r = await edge.run("grep -n 'op_class=' /lib/netifd/wireless/morse.sh | head -20", timeout=10)
    print(r.stdout)
    
    print("\n=== Where s1g_prim_chwidth is SET ===")
    r = await edge.run("grep -n 's1g_prim_chwidth' /lib/netifd/wireless/morse.sh | head -20", timeout=10)
    print(r.stdout)
    
    # Check morse_set_chan_info
    print("\n=== morse_set_chan_info function ===")
    r = await edge.run("awk '/^morse_set_chan_info/,/^}/' /lib/netifd/wireless/morse.sh | head -50", timeout=10)
    print(r.stdout)
    
    edge.close()

asyncio.run(main())
