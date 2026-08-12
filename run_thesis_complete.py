#!/usr/bin/env python3
"""
Suite COMPLETA de pruebas HaLow IEEE 802.11ah para tesis UNAL.

FASES:
  1. Configurar HaLow (canal 14, 2 MHz, WPA3-SAE) en AP y STA
  2. Corregir rutas + ARP en Edge para forzar tráfico por HaLow
  3. Verificar enlace HaLow (ping, contadores)
  4. Ejecutar 5 pruebas (TCP, UDP, Latencia, Estabilidad, Wireless Stats)
  5. Verificar con contadores wlan0 que el tráfico fue por HaLow

IMPORTANTE:
  - SSH Control a Edge via Ethernet (.111) → NO interfiere con datos
  - iperf3 data forzado por HaLow (bind .196 + host route + arp_ignore)
  - Contadores wlan0 antes/después de cada test prueban ruta HaLow
"""
import asyncio
import asyncssh
import json
import csv
import os
import re
import sys
from datetime import datetime

# ═══════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════

# SSH control via ETHERNET — no compite con tráfico de prueba
EDGE = {"host": "192.168.1.111", "user": "root", "password": "root", "name": "Edge Gateway"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root", "name": "Tube-AHM"}
EDGE_HALOW_IP = "192.168.1.196"

# HaLow
SSID = "UNAL-HaLow-Tesis"
KEY = "banano2026"
CHANNEL = "14"       # 909 MHz
S1G_CHANBW = "2"     # 2 MHz — probado confiable (8 MHz da 80% loss)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "thesis_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


# ═══════════════════════════════════════════════════════════
# UTILIDADES SSH
# ═══════════════════════════════════════════════════════════

def ckw(dev):
    return {"host": dev["host"], "port": 22, "username": dev["user"],
            "password": dev.get("password"), "known_hosts": None, "login_timeout": 15}


async def cmd(dev, command, timeout=30, label=None):
    """Run SSH command with robust timeout."""
    async def _do():
        async with asyncssh.connect(**ckw(dev)) as c:
            r = await c.run(command, timeout=timeout)
            return (r.stdout or "").strip()
    try:
        result = await asyncio.wait_for(_do(), timeout=timeout + 20)
        if label:
            # Truncate for readability
            lines = result.split('\n')
            preview = '\n    '.join(lines[:8])
            if len(lines) > 8:
                preview += f"\n    ... ({len(lines)} líneas)"
            print(f"  [{label}]\n    {preview}", flush=True)
        return result
    except asyncio.TimeoutError:
        if label:
            print(f"  [{label}] TIMEOUT ({timeout}s)", flush=True)
        return ""
    except Exception as e:
        if label:
            print(f"  [{label}] ERROR: {e}", flush=True)
        return ""


async def cmd_long(dev, command, timeout=180):
    return await cmd(dev, command, timeout=timeout)


def save_csv(filename, headers, rows):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  -> CSV: {path}", flush=True)
    return path


def save_json(filename, data):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"  -> JSON: {path}", flush=True)
    return path


async def wlan0_counters(dev):
    """Get wlan0 TX/RX byte counters from /proc/net/dev."""
    raw = await cmd(dev, "cat /proc/net/dev | grep wlan0", timeout=10)
    parts = raw.split()
    if len(parts) >= 10:
        return {"rx_bytes": int(parts[1]), "tx_bytes": int(parts[9]),
                "rx_pkts": int(parts[2]), "tx_pkts": int(parts[10])}
    return {"rx_bytes": 0, "tx_bytes": 0, "rx_pkts": 0, "tx_pkts": 0}


def fmt_bytes(b):
    if b > 1e6:
        return f"{b/1e6:.1f} MB"
    return f"{b/1e3:.1f} KB"


async def ensure_iperf3_server(dev, port=5201):
    """Start iperf3 server reliably."""
    await cmd(dev, "killall iperf3 2>/dev/null; sleep 1; echo ok", timeout=10)
    await cmd(dev, f"iperf3 -s -D -1 -p {port}", timeout=10)
    await asyncio.sleep(2)
    check = await cmd(dev, f"ss -tlnp 2>/dev/null | grep {port} || netstat -tlnp 2>/dev/null | grep {port}", timeout=5)
    if str(port) not in check:
        # Retry
        await cmd(dev, f"killall iperf3 2>/dev/null; sleep 2; iperf3 -s -D -1 -p {port}", timeout=15)
        await asyncio.sleep(3)
        check = await cmd(dev, f"ss -tlnp 2>/dev/null | grep {port}", timeout=5)
    return str(port) in check


