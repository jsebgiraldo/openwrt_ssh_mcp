#!/usr/bin/env python3
"""
SYMMETRIC Multi-BW Thesis Charts
=================================
Generates publication-quality charts from SYMMETRIC test data
where ALL bandwidths (2, 4, 8 MHz) were tested with identical parameters.

All data comes from logs/thesis_symmetric/ with uniform JSON format.
"""
import json
import os
import re
import sys
import io
import numpy as np

# Windows encoding fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# Style
plt.rcParams.update({
    'figure.figsize': (10, 6),
    'font.size': 12,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'legend.fontsize': 10,
    'figure.dpi': 150,
    'axes.grid': True,
    'grid.alpha': 0.3,
})

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_symmetric")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_symmetric_charts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BW_COLORS = {"2 MHz": "#2196F3", "4 MHz": "#FF9800", "8 MHz": "#4CAF50"}
BW_MARKERS = {"2 MHz": "o", "4 MHz": "s", "8 MHz": "D"}
BWS = ["2 MHz", "4 MHz", "8 MHz"]

def load_data():
    """Load all symmetric test results."""
    data = {}
    for bw in [2, 4, 8]:
        # Find matching file
        for f in os.listdir(DATA_DIR):
            if f.startswith(f"results_{bw}mhz_") and f.endswith(".json"):
                path = os.path.join(DATA_DIR, f)
                with open(path, "r", encoding="utf-8") as fp:
                    data[f"{bw} MHz"] = json.load(fp)
                print(f"  Loaded: {f}", flush=True)
                break
    return data


def fig1_tcp_throughput_bars(data):
    """Fig 1: TCP Upload + Download bar chart."""
    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(BWS))
    width = 0.35

    uploads = []
    downloads = []
    for bw in BWS:
        r = data.get(bw, {})
        up = r.get("tcp_upload", {})
        down = r.get("tcp_download", {})
        uploads.append(up.get("sent_mbps", 0) if not up.get("error") else 0)
        downloads.append(down.get("sent_mbps", 0) if not down.get("error") else 0)

    bars1 = ax.bar(x - width/2, uploads, width, label="Upload (Edge→Tube)",
                   color="#2196F3", edgecolor="black", linewidth=0.5)
    bars2 = ax.bar(x + width/2, downloads, width, label="Download (Tube→Edge, -R)",
                   color="#FF9800", edgecolor="black", linewidth=0.5)

    # Value labels
    for bar in bars1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.05, f"{h:.2f}",
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    for bar in bars2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.05, f"{h:.2f}",
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_xlabel("Channel Bandwidth")
    ax.set_ylabel("Throughput (Mbps)")
    ax.set_title("IEEE 802.11ah TCP Throughput: Upload vs Download\n(30s tests, identical parameters)")
    ax.set_xticks(x)
    ax.set_xticklabels(BWS)
    ax.legend(loc='upper right')
    ax.set_ylim(0, max(max(uploads), max(downloads)) * 1.25)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig1_tcp_throughput_bars.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> {path}", flush=True)


