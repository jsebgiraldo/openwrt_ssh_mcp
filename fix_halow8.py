"""
fix_halow8.py - THE REAL FIX
Root cause: s1g_chanbw='2' doesn't match channels.csv (US,8,12,...) 
→ _get_regulatory fails → morse_set_chan_info fails → no S1G params in JSON
→ wpa_supplicant config has no S1G params → association fails

Fix: Set s1g_chanbw='8' (operating bandwidth matching channels.csv),
clean debug lines, restart wifi.
"""
import asyncio, asyncssh

EDGE_IP = '192.168.1.111'
TUBE_IP = '192.168.1.103'
SSH_USER = 'root'
SSH_PASS = 'root'
MORSE_SH = '/lib/netifd/wireless/morse.sh'
OVERRIDES_SH = '/lib/netifd/morse/morse_overrides.sh'


async def ssh_connect(host, timeout=20):
    return await asyncio.wait_for(
        asyncssh.connect(host, username=SSH_USER, password=SSH_PASS, known_hosts=None, login_timeout=15),
        timeout=timeout
    )


async def run_cmd(conn, cmd, label="", timeout=15):
    r = await conn.run(cmd, timeout=timeout)
    out = r.stdout.strip()
    if label:
        print(f"  [{label}] {out}")
    return out


async def clean_debug_lines(conn, filepath, markers):
    """Remove debug echo lines from a file"""
    r = await conn.run(f'cat {filepath}', timeout=30)
    content = r.stdout
    modified = False
    for marker in markers:
        lines = content.split('\n')
        new_lines = [l for l in lines if marker not in l]
        if len(new_lines) < len(lines):
            content = '\n'.join(new_lines)
            modified = True
    if modified:
        async with conn.start_sftp_client() as sftp:
            async with sftp.open(filepath, 'w') as f:
                await f.write(content)
        return True
    return False


async def main():
    print("=" * 60)
    print("FIX HALOW 8: Set s1g_chanbw=8 (correct operating BW)")
    print("=" * 60)

    edge = await ssh_connect(EDGE_IP)
    print(f"  Connected to {EDGE_IP}")

    # Step 1: Clean debug lines from both files
    print("\n[1] Cleaning debug lines...")
    if await clean_debug_lines(edge, MORSE_SH, ['DBG1_drv_setup', 'DBG2_setup_sta']):
        print("  morse.sh: debug lines removed")
    else:
        print("  morse.sh: clean")
    
    if await clean_debug_lines(edge, OVERRIDES_SH, ['DBG3_override']):
        print("  morse_overrides.sh: debug lines removed") 
    else:
        print("  morse_overrides.sh: clean")

    # Step 2: Verify patches still in place
    print("\n[2] Verifying patches...")
    r1 = await run_cmd(edge, f'grep -c "re-read S1G" {MORSE_SH}')
    r2 = await run_cmd(edge, f'grep -c "Fix: Add S1G channel" {OVERRIDES_SH}')
    print(f"  morse.sh patch: {'✓' if r1 == '1' else '✗ ('+r1+')'}")
    print(f"  morse_overrides.sh patch: {'✓' if r2 == '1' else '✗ ('+r2+')'}")

    # Step 3: Set correct UCI - s1g_chanbw=8 (operating BW, matches channels.csv)
    print("\n[3] Setting UCI s1g_chanbw='8'...")
    await run_cmd(edge, "uci set wireless.radio0.s1g_chanbw='8'", 'set')
    await run_cmd(edge, "uci commit wireless", 'commit')
    
    # Show config
    print("  Current config:")
    await run_cmd(edge, "uci show wireless.radio0", 'radio')

    # Step 4: Clean wifi restart
    print("\n[4] wifi down...")
    await run_cmd(edge, "wifi down", 'down')
    await asyncio.sleep(4)
    
    print("  wifi up...")
    await run_cmd(edge, "wifi up", 'up')

    # Step 5: Wait for association
    print("\n[5] Monitoring association...")
    associated = False
    for i in range(18):
        await asyncio.sleep(5)
        elapsed = (i + 1) * 5
        
        iwinfo = await run_cmd(edge, "iwinfo wlan0 info 2>/dev/null | head -3")
        
        if 'UNAL-HaLow' in iwinfo:
            print(f"\n  *** ASSOCIATED after {elapsed}s! ***")
            associated = True
            break
        
        log = await run_cmd(edge, "logread | grep -E 'wlan0.*auth|CTRL-EVENT' | tail -2")
        print(f"  [{elapsed}s] {log[:150] if log else 'waiting...'}")

    # Step 6: Final status
    print("\n" + "=" * 60)
    print("FINAL STATUS")
    print("=" * 60)
    
    print("\n--- Edge iwinfo ---")
    await run_cmd(edge, "iwinfo wlan0 info | head -12", 'edge')
    
    print("\n--- Edge morse_cli channel ---")
    await run_cmd(edge, "morse_cli -i wlan0 channel 2>/dev/null", 'ch')
    
    print("\n--- Edge wpa_supplicant config ---")
    cfg = await run_cmd(edge, "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null")
    for line in cfg.split('\n'):
        print(f"  {line}")
    
    if associated:
        print("\n--- Ping test ---")
        await run_cmd(edge, "ping -c 5 -W 2 192.168.1.103", 'ping')
        
        print("\n--- Edge sees AP ---")
        await run_cmd(edge, "iwinfo wlan0 assoclist", 'edge-assoc')
        
        try:
            tube = await ssh_connect(TUBE_IP)
            print("\n--- Tube sees Edge ---")
            await run_cmd(tube, "iwinfo wlan0 assoclist", 'tube-assoc')
            tube.close()
        except Exception as e:
            print(f"  Tube: {e}")
    else:
        print("\n--- Debug: check if morse_set_chan_info succeeded ---")
        r = await edge.run('cat /tmp/debug_sta.log 2>/dev/null || echo "no debug"', timeout=5)
        print(f"  {r.stdout.strip()}")
        
        print("\n--- Edge logs ---")
        await run_cmd(edge, "logread | grep -iE 'auth|assoc|regul|chan_info|Couldn' | tail -15", 'logs')

    edge.close()
    print("\nDone!")


if __name__ == '__main__':
    asyncio.run(main())