# ═══════════════════════════════════════════════════════════
# FASE 1: CONFIGURAR HALOW
# ═══════════════════════════════════════════════════════════
async def phase1_setup():
    print("\n" + "=" * 60)
    print("  FASE 1: Configurar HaLow (canal 14, 2 MHz)")
    print("=" * 60)

    # Check current config on both devices
    edge_ch = await cmd(EDGE, "uci get wireless.radio0.channel 2>/dev/null")
    edge_bw = await cmd(EDGE, "uci get wireless.radio0.s1g_chanbw 2>/dev/null")
    tube_ch = await cmd(TUBE, "uci get wireless.radio0.channel 2>/dev/null")
    tube_bw = await cmd(TUBE, "uci get wireless.radio0.s1g_chanbw 2>/dev/null")
    print(f"  Actual: Tube ch={tube_ch}/bw={tube_bw} | Edge ch={edge_ch}/bw={edge_bw}")
    print(f"  Target: ch={CHANNEL}/bw={S1G_CHANBW}")

    need_reconfig = (edge_ch != CHANNEL or edge_bw != S1G_CHANBW or
                     tube_ch != CHANNEL or tube_bw != S1G_CHANBW)

    if need_reconfig:
        print("\n  Reconfigurando AP (Tube-AHM)...", flush=True)
        # --- AP ---
        for c in [
            f"uci set wireless.radio0.channel='{CHANNEL}'",
            f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
            "uci set wireless.radio0.disabled='0'",
            "uci set wireless.radio0.country='US'",
            "uci commit wireless",
        ]:
            await cmd(TUBE, c)

        # Check if wifi-iface exists on Tube
        iface_check = await cmd(TUBE, "uci get wireless.wifinet0.ssid 2>/dev/null")
        if SSID not in iface_check and not iface_check:
            print("  wifi-iface falta en Tube - creándolo...", flush=True)
            for c in [
                "uci set wireless.wifinet0=wifi-iface",
                "uci set wireless.wifinet0.device='radio0'",
                "uci set wireless.wifinet0.mode='ap'",
                f"uci set wireless.wifinet0.ssid='{SSID}'",
                "uci set wireless.wifinet0.encryption='sae'",
                "uci set wireless.wifinet0.sae_pwe='1'",
                f"uci set wireless.wifinet0.key='{KEY}'",
                "uci set wireless.wifinet0.network='ahwlan'",
                "uci set wireless.wifinet0.wds='1'",
                "uci commit wireless",
            ]:
                await cmd(TUBE, c)

        await cmd(TUBE, "wifi", timeout=20, label="Tube wifi restart")
        print("  Esperando 15s para que AP inicialice...", flush=True)
        await asyncio.sleep(15)

        # Verify AP
        ap_info = await cmd(TUBE, "iwinfo wlan0 info 2>/dev/null | head -5", label="AP status")
        if SSID not in ap_info:
            print("  Esperando 10s más...", flush=True)
            await asyncio.sleep(10)
            ap_info = await cmd(TUBE, "iwinfo wlan0 info 2>/dev/null | head -5", label="AP retry")
            if SSID not in ap_info:
                print("  FALLO: AP no inició.", flush=True)
                return False

        # --- STA ---
        print("\n  Reconfigurando STA (Edge)...", flush=True)
        for c in [
            f"uci set wireless.radio0.channel='{CHANNEL}'",
            f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
            "uci set wireless.radio0.txpower='21'",
            "uci set wireless.radio0.disabled='0'",
            "uci set wireless.radio0.country='US'",
            "uci commit wireless",
        ]:
            await cmd(EDGE, c)

        await cmd(EDGE, "wifi", timeout=20, label="Edge wifi restart")
        print("  Esperando asociación STA (max 90s)...", flush=True)

        for i in range(18):
            await asyncio.sleep(5)
            info = await cmd(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal'")
            if SSID in info and "Signal" in info:
                print(f"  Asociado en {(i+1)*5}s", flush=True)
                break
            print(f"  [{(i+1)*5}s] esperando...", flush=True)
        else:
            print("  FALLO: STA no asoció.", flush=True)
            return False
    else:
        print("  Config HaLow correcta.", flush=True)
        # Verify association
        info = await cmd(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal'")
        if SSID not in info:
            print("  No asociado, reiniciando wifi...", flush=True)
            await cmd(EDGE, "wifi", timeout=20)
            await asyncio.sleep(15)
            info = await cmd(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal'")
            if SSID not in info:
                print("  FALLO: STA no asoció.", flush=True)
                return False
        print(f"  STA asociado: {info}", flush=True)

    return True


# ═══════════════════════════════════════════════════════════
# FASE 2: RUTAS + ARP
# ═══════════════════════════════════════════════════════════
async def phase2_routing():
    print("\n" + "=" * 60)
    print("  FASE 2: Configurar rutas y ARP en Edge")
    print("=" * 60)

    # Verify wlan0 IP
    ip_out = await cmd(EDGE, "ip addr show wlan0 | grep 'inet '")
    if EDGE_HALOW_IP not in ip_out:
        print(f"  Asignando {EDGE_HALOW_IP} a wlan0...", flush=True)
        await cmd(EDGE, f"ip addr add {EDGE_HALOW_IP}/24 dev wlan0 2>/dev/null; echo ok")

    # Force host route to Tube via wlan0
    await cmd(EDGE, f"ip route replace 192.168.1.103 dev wlan0 src {EDGE_HALOW_IP}",
              label="Route .103 via wlan0")

    # ARP isolation: prevent eth0 from responding to ARP for .196
    # This ensures Tube sends data to Edge through HaLow, not Ethernet
    await cmd(EDGE, "echo 1 > /proc/sys/net/ipv4/conf/eth0/arp_ignore",
              label="arp_ignore=1 on eth0")
    await cmd(EDGE, "echo 2 > /proc/sys/net/ipv4/conf/eth0/arp_announce",
              label="arp_announce=2 on eth0")

    # Flush Tube's ARP cache so it re-learns .196 via HaLow
    await cmd(TUBE, f"ip neigh flush {EDGE_HALOW_IP} 2>/dev/null; echo ok",
              label="Flush ARP .196 on Tube")

    # Show final routes
    await cmd(EDGE, "ip route show", label="Edge routes")
    return True


# ═══════════════════════════════════════════════════════════
# FASE 3: VERIFICAR HALOW
# ═══════════════════════════════════════════════════════════
async def phase3_verify():
    print("\n" + "=" * 60)
    print("  FASE 3: Verificar enlace HaLow")
    print("=" * 60)

    # Show wireless info
    await cmd(TUBE, "iwinfo wlan0 info 2>/dev/null", label="AP iwinfo")
    await cmd(TUBE, "morse_cli -i wlan0 channel 2>/dev/null", label="AP channel")
    await cmd(EDGE, "iwinfo wlan0 info 2>/dev/null", label="STA iwinfo")
    await cmd(EDGE, "morse_cli -i wlan0 channel 2>/dev/null", label="STA channel")

    # Bridge check on Tube (must include wlan0)
    br = await cmd(TUBE, "brctl show 2>/dev/null", label="Tube bridges")
    if "wlan0" not in br:
        print("  ADVERTENCIA: wlan0 NO está en el bridge de Tube!", flush=True)

    # Ping via HaLow
    ping1 = await cmd(EDGE, "ping -c 5 -W 3 -I wlan0 192.168.1.103", timeout=25,
                      label="Edge -> Tube via wlan0")
    loss_m = re.search(r'(\d+)% packet loss', ping1)
    loss1 = int(loss_m.group(1)) if loss_m else 100

    ping2 = await cmd(TUBE, f"ping -c 5 -W 3 {EDGE_HALOW_IP}", timeout=25,
                      label="Tube -> Edge via HaLow")
    loss_m2 = re.search(r'(\d+)% packet loss', ping2)
    loss2 = int(loss_m2.group(1)) if loss_m2 else 100

    if loss1 > 50 or loss2 > 50:
        print(f"  FALLO: Packet loss demasiado alto (Edge→Tube: {loss1}%, Tube→Edge: {loss2}%)")
        return False

    # Check iperf3 availability
    for dev in [EDGE, TUBE]:
        check = await cmd(dev, "which iperf3 2>/dev/null")
        if not check:
            print(f"  Instalando iperf3 en {dev['name']}...", flush=True)
            await cmd(dev, "opkg update; opkg install iperf3", timeout=60)

    # Pre-cleanup
    await cmd(EDGE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
    await cmd(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)

    print(f"\n  HaLow OK: loss Edge→Tube={loss1}%, Tube→Edge={loss2}%", flush=True)
    return True


# ═══════════════════════════════════════════════════════════
# TEST 1: THROUGHPUT TCP (60s, intervalos 1s)
# ═══════════════════════════════════════════════════════════
async def test1_tcp():
    print("\n" + "=" * 60)
    print("  TEST 1: Throughput TCP (iperf3, 60s, intervalos 1s)")
    print("=" * 60)

    results = {}

    for direction, server, client, target, bind_arg in [
        ("Upload (Edge->Tube)", TUBE, EDGE, "192.168.1.103", f"-B {EDGE_HALOW_IP}"),
        ("Download (Tube->Edge)", EDGE, TUBE, EDGE_HALOW_IP, ""),
    ]:
        print(f"\n  --- {direction} ---", flush=True)

        # Counters before
        e_before = await wlan0_counters(EDGE)
        t_before = await wlan0_counters(TUBE)

        # iperf3 server
        ok = await ensure_iperf3_server(server)
        if not ok:
            print("  WARN: iperf3 server puede no estar listo", flush=True)

        # iperf3 client (60s)
        print(f"  Ejecutando iperf3 (60s)...", flush=True)
        try:
            raw = await cmd_long(
                client,
                f"iperf3 -c {target} {bind_arg} -t 60 -i 1 -J".strip(),
                timeout=120
            )
            data = json.loads(raw)
            results[direction] = data

            intervals = data.get("intervals", [])
            throughputs = [iv["sum"]["bits_per_second"] / 1e6 for iv in intervals if "sum" in iv]

            end_sent = data.get("end", {}).get("sum_sent", {})
            end_recv = data.get("end", {}).get("sum_received", {})
            avg_sent = end_sent.get("bits_per_second", 0) / 1e6
            avg_recv = end_recv.get("bits_per_second", 0) / 1e6
            retrans = end_sent.get("retransmits", "N/A")

            print(f"  Sent: {avg_sent:.2f} Mbps | Recv: {avg_recv:.2f} Mbps | Retrans: {retrans}")
            if throughputs:
                print(f"  Min: {min(throughputs):.2f} | Max: {max(throughputs):.2f} | Samples: {len(throughputs)}")

        except json.JSONDecodeError:
            print(f"  ERROR: iperf3 no devolvió JSON válido")
            print(f"  Raw output (primeros 500 chars): {raw[:500]}")
            results[direction] = {"error": "invalid JSON", "raw": raw[:1000]}
        except Exception as e:
            print(f"  ERROR: {e}")
            results[direction] = {"error": str(e)}

        # Counters after
        e_after = await wlan0_counters(EDGE)
        t_after = await wlan0_counters(TUBE)

        etx = e_after["tx_bytes"] - e_before["tx_bytes"]
        erx = e_after["rx_bytes"] - e_before["rx_bytes"]
        ttx = t_after["tx_bytes"] - t_before["tx_bytes"]
        trx = t_after["rx_bytes"] - t_before["rx_bytes"]

        print(f"  HALOW PROOF: Edge wlan0 TX={fmt_bytes(etx)} RX={fmt_bytes(erx)} | Tube wlan0 TX={fmt_bytes(ttx)} RX={fmt_bytes(trx)}")

        if direction in results and "error" not in results[direction]:
            results[direction]["halow_verification"] = {
                "edge_wlan0_tx_bytes": etx, "edge_wlan0_rx_bytes": erx,
                "tube_wlan0_tx_bytes": ttx, "tube_wlan0_rx_bytes": trx,
            }

        await cmd(server, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        await asyncio.sleep(3)

    save_json(f"tcp_throughput_{TIMESTAMP}.json", results)

    rows = []
    for direction, data in results.items():
        if isinstance(data, dict) and "error" not in data:
            for i, iv in enumerate(data.get("intervals", [])):
                s = iv.get("sum", {})
                rows.append([direction, i + 1,
                             round(s.get("bits_per_second", 0) / 1e6, 3),
                             s.get("bytes", 0), s.get("retransmits", 0)])
    save_csv(f"tcp_throughput_{TIMESTAMP}.csv",
             ["direction", "second", "throughput_mbps", "bytes", "retransmits"], rows)

    return results


# ═══════════════════════════════════════════════════════════
# TEST 2: THROUGHPUT UDP A DISTINTAS TASAS
# ═══════════════════════════════════════════════════════════
async def test2_udp():
    print("\n" + "=" * 60)
    print("  TEST 2: Throughput UDP (Edge->Tube, distintas tasas)")
    print("=" * 60)

    rates = ["500K", "1M", "2M", "4M", "6M", "8M"]
    results = []

    for rate in rates:
        print(f"\n  --- UDP @ {rate}bps (15s) ---", flush=True)

        e_before = await wlan0_counters(EDGE)

        ok = await ensure_iperf3_server(TUBE)
        if not ok:
            print("  WARN: server no listo", flush=True)

        try:
            raw = await cmd_long(
                EDGE,
                f"iperf3 -c 192.168.1.103 -B {EDGE_HALOW_IP} -u -b {rate} -t 15 -i 1 -J",
                timeout=60
            )
            data = json.loads(raw)

            udp_end = data.get("end", {}).get("sum", {})
            actual_mbps = udp_end.get("bits_per_second", 0) / 1e6
            jitter = udp_end.get("jitter_ms", 0)
            lost = udp_end.get("lost_packets", 0)
            total = udp_end.get("packets", 1)
            loss_pct = udp_end.get("lost_percent", (lost / max(total, 1) * 100))

            results.append({
                "target_rate": rate,
                "actual_mbps": round(actual_mbps, 3),
                "jitter_ms": round(jitter, 3),
                "lost_packets": lost,
                "total_packets": total,
                "loss_percent": round(loss_pct, 2),
            })
            print(f"  Actual: {actual_mbps:.2f} Mbps | Jitter: {jitter:.2f} ms | Loss: {loss_pct:.1f}%")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"target_rate": rate, "error": str(e)})

        e_after = await wlan0_counters(EDGE)
        etx = e_after["tx_bytes"] - e_before["tx_bytes"]
        print(f"  HALOW PROOF: Edge wlan0 TX={fmt_bytes(etx)}")

        await cmd(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        await asyncio.sleep(3)

    save_json(f"udp_throughput_{TIMESTAMP}.json", results)
    csv_rows = [[r.get("target_rate"), r.get("actual_mbps"), r.get("jitter_ms"),
                 r.get("lost_packets"), r.get("total_packets"), r.get("loss_percent")]
                for r in results if "error" not in r]
    save_csv(f"udp_throughput_{TIMESTAMP}.csv",
             ["target_rate", "actual_mbps", "jitter_ms", "lost_packets", "total_packets", "loss_pct"],
             csv_rows)

    return results


# ═══════════════════════════════════════════════════════════
# TEST 3: LATENCIA ICMP (200 pings via HaLow)
# ═══════════════════════════════════════════════════════════
async def test3_latency():
    print("\n" + "=" * 60)
    print("  TEST 3: Latencia ICMP (200 pings, Edge->Tube via wlan0)")
    print("=" * 60)

    e_before = await wlan0_counters(EDGE)

    # Forcing wlan0 interface explicitly
    raw = await cmd_long(EDGE, "ping -c 200 -i 0.5 -I wlan0 192.168.1.103", timeout=150)

    e_after = await wlan0_counters(EDGE)
    etx = e_after["tx_pkts"] - e_before["tx_pkts"]
    print(f"  HALOW PROOF: Edge wlan0 TX packets during ping: {etx}")

    latencies = []
    for line in raw.split('\n'):
        m = re.search(r'time[=<](\d+\.?\d*)', line)
        if m:
            latencies.append(float(m.group(1)))

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
        "interface": "wlan0 (HaLow forced)",
        "samples": len(latencies),
        "min_ms": rtt_min,
        "avg_ms": rtt_avg,
        "max_ms": rtt_max,
        "mdev_ms": rtt_mdev,
        "packet_loss_pct": loss_pct,
        "latencies": latencies,
    }

    print(f"  Samples: {len(latencies)} | Min: {rtt_min:.2f} | Avg: {rtt_avg:.2f} | Max: {rtt_max:.2f} | Mdev: {rtt_mdev:.2f} ms")
    print(f"  Packet loss: {loss_pct}%")

    save_json(f"latency_{TIMESTAMP}.json", result)
    csv_rows = [[i + 1, lat] for i, lat in enumerate(latencies)]
    save_csv(f"latency_{TIMESTAMP}.csv", ["ping_number", "rtt_ms"], csv_rows)

    return result


# ═══════════════════════════════════════════════════════════
# TEST 4: ESTABILIDAD TEMPORAL (20 mediciones x 5s)
# ═══════════════════════════════════════════════════════════
async def test4_stability():
    N_ROUNDS = 20
    print("\n" + "=" * 60)
    print(f"  TEST 4: Estabilidad ({N_ROUNDS} mediciones x 5s, cada 10s)")
    print("=" * 60)

    results = []
    e_before = await wlan0_counters(EDGE)

    for i in range(N_ROUNDS):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{i+1:2d}/{N_ROUNDS}] {ts} ", end="", flush=True)

        ok = await ensure_iperf3_server(TUBE)

        try:
            raw = await cmd(EDGE,
                            f"iperf3 -c 192.168.1.103 -B {EDGE_HALOW_IP} -t 5 -J",
                            timeout=30)
            data = json.loads(raw)

            sent = data.get("end", {}).get("sum_sent", {})
            recv = data.get("end", {}).get("sum_received", {})
            sent_mbps = sent.get("bits_per_second", 0) / 1e6
            recv_mbps = recv.get("bits_per_second", 0) / 1e6
            retrans = sent.get("retransmits", 0)

            # Wireless stats
            winfo = await cmd(EDGE,
                              "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Noise|Bit Rate'",
                              timeout=10)
            sig_m = re.search(r'Signal:\s*(-?\d+)', winfo)
            noi_m = re.search(r'Noise:\s*(-?\d+)', winfo)
            sig = int(sig_m.group(1)) if sig_m else None
            noi = int(noi_m.group(1)) if noi_m else None

            results.append({
                "sample": i + 1, "timestamp": ts,
                "sent_mbps": round(sent_mbps, 3),
                "recv_mbps": round(recv_mbps, 3),
                "retransmits": retrans,
                "signal_dbm": sig, "noise_dbm": noi,
                "snr_db": (sig - noi) if sig is not None and noi is not None else None,
            })
            print(f"TX: {sent_mbps:.2f} | RX: {recv_mbps:.2f} Mbps | Signal: {sig} dBm | Retrans: {retrans}")

        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"sample": i + 1, "timestamp": ts, "error": str(e)})

        await cmd(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)

    e_after = await wlan0_counters(EDGE)
    etx = e_after["tx_bytes"] - e_before["tx_bytes"]
    print(f"\n  HALOW PROOF: Edge wlan0 TX total en estabilidad: {fmt_bytes(etx)}")

    save_json(f"stability_{TIMESTAMP}.json", results)
    csv_rows = [[r.get("sample"), r.get("timestamp"), r.get("sent_mbps"),
                 r.get("recv_mbps"), r.get("retransmits"),
                 r.get("signal_dbm"), r.get("noise_dbm"), r.get("snr_db")]
                for r in results if "error" not in r]
    save_csv(f"stability_{TIMESTAMP}.csv",
             ["sample", "timestamp", "sent_mbps", "recv_mbps", "retransmits",
              "signal_dbm", "noise_dbm", "snr_db"], csv_rows)

    return results


