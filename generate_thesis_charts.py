#!/usr/bin/env python3
"""
Generate thesis-quality charts for IEEE 802.11ah (HaLow) performance evaluation.
All data from verified HaLow link (wlan0) — Channel 14, 909 MHz, 2 MHz BW.
"""

import json
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# ─── Configuration ────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_data", "20260225_202638")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_charts")
os.makedirs(OUT_DIR, exist_ok=True)

# Style
plt.rcParams.update({
    'font.size': 12,
    'axes.titlesize': 14,
    'axes.labelsize': 13,
    'xtick.labelsize': 11,
    'ytick.labelsize': 11,
    'legend.fontsize': 11,
    'figure.dpi': 150,
    'savefig.dpi': 150,
    'savefig.bbox': 'tight',
    'axes.grid': True,
    'grid.alpha': 0.3,
})

# Colors
C_BLUE = '#2563EB'
C_RED = '#DC2626'
C_GREEN = '#16A34A'
C_ORANGE = '#EA580C'
C_PURPLE = '#9333EA'
C_GRAY = '#6B7280'

# ─── Load data ────────────────────────────────────────────────────────
with open(os.path.join(DATA_DIR, "SUMMARY.json"), "r") as f:
    data = json.load(f)

with open(os.path.join(DATA_DIR, "04b_stability_halow.json"), "r") as f:
    stability = json.load(f)

with open(os.path.join(DATA_DIR, "03b_latency_halow.json"), "r") as f:
    latency = json.load(f)


