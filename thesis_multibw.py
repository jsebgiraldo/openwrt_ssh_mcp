#!/usr/bin/env python3
"""
Multi-BW HaLow comparison test for thesis.

Tests 2 MHz, 4 MHz, and 8 MHz bandwidths on the same HaLow link.
For each BW:
  1. Reconfigure AP (Tube) and STA (Edge) 
  2. Establish association using fix_halow9 sequence
  3. Set up routing to force traffic over HaLow
  4. Run: ping, iperf3 TCP upload/download, iperf3 UDP, wireless stats
  5. Save results

Channel mapping (near 908 MHz):
  - 2 MHz: Channel 14, 909.0 MHz, op_class 69
  - 4 MHz: Channel 8, 906.0 MHz, op_class 70
  - 8 MHz: Channel 12, 908.0 MHz, op_class 71
"""
import asyncio
import asyncssh
import json
import csv
import os
import re
import time
from datetime import datetime

# === Devices (SSH via Ethernet for management) ===
EDGE_ETH = {"host": "192.168.1.111", "user": "root", "password": "root", "name": "Edge (Eth)"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root", "name": "Tube-AHM"}

EDGE_HALOW_IP = "192.168.1.196"
TUBE_IP = "192.168.1.103"
EDGE_WLAN_MAC = "0c:bf:74:1c:de:87"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_multibw")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# BW configs: (bw_mhz, channel, freq_khz, oper_bw, prim_bw, description)
BW_CONFIGS = [
    {"bw": 2, "channel": "14", "s1g_chanbw": "2", "freq_khz": 909000,
     "oper_bw": 2, "prim_bw": 2, "prim_idx": 0, "desc": "2 MHz (ch14, 909 MHz)"},
    {"bw": 4, "channel": "8", "s1g_chanbw": "4", "freq_khz": 906000,
     "oper_bw": 4, "prim_bw": 2, "prim_idx": 1, "desc": "4 MHz (ch8, 906 MHz)"},
    {"bw": 8, "channel": "12", "s1g_chanbw": "8", "freq_khz": 908000,
     "oper_bw": 8, "prim_bw": 2, "prim_idx": 3, "desc": "8 MHz (ch12, 908 MHz)"},
]


async def ssh_run(dev, cmd, timeout=30):
    """Run SSH command with retry."""
    for attempt in range(3):
        try:
            async with asyncssh.connect(
                dev["host"], port=22, username=dev["user"],
                password=dev["password"], known_hosts=None, login_timeout=15
            ) as conn:
                r = await conn.run(cmd, timeout=timeout)
                return r.stdout.strip()
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(3)
            else:
                raise Exception(f"SSH to {dev['host']} failed after 3 attempts: {e}")


async def ssh_run_long(dev, cmd, timeout=120):
    return await ssh_run(dev, cmd, timeout=timeout)


def save_json(filename, data):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"    -> JSON: {path}")
    return path


def save_csv(filename, headers, rows):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"    -> CSV: {path}")
    return path


