#!/usr/bin/env python3
"""
Suite completa de pruebas HaLow para tesis UNAL.

Tests:
  1. Throughput TCP (Edge->Tube, Tube->Edge) - 60s con intervalos 1s
  2. Throughput UDP a distintas tasas
  3. Latencia ICMP (200 pings)
  4. Estabilidad temporal (throughput cada 10s durante 5 minutos)
  5. Wireless stats sampling durante tests

Genera CSV + JSON para diagramas.
"""
import asyncio
import asyncssh
import json
import csv
import os
import re
import time
from datetime import datetime

# === Dispositivos ===
EDGE = {"host": "192.168.1.196", "user": "root", "password": "root", "name": "Edge Gateway"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root", "name": "Tube-AHM"}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def connect_kwargs(device):
    kw = {"host": device["host"], "port": 22, "username": device["user"], "known_hosts": None}
    if "key" in device:
        kw["client_keys"] = [device["key"]]
    else:
        kw["password"] = device["password"]
    return kw


async def ssh_exec(device, cmd, timeout=120):
    async def _do():
        async with asyncssh.connect(**connect_kwargs(device), login_timeout=20) as conn:
            r = await conn.run(cmd, timeout=timeout)
            return r.stdout.strip()
    try:
        return await asyncio.wait_for(_do(), timeout=timeout + 25)
    except asyncio.TimeoutError:
        raise Exception(f"SSH total timeout to {device['host']} ({timeout+25}s)")
    except (OSError, asyncssh.Error) as e:
        raise Exception(f"SSH error to {device['host']}: {e}")


async def ssh_exec_long(device, cmd, timeout=300):
    """For long-running commands."""
    return await ssh_exec(device, cmd, timeout=timeout)


def save_csv(filename, headers, rows):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  -> CSV: {path}")
    return path


def save_json(filename, data):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"  -> JSON: {path}")
    return path


