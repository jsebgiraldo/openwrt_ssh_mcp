#!/usr/bin/env python3
"""iperf3 tests at 2 MHz - download + UDP."""
import asyncio
import asyncssh

async def ssh_run(host, cmd, timeout=60):
    async with asyncssh.connect(
        host, port=22, username="root", password="root",
        known_hosts=None, login_timeout=10
    ) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()

async def main():
    EDGE = "192.168.1.111"
    TUBE = "192.168.1.103"
    
    print("2 MHz iperf3 - Download + UDP Tests")
    print("=" * 50)
    
    # Check link
    out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
    print(f"Edge signal: {out}")
    
    # Ensure route + ARP
    await ssh_run(EDGE, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
    await ssh_run(TUBE, "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent")
    
    # Kill existing 
    for h in [EDGE, TUBE]:
        try:
            await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
    await asyncio.sleep(2)
    
    # === TCP Download (Tube -> Edge) ===
    print("\n[1] TCP DOWNLOAD (Tube->Edge) - server on Edge, client on Tube:")
    # Start server on Edge (listen on HaLow IP)
    await ssh_run(EDGE, "nohup iperf3 -s -B 192.168.1.196 -1 > /tmp/iperf3_srv.log 2>&1 &")
    await asyncio.sleep(3)
    
    try:
        out = await ssh_run(TUBE,
            "iperf3 -c 192.168.1.196 -t 15 -i 3 2>&1",
            timeout=45)
        print(out)
    except Exception as e:
        print(f"Download error: {e}")
        # Check server log
        try:
            log = await ssh_run(EDGE, "cat /tmp/iperf3_srv.log 2>/dev/null")
            print(f"Server log: {log}")
        except:
            pass
    
    # Cleanup
    for h in [EDGE, TUBE]:
        try:
            await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
    await asyncio.sleep(2)
    
    # === TCP Reverse (Edge runs client with --reverse) ===
    print("\n[2] TCP DOWNLOAD via --reverse (server on Tube, Edge uses -R):")
    await ssh_run(TUBE, "nohup iperf3 -s -1 > /tmp/iperf3_srv.log 2>&1 &")
    await asyncio.sleep(3)
    
    try:
        out = await ssh_run(EDGE,
            "iperf3 -c 192.168.1.103 -B 192.168.1.196 -R -t 15 -i 3 2>&1",
            timeout=45)
        print(out)
    except Exception as e:
        print(f"Reverse error: {e}")
    
    # Cleanup
    for h in [EDGE, TUBE]:
        try:
            await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
    await asyncio.sleep(2)
    
    # === UDP Tests ===
    for rate in ["500K", "1M"]:
        print(f"\n[3] UDP UPLOAD {rate} (Edge->Tube):")
        await ssh_run(TUBE, "nohup iperf3 -s -1 > /tmp/iperf3_srv.log 2>&1 &")
        await asyncio.sleep(3)
        try:
            out = await ssh_run(EDGE,
                f"iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b {rate} -t 10 -i 5 2>&1",
                timeout=30)
            print(out)
        except Exception as e:
            print(f"UDP error: {e}")
        
        for h in [EDGE, TUBE]:
            try:
                await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
            except:
                pass
        await asyncio.sleep(2)
    
    # Signal after tests
    print("\n[4] Signal after all tests:")
    out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
    print(f"  Edge: {out}")
    
    print("\nDone!")

asyncio.run(main())