# =================================================================
# STEP 1: Configure BW on both devices
# =================================================================
async def configure_bw(cfg):
    """Configure AP and STA for a specific bandwidth."""
    bw = cfg["bw"]
    ch = cfg["channel"]
    chanbw = cfg["s1g_chanbw"]
    
    print(f"\n{'='*60}")
    print(f"  CONFIGURING {cfg['desc']}")
    print(f"{'='*60}")
    
    # 1a. Configure Tube AP
    print(f"\n  [1a] Configuring Tube AP: channel={ch}, s1g_chanbw={chanbw}...")
    await ssh_run(TUBE, 
        f"uci set wireless.radio0.channel='{ch}'; "
        f"uci set wireless.radio0.s1g_chanbw='{chanbw}'; "
        f"uci commit wireless"
    )
    
    # Restart Tube AP
    print(f"  [1b] Restarting Tube AP wifi...")
    try:
        await ssh_run(TUBE, "wifi down; sleep 2; wifi up", timeout=30)
    except:
        pass
    
    # Wait for AP to come up
    print(f"  [1c] Waiting 15s for Tube AP to stabilize...")
    await asyncio.sleep(15)
    
    # Verify AP
    tube_info = await ssh_run(TUBE, "iwinfo wlan0 info 2>/dev/null | head -5")
    print(f"    Tube: {tube_info}")
    tube_ch = await ssh_run(TUBE, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"    {tube_ch}")
    
    # 1b. Configure Edge STA  
    print(f"\n  [2a] Configuring Edge STA: channel={ch}, s1g_chanbw={chanbw}...")
    await ssh_run(EDGE_ETH,
        f"uci set wireless.radio0.channel='{ch}'; "
        f"uci set wireless.radio0.s1g_chanbw='{chanbw}'; "
        f"uci set wireless.radio0.txpower='21'; "
        f"uci commit wireless"
    )
    
    # Apply fix_halow9 sequence
    print(f"  [2b] Running fix_halow9 sequence on Edge...")
    
    # wifi down/up
    try:
        await ssh_run(EDGE_ETH, "wifi down; sleep 2; wifi up", timeout=30)
    except:
        pass
    await asyncio.sleep(10)
    
    # Read generated wpa_supplicant config for S1G params
    wpa_conf = await ssh_run(EDGE_ETH, "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null")
    print(f"    WPA config:\n{wpa_conf}")
    
    # Extract S1G params from generated config
    op_class = None
    prim_chwidth = None
    prim_1mhz_idx = None
    for line in wpa_conf.split('\n'):
        if 'op_class=' in line:
            m = re.search(r'op_class=(\d+)', line)
            if m: op_class = int(m.group(1))
        if 's1g_prim_chwidth=' in line:
            m = re.search(r's1g_prim_chwidth=(\d+)', line)
            if m: prim_chwidth = int(m.group(1))
        if 's1g_prim_1mhz_chan_index=' in line:
            m = re.search(r's1g_prim_1mhz_chan_index=(\d+)', line)
            if m: prim_1mhz_idx = int(m.group(1))
    
    print(f"    Extracted: op_class={op_class}, prim_chwidth={prim_chwidth}, prim_1mhz_idx={prim_1mhz_idx}")
    
    # Kill wpa_supplicant_s1g
    print(f"  [2c] Kill wpa_supplicant_s1g, set morse_cli channel, restart...")
    await ssh_run(EDGE_ETH, "killall wpa_supplicant_s1g 2>/dev/null; sleep 1; echo killed")
    await asyncio.sleep(2)
    
    # Set morse_cli channel
    freq = cfg["freq_khz"]
    obw = cfg["oper_bw"]
    pbw = cfg["prim_bw"]
    pidx = prim_1mhz_idx if prim_1mhz_idx is not None else cfg["prim_idx"]
    
    morse_cmd = f"morse_cli -i wlan0 channel -c {freq} -o {obw} -p {pbw} -n {pidx}"
    print(f"    Running: {morse_cmd}")
    out = await ssh_run(EDGE_ETH, morse_cmd)
    print(f"    {out}")
    
    # Set TX power
    await ssh_run(EDGE_ETH, "iw dev wlan0 set txpower fixed 2100 2>/dev/null; echo txpower_set")
    
    # Disable power save
    await ssh_run(EDGE_ETH, "iw dev wlan0 set power_save off 2>/dev/null; echo ps_off")
    
    await asyncio.sleep(3)
    
    # Restart wpa_supplicant_s1g
    await ssh_run(EDGE_ETH,
        "/usr/sbin/wpa_supplicant_s1g -t -D nl80211 -s -i wlan0 "
        "-c /var/run/wpa_supplicant-wlan0.conf -B"
    )
    
    # Wait for association
    print(f"  [2d] Waiting up to 30s for association...")
    associated = False
    for i in range(15):
        await asyncio.sleep(2)
        info = await ssh_run(EDGE_ETH, "iwinfo wlan0 info 2>/dev/null | grep ESSID")
        if "UNAL-HaLow-Tesis" in info:
            print(f"    ASSOCIATED after {(i+1)*2}s!")
            associated = True
            break
        print(f"    {(i+1)*2}s: not yet... ({info})")
    
    if not associated:
        print(f"    *** ASSOCIATION FAILED at {cfg['desc']} ***")
        return False
    
    # Set up routing
    print(f"  [3a] Setting up routing...")
    await ssh_run(EDGE_ETH, 
        f"ip route replace {TUBE_IP}/32 dev wlan0 src {EDGE_HALOW_IP}"
    )
    await ssh_run(TUBE,
        f"ip neigh replace {EDGE_HALOW_IP} dev br-ahwlan lladdr {EDGE_WLAN_MAC} nud permanent"
    )
    
    # Verify
    print(f"  [3b] Verification...")
    info = await ssh_run(EDGE_ETH, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit Rate|Channel'")
    print(f"    Edge: {info}")
    ch_info = await ssh_run(EDGE_ETH, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"    {ch_info}")
    
    return True


# =================================================================
# STEP 2: Run tests at current BW
# =================================================================
async def run_tests(cfg):
    """Run all tests at the current bandwidth configuration."""
    bw = cfg["bw"]
    desc = cfg["desc"]
    results = {"config": cfg, "timestamp": TIMESTAMP}
    
    print(f"\n{'='*60}")
    print(f"  RUNNING TESTS: {desc}")
    print(f"{'='*60}")
    
    # --- Wireless stats snapshot ---
    print(f"\n  [T0] Wireless stats...")
    try:
        edge_info = await ssh_run(EDGE_ETH, "iwinfo wlan0 info 2>/dev/null")
        tube_assoc = await ssh_run(TUBE, "iwinfo wlan0 assoclist 2>/dev/null")
        edge_station = await ssh_run(EDGE_ETH, "iw dev wlan0 station dump 2>/dev/null")
        tube_station = await ssh_run(TUBE, "iw dev wlan0 station dump 2>/dev/null")
        
        results["wireless"] = {
            "edge_info": edge_info,
            "tube_assoclist": tube_assoc,
            "edge_station": edge_station,
            "tube_station": tube_station,
        }
        
        # Extract signal levels
        sig_match = re.search(r'Signal:\s*(-?\d+)', edge_info)
        results["edge_signal_dbm"] = int(sig_match.group(1)) if sig_match else None
        
        tube_sig = re.search(r'(-?\d+)\s*dBm', tube_assoc)
        results["tube_signal_dbm"] = int(tube_sig.group(1)) if tube_sig else None
        
        print(f"    Edge signal: {results['edge_signal_dbm']} dBm")
        print(f"    Tube sees Edge: {results['tube_signal_dbm']} dBm")
    except Exception as e:
        print(f"    Stats error: {e}")
    
    # --- Ping test ---
    print(f"\n  [T1] Ping test (20 pings via HaLow)...")
    try:
        out = await ssh_run_long(EDGE_ETH,
            f"ping -c 20 -W 5 -i 1 {TUBE_IP} 2>&1",
            timeout=60
        )
        
        latencies = []
        for line in out.split('\n'):
            m = re.search(r'time[=<](\d+\.?\d*)', line)
            if m:
                latencies.append(float(m.group(1)))
        
        loss_match = re.search(r'(\d+)% packet loss', out)
        loss_pct = float(loss_match.group(1)) if loss_match else 100
        
        rtt_match = re.search(r'= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', out)
        rtt = {}
        if rtt_match:
            rtt = {
                "min": float(rtt_match.group(1)),
                "avg": float(rtt_match.group(2)),
                "max": float(rtt_match.group(3)),
                "mdev": float(rtt_match.group(4)),
            }
        
        results["ping"] = {
            "total_sent": 20,
            "received": len(latencies),
            "loss_pct": loss_pct,
            "rtt": rtt,
            "latencies": latencies,
        }
        print(f"    Received: {len(latencies)}/20, Loss: {loss_pct}%")
        if rtt:
            print(f"    RTT min/avg/max: {rtt['min']}/{rtt['avg']}/{rtt['max']} ms")
    except Exception as e:
        print(f"    Ping error: {e}")
        results["ping"] = {"error": str(e)}
    
    # --- iperf3 TCP Upload (Edge → Tube) ---
    print(f"\n  [T2] iperf3 TCP Upload (Edge→Tube, 30s)...")
    try:
        await ssh_run(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
    except:
        pass
    await asyncio.sleep(1)
    
    try:
        await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
        await asyncio.sleep(2)
        
        raw = await ssh_run_long(EDGE_ETH,
            f"iperf3 -c {TUBE_IP} -B {EDGE_HALOW_IP} -t 30 -i 1 -J 2>&1",
            timeout=60
        )
        
        try:
            data = json.loads(raw)
            end = data.get("end", {}).get("sum_sent", {})
            avg_mbps = end.get("bits_per_second", 0) / 1e6
            retransmits = end.get("retransmits", "N/A")
            
            intervals = data.get("intervals", [])
            throughputs = [iv.get("sum", {}).get("bits_per_second", 0) / 1e6 for iv in intervals]
            
            results["tcp_upload"] = {
                "avg_mbps": round(avg_mbps, 3),
                "retransmits": retransmits,
                "min_mbps": round(min(throughputs), 3) if throughputs else 0,
                "max_mbps": round(max(throughputs), 3) if throughputs else 0,
                "samples": len(throughputs),
                "throughputs": [round(t, 3) for t in throughputs],
                "raw_json": data,
            }
            print(f"    Avg: {avg_mbps:.3f} Mbps | Retrans: {retransmits}")
        except json.JSONDecodeError:
            print(f"    Raw output (not JSON):\n    {raw[:500]}")
            results["tcp_upload"] = {"error": "not_json", "raw": raw[:1000]}
    except Exception as e:
        print(f"    Upload error: {e}")
        results["tcp_upload"] = {"error": str(e)}
    
    try:
        await ssh_run(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
    except:
        pass
    await asyncio.sleep(3)
    
    # --- iperf3 TCP Download (Tube → Edge) ---
    print(f"\n  [T3] iperf3 TCP Download (Tube→Edge, 30s)...")
    try:
        # Start server on Edge bound to HaLow IP
        await ssh_run(EDGE_ETH, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        await asyncio.sleep(1)
        await ssh_run(EDGE_ETH, f"iperf3 -s -B {EDGE_HALOW_IP} -D -1", timeout=10)
        await asyncio.sleep(2)
        
        raw = await ssh_run_long(TUBE,
            f"iperf3 -c {EDGE_HALOW_IP} -t 30 -i 1 -J 2>&1",
            timeout=90
        )
        
        try:
            data = json.loads(raw)
            end = data.get("end", {}).get("sum_sent", {})
            avg_mbps = end.get("bits_per_second", 0) / 1e6
            retransmits = end.get("retransmits", "N/A")
            
            intervals = data.get("intervals", [])
            throughputs = [iv.get("sum", {}).get("bits_per_second", 0) / 1e6 for iv in intervals]
            
            results["tcp_download"] = {
                "avg_mbps": round(avg_mbps, 3),
                "retransmits": retransmits,
                "min_mbps": round(min(throughputs), 3) if throughputs else 0,
                "max_mbps": round(max(throughputs), 3) if throughputs else 0,
                "samples": len(throughputs),
                "throughputs": [round(t, 3) for t in throughputs],
                "raw_json": data,
            }
            print(f"    Avg: {avg_mbps:.3f} Mbps | Retrans: {retransmits}")
        except json.JSONDecodeError:
            print(f"    Raw output (not JSON):\n    {raw[:500]}")
            results["tcp_download"] = {"error": "not_json", "raw": raw[:1000]}
    except Exception as e:
        print(f"    Download error: {e}")
        results["tcp_download"] = {"error": str(e)}
    
    try:
        await ssh_run(EDGE_ETH, "killall iperf3 2>/dev/null; echo ok", timeout=5)
    except:
        pass
    await asyncio.sleep(3)
    
    # --- iperf3 UDP at various rates ---
    print(f"\n  [T4] iperf3 UDP (Edge→Tube, various rates)...")
    rates = ["0.5M", "1M", "2M", "4M", "8M"]
    udp_results = []
    
    for rate in rates:
        print(f"    --- UDP @ {rate} ---")
        try:
            await ssh_run(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
        await asyncio.sleep(1)
        
        try:
            await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
            await asyncio.sleep(2)
            
            raw = await ssh_run_long(EDGE_ETH,
                f"iperf3 -c {TUBE_IP} -B {EDGE_HALOW_IP} -u -b {rate} -t 10 -i 1 -J 2>&1",
                timeout=30
            )
            
            data = json.loads(raw)
            udp_end = data.get("end", {}).get("sum", {})
            actual_mbps = udp_end.get("bits_per_second", 0) / 1e6
            jitter_ms = udp_end.get("jitter_ms", 0)
            lost = udp_end.get("lost_packets", 0)
            total = udp_end.get("packets", 1)
            loss_pct = udp_end.get("lost_percent", (lost / total * 100) if total else 0)
            
            udp_results.append({
                "target_rate": rate,
                "actual_mbps": round(actual_mbps, 3),
                "jitter_ms": round(jitter_ms, 3),
                "lost_packets": lost,
                "total_packets": total,
                "loss_pct": round(loss_pct, 2),
            })
            print(f"      Actual: {actual_mbps:.3f} Mbps | Jitter: {jitter_ms:.2f}ms | Loss: {loss_pct:.1f}%")
        except Exception as e:
            print(f"      Error: {e}")
            udp_results.append({"target_rate": rate, "error": str(e)})
        
        try:
            await ssh_run(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
        await asyncio.sleep(2)
    
    results["udp"] = udp_results
    
    # --- Final wireless stats ---
    print(f"\n  [T5] Final wireless stats after tests...")
    try:
        edge_info = await ssh_run(EDGE_ETH, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit Rate|Channel'")
        tube_assoc = await ssh_run(TUBE, "iwinfo wlan0 assoclist 2>/dev/null")
        print(f"    Edge: {edge_info}")
        print(f"    Tube assoclist: {tube_assoc}")
        results["wireless_final"] = {"edge": edge_info, "tube_assoc": tube_assoc}
    except Exception as e:
        print(f"    Error: {e}")
    
    return results


# =================================================================
# MAIN
# =================================================================
async def main():
    print("=" * 60)
    print("  MULTI-BW HALOW COMPARISON TEST")
    print(f"  Timestamp: {TIMESTAMP}")
    print(f"  Topology: WAN--Eth--Tube(AP)===HaLow===Edge(STA)")
    print("=" * 60)
    
    all_results = {}
    
    for cfg in BW_CONFIGS:
        bw = cfg["bw"]
        desc = cfg["desc"]
        
        # Configure
        ok = await configure_bw(cfg)
        if not ok:
            print(f"\n  *** SKIPPING TESTS for {desc} - association failed ***")
            all_results[f"{bw}MHz"] = {"config": cfg, "error": "association_failed"}
            continue
        
        # Run tests
        results = await run_tests(cfg)
        all_results[f"{bw}MHz"] = results
        
        # Save per-BW results
        save_json(f"results_{bw}mhz_{TIMESTAMP}.json", results)
        
        print(f"\n  {'='*60}")
        print(f"  COMPLETED: {desc}")
        print(f"  {'='*60}")
        await asyncio.sleep(5)
    
    # Save combined results
    save_json(f"all_results_{TIMESTAMP}.json", all_results)
    
    # Print summary
    print("\n\n" + "=" * 60)
    print("  SUMMARY - MULTI-BW COMPARISON")
    print("=" * 60)
    print(f"{'BW':>6} | {'Ping Loss':>10} | {'RTT Avg':>10} | {'TCP Up':>10} | {'TCP Down':>10} | {'Edge Sig':>10} | {'Tube Sig':>10}")
    print("-" * 85)
    
    for bw_key in ["2MHz", "4MHz", "8MHz"]:
        r = all_results.get(bw_key, {})
        if "error" in r:
            print(f"{bw_key:>6} | {'FAILED':^10} | {'---':^10} | {'---':^10} | {'---':^10} | {'---':^10} | {'---':^10}")
            continue
        
        ping = r.get("ping", {})
        tcp_up = r.get("tcp_upload", {})
        tcp_down = r.get("tcp_download", {})
        
        ping_loss = f"{ping.get('loss_pct', '?')}%"
        rtt_avg = f"{ping.get('rtt', {}).get('avg', '?')}ms" if ping.get('rtt') else "?"
        up_mbps = f"{tcp_up.get('avg_mbps', '?')}Mbps" if not tcp_up.get('error') else "ERR"
        down_mbps = f"{tcp_down.get('avg_mbps', '?')}Mbps" if not tcp_down.get('error') else "ERR"
        edge_sig = f"{r.get('edge_signal_dbm', '?')}dBm"
        tube_sig = f"{r.get('tube_signal_dbm', '?')}dBm"
        
        print(f"{bw_key:>6} | {ping_loss:>10} | {rtt_avg:>10} | {up_mbps:>10} | {down_mbps:>10} | {edge_sig:>10} | {tube_sig:>10}")
    
    # Generate CSV summary
    csv_rows = []
    for bw_key in ["2MHz", "4MHz", "8MHz"]:
        r = all_results.get(bw_key, {})
        if "error" in r:
            csv_rows.append([bw_key, "FAILED", "", "", "", "", "", ""])
            continue
        ping = r.get("ping", {})
        tcp_up = r.get("tcp_upload", {})
        tcp_down = r.get("tcp_download", {})
        csv_rows.append([
            bw_key,
            r.get("edge_signal_dbm"),
            r.get("tube_signal_dbm"),
            ping.get("loss_pct"),
            ping.get("rtt", {}).get("avg"),
            tcp_up.get("avg_mbps") if not tcp_up.get("error") else "ERR",
            tcp_down.get("avg_mbps") if not tcp_down.get("error") else "ERR",
            tcp_up.get("retransmits") if not tcp_up.get("error") else "",
        ])
    
    save_csv(f"comparison_summary_{TIMESTAMP}.csv",
             ["bandwidth", "edge_signal_dbm", "tube_signal_dbm", "ping_loss_pct",
              "rtt_avg_ms", "tcp_upload_mbps", "tcp_download_mbps", "tcp_retransmits"],
             csv_rows)
    
    print(f"\n  Results saved to: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