# ═══════════════════════════════════════════════════════════════════════
# CHART 1: TCP Throughput — Upload vs Download
# ═══════════════════════════════════════════════════════════════════════
def chart_tcp_throughput():
    fig, ax = plt.subplots(figsize=(7, 5))
    
    labels = ['Upload\n(STA → AP → WAN)', 'Download\n(WAN → AP → STA)']
    values = [data['tcp_upload_mbps'], data['tcp_download_mbps']]
    colors = [C_BLUE, C_GREEN]
    
    bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor='white', linewidth=1.5)
    
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.08,
                f'{val:.2f} Mbps', ha='center', va='bottom', fontweight='bold', fontsize=13)
    
    ax.set_ylabel('Throughput (Mbps)')
    ax.set_title('IEEE 802.11ah TCP Throughput\n(Channel 14, 909 MHz, 2 MHz BW, 30s iperf3)')
    ax.set_ylim(0, 5.0)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(0.5))
    
    # Asymmetry annotation
    ratio = data['tcp_download_mbps'] / data['tcp_upload_mbps']
    ax.annotate(f'Asymmetry ratio: {ratio:.1f}:1\n(DL / UL)',
                xy=(0.5, 0.85), xycoords='axes fraction',
                ha='center', fontsize=11, color=C_RED,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#FEE2E2', edgecolor=C_RED, alpha=0.8))
    
    plt.tight_layout()
    path = os.path.join(OUT_DIR, "01_tcp_throughput.png")
    plt.savefig(path)
    plt.close()
    print(f"  ✓ {path}")


# ═══════════════════════════════════════════════════════════════════════
# CHART 2: UDP Throughput vs Target Rate (with loss overlay)
# ═══════════════════════════════════════════════════════════════════════
def chart_udp_throughput():
    fig, ax1 = plt.subplots(figsize=(9, 5.5))
    
    udp = data['udp_results']
    rates_label = ['200K', '500K', '750K', '1M', '1.2M', '1.5M', '2M']
    target_mbps = [0.2, 0.5, 0.75, 1.0, 1.2, 1.5, 2.0]
    achieved = [udp[f'udp_{r}']['mbps'] for r in rates_label]
    loss = [udp[f'udp_{r}']['loss_pct'] for r in rates_label]
    jitter = [udp[f'udp_{r}']['jitter_ms'] for r in rates_label]
    
    x = np.arange(len(rates_label))
    width = 0.35
    
    # Target vs achieved bars
    bars1 = ax1.bar(x - width/2, target_mbps, width, label='Target Rate', color=C_GRAY, alpha=0.4, edgecolor='white')
    bars2 = ax1.bar(x + width/2, achieved, width, label='Achieved Rate', color=C_BLUE, edgecolor='white')
    
    ax1.set_ylabel('Throughput (Mbps)', color='black')
    ax1.set_xlabel('Target UDP Rate')
    ax1.set_xticks(x)
    ax1.set_xticklabels([f'{r} bps' for r in rates_label])
    ax1.set_ylim(0, 2.3)
    ax1.yaxis.set_major_locator(ticker.MultipleLocator(0.25))
    
    # Loss line on secondary axis
    ax2 = ax1.twinx()
    ax2.plot(x, loss, 'o-', color=C_RED, linewidth=2, markersize=7, label='Packet Loss')
    ax2.set_ylabel('Packet Loss (%)', color=C_RED)
    ax2.tick_params(axis='y', labelcolor=C_RED)
    ax2.set_ylim(0, 8)
    
    # Saturation line
    ax1.axhline(y=1.17, color=C_ORANGE, linestyle='--', alpha=0.6, linewidth=1.5)
    ax1.text(0.02, 1.20, 'Max effective throughput ≈ 1.17 Mbps', fontsize=9, color=C_ORANGE)
    
    ax1.set_title('IEEE 802.11ah UDP Throughput & Packet Loss\n(Upload, 15s per rate, via wlan0/HaLow)')
    
    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    plt.tight_layout()
    path = os.path.join(OUT_DIR, "02_udp_throughput_loss.png")
    plt.savefig(path)
    plt.close()
    print(f"  ✓ {path}")


# ═══════════════════════════════════════════════════════════════════════
# CHART 3: UDP Jitter vs Rate
# ═══════════════════════════════════════════════════════════════════════
def chart_udp_jitter():
    fig, ax = plt.subplots(figsize=(8, 5))
    
    udp = data['udp_results']
    rates_label = ['200K', '500K', '750K', '1M', '1.2M', '1.5M', '2M']
    jitter = [udp[f'udp_{r}']['jitter_ms'] for r in rates_label]
    loss = [udp[f'udp_{r}']['loss_pct'] for r in rates_label]
    
    x = np.arange(len(rates_label))
    
    # Color bars by performance zone
    colors = []
    for j, l in zip(jitter, loss):
        if j < 5 and l < 0.5:
            colors.append(C_GREEN)    # Good
        elif j < 15 and l < 2:
            colors.append(C_ORANGE)   # Moderate
        else:
            colors.append(C_RED)      # Degraded
    
    bars = ax.bar(x, jitter, color=colors, width=0.6, edgecolor='white', linewidth=1.5)
    
    for bar, j in zip(bars, jitter):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.3,
                f'{j:.1f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_ylabel('Jitter (ms)')
    ax.set_xlabel('Target UDP Rate')
    ax.set_xticks(x)
    ax.set_xticklabels([f'{r} bps' for r in rates_label])
    ax.set_ylim(0, 25)
    ax.set_title('IEEE 802.11ah UDP Jitter vs Offered Load\n(Lower is better)')
    
    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=C_GREEN, label='Good (< 5 ms, < 0.5% loss)'),
        Patch(facecolor=C_ORANGE, label='Moderate (< 15 ms, < 2% loss)'),
        Patch(facecolor=C_RED, label='Degraded (> 15 ms or > 2% loss)'),
    ]
    ax.legend(handles=legend_elements, loc='upper left')
    
    plt.tight_layout()
    path = os.path.join(OUT_DIR, "03_udp_jitter.png")
    plt.savefig(path)
    plt.close()
    print(f"  ✓ {path}")


