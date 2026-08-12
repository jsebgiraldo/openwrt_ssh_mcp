"""Check variable scoping: read _get_regulatory and trace where vars are set"""
import asyncio, asyncssh

async def main():
    edge = await asyncio.wait_for(asyncssh.connect('192.168.1.111', username='root', password='root', known_hosts=None, login_timeout=15), timeout=20)
    
    # Read _get_regulatory function
    print("=== _get_regulatory function ===")
    r = await edge.run("awk '/_get_regulatory\\(\\)/,/^}/' /lib/netifd/morse/morse_utils.sh", timeout=10)
    print(r.stdout[:3000])
    
    # Check drv_morse_setup for local declarations
    print("\n=== drv_morse_setup local vars ===")
    r = await edge.run("awk '/drv_morse_setup\\(\\)/,/^}/' /lib/netifd/wireless/morse.sh | grep -E 'local|op_class|s1g_prim' | head -20", timeout=10)
    print(r.stdout.strip())
    
    # Check for_each_interface is subshell or not
    print("\n=== for_each_interface (first 20 lines) ===")
    r = await edge.run("grep -A20 'for_each_interface()' /lib/netifd/netifd-wireless.sh 2>/dev/null || grep -A20 'for_each_interface()' /lib/netifd/wireless/morse.sh 2>/dev/null || echo 'not found in expected files'", timeout=10)
    print(r.stdout[:2000])
    
    # Also check morse_wpa_supplicant_add for where vars come from
    print("\n=== morse_wpa_supplicant_add context ===")
    r = await edge.run("awk '/morse_wpa_supplicant_add\\(\\)/,/^}/' /lib/netifd/wireless/morse.sh | head -30", timeout=10)
    print(r.stdout.strip())
    
    # Check where freq/htmode/etc come from for non-STA modes
    print("\n=== morse_setup_adhoc (to see how vars are passed) ===")
    r = await edge.run("awk '/morse_setup_adhoc\\(\\)/,/^}/' /lib/netifd/wireless/morse.sh | head -30", timeout=10)
    print(r.stdout.strip())
    
    edge.close()

asyncio.run(main())
