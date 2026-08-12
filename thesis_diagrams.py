#!/usr/bin/env python3
"""
Generador de diagramas para tesis UNAL - Enlace HaLow IEEE 802.11ah.

Genera:
  1. Throughput TCP en el tiempo (Upload/Download)
  2. Throughput UDP vs tasa objetivo
  3. Distribución de latencia (histograma + CDF)
  4. Estabilidad temporal (throughput + señal)
  5. Topología de red
  6. Resumen comparativo

Requiere: matplotlib, numpy (pip install matplotlib numpy)
"""
import json
import os
import sys
import glob
import numpy as np

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
except ImportError:
    print("Instalando matplotlib...")
    os.system(f"{sys.executable} -m pip install matplotlib numpy")
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_data")
FIGS_DIR = os.path.join(DATA_DIR, "figures")
os.makedirs(FIGS_DIR, exist_ok=True)

# Style
plt.rcParams.update({
    'font.size': 11,
    'font.family': 'sans-serif',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})

COLORS = {
    'upload': '#2196F3',
    'download': '#FF5722',
    'signal': '#4CAF50',
    'latency': '#9C27B0',
    'udp': '#FF9800',
    'retrans': '#F44336',
}


def find_latest(pattern):
    """Find latest file matching pattern."""
    files = sorted(glob.glob(os.path.join(DATA_DIR, pattern)))
    return files[-1] if files else None


def load_json(filepath):
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


