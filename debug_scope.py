"""Debug: add logging to morse_overrides.sh to see what variables are available at STA block"""
import asyncio, asyncssh

EDGE_IP = '192.168.1.111'
SSH_USER = 'root'
SSH_PASS = 'root'
OVERRIDES_PATH = '/lib/netifd/morse/morse_overrides.sh'

async def main():
    edge = await asyncio.wait_for(
        asyncssh.connect(EDGE_IP, username=SSH_USER, password=SSH_PASS, known_hosts=None, login_timeout=15),
        timeout=20
    )
    
    # Read current file
    r = await edge.run(f'cat {OVERRIDES_PATH}', timeout=30)
    content = r.stdout
    
    # Find my STA patch and add debug logging before it
    old_patch = '\t# Fix: Add S1G channel params for STA mode (mirrors adhoc/mesh blocks)'
    debug_line = '\techo "DEBUG_STA _w_mode=$_w_mode op=$op_class prim=$s1g_prim_chwidth idx=$s1g_prim_1mhz_chan_index chan=$channel country=$country bw=$s1g_chanbw" >> /tmp/debug_sta.log'
    
    if old_patch in content:
        new_content = content.replace(old_patch, debug_line + '\n' + old_patch, 1)
        
        # Write via SFTP
        async with edge.start_sftp_client() as sftp:
            async with sftp.open(OVERRIDES_PATH, 'w') as f:
                await f.write(new_content)
        print("Debug logging added")
    else:
        print("Patch not found!")
        edge.close()
        return
    
    # Clear old debug log
    await edge.run('rm -f /tmp/debug_sta.log', timeout=5)
    
    # Restart wifi
    print("wifi down...")
    await edge.run('wifi down', timeout=10)
    await asyncio.sleep(3)
    print("wifi up...")
    await edge.run('wifi up', timeout=10)
    await asyncio.sleep(8)
    
    # Read debug log
    print("\n=== DEBUG LOG ===")
    r = await edge.run('cat /tmp/debug_sta.log 2>/dev/null || echo "No log created"', timeout=5)
    print(r.stdout.strip())
    
    # Also read generated config
    print("\n=== Generated wpa_supplicant config ===")
    r = await edge.run('cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || echo "not found"', timeout=5)
    print(r.stdout.strip())
    
    edge.close()

asyncio.run(main())
