#!/usr/bin/env python3
"""
Restore HaLow link after crash, re-run failed tests.
Merges valid data from 20260225_182030 with new test results.
"""
import asyncio
import asyncssh
import json
import time
import os
from datetime import datetime

WAN   = "192.168.1.1"
TUBE  = "192.168.1.103"
EDGE_ETH  = "192.168.1.111"
EDGE_WLAN = "192.168.1.196"
IPERF_PORT = 5201

# Use the same data dir to merge results
ORIG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_data", "20260225_182030")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_data", TIMESTAMP)
os.makedirs(DATA_DIR, exist_ok=True)

async def ssh_conn(host, password=None):
    kw = dict(username="root", known_hosts=None, login_timeout=15)
    if password:
        kw["password"] = password
    return await asyncio.wait_for(asyncssh.connect(host, **kw), timeout=20)

def save(name, data):
    path = os.path.join(DATA_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data, indent=2))
    print(f"  [saved] {path}")


# ─── PASO 1: Restore Tube-AHM AP (channel 14, 2 MHz) ─────────────────
async def restore_tube():
    print("=" * 60)
    print("PASO 1: RESTORING TUBE-AHM AP (Channel 14, 2 MHz)")
    print("=" * 60)
    c = await ssh_conn(TUBE, password="root")
    async with c:
        # Check current state
        r = await c.run("iwinfo wlan0 info 2>&1", timeout=10)
        print(f"  Current: {r.stdout[:200]}")
        
        r = await c.run("morse_cli -i wlan0 channel 2>&1", timeout=10)
        print(f"  Channel: {r.stdout.strip()}")
        
        # Check if already on channel 14 / 2 MHz
        if "909.000" in r.stdout or "909000" in (await c.run("morse_cli -i wlan0 channel 2>&1", timeout=5)).stdout:
            print("  AP already on channel 14 (909 MHz) ✓")
            return True
        
        print("  AP needs reconfiguration...")
        # Set UCI config
        cmds = [
            "uci set wireless.radio0.channel='14'",
            "uci set wireless.radio0.s1g_chanbw='2'",
            "uci set wireless.radio0.txpower='24'",
            "uci commit wireless",
            "wifi down; sleep 2; wifi up",
        ]
        for cmd in cmds:
            r = await c.run(cmd, timeout=15)
            if r.stdout.strip():
                print(f"    {cmd}: {r.stdout.strip()[:80]}")
        
        print("  Waiting 15s for AP to start...")
        await asyncio.sleep(15)
        
        r = await c.run("iwinfo wlan0 info 2>&1", timeout=10)
        print(f"  AP status: {r.stdout[:300]}")
        
        r = await c.run("morse_cli -i wlan0 channel 2>&1", timeout=10)
        print(f"  Channel: {r.stdout.strip()}")
        
        if "UNAL-HaLow-Tesis" in r.stdout or "909" in (await c.run("morse_cli -i wlan0 channel 2>&1", timeout=5)).stdout:
            print("  ✓ Tube AP restored")
            return True
        else:
            print("  ✗ Tube AP failed to restore!")
            return False


# ─── PASO 2: Restore Edge STA ─────────────────────────────────────────
async def restore_edge():
    print("\n" + "=" * 60)
    print("PASO 2: RESTORING EDGE STA")
    print("=" * 60)
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        # Check wlan0
        r = await c.run("iwinfo wlan0 info 2>&1", timeout=10)
        if "UNAL-HaLow-Tesis" in r.stdout and "Access Point" in r.stdout:
            print("  Edge STA already associated ✓")
            # Check IP
            r = await c.run("ip addr show wlan0 2>&1", timeout=5)
            if "192.168.1.196" in r.stdout:
                print("  Edge IP 192.168.1.196 ✓")
                return True
        
        print("  Restarting Edge wifi...")
        # Ensure config is correct
        cmds = [
            "uci set wireless.radio0.channel='14'",
            "uci set wireless.radio0.s1g_chanbw='2'",
            "uci commit wireless",
        ]
        for cmd in cmds:
            await c.run(cmd, timeout=5)
        
        # Restart wifi
        await c.run("wifi down 2>/dev/null", timeout=10)
        await asyncio.sleep(3)
        await c.run("wifi up 2>/dev/null", timeout=10)
        
        print("  Waiting 20s for STA association...")
        await asyncio.sleep(20)
        
        r = await c.run("iwinfo wlan0 info 2>&1", timeout=10)
        print(f"  STA status: {r.stdout[:300]}")
        
        if "UNAL-HaLow-Tesis" not in r.stdout:
            print("  ✗ STA not associated, trying manual fix...")
            # Use the proven manual wpa_supplicant workaround
            await c.run("wifi down 2>/dev/null", timeout=10)
            await asyncio.sleep(2)
            await c.run("wifi up 2>/dev/null", timeout=10)
            await asyncio.sleep(25)
            r = await c.run("iwinfo wlan0 info 2>&1", timeout=10)
            print(f"  STA retry: {r.stdout[:300]}")
        
        # Set IP
        await c.run("ip addr flush dev wlan0 2>/dev/null", timeout=5)
        await c.run("ip addr add 192.168.1.196/24 dev wlan0 2>/dev/null", timeout=5)
        await c.run("ip link set wlan0 up 2>/dev/null", timeout=5)
        
        r = await c.run("ip addr show wlan0 2>&1", timeout=5)
        print(f"  IP: {r.stdout.strip()[:200]}")
        
        return "192.168.1.196" in r.stdout


