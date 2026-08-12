#!/usr/bin/env python3
"""
Fix routing on Edge Gateway for HaLow-only thesis tests.
Then run the complete 5-test thesis performance suite.

Topology: WAN(192.168.1.1) -> Ethernet -> Tube-AHM AP(192.168.1.103) -> HaLow -> Edge STA(192.168.1.196/wlan0)
SSH management via Edge eth0 (192.168.1.111).
"""
import asyncio
import asyncssh
import json
import time
import os
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────
WAN   = "192.168.1.1"
TUBE  = "192.168.1.103"
EDGE_ETH  = "192.168.1.111"    # SSH management (Ethernet)
EDGE_WLAN = "192.168.1.196"    # HaLow IP
IPERF_PORT = 5201
TIMESTAMP  = datetime.now().strftime("%Y%m%d_%H%M%S")
DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_data", TIMESTAMP)
os.makedirs(DATA_DIR, exist_ok=True)

async def ssh(host, cmd, timeout=30, password=None):
    """Helper: connect + run command."""
    kw = dict(username="root", known_hosts=None, login_timeout=15)
    if password:
        kw["password"] = password
    c = await asyncio.wait_for(asyncssh.connect(host, **kw), timeout=20)
    async with c:
        r = await c.run(cmd, timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")

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

# ────────────────────────────────────────────────────────────────────────
# PASO 0: Fix routing
# ────────────────────────────────────────────────────────────────────────
async def fix_routing():
    print("=" * 60)
    print("PASO 0: FIXING EDGE ROUTING FOR HALOW-ONLY TESTS")
    print("=" * 60)
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        # Clean old routes
        for cmd in [
            "ip route del default via 192.168.1.1 dev eth0 2>/dev/null",
            "ip route del default via 192.168.1.1 dev eth0 proto static src 192.168.1.111 2>/dev/null",
            "ip route del default via 192.168.1.1 dev wlan0 proto static metric 600 2>/dev/null",
            "ip route del 192.168.1.0/24 dev wlan0 proto static scope link metric 600 2>/dev/null",
        ]:
            await c.run(cmd, timeout=5)
        
        # Set wlan0 as default
        await c.run("ip route replace default via 192.168.1.1 dev wlan0 src 192.168.1.196", timeout=5)
        # Host route to WAN via wlan0
        await c.run("ip route replace 192.168.1.1 dev wlan0 src 192.168.1.196", timeout=5)
        # Host route to AP via wlan0
        await c.run("ip route replace 192.168.1.103 dev wlan0 scope link src 192.168.1.196", timeout=5)
        # wlan0 subnet low metric
        await c.run("ip route replace 192.168.1.0/24 dev wlan0 proto static scope link src 192.168.1.196 metric 10", timeout=5)
        # eth0 subnet high metric (keep for SSH management)
        await c.run("ip route replace 192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.111 metric 1000", timeout=5)

        r = await c.run("ip route show", timeout=5)
        print("Routes:", r.stdout)
        
        # Verify
        r = await c.run("ip route get 192.168.1.1", timeout=5)
        wan_route = r.stdout.strip()
        print(f"Route to WAN: {wan_route}")
        assert "wlan0" in wan_route, "ERROR: WAN traffic NOT going through wlan0!"
        
        r = await c.run("ip route get 192.168.1.103", timeout=5)
        ap_route = r.stdout.strip()
        print(f"Route to AP:  {ap_route}")
        assert "wlan0" in ap_route, "ERROR: AP traffic NOT going through wlan0!"
        
        print("✓ All traffic routed through HaLow (wlan0)\n")

# ────────────────────────────────────────────────────────────────────────
# PASO 1: Wireless Status Snapshot
# ────────────────────────────────────────────────────────────────────────
async def test0_wireless_status():
    print("=" * 60)
    print("PRE-TEST: WIRELESS STATUS SNAPSHOT")
    print("=" * 60)
    results = {}
    
    # Edge
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        for label, cmd in [
            ("iwinfo", "iwinfo wlan0 info"),
            ("channel", "morse_cli -i wlan0 channel"),
            ("stats", "morse_cli -i wlan0 stats"),
            ("iface_counters", "cat /proc/net/dev"),
            ("ip_addr", "ip addr show wlan0"),
            ("routes", "ip route show"),
        ]:
            r = await c.run(cmd + " 2>&1", timeout=10)
            results[f"edge_{label}"] = r.stdout
            print(f"  Edge {label}: OK")
    
    # Tube-AHM
    c = await ssh_conn(TUBE, password="root")
    async with c:
        for label, cmd in [
            ("iwinfo", "iwinfo wlan0 info"),
            ("channel", "morse_cli -i wlan0 channel"),
            ("stats", "morse_cli -i wlan0 stats"),
            ("assoclist", "iwinfo wlan0 assoclist"),
        ]:
            r = await c.run(cmd + " 2>&1", timeout=10)
            results[f"tube_{label}"] = r.stdout
            print(f"  Tube {label}: OK")
    
    save("00_wireless_status.json", results)
    
    # Print highlights
    for key in ["edge_iwinfo", "tube_iwinfo"]:
        print(f"\n--- {key} ---")
        print(results[key][:500])
    
    return results

# ────────────────────────────────────────────────────────────────────────
# Helper: manage iperf3 server on WAN
# ────────────────────────────────────────────────────────────────────────
async def ensure_iperf3_server(port=IPERF_PORT):
    """Start iperf3 server on WAN, kill any existing first."""
    w = await ssh_conn(WAN)
    async with w:
        await w.run("killall iperf3 2>/dev/null", timeout=5)
        await asyncio.sleep(2)
        # Use iperf3 built-in daemon mode (-D) and shell backgrounding as fallback
        r = await w.run(f"iperf3 -s -D -p {port} 2>&1 || sh -c 'iperf3 -s -p {port} >/dev/null 2>&1 &'", timeout=10)
        if r.stdout.strip():
            print(f"  iperf3 start output: {r.stdout.strip()[:100]}")
        await asyncio.sleep(2)
        # Check if process is running
        r = await w.run("ps w 2>/dev/null | grep iperf3 | grep -v grep", timeout=5)
        procs = r.stdout.strip()
        print(f"  WAN iperf3 server: {procs[:120] if procs else 'NOT FOUND'}")
        if not procs:
            raise RuntimeError("Failed to start iperf3 server on WAN")
    return True

async def kill_iperf3_server():
    w = await ssh_conn(WAN)
    async with w:
        await w.run("killall iperf3 2>/dev/null", timeout=5)

# ────────────────────────────────────────────────────────────────────────
# TEST 1: TCP throughput (Upload + Download)
# ────────────────────────────────────────────────────────────────────────
async def test1_tcp_throughput():
    print("\n" + "=" * 60)
    print("TEST 1: TCP THROUGHPUT (Upload + Download)")
    print("=" * 60)
    results = {}
    
    await ensure_iperf3_server()
    
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        # Record wlan0 counters before
        r = await c.run("cat /proc/net/dev | grep wlan0", timeout=5)
        results["wlan0_before"] = r.stdout.strip()
        print(f"  wlan0 before: {r.stdout.strip()[:80]}")
        
        # UPLOAD: Edge -> WAN (30s)
        print("  Running TCP Upload (30s)...", flush=True)
        r = await c.run(
            f"iperf3 -c {WAN} -p {IPERF_PORT} -B {EDGE_WLAN} -t 30 -J 2>&1",
            timeout=60
        )
        results["tcp_upload_raw"] = r.stdout
        try:
            j = json.loads(r.stdout)
            bps = j["end"]["sum_sent"]["bits_per_second"]
            print(f"  TCP Upload: {bps/1e6:.2f} Mbps")
            results["tcp_upload_mbps"] = bps / 1e6
        except Exception as e:
            print(f"  TCP Upload parse error: {e}")
            print(f"  Raw: {r.stdout[:300]}")
            results["tcp_upload_mbps"] = 0
        
        await asyncio.sleep(3)
        
        # Restart iperf3 server for download test
        await kill_iperf3_server()
        await asyncio.sleep(2)
        await ensure_iperf3_server()
        
        # DOWNLOAD: WAN -> Edge (30s, reverse)
        print("  Running TCP Download (30s)...", flush=True)
        r = await c.run(
            f"iperf3 -c {WAN} -p {IPERF_PORT} -B {EDGE_WLAN} -t 30 -R -J 2>&1",
            timeout=60
        )
        results["tcp_download_raw"] = r.stdout
        try:
            j = json.loads(r.stdout)
            bps = j["end"]["sum_received"]["bits_per_second"]
            print(f"  TCP Download: {bps/1e6:.2f} Mbps")
            results["tcp_download_mbps"] = bps / 1e6
        except Exception as e:
            print(f"  TCP Download parse error: {e}")
            print(f"  Raw: {r.stdout[:300]}")
            results["tcp_download_mbps"] = 0
        
        # Record wlan0 counters after
        r = await c.run("cat /proc/net/dev | grep wlan0", timeout=5)
        results["wlan0_after"] = r.stdout.strip()
        print(f"  wlan0 after:  {r.stdout.strip()[:80]}")
    
    save("01_tcp_throughput.json", results)
    await kill_iperf3_server()
    return results

# ────────────────────────────────────────────────────────────────────────
# TEST 2: UDP throughput at multiple rates
# ────────────────────────────────────────────────────────────────────────
async def test2_udp_throughput():
    print("\n" + "=" * 60)
    print("TEST 2: UDP THROUGHPUT (Multiple Rates)")
    print("=" * 60)
    results = {}
    
    # Test at multiple target rates
    rates = ["500K", "1M", "2M", "3M", "5M"]
    
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        for rate in rates:
            await kill_iperf3_server()
            await asyncio.sleep(2)
            await ensure_iperf3_server()
            
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
                print(f"    {rate}: {bps/1e6:.2f} Mbps, jitter={jitter:.1f}ms, loss={loss_pct:.1f}%")
                results[f"udp_{rate}"] = {
                    "mbps": bps / 1e6,
                    "jitter_ms": jitter,
                    "loss_pct": loss_pct,
                    "lost_packets": lost,
                    "total_packets": total,
                }
            except Exception as e:
                print(f"    {rate}: parse error: {e}")
                print(f"    Raw: {r.stdout[:200]}")
                results[f"udp_{rate}"] = {"error": str(e)}
            
            await asyncio.sleep(2)
    
    save("02_udp_throughput.json", results)
    await kill_iperf3_server()
    return results

# ────────────────────────────────────────────────────────────────────────
# TEST 3: Latency (ping)
# ────────────────────────────────────────────────────────────────────────
async def test3_latency():
    print("\n" + "=" * 60)
    print("TEST 3: LATENCY (Ping)")
    print("=" * 60)
    results = {}
    
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        # Ping AP (1 hop HaLow)
        print("  Ping AP (100 packets)...", flush=True)
        r = await c.run(f"ping -c 100 -W 5 -I wlan0 {TUBE} 2>&1", timeout=120)
        results["ping_ap_raw"] = r.stdout
        print(f"  AP ping done")
        
        # Ping WAN (2 hops: HaLow + Ethernet)
        print("  Ping WAN (100 packets)...", flush=True)
        r = await c.run(f"ping -c 100 -W 5 {WAN} 2>&1", timeout=120)
        results["ping_wan_raw"] = r.stdout
        print(f"  WAN ping done")
        
        # Parse results
        for label, key in [("AP", "ping_ap_raw"), ("WAN", "ping_wan_raw")]:
            raw = results[key]
            # Extract stats line
            for line in raw.split("\n"):
                if "packets transmitted" in line:
                    results[f"ping_{label.lower()}_stats"] = line.strip()
                    print(f"  {label}: {line.strip()}")
                if "min/avg/max" in line or "rtt" in line.lower():
                    results[f"ping_{label.lower()}_rtt"] = line.strip()
                    print(f"  {label}: {line.strip()}")
    
    save("03_latency.json", results)
    return results

# ────────────────────────────────────────────────────────────────────────
# TEST 4: Link Stability (15-min ping)
# ────────────────────────────────────────────────────────────────────────
async def test4_stability():
    print("\n" + "=" * 60)
    print("TEST 4: LINK STABILITY (5-min continuous ping)")
    print("=" * 60)
    results = {}
    
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        # 5 minutes = 300 pings
        print("  Running 300 pings to AP (5 min)...", flush=True)
        r = await c.run(f"ping -c 300 -i 1 -W 5 -I wlan0 {TUBE} 2>&1", timeout=360)
        results["stability_raw"] = r.stdout
        
        for line in r.stdout.split("\n"):
            if "packets transmitted" in line:
                results["stability_stats"] = line.strip()
                print(f"  Stats: {line.strip()}")
            if "min/avg/max" in line or "rtt" in line.lower():
                results["stability_rtt"] = line.strip()
                print(f"  RTT: {line.strip()}")
    
    save("04_stability.json", results)
    return results

# ────────────────────────────────────────────────────────────────────────
# TEST 5: Wireless Stats (post-test snapshot)
# ────────────────────────────────────────────────────────────────────────
async def test5_wireless_stats():
    print("\n" + "=" * 60)
    print("TEST 5: POST-TEST WIRELESS STATS")
    print("=" * 60)
    results = {}
    
    # Edge
    c = await ssh_conn(EDGE_ETH, password="root")
    async with c:
        for label, cmd in [
            ("iwinfo", "iwinfo wlan0 info"),
            ("channel", "morse_cli -i wlan0 channel"),
            ("stats", "morse_cli -i wlan0 stats"),
            ("counters", "cat /proc/net/dev"),
        ]:
            r = await c.run(cmd + " 2>&1", timeout=10)
            results[f"edge_{label}"] = r.stdout
    
    # Tube-AHM
    c = await ssh_conn(TUBE, password="root")
    async with c:
        for label, cmd in [
            ("iwinfo", "iwinfo wlan0 info"),
            ("channel", "morse_cli -i wlan0 channel"),
            ("stats", "morse_cli -i wlan0 stats"),
            ("assoclist", "iwinfo wlan0 assoclist"),
        ]:
            r = await c.run(cmd + " 2>&1", timeout=10)
            results[f"tube_{label}"] = r.stdout
    
    save("05_wireless_stats.json", results)
    
    print("\n--- Edge wireless ---")
    print(results.get("edge_iwinfo", "N/A")[:400])
    print("\n--- Tube wireless ---")
    print(results.get("tube_iwinfo", "N/A")[:400])
    
    return results

# ────────────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────────────
async def main():
    start = time.time()
    all_results = {"timestamp": TIMESTAMP, "topology": "WAN->Ethernet->Tube-AHM(AP)->HaLow_2MHz_Ch14->Edge(STA)"}
    
    print(f"\n{'#' * 60}")
    print(f"# IEEE 802.11ah (HaLow) THESIS PERFORMANCE TESTS")
    print(f"# Timestamp: {TIMESTAMP}")
    print(f"# Data dir:  {DATA_DIR}")
    print(f"# Topology:  WAN({WAN}) -> ETH -> Tube-AHM AP({TUBE})")
    print(f"#            -> HaLow 2MHz Ch14 -> Edge STA({EDGE_WLAN})")
    print(f"{'#' * 60}\n")
    
    # Step 0: Fix routing
    await fix_routing()
    
    # Step 0.5: Pre-test wireless status
    ws = await test0_wireless_status()
    all_results["pre_wireless"] = {k: v[:200] for k, v in ws.items()}
    
    # Test 1: TCP throughput
    t1 = await test1_tcp_throughput()
    all_results["tcp_upload_mbps"] = t1.get("tcp_upload_mbps", 0)
    all_results["tcp_download_mbps"] = t1.get("tcp_download_mbps", 0)
    
    # Test 2: UDP throughput
    t2 = await test2_udp_throughput()
    all_results["udp_results"] = {k: v for k, v in t2.items() if not k.endswith("_raw")}
    
    # Test 3: Latency
    t3 = await test3_latency()
    all_results["latency"] = {k: v for k, v in t3.items() if not k.endswith("_raw")}
    
    # Test 4: Stability
    t4 = await test4_stability()
    all_results["stability"] = {k: v for k, v in t4.items() if not k.endswith("_raw")}
    
    # Test 5: Post-test wireless stats
    t5 = await test5_wireless_stats()
    all_results["post_wireless"] = {k: v[:200] for k, v in t5.items()}
    
    elapsed = time.time() - start
    all_results["total_elapsed_s"] = elapsed
    
    save("SUMMARY.json", all_results)
    
    # ── Final Summary ──
    print(f"\n{'#' * 60}")
    print(f"# TESTS COMPLETE — Elapsed: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"# Data saved in: {DATA_DIR}")
    print(f"{'#' * 60}")
    print(f"\n  TCP Upload:   {all_results.get('tcp_upload_mbps', 0):.2f} Mbps")
    print(f"  TCP Download: {all_results.get('tcp_download_mbps', 0):.2f} Mbps")
    print(f"\n  UDP Results:")
    for k, v in all_results.get("udp_results", {}).items():
        if isinstance(v, dict) and "mbps" in v:
            print(f"    {k}: {v['mbps']:.2f} Mbps, jitter={v.get('jitter_ms',0):.1f}ms, loss={v.get('loss_pct',0):.1f}%")
    print(f"\n  Latency:")
    for k, v in all_results.get("latency", {}).items():
        print(f"    {k}: {v}")
    print(f"\n  Stability:")
    for k, v in all_results.get("stability", {}).items():
        print(f"    {k}: {v}")
    print()

if __name__ == "__main__":
    asyncio.run(main())