# ═══════════════════════════════════════════════════════════════════════
# CHART 4: Latency Comparison (AP vs WAN)
# ═══════════════════════════════════════════════════════════════════════
def chart_latency():
    fig, ax = plt.subplots(figsize=(8, 5))
    
    # Parse RTT values
    ap_rtt = data['latency']['ping_AP_via_wlan0_rtt']
    wan_rtt = data['latency']['ping_WAN_via_halow_rtt']
    
    def parse_rtt(s):
        # "round-trip min/avg/max = 3.528/8.683/18.154 ms"
        parts = s.split('=')[1].strip().split(' ')[0].split('/')
        return float(parts[0]), float(parts[1]), float(parts[2])
    
    ap_min, ap_avg, ap_max = parse_rtt(ap_rtt)
    wan_min, wan_avg, wan_max = parse_rtt(wan_rtt)
    
    labels = ['AP (1 hop)\nEdge → Tube', 'WAN (2 hops)\nEdge → Tube → WAN']
    avgs = [ap_avg, wan_avg]
    mins = [ap_min, wan_min]
    maxs = [ap_max, wan_max]
    
    x = np.arange(len(labels))
    
    # Bar for average
    bars = ax.bar(x, avgs, color=[C_BLUE, C_PURPLE], width=0.5, edgecolor='white', linewidth=1.5)
    
    # Error bars for min/max
    yerr_lower = [a - m for a, m in zip(avgs, mins)]
    yerr_upper = [m - a for a, m in zip(avgs, maxs)]
    ax.errorbar(x, avgs, yerr=[yerr_lower, yerr_upper], fmt='none',
                ecolor='black', capsize=8, capthick=2, linewidth=2)
    
    # Labels
    for bar, avg, mn, mx in zip(bars, avgs, mins, maxs):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + (mx - avg) + 15,
                f'avg: {avg:.1f} ms\nmin: {mn:.1f} / max: {mx:.1f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_ylabel('Round-Trip Time (ms)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title('IEEE 802.11ah Latency (50 ICMP pings via wlan0)\nNote: WAN max of 1090 ms indicates bufferbloat')
    ax.set_ylim(0, 180)
    
    # Note about max
    ax.annotate(f'WAN max: {wan_max:.0f} ms\n(bufferbloat spike)',
                xy=(1, wan_avg + (wan_max - wan_avg)),
                xytext=(0.3, 150),
                arrowprops=dict(arrowstyle='->', color=C_RED),
                fontsize=10, color=C_RED, ha='center')
    
    plt.tight_layout()
    path = os.path.join(OUT_DIR, "04_latency.png")
    plt.savefig(path)
    plt.close()
    print(f"  ✓ {path}")


# ═══════════════════════════════════════════════════════════════════════
# CHART 5: Stability — Ping RTT time series (from raw data)
# ═══════════════════════════════════════════════════════════════════════
def chart_stability():
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Parse raw ping data
    raw = stability.get('stability_raw', '')
    rtts = []
    seq_nums = []
    for line in raw.split('\n'):
        if 'time=' in line:
            try:
                t = float(line.split('time=')[1].split(' ')[0])
                # Extract seq number
                seq = int(line.split('seq=')[1].split(' ')[0])
                rtts.append(t)
                seq_nums.append(seq)
            except (ValueError, IndexError):
                pass
    
    if rtts:
        x = list(range(len(rtts)))
        
        # Color-code by latency
        colors = []
        for r in rtts:
            if r < 20:
                colors.append(C_GREEN)
            elif r < 100:
                colors.append(C_ORANGE)
            else:
                colors.append(C_RED)
        
        ax.scatter(x, rtts, c=colors, s=15, alpha=0.7, edgecolors='none')
        
        # Moving average (window=10)
        if len(rtts) > 10:
            window = 10
            ma = np.convolve(rtts, np.ones(window)/window, mode='valid')
            ax.plot(range(window-1, len(rtts)), ma, color=C_BLUE, linewidth=2,
                    label=f'Moving avg (w={window})', alpha=0.8)
        
        # Stats
        avg = np.mean(rtts)
        p95 = np.percentile(rtts, 95)
        p99 = np.percentile(rtts, 99)
        
        ax.axhline(y=avg, color=C_BLUE, linestyle='--', alpha=0.5, linewidth=1)
        ax.text(len(rtts)*0.02, avg + 15, f'Mean: {avg:.1f} ms', color=C_BLUE, fontsize=10)
        
        ax.axhline(y=p95, color=C_ORANGE, linestyle=':', alpha=0.5, linewidth=1)
        ax.text(len(rtts)*0.02, p95 + 15, f'P95: {p95:.1f} ms', color=C_ORANGE, fontsize=10)
        
        # Stats box
        stats_text = (f'N = {len(rtts)} packets\n'
                      f'Lost = {180 - len(rtts)}\n'
                      f'Min = {np.min(rtts):.1f} ms\n'
                      f'Mean = {avg:.1f} ms\n'
                      f'Median = {np.median(rtts):.1f} ms\n'
                      f'P95 = {p95:.1f} ms\n'
                      f'P99 = {p99:.1f} ms\n'
                      f'Max = {np.max(rtts):.1f} ms')
        ax.text(0.98, 0.98, stats_text, transform=ax.transAxes, fontsize=9,
                verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor=C_GRAY))
    
    ax.set_xlabel('Ping Sequence (1 per second)')
    ax.set_ylabel('RTT (ms)')
    ax.set_title('IEEE 802.11ah Link Stability — 3 min continuous ping via wlan0\n(Edge STA → Tube AP, Channel 14, 2 MHz)')
    ax.legend(loc='upper left')
    
    plt.tight_layout()
    path = os.path.join(OUT_DIR, "05_stability_timeseries.png")
    plt.savefig(path)
    plt.close()
    print(f"  ✓ {path}")