# ─── PASO 3: Fix routing ──────────────────────────────────────────────
async def fix_routing():
    print("\n" + "=" * 60)
    print("PASO 3: FIXING ROUTING")
    print("=" * 60)
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        for cmd in [
            "ip route del default via 192.168.1.1 dev eth0 2>/dev/null",
            "ip route del default via 192.168.1.1 dev eth0 proto static src 192.168.1.111 2>/dev/null",
            "ip route del default via 192.168.1.1 dev wlan0 proto static metric 600 2>/dev/null",
            "ip route replace default via 192.168.1.1 dev wlan0 src 192.168.1.196",
            "ip route replace 192.168.1.1 dev wlan0 src 192.168.1.196",
            "ip route replace 192.168.1.103 dev wlan0 scope link src 192.168.1.196",
            "ip route replace 192.168.1.0/24 dev wlan0 proto static scope link src 192.168.1.196 metric 10",
            "ip route replace 192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.111 metric 1000",
        ]:
            await c.run(cmd, timeout=5)
        
        r = await c.run("ip route get 192.168.1.1", timeout=5)
        wan_route = r.stdout.strip()
        print(f"  Route to WAN: {wan_route}")
        assert "wlan0" in wan_route, "WAN traffic NOT going through wlan0!"
        
        # Verify with ping  
        r = await c.run("ping -c 3 -W 5 -I wlan0 192.168.1.103 2>&1", timeout=20)
        for line in r.stdout.split("\n"):
            if "transmitted" in line or "min/avg" in line:
                print(f"  {line.strip()}")
        
        if "0% packet loss" not in r.stdout and "0 packets received" in r.stdout:
            print("  ✗ HaLow link not working!")
            return False
        
        print("  ✓ Routing fixed, HaLow link verified")
        return True


# ─── iperf3 helpers ───────────────────────────────────────────────────
async def ensure_iperf3_server(port=IPERF_PORT):
    w = await ssh_conn(WAN)
    async with w:
        await w.run("killall iperf3 2>/dev/null", timeout=5)
        await asyncio.sleep(2)
        r = await w.run(f"iperf3 -s -D -p {port} 2>&1", timeout=10)
        if r.stdout.strip():
            print(f"  iperf3 start: {r.stdout.strip()[:80]}")
        await asyncio.sleep(2)
        r = await w.run("ps w 2>/dev/null | grep iperf3 | grep -v grep", timeout=5)
        ok = "iperf3" in r.stdout
        print(f"  WAN iperf3: {'OK' if ok else 'FAILED'}")
        return ok

async def kill_iperf3():
    w = await ssh_conn(WAN)
    async with w:
        await w.run("killall iperf3 2>/dev/null", timeout=5)


