"""
fix_halow6c.py - Persist morse_overrides.sh patch + set UCI + test clean wifi restart
Uses asyncssh SFTPClient correctly (open/read/write instead of .read)
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
    if label:
        print(f"  [{label}] {out}")
    return out


async def main():
    print("=" * 60)
    print("PERSIST PATCH + SET UCI + CLEAN WIFI RESTART")
    print("=" * 60)

    edge = await ssh_connect(EDGE_IP)
    print(f"  Connected to {EDGE_IP}")

    # Step 1: Read file via SSH cat (SFTP read API was wrong)
    print("\n[1] Reading morse_overrides.sh...")
    r = await edge.run(f'cat {OVERRIDES_PATH}', timeout=30)
    content = r.stdout
    print(f"  Read {len(content)} chars")

    # Step 2: Check if already patched
    if '# Fix: Add S1G channel params for STA mode' in content:
        print("  Already patched! Skipping.")
    else:
        # Find anchor and insert
        anchor = '\t[ "$multi_ap" = 1 -a "$_w_mode" = "sta" ] && append network_data "multi_ap_backhaul_sta=1" "$N$T"'
        
        if anchor not in content:
            print("  ERROR: Anchor line not found!")
            # Debug: show lines around multi_ap
            for i, line in enumerate(content.split('\n')):
                if 'multi_ap' in line:
                    print(f"    Line {i+1}: [{repr(line)}]")
            edge.close()
            return
        
        # Patch text (real tabs)
        patch = '\n'.join([
            '',
            '\t# Fix: Add S1G channel params for STA mode (mirrors adhoc/mesh blocks)',
            '\t[ "$_w_mode" = "sta" ] && {',
            '\t\t[ -n "$op_class" ] && append network_data "op_class=$op_class" "$N$T"',
            '\t\t[ -n "$s1g_prim_chwidth" ] && append network_data "s1g_prim_chwidth=$s1g_prim_chwidth" "$N$T"',
            '\t\t[ -n "$s1g_prim_1mhz_chan_index" ] && append network_data "s1g_prim_1mhz_chan_index=$s1g_prim_1mhz_chan_index" "$N$T"',
            '\t}',
        ])
        
        patched = content.replace(anchor, anchor + patch, 1)
        
        if '# Fix: Add S1G channel params for STA mode' not in patched:
            print("  ERROR: Patch not applied!")
            edge.close()
            return
        
        print(f"  Patch ready (+{len(patched)-len(content)} chars)")

        # Write via SFTP using proper API
        print("\n[2] Writing patched file via SFTP...")
        async with edge.start_sftp_client() as sftp:
            async with sftp.open(OVERRIDES_PATH, 'w') as f:
                await f.write(patched)
        print("  Written!")

        # Verify
        print("\n[3] Verifying patch...")
        verify = await run_cmd(edge, f'grep -A7 "multi_ap_backhaul_sta" {OVERRIDES_PATH}', 'verify')
        print(f"\n{verify}")

    # Step 3: Set UCI config
    print("\n[4] Setting UCI s1g_chanbw='2'...")
    await run_cmd(edge, "uci set wireless.radio0.s1g_chanbw='2'", 'set')
    await run_cmd(edge, "uci commit wireless", 'commit')
    print("  Done")

    # Step 4: Clean wifi restart test
    print("\n[5] Testing clean wifi restart (wifi down + wifi up)...")
    print("  wifi down...")
    await run_cmd(edge, "wifi down", 'down')
    await asyncio.sleep(4)
    
    print("  wifi up...")
    await run_cmd(edge, "wifi up", 'up')
    
    # Wait for association
    print("  Waiting for association...")
    associated = False
    for i in range(18):
        await asyncio.sleep(5)
        elapsed = (i + 1) * 5
        
        iwinfo = await run_cmd(edge, "iwinfo wlan0 info 2>/dev/null | head -3")
        if 'UNAL-HaLow' in iwinfo:
            print(f"\n  *** ASSOCIATED after {elapsed}s! ***")
            associated = True
            break
        
        log = await run_cmd(edge, "logread | grep -E 'auth|assoc|CTRL-EVENT' | tail -2")
        print(f"  [{elapsed}s] {log[:120] if log else 'waiting...'}")

    # Final status
    print("\n" + "=" * 60)
    print("FINAL STATUS AFTER CLEAN WIFI RESTART")
    print("=" * 60)
    
    print("\n--- Edge iwinfo ---")
    await run_cmd(edge, "iwinfo wlan0 info | head -12", 'edge')
    
    print("\n--- Edge morse_cli channel ---")
    await run_cmd(edge, "morse_cli -i wlan0 channel", 'ch')
    
    print("\n--- Edge wpa_supplicant config (should have S1G params) ---")
    cfg = await run_cmd(edge, "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || cat /tmp/run/wpa_supplicant-wlan0.conf 2>/dev/null")
    print(f"  {cfg}")
    
    if associated:
        print("\n--- Ping test ---")
        await run_cmd(edge, "ping -c 5 -W 2 192.168.1.103", 'ping')
        
        try:
            tube = await ssh_connect(TUBE_IP)
            print("\n--- Tube assoclist ---")
            await run_cmd(tube, "iwinfo wlan0 assoclist", 'tube')
            tube.close()
        except Exception as e:
            print(f"  Tube: {e}")
    
    edge.close()
    print("\nDone!")


if __name__ == '__main__':
    asyncio.run(main())
