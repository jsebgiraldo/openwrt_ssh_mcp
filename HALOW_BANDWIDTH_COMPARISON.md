# IEEE 802.11ah (HaLow) — Multi-Bandwidth Throughput Comparison
## Thesis: UNAL Network Performance Analysis

**Date:** June 2025  
**Equipment:** Morse Micro Tube-AHM (AP, 24 dBm) → Morse Micro MM6108A1 Edge Gateway (STA, 21 dBm)  
**Frequency Band:** US 902–928 MHz  
**Security:** WPA3-SAE (CCMP)  
**Test Tool:** iperf3 (TCP: 15s, UDP: 10s)  
**Distance:** Indoor, same room (~3m line of sight)

---

## 1. Channel Configuration Summary

| Parameter | 2 MHz | 4 MHz | 8 MHz |
|-----------|-------|-------|-------|
| S1G Channel | 14 | 8 | 12 |
| Center Freq (MHz) | 909 | 906 | 908 |
| Op Class (global) | 69 | 70 | 71 |
| Primary BW | 1 MHz | 2 MHz | 2 MHz |
| Primary Chan Index | — | 2 | 3 |

## 2. RF Conditions

| Metric | 2 MHz | 4 MHz | 8 MHz |
|--------|-------|-------|-------|
| Edge Signal (dBm) | −38 | −38 | −32 |
| Edge Noise (dBm) | −89 | −88 | −80 |
| Edge SNR (dB) | ~51 | ~50 | ~48 |
| Tube Signal from STA (dBm) | — | −76 | −78 |
| Tube Noise (dBm) | — | −84 | −90→−74 |
| Tube SNR (dB) | — | 8 | 12→−1 |
| RX MCS (from STA) | MCS 7 2MHz | MCS 1 4MHz | MCS 0–1 8MHz |
| TX MCS (to STA) | MCS 7 2MHz | MCS 7 4MHz | MCS 7 8MHz |
| RX PHY Rate (Mbps) | 7.8 | 2.7 | 1.5–6.5 |
| TX PHY Rate (Mbps) | 7.8 | 15.4 | 32.5 |

**Key observation:** The AP-side (Tube) noise floor rises dramatically at 8 MHz (−90→−74 dBm), causing severe SNR degradation and limiting the uplink MCS. The downlink benefits from wider bandwidth (higher MCS 7 rates), but the uplink is bottlenecked.

---

## 3. TCP Results

### 3.1 TCP Upload (STA → AP)

| Metric | 2 MHz | 4 MHz | 8 MHz |
|--------|-------|-------|-------|
| Sender (Mbps) | **1.99** | 1.82 | 1.43 |
| Receiver (Mbps) | **1.20** | 1.12 | 0.82 |
| Retransmissions | **0** | 13 | 62 |

**Trend:** TCP upload throughput **decreases** with wider bandwidth — opposite to theoretical expectation. This is because the AP experiences progressively worse SNR at wider bandwidths, forcing lower MCS selections for frames received from the STA. The 8 MHz uplink shows 3 of 5 intervals with zero throughput.

### 3.2 TCP Download (AP → STA)

| Metric | 2 MHz | 4 MHz | 8 MHz |
|--------|-------|-------|-------|
| Sender (Mbps) | 4.27 | 5.74 | **6.06** |
| Receiver (Mbps) | 3.90 | 5.48 | **5.63** |
| Retransmissions | 0 | 0 | 0 |

**Trend:** TCP download **increases** with bandwidth as expected, because the AP transmits at MCS 7 and wider bandwidth means higher PHY rates. The gain diminishes from 4→8 MHz (+2.7%) compared to 2→4 MHz (+40.5%), suggesting the TCP ACK bottleneck on the poor uplink limits further gains.

---

## 4. UDP Results

### 4.1 UDP Upload Comparison Table

| Target Rate | 2 MHz Send | 2 MHz Recv | 2 MHz Loss | 4 MHz Send | 4 MHz Recv | 4 MHz Loss | 8 MHz Send | 8 MHz Recv | 8 MHz Loss |
|-------------|-----------|-----------|-----------|-----------|-----------|-----------|-----------|-----------|-----------|
| 500 Kbps | 500 Kbps | 498 Kbps | 0% | 166 Kbps⚠ | 30 Kbps⚠ | 77%⚠ | 500 Kbps | 487 Kbps | 2.1% |
| 1 Mbps | 1.00 Mbps | 995 Kbps | 0% | 1.00 Mbps | 989 Kbps | 0.35% | 1.00 Mbps | 716 Kbps | 9.3% |
| 2 Mbps | 1.23 Mbps* | 1.20 Mbps | 0% | 1.60 Mbps | 1.52 Mbps | 0.43% | 1.58 Mbps | 1.48 Mbps | 2.2% |
| 4 Mbps | — | — | — | 1.43 Mbps | 1.38 Mbps | 0.65% | 1.67 Mbps | 1.53 Mbps | 2.1% |
| 8 Mbps | — | — | — | — | — | — | 1.68 Mbps | 1.58 Mbps | 2.5% |