# ─── TEST: Re-run UDP at safe rates ──────────────────────────────────
async def test_udp_rerun():
    print("\n" + "=" * 60)
    print("TEST 2b: UDP THROUGHPUT (Conservative Rates)")
    print("=" * 60)
    results = {}
    
    # Rates up to the TCP upload limit (~1.45 Mbps) + a couple above to find the ceiling
    rates = ["200K", "500K", "750K", "1M", "1.2M", "1.5M", "2M"]
    
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        for rate in rates:
            # Check wlan0 is still alive before each test
            r = await c.run("iwinfo wlan0 info 2>&1 | head -3", timeout=5)
            if "UNAL-HaLow-Tesis" not in r.stdout:
                print(f"  ✗ wlan0 died before UDP {rate} test!")
                results[f"udp_{rate}"] = {"error": "wlan0 died"}
                break
            
            await kill_iperf3()
            await asyncio.sleep(2)
            ok = await ensure_iperf3_server()
            if not ok:
                results[f"udp_{rate}"] = {"error": "iperf3 server failed"}
                continue
            
            print(f"  UDP Upload @ {rate}bps (15s)...", flush=True)
            r = await c.run(
                f"iperf3 -c {WAN} -p {IPERF_PORT} -B {EDGE_WLAN} -u -b {rate} -t 15 -J 2>&1",
                timeout=40
            )
            results[f"udp_{rate}_raw"] = r.stdout
            try:
                j = json.loads(r.stdout)
                summary = j["end"]["sum"]
                bps = summary["bits_per_second"]
                jitter = summary.get("jitter_ms", 0)
                lost = summary.get("lost_packets", 0)
                total = summary.get("packets", 1)
                loss_pct = (lost / total * 100) if total > 0 else 0
                print(f"    {rate}: {bps/1e6:.3f} Mbps, jitter={jitter:.1f}ms, loss={loss_pct:.1f}%")
                results[f"udp_{rate}"] = {
                    "mbps": bps / 1e6, "jitter_ms": jitter,
                    "loss_pct": loss_pct, "lost_packets": lost, "total_packets": total,
                }
            except Exception as e:
                print(f"    {rate}: parse error: {e}")
                # Try alternate JSON path
                try:
                    j = json.loads(r.stdout)
                    if "error" in j:
                        print(f"    iperf3 error: {j['error'][:100]}")
                        results[f"udp_{rate}"] = {"error": j["error"][:200]}
                    else:
                        # Try sum_sent for UDP
                        ss = j.get("end", {}).get("sum_sent", {})
                        if ss:
                            bps = ss.get("bits_per_second", 0)
                            print(f"    {rate} (sent): {bps/1e6:.3f} Mbps")
                            results[f"udp_{rate}"] = {"mbps_sent": bps/1e6, "note": "only sender stats"}
                        else:
                            results[f"udp_{rate}"] = {"error": str(e)}
                except:
                    results[f"udp_{rate}"] = {"error": str(e), "raw_head": r.stdout[:200]}
            
            await asyncio.sleep(3)
    
    save("02b_udp_rerun.json", results)
    await kill_iperf3()
    return results


# ─── TEST: Latency via wlan0 (forced binding) ────────────────────────
async def test_latency_halow():
    print("\n" + "=" * 60)
    print("TEST 3b: LATENCY (Forced wlan0 binding)")
    print("=" * 60)
    results = {}
    
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        # Ping AP via wlan0 (1 hop)
        print("  Ping AP via wlan0 (50 packets)...", flush=True)
        r = await c.run(f"ping -c 50 -W 5 -i 1 -I wlan0 {TUBE} 2>&1", timeout=120)
        results["ping_ap_raw"] = r.stdout
        
        # Ping WAN forcing source IP to wlan0 IP
        print("  Ping WAN via wlan0 src (50 packets)...", flush=True)
        r = await c.run(f"ping -c 50 -W 5 -i 1 -I {EDGE_WLAN} {WAN} 2>&1", timeout=120)
        results["ping_wan_raw"] = r.stdout
        
        # Parse
        for label, key in [("AP_via_wlan0", "ping_ap_raw"), ("WAN_via_halow", "ping_wan_raw")]:
            raw = results[key]
            for line in raw.split("\n"):
                if "packets transmitted" in line:
                    results[f"ping_{label}_stats"] = line.strip()
                    print(f"  {label}: {line.strip()}")
                if "min/avg/max" in line:
                    results[f"ping_{label}_rtt"] = line.strip()
                    print(f"  {label}: {line.strip()}")
    
    save("03b_latency_halow.json", results)
    return results


# ─── TEST: Stability (shorter, with link monitoring) ─────────────────
async def test_stability_halow():
    print("\n" + "=" * 60)
    print("TEST 4b: LINK STABILITY (3-min via wlan0)")
    print("=" * 60)
    results = {}
    
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        # Pre-check
        r = await c.run("iwinfo wlan0 info 2>&1 | head -5", timeout=5)
        results["pre_iwinfo"] = r.stdout.strip()
        print(f"  Pre: {r.stdout.strip()[:100]}")
        
        # 3 min = 180 pings via wlan0
        print("  Running 180 pings to AP via wlan0 (3 min)...", flush=True)
        r = await c.run(f"ping -c 180 -i 1 -W 5 -I wlan0 {TUBE} 2>&1", timeout=240)
        results["stability_raw"] = r.stdout
        
        for line in r.stdout.split("\n"):
            if "packets transmitted" in line:
                results["stability_stats"] = line.strip()
                print(f"  Stats: {line.strip()}")
            if "min/avg/max" in line:
                results["stability_rtt"] = line.strip()
                print(f"  RTT: {line.strip()}")
        
        # Post-check
        r = await c.run("iwinfo wlan0 info 2>&1 | head -5", timeout=5)
        results["post_iwinfo"] = r.stdout.strip()
        print(f"  Post: {r.stdout.strip()[:100]}")
    
    save("04b_stability_halow.json", results)
    return results


