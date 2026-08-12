"""Read complete morse_set_chan_info and check json_select cleanup"""
import asyncio, asyncssh
async def main():
    e = await asyncio.wait_for(asyncssh.connect('192.168.1.111', username='root', password='root', known_hosts=None), timeout=20)
    
    # Read complete morse_set_chan_info
    print("=== COMPLETE morse_set_chan_info (lines 1007-1060) ===")
    r = await e.run("sed -n '1007,1060p' /lib/netifd/wireless/morse.sh", timeout=5)
    print(r.stdout)
    
    # Check STA section in drv_morse_setup (lines 490-502 ish)
    print("=== STA section in drv_morse_setup (lines 488-505) ===")
    r = await e.run("sed -n '488,510p' /lib/netifd/wireless/morse.sh", timeout=5)
    print(r.stdout)
    
    # Check json_select pairs in drv_morse_setup 
    print("=== All json_select calls in drv_morse_setup ===")
    r = await e.run("awk '/^drv_morse_setup/,/^[a-z_]*_morse_/' /lib/netifd/wireless/morse.sh | grep -n 'json_select'", timeout=5)
    print(r.stdout)
    
    # Try adding debug in STA section to see json state
    print("\n=== Check what json_dump shows ===")
    # Read the entire json environment
    r = await e.run("cat /var/run/wifi-phy0.json 2>/dev/null || echo 'no json file'", timeout=5)
    json_content = r.stdout[:3000]
    print(json_content)
    
    e.close()
asyncio.run(main())
