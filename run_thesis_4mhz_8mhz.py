#!/usr/bin/env python3
"""
Multi-BW HaLow tests: 4 MHz and 8 MHz only.
(2 MHz already tested and saved in thesis_package_20260225)

Incorporates all fixes from successful 2 MHz run:
  - Routing isolation: arp_ignore=1, arp_announce=2 on eth0
  - TCP download using -R flag (Edge initiates, Tube sends)
  - wlan0 packet counter verification (HaLow proof)
  - Windows encoding fix

Channel mapping:
  - 4 MHz: Channel 8, 906.0 MHz, s1g_chanbw=4
  - 8 MHz: Channel 12, 908.0 MHz, s1g_chanbw=8

At the end, restores 2 MHz (ch14, 909 MHz) working config.
"""
import asyncio
import asyncssh
import json
import csv
import os
import re
import sys
import io
import time
from datetime import datetime

# Windows encoding fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# === Devices ===
EDGE = {"host": "192.168.1.111", "user": "root", "password": "root", "name": "Edge (Eth)"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root", "name": "Tube-AHM"}

EDGE_HALOW_IP = "192.168.1.196"
TUBE_IP = "192.168.1.103"
EDGE_WLAN_MAC = "0c:bf:74:1c:de:87"
SSID = "UNAL-HaLow-Tesis"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_multibw")
os.makedirs(OUTPUT_DIR, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# BW configs to test (4 MHz and 8 MHz only; 2 MHz already done)
BW_CONFIGS = [
    {"bw": 4, "channel": "8", "s1g_chanbw": "4", "freq_khz": 906000,
     "oper_bw": 4, "prim_bw": 2, "prim_idx": 1, "desc": "4 MHz (ch8, 906 MHz)"},
    {"bw": 8, "channel": "12", "s1g_chanbw": "8", "freq_khz": 908000,
     "oper_bw": 8, "prim_bw": 2, "prim_idx": 3, "desc": "8 MHz (ch12, 908 MHz)"},
]

# Restore config (2 MHz, our known working config)
RESTORE_CONFIG = {"channel": "14", "s1g_chanbw": "2", "desc": "2 MHz (ch14, 909 MHz)"}


async def ssh_run(dev, cmd_str, timeout=30):
    """Run SSH command with retry."""
    for attempt in range(3):
        try:
            async with asyncssh.connect(
                dev["host"], port=22, username=dev["user"],
                password=dev["password"], known_hosts=None, login_timeout=15
            ) as conn:
                r = await conn.run(cmd_str, timeout=timeout)
                return r.stdout.strip()
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(3)
            else:
                return f"ERROR: {e}"


async def ssh_run_long(dev, cmd_str, timeout=120):
    return await ssh_run(dev, cmd_str, timeout=timeout)


def save_json(filename, data):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"  -> Saved: {path}", flush=True)
    return path


def save_csv(filename, headers, rows):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  -> CSV: {path}", flush=True)
    return path


# =================================================================
# CONFIGURE BW
# =================================================================
async def configure_bw(cfg):
    """Configure AP and STA for a specific bandwidth."""
    ch = cfg["channel"]
    chanbw = cfg["s1g_chanbw"]
    desc = cfg["desc"]

    print(f"\n{'='*60}", flush=True)
    print(f"  CONFIGURING: {desc}", flush=True)
    print(f"{'='*60}", flush=True)

    # 1. Configure and restart Tube AP
    print(f"\n  [1] Tube AP: channel={ch}, s1g_chanbw={chanbw}...", flush=True)
    await ssh_run(TUBE,
        f"uci set wireless.radio0.channel='{ch}'; "
        f"uci set wireless.radio0.s1g_chanbw='{chanbw}'; "
        f"uci commit wireless"
    )
    try:
        await ssh_run(TUBE, "wifi down; sleep 2; wifi up", timeout=30)
    except:
        pass
    print(f"  Waiting 18s for Tube AP...", flush=True)
    await asyncio.sleep(18)

    # Verify AP
    tube_info = await ssh_run(TUBE, "iwinfo wlan0 info 2>/dev/null | head -5")
    print(f"    Tube: {tube_info}", flush=True)
    tube_ch = await ssh_run(TUBE, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"    Channel: {tube_ch}", flush=True)

    if SSID not in tube_info:
        print(f"  ERROR: Tube AP not broadcasting {SSID}!", flush=True)
        return False

    # 2. Configure Edge STA
    print(f"\n  [2] Edge STA: channel={ch}, s1g_chanbw={chanbw}...", flush=True)
    await ssh_run(EDGE,
        f"uci set wireless.radio0.channel='{ch}'; "
        f"uci set wireless.radio0.s1g_chanbw='{chanbw}'; "
        f"uci set wireless.radio0.txpower='21'; "
        f"uci commit wireless"
    )

    try:
        await ssh_run(EDGE, "wifi down; sleep 2; wifi up", timeout=30)
    except:
        pass
    print(f"  Waiting 12s for Edge wifi up...", flush=True)
    await asyncio.sleep(12)

    # 3. Read generated wpa_supplicant config for S1G params
    wpa_conf = await ssh_run(EDGE, "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null")
    print(f"    WPA config (last 10 lines):", flush=True)
    for line in wpa_conf.split('\n')[-10:]:
        print(f"      {line}", flush=True)

    # Extract S1G params
    prim_1mhz_idx = cfg["prim_idx"]  # default
    for line in wpa_conf.split('\n'):
        if 's1g_prim_1mhz_chan_index=' in line:
            m = re.search(r's1g_prim_1mhz_chan_index=(\d+)', line)
            if m:
                prim_1mhz_idx = int(m.group(1))

    # 4. Fix_halow sequence: kill wpa_supplicant, set morse_cli channel, restart
    print(f"\n  [3] Fix_halow sequence...", flush=True)
    await ssh_run(EDGE, "killall wpa_supplicant_s1g 2>/dev/null; sleep 1; echo killed")
    await asyncio.sleep(2)

    freq = cfg["freq_khz"]
    obw = cfg["oper_bw"]
    pbw = cfg["prim_bw"]
    morse_cmd = f"morse_cli -i wlan0 channel -c {freq} -o {obw} -p {pbw} -n {prim_1mhz_idx}"
    print(f"    {morse_cmd}", flush=True)
    out = await ssh_run(EDGE, morse_cmd)
    print(f"    Result: {out}", flush=True)

    await ssh_run(EDGE, "iw dev wlan0 set txpower fixed 2100 2>/dev/null; echo ok")
    await ssh_run(EDGE, "iw dev wlan0 set power_save off 2>/dev/null; echo ok")
    await asyncio.sleep(2)

    # Restart wpa_supplicant_s1g
    await ssh_run(EDGE,
        "/usr/sbin/wpa_supplicant_s1g -t -D nl80211 -s -i wlan0 "
        "-c /var/run/wpa_supplicant-wlan0.conf -B"
    )

    # 5. Wait for association
    print(f"  [4] Waiting for association (up to 40s)...", flush=True)
    associated = False
    for i in range(20):
        await asyncio.sleep(2)
        info = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Channel'")
        if SSID in info:
            print(f"    ASSOCIATED after {(i+1)*2}s: {info}", flush=True)
            associated = True
            break
        print(f"    {(i+1)*2}s: {info}", flush=True)

    if not associated:
        # Try alternate prim_bw
        print(f"  Trying alternate prim_bw...", flush=True)
        await ssh_run(EDGE, "killall wpa_supplicant_s1g 2>/dev/null; sleep 1; echo killed")
        await asyncio.sleep(2)
        alt_pbw = 1 if pbw == 2 else 2
        morse_cmd2 = f"morse_cli -i wlan0 channel -c {freq} -o {obw} -p {alt_pbw} -n {prim_1mhz_idx}"
        print(f"    {morse_cmd2}", flush=True)
        await ssh_run(EDGE, morse_cmd2)
        await asyncio.sleep(1)
        await ssh_run(EDGE,
            "/usr/sbin/wpa_supplicant_s1g -t -D nl80211 -s -i wlan0 "
            "-c /var/run/wpa_supplicant-wlan0.conf -B"
        )
        for i in range(15):
            await asyncio.sleep(2)
            info = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal'")
            if SSID in info:
                print(f"    ASSOCIATED (alt) after {(i+1)*2}s: {info}", flush=True)
                associated = True
                break

    if not associated:
        print(f"  *** ASSOCIATION FAILED at {desc} ***", flush=True)
        return False

    # 6. Setup routing isolation (proven in 2 MHz tests)
    print(f"\n  [5] Routing isolation...", flush=True)

    # Ensure wlan0 has the HaLow IP
    ip_out = await ssh_run(EDGE, "ip addr show wlan0 | grep 'inet '")
    if EDGE_HALOW_IP not in ip_out:
        print(f"    Assigning {EDGE_HALOW_IP} to wlan0...", flush=True)
        await ssh_run(EDGE, f"ip addr add {EDGE_HALOW_IP}/24 dev wlan0 2>/dev/null; echo ok")

    await ssh_run(EDGE, f"ip route replace {TUBE_IP}/32 dev wlan0 src {EDGE_HALOW_IP}")
    await ssh_run(EDGE, "echo 1 > /proc/sys/net/ipv4/conf/eth0/arp_ignore")
    await ssh_run(EDGE, "echo 2 > /proc/sys/net/ipv4/conf/eth0/arp_announce")
    await ssh_run(TUBE, f"ip neigh replace {EDGE_HALOW_IP} dev br-ahwlan lladdr {EDGE_WLAN_MAC} nud permanent")
    await ssh_run(TUBE, f"ip neigh flush {EDGE_HALOW_IP} 2>/dev/null; echo ok")

    # 7. Verify with ping
    print(f"\n  [6] Verification ping...", flush=True)
    ping_out = await ssh_run(EDGE, f"ping -c 5 -W 3 -i 0.5 {TUBE_IP} 2>&1", timeout=20)
    loss_m = re.search(r'(\d+)% packet loss', ping_out)
    loss = int(loss_m.group(1)) if loss_m else 100
    print(f"    Ping: {loss}% loss", flush=True)
    if loss > 50:
        print(f"    WARNING: High packet loss ({loss}%)", flush=True)

    # Show channel info
    ch_out = await ssh_run(EDGE, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"    Channel info:\n{ch_out}", flush=True)

    return True


# =================================================================
# RUN TEST SUITE at current BW
# =================================================================
async def run_tests(cfg):
    """Run full test suite at the current BW."""
    bw = cfg["bw"]
    desc = cfg["desc"]
    results = {"config": cfg, "timestamp": TIMESTAMP}

    print(f"\n{'='*60}", flush=True)
    print(f"  RUNNING TESTS: {desc}", flush=True)
    print(f"{'='*60}", flush=True)

    # ---- T0: Wireless stats ----
    print(f"\n  [T0] Wireless stats...", flush=True)
    try:
        edge_info = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null")
        tube_assoc = await ssh_run(TUBE, "iwinfo wlan0 assoclist 2>/dev/null")
        edge_station = await ssh_run(EDGE, "iw dev wlan0 station dump 2>/dev/null")
        tube_station = await ssh_run(TUBE, "iw dev wlan0 station dump 2>/dev/null")

        results["wireless"] = {
            "edge_iwinfo": edge_info,
            "tube_assoclist": tube_assoc,
            "edge_station_dump": edge_station,
            "tube_station_dump": tube_station,
        }

        sig_match = re.search(r'Signal:\s*(-?\d+)', edge_info)
        results["edge_signal_dbm"] = int(sig_match.group(1)) if sig_match else None
        tube_sig = re.search(r'(-?\d+)\s*dBm', tube_assoc)
        results["tube_signal_dbm"] = int(tube_sig.group(1)) if tube_sig else None

        # Extract MCS/bitrate
        br_match = re.search(r'Bit Rate:\s*([\d.]+)', edge_info)
        results["edge_bitrate"] = float(br_match.group(1)) if br_match else None

        print(f"    Edge signal: {results['edge_signal_dbm']} dBm, Bitrate: {results['edge_bitrate']} Mbit/s", flush=True)
        print(f"    Tube sees Edge: {results['tube_signal_dbm']} dBm", flush=True)
    except Exception as e:
        print(f"    Stats error: {e}", flush=True)

    # ---- T1: Ping test (50 pings) ----
    print(f"\n  [T1] Ping test (50 pings)...", flush=True)
    try:
        # Record wlan0 TX before
        tx_before = await ssh_run(EDGE, "cat /sys/class/net/wlan0/statistics/tx_packets")
        tx_before = int(tx_before) if tx_before.isdigit() else 0

        out = await ssh_run_long(EDGE,
            f"ping -c 50 -W 5 -i 0.5 {TUBE_IP} 2>&1",
            timeout=60
        )

        tx_after = await ssh_run(EDGE, "cat /sys/class/net/wlan0/statistics/tx_packets")
        tx_after = int(tx_after) if tx_after.isdigit() else 0

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
            "total_sent": 50,
            "received": len(latencies),
            "loss_pct": loss_pct,
            "rtt": rtt,
            "latencies": latencies,
            "wlan0_tx_delta": tx_after - tx_before,
        }
        print(f"    Received: {len(latencies)}/50, Loss: {loss_pct}%", flush=True)
        if rtt:
            print(f"    RTT min/avg/max: {rtt['min']}/{rtt['avg']}/{rtt['max']} ms", flush=True)
        print(f"    HALOW PROOF: wlan0 TX delta: {tx_after - tx_before} packets", flush=True)
    except Exception as e:
        print(f"    Ping error: {e}", flush=True)
        results["ping"] = {"error": str(e)}

    # ---- T2: TCP Upload (Edge -> Tube, 30s) ----
    print(f"\n  [T2] TCP Upload Edge->Tube (30s)...", flush=True)
    for dev in [EDGE, TUBE]:
        try:
            await ssh_run(dev, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
    await asyncio.sleep(2)

    try:
        await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
        await asyncio.sleep(2)

        raw = await ssh_run_long(EDGE,
            f"iperf3 -c {TUBE_IP} -B {EDGE_HALOW_IP} -t 30 -i 1 -J 2>&1",
            timeout=60
        )

        try:
            data = json.loads(raw)
            end_sent = data.get("end", {}).get("sum_sent", {})
            end_recv = data.get("end", {}).get("sum_received", {})
            sent_mbps = end_sent.get("bits_per_second", 0) / 1e6
            recv_mbps = end_recv.get("bits_per_second", 0) / 1e6
            retransmits = end_sent.get("retransmits", "N/A")

            intervals = data.get("intervals", [])
            throughputs = [iv.get("sum", {}).get("bits_per_second", 0) / 1e6 for iv in intervals]

            results["tcp_upload"] = {
                "sent_mbps": round(sent_mbps, 3),
                "recv_mbps": round(recv_mbps, 3),
                "retransmits": retransmits,
                "min_mbps": round(min(throughputs), 3) if throughputs else 0,
                "max_mbps": round(max(throughputs), 3) if throughputs else 0,
                "samples": len(throughputs),
                "throughputs": [round(t, 3) for t in throughputs],
            }
            print(f"    Sent: {sent_mbps:.3f} Mbps | Recv: {recv_mbps:.3f} Mbps | Retrans: {retransmits}", flush=True)
        except json.JSONDecodeError:
            print(f"    Raw (not JSON): {raw[:300]}", flush=True)
            results["tcp_upload"] = {"error": "not_json", "raw": raw[:1000]}
    except Exception as e:
        print(f"    Upload error: {e}", flush=True)
        results["tcp_upload"] = {"error": str(e)}

    for dev in [EDGE, TUBE]:
        try:
            await ssh_run(dev, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
    await asyncio.sleep(3)

    # ---- T3: TCP Download (Tube -> Edge) using -R flag ----
    print(f"\n  [T3] TCP Download Tube->Edge (30s, -R flag)...", flush=True)
    for dev in [EDGE, TUBE]:
        try:
            await ssh_run(dev, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
    await asyncio.sleep(2)

    try:
        # Start server on Tube (same as upload)
        await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
        await asyncio.sleep(2)

        # Edge connects to Tube with -R: Tube sends data -> Edge receives = download
        raw = await ssh_run_long(EDGE,
            f"iperf3 -c {TUBE_IP} -B {EDGE_HALOW_IP} -R -t 30 -i 1 -J 2>&1",
            timeout=60
        )

        try:
            data = json.loads(raw)
            end_sent = data.get("end", {}).get("sum_sent", {})
            end_recv = data.get("end", {}).get("sum_received", {})
            sent_mbps = end_sent.get("bits_per_second", 0) / 1e6
            recv_mbps = end_recv.get("bits_per_second", 0) / 1e6
            retransmits = end_sent.get("retransmits", "N/A")

            intervals = data.get("intervals", [])
            throughputs = [iv.get("sum", {}).get("bits_per_second", 0) / 1e6 for iv in intervals]

            results["tcp_download"] = {
                "sent_mbps": round(sent_mbps, 3),
                "recv_mbps": round(recv_mbps, 3),
                "retransmits": retransmits,
                "min_mbps": round(min(throughputs), 3) if throughputs else 0,
                "max_mbps": round(max(throughputs), 3) if throughputs else 0,
                "samples": len(throughputs),
                "throughputs": [round(t, 3) for t in throughputs],
            }
            print(f"    Sent: {sent_mbps:.3f} Mbps | Recv: {recv_mbps:.3f} Mbps | Retrans: {retransmits}", flush=True)
        except json.JSONDecodeError:
            print(f"    Raw (not JSON): {raw[:300]}", flush=True)
            results["tcp_download"] = {"error": "not_json", "raw": raw[:1000]}
    except Exception as e:
        print(f"    Download error: {e}", flush=True)
        results["tcp_download"] = {"error": str(e)}

    for dev in [EDGE, TUBE]:
        try:
            await ssh_run(dev, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
    await asyncio.sleep(3)

    # ---- T4: UDP at various rates ----
    print(f"\n  [T4] UDP Upload at various rates...", flush=True)
    rates = ["0.5M", "1M", "2M", "4M"]
    if bw >= 8:
        rates.append("8M")
    udp_results = []

    for rate in rates:
        print(f"    --- UDP @ {rate} ---", flush=True)
        for dev in [EDGE, TUBE]:
            try:
                await ssh_run(dev, "killall iperf3 2>/dev/null; echo ok", timeout=5)
            except:
                pass
        await asyncio.sleep(1)

        try:
            await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
            await asyncio.sleep(2)

            raw = await ssh_run_long(EDGE,
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
            print(f"      Actual: {actual_mbps:.3f} Mbps | Jitter: {jitter_ms:.2f}ms | Loss: {loss_pct:.1f}%", flush=True)
        except Exception as e:
            print(f"      Error: {e}", flush=True)
            udp_results.append({"target_rate": rate, "error": str(e)})

        for dev in [EDGE, TUBE]:
            try:
                await ssh_run(dev, "killall iperf3 2>/dev/null; echo ok", timeout=5)
            except:
                pass
        await asyncio.sleep(2)

    results["udp"] = udp_results

    # ---- T5: Stability (10 samples, 5s each) ----
    print(f"\n  [T5] Stability test (10 x 5s TCP)...", flush=True)
    stability_samples = []
    for i in range(10):
        for dev in [EDGE, TUBE]:
            try:
                await ssh_run(dev, "killall iperf3 2>/dev/null; echo ok", timeout=5)
            except:
                pass
        await asyncio.sleep(1)

        try:
            await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
            await asyncio.sleep(2)
            raw = await ssh_run_long(EDGE,
                f"iperf3 -c {TUBE_IP} -B {EDGE_HALOW_IP} -t 5 -J 2>&1",
                timeout=20
            )
            data = json.loads(raw)
            end_sent = data.get("end", {}).get("sum_sent", {})
            end_recv = data.get("end", {}).get("sum_received", {})
            tx = end_sent.get("bits_per_second", 0) / 1e6
            rx = end_recv.get("bits_per_second", 0) / 1e6
            stability_samples.append({"sample": i + 1, "tx_mbps": round(tx, 3), "rx_mbps": round(rx, 3)})
            print(f"    [{i+1}/10] TX: {tx:.3f} Mbps, RX: {rx:.3f} Mbps", flush=True)
        except Exception as e:
            print(f"    [{i+1}/10] Error: {e}", flush=True)
            stability_samples.append({"sample": i + 1, "error": str(e)})

    results["stability"] = stability_samples

    # ---- T6: Final wireless stats ----
    print(f"\n  [T6] Final wireless stats...", flush=True)
    try:
        edge_info = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null")
        tube_assoc = await ssh_run(TUBE, "iwinfo wlan0 assoclist 2>/dev/null")
        edge_ch = await ssh_run(EDGE, "morse_cli -i wlan0 channel 2>/dev/null")
        tube_ch = await ssh_run(TUBE, "morse_cli -i wlan0 channel 2>/dev/null")
        print(f"    Edge iwinfo:\n{edge_info}", flush=True)
        print(f"    Tube assoc:\n{tube_assoc}", flush=True)
        results["wireless_final"] = {
            "edge_iwinfo": edge_info,
            "tube_assoclist": tube_assoc,
            "edge_channel": edge_ch,
            "tube_channel": tube_ch,
        }
    except Exception as e:
        print(f"    Error: {e}", flush=True)

    return results


# =================================================================
# RESTORE 2 MHz
# =================================================================
async def restore_2mhz():
    """Restore 2 MHz working configuration."""
    print(f"\n{'='*60}", flush=True)
    print(f"  RESTORING: {RESTORE_CONFIG['desc']}", flush=True)
    print(f"{'='*60}", flush=True)

    ch = RESTORE_CONFIG["channel"]
    chanbw = RESTORE_CONFIG["s1g_chanbw"]

    # Tube
    await ssh_run(TUBE,
        f"uci set wireless.radio0.channel='{ch}'; "
        f"uci set wireless.radio0.s1g_chanbw='{chanbw}'; "
        f"uci commit wireless"
    )
    try:
        await ssh_run(TUBE, "wifi down; sleep 2; wifi up", timeout=30)
    except:
        pass
    await asyncio.sleep(15)

    # Edge
    await ssh_run(EDGE,
        f"uci set wireless.radio0.channel='{ch}'; "
        f"uci set wireless.radio0.s1g_chanbw='{chanbw}'; "
        f"uci commit wireless"
    )
    try:
        await ssh_run(EDGE, "wifi down; sleep 2; wifi up", timeout=30)
    except:
        pass
    await asyncio.sleep(15)

    # Verify
    info = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal'")
    print(f"  Edge after restore: {info}", flush=True)

    # Re-setup routing
    ip_out = await ssh_run(EDGE, "ip addr show wlan0 | grep 'inet '")
    if EDGE_HALOW_IP not in ip_out:
        await ssh_run(EDGE, f"ip addr add {EDGE_HALOW_IP}/24 dev wlan0 2>/dev/null; echo ok")
    await ssh_run(EDGE, f"ip route replace {TUBE_IP}/32 dev wlan0 src {EDGE_HALOW_IP}")
    await ssh_run(EDGE, "echo 1 > /proc/sys/net/ipv4/conf/eth0/arp_ignore")
    await ssh_run(EDGE, "echo 2 > /proc/sys/net/ipv4/conf/eth0/arp_announce")
    await ssh_run(TUBE, f"ip neigh replace {EDGE_HALOW_IP} dev br-ahwlan lladdr {EDGE_WLAN_MAC} nud permanent")

    ping_out = await ssh_run(EDGE, f"ping -c 3 -W 3 {TUBE_IP} 2>&1", timeout=15)
    print(f"  Restore ping: {ping_out.split(chr(10))[-1] if ping_out else 'no output'}", flush=True)


# =================================================================
# MAIN
# =================================================================
async def main():
    print("=" * 60, flush=True)
    print("  THESIS HALOW TEST: 4 MHz + 8 MHz", flush=True)
    print(f"  Timestamp: {TIMESTAMP}", flush=True)
    print(f"  Output: {OUTPUT_DIR}", flush=True)
    print(f"  (2 MHz data already in thesis_package_20260225)", flush=True)
    print("=" * 60, flush=True)

    all_results = {}

    for cfg in BW_CONFIGS:
        bw = cfg["bw"]
        desc = cfg["desc"]

        # Configure
        ok = await configure_bw(cfg)
        if not ok:
            print(f"\n  *** SKIPPING {desc} - association failed ***", flush=True)
            all_results[f"{bw}MHz"] = {"config": cfg, "error": "association_failed"}
            # Save partial
            save_json(f"results_{bw}mhz_{TIMESTAMP}.json",
                      {"config": cfg, "error": "association_failed"})
            await asyncio.sleep(5)
            continue

        # Run tests
        results = await run_tests(cfg)
        all_results[f"{bw}MHz"] = results

        # Save per-BW results
        save_json(f"results_{bw}mhz_{TIMESTAMP}.json", results)

        print(f"\n  COMPLETED: {desc}", flush=True)
        await asyncio.sleep(5)

    # Save combined
    save_json(f"results_4_8mhz_{TIMESTAMP}.json", all_results)

    # Print summary
    print(f"\n\n{'='*60}", flush=True)
    print(f"  SUMMARY", flush=True)
    print(f"{'='*60}", flush=True)
    hdr = f"{'BW':>6} | {'Ping Loss':>10} | {'RTT Avg':>10} | {'TCP Up':>10} | {'TCP Down':>10} | {'Edge Sig':>10} | {'Tube Sig':>10}"
    print(hdr, flush=True)
    print("-" * len(hdr), flush=True)

    for bw_key in ["4MHz", "8MHz"]:
        r = all_results.get(bw_key, {})
        if "error" in r and isinstance(r.get("error"), str):
            print(f"{bw_key:>6} | {'FAILED':^10} | {'---':^10} | {'---':^10} | {'---':^10} | {'---':^10} | {'---':^10}", flush=True)
            continue

        ping = r.get("ping", {})
        tcp_up = r.get("tcp_upload", {})
        tcp_down = r.get("tcp_download", {})

        ping_loss = f"{ping.get('loss_pct', '?')}%"
        rtt_avg = f"{ping.get('rtt', {}).get('avg', '?')}ms" if ping.get('rtt') else "?"
        up_mbps = f"{tcp_up.get('sent_mbps', '?')}" if not tcp_up.get('error') else "ERR"
        down_mbps = f"{tcp_down.get('sent_mbps', '?')}" if not tcp_down.get('error') else "ERR"
        edge_sig = f"{r.get('edge_signal_dbm', '?')}dBm"
        tube_sig = f"{r.get('tube_signal_dbm', '?')}dBm"

        print(f"{bw_key:>6} | {ping_loss:>10} | {rtt_avg:>10} | {up_mbps:>10} | {down_mbps:>10} | {edge_sig:>10} | {tube_sig:>10}", flush=True)

    # Generate comparison CSV (including 2 MHz from previous data for reference)
    csv_rows = []
    for bw_key in ["4MHz", "8MHz"]:
        r = all_results.get(bw_key, {})
        if "error" in r and isinstance(r.get("error"), str):
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
            tcp_up.get("sent_mbps") if not tcp_up.get("error") else "ERR",
            tcp_down.get("sent_mbps") if not tcp_down.get("error") else "ERR",
            tcp_up.get("retransmits") if not tcp_up.get("error") else "",
        ])

    save_csv(f"comparison_4_8mhz_{TIMESTAMP}.csv",
             ["bandwidth", "edge_signal_dbm", "tube_signal_dbm", "ping_loss_pct",
              "rtt_avg_ms", "tcp_upload_mbps", "tcp_download_mbps", "tcp_retransmits"],
             csv_rows)

    # Restore 2 MHz
    print(f"\n  Restoring 2 MHz...", flush=True)
    await restore_2mhz()

    print(f"\n{'='*60}", flush=True)
    print(f"  ALL DONE. Results in: {OUTPUT_DIR}", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
