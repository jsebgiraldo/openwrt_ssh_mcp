#!/usr/bin/env python3
"""
Recopilación exhaustiva de información de dispositivos HaLow para tesis UNAL.
Genera archivos de texto con toda la info relevante para anexos.
"""
import asyncio
import asyncssh
import os
from datetime import datetime

EDGE = {"host": "192.168.1.196", "user": "root", "password": "root", "name": "Edge Gateway"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root", "name": "Tube-AHM"}
WAN  = {"host": "192.168.1.1", "user": "root", "key": r"C:\Users\jsgir\.ssh\id_rsa", "name": "WAN Router"}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "thesis_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)


async def ssh_exec(device, cmd, timeout=30):
    kwargs = {"host": device["host"], "port": 22, "username": device["user"], "known_hosts": None}
    if "key" in device:
        kwargs["client_keys"] = [device["key"]]
    else:
        kwargs["password"] = device["password"]
    async with asyncssh.connect(**kwargs) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()


async def gather_device_info(device, sections):
    """Gather all info sections from a device."""
    results = {}
    for title, cmd in sections:
        try:
            out = await ssh_exec(device, cmd)
            results[title] = out
        except Exception as e:
            results[title] = f"ERROR: {e}"
    return results


def write_report(filepath, device_name, results):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"{'='*70}\n")
        f.write(f"  INFORMACIÓN DEL DISPOSITIVO: {device_name}\n")
        f.write(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*70}\n\n")
        for title, content in results.items():
            f.write(f"--- {title} ---\n")
            f.write(f"{content}\n\n")


