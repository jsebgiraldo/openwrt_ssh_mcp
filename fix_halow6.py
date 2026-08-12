"""
fix_halow6.py - Patch morse_overrides.sh on Edge Gateway to add S1G params for STA mode

ROOT CAUSE: morse_override_wpa_supplicant_add_network() adds S1G channel parameters
(op_class, s1g_prim_chwidth, s1g_prim_1mhz_chan_index) for adhoc and mesh modes,
but NOT for STA mode. This causes the STA to scan at 1 MHz and fail to associate
with the 8 MHz AP.

FIX: Insert STA S1G param block after the multi_ap line, mirroring adhoc/mesh blocks.
Then set UCI s1g_chanbw='2' and do a clean wifi restart.
"""
import asyncio
import asyncssh

EDGE_IP = '192.168.1.111'
TUBE_IP = '192.168.1.103'
SSH_USER = 'root'
SSH_PASS = 'root'

OVERRIDES_PATH = '/lib/netifd/morse/morse_overrides.sh'

# The line we insert AFTER (line 858 in the original)
ANCHOR_LINE = '\t[ "$multi_ap" = 1 -a "$_w_mode" = "sta" ] && append network_data "multi_ap_backhaul_sta=1" "$N$T"'

# The S1G params block to add for STA mode
STA_S1G_PATCH = '''
\t# Fix: Add S1G channel params for STA mode (mirrors adhoc/mesh blocks)
\t[ "$_w_mode" = "sta" ] && {
\t\t[ -n "$op_class" ] && append network_data "op_class=$op_class" "$N$T"
\t\t[ -n "$s1g_prim_chwidth" ] && append network_data "s1g_prim_chwidth=$s1g_prim_chwidth" "$N$T"
\t\t[ -n "$s1g_prim_1mhz_chan_index" ] && append network_data "s1g_prim_1mhz_chan_index=$s1g_prim_1mhz_chan_index" "$N$T"
\t}'''


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
    print("FIX HALOW 6: Patch morse_overrides.sh for STA S1G params")
    print("=" * 60)

    # Connect to Edge
    print("\n[1] Connecting to Edge Gateway...")
    edge = await ssh_connect(EDGE_IP)
    print(f"  Connected to {EDGE_IP}")

    # Step 1: Backup morse_overrides.sh
    print("\n[2] Backing up morse_overrides.sh...")
    await run_cmd(edge, f'cp {OVERRIDES_PATH} {OVERRIDES_PATH}.bak', 'backup')
    print("  Backup created")

    # Step 2: Check if patch already applied
    print("\n[3] Checking if patch already applied...")
    check = await run_cmd(edge, f'grep -c "Fix: Add S1G channel params for STA" {OVERRIDES_PATH}')
    if check != '0':
        print("  Patch already applied! Skipping file modification.")
    else:
        # Step 3: Apply the patch using sed
        # Find the exact line number of the anchor
        print("\n[4] Finding anchor line...")
        anchor_search = await run_cmd(edge, f'grep -n "multi_ap_backhaul_sta" {OVERRIDES_PATH}')
        print(f"  Found: {anchor_search}")
        
        # Extract line number
        line_num = anchor_search.split(':')[0]
        print(f"  Anchor at line {line_num}")

        # Use sed to insert after the anchor line
        # First create the patch text as a file, then use sed
        patch_text = (
            '\\t# Fix: Add S1G channel params for STA mode (mirrors adhoc/mesh blocks)\\n'
            '\\t[ "$_w_mode" = "sta" ] \\&\\& {\\n'
            '\\t\\t[ -n "$op_class" ] \\&\\& append network_data "op_class=$op_class" "$N$T"\\n'
            '\\t\\t[ -n "$s1g_prim_chwidth" ] \\&\\& append network_data "s1g_prim_chwidth=$s1g_prim_chwidth" "$N$T"\\n'
            '\\t\\t[ -n "$s1g_prim_1mhz_chan_index" ] \\&\\& append network_data "s1g_prim_1mhz_chan_index=$s1g_prim_1mhz_chan_index" "$N$T"\\n'
            '\\t}'
        )
        
        # Use a heredoc approach - write a small script to do the patching
        patch_script = f"""
cat > /tmp/patch_overrides.sh << 'PATCHEOF'
#!/bin/sh
FILE="{OVERRIDES_PATH}"
LINE={line_num}
# Create temp file with the patch inserted after line $LINE
head -n $LINE "$FILE" > /tmp/overrides_patched.sh
cat >> /tmp/overrides_patched.sh << 'INSERTEOF'

\t# Fix: Add S1G channel params for STA mode (mirrors adhoc/mesh blocks)
\t[ "$_w_mode" = "sta" ] && {{
\t\t[ -n "$op_class" ] && append network_data "op_class=$op_class" "$N$T"
\t\t[ -n "$s1g_prim_chwidth" ] && append network_data "s1g_prim_chwidth=$s1g_prim_chwidth" "$N$T"
\t\t[ -n "$s1g_prim_1mhz_chan_index" ] && append network_data "s1g_prim_1mhz_chan_index=$s1g_prim_1mhz_chan_index" "$N$T"
\t}}
INSERTEOF
tail -n +$(($LINE + 1)) "$FILE" >> /tmp/overrides_patched.sh
cp /tmp/overrides_patched.sh "$FILE"
rm /tmp/overrides_patched.sh
PATCHEOF
chmod +x /tmp/patch_overrides.sh
"""
        # Actually, let's use a simpler Python-on-device approach since sed escaping is painful
        # Write patch via Python directly from here
        print("\n[4] Applying patch...")
        
        # Read the file content
        r = await edge.run(f'cat {OVERRIDES_PATH}', timeout=15)
        content = r.stdout
        
        # Find the anchor line and insert after it
        anchor = '[ "$multi_ap" = 1 -a "$_w_mode" = "sta" ] && append network_data "multi_ap_backhaul_sta=1" "$N$T"'
        
        if anchor not in content:
            print("  ERROR: Could not find anchor line!")
            print("  Looking for similar lines...")
            for i, line in enumerate(content.split('\n')):
                if 'multi_ap' in line and 'sta' in line:
                    print(f"    Line {i+1}: {line.rstrip()}")
            edge.close()
            return
        
        # Create the insertion text (using actual tabs)
        insert_text = '\n'.join([
            '',
            '\t# Fix: Add S1G channel params for STA mode (mirrors adhoc/mesh blocks)',
            '\t[ "$_w_mode" = "sta" ] && {',
            '\t\t[ -n "$op_class" ] && append network_data "op_class=$op_class" "$N$T"',
            '\t\t[ -n "$s1g_prim_chwidth" ] && append network_data "s1g_prim_chwidth=$s1g_prim_chwidth" "$N$T"',
            '\t\t[ -n "$s1g_prim_1mhz_chan_index" ] && append network_data "s1g_prim_1mhz_chan_index=$s1g_prim_1mhz_chan_index" "$N$T"',
            '\t}',
        ])
        
        # Insert after anchor
        patched = content.replace(anchor, anchor + insert_text)
        
        # Write patched file back
        # Use base64 to avoid escaping issues
        import base64
        encoded = base64.b64encode(patched.encode()).decode()
        
        await run_cmd(edge, f'echo "{encoded}" | base64 -d > {OVERRIDES_PATH}', 'write')
        print("  Patch applied!")
        
        # Verify
        print("\n[5] Verifying patch...")
        verify = await run_cmd(edge, f'grep -A6 "multi_ap_backhaul_sta" {OVERRIDES_PATH}')
        print(f"  Patched section:\n{verify}")

    # Step 4: Set UCI s1g_chanbw on Edge
    print("\n[6] Setting UCI s1g_chanbw='2' on Edge...")
    await run_cmd(edge, "uci set wireless.radio0.s1g_chanbw='2'", 'uci-set')
    await run_cmd(edge, "uci commit wireless", 'uci-commit')
    
    # Verify UCI
    bw = await run_cmd(edge, "uci get wireless.radio0.s1g_chanbw", 'verify')
    print(f"  s1g_chanbw = {bw}")
    
    # Show full radio config
    print("\n[7] Edge radio config:")
    await run_cmd(edge, "uci show wireless.radio0", 'radio0')

    # Step 5: Kill any stale wpa_supplicant_s1g
    print("\n[8] Killing stale wpa_supplicant_s1g...")
    await run_cmd(edge, "killall wpa_supplicant_s1g 2>/dev/null; sleep 1", 'kill')

    # Step 6: Clean wifi restart
    print("\n[9] Restarting wifi (wifi down + wifi up)...")
    await run_cmd(edge, "wifi down", 'wifi-down')
    await asyncio.sleep(3)
    print("  wifi down complete, waiting 3s...")
    
    await run_cmd(edge, "wifi up", 'wifi-up')
    print("  wifi up complete")

    # Step 7: Wait for association
    print("\n[10] Waiting for association (checking every 5s for 60s)...")
    for i in range(12):
        await asyncio.sleep(5)
        
        # Check iwinfo
        iwinfo = await run_cmd(edge, "iwinfo wlan0 info 2>/dev/null | head -3")
        
        if 'UNAL-HaLow' in iwinfo:
            print(f"\n  *** ASSOCIATED! (after {(i+1)*5}s) ***")
            print(f"  {iwinfo}")
            break
        
        # Check if wpa_supplicant_s1g is running
        ps = await run_cmd(edge, "ps | grep wpa_supplicant_s1g | grep -v grep")
        if not ps:
            print(f"  [{(i+1)*5}s] wpa_supplicant_s1g not running! Checking logs...")
            logs = await run_cmd(edge, "logread | tail -10")
            print(f"  {logs}")
            break
        
        # Check log for auth events
        log = await run_cmd(edge, "logread | grep -E 'auth|assoc|CTRL-EVENT' | tail -3")
        print(f"  [{(i+1)*5}s] {log}")
    else:
        print("\n  Association FAILED after 60s")

    # Step 8: Final status
    print("\n" + "=" * 60)
    print("FINAL STATUS")
    print("=" * 60)
    
    print("\n--- Edge iwinfo ---")
    await run_cmd(edge, "iwinfo wlan0 info | head -10", 'edge-iwinfo')
    
    print("\n--- Edge morse_cli channel ---") 
    await run_cmd(edge, "morse_cli -i wlan0 channel", 'edge-channel')
    
    print("\n--- Edge wpa_supplicant config ---")
    r = await edge.run("cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || cat /tmp/run/wpa_supplicant-wlan0.conf 2>/dev/null || echo 'No config found'", timeout=10)
    print(f"  {r.stdout.strip()}")
    
    print("\n--- Edge logs (last auth events) ---")
    await run_cmd(edge, "logread | grep -iE 'auth|assoc|SAE|connected|CTRL-EVENT' | tail -10", 'edge-logs')
    
    # Check Tube
    try:
        print("\n--- Tube assoclist ---")
        tube = await ssh_connect(TUBE_IP)
        await run_cmd(tube, "iwinfo wlan0 assoclist", 'tube-assoc')
        tube.close()
    except Exception as e:
        print(f"  Could not check Tube: {e}")

    edge.close()
    print("\nDone!")


if __name__ == '__main__':
    asyncio.run(main())