# ═══════════════════════════════════════════════════════════
# TEST 5: WIRELESS STATS SNAPSHOT
# ═══════════════════════════════════════════════════════════
async def test5_wireless_stats():
    print("\n" + "=" * 60)
    print("  TEST 5: Estadísticas wireless detalladas")
    print("=" * 60)

    stats = {}

    for label, dev in [("edge", EDGE), ("tube", TUBE)]:
        info = await cmd(dev, "iwinfo wlan0 info 2>/dev/null", timeout=15)
        assoc = await cmd(dev, "iwinfo wlan0 assoclist 2>/dev/null", timeout=15)
        station = await cmd(dev, "iw dev wlan0 station dump 2>/dev/null", timeout=15)
        ip_stats = await cmd(dev, "ip -s link show wlan0 2>/dev/null", timeout=15)
        proc_dev = await cmd(dev, "cat /proc/net/dev | grep wlan0", timeout=10)
        morse_ch = await cmd(dev, "morse_cli -i wlan0 channel 2>/dev/null", timeout=10)

        stats[label] = {
            "iwinfo": info,
            "assoclist": assoc,
            "station_dump": station,
            "ip_link_stats": ip_stats,
            "proc_net_dev": proc_dev,
            "morse_channel": morse_ch,
        }

        print(f"\n  --- {dev['name']} ---")
        print(f"  {info[:400]}")
        if assoc:
            print(f"  Assoclist: {assoc[:300]}")
        print(f"  Morse: {morse_ch}")

    save_json(f"wireless_stats_{TIMESTAMP}.json", stats)
    return stats


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
async def main():
    print("=" * 60)
    print("  SUITE DE PRUEBAS HALOW PARA TESIS UNAL")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Topología: WAN (.1) --Eth-- Tube-AHM AP (.103) ==HaLow 909MHz 2MHz== Edge STA (.196)")
    print(f"  SSH Control: Edge via Ethernet (.111) | Data: HaLow (.196)")
    print(f"  Datos: {OUTPUT_DIR}")
    print(f"  Timestamp: {TIMESTAMP}")
    print("=" * 60)

    # FASE 1: Setup HaLow
    if not await phase1_setup():
        print("\nABORTADO: HaLow no se pudo configurar")
        return

    # FASE 2: Fix Routing
    await phase2_routing()

    # FASE 3: Verify
    if not await phase3_verify():
        print("\nABORTADO: Verificación HaLow falló")
        return

    # Save initial wlan0 counters
    e0 = await wlan0_counters(EDGE)
    t0 = await wlan0_counters(TUBE)

    all_results = {}

    # TEST 1: TCP Throughput
    all_results["tcp_throughput"] = await test1_tcp()

    # TEST 2: UDP Throughput
    all_results["udp_throughput"] = await test2_udp()

    # TEST 3: Latency
    all_results["latency"] = await test3_latency()

    # TEST 4: Stability
    all_results["stability"] = await test4_stability()

    # TEST 5: Wireless stats
    all_results["wireless_stats"] = await test5_wireless_stats()

    # Final wlan0 counters
    e1 = await wlan0_counters(EDGE)
    t1 = await wlan0_counters(TUBE)

    total_edge_tx = e1["tx_bytes"] - e0["tx_bytes"]
    total_edge_rx = e1["rx_bytes"] - e0["rx_bytes"]
    total_tube_tx = t1["tx_bytes"] - t0["tx_bytes"]
    total_tube_rx = t1["rx_bytes"] - t0["rx_bytes"]

    summary = {
        "timestamp": TIMESTAMP,
        "topology": "WAN(.1)--Eth--Tube-AHM_AP(.103)==HaLow_909MHz_2MHz==Edge_STA(.196)",
        "ssh_control": "Edge via Ethernet (.111)",
        "channel": CHANNEL,
        "bandwidth_mhz": S1G_CHANBW,
        "halow_total_traffic": {
            "edge_wlan0_tx": total_edge_tx,
            "edge_wlan0_rx": total_edge_rx,
            "tube_wlan0_tx": total_tube_tx,
            "tube_wlan0_rx": total_tube_rx,
            "edge_wlan0_tx_human": fmt_bytes(total_edge_tx),
            "edge_wlan0_rx_human": fmt_bytes(total_edge_rx),
        }
    }
    all_results["summary"] = summary

    save_json(f"all_tests_{TIMESTAMP}.json", all_results)

    print("\n" + "=" * 60)
    print("  PRUEBAS COMPLETAS")
    print(f"  Datos en: {OUTPUT_DIR}")
    print(f"  HaLow total: Edge TX={fmt_bytes(total_edge_tx)} RX={fmt_bytes(total_edge_rx)}")
    print(f"               Tube TX={fmt_bytes(total_tube_tx)} RX={fmt_bytes(total_tube_rx)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
