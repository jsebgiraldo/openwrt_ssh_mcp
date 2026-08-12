import asyncio, asyncssh

async def main():
    edge = await asyncio.wait_for(
        asyncssh.connect('192.168.1.111', username='root', password='root', known_hosts=None, login_timeout=15),
        timeout=20
    )
    
    # Read morse_overrides.sh around the wpa_supplicant_add_network function
    # First, find the function and nearby lines
    print("=== Finding function boundaries ===")
    r = await edge.run("grep -n 'morse_override_wpa_supplicant_add_network\\|adhoc\\|mesh\\|sta\\|mode\\|op_class\\|s1g_prim\\|frequency\\|wpa_supplicant_config_append' /lib/netifd/morse/morse_overrides.sh", timeout=10)
    print(r.stdout)
    
    # Read the full function
    print("\n=== Full function (lines 740-870) ===")
    r = await edge.run("sed -n '740,870p' /lib/netifd/morse/morse_overrides.sh", timeout=10)
    print(r.stdout)
    
    edge.close()

asyncio.run(main())
