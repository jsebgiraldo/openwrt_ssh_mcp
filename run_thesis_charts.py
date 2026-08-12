#!/usr/bin/env python3
"""
Generate thesis-quality charts and report for IEEE 802.11ah (HaLow) tests.
Dataset: 20260225_203123 - Channel 14, 909 MHz, 2 MHz BW, WPA3-SAE.
Topology: WAN(.1) -> Eth -> Tube-AHM AP(.103) ==HaLow== Edge STA(.196)

Generates 6 publication-quality figures + Markdown report.
"""

import json
import os
import sys
import numpy as np
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch

# ---- Config ----
TS = "20260225_203123"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_data")
FIGS_DIR = os.path.join(DATA_DIR, "figures")
os.makedirs(FIGS_DIR, exist_ok=True)

# HaLow config for labels
HALOW_CFG = "Canal 14, 909 MHz, 2 MHz BW, WPA3-SAE"
HALOW_SHORT = "2 MHz / 909 MHz"

# Colors
C = {
    'upload': '#2196F3',
    'download': '#FF5722',
    'signal': '#4CAF50',
    'latency': '#9C27B0',
    'udp': '#FF9800',
    'retrans': '#F44336',
    'snr': '#FF9800',
}

plt.rcParams.update({
    'font.size': 11,
    'font.family': 'sans-serif',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})


def load_json(name):
    path = os.path.join(DATA_DIR, name)
    with open(path, encoding='utf-8') as f:
        return json.load(f)


import re

def parse_wireless(raw):
    """Parse raw wireless stats into structured dict."""
    result = {}
    for side in ['edge', 'tube']:
        d = raw.get(side, {})
        iwinfo = d.get("iwinfo", "")
        assoc = d.get("assoclist", "")

        sig_m = re.search(r'Signal:\s*(-?\d+)\s*dBm', iwinfo)
        noise_m = re.search(r'Noise:\s*(-?\d+)\s*dBm', iwinfo)
        snr_m = re.search(r'SNR\s+(\d+)', assoc)

        # TX/RX from assoclist
        tx_m = re.search(r'TX:\s*([\d.]+)\s*MBit/s,\s*MCS\s*(\d+),\s*(\d+)MHz', assoc)
        rx_m = re.search(r'RX:\s*([\d.]+)\s*MBit/s,\s*MCS\s*(\d+),\s*(\d+)MHz', assoc)

        result[side] = {
            'signal_dbm': int(sig_m.group(1)) if sig_m else None,
            'noise_dbm': int(noise_m.group(1)) if noise_m else None,
            'snr_db': int(snr_m.group(1)) if snr_m else None,
            'tx_rate': f"{tx_m.group(1)} MBit/s" if tx_m else "N/A",
            'tx_mcs': f"MCS {tx_m.group(2)}, {tx_m.group(3)}MHz" if tx_m else "N/A",
            'rx_rate': f"{rx_m.group(1)} MBit/s" if rx_m else "N/A",
            'rx_mcs': f"MCS {rx_m.group(2)}, {rx_m.group(3)}MHz" if rx_m else "N/A",
        }
    return result


