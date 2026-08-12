"""Read drv_morse_setup() to find where op_class gets cleared"""
import asyncio, asyncssh

async def main():
    edge = await asyncio.wait_for(
        asyncssh.connect('192.168.1.111', username='root', password='root', known_hosts=None, login_timeout=15),
        timeout=20
    )
    
    # Read the entire drv_morse_setup function
    print("=== drv_morse_setup (lines 380-530) ===")
    r = await edge.run("sed -n '380,530p' /lib/netifd/wireless/morse.sh", timeout=10)
    print(r.stdout)
    
    # Also read morse_set_chan_info line number
    print("\n=== morse_set_chan_info call location ===")
    r = await edge.run("grep -n 'morse_set_chan_info' /lib/netifd/wireless/morse.sh", timeout=10)
    print(r.stdout)
    
    # Check _wpa_supplicant_common for json_get_vars
    print("\n=== _wpa_supplicant_common function ===")
    r = await edge.run("grep -n 'json_get_vars' /lib/netifd/wireless/morse.sh | head -30", timeout=10)
    print(r.stdout)
    
    # Check standard OpenWrt wpa_supplicant functions
    print("\n=== Standard wpa_supplicant_prepare_interface ===")
    r = await edge.run("grep -r 'json_get_vars.*op_class' /lib/netifd/ 2>/dev/null | head -10", timeout=10)
    print(r.stdout.strip() or "No json_get_vars with op_class found")
    
    edge.close()

asyncio.run(main())