# =========================================================
# DIAGRAM 1: TCP Throughput over time
# =========================================================
def plot_tcp_throughput(data):
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle('Throughput TCP sobre enlace IEEE 802.11ah (HaLow)\n8 MHz, Canal 12 (908 MHz), WPA3-SAE',
                 fontsize=14, fontweight='bold')

    for idx, (direction, d) in enumerate(data.items()):
        if "error" in d:
            continue
        intervals = d.get("intervals", [])
        seconds = list(range(1, len(intervals) + 1))
        throughputs = [iv.get("sum", {}).get("bits_per_second", 0) / 1e6 for iv in intervals]
        retransmits = [iv.get("sum", {}).get("retransmits", 0) for iv in intervals]

        ax = axes[idx]
        color = COLORS['upload'] if idx == 0 else COLORS['download']

        ax.plot(seconds, throughputs, color=color, linewidth=1.5, alpha=0.8)
        ax.fill_between(seconds, throughputs, alpha=0.15, color=color)

        avg = np.mean(throughputs) if throughputs else 0
        ax.axhline(y=avg, color=color, linestyle='--', alpha=0.5, label=f'Promedio: {avg:.2f} Mbps')

        ax.set_ylabel('Throughput (Mbps)')
        ax.set_title(direction, fontsize=12)
        ax.legend(loc='upper right')

        # Add stats text
        if throughputs:
            stats_text = f'Min: {min(throughputs):.2f} | Max: {max(throughputs):.2f} | σ: {np.std(throughputs):.2f} Mbps'
            ax.text(0.02, 0.05, stats_text, transform=ax.transAxes, fontsize=9,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='wheat', alpha=0.5))

    axes[-1].set_xlabel('Tiempo (s)')
    plt.tight_layout()

    path = os.path.join(FIGS_DIR, 'tcp_throughput.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")


# =========================================================
# DIAGRAM 2: UDP Throughput vs target rate
# =========================================================
def plot_udp_throughput(data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('Throughput UDP sobre enlace IEEE 802.11ah (HaLow)', fontsize=14, fontweight='bold')

    rates_label = []
    actual_mbps = []
    jitter_vals = []
    loss_vals = []

    for entry in data:
        if "error" in entry:
            continue
        rates_label.append(entry["target_rate"])
        actual_mbps.append(entry.get("actual_mbps", 0))
        jitter_vals.append(entry.get("jitter_ms", 0))
        loss_vals.append(entry.get("loss_percent", 0))

    target_numeric = [float(r.replace('M', '')) for r in rates_label]

    # Throughput actual vs objetivo
    x = np.arange(len(rates_label))
    width = 0.35
    ax1.bar(x - width/2, target_numeric, width, label='Tasa objetivo', color='#BBDEFB', edgecolor='#1565C0')
    ax1.bar(x + width/2, actual_mbps, width, label='Throughput real', color=COLORS['udp'], edgecolor='#E65100')
    ax1.set_xlabel('Tasa objetivo (Mbps)')
    ax1.set_ylabel('Throughput (Mbps)')
    ax1.set_title('Throughput real vs objetivo')
    ax1.set_xticks(x)
    ax1.set_xticklabels(rates_label)
    ax1.legend()

    # Jitter y pérdida
    ax2_twin = ax2.twinx()
    line1 = ax2.plot(x, jitter_vals, 'o-', color=COLORS['latency'], linewidth=2, label='Jitter (ms)')
    line2 = ax2_twin.plot(x, loss_vals, 's-', color=COLORS['retrans'], linewidth=2, label='Pérdida (%)')
    ax2.set_xlabel('Tasa objetivo')
    ax2.set_ylabel('Jitter (ms)', color=COLORS['latency'])
    ax2_twin.set_ylabel('Pérdida de paquetes (%)', color=COLORS['retrans'])
    ax2.set_title('Jitter y pérdida de paquetes')
    ax2.set_xticks(x)
    ax2.set_xticklabels(rates_label)

    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax2.legend(lines, labels, loc='upper left')

    plt.tight_layout()
    path = os.path.join(FIGS_DIR, 'udp_throughput.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")


# =========================================================
# DIAGRAM 3: Latency distribution
# =========================================================
def plot_latency(data):
    latencies = data.get("latencies", [])
    if not latencies:
        print("  No hay datos de latencia")
        return

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle('Análisis de latencia ICMP sobre enlace IEEE 802.11ah (HaLow)',
                 fontsize=14, fontweight='bold')

    # Histogram
    ax1 = axes[0]
    ax1.hist(latencies, bins=40, color=COLORS['latency'], alpha=0.7, edgecolor='white')
    ax1.axvline(np.mean(latencies), color='red', linestyle='--', label=f'Media: {np.mean(latencies):.2f} ms')
    ax1.axvline(np.median(latencies), color='orange', linestyle='--', label=f'Mediana: {np.median(latencies):.2f} ms')
    ax1.set_xlabel('RTT (ms)')
    ax1.set_ylabel('Frecuencia')
    ax1.set_title('Distribución de latencia')
    ax1.legend(fontsize=9)

    # CDF
    ax2 = axes[1]
    sorted_lat = np.sort(latencies)
    cdf = np.arange(1, len(sorted_lat) + 1) / len(sorted_lat) * 100
    ax2.plot(sorted_lat, cdf, color=COLORS['latency'], linewidth=2)
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    ax2.axhline(50, color='gray', linestyle=':', alpha=0.5)
    ax2.axhline(95, color='gray', linestyle=':', alpha=0.5)
    ax2.axhline(99, color='gray', linestyle=':', alpha=0.5)
    ax2.axvline(p50, color='green', linestyle='--', alpha=0.5, label=f'P50: {p50:.2f} ms')
    ax2.axvline(p95, color='orange', linestyle='--', alpha=0.5, label=f'P95: {p95:.2f} ms')
    ax2.axvline(p99, color='red', linestyle='--', alpha=0.5, label=f'P99: {p99:.2f} ms')
    ax2.set_xlabel('RTT (ms)')
    ax2.set_ylabel('Percentil (%)')
    ax2.set_title('Función de distribución acumulada (CDF)')
    ax2.legend(fontsize=9)

    # Over time
    ax3 = axes[2]
    ax3.plot(range(1, len(latencies) + 1), latencies, color=COLORS['latency'], linewidth=0.8, alpha=0.7)
    ax3.axhline(np.mean(latencies), color='red', linestyle='--', alpha=0.5)
    ax3.set_xlabel('Número de ping')
    ax3.set_ylabel('RTT (ms)')
    ax3.set_title('Latencia en el tiempo')

    # Stats box
    stats = (f'N={len(latencies)}\n'
             f'μ={np.mean(latencies):.2f} ms\n'
             f'σ={np.std(latencies):.2f} ms\n'
             f'Min={min(latencies):.2f} ms\n'
             f'Max={max(latencies):.2f} ms')
    ax3.text(0.98, 0.98, stats, transform=ax3.transAxes, fontsize=9,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='lavender', alpha=0.8))

    plt.tight_layout()
    path = os.path.join(FIGS_DIR, 'latency_analysis.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")


# =========================================================
# DIAGRAM 4: Stability over time
# =========================================================
def plot_stability(data):
    valid = [r for r in data if "error" not in r]
    if not valid:
        print("  No hay datos de estabilidad")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.suptitle('Estabilidad del enlace IEEE 802.11ah (HaLow) - 5 minutos',
                 fontsize=14, fontweight='bold')

    samples = [r["sample"] for r in valid]
    sent = [r.get("sent_mbps", 0) for r in valid]
    recv = [r.get("recv_mbps", 0) for r in valid]
    signals = [r.get("signal_dbm") for r in valid]
    snrs = [r.get("snr_db") for r in valid]
    retrans = [r.get("retransmits", 0) for r in valid]

    # Throughput
    ax1.plot(samples, sent, 'o-', color=COLORS['upload'], linewidth=2, markersize=4, label='TX (enviado)')
    ax1.plot(samples, recv, 's-', color=COLORS['download'], linewidth=2, markersize=4, label='RX (recibido)')
    ax1.axhline(np.mean(sent), color=COLORS['upload'], linestyle='--', alpha=0.4)
    ax1.axhline(np.mean(recv), color=COLORS['download'], linestyle='--', alpha=0.4)
    ax1.set_ylabel('Throughput (Mbps)')
    ax1.set_title('Throughput TCP en el tiempo')
    ax1.legend(loc='upper right')

    stats_text = (f'TX: μ={np.mean(sent):.2f}, σ={np.std(sent):.2f} Mbps\n'
                  f'RX: μ={np.mean(recv):.2f}, σ={np.std(recv):.2f} Mbps')
    ax1.text(0.02, 0.05, stats_text, transform=ax1.transAxes, fontsize=9,
             bbox=dict(boxstyle='round,pad=0.3', facecolor='wheat', alpha=0.5))

    # Signal + SNR
    valid_signals = [(s, snr) for s, snr in zip(signals, snrs) if s is not None]
    if valid_signals:
        sig_vals = [v[0] for v in valid_signals]
        snr_vals = [v[1] for v in valid_signals]
        sig_samples = [samples[i] for i, s in enumerate(signals) if s is not None]

        ax2.plot(sig_samples, sig_vals, 'o-', color=COLORS['signal'], linewidth=2, markersize=4, label='RSSI (dBm)')
        ax2_twin = ax2.twinx()
        ax2_twin.plot(sig_samples, snr_vals, 's-', color='#FF9800', linewidth=2, markersize=4, label='SNR (dB)')
        ax2.set_xlabel('Muestra (#)')
        ax2.set_ylabel('RSSI (dBm)', color=COLORS['signal'])
        ax2_twin.set_ylabel('SNR (dB)', color='#FF9800')
        ax2.set_title('Señal y SNR en el tiempo')

        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_twin.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    plt.tight_layout()
    path = os.path.join(FIGS_DIR, 'stability.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")


# =========================================================
# DIAGRAM 5: Network topology
# =========================================================
def plot_topology():
    fig, ax = plt.subplots(1, 1, figsize=(14, 7))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 7)
    ax.axis('off')
    ax.set_title('Topología de Red - Tesis UNAL: IEEE 802.11ah (HaLow)',
                 fontsize=16, fontweight='bold', pad=20)

    # Device boxes - Corrected topology: WAN -> Ethernet -> Tube-AHM -> HaLow -> Edge
    devices = [
        (1.5, 3.5, 'Internet\n(WAN)', '#E3F2FD', '#1565C0'),
        (5, 3.5, 'WAN Router\nLinksys WRT1900ACS\n192.168.1.1\nOpenWrt 24.10.4', '#E8F5E9', '#2E7D32'),
        (8.5, 3.5, 'Tube-AHM\nMorseMicro HaLow\n192.168.1.103\nTube-AHM v23.05.3\n(AP)', '#F3E5F5', '#6A1B9A'),
        (12, 3.5, 'Edge Gateway\nMorseMicro MM6108A1\n192.168.1.196\nOpenWrt 23.05.5 Morse-2.9\n(STA)', '#FFF3E0', '#E65100'),
    ]

    for x, y, text, bg, border in devices:
        box = FancyBboxPatch((x - 1.3, y - 1.0), 2.6, 2.0,
                             boxstyle="round,pad=0.15", facecolor=bg,
                             edgecolor=border, linewidth=2)
        ax.add_patch(box)
        ax.text(x, y, text, ha='center', va='center', fontsize=8, fontweight='bold')

    # Links
    # Internet -> WAN
    ax.annotate('', xy=(3.7, 3.5), xytext=(2.8, 3.5),
                arrowprops=dict(arrowstyle='->', color='#1565C0', lw=2))
    ax.text(3.25, 4.0, 'WAN', ha='center', fontsize=8, color='#1565C0')

    # WAN -> Tube-AHM (Ethernet)
    ax.annotate('', xy=(7.2, 3.5), xytext=(6.3, 3.5),
                arrowprops=dict(arrowstyle='<->', color='#2E7D32', lw=2))
    ax.text(6.75, 4.1, 'Ethernet\n100 Mbps', ha='center', fontsize=8, color='#2E7D32')

    # Tube-AHM <-> Edge (HaLow)
    ax.annotate('', xy=(10.7, 3.5), xytext=(9.8, 3.5),
                arrowprops=dict(arrowstyle='<->', color='#E65100', lw=3, linestyle='--'))
    ax.text(10.25, 5.0, 'IEEE 802.11ah\nHaLow Sub-GHz\n908 MHz / 8 MHz BW\nWPA3-SAE', 
            ha='center', fontsize=8, color='#E65100', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFF8E1', alpha=0.9))

    # Legend
    ax.text(1, 1.2, 'Protocolo: IEEE 802.11ah (Wi-Fi HaLow)\n'
                     'Frecuencia: 908 MHz (Sub-GHz, Canal 12)\n'
                     'Ancho de banda: 8 MHz\n'
                     'Seguridad: WPA3-SAE (CCMP)\n'
                     'Chip: Morse Micro MM6108',
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#FAFAFA', edgecolor='#BDBDBD'))

    plt.tight_layout()
    path = os.path.join(FIGS_DIR, 'network_topology.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")


# =========================================================
# DIAGRAM 6: Summary dashboard
# =========================================================
def plot_summary_dashboard(tcp_data, udp_data, latency_data, stability_data):
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle('Resumen de Rendimiento - Enlace IEEE 802.11ah (HaLow) para Tesis UNAL',
                 fontsize=16, fontweight='bold')

    gs = gridspec.GridSpec(2, 3, hspace=0.35, wspace=0.35)

    # 1. TCP summary bar chart
    ax1 = fig.add_subplot(gs[0, 0])
    tcp_labels = []
    tcp_avgs = []
    for direction, d in tcp_data.items():
        if "error" in d:
            continue
        end = d.get("end", {}).get("sum_sent", {})
        avg = end.get("bits_per_second", 0) / 1e6
        tcp_labels.append(direction.split('(')[1].replace(')', ''))
        tcp_avgs.append(avg)
    if tcp_labels:
        bars = ax1.bar(tcp_labels, tcp_avgs, color=[COLORS['upload'], COLORS['download']], edgecolor='white')
        for bar, val in zip(bars, tcp_avgs):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                    f'{val:.1f}', ha='center', fontsize=10, fontweight='bold')
    ax1.set_ylabel('Mbps')
    ax1.set_title('Throughput TCP promedio')

    # 2. UDP max throughput
    ax2 = fig.add_subplot(gs[0, 1])
    if udp_data:
        valid_udp = [r for r in udp_data if "error" not in r]
        rates = [r["target_rate"] for r in valid_udp]
        actuals = [r["actual_mbps"] for r in valid_udp]
        ax2.bar(rates, actuals, color=COLORS['udp'], edgecolor='white')
        ax2.set_ylabel('Mbps')
        ax2.set_title('Throughput UDP real')
        ax2.tick_params(axis='x', rotation=45)

    # 3. Latency box plot
    ax3 = fig.add_subplot(gs[0, 2])
    if latency_data and latency_data.get("latencies"):
        lats = latency_data["latencies"]
        bp = ax3.boxplot(lats, patch_artist=True, boxprops=dict(facecolor=COLORS['latency'], alpha=0.5))
        ax3.set_ylabel('RTT (ms)')
        ax3.set_title('Distribución de latencia')
        ax3.text(0.5, 0.95, f'μ={np.mean(lats):.2f} ms\nP95={np.percentile(lats, 95):.2f} ms',
                transform=ax3.transAxes, ha='center', va='top', fontsize=9,
                bbox=dict(boxstyle='round', facecolor='lavender'))

    # 4. Stability throughput
    ax4 = fig.add_subplot(gs[1, 0:2])
    if stability_data:
        valid_stab = [r for r in stability_data if "error" not in r]
        if valid_stab:
            samples = [r["sample"] for r in valid_stab]
            sent = [r.get("sent_mbps", 0) for r in valid_stab]
            recv = [r.get("recv_mbps", 0) for r in valid_stab]
            ax4.plot(samples, sent, 'o-', color=COLORS['upload'], markersize=3, label='TX')
            ax4.plot(samples, recv, 's-', color=COLORS['download'], markersize=3, label='RX')
            ax4.set_xlabel('Muestra')
            ax4.set_ylabel('Mbps')
            ax4.set_title('Estabilidad del throughput (5 min)')
            ax4.legend()

    # 5. Summary table
    ax5 = fig.add_subplot(gs[1, 2])
    ax5.axis('off')

    summary_rows = []
    # TCP
    for direction, d in tcp_data.items():
        if "error" in d:
            continue
        end = d.get("end", {}).get("sum_sent", {})
        avg = end.get("bits_per_second", 0) / 1e6
        label = "TCP " + ("UL" if "Upload" in direction else "DL")
        summary_rows.append([label, f"{avg:.2f} Mbps"])

    # Latency
    if latency_data and latency_data.get("latencies"):
        summary_rows.append(["Latencia (avg)", f"{latency_data['avg_ms']:.2f} ms"])
        summary_rows.append(["Latencia (P95)", f"{np.percentile(latency_data['latencies'], 95):.2f} ms"])
        summary_rows.append(["Pkt loss", f"{latency_data['packet_loss_pct']}%"])

    # Stability
    if stability_data:
        valid_s = [r.get("sent_mbps", 0) for r in stability_data if "error" not in r]
        if valid_s:
            summary_rows.append(["Estab. (σ)", f"{np.std(valid_s):.2f} Mbps"])

    if summary_rows:
        table = ax5.table(cellText=summary_rows, colLabels=['Métrica', 'Valor'],
                         loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.5)
        ax5.set_title('Resumen', fontsize=12, fontweight='bold')

    path = os.path.join(FIGS_DIR, 'summary_dashboard.png')
    plt.savefig(path)
    plt.close()
    print(f"  -> {path}")


# =========================================================
# MAIN
# =========================================================
def main():
    print("=" * 60)
    print("  GENERADOR DE DIAGRAMAS PARA TESIS UNAL")
    print("=" * 60)

    # Load latest data files
    tcp_file = find_latest("tcp_throughput_*.json")
    udp_file = find_latest("udp_throughput_*.json")
    lat_file = find_latest("latency_*.json")
    stab_file = find_latest("stability_*.json")

    tcp_data = load_json(tcp_file) if tcp_file else {}
    udp_data = load_json(udp_file) if udp_file else []
    lat_data = load_json(lat_file) if lat_file else {}
    stab_data = load_json(stab_file) if stab_file else []

    print(f"\n  Datos encontrados:")
    print(f"    TCP:       {tcp_file}")
    print(f"    UDP:       {udp_file}")
    print(f"    Latencia:  {lat_file}")
    print(f"    Estabilid: {stab_file}")

    # Generate diagrams
    print("\n  Generando diagramas...")

    print("\n  1. Topología de red")
    plot_topology()

    if tcp_data:
        print("  2. Throughput TCP")
        plot_tcp_throughput(tcp_data)

    if udp_data:
        print("  3. Throughput UDP")
        plot_udp_throughput(udp_data)

    if lat_data:
        print("  4. Análisis de latencia")
        plot_latency(lat_data)

    if stab_data:
        print("  5. Estabilidad")
        plot_stability(stab_data)

    print("  6. Dashboard resumen")
    plot_summary_dashboard(tcp_data, udp_data, lat_data, stab_data)

    print(f"\n  Diagramas guardados en: {FIGS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
