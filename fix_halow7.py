"""
fix_halow7.py - Complete fix: patch BOTH morse.sh (add json_get_vars for STA) 
AND morse_overrides.sh (add S1G params to wpa_supplicant network block for STA)

ROOT CAUSE: drv_morse_setup() in morse.sh re-reads op_class/s1g_prim_chwidth/
s1g_prim_1mhz_chan_index from JSON before calling adhoc/mesh setup, but NOT
before STA setup. Combined with the missing STA block in morse_overrides.sh.

TWO-PART FIX:
1. morse.sh: Add json_get_vars for STA section (like mesh/adhoc)
2. morse_overrides.sh: Already patched (add STA S1G params block)
"""
import asyncio
import asyncssh

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


async def patch_file_sftp(conn, filepath, old_text, new_text, label):
    """Read, patch, and write a file via SSH cat + SFTP"""
    r = await conn.run(f'cat {filepath}', timeout=30)
    content = r.stdout
    
    if old_text not in content:
        print(f"  [{label}] WARNING: anchor text not found!")
        return False
    
    if new_text in content:
        print(f"  [{label}] Already patched!")
        return True
    
    patched = content.replace(old_text, new_text, 1)
    
    async with conn.start_sftp_client() as sftp:
        async with sftp.open(filepath, 'w') as f:
            await f.write(patched)
    
    print(f"  [{label}] Patched! (+{len(patched)-len(content)} chars)")
    return True


async def main():
    print("=" * 60)
    print("FIX HALOW 7: Complete two-part S1G fix for STA mode")
    print("=" * 60)

    edge = await ssh_connect(EDGE_IP)
    print(f"  Connected to {EDGE_IP}")

    # =============================================
    # PART 1: Patch morse.sh - add json_get_vars for STA section
    # =============================================
    print("\n[PART 1] Patching morse.sh (add json_get_vars for STA)...")
    
    # The STA section currently reads only matter/keepalive vars
    sta_old = """\tif [ -n "$ifnames_sta" ]; then
\t\tget_matter_config
\t\tjson_select config
\t\tjson_get_vars vendor_keep_alive_offload matter_enable
\t\tjson_select .."""
    
    # Add the S1G json_get_vars (same as mesh/adhoc sections)
    sta_new = """\tif [ -n "$ifnames_sta" ]; then
\t\tget_matter_config
\t\tjson_select config
\t\tjson_get_vars vendor_keep_alive_offload matter_enable
\t\t# Fix: re-read S1G channel params (same as mesh/adhoc sections)
\t\tjson_get_vars op_class channel country s1g_prim_chwidth s1g_prim_1mhz_chan_index
\t\tjson_select .."""

    ok1 = await patch_file_sftp(edge, MORSE_SH, sta_old, sta_new, 'morse.sh')
    
    if ok1:
        # Verify
        verify = await run_cmd(edge, f'grep -A6 "ifnames_sta" {MORSE_SH} | head -8', 'verify')
        print(f"  {verify}")

    # =============================================
    # PART 2: Verify morse_overrides.sh patch (already done earlier)
    # =============================================
    print("\n[PART 2] Verifying morse_overrides.sh patch...")
    
    check = await run_cmd(edge, f'grep -c "Fix: Add S1G channel params" {OVERRIDES_SH}')
    if check == '1':
        print("  morse_overrides.sh: Patch present ✓")
    else:
        print(f"  Patch count: {check} — may need re-patching")

    # Also remove the debug line we added earlier
    print("\n[2b] Removing debug logging from morse_overrides.sh...")
    r = await edge.run(f'cat {OVERRIDES_SH}', timeout=30)
    content = r.stdout
    debug_line = '\techo "DEBUG_STA _w_mode=$_w_mode op=$op_class prim=$s1g_prim_chwidth idx=$s1g_prim_1mhz_chan_index chan=$channel country=$country bw=$s1g_chanbw" >> /tmp/debug_sta.log\n'
    if debug_line in content:
        cleaned = content.replace(debug_line, '', 1)
        async with edge.start_sftp_client() as sftp:
            async with sftp.open(OVERRIDES_SH, 'w') as f:
                await f.write(cleaned)
        print("  Debug line removed")
    else:
        print("  No debug line found (ok)")

    # =============================================
    # Set UCI and restart
    # =============================================
    print("\n[3] Setting UCI s1g_chanbw='2'...")
    await run_cmd(edge, "uci set wireless.radio0.s1g_chanbw='2'", 'set')
    await run_cmd(edge, "uci commit wireless", 'commit')

    print("\n[4] Clean wifi restart...")
    await run_cmd(edge, "wifi down", 'down')
    await asyncio.sleep(4)
    print("  wifi down done, waiting 4s...")
    
    await run_cmd(edge, "wifi up", 'up')
    print("  wifi up done")

    # Wait for association
    print("\n[5] Waiting for association...")
    associated = False
    for i in range(18):
        await asyncio.sleep(5)
        elapsed = (i + 1) * 5
        
        iwinfo = await run_cmd(edge, "iwinfo wlan0 info 2>/dev/null | head -3")
        
        if 'UNAL-HaLow' in iwinfo:
            print(f"\n  *** ASSOCIATED after {elapsed}s! ***")
            associated = True
            break
        
        log = await run_cmd(edge, "logread | grep -E 'auth|CTRL-EVENT' | tail -2")
        print(f"  [{elapsed}s] {log[:150] if log else 'waiting...'}")

    # Final status
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
    
    # Check debug log
    print("\n--- Debug log (should show vars populated) ---")
    dbg = await run_cmd(edge, "cat /tmp/debug_sta.log 2>/dev/null || echo 'no debug log'")
    print(f"  {dbg}")
    
    if associated:
        # Ping test
        print("\n--- Ping test ---")
        await run_cmd(edge, "ping -c 3 -W 2 192.168.1.103", 'ping')
        
        # Check Tube
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