# ============================================================
# FIG 1: TCP Throughput - Upload & Download (time series)
# ============================================================
def fig_tcp_throughput(upload_data, download_data):
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle(f'Throughput TCP sobre enlace IEEE 802.11ah (HaLow)\n{HALOW_CFG}',
                 fontsize=14, fontweight='bold')

    for idx, (label, data, color) in enumerate([
        ("Upload (Edge STA -> Tube-AHM AP)", upload_data, C['upload']),
        ("Download (Tube-AHM AP -> Edge STA) [-R]", download_data, C['download']),
    ]):
        intervals = data.get("intervals", [])
        if not intervals:
            continue

        seconds = list(range(1, len(intervals) + 1))
        # In reverse mode, the "sum" still has bits_per_second
        throughputs = [iv.get("sum", {}).get("bits_per_second", 0) / 1e6 for iv in intervals]

        ax = axes[idx]
        ax.plot(seconds, throughputs, color=color, linewidth=1.2, alpha=0.8)
        ax.fill_between(seconds, throughputs, alpha=0.12, color=color)

        avg = np.mean(throughputs) if throughputs else 0
        ax.axhline(y=avg, color=color, linestyle='--', alpha=0.5,
                   label=f'Promedio: {avg:.2f} Mbps')

        ax.set_ylabel('Throughput (Mbps)')
        ax.set_title(label, fontsize=12)
        ax.legend(loc='upper right')

        if throughputs:
            stats = f'Min: {min(throughputs):.2f} | Max: {max(throughputs):.2f} | sigma: {np.std(throughputs):.2f} Mbps'
            ax.text(0.02, 0.05, stats, transform=ax.transAxes, fontsize=9,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='wheat', alpha=0.5))

    axes[-1].set_xlabel('Tiempo (s)')
    plt.tight_layout()
    path = os.path.join(FIGS_DIR, 'fig01_tcp_throughput.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")
    return path


# ============================================================
# FIG 2: UDP Throughput vs target rate + Jitter/Loss
# ============================================================
def fig_udp_throughput(udp_data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    fig.suptitle(f'Throughput UDP sobre enlace IEEE 802.11ah ({HALOW_SHORT})',
                 fontsize=14, fontweight='bold')

    rates = [r["target_rate"] for r in udp_data]
    actuals = [r["actual_mbps"] for r in udp_data]
    jitters = [r["jitter_ms"] for r in udp_data]
    losses = [r["loss_percent"] for r in udp_data]

    # Parse numeric target rates
    target_num = []
    for r in rates:
        if 'K' in r:
            target_num.append(float(r.replace('K', '')) / 1000)
        else:
            target_num.append(float(r.replace('M', '')))

    x = np.arange(len(rates))
    width = 0.35

    # Left: actual vs target
    ax1.bar(x - width/2, target_num, width, label='Tasa objetivo', color='#BBDEFB', edgecolor='#1565C0')
    bars = ax1.bar(x + width/2, actuals, width, label='Throughput real', color=C['udp'], edgecolor='#E65100')
    for bar, val in zip(bars, actuals):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.03,
                f'{val:.2f}', ha='center', fontsize=8, fontweight='bold')
    ax1.set_xlabel('Tasa objetivo')
    ax1.set_ylabel('Throughput (Mbps)')
    ax1.set_title('Throughput real vs objetivo')
    ax1.set_xticks(x)
    ax1.set_xticklabels(rates)
    ax1.legend()

    # Right: jitter + loss
    ax2_twin = ax2.twinx()
    line1 = ax2.plot(x, jitters, 'o-', color=C['latency'], linewidth=2, markersize=6, label='Jitter (ms)')
    line2 = ax2_twin.plot(x, losses, 's-', color=C['retrans'], linewidth=2, markersize=6, label='Perdida (%)')
    ax2.set_xlabel('Tasa objetivo')
    ax2.set_ylabel('Jitter (ms)', color=C['latency'])
    ax2_twin.set_ylabel('Perdida de paquetes (%)', color=C['retrans'])
    ax2.set_title('Jitter y perdida de paquetes')
    ax2.set_xticks(x)
    ax2.set_xticklabels(rates)
    lines = line1 + line2
    ax2.legend(lines, [l.get_label() for l in lines], loc='upper left')

    plt.tight_layout()
    path = os.path.join(FIGS_DIR, 'fig02_udp_throughput.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")
    return path


# ============================================================
# FIG 3: Latency analysis (histogram + CDF + time series)
# ============================================================
def fig_latency(lat_data):
    latencies = lat_data.get("latencies", [])
    if not latencies:
        print("  No latency data")
        return None

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(f'Analisis de latencia ICMP sobre enlace IEEE 802.11ah ({HALOW_SHORT})',
                 fontsize=14, fontweight='bold')

    # 1. Histogram
    ax1 = axes[0]
    # Filter outliers for better histogram visibility
    p99 = np.percentile(latencies, 99)
    normal = [l for l in latencies if l <= p99 * 1.5]
    ax1.hist(normal, bins=30, color=C['latency'], alpha=0.7, edgecolor='white')
    ax1.axvline(np.mean(latencies), color='red', linestyle='--',
                label=f'Media: {np.mean(latencies):.2f} ms')
    ax1.axvline(np.median(latencies), color='orange', linestyle='--',
                label=f'Mediana: {np.median(latencies):.2f} ms')
    ax1.set_xlabel('RTT (ms)')
    ax1.set_ylabel('Frecuencia')
    ax1.set_title('Distribucion de latencia')
    ax1.legend(fontsize=9)

    # 2. CDF
    ax2 = axes[1]
    sorted_lat = np.sort(latencies)
    cdf = np.arange(1, len(sorted_lat) + 1) / len(sorted_lat) * 100
    ax2.plot(sorted_lat, cdf, color=C['latency'], linewidth=2)
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99_val = np.percentile(latencies, 99)
    for pct, val, col in [(50, p50, 'green'), (95, p95, 'orange'), (99, p99_val, 'red')]:
        ax2.axhline(pct, color='gray', linestyle=':', alpha=0.4)
        ax2.axvline(val, color=col, linestyle='--', alpha=0.6,
                    label=f'P{pct}: {val:.2f} ms')
    ax2.set_xlabel('RTT (ms)')
    ax2.set_ylabel('Percentil (%)')
    ax2.set_title('CDF de latencia')
    ax2.legend(fontsize=9)

    # 3. Time series
    ax3 = axes[2]
    ax3.plot(range(1, len(latencies) + 1), latencies, color=C['latency'],
             linewidth=0.8, alpha=0.7)
    ax3.axhline(np.mean(latencies), color='red', linestyle='--', alpha=0.5)
    ax3.set_xlabel('Numero de ping')
    ax3.set_ylabel('RTT (ms)')
    ax3.set_title('Latencia en el tiempo')

    stats = (f'N={len(latencies)}\n'
             f'u={np.mean(latencies):.2f} ms\n'
             f's={np.std(latencies):.2f} ms\n'
             f'Min={min(latencies):.2f} ms\n'
             f'Max={max(latencies):.2f} ms\n'
             f'Loss={lat_data["packet_loss_pct"]}%')
    ax3.text(0.98, 0.98, stats, transform=ax3.transAxes, fontsize=9,
             va='top', ha='right',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='lavender', alpha=0.8))

    plt.tight_layout()
    path = os.path.join(FIGS_DIR, 'fig03_latency.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")
    return path


# ============================================================
# FIG 4: Stability (throughput + signal over 20 samples)
# ============================================================
def fig_stability(stab_data):
    valid = [r for r in stab_data if "error" not in r]
    if not valid:
        print("  No stability data")
        return None

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    fig.suptitle(f'Estabilidad del enlace IEEE 802.11ah ({HALOW_SHORT}) - 20 muestras',
                 fontsize=14, fontweight='bold')

    samples = [r["sample"] for r in valid]
    sent = [r["sent_mbps"] for r in valid]
    recv = [r["recv_mbps"] for r in valid]
    signals = [r["signal_dbm"] for r in valid]
    snrs = [r["snr_db"] for r in valid]
    retrans = [r["retransmits"] for r in valid]

    # Panel 1: Throughput
    ax1 = axes[0]
    ax1.plot(samples, sent, 'o-', color=C['upload'], linewidth=2, markersize=5, label='TX (enviado)')
    ax1.plot(samples, recv, 's-', color=C['download'], linewidth=2, markersize=5, label='RX (recibido)')
    ax1.axhline(np.mean(sent), color=C['upload'], linestyle='--', alpha=0.4)
    ax1.axhline(np.mean(recv), color=C['download'], linestyle='--', alpha=0.4)
    ax1.set_ylabel('Throughput (Mbps)')
    ax1.set_title('Throughput TCP (5s por muestra)')
    ax1.legend(loc='upper right')
    stats = (f'TX: u={np.mean(sent):.2f}, s={np.std(sent):.2f} Mbps\n'
             f'RX: u={np.mean(recv):.2f}, s={np.std(recv):.2f} Mbps')
    ax1.text(0.02, 0.05, stats, transform=ax1.transAxes, fontsize=9,
             bbox=dict(boxstyle='round,pad=0.3', facecolor='wheat', alpha=0.5))

    # Panel 2: Signal + SNR
    ax2 = axes[1]
    ax2.plot(samples, signals, 'o-', color=C['signal'], linewidth=2, markersize=5, label='RSSI (dBm)')
    ax2_twin = ax2.twinx()
    ax2_twin.plot(samples, snrs, 's-', color=C['snr'], linewidth=2, markersize=5, label='SNR (dB)')
    ax2.set_ylabel('RSSI (dBm)', color=C['signal'])
    ax2_twin.set_ylabel('SNR (dB)', color=C['snr'])
    ax2.set_title('Calidad de senal')
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    # Panel 3: Retransmissions
    ax3 = axes[2]
    ax3.bar(samples, retrans, color=C['retrans'], alpha=0.7, edgecolor='white')
    ax3.set_xlabel('Muestra (#)')
    ax3.set_ylabel('Retransmisiones')
    ax3.set_title('Retransmisiones TCP por muestra')
    ax3.axhline(np.mean(retrans), color=C['retrans'], linestyle='--', alpha=0.5,
                label=f'Promedio: {np.mean(retrans):.1f}')
    ax3.legend()

    plt.tight_layout()
    path = os.path.join(FIGS_DIR, 'fig04_stability.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")
    return path


# ============================================================
# FIG 5: Network topology
# ============================================================
def fig_topology():
    fig, ax = plt.subplots(1, 1, figsize=(16, 8))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 8)
    ax.axis('off')
    ax.set_title('Topologia de Red - Tesis UNAL: IEEE 802.11ah (HaLow)',
                 fontsize=16, fontweight='bold', pad=20)

    devices = [
        (2, 4, 'Internet\n(WAN)', '#E3F2FD', '#1565C0', 2.4, 1.6),
        (6, 4, 'WAN Router\nLinksys WRT1900ACS\n192.168.1.1\nOpenWrt 24.10.4', '#E8F5E9', '#2E7D32', 2.8, 2.0),
        (10, 4, 'Tube-AHM (AP)\nMorse Micro HaLow\n192.168.1.103\nOpenWrt v23.05.3\nTX: 24 dBm', '#F3E5F5', '#6A1B9A', 2.8, 2.2),
        (14, 4, 'Edge Gateway (STA)\nMorse MM6108A1\n192.168.1.196 (HaLow)\n192.168.1.111 (Eth)\nOpenWrt 23.05.5\nTX: 23 dBm', '#FFF3E0', '#E65100', 2.8, 2.4),
    ]

    for x, y, text, bg, border, w, h in devices:
        box = FancyBboxPatch((x - w/2, y - h/2), w, h,
                             boxstyle="round,pad=0.15", facecolor=bg,
                             edgecolor=border, linewidth=2)
        ax.add_patch(box)
        ax.text(x, y, text, ha='center', va='center', fontsize=8, fontweight='bold')

    # Links
    # Internet -> WAN
    ax.annotate('', xy=(4.6, 4), xytext=(3.2, 4),
                arrowprops=dict(arrowstyle='->', color='#1565C0', lw=2))
    ax.text(3.9, 4.5, 'WAN', ha='center', fontsize=9, color='#1565C0')

    # WAN -> Tube-AHM (Ethernet)
    ax.annotate('', xy=(8.6, 4), xytext=(7.4, 4),
                arrowprops=dict(arrowstyle='<->', color='#2E7D32', lw=2))
    ax.text(8, 4.7, 'Ethernet\n100 Mbps', ha='center', fontsize=9, color='#2E7D32')

    # Tube-AHM <-> Edge (HaLow) — wavy line + label
    ax.annotate('', xy=(12.6, 4), xytext=(11.4, 4),
                arrowprops=dict(arrowstyle='<->', color='#E65100', lw=3, linestyle='--'))
    ax.text(12, 6.2, 'IEEE 802.11ah (HaLow)\n909 MHz / 2 MHz BW\nCanal 14 / WPA3-SAE\nRSSI: -43 dBm (STA)\nRSSI: -77 dBm (AP)',
            ha='center', fontsize=9, color='#E65100', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFF8E1', alpha=0.9, edgecolor='#E65100'))

    # Signal asymmetry note
    ax.text(12, 1.5,
            'Asimetria de senal: 38 dB\n'
            'Edge ve AP a -43 dBm (SNR 51) -> MCS 7 (7.5 Mbps)\n'
            'AP ve Edge a -77 dBm (SNR 11) -> MCS 0 (0.3 Mbps)',
            ha='center', fontsize=9,
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFEBEE', alpha=0.9, edgecolor='#C62828'))

    # Control plane note  
    ax.text(12, 0.5,
            'SSH Control: Edge via Ethernet (.111) | Data: HaLow (.196)',
            ha='center', fontsize=8, color='gray', style='italic')

    plt.tight_layout()
    path = os.path.join(FIGS_DIR, 'fig05_topology.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")
    return path


# ============================================================
# FIG 6: Summary dashboard
# ============================================================
def fig_dashboard(upload, download, udp_data, lat_data, stab_data, wireless):
    fig = plt.figure(figsize=(18, 11))
    fig.suptitle('Resumen de Rendimiento - IEEE 802.11ah (HaLow)\n'
                 f'{HALOW_CFG} | UNAL Tesis',
                 fontsize=16, fontweight='bold')

    gs = gridspec.GridSpec(2, 3, hspace=0.4, wspace=0.35)

    # 1. TCP bar chart
    ax1 = fig.add_subplot(gs[0, 0])
    # Upload: sum_sent.bits_per_second, Download: sum_received (since -R)
    up_sent = upload.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0) / 1e6
    up_recv = upload.get("end", {}).get("sum_received", {}).get("bits_per_second", 0) / 1e6
    # For download with -R, the "sum_received" is what Edge actually received
    dl_sent = download.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0) / 1e6
    dl_recv = download.get("end", {}).get("sum_received", {}).get("bits_per_second", 0) / 1e6

    labels = ['Upload\n(Edge->Tube)', 'Download\n(Tube->Edge)']
    sent_vals = [up_sent, dl_sent]
    recv_vals = [up_recv, dl_recv]
    x = np.arange(len(labels))
    w = 0.35
    b1 = ax1.bar(x - w/2, sent_vals, w, label='Enviado', color=C['upload'], edgecolor='white')
    b2 = ax1.bar(x + w/2, recv_vals, w, label='Recibido', color=C['download'], edgecolor='white')
    for bar, val in zip(list(b1) + list(b2), sent_vals + recv_vals):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f'{val:.2f}', ha='center', fontsize=9, fontweight='bold')
    ax1.set_ylabel('Mbps')
    ax1.set_title('Throughput TCP (60s)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.legend(fontsize=9)

    # 2. UDP
    ax2 = fig.add_subplot(gs[0, 1])
    rates = [r["target_rate"] for r in udp_data]
    actuals = [r["actual_mbps"] for r in udp_data]
    bars = ax2.bar(rates, actuals, color=C['udp'], edgecolor='white')
    for bar, val in zip(bars, actuals):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'{val:.2f}', ha='center', fontsize=8)
    ax2.set_ylabel('Mbps')
    ax2.set_title('Throughput UDP real')
    ax2.tick_params(axis='x', rotation=0)

    # 3. Latency boxplot
    ax3 = fig.add_subplot(gs[0, 2])
    lats = lat_data["latencies"]
    bp = ax3.boxplot(lats, patch_artist=True,
                     boxprops=dict(facecolor=C['latency'], alpha=0.5))
    ax3.set_ylabel('RTT (ms)')
    ax3.set_title('Latencia ICMP')
    stats_txt = (f'u={np.mean(lats):.2f} ms\n'
                 f'P50={np.percentile(lats, 50):.2f} ms\n'
                 f'P95={np.percentile(lats, 95):.2f} ms\n'
                 f'Loss={lat_data["packet_loss_pct"]}%')
    ax3.text(0.5, 0.95, stats_txt, transform=ax3.transAxes, ha='center', va='top',
             fontsize=9, bbox=dict(boxstyle='round', facecolor='lavender'))

    # 4. Stability
    ax4 = fig.add_subplot(gs[1, 0:2])
    valid = [r for r in stab_data if "error" not in r]
    samples = [r["sample"] for r in valid]
    sent_s = [r["sent_mbps"] for r in valid]
    recv_s = [r["recv_mbps"] for r in valid]
    retrans_s = [r["retransmits"] for r in valid]

    ax4.plot(samples, sent_s, 'o-', color=C['upload'], markersize=4, linewidth=1.5, label='TX (enviado)')
    ax4.plot(samples, recv_s, 's-', color=C['download'], markersize=4, linewidth=1.5, label='RX (recibido)')
    ax4_twin = ax4.twinx()
    ax4_twin.bar(samples, retrans_s, alpha=0.3, color=C['retrans'], label='Retrans')
    ax4.set_xlabel('Muestra')
    ax4.set_ylabel('Throughput (Mbps)')
    ax4_twin.set_ylabel('Retransmisiones')
    ax4.set_title('Estabilidad (20 muestras x 5s)')
    lines1, labels1 = ax4.get_legend_handles_labels()
    lines2, labels2 = ax4_twin.get_legend_handles_labels()
    ax4.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=9)

    # 5. Summary table
    ax5 = fig.add_subplot(gs[1, 2])
    ax5.axis('off')

    edge_w = wireless.get("edge", {})
    tube_w = wireless.get("tube", {})

    rows = [
        ["TCP Upload", f"{up_recv:.2f} Mbps"],
        ["TCP Download", f"{dl_recv:.2f} Mbps"],
        ["UDP max", f"{max(actuals):.2f} Mbps"],
        ["Latencia (avg)", f"{lat_data['avg_ms']:.2f} ms"],
        ["Latencia (P95)", f"{np.percentile(lats, 95):.2f} ms"],
        ["Pkt loss", f"{lat_data['packet_loss_pct']}%"],
        ["Estab. TX (s)", f"{np.std(sent_s):.2f} Mbps"],
        ["Estab. RX (s)", f"{np.std(recv_s):.2f} Mbps"],
        ["RSSI STA", f"{edge_w.get('signal_dbm', 'N/A')} dBm"],
        ["RSSI AP", f"{tube_w.get('signal_dbm', 'N/A')} dBm"],
        ["Asimetria", f"{abs(edge_w.get('signal_dbm', 0) - tube_w.get('signal_dbm', 0))} dB"],
    ]

    table = ax5.table(cellText=rows, colLabels=['Metrica', 'Valor'],
                      loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.4)
    # Header style
    for j in range(2):
        table[0, j].set_facecolor('#E0E0E0')
        table[0, j].set_text_props(fontweight='bold')
    ax5.set_title('Resumen', fontsize=12, fontweight='bold')

    path = os.path.join(FIGS_DIR, 'fig06_dashboard.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")
    return path


# ============================================================
# MARKDOWN REPORT
# ============================================================
def generate_report(upload, download, udp_data, lat_data, stab_data, wireless):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    up_recv = upload.get("end", {}).get("sum_received", {}).get("bits_per_second", 0) / 1e6
    up_sent = upload.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0) / 1e6
    up_retrans = upload.get("end", {}).get("sum_sent", {}).get("retransmits", 0)
    dl_recv = download.get("end", {}).get("sum_received", {}).get("bits_per_second", 0) / 1e6
    dl_sent = download.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0) / 1e6
    dl_retrans = download.get("end", {}).get("sum_sent", {}).get("retransmits", 0)

    lats = lat_data["latencies"]
    valid_stab = [r for r in stab_data if "error" not in r]
    sent_s = [r["sent_mbps"] for r in valid_stab]
    recv_s = [r["recv_mbps"] for r in valid_stab]

    edge_w = wireless.get("edge", {})
    tube_w = wireless.get("tube", {})

    r = []
    r.append("# Informe de Pruebas - Enlace IEEE 802.11ah (Wi-Fi HaLow)")
    r.append("")
    r.append("**Universidad Nacional de Colombia**")
    r.append(f"**Fecha de pruebas:** 2026-02-25 20:31 - 20:47 UTC-5")
    r.append(f"**Generado:** {now}")
    r.append("")

    r.append("## 1. Configuracion del enlace")
    r.append("")
    r.append("| Parametro | Valor |")
    r.append("|-----------|-------|")
    r.append("| Estandar | IEEE 802.11ah (Wi-Fi HaLow) |")
    r.append("| Frecuencia | 909 MHz (Canal 14, Sub-GHz) |")
    r.append("| Ancho de banda | 2 MHz |")
    r.append("| Seguridad | WPA3-SAE (CCMP) |")
    r.append("| SSID | UNAL-HaLow-Tesis |")
    r.append("| AP | Tube-AHM, Morse Micro, TX 24 dBm, 192.168.1.103 |")
    r.append("| STA | Edge Gateway, MM6108A1, TX 23 dBm, 192.168.1.196 |")
    r.append("| Distancia | ~3m (laboratorio indoor) |")
    r.append("")

    r.append("## 2. Topologia")
    r.append("")
    r.append("```")
    r.append("[Internet] --> [WAN Router .1] --Ethernet--> [Tube-AHM AP .103] ==HaLow 909MHz 2MHz== [Edge STA .196]")
    r.append("                                                                                       [.111 Ethernet control]")
    r.append("```")
    r.append("")
    r.append("**Nota:** El control SSH al Edge se realiza via Ethernet (.111) para no interferir con las mediciones.")
    r.append("Las rutas del Edge fuerzan todo el trafico de datos via wlan0 (HaLow). Verificado con contadores de paquetes wlan0.")
    r.append("")

    r.append("## 3. Resultados")
    r.append("")

    r.append("### 3.1 Throughput TCP (60 segundos)")
    r.append("")
    r.append("| Direccion | Enviado (Mbps) | Recibido (Mbps) | Retransmisiones |")
    r.append("|-----------|---------------|----------------|----------------|")
    r.append(f"| Upload (Edge->Tube) | {up_sent:.2f} | {up_recv:.2f} | {up_retrans} |")
    r.append(f"| Download (Tube->Edge) | {dl_sent:.2f} | {dl_recv:.2f} | {dl_retrans} |")
    r.append("")
    r.append(f"**Asimetria TCP:** El download ({dl_recv:.2f} Mbps) es {dl_recv/up_recv:.1f}x mas rapido que el upload ({up_recv:.2f} Mbps).")
    r.append(f"Esto se debe a la asimetria de senal: el AP transmite a MCS 7 (7.5 Mbps cap) mientras el STA transmite a MCS 2 (2.2 Mbps cap).")
    r.append("")

    r.append("### 3.2 Throughput UDP")
    r.append("")
    r.append("| Tasa objetivo | Throughput real (Mbps) | Jitter (ms) | Perdida (%) |")
    r.append("|--------------|----------------------|-------------|-------------|")
    for u in udp_data:
        r.append(f"| {u['target_rate']} | {u['actual_mbps']:.2f} | {u['jitter_ms']:.2f} | {u['loss_percent']:.1f} |")
    r.append("")
    max_udp = max(udp_data, key=lambda x: x['actual_mbps'])
    r.append(f"**Throughput maximo UDP:** {max_udp['actual_mbps']:.2f} Mbps a tasa objetivo {max_udp['target_rate']}.")
    r.append("Se observa saturacion del canal a partir de 2 Mbps: tasas superiores no producen mayor throughput real y el jitter aumenta.")
    r.append("")

    r.append("### 3.3 Latencia ICMP")
    r.append("")
    r.append(f"| Metrica | Valor |")
    r.append("|---------|-------|")
    r.append(f"| Muestras | {len(lats)} |")
    r.append(f"| Minima | {min(lats):.2f} ms |")
    r.append(f"| Media | {np.mean(lats):.2f} ms |")
    r.append(f"| Mediana | {np.median(lats):.2f} ms |")
    r.append(f"| P95 | {np.percentile(lats, 95):.2f} ms |")
    r.append(f"| P99 | {np.percentile(lats, 99):.2f} ms |")
    r.append(f"| Maxima | {max(lats):.2f} ms |")
    r.append(f"| Desv. estandar | {np.std(lats):.2f} ms |")
    r.append(f"| Perdida | {lat_data['packet_loss_pct']}% |")
    r.append("")

    r.append("### 3.4 Estabilidad (20 muestras x 5s)")
    r.append("")
    r.append("| Metrica | TX (Mbps) | RX (Mbps) |")
    r.append("|---------|-----------|-----------|")
    r.append(f"| Media | {np.mean(sent_s):.2f} | {np.mean(recv_s):.2f} |")
    r.append(f"| Desv. estandar | {np.std(sent_s):.2f} | {np.std(recv_s):.2f} |")
    r.append(f"| Minimo | {min(sent_s):.2f} | {min(recv_s):.2f} |")
    r.append(f"| Maximo | {max(sent_s):.2f} | {max(recv_s):.2f} |")
    r.append(f"| Total retransmisiones | {sum(r_['retransmits'] for r_ in valid_stab)} |")
    r.append("")

    r.append("### 3.5 Estadisticas wireless")
    r.append("")
    r.append("| Parametro | Edge STA | Tube-AHM AP |")
    r.append("|-----------|----------|-------------|")
    r.append(f"| RSSI | {edge_w.get('signal_dbm', 'N/A')} dBm | {tube_w.get('signal_dbm', 'N/A')} dBm |")
    r.append(f"| Noise | {edge_w.get('noise_dbm', 'N/A')} dBm | {tube_w.get('noise_dbm', 'N/A')} dBm |")
    r.append(f"| SNR | {edge_w.get('snr_db', 'N/A')} dB | {tube_w.get('snr_db', 'N/A')} dB |")
    r.append(f"| TX MCS | {edge_w.get('tx_mcs', 'N/A')} | {tube_w.get('tx_mcs', 'N/A')} |")
    r.append(f"| TX Rate | {edge_w.get('tx_rate', 'N/A')} | {tube_w.get('tx_rate', 'N/A')} |")
    r.append(f"| RX MCS | {edge_w.get('rx_mcs', 'N/A')} | {tube_w.get('rx_mcs', 'N/A')} |")
    r.append(f"| TX Power | 23 dBm | 24 dBm |")
    r.append("")
    asym = abs(edge_w.get('signal_dbm', 0) - tube_w.get('signal_dbm', 0))
    r.append(f"**Asimetria de senal:** {asym} dB. El AP ve al STA a {tube_w.get('signal_dbm', 'N/A')} dBm (SNR {tube_w.get('snr_db', 'N/A')}),")
    r.append(f"mientras el STA ve al AP a {edge_w.get('signal_dbm', 'N/A')} dBm (SNR {edge_w.get('snr_db', 'N/A')}). Probable causa: antena o hardware del Edge Gateway.")
    r.append("")

    r.append("## 4. Verificacion de ruta HaLow")
    r.append("")
    r.append("Todos los tests usaron contadores de paquetes en wlan0 (interfaz HaLow) como prueba de que el trafico")
    r.append("efectivamente paso por el enlace 802.11ah y no por Ethernet:")
    r.append("")
    r.append("- **TCP Upload:** Edge wlan0 TX=9.1 MB, Tube wlan0 RX=9.0 MB")
    r.append("- **TCP Download:** Edge wlan0 RX=28.6 MB, Tube wlan0 TX=29.1 MB")
    r.append("- **Latencia:** 374 paquetes TX en wlan0 para 200 pings")
    r.append("- **Estabilidad:** Edge wlan0 TX=13.9 MB total")
    r.append("")
    r.append("Mecanismos de aislamiento de ruta:")
    r.append("- host routes via wlan0 en Edge")
    r.append("- arp_ignore=1 y arp_announce=2 en eth0 del Edge")
    r.append("- iperf3 -B 192.168.1.196 (bind a IP HaLow)")
    r.append("")

    r.append("## 5. Conclusiones")
    r.append("")
    r.append(f"1. **Throughput TCP:** Upload {up_recv:.2f} Mbps, Download {dl_recv:.2f} Mbps. La asimetria de ~{dl_recv/up_recv:.1f}x refleja la diferencia de MCS entre AP y STA.")
    r.append(f"2. **Throughput UDP maximo:** {max_udp['actual_mbps']:.2f} Mbps con 0% perdida. El canal se satura a ~1.3 Mbps en direccion upload.")
    r.append(f"3. **Latencia:** {np.mean(lats):.2f} ms promedio, 0% perdida, adecuada para IoT y aplicaciones de baja velocidad.")
    r.append(f"4. **Estabilidad:** Throughput consistente durante 5 minutos (sigma TX={np.std(sent_s):.2f}, sigma RX={np.std(recv_s):.2f} Mbps).")
    r.append(f"5. **Asimetria de senal ({asym} dB):** Principal limitante del enlace. Sugiere problema de antena/hardware en Edge Gateway.")
    r.append(f"6. **IEEE 802.11ah en 2 MHz:** Confiable (0% loss) con throughput adecuado para sensores y edge computing.")  
    r.append("")

    r.append("---")
    r.append(f"*Generado automaticamente por run_thesis_charts.py | Timestamp: {TS}*")

    report_text = "\n".join(r)
    path = os.path.join(DATA_DIR, f"THESIS_REPORT_{TS}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"  -> {path}")
    return path


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("  GENERADOR DE GRAFICAS Y REPORTE PARA TESIS UNAL")
    print(f"  Dataset: {TS} | {HALOW_CFG}")
    print("=" * 60)

    # Load data
    print("\n  Cargando datos...")
    tcp_data = load_json(f"tcp_throughput_{TS}.json")
    tcp_dl_fix = load_json(f"tcp_download_fix_{TS}.json")
    udp_data = load_json(f"udp_throughput_{TS}.json")
    lat_data = load_json(f"latency_{TS}.json")
    stab_data = load_json(f"stability_{TS}.json")
    wireless_raw = load_json(f"wireless_stats_{TS}.json")
    wireless = parse_wireless(wireless_raw)

    # Extract upload (original) and download (fixed)
    upload = tcp_data.get("Upload (Edge->Tube)", {})
    download = tcp_dl_fix  # This is the fixed download with -R flag

    print("  Datos cargados OK")

    # Generate figures
    print("\n  Generando figuras...")

    print("\n  Fig 1: TCP Throughput")
    fig_tcp_throughput(upload, download)

    print("  Fig 2: UDP Throughput")
    fig_udp_throughput(udp_data)

    print("  Fig 3: Latencia")
    fig_latency(lat_data)

    print("  Fig 4: Estabilidad")
    fig_stability(stab_data)

    print("  Fig 5: Topologia")
    fig_topology()

    print("  Fig 6: Dashboard resumen")
    fig_dashboard(upload, download, udp_data, lat_data, stab_data, wireless)

    # Generate report
    print("\n  Generando reporte Markdown...")
    generate_report(upload, download, udp_data, lat_data, stab_data, wireless)

    print(f"\n  Figuras en: {FIGS_DIR}")
    print(f"  Reporte en: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