# =========================================================
# TEST 1: Throughput TCP con iperf3 (intervalos 1s)
# =========================================================
async def test_tcp_throughput():
    """TCP throughput: server on Tube-AHM, client on Edge (and reverse)."""
    print("\n" + "=" * 60)
    print("  TEST 1: Throughput TCP (iperf3, 60s, intervalos 1s)")
    print("=" * 60)

    results = {}

    for direction, server_dev, client_dev, server_ip in [
        ("Edge→Tube (Upload)", TUBE, EDGE, "192.168.1.103"),
        ("Tube→Edge (Download)", EDGE, TUBE, "192.168.1.196"),
    ]:
        print(f"\n  --- {direction} ---")

        # Kill any existing iperf3 server
        try:
            await ssh_exec(server_dev, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
        await asyncio.sleep(1)

        # Start iperf3 server
        print(f"  Iniciando servidor iperf3 en {server_dev['name']}...")
        try:
            await ssh_exec(server_dev, "iperf3 -s -D -1", timeout=10)
        except:
            pass
        await asyncio.sleep(2)

        # Run client with JSON output, 60 seconds, 1s intervals
        print(f"  Ejecutando cliente iperf3 en {client_dev['name']} (60s)...")
        try:
            raw = await ssh_exec_long(
                client_dev,
                f"iperf3 -c {server_ip} -t 60 -i 1 -J",
                timeout=120
            )
            data = json.loads(raw)
            results[direction] = data

            # Extract per-second throughput
            intervals = data.get("intervals", [])
            throughputs = []
            for iv in intervals:
                s = iv.get("sum", {})
                bps = s.get("bits_per_second", 0)
                mbps = bps / 1e6
                throughputs.append(mbps)

            # Summary
            end = data.get("end", {}).get("sum_sent", {})
            avg_mbps = end.get("bits_per_second", 0) / 1e6
            retransmits = end.get("retransmits", "N/A")

            print(f"  Promedio: {avg_mbps:.2f} Mbps | Retransmits: {retransmits}")
            print(f"  Min: {min(throughputs):.2f} | Max: {max(throughputs):.2f} | Samples: {len(throughputs)}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results[direction] = {"error": str(e)}

        # Cleanup
        try:
            await ssh_exec(server_dev, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
        await asyncio.sleep(3)

    save_json(f"tcp_throughput_{TIMESTAMP}.json", results)

    # Generate CSV
    rows = []
    for direction, data in results.items():
        if "error" in data:
            continue
        for i, iv in enumerate(data.get("intervals", [])):
            s = iv.get("sum", {})
            rows.append([
                direction,
                i + 1,
                round(s.get("bits_per_second", 0) / 1e6, 3),
                s.get("bytes", 0),
                s.get("retransmits", 0),
            ])
    save_csv(f"tcp_throughput_{TIMESTAMP}.csv",
             ["direction", "second", "throughput_mbps", "bytes", "retransmits"], rows)

    return results


# =========================================================
# TEST 2: Throughput UDP a distintas tasas
# =========================================================
async def test_udp_throughput():
    """UDP throughput at various bitrates to find max."""
    print("\n" + "=" * 60)
    print("  TEST 2: Throughput UDP (iperf3, distintas tasas)")
    print("=" * 60)

    rates = ["1M", "2M", "4M", "8M", "12M", "16M", "20M"]
    results = []

    for rate in rates:
        print(f"\n  --- UDP @ {rate}bps (Edge→Tube, 15s) ---")

        try:
            await ssh_exec(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
        await asyncio.sleep(1)

        try:
            await ssh_exec(TUBE, "iperf3 -s -D -1", timeout=10)
        except:
            pass
        await asyncio.sleep(2)

        try:
            raw = await ssh_exec_long(
                EDGE,
                f"iperf3 -c 192.168.1.103 -u -b {rate} -t 15 -i 1 -J",
                timeout=60
            )
            data = json.loads(raw)

            udp_end = data.get("end", {}).get("sum", {})
            sent_mbps = udp_end.get("bits_per_second", 0) / 1e6
            jitter_ms = udp_end.get("jitter_ms", 0)
            lost = udp_end.get("lost_packets", 0)
            total = udp_end.get("packets", 1)
            loss_pct = udp_end.get("lost_percent", (lost / total * 100) if total else 0)

            results.append({
                "target_rate": rate,
                "actual_mbps": round(sent_mbps, 3),
                "jitter_ms": round(jitter_ms, 3),
                "lost_packets": lost,
                "total_packets": total,
                "loss_percent": round(loss_pct, 2),
            })
            print(f"  Actual: {sent_mbps:.2f} Mbps | Jitter: {jitter_ms:.2f} ms | Loss: {loss_pct:.1f}%")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"target_rate": rate, "error": str(e)})

        try:
            await ssh_exec(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
        await asyncio.sleep(3)

    save_json(f"udp_throughput_{TIMESTAMP}.json", results)
    csv_rows = [[r.get("target_rate"), r.get("actual_mbps"), r.get("jitter_ms"),
                 r.get("lost_packets"), r.get("total_packets"), r.get("loss_percent")]
                for r in results if "error" not in r]
    save_csv(f"udp_throughput_{TIMESTAMP}.csv",
             ["target_rate", "actual_mbps", "jitter_ms", "lost_packets", "total_packets", "loss_pct"], csv_rows)

    return results


# =========================================================
# TEST 3: Latencia ICMP (ping)
# =========================================================
async def test_latency():
    """ICMP latency: 200 pings from Edge to Tube-AHM."""
    print("\n" + "=" * 60)
    print("  TEST 3: Latencia ICMP (200 pings, Edge→Tube)")
    print("=" * 60)

    raw = await ssh_exec_long(EDGE, "ping -c 200 -i 0.5 192.168.1.103", timeout=150)

    # Parse each ping line
    latencies = []
    for line in raw.split('\n'):
        m = re.search(r'time[=<](\d+\.?\d*)', line)
        if m:
            latencies.append(float(m.group(1)))

    # Parse summary
    stats_line = [l for l in raw.split('\n') if 'transmitted' in l]
    rtt_line = [l for l in raw.split('\n') if 'rtt' in l or 'round-trip' in l]

    loss_match = re.search(r'(\d+)% packet loss', raw)
    loss_pct = float(loss_match.group(1)) if loss_match else 0

    rtt_match = re.search(r'= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', raw)
    if rtt_match:
        rtt_min, rtt_avg, rtt_max, rtt_mdev = [float(x) for x in rtt_match.groups()]
    else:
        rtt_min = min(latencies) if latencies else 0
        rtt_avg = sum(latencies) / len(latencies) if latencies else 0
        rtt_max = max(latencies) if latencies else 0
        rtt_mdev = 0

    result = {
        "samples": len(latencies),
        "min_ms": rtt_min,
        "avg_ms": rtt_avg,
        "max_ms": rtt_max,
        "mdev_ms": rtt_mdev,
        "packet_loss_pct": loss_pct,
        "latencies": latencies,
    }

    print(f"  Samples: {len(latencies)}")
    print(f"  Min: {rtt_min:.2f} ms | Avg: {rtt_avg:.2f} ms | Max: {rtt_max:.2f} ms | Mdev: {rtt_mdev:.2f} ms")
    print(f"  Packet loss: {loss_pct}%")

    save_json(f"latency_{TIMESTAMP}.json", result)
    csv_rows = [[i + 1, lat] for i, lat in enumerate(latencies)]
    save_csv(f"latency_{TIMESTAMP}.csv", ["ping_number", "rtt_ms"], csv_rows)

    return result


# =========================================================
# TEST 4: Estabilidad temporal (5 minutos, muestreo cada 10s)
# =========================================================
async def test_stability():
    """Throughput stability: 20 x 5s TCP tests."""
    N_ROUNDS = 20
    print("\n" + "=" * 60)
    print(f"  TEST 4: Estabilidad ({N_ROUNDS} mediciones x 5s)")
    print("=" * 60)

    results = []
    for i in range(N_ROUNDS):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{i+1:2d}/{N_ROUNDS}] {ts} ...", end=" ", flush=True)

        try:
            await ssh_exec(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
        await asyncio.sleep(1)

        try:
            await ssh_exec(TUBE, "iperf3 -s -D -1", timeout=5)
        except:
            pass
        await asyncio.sleep(1)

        try:
            raw = await ssh_exec(EDGE, "iperf3 -c 192.168.1.103 -t 5 -J", timeout=25)
            data = json.loads(raw)

            sent = data.get("end", {}).get("sum_sent", {})
            recv = data.get("end", {}).get("sum_received", {})
            sent_mbps = sent.get("bits_per_second", 0) / 1e6
            recv_mbps = recv.get("bits_per_second", 0) / 1e6
            retrans = sent.get("retransmits", 0)

            # Also get wireless stats
            winfo = await ssh_exec(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Quality|Bit Rate'", timeout=15)
            signal_match = re.search(r'Signal:\s*(-?\d+)', winfo)
            noise_match = re.search(r'Noise:\s*(-?\d+)', winfo)
            signal = int(signal_match.group(1)) if signal_match else None
            noise = int(noise_match.group(1)) if noise_match else None

            results.append({
                "sample": i + 1,
                "timestamp": ts,
                "sent_mbps": round(sent_mbps, 3),
                "recv_mbps": round(recv_mbps, 3),
                "retransmits": retrans,
                "signal_dbm": signal,
                "noise_dbm": noise,
                "snr_db": (signal - noise) if signal and noise else None,
            })
            print(f"TX: {sent_mbps:.2f} Mbps | RX: {recv_mbps:.2f} Mbps | Signal: {signal} dBm | Retrans: {retrans}")

        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"sample": i + 1, "timestamp": ts, "error": str(e)})

        try:
            await ssh_exec(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass

    save_json(f"stability_{TIMESTAMP}.json", results)
    csv_rows = [[r.get("sample"), r.get("timestamp"), r.get("sent_mbps"), r.get("recv_mbps"),
                 r.get("retransmits"), r.get("signal_dbm"), r.get("noise_dbm"), r.get("snr_db")]
                for r in results if "error" not in r]
    save_csv(f"stability_{TIMESTAMP}.csv",
             ["sample", "timestamp", "sent_mbps", "recv_mbps", "retransmits", "signal_dbm", "noise_dbm", "snr_db"],
             csv_rows)

    return results


# =========================================================
# TEST 5: Wireless stats snapshot
# =========================================================
async def test_wireless_stats():
    """Detailed wireless statistics from both ends."""
    print("\n" + "=" * 60)
    print("  TEST 5: Estadísticas wireless detalladas")
    print("=" * 60)

    stats = {}

    for dev_name, dev in [("edge", EDGE), ("tube", TUBE)]:
        info = await ssh_exec(dev, "iwinfo wlan0 info 2>/dev/null", timeout=20)
        assoc = await ssh_exec(dev, "iwinfo wlan0 assoclist 2>/dev/null", timeout=20)
        station = await ssh_exec(dev, "iw dev wlan0 station dump 2>/dev/null", timeout=20)
        ip_stats = await ssh_exec(dev, "ip -s link show wlan0 2>/dev/null", timeout=20)
        proc_stats = await ssh_exec(dev, "cat /proc/net/dev | grep wlan0", timeout=20)

        stats[dev_name] = {
            "iwinfo": info,
            "assoclist": assoc,
            "station_dump": station,
            "ip_stats": ip_stats,
            "proc_net_dev": proc_stats,
        }

        print(f"\n--- {dev['name']} ---")
        print(info)
        if assoc:
            print(f"Assoclist: {assoc}")

    save_json(f"wireless_stats_{TIMESTAMP}.json", stats)
    return stats


# =========================================================
# MAIN
# =========================================================
async def main():
    print("=" * 60)
    print("  SUITE DE PRUEBAS HALOW PARA TESIS UNAL")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Topología: WAN (192.168.1.1) --Eth-- Tube-AHM (AP, 192.168.1.103) ==HaLow 908MHz 8MHz== Edge (STA, 192.168.1.196)")
    print("=" * 60)

    all_results = {}

    # Test 1: TCP Throughput
    all_results["tcp_throughput"] = await test_tcp_throughput()

    # Test 2: UDP Throughput
    all_results["udp_throughput"] = await test_udp_throughput()

    # Test 3: Latency
    all_results["latency"] = await test_latency()

    # Test 4: Stability
    all_results["stability"] = await test_stability()

    # Test 5: Wireless stats
    all_results["wireless_stats"] = await test_wireless_stats()

    # Save complete results
    save_json(f"all_tests_{TIMESTAMP}.json", all_results)

    print("\n" + "=" * 60)
    print("  PRUEBAS COMPLETAS")
    print(f"  Datos en: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
