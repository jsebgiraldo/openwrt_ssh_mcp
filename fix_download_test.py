#!/usr/bin/env python3
"""
Re-run TCP download test using -R (reverse) flag.
Edge connects to Tube, -R makes Tube send data → Edge receives = download.
Merges results into the existing all_tests JSON.
"""

import asyncio, asyncssh, json, os, sys, time

TUBE = {"host": "192.168.1.103", "username": "root", "password": "root"}
EDGE = {"host": "192.168.1.111", "username": "root", "password": "root"}
EDGE_HALOW_IP = "192.168.1.196"
TIMESTAMP = "20260225_203123"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_data")


async def ssh_cmd(host_cfg, command, timeout=30):
    conn = await asyncssh.connect(
        host_cfg["host"], username=host_cfg["username"],
        password=host_cfg["password"],
        known_hosts=None
    )
    result = await asyncio.wait_for(conn.run(command), timeout=timeout)
    conn.close()
    return result.stdout.strip()


async def wlan0_counters(host_cfg):
    raw = await ssh_cmd(host_cfg, "cat /proc/net/dev | grep wlan0", timeout=10)
    parts = raw.split()
    return {"rx_bytes": int(parts[1]), "tx_bytes": int(parts[9]),
            "rx_packets": int(parts[2]), "tx_packets": int(parts[10])}


def fmt_bytes(b):
    if b > 1048576:
        return f"{b/1048576:.1f} MB"
    elif b > 1024:
        return f"{b/1024:.1f} KB"
    return f"{b} B"


async def main():
    print("=" * 60)
    print("  FIX: TCP Download re-test using -R (reverse) flag")
    print("  Tube(.103) --send data--> Edge(.196) via HaLow")
    
    # Fix Windows encoding
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("=" * 60)

    # 1. Kill any existing iperf3
    print("\n  Cleaning up existing iperf3...", flush=True)
    await ssh_cmd(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
    await ssh_cmd(EDGE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
    await asyncio.sleep(1)

    # 2. Start iperf3 server on TUBE
    print("  Starting iperf3 server on Tube (.103)...", flush=True)
    await ssh_cmd(TUBE, "iperf3 -s -D -1", timeout=10)
    await asyncio.sleep(2)

    # Verify server
    check = await ssh_cmd(TUBE, "ss -tlnp | grep 5201 || netstat -tlnp 2>/dev/null | grep 5201 || echo NOSERVER", timeout=5)
    print(f"  Server check: {check}", flush=True)
    if "NOSERVER" in check:
        print("  ERROR: iperf3 server not running on Tube!")
        return

    # 3. Get wlan0 counters before
    e_before = await wlan0_counters(EDGE)
    t_before = await wlan0_counters(TUBE)

    # 4. Run iperf3 client on Edge with -R (reverse = server sends to client)
    #    Edge connects to Tube, -R makes Tube push data to Edge = download dir
    print("  Running iperf3 download (60s) with -R flag...", flush=True)
    try:
        raw = await ssh_cmd(
            EDGE,
            f"iperf3 -c 192.168.1.103 -B {EDGE_HALOW_IP} -R -t 60 -i 1 -J",
            timeout=120
        )
        data = json.loads(raw)

        intervals = data.get("intervals", [])
        throughputs = [iv["sum"]["bits_per_second"] / 1e6 for iv in intervals if "sum" in iv]

        end_sent = data.get("end", {}).get("sum_sent", {})
        end_recv = data.get("end", {}).get("sum_received", {})
        avg_sent = end_sent.get("bits_per_second", 0) / 1e6
        avg_recv = end_recv.get("bits_per_second", 0) / 1e6
        retrans = end_sent.get("retransmits", "N/A")

        print(f"\n  Sent (Tube->Edge): {avg_sent:.2f} Mbps | Recv (Edge): {avg_recv:.2f} Mbps | Retrans: {retrans}")
        if throughputs:
            print(f"  Min: {min(throughputs):.2f} | Max: {max(throughputs):.2f} | Samples: {len(throughputs)}")

    except json.JSONDecodeError:
        print(f"  ERROR: invalid JSON:\n{raw[:500]}")
        data = {"error": "invalid JSON"}
    except Exception as e:
        print(f"  ERROR: {e}")
        data = {"error": str(e)}

    # 5. Get wlan0 counters after
    e_after = await wlan0_counters(EDGE)
    t_after = await wlan0_counters(TUBE)

    etx = e_after["tx_bytes"] - e_before["tx_bytes"]
    erx = e_after["rx_bytes"] - e_before["rx_bytes"]
    ttx = t_after["tx_bytes"] - t_before["tx_bytes"]
    trx = t_after["rx_bytes"] - t_before["rx_bytes"]

    print(f"  HALOW PROOF: Edge wlan0 TX={fmt_bytes(etx)} RX={fmt_bytes(erx)} | Tube wlan0 TX={fmt_bytes(ttx)} RX={fmt_bytes(trx)}")

    if "error" not in data:
        data["halow_verification"] = {
            "edge_wlan0_tx_bytes": etx, "edge_wlan0_rx_bytes": erx,
            "tube_wlan0_tx_bytes": ttx, "tube_wlan0_rx_bytes": trx,
        }

    # 6. Save results and merge into existing all_tests JSON
    # Save standalone download JSON
    dl_path = os.path.join(DATA_DIR, f"tcp_download_fix_{TIMESTAMP}.json")
    with open(dl_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  -> Standalone: {dl_path}")

    # Merge into all_tests
    all_path = os.path.join(DATA_DIR, f"all_tests_{TIMESTAMP}.json")
    if os.path.exists(all_path):
        with open(all_path, "r") as f:
            all_data = json.load(f)
        # Replace the failed download with the fixed one
        if "tcp_throughput" in all_data:
            all_data["tcp_throughput"]["Download (Tube->Edge) [FIXED -R]"] = data
        with open(all_path, "w") as f:
            json.dump(all_data, f, indent=2)
        print(f"  -> Merged into: {all_path}")

    # Also update the TCP CSV with download row
    if "error" not in data:
        csv_path = os.path.join(DATA_DIR, f"tcp_throughput_{TIMESTAMP}.csv")
        with open(csv_path, "a") as f:
            for iv in data.get("intervals", []):
                s = iv.get("sum", {})
                t_sec = s.get("start", 0)
                mbps = s.get("bits_per_second", 0) / 1e6
                f.write(f"download,{t_sec:.1f},{mbps:.4f}\n")
        print(f"  -> Appended to: {csv_path}")

    # Cleanup
    await ssh_cmd(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)

    print("\n  DOWNLOAD FIX COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