async def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # =========================================================
    # EDGE GATEWAY - Información completa
    # =========================================================
    print("Recopilando info del Edge Gateway...")
    edge_sections = [
        ("Sistema", "cat /etc/openwrt_release; echo '---'; uname -a"),
        ("Hostname", "uci get system.@system[0].hostname 2>/dev/null; hostname"),
        ("Uptime y carga", "uptime"),
        ("CPU", "cat /proc/cpuinfo"),
        ("Memoria", "free -h; echo '---'; cat /proc/meminfo | head -20"),
        ("Almacenamiento", "df -h"),
        ("Interfaces de red", "ip addr"),
        ("Tabla de rutas", "ip route"),
        ("ARP Table", "ip neigh"),
        ("Wireless - iwinfo completo", "iwinfo wlan0 info"),
        ("Wireless - iwinfo scan", "iwinfo wlan0 scan 2>/dev/null"),
        ("Wireless - iwinfo assoclist", "iwinfo wlan0 assoclist 2>/dev/null"),
        ("Wireless - iwinfo freqlist", "iwinfo wlan0 freqlist 2>/dev/null"),
        ("Wireless - iw dev wlan0 link", "iw dev wlan0 link 2>/dev/null"),
        ("Wireless - iw dev wlan0 station dump", "iw dev wlan0 station dump 2>/dev/null"),
        ("Wireless - iw phy info", "iw phy phy0 info 2>/dev/null | head -80"),
        ("wpa_cli_s1g status", "wpa_cli_s1g -i wlan0 status 2>/dev/null"),
        ("Config wireless (UCI)", "cat /etc/config/wireless"),
        ("Config network (UCI)", "cat /etc/config/network"),
        ("Config firewall (UCI)", "cat /etc/config/firewall 2>/dev/null | head -50"),
        ("Config DHCP", "cat /etc/config/dhcp 2>/dev/null | head -30"),
        ("Morse Micro driver info", "dmesg | grep -i morse | head -30"),
        ("Morse Micro BCF", "ls -la /lib/firmware/morse/"),
        ("Morse Micro módulo", "lsmod | grep morse"),
        ("Morse Micro chip info", "cat /sys/kernel/debug/ieee80211/phy0/morse/hw_version 2>/dev/null; cat /sys/kernel/debug/ieee80211/phy0/morse/fw_version 2>/dev/null"),
        ("Bridge info", "brctl show 2>/dev/null"),
        ("Paquetes instalados (HaLow)", "opkg list-installed | grep -iE 'morse|halow|wpa|hostapd'"),
        ("Procesos wireless", "ps | grep -iE 'wpa_supplicant|hostapd|morse'"),
        ("Kernel log (wireless)", "logread | grep -iE 'wpa_supplicant_s1g|hostapd_s1g|morse|wlan0|assoc|auth|channel' | tail -40"),
        ("Estadísticas wlan0", "cat /proc/net/dev | head -1; cat /proc/net/dev | grep wlan0"),
        ("Estadísticas detalladas", "ip -s link show wlan0"),
        ("Resolución DNS", "nslookup google.com 2>/dev/null || echo 'nslookup no disponible'"),
        ("Temperatura CPU", "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null || echo 'N/A'"),
    ]
    edge_results = await gather_device_info(EDGE, edge_sections)
    edge_file = os.path.join(OUTPUT_DIR, f"edge_gateway_{timestamp}.txt")
    write_report(edge_file, "Edge Gateway (192.168.1.196)", edge_results)
    print(f"  -> {edge_file}")

    # =========================================================
    # TUBE-AHM - Información completa
    # =========================================================
    print("Recopilando info del Tube-AHM...")
    tube_sections = [
        ("Sistema", "cat /etc/openwrt_release; echo '---'; uname -a"),
        ("Hostname", "uci get system.@system[0].hostname 2>/dev/null; hostname"),
        ("Uptime y carga", "uptime"),
        ("CPU", "cat /proc/cpuinfo"),
        ("Memoria", "free -h; echo '---'; cat /proc/meminfo | head -20"),
        ("Almacenamiento", "df -h"),
        ("Interfaces de red", "ip addr"),
        ("Tabla de rutas", "ip route"),
        ("ARP Table", "ip neigh"),
        ("Wireless - iwinfo completo", "iwinfo wlan0 info"),
        ("Wireless - iwinfo assoclist", "iwinfo wlan0 assoclist 2>/dev/null"),
        ("Wireless - iwinfo freqlist", "iwinfo wlan0 freqlist 2>/dev/null"),
        ("Wireless - iw dev wlan0 station dump", "iw dev wlan0 station dump 2>/dev/null"),
        ("hostapd_s1g info", "cat /var/run/hostapd_s1g/wlan0 2>/dev/null || echo 'N/A'"),
        ("Config wireless (UCI)", "cat /etc/config/wireless"),
        ("Config network (UCI)", "cat /etc/config/network"),
        ("Morse Micro driver info", "dmesg | grep -i morse | head -30"),
        ("Morse Micro BCF", "ls -la /lib/firmware/morse/"),
        ("Morse Micro módulo", "lsmod | grep morse"),
        ("Bridge info", "brctl show 2>/dev/null"),
        ("Paquetes instalados (HaLow)", "opkg list-installed | grep -iE 'morse|halow|wpa|hostapd'"),
        ("Procesos wireless", "ps | grep -iE 'wpa_supplicant|hostapd|morse'"),
        ("Kernel log (wireless)", "logread | grep -iE 'hostapd_s1g|morse|wlan0|assoc|AP-STA|channel|Operating' | tail -40"),
        ("Estadísticas wlan0", "cat /proc/net/dev | head -1; cat /proc/net/dev | grep wlan0"),
        ("Estadísticas detalladas", "ip -s link show wlan0"),
        ("Temperatura CPU", "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null || echo 'N/A'"),
    ]
    tube_results = await gather_device_info(TUBE, tube_sections)
    tube_file = os.path.join(OUTPUT_DIR, f"tube_ahm_{timestamp}.txt")
    write_report(tube_file, "Tube-AHM (192.168.1.103)", tube_results)
    print(f"  -> {tube_file}")

    # =========================================================
    # WAN ROUTER - Info básica
    # =========================================================
    print("Recopilando info del WAN Router...")
    wan_sections = [
        ("Sistema", "cat /etc/openwrt_release; echo '---'; uname -a"),
        ("Hostname", "hostname"),
        ("Uptime", "uptime"),
        ("Interfaces", "ip addr show br-lan; ip addr show wan"),
        ("Rutas", "ip route"),
        ("ARP", "ip neigh"),
        ("DHCP leases", "cat /tmp/dhcp.leases 2>/dev/null"),
    ]
    wan_results = await gather_device_info(WAN, wan_sections)
    wan_file = os.path.join(OUTPUT_DIR, f"wan_router_{timestamp}.txt")
    write_report(wan_file, "WAN Router (192.168.1.1)", wan_results)
    print(f"  -> {wan_file}")

    # Print key thesis info to console
    print("\n" + "=" * 70)
    print("  RESUMEN PARA TESIS")
    print("=" * 70)
    print(f"\n--- Edge Gateway ---")
    print(edge_results.get("Sistema", ""))
    print(f"\nWireless:")
    print(edge_results.get("Wireless - iwinfo completo", ""))
    print(f"\nMorse Micro:")
    print(edge_results.get("Morse Micro BCF", ""))
    print(edge_results.get("Paquetes instalados (HaLow)", ""))

    print(f"\n--- Tube-AHM ---")
    print(tube_results.get("Sistema", ""))
    print(f"\nWireless:")
    print(tube_results.get("Wireless - iwinfo completo", ""))
    print(f"\nEstaciones conectadas:")
    print(tube_results.get("Wireless - iwinfo assoclist", ""))

    print(f"\nArchivos guardados en: {OUTPUT_DIR}")


asyncio.run(main())