# ─── POST-TEST snapshot ──────────────────────────────────────────────
async def test_post_wireless():
    print("\n" + "=" * 60)
    print("POST-TEST: FINAL WIRELESS STATUS")
    print("=" * 60)
    results = {}
    
    for label, host, pw in [("edge", EDGE_ETH, "root"), ("tube", TUBE, "root")]:
        c = await ssh_conn(host, password=pw)
        async with c:
            for sub, cmd in [
                ("iwinfo", "iwinfo wlan0 info"),
                ("channel", "morse_cli -i wlan0 channel"),
                ("stats", "morse_cli -i wlan0 stats"),
            ]:
                r = await c.run(cmd + " 2>&1", timeout=10)
                results[f"{label}_{sub}"] = r.stdout
                print(f"  {label}_{sub}: OK" if r.stdout.strip() and "not found" not in r.stdout.lower() and "No such" not in r.stdout else f"  {label}_{sub}: FAILED")
    
    if "tube" in str(results.get("tube_iwinfo", "")):
        # Get assoclist
        c = await ssh_conn(TUBE, password="root")
        async with c:
            r = await c.run("iwinfo wlan0 assoclist 2>&1", timeout=10)
            results["tube_assoclist"] = r.stdout
            print(f"  Assoclist: {r.stdout.strip()[:150]}")
    
    save("05b_wireless_final.json", results)
    return results


# ─── MAIN ─────────────────────────────────────────────────────────────
async def main():
    start = time.time()
    
    print(f"\n{'#' * 60}")
    print(f"# HALOW LINK RESTORE + RE-RUN FAILED TESTS")
    print(f"# Timestamp: {TIMESTAMP}")
    print(f"# Original data: {ORIG_DIR}")
    print(f"# New data: {DATA_DIR}")
    print(f"{'#' * 60}\n")
    
    # Restore link
    ok = await restore_tube()
    if not ok:
        print("ABORT: Could not restore Tube AP")
        return
    
    ok = await restore_edge()
    if not ok:
        print("ABORT: Could not restore Edge STA")
        return
    
    ok = await fix_routing()
    if not ok:
        print("ABORT: Routing fix failed")
        return
    
    # Re-run failed tests
    udp = await test_udp_rerun()
    lat = await test_latency_halow()
    stab = await test_stability_halow()
    post = await test_post_wireless()
    
    # Build combined summary
    summary = {
        "timestamp": TIMESTAMP,
        "original_run": "20260225_182030",
        "topology": "WAN->Ethernet->Tube-AHM(AP)->HaLow_2MHz_Ch14->Edge(STA)",
        "note": "TCP results from original run, UDP/latency/stability re-run",
        # From original run
        "tcp_upload_mbps": 1.45,
        "tcp_download_mbps": 3.92,
        # New UDP
        "udp_results": {k: v for k, v in udp.items() if not k.endswith("_raw")},
        # New latency
        "latency": {k: v for k, v in lat.items() if not k.endswith("_raw")},
        # New stability
        "stability": {k: v for k, v in stab.items() if not k.endswith("_raw")},
    }
    
    save("SUMMARY.json", summary)
    
    elapsed = time.time() - start
    print(f"\n{'#' * 60}")
    print(f"# COMPLETE — {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"{'#' * 60}")
    
    print(f"\n  TCP Upload:   1.45 Mbps (from original run)")
    print(f"  TCP Download: 3.92 Mbps (from original run)")
    print(f"\n  UDP Results (re-run):")
    for k, v in summary["udp_results"].items():
        if isinstance(v, dict) and "mbps" in v:
            print(f"    {k}: {v['mbps']:.3f} Mbps, jitter={v.get('jitter_ms',0):.1f}ms, loss={v.get('loss_pct',0):.1f}%")
        elif isinstance(v, dict) and "error" in v:
            print(f"    {k}: ERROR - {v['error'][:80]}")
    print(f"\n  Latency (re-run):")
    for k, v in summary["latency"].items():
        if isinstance(v, str):
            print(f"    {k}: {v}")
    print(f"\n  Stability (re-run):")
    for k, v in summary["stability"].items():
        if isinstance(v, str) and ("transmitted" in v or "min/avg" in v):
            print(f"    {k}: {v}")

if __name__ == "__main__":
    asyncio.run(main())