\* Saturated: 2 MHz link could only push ~1.23 Mbps when requesting 2 Mbps.  
⚠ 4 MHz UDP 500K was anomalous (transient link disruption); subsequent tests recovered.

### 4.2 Jitter Comparison (ms)

| Target Rate | 2 MHz | 4 MHz | 8 MHz |
|-------------|-------|-------|-------|
| 500 Kbps | **1.7** | 114⚠ | 11.6 |
| 1 Mbps | **1.9** | 6.4 | 81.6 |
| 2 Mbps | **12.8** | 13.9 | 11.3 |
| 4 Mbps | — | 12.2 | 17.6 |
| 8 Mbps | — | — | 8.2 |

### 4.3 Max Achieved UDP Uplink Throughput

| BW | Max Sender (Mbps) | Max Receiver (Mbps) | Loss at Max |
|----|-------------------|---------------------|-------------|
| 2 MHz | 1.23 | 1.20 | 0% |
| 4 MHz | 1.60 | 1.52 | 0.43% |
| 8 MHz | 1.68 | 1.58 | 2.5% |

The maximum achievable UDP uplink throughput increases modestly (+29% from 2→4 MHz, +4% from 4→8 MHz) but at the cost of increasing packet loss.

---

## 5. Key Findings

### 5.1 Asymmetric Link Performance
The most striking observation is the severe **uplink/downlink asymmetry** at wider bandwidths:
- At 8 MHz: Download = 5.63 Mbps vs Upload = 0.82 Mbps TCP (**6.9× ratio**)
- At 4 MHz: Download = 5.48 Mbps vs Upload = 1.12 Mbps TCP (**4.9× ratio**)
- At 2 MHz: Download = 3.90 Mbps vs Upload = 1.20 Mbps TCP (**3.3× ratio**)

**Root cause:** The AP's noise floor rises with wider channel bandwidth, degrading the SNR for received frames from the STA. The AP can still transmit at high MCS because the STA has a clean receive path.

### 5.2 Bandwidth Efficiency
- **2 MHz is the most efficient**: Zero packet loss, zero retransmissions, lowest jitter
- **4 MHz offers the best download gain**: +40% TCP download over 2 MHz with acceptable reliability
- **8 MHz provides diminishing returns**: Only +2.7% TCP download gain over 4 MHz, but with severe uplink degradation (62 retransmissions, 2–9% UDP loss)

### 5.3 Optimal Configuration Recommendation
For **reliability-critical IoT applications**: Use 2 MHz (0% loss, stable)  
For **maximum download throughput**: Use 4 MHz (best cost/benefit ratio)  
For **maximum theoretical capacity**: 8 MHz only viable with improved AP noise isolation

### 5.4 Noise Floor Anomaly at AP (Tube-AHM)
The Tube-AHM AP exhibits a noise floor that increases from −84 dBm at 4 MHz to −74 dBm at 8 MHz (10 dB increase). This may indicate:
- Self-interference from the AP's transmitter front-end
- Environmental noise in the 902–928 MHz ISM band
- Hardware sensitivity limitation of the Tube-AHM at 8 MHz bandwidth

---

## 6. Data for Graphing (CSV format)

See companion file: `halow_throughput_data.csv`

---

## 7. Test Environment Notes

- **Firmware**: Tube AP v23.05.3 (ramips/mt76x8), Edge Gateway v23.05.5 Morse-2.9-dev (bcm27xx/bcm2711)
- **BCF Files**: Tube = bcf_mf04151.bin, Edge = bcf_mf15457.bin
- **Firmware patches applied**: morse_overrides.sh STA S1G block fix, morse.sh json_get_vars fix
- **Routing**: Static route on Edge (192.168.1.103 via wlan0), static ARP on Tube (192.168.1.196 → 0C:BF:74:1C:DE:87)
- **Power save**: Disabled on STA
- **iperf3 server**: Runs on Tube AP (192.168.1.103:5201)
- **iperf3 client**: Runs on Edge STA, bound to 192.168.1.196 (wlan0)
