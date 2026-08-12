"""Add debug logging at 3 key points to trace where op_class gets cleared"""
import asyncio, asyncssh

EDGE_IP = '192.168.1.111'
SSH_USER = 'root'
SSH_PASS = 'root'
MORSE_SH = '/lib/netifd/wireless/morse.sh'
OVERRIDES_SH = '/lib/netifd/morse/morse_overrides.sh'

async def patch_file(conn, filepath, anchor, insert_after, tag):
    r = await conn.run(f'cat {filepath}', timeout=30)
    content = r.stdout
    
    if tag in content:
        print(f"  [{tag}] Already added")
        return True
    
    if anchor not in content:
        print(f"  [{tag}] ERROR: Anchor not found!")
        print(f"  Looking for: {repr(anchor[:80])}")
        return False
    
    patched = content.replace(anchor, anchor + '\n' + insert_after, 1)
    async with conn.start_sftp_client() as sftp:
        async with sftp.open(filepath, 'w') as f:
            await f.write(patched)
    print(f"  [{tag}] Added")
    return True

async def main():
    e = await asyncio.wait_for(asyncssh.connect(EDGE_IP, username=SSH_USER, password=SSH_PASS, known_hosts=None), timeout=20)
    
    # Clear old debug log
    await e.run('rm -f /tmp/debug_sta.log', timeout=5)
    
    # Debug point 1: In drv_morse_setup STA section, after json_get_vars
    print("[1] Adding debug after json_get_vars in STA section (morse.sh)...")
    await patch_file(e, MORSE_SH,
        '\t\t# Fix: re-read S1G channel params (same as mesh/adhoc sections)\n\t\tjson_get_vars op_class channel country s1g_prim_chwidth s1g_prim_1mhz_chan_index',
        '\t\techo "DBG1_drv_setup: op=$op_class prim=$s1g_prim_chwidth idx=$s1g_prim_1mhz_chan_index ch=$channel" >> /tmp/debug_sta.log',
        'DBG1_drv_setup')
    
    # Debug point 2: Inside morse_setup_sta, before calling morse_wpa_supplicant_add
    print("[2] Adding debug in morse_setup_sta (morse.sh)...")
    await patch_file(e, MORSE_SH,
        '\tmorse_wpa_supplicant_add $ifname 1 $matter_enable || failed=1',
        '\techo "DBG2_setup_sta: op=$op_class prim=$s1g_prim_chwidth idx=$s1g_prim_1mhz_chan_index ifname=$ifname" >> /tmp/debug_sta.log',
        'DBG2_setup_sta')
    
    # Debug point 3: Inside morse_override_wpa_supplicant_add_network, before STA block
    print("[3] Adding debug before STA S1G block (morse_overrides.sh)...")
    await patch_file(e, OVERRIDES_SH,
        '\t# Fix: Add S1G channel params for STA mode (mirrors adhoc/mesh blocks)',
        '\techo "DBG3_override: _w_mode=$_w_mode op=$op_class prim=$s1g_prim_chwidth idx=$s1g_prim_1mhz_chan_index" >> /tmp/debug_sta.log',
        'DBG3_override')
    
    # Restart wifi
    print("\nRestarting wifi...")
    await e.run('wifi down', timeout=10)
    await asyncio.sleep(4)
    await e.run('wifi up', timeout=10)
    await asyncio.sleep(8)
    
    # Read debug log
    print("\n=== DEBUG LOG ===")
    r = await e.run('cat /tmp/debug_sta.log 2>/dev/null || echo "empty"', timeout=5)
    print(r.stdout.strip())
    
    # Check config
    print("\n=== WPA CONFIG ===")
    r = await e.run('cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || echo "not found"', timeout=5)
    print(r.stdout.strip())
    
    e.close()
asyncio.run(main())