def fig2_tcp_timeseries(data):
    """Fig 2: TCP Upload time series (symmetric x-axis)."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Upload
    ax = axes[0]
    for bw in BWS:
        r = data.get(bw, {})
        up = r.get("tcp_upload", {})
        tp = up.get("throughputs", [])
        if tp:
            t = list(range(1, len(tp) + 1))
            ax.plot(t, tp, marker=BW_MARKERS[bw], color=BW_COLORS[bw],
                    label=bw, markersize=4, linewidth=1.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Throughput (Mbps)")
    ax.set_title("TCP Upload (Edge→Tube)")
    ax.legend()

    # Download
    ax = axes[1]
    for bw in BWS:
        r = data.get(bw, {})
        down = r.get("tcp_download", {})
        tp = down.get("throughputs", [])
        if tp:
            t = list(range(1, len(tp) + 1))
            ax.plot(t, tp, marker=BW_MARKERS[bw], color=BW_COLORS[bw],
                    label=bw, markersize=4, linewidth=1.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Throughput (Mbps)")
    ax.set_title("TCP Download (Tube→Edge, -R)")
    ax.legend()

    fig.suptitle("IEEE 802.11ah TCP Time Series — Symmetric 30s Tests", fontsize=14, y=1.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig2_tcp_timeseries.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> {path}", flush=True)


def fig3_latency(data):
    """Fig 3: Ping latency boxplot + CDF."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Boxplot
    ax = axes[0]
    latency_data = []
    labels = []
    for bw in BWS:
        r = data.get(bw, {})
        lats = r.get("ping", {}).get("latencies", [])
        if lats:
            latency_data.append(lats)
            labels.append(bw)

    if latency_data:
        bp = ax.boxplot(latency_data, labels=labels, patch_artist=True)
        colors = [BW_COLORS[l] for l in labels]
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
    ax.set_ylabel("RTT (ms)")
    ax.set_title("Ping Latency Distribution")

    # CDF
    ax = axes[1]
    for bw in BWS:
        r = data.get(bw, {})
        lats = r.get("ping", {}).get("latencies", [])
        if lats:
            sorted_lats = np.sort(lats)
            cdf = np.arange(1, len(sorted_lats) + 1) / len(sorted_lats) * 100
            loss_pct = r.get("ping", {}).get("loss_pct", 0)
            ax.plot(sorted_lats, cdf, color=BW_COLORS[bw], linewidth=2,
                    label=f"{bw} (loss={loss_pct}%)")
    ax.set_xlabel("RTT (ms)")
    ax.set_ylabel("CDF (%)")
    ax.set_title("Cumulative Latency Distribution")
    ax.legend()

    fig.suptitle("IEEE 802.11ah Ping Latency Analysis — 50 packets each", fontsize=14, y=1.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig3_latency.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> {path}", flush=True)


def fig4_udp_analysis(data):
    """Fig 4: UDP throughput and loss vs target rate."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Throughput
    ax = axes[0]
    for bw in BWS:
        r = data.get(bw, {})
        udp = r.get("udp", [])
        rates = []
        actuals = []
        for u in udp:
            if "error" not in u:
                rate_str = u["target_rate"]
                rate_val = float(rate_str.replace("M", ""))
                rates.append(rate_val)
                actuals.append(u["actual_mbps"])
        if rates:
            ax.plot(rates, actuals, marker=BW_MARKERS[bw], color=BW_COLORS[bw],
                    label=bw, linewidth=2, markersize=8)

    # Ideal line
    max_rate = 8
    ax.plot([0, max_rate], [0, max_rate], 'k--', alpha=0.3, label="Ideal")
    ax.set_xlabel("Target Rate (Mbps)")
    ax.set_ylabel("Actual Throughput (Mbps)")
    ax.set_title("UDP Throughput vs Target Rate")
    ax.legend()

    # Loss
    ax = axes[1]
    for bw in BWS:
        r = data.get(bw, {})
        udp = r.get("udp", [])
        rates = []
        losses = []
        for u in udp:
            if "error" not in u:
                rate_str = u["target_rate"]
                rate_val = float(rate_str.replace("M", ""))
                rates.append(rate_val)
                losses.append(u["loss_pct"])
        if rates:
            ax.plot(rates, losses, marker=BW_MARKERS[bw], color=BW_COLORS[bw],
                    label=bw, linewidth=2, markersize=8)

    ax.set_xlabel("Target Rate (Mbps)")
    ax.set_ylabel("Packet Loss (%)")
    ax.set_title("UDP Packet Loss vs Target Rate")
    ax.legend()

    fig.suptitle("IEEE 802.11ah UDP Performance Analysis — 10s per rate", fontsize=14, y=1.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig4_udp_analysis.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> {path}", flush=True)


def fig5_stability(data):
    """Fig 5: Stability test (10 samples)."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # TX
    ax = axes[0]
    for bw in BWS:
        r = data.get(bw, {})
        stab = r.get("stability", [])
        samples = [s.get("tx_mbps", 0) for s in stab if "error" not in s]
        if samples:
            x = list(range(1, len(samples) + 1))
            ax.plot(x, samples, marker=BW_MARKERS[bw], color=BW_COLORS[bw],
                    label=f"{bw} (avg={np.mean(samples):.2f})", linewidth=2, markersize=6)
    ax.set_xlabel("Sample #")
    ax.set_ylabel("TX Throughput (Mbps)")
    ax.set_title("Upload Stability (5s TCP samples)")
    ax.legend()

    # RX
    ax = axes[1]
    for bw in BWS:
        r = data.get(bw, {})
        stab = r.get("stability", [])
        samples = [s.get("rx_mbps", 0) for s in stab if "error" not in s]
        if samples:
            x = list(range(1, len(samples) + 1))
            ax.plot(x, samples, marker=BW_MARKERS[bw], color=BW_COLORS[bw],
                    label=f"{bw} (avg={np.mean(samples):.2f})", linewidth=2, markersize=6)
    ax.set_xlabel("Sample #")
    ax.set_ylabel("RX Throughput (Mbps)")
    ax.set_title("Download Stability (5s TCP samples)")
    ax.legend()

    fig.suptitle("IEEE 802.11ah Link Stability — 10 × 5s TCP", fontsize=14, y=1.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig5_stability.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> {path}", flush=True)


def fig6_signal_asymmetry(data):
    """Fig 6: Signal strength and asymmetry."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    edge_sigs = []
    tube_sigs = []
    asymmetry = []
    for bw in BWS:
        r = data.get(bw, {})
        e = r.get("edge_signal_dbm")
        t = r.get("tube_signal_dbm")
        edge_sigs.append(abs(e) if e else 0)
        tube_sigs.append(abs(t) if t else 0)
        asym = abs(e - t) if (e is not None and t is not None) else 0
        asymmetry.append(asym)

    x = np.arange(len(BWS))
    width = 0.35

    # Signal levels
    ax = axes[0]
    bars1 = ax.bar(x - width/2, [-e for e in edge_sigs], width,
                   label="Edge sees Tube (dBm)", color="#2196F3",
                   edgecolor="black", linewidth=0.5)
    bars2 = ax.bar(x + width/2, [-t for t in tube_sigs], width,
                   label="Tube sees Edge (dBm)", color="#FF5722",
                   edgecolor="black", linewidth=0.5)

    for bar, val in zip(bars1, edge_sigs):
        ax.text(bar.get_x() + bar.get_width()/2, -val - 1, f"-{val}",
                ha='center', va='top', fontsize=10, fontweight='bold')
    for bar, val in zip(bars2, tube_sigs):
        ax.text(bar.get_x() + bar.get_width()/2, -val - 1, f"-{val}",
                ha='center', va='top', fontsize=10, fontweight='bold')

    ax.set_xlabel("Channel Bandwidth")
    ax.set_ylabel("Signal Strength (dBm)")
    ax.set_title("Received Signal Strength")
    ax.set_xticks(x)
    ax.set_xticklabels(BWS)
    ax.legend(loc='lower right')

    # Asymmetry
    ax = axes[1]
    bars = ax.bar(BWS, asymmetry, color=["#2196F3", "#FF9800", "#4CAF50"],
                  edgecolor="black", linewidth=0.5, width=0.5)
    for bar, val in zip(bars, asymmetry):
        ax.text(bar.get_x() + bar.get_width()/2, val + 0.5, f"{val} dB",
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    ax.set_xlabel("Channel Bandwidth")
    ax.set_ylabel("Asymmetry (dB)")
    ax.set_title("Signal Asymmetry (|Edge - Tube|)")
    ax.axhline(y=20, color='red', linestyle='--', alpha=0.5, label="20 dB typical concern")
    ax.legend()

    fig.suptitle("IEEE 802.11ah Signal Analysis — HaLow Link", fontsize=14, y=1.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig6_signal_asymmetry.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> {path}", flush=True)


def fig7_comprehensive_dashboard(data):
    """Fig 7: Comprehensive 4-panel dashboard."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Panel 1: TCP throughput bars
    ax = axes[0, 0]
    x = np.arange(len(BWS))
    width = 0.35
    uploads = [data.get(bw, {}).get("tcp_upload", {}).get("sent_mbps", 0) for bw in BWS]
    downloads = [data.get(bw, {}).get("tcp_download", {}).get("sent_mbps", 0) for bw in BWS]
    ax.bar(x - width/2, uploads, width, label="Upload", color="#2196F3", edgecolor="black", linewidth=0.5)
    ax.bar(x + width/2, downloads, width, label="Download (-R)", color="#FF9800", edgecolor="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(BWS)
    ax.set_ylabel("Mbps")
    ax.set_title("TCP Throughput (30s)")
    ax.legend(fontsize=9)

    # Panel 2: Latency boxplot
    ax = axes[0, 1]
    latency_data = []
    labels = []
    for bw in BWS:
        lats = data.get(bw, {}).get("ping", {}).get("latencies", [])
        if lats:
            latency_data.append(lats)
            labels.append(bw)
    if latency_data:
        bp = ax.boxplot(latency_data, labels=labels, patch_artist=True)
        colors = [BW_COLORS[l] for l in labels]
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
    ax.set_ylabel("RTT (ms)")
    ax.set_title("Ping Latency (50 packets)")

    # Panel 3: UDP throughput
    ax = axes[1, 0]
    for bw in BWS:
        udp = data.get(bw, {}).get("udp", [])
        rates = []
        actuals = []
        for u in udp:
            if "error" not in u:
                rate_val = float(u["target_rate"].replace("M", ""))
                rates.append(rate_val)
                actuals.append(u["actual_mbps"])
        if rates:
            ax.plot(rates, actuals, marker=BW_MARKERS[bw], color=BW_COLORS[bw],
                    label=bw, linewidth=2, markersize=6)
    ax.plot([0, 8], [0, 8], 'k--', alpha=0.3, label="Ideal")
    ax.set_xlabel("Target (Mbps)")
    ax.set_ylabel("Actual (Mbps)")
    ax.set_title("UDP Throughput")
    ax.legend(fontsize=9)

    # Panel 4: Stability TX
    ax = axes[1, 1]
    for bw in BWS:
        stab = data.get(bw, {}).get("stability", [])
        samples = [s.get("tx_mbps", 0) for s in stab if "error" not in s]
        if samples:
            x_s = list(range(1, len(samples) + 1))
            avg = np.mean(samples)
            ax.plot(x_s, samples, marker=BW_MARKERS[bw], color=BW_COLORS[bw],
                    label=f"{bw} (avg={avg:.2f})", linewidth=1.5, markersize=5)
    ax.set_xlabel("Sample")
    ax.set_ylabel("TX Mbps")
    ax.set_title(f"Stability ({len(stab)}×5s TCP)")
    ax.legend(fontsize=9)

    fig.suptitle("IEEE 802.11ah HaLow — Symmetric Multi-Bandwidth Comparison\n"
                 "All tests: TCP=30s | Ping=50 | UDP=10s | Stability=10×5s",
                 fontsize=15, y=1.02, fontweight='bold')
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig7_dashboard.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> {path}", flush=True)


def fig8_retransmits_jitter(data):
    """Fig 8: TCP retransmits + UDP jitter analysis."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Retransmits
    ax = axes[0]
    up_retrans = []
    down_retrans = []
    for bw in BWS:
        r = data.get(bw, {})
        up_r = r.get("tcp_upload", {}).get("retransmits", 0)
        down_r = r.get("tcp_download", {}).get("retransmits", 0)
        up_retrans.append(up_r if isinstance(up_r, (int, float)) else 0)
        down_retrans.append(down_r if isinstance(down_r, (int, float)) else 0)

    x = np.arange(len(BWS))
    width = 0.35
    ax.bar(x - width/2, up_retrans, width, label="Upload", color="#F44336", edgecolor="black", linewidth=0.5)
    ax.bar(x + width/2, down_retrans, width, label="Download (-R)", color="#9C27B0", edgecolor="black", linewidth=0.5)

    for i, (u, d) in enumerate(zip(up_retrans, down_retrans)):
        ax.text(i - width/2, u + 1, str(u), ha='center', va='bottom', fontsize=10, fontweight='bold')
        ax.text(i + width/2, d + 1, str(d), ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(BWS)
    ax.set_ylabel("Retransmits")
    ax.set_title("TCP Retransmits (30s)")
    ax.legend()

    # Jitter
    ax = axes[1]
    for bw in BWS:
        udp = data.get(bw, {}).get("udp", [])
        rates = []
        jitters = []
        for u in udp:
            if "error" not in u:
                rate_val = float(u["target_rate"].replace("M", ""))
                rates.append(rate_val)
                jitters.append(u["jitter_ms"])
        if rates:
            ax.plot(rates, jitters, marker=BW_MARKERS[bw], color=BW_COLORS[bw],
                    label=bw, linewidth=2, markersize=8)

    ax.set_xlabel("Target Rate (Mbps)")
    ax.set_ylabel("Jitter (ms)")
    ax.set_title("UDP Jitter vs Target Rate")
    ax.legend()

    fig.suptitle("IEEE 802.11ah Reliability Analysis", fontsize=14, y=1.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig8_retransmits_jitter.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> {path}", flush=True)


def main():
    print("=" * 60, flush=True)
    print("  SYMMETRIC THESIS CHARTS", flush=True)
    print(f"  Data: {DATA_DIR}", flush=True)
    print(f"  Output: {OUTPUT_DIR}", flush=True)
    print("=" * 60, flush=True)

    data = load_data()
    if len(data) < 3:
        print(f"  WARNING: Only {len(data)} BWs loaded (expected 3)", flush=True)

    print(f"\n  Generating 8 figures...\n", flush=True)

    fig1_tcp_throughput_bars(data)
    fig2_tcp_timeseries(data)
    fig3_latency(data)
    fig4_udp_analysis(data)
    fig5_stability(data)
    fig6_signal_asymmetry(data)
    fig7_comprehensive_dashboard(data)
    fig8_retransmits_jitter(data)

    print(f"\n  ALL CHARTS DONE: {OUTPUT_DIR}", flush=True)
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith('.png'):
            print(f"    - {f}", flush=True)


if __name__ == "__main__":
    main()