# ═══════════════════════════════════════════════════════════════════════
# CHART 6: Signal Asymmetry & Link Budget
# ═══════════════════════════════════════════════════════════════════════
def chart_signal_asymmetry():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Left: Signal levels
    labels_sig = ['Edge sees AP\n(Downlink RX)', 'AP sees Edge\n(Uplink RX)']
    signals = [-41, -78]  # From post-test wireless status
    noise = [-94, -88]
    snr = [s - n for s, n in zip(signals, noise)]
    
    x = np.arange(len(labels_sig))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, [-s for s in signals], width, label='Signal Strength', color=[C_GREEN, C_RED])
    bars2 = ax1.bar(x + width/2, [-n for n in noise], width, label='Noise Floor', color=[C_GRAY, C_GRAY], alpha=0.4)
    
    for bar, val in zip(bars1, signals):
        ax1.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
                f'{val} dBm', ha='center', va='bottom', fontweight='bold', fontsize=11)
    
    ax1.set_ylabel('Power Level (inverted, dBm → positive)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels_sig)
    ax1.set_title('Signal Levels')
    ax1.legend()
    ax1.set_ylim(0, 105)
    
    # Asymmetry annotation
    diff = signals[0] - signals[1]
    ax1.annotate(f'Δ = {abs(diff)} dB asymmetry',
                xy=(0.5, 0.92), xycoords='axes fraction', ha='center',
                fontsize=12, color=C_RED, fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='#FEE2E2', edgecolor=C_RED))
    
    # Right: SNR and TX success rate
    labels_snr = ['Edge\n(STA)', 'Tube-AHM\n(AP)']
    snrs = [snr[0], snr[1]]  # 53, 10
    tx_success = [73, 56]  # From morse_cli stats
    
    x2 = np.arange(len(labels_snr))
    
    bars_snr = ax2.bar(x2 - width/2, snrs, width, label='SNR (dB)', color=[C_BLUE, C_ORANGE])
    bars_tx = ax2.bar(x2 + width/2, tx_success, width, label='TX Success (%)', color=[C_GREEN, C_RED])
    
    for bar, val in zip(bars_snr, snrs):
        ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5,
                f'{val} dB', ha='center', va='bottom', fontsize=10, fontweight='bold')
    for bar, val in zip(bars_tx, tx_success):
        ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5,
                f'{val}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax2.set_ylabel('Value')
    ax2.set_xticks(x2)
    ax2.set_xticklabels(labels_snr)
    ax2.set_title('SNR & TX Round-Trip Success')
    ax2.legend()
    ax2.set_ylim(0, 85)
    
    fig.suptitle('IEEE 802.11ah Signal Asymmetry Analysis\n(Post-test measurements)', fontsize=14, y=1.02)
    
    plt.tight_layout()
    path = os.path.join(OUT_DIR, "06_signal_asymmetry.png")
    plt.savefig(path)
    plt.close()
    print(f"  ✓ {path}")


