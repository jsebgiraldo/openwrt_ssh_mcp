"""
fix_halow6b.py - Patch morse_overrides.sh using SFTP (avoids shell escaping issues)
"""
import asyncio
import asyncssh

EDGE_IP = '192.168.1.111'
TUBE_IP = '192.168.1.103'
SSH_USER = 'root'
SSH_PASS = 'root'
OVERRIDES_PATH = '/lib/netifd/morse/morse_overrides.sh'


async def ssh_connect(host, timeout=20):
    return await asyncio.wait_for(
        asyncssh.connect(host, username=SSH_USER, password=SSH_PASS, known_hosts=None, login_timeout=15),
        timeout=timeout
    )


async def run_cmd(conn, cmd, label="", timeout=15):
    r = await conn.run(cmd, timeout=timeout)
    out = r.stdout.strip()
    err = r.stderr.strip()
    if label:
        print(f"  [{label}] {out}")
        if err:
            print(f"  [{label} ERR] {err}")
    return out


async def main():
    print("=" * 60)
    print("FIX HALOW 6b: Patch morse_overrides.sh via SFTP")
    print("=" * 60)

    edge = await ssh_connect(EDGE_IP)
    print(f"  Connected to {EDGE_IP}")

    # Step 1: Check current state
    print("\n[1] Pre-flight checks...")
    await run_cmd(edge, "iwinfo wlan0 info 2>/dev/null | head -3", 'iwinfo')
    await run_cmd(edge, "morse_cli -i wlan0 channel 2>/dev/null | head -5", 'channel')

    # Step 2: Read the file via SFTP
    print("\n[2] Reading morse_overrides.sh via SFTP...")
    async with edge.start_sftp_client() as sftp:
        content_bytes = await sftp.read(OVERRIDES_PATH)
        if isinstance(content_bytes, bytes):
            content = content_bytes.decode('utf-8')
        else:
            content = content_bytes
    
    print(f"  Read {len(content)} bytes")

    # Step 3: Check if already patched
    if '# Fix: Add S1G channel params for STA mode' in content:
        print("  Already patched! Skipping file modification.")
    else:
        # Step 4: Find anchor and insert patch
        anchor = '\t[ "$multi_ap" = 1 -a "$_w_mode" = "sta" ] && append network_data "multi_ap_backhaul_sta=1" "$N$T"'
        
        if anchor not in content:
            print("  ERROR: Anchor line not found!")
            # Try to find it
            for i, line in enumerate(content.split('\n')):
                if 'multi_ap' in line and 'sta' in line:
                    print(f"    Line {i+1}: [{repr(line)}]")
            edge.close()
            return
        
        # The patch to insert (using real tabs)
        patch = '\n'.join([
            '',
            '\t# Fix: Add S1G channel params for STA mode (mirrors adhoc/mesh blocks)',
            '\t[ "$_w_mode" = "sta" ] && {',
            '\t\t[ -n "$op_class" ] && append network_data "op_class=$op_class" "$N$T"',
            '\t\t[ -n "$s1g_prim_chwidth" ] && append network_data "s1g_prim_chwidth=$s1g_prim_chwidth" "$N$T"',
            '\t\t[ -n "$s1g_prim_1mhz_chan_index" ] && append network_data "s1g_prim_1mhz_chan_index=$s1g_prim_1mhz_chan_index" "$N$T"',
            '\t}',
        ])
        
        patched = content.replace(anchor, anchor + patch, 1)  # Replace only first occurrence
        
        # Verify patch was applied
        if '# Fix: Add S1G channel params for STA mode' not in patched:
            print("  ERROR: Patch insertion failed!")
            edge.close()
            return
        
        print(f"  Patched content: {len(patched)} bytes (+{len(patched)-len(content)} bytes)")
        
        # Step 5: Write patched file via SFTP
        print("\n[3] Writing patched file via SFTP...")
        async with edge.start_sftp_client() as sftp:
            await sftp.write(OVERRIDES_PATH, patched.encode('utf-8'))
        print("  Written successfully!")
        
        # Verify
        print("\n[4] Verifying patch...")
        verify = await run_cmd(edge, f'grep -A7 "multi_ap_backhaul_sta" {OVERRIDES_PATH}', 'verify')
        print(f"\n{verify}")

    # Step 6: Set UCI s1g_chanbw='2' on Edge (same as Tube)
    print("\n[5] Setting UCI s1g_chanbw='2' on Edge...")
    await run_cmd(edge, "uci set wireless.radio0.s1g_chanbw='2'", 'set')
    await run_cmd(edge, "uci commit wireless", 'commit')
    bw = await run_cmd(edge, "uci get wireless.radio0.s1g_chanbw", 'get')
    print(f"  s1g_chanbw = {bw}")
    
    # Show current Edge config
    print("\n[6] Edge wireless config:")
    await run_cmd(edge, "uci show wireless", 'config')

    # Step 7: Kill any stale processes
    print("\n[7] Killing stale wpa_supplicant_s1g...")
    await run_cmd(edge, "killall wpa_supplicant_s1g 2>/dev/null", 'kill')
    await asyncio.sleep(1)

    # Step 8: Clean wifi restart
    print("\n[8] wifi down...")
    await run_cmd(edge, "wifi down", 'down')
    await asyncio.sleep(4)
    print("  Waiting 4s...")
    
    print("  wifi up...")
    await run_cmd(edge, "wifi up", 'up')
    print("  wifi up complete")

    # Step 9: Wait for association
    print("\n[9] Monitoring association (5s intervals, 90s max)...")
    associated = False
    for i in range(18):
        await asyncio.sleep(5)
        elapsed = (i + 1) * 5
        
        # Check iwinfo
        iwinfo = await run_cmd(edge, "iwinfo wlan0 info 2>/dev/null | head -5")
        
        if 'UNAL-HaLow' in iwinfo:
            print(f"\n  *** ASSOCIATED after {elapsed}s! ***")
            associated = True
            break
        
        # Check process
        ps = await run_cmd(edge, "pgrep -f wpa_supplicant_s1g")
        if not ps:
            print(f"  [{elapsed}s] wpa_supplicant_s1g NOT running!")
            # Check if wifi is still coming up
            logr = await run_cmd(edge, "logread | tail -5")
            print(f"  {logr}")
            if elapsed > 20:
                print("  Giving up - process not starting")
                break
            continue
        
        # Show last relevant log
        log = await run_cmd(edge, "logread | grep -E 'wlan0.*auth|wlan0.*assoc|CTRL-EVENT|s1g_prim|op_class|morse' | tail -3")
        print(f"  [{elapsed}s] {log}")

    # Step 10: Final status
    print("\n" + "=" * 60)
    print("FINAL STATUS")
    print("=" * 60)
    
    print("\n--- Edge iwinfo ---")
    iwinfo_full = await run_cmd(edge, "iwinfo wlan0 info 2>/dev/null | head -10", 'iwinfo')
    
    print("\n--- Edge morse_cli channel ---")
    await run_cmd(edge, "morse_cli -i wlan0 channel 2>/dev/null", 'channel')
    
    print("\n--- Edge wpa_supplicant config ---")
    wpacfg = await run_cmd(edge, "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || echo 'not found'")
    if wpacfg == 'not found':
        wpacfg = await run_cmd(edge, "cat /tmp/run/wpa_supplicant-wlan0.conf 2>/dev/null || echo 'still not found'")
    for line in wpacfg.split('\n'):
        print(f"  {line}")
    
    print("\n--- Edge auth logs ---")
    await run_cmd(edge, "logread | grep -iE 'auth|assoc|SAE|CTRL-EVENT' | tail -15", 'logs')
    
    if associated:
        print("\n--- Testing connectivity ---")
        ping = await run_cmd(edge, "ping -c 3 -W 2 192.168.1.103 2>/dev/null", 'ping')
        print(f"  {ping}")
        
        # Check Tube
        try:
            tube = await ssh_connect(TUBE_IP)
            print("\n--- Tube assoclist ---")
            await run_cmd(tube, "iwinfo wlan0 assoclist", 'tube-assoc')
            tube.close()
        except Exception as e:
            print(f"  Tube check failed: {e}")
    
    edge.close()
    print("\nDone!")


if __name__ == '__main__':
    asyncio.run(main())