# ═══════════════════════════════════════════════════════════════════════
# CHART 7 (BONUS): Summary Dashboard
# ═══════════════════════════════════════════════════════════════════════
def chart_summary_dashboard():
    fig = plt.figure(figsize=(14, 8))
    fig.suptitle('IEEE 802.11ah (HaLow) Performance Summary — UNAL Thesis\nChannel 14 (909 MHz), 2 MHz BW, Morse Micro MM6108', 
                 fontsize=15, fontweight='bold', y=0.98)
    
    gs = fig.add_gridspec(2, 3, hspace=0.4, wspace=0.3)
    
    # 1. TCP
    ax1 = fig.add_subplot(gs[0, 0])
    bars = ax1.bar(['Upload', 'Download'], [data['tcp_upload_mbps'], data['tcp_download_mbps']], 
                   color=[C_BLUE, C_GREEN], width=0.6)
    for b, v in zip(bars, [data['tcp_upload_mbps'], data['tcp_download_mbps']]):
        ax1.text(b.get_x() + b.get_width()/2., b.get_height() + 0.05, f'{v:.2f}', 
                ha='center', fontweight='bold', fontsize=11)
    ax1.set_ylabel('Mbps')
    ax1.set_title('TCP Throughput')
    ax1.set_ylim(0, 5)
    
    # 2. UDP achieved vs target
    ax2 = fig.add_subplot(gs[0, 1])
    udp = data['udp_results']
    rates = ['200K', '500K', '750K', '1M', '1.2M', '1.5M', '2M']
    target_m = [0.2, 0.5, 0.75, 1.0, 1.2, 1.5, 2.0]
    achieved_m = [udp[f'udp_{r}']['mbps'] for r in rates]
    x_udp = range(len(rates))
    ax2.plot(x_udp, target_m, 's--', color=C_GRAY, label='Target', markersize=4)
    ax2.plot(x_udp, achieved_m, 'o-', color=C_BLUE, label='Achieved', markersize=5)
    ax2.fill_between(x_udp, achieved_m, target_m, alpha=0.15, color=C_RED)
    ax2.set_xticks(list(x_udp))
    ax2.set_xticklabels(rates, fontsize=8)
    ax2.set_ylabel('Mbps')
    ax2.set_title('UDP: Target vs Achieved')
    ax2.legend(fontsize=8)
    
    # 3. UDP loss
    ax3 = fig.add_subplot(gs[0, 2])
    losses = [udp[f'udp_{r}']['loss_pct'] for r in rates]
    clrs = [C_GREEN if l < 1 else (C_ORANGE if l < 3 else C_RED) for l in losses]
    ax3.bar(range(len(rates)), losses, color=clrs, width=0.7)
    ax3.set_xticks(range(len(rates)))
    ax3.set_xticklabels(rates, fontsize=8)
    ax3.set_ylabel('Loss (%)')
    ax3.set_title('UDP Packet Loss')
    
    # 4. Latency
    ax4 = fig.add_subplot(gs[1, 0])
    def parse_rtt(s):
        parts = s.split('=')[1].strip().split(' ')[0].split('/')
        return float(parts[0]), float(parts[1]), float(parts[2])
    
    ap_min, ap_avg, ap_max = parse_rtt(data['latency']['ping_AP_via_wlan0_rtt'])
    wan_min, wan_avg, wan_max = parse_rtt(data['latency']['ping_WAN_via_halow_rtt'])
    
    bars = ax4.bar(['AP (1 hop)', 'WAN (2 hops)'], [ap_avg, wan_avg], 
                   color=[C_BLUE, C_PURPLE], width=0.6)
    for b, v in zip(bars, [ap_avg, wan_avg]):
        ax4.text(b.get_x() + b.get_width()/2., b.get_height() + 1, f'{v:.1f} ms',
                ha='center', fontweight='bold', fontsize=10)
    ax4.set_ylabel('RTT (ms)')
    ax4.set_title('Latency (avg)')
    
    # 5. Signal
    ax5 = fig.add_subplot(gs[1, 1])
    sig_labels = ['Edge→AP\n(RX at STA)', 'AP→Edge\n(RX at AP)']
    sigs = [-41, -78]
    clrs_sig = [C_GREEN, C_RED]
    bars = ax5.barh(sig_labels, [abs(s) for s in sigs], color=clrs_sig, height=0.5)
    for b, s in zip(bars, sigs):
        ax5.text(b.get_width() + 1, b.get_y() + b.get_height()/2., f'{s} dBm',
                va='center', fontweight='bold', fontsize=10)
    ax5.set_xlabel('|Signal| (dBm)')
    ax5.set_title('Signal Asymmetry')
    ax5.set_xlim(0, 100)
    
    # 6. Key metrics text
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.axis('off')
    metrics = (
        "Key Findings\n"
        "─────────────────────\n"
        f"TCP DL/UL ratio: {data['tcp_download_mbps']/data['tcp_upload_mbps']:.1f}:1\n"
        f"Max UDP (< 1% loss): 1.17 Mbps\n"
        f"AP latency: {ap_avg:.1f} ms avg\n"
        f"WAN latency: {wan_avg:.1f} ms avg\n"
        f"Signal Δ: 37 dB\n"
        f"Stability: 0% loss / 3 min\n"
        f"AP TX success: 56%\n"
        f"STA TX success: 73%"
    )
    ax6.text(0.1, 0.95, metrics, transform=ax6.transAxes, fontsize=11,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='#F8FAFC', edgecolor=C_GRAY))
    
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    path = os.path.join(OUT_DIR, "00_summary_dashboard.png")
    plt.savefig(path)
    plt.close()
    print(f"  ✓ {path}")


# ─── Main ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating thesis charts...")
    chart_tcp_throughput()
    chart_udp_throughput()
    chart_udp_jitter()
    chart_latency()
    chart_stability()
    chart_signal_asymmetry()
    chart_summary_dashboard()
    print(f"\nAll charts saved to: {OUT_DIR}")
