"""OpenWRT-specific tools for MCP server."""

import json
import logging
import re
from typing import Any, Optional

from .ssh_client import ssh_client
from .security import SecurityValidator

logger = logging.getLogger(__name__)


class OpenWRTTools:
    """Collection of OpenWRT management tools."""

    @staticmethod
    async def execute_command(command: str) -> dict[str, Any]:
        """
        Execute a validated command on the OpenWRT router.
        
        Args:
            command: Shell command to execute
            
        Returns:
            dict: Execution result
        """
        # Validate command
        is_valid, error_msg = SecurityValidator.validate_command(command)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg,
                "output": "",
            }

        # Execute
        await ssh_client.ensure_connected()
        result = await ssh_client.execute(command)

        return {
            "success": result["success"],
            "output": result["stdout"],
            "error": result["stderr"],
            "exit_code": result["exit_code"],
            "execution_time": result["execution_time"],
        }

    @staticmethod
    async def get_system_info() -> dict[str, Any]:
        """
        Get OpenWRT system information (uptime, memory, load).
        
        Returns:
            dict: System information
        """
        try:
            await ssh_client.ensure_connected()

            # Execute multiple commands to gather system info
            commands = {
                "board": "ubus call system board",
                "info": "ubus call system info",
                "uptime": "cat /proc/uptime",
                "loadavg": "cat /proc/loadavg",
            }

            results = {}
            for key, cmd in commands.items():
                result = await ssh_client.execute(cmd)
                if result["success"]:
                    if key in ["board", "info"]:
                        # Parse JSON output from ubus
                        try:
                            results[key] = json.loads(result["stdout"])
                        except json.JSONDecodeError:
                            results[key] = result["stdout"]
                    else:
                        results[key] = result["stdout"]
                else:
                    results[key] = {"error": result["stderr"]}

            return {
                "success": True,
                "system_info": results,
            }

        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @staticmethod
    async def restart_interface(interface: str) -> dict[str, Any]:
        """
        Restart a network interface.
        
        Args:
            interface: Interface name (e.g., 'wan', 'lan')
            
        Returns:
            dict: Operation result
        """
        command = f"ubus call network.interface.{interface} restart"
        
        # Validate interface name (alphanumeric and underscore only)
        if not interface.replace("_", "").isalnum():
            return {
                "success": False,
                "error": "Invalid interface name",
            }

        result = await OpenWRTTools.execute_command(command)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Interface '{interface}' restarted successfully",
                "output": result["output"],
            }
        else:
            return {
                "success": False,
                "error": f"Failed to restart interface '{interface}': {result['error']}",
            }

    @staticmethod
    async def get_wifi_status() -> dict[str, Any]:
        """
        Get WiFi status and connected clients.
        
        Returns:
            dict: WiFi status information
        """
        command = "ubus call network.wireless status"
        result = await OpenWRTTools.execute_command(command)

        if result["success"]:
            try:
                wifi_data = json.loads(result["output"])
                return {
                    "success": True,
                    "wifi_status": wifi_data,
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "wifi_status": result["output"],
                }
        else:
            return {
                "success": False,
                "error": result["error"],
            }

    @staticmethod
    async def list_dhcp_leases() -> dict[str, Any]:
        """
        List DHCP leases (connected devices).
        
        Returns:
            dict: DHCP leases information
        """
        # Try both possible locations for DHCP leases file
        commands = [
            "cat /tmp/dhcp.leases",
            "cat /var/dhcp.leases",
        ]

        for cmd in commands:
            result = await OpenWRTTools.execute_command(cmd)
            if result["success"] and result["output"]:
                # Parse DHCP leases
                leases = []
                for line in result["output"].strip().split("\n"):
                    if line:
                        parts = line.split()
                        if len(parts) >= 4:
                            leases.append({
                                "timestamp": parts[0],
                                "mac": parts[1],
                                "ip": parts[2],
                                "hostname": parts[3] if len(parts) > 3 else "",
                                "client_id": parts[4] if len(parts) > 4 else "",
                            })

                return {
                    "success": True,
                    "leases": leases,
                    "count": len(leases),
                }

        return {
            "success": False,
            "error": "Could not read DHCP leases file",
        }

    @staticmethod
    async def get_firewall_rules() -> dict[str, Any]:
        """
        Get firewall rules.
        
        Returns:
            dict: Firewall rules
        """
        command = "iptables -L -n -v"
        result = await OpenWRTTools.execute_command(command)

        if result["success"]:
            return {
                "success": True,
                "rules": result["output"],
            }
        else:
            return {
                "success": False,
                "error": result["error"],
            }

    @staticmethod
    async def read_config(config_name: str) -> dict[str, Any]:
        """
        Read a UCI configuration file.
        
        Args:
            config_name: Configuration name (e.g., 'network', 'wireless', 'dhcp')
            
        Returns:
            dict: Configuration content
        """
        # Whitelist of allowed config names
        allowed_configs = ["network", "wireless", "dhcp", "firewall", "system"]
        
        if config_name not in allowed_configs:
            return {
                "success": False,
                "error": f"Configuration '{config_name}' not allowed. Allowed: {', '.join(allowed_configs)}",
            }

        command = f"uci show {config_name}"
        result = await OpenWRTTools.execute_command(command)

        if result["success"]:
            return {
                "success": True,
                "config_name": config_name,
                "config": result["output"],
            }
        else:
            return {
                "success": False,
                "error": result["error"],
            }

    @staticmethod
    async def test_connection() -> dict[str, Any]:
        """
        Test SSH connection to the router.
        
        Returns:
            dict: Connection test result
        """
        return await ssh_client.test_connection()

    # ========== OpenThread Border Router (OTBR) Tools ==========

    @staticmethod
    async def thread_get_state() -> dict[str, Any]:
        """
        Get current OpenThread state.
        
        Returns:
            dict: Thread state (disabled, detached, child, router, leader)
        """
        command = "/usr/sbin/ot-ctl state"
        result = await OpenWRTTools.execute_command(command)

        if result["success"]:
            return {
                "success": True,
                "state": result["output"].strip(),
            }
        else:
            return {
                "success": False,
                "error": result["error"],
            }

    @staticmethod
    async def thread_create_network(
        network_name: str = "OpenWRT-Thread",
        channel: int = 15,
        panid: str = None,
    ) -> dict[str, Any]:
        """
        Create a new Thread network.
        
        Args:
            network_name: Network name (default: OpenWRT-Thread)
            channel: Thread channel 11-26 (default: 15)
            panid: PAN ID in hex format (auto-generated if not provided)
            
        Returns:
            dict: Operation result with network credentials
        """
        try:
            await ssh_client.ensure_connected()

            # Validate parameters
            if not network_name.replace("-", "").replace("_", "").isalnum():
                return {
                    "success": False,
                    "error": "Invalid network name. Use only alphanumeric, dash, and underscore.",
                }

            if not (11 <= channel <= 26):
                return {
                    "success": False,
                    "error": "Channel must be between 11 and 26",
                }

            # Generate random PAN ID if not provided
            if not panid:
                import secrets
                panid = f"0x{secrets.randbelow(0xFFFF):04x}"

            # Step 1: Initialize new dataset
            result = await ssh_client.execute("/usr/sbin/ot-ctl dataset init new")
            if not result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to initialize dataset: {result['stderr']}",
                }

            # Step 2: Set network parameters
            commands = [
                f"/usr/sbin/ot-ctl channel {channel}",
                f"/usr/sbin/ot-ctl panid {panid}",
                f"/usr/sbin/ot-ctl networkname {network_name}",
            ]

            for cmd in commands:
                result = await ssh_client.execute(cmd)
                if not result["success"]:
                    return {
                        "success": False,
                        "error": f"Failed to execute '{cmd}': {result['stderr']}",
                    }

            # Step 3: Commit dataset
            result = await ssh_client.execute("/usr/sbin/ot-ctl dataset commit active")
            if not result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to commit dataset: {result['stderr']}",
                }

            # Step 4: Bring up interface
            result = await ssh_client.execute("/usr/sbin/ot-ctl ifconfig up")
            if not result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to bring up interface: {result['stderr']}",
                }

            # Step 5: Start Thread
            result = await ssh_client.execute("/usr/sbin/ot-ctl thread start")
            if not result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to start Thread: {result['stderr']}",
                }

            # Step 6: Get network credentials
            import asyncio
            await asyncio.sleep(2)  # Wait for network to stabilize

            credentials = {}
            
            # Get network key
            result = await ssh_client.execute("/usr/sbin/ot-ctl networkkey")
            if result["success"]:
                credentials["network_key"] = result["stdout"].strip()

            # Get extended PAN ID
            result = await ssh_client.execute("/usr/sbin/ot-ctl extpanid")
            if result["success"]:
                credentials["ext_panid"] = result["stdout"].strip()

            # Get dataset in hex format
            result = await ssh_client.execute("/usr/sbin/ot-ctl dataset active -x")
            if result["success"]:
                credentials["dataset_hex"] = result["stdout"].strip()

            # Get current state
            result = await ssh_client.execute("/usr/sbin/ot-ctl state")
            if result["success"]:
                credentials["state"] = result["stdout"].strip()

            return {
                "success": True,
                "message": f"Thread network '{network_name}' created successfully",
                "network_name": network_name,
                "channel": channel,
                "panid": panid,
                "credentials": credentials,
            }

        except Exception as e:
            logger.error(f"Failed to create Thread network: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @staticmethod
    async def thread_get_dataset() -> dict[str, Any]:
        """
        Get active Thread dataset (network credentials).
        
        Returns:
            dict: Active dataset information
        """
        command = "/usr/sbin/ot-ctl dataset active"
        result = await OpenWRTTools.execute_command(command)

        if result["success"]:
            # Also get hex format for easy sharing
            hex_result = await OpenWRTTools.execute_command("/usr/sbin/ot-ctl dataset active -x")
            
            return {
                "success": True,
                "dataset": result["output"],
                "dataset_hex": hex_result["output"].strip() if hex_result["success"] else None,
            }
        else:
            return {
                "success": False,
                "error": result["error"],
            }

    @staticmethod
    async def thread_get_info() -> dict[str, Any]:
        """
        Get comprehensive Thread network information.
        
        Returns:
            dict: Network state, neighbors, routes, etc.
        """
        try:
            await ssh_client.ensure_connected()

            info = {}

            # Get various Thread info
            commands = {
                "state": "/usr/sbin/ot-ctl state",
                "channel": "/usr/sbin/ot-ctl channel",
                "panid": "/usr/sbin/ot-ctl panid",
                "networkname": "/usr/sbin/ot-ctl networkname",
                "extpanid": "/usr/sbin/ot-ctl extpanid",
                "ipaddr": "/usr/sbin/ot-ctl ipaddr",
                "rloc16": "/usr/sbin/ot-ctl rloc16",
                "leaderdata": "/usr/sbin/ot-ctl leaderdata",
                "neighbor_table": "/usr/sbin/ot-ctl neighbor table",
                "child_table": "/usr/sbin/ot-ctl child table",
            }

            for key, cmd in commands.items():
                result = await ssh_client.execute(cmd)
                if result["success"]:
                    info[key] = result["stdout"].strip()
                else:
                    info[key] = None

            return {
                "success": True,
                "thread_info": info,
            }

        except Exception as e:
            logger.error(f"Failed to get Thread info: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @staticmethod
    async def thread_enable_commissioner(passphrase: str = "THREAD123") -> dict[str, Any]:
        """
        Enable Thread Commissioner to allow devices to join.
        
        Args:
            passphrase: Joiner passphrase (default: THREAD123)
            
        Returns:
            dict: Operation result
        """
        try:
            await ssh_client.ensure_connected()

            # Start commissioner
            result = await ssh_client.execute("/usr/sbin/ot-ctl commissioner start")
            if not result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to start commissioner: {result['stderr']}",
                }

            # Add joiner with wildcard (any device can join with this passphrase)
            result = await ssh_client.execute(f"/usr/sbin/ot-ctl commissioner joiner add * {passphrase}")
            if not result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to add joiner: {result['stderr']}",
                }

            return {
                "success": True,
                "message": "Thread Commissioner enabled",
                "passphrase": passphrase,
                "note": "Devices can now join using this passphrase",
            }

        except Exception as e:
            logger.error(f"Failed to enable commissioner: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @staticmethod
    async def otbr_persist_network(
        dataset_path: str = "/etc/otbr/active-dataset.tlvs",
        enable_service: bool = True,
        add_to_sysupgrade: bool = True,
    ) -> dict[str, Any]:
        """
        Persist the active Thread dataset and otbr-agent service across reboots.

        Steps:
        1. Saves dataset TLV to /etc/otbr/active-dataset.tlvs (mode 600).
        2. Saves human-readable dataset to /etc/otbr/active-dataset.txt.
        3. Creates /etc/otbr/reapply-dataset.sh that re-applies the dataset on boot.
        4. Hooks the script via uci otbr-agent (preferred) or /etc/rc.local.
        5. Optionally enables and restarts otbr-agent service.
        6. Optionally adds /etc/otbr/ and /etc/rc.local to /etc/sysupgrade.conf.

        Args:
            dataset_path: Destination path for the TLV file.
            enable_service: Enable and restart otbr-agent service after saving.
            add_to_sysupgrade: Protect /etc/otbr/ in /etc/sysupgrade.conf.

        Returns:
            dict: dataset_saved, mode, service_enabled, sysupgrade_protected, state_after
        """
        try:
            await ssh_client.ensure_connected()

            # 1. Create directory
            r = await ssh_client.execute("mkdir -p /etc/otbr")
            if not r["success"]:
                return {"success": False, "error": f"mkdir /etc/otbr failed: {r['stderr']}"}

            # 2. Retrieve active dataset TLV
            r = await ssh_client.execute("ot-ctl dataset active -x")
            if not r["success"] or not r["stdout"].strip():
                return {
                    "success": False,
                    "error": "No active Thread dataset. Is the Thread network running?",
                }
            # First token handles trailing 'Done' line that ot-ctl sometimes emits
            tlv = r["stdout"].strip().splitlines()[0].strip()

            # 3. Write TLV file atomically (hex chars only — safe to single-quote)
            r = await ssh_client.execute(
                f"printf '%s\\n' '{tlv}' > /etc/otbr/active-dataset.tlvs"
                f" && chmod 600 /etc/otbr/active-dataset.tlvs"
            )
            if not r["success"]:
                return {"success": False, "error": f"Failed to write TLV file: {r['stderr']}"}

            # 4. Write human-readable dataset
            r2 = await ssh_client.execute("ot-ctl dataset active")
            if r2["success"] and r2["stdout"].strip():
                # Escape single quotes for safe embedding in printf '...'
                human = r2["stdout"].strip().replace("'", "'\\''")
                await ssh_client.execute(
                    f"printf '%s\\n' '{human}' > /etc/otbr/active-dataset.txt"
                )

            # 5. Write reapply script via heredoc (single-quoted delimiter → no expansion)
            write_script = (
                "cat > /etc/otbr/reapply-dataset.sh << 'OTBR_REAPPLY_EOF'\n"
                "#!/bin/sh\n"
                "TLV=$(cat /etc/otbr/active-dataset.tlvs 2>/dev/null)\n"
                "[ -z \"$TLV\" ] && exit 1\n"
                "STATE=$(ot-ctl state 2>/dev/null | head -1)\n"
                "if [ \"$STATE\" = \"disabled\" ] || [ \"$STATE\" = \"detached\" ]; then\n"
                "  ot-ctl dataset set active \"$TLV\"\n"
                "  ot-ctl ifconfig up\n"
                "  ot-ctl thread start\n"
                "fi\n"
                "OTBR_REAPPLY_EOF\n"
                "chmod 755 /etc/otbr/reapply-dataset.sh"
            )
            await ssh_client.execute(write_script)

            # 6. Persistence mode: uci preferred, rc.local fallback
            mode = "rc.local"
            uci_check = await ssh_client.execute(
                "ls /etc/config/otbr-agent 2>/dev/null && echo found"
            )
            if uci_check["success"] and "found" in uci_check["stdout"]:
                uci_r = await ssh_client.execute(
                    f"uci set otbr-agent.@main[0].dataset='{tlv}' && uci commit otbr-agent"
                )
                if uci_r["success"]:
                    mode = "uci"

            if mode == "rc.local":
                marker = "/etc/otbr/reapply-dataset.sh"
                chk = await ssh_client.execute(
                    f"grep -qF '{marker}' /etc/rc.local 2>/dev/null && echo found"
                )
                if not (chk["success"] and "found" in chk["stdout"]):
                    # Insert the background call before the final 'exit 0'
                    await ssh_client.execute(
                        "sed -i 's|^exit 0|"
                        "( sleep 8 \\&\\& /etc/otbr/reapply-dataset.sh >> /tmp/otbr-reapply.log 2>\\&1 ) \\&\\n"
                        "exit 0|' /etc/rc.local"
                    )

            # 7. Optionally enable and restart otbr-agent
            service_enabled = False
            if enable_service:
                svc_r = await ssh_client.execute(
                    "/etc/init.d/otbr-agent enable && /etc/init.d/otbr-agent restart"
                )
                service_enabled = svc_r["success"]

            # 8. Optionally protect in sysupgrade
            sysupgrade_protected = False
            if add_to_sysupgrade:
                for entry in ["/etc/otbr/", "/etc/rc.local"]:
                    chk = await ssh_client.execute(
                        f"grep -qF '{entry}' /etc/sysupgrade.conf 2>/dev/null && echo found"
                    )
                    if not (chk["success"] and "found" in chk["stdout"]):
                        await ssh_client.execute(
                            f"printf '%s\\n' '{entry}' >> /etc/sysupgrade.conf"
                        )
                sysupgrade_protected = True

            # 9. Final state check
            state_r = await ssh_client.execute("ot-ctl state")
            state_after = (
                state_r["stdout"].strip().splitlines()[0].strip()
                if state_r["success"] and state_r["stdout"].strip()
                else "unknown"
            )

            return {
                "success": True,
                "dataset_saved": True,
                "dataset_path": dataset_path,
                "service_enabled": service_enabled,
                "sysupgrade_protected": sysupgrade_protected,
                "mode": mode,
                "state_after": state_after,
                "tlv_length": len(tlv),
            }

        except Exception as e:
            logger.error(f"Failed to persist OTBR network: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def thingsboard_probe(
        host: Optional[str] = None,
        mqtt_port: int = 1883,
        mqtts_port: int = 8883,
        http_port: int = 8080,
        timeout_s: int = 3,
    ) -> dict[str, Any]:
        """
        Discover ThingsBoard gateway config on the edge and probe TCP/HTTP reachability.

        Discovery (when host is None):
        - Searches process list for tb-gateway / thingsboard processes.
        - Searches /etc, /opt, /root for tb_gateway.yaml / thingsboard*.conf.
        - Checks running Docker containers.
        - Checks uci config for references.

        Reachability probes:
        - MQTT:  nc -zv on mqtt_port
        - MQTTS: nc -zv on mqtts_port
        - HTTP:  curl HTTP status code on http_port /api/auth/login

        Args:
            host: ThingsBoard server host. Auto-discovered when None.
            mqtt_port: MQTT port (default: 1883)
            mqtts_port: MQTTS port (default: 8883)
            http_port: HTTP port (default: 8080)
            timeout_s: TCP/HTTP timeout in seconds (default: 3)

        Returns:
            dict: discovered, host, reachability, transport_guess, discovery_log
        """
        try:
            await ssh_client.ensure_connected()

            discovered_host = host
            discovery_log: list[str] = []

            if not discovered_host:
                # 1. Process list
                r = await ssh_client.execute(
                    "ps w | grep -E 'tb-gateway|thingsboard' | grep -v grep"
                )
                if r["success"] and r["stdout"].strip():
                    discovery_log.append(f"process: {r['stdout'].strip()[:200]}")

                # 2. Config files
                r = await ssh_client.execute(
                    "find /etc /opt /root -maxdepth 4 -name 'tb_gateway.yaml'"
                    " -o -name 'thingsboard*.conf' 2>/dev/null"
                )
                if r["success"] and r["stdout"].strip():
                    for cfg_file in r["stdout"].strip().splitlines()[:3]:
                        discovery_log.append(f"config_file: {cfg_file}")
                        cr = await ssh_client.execute(
                            f"grep -E 'host:|url:|thingsboard' '{cfg_file}' 2>/dev/null | head -5"
                        )
                        if cr["success"] and cr["stdout"].strip():
                            discovery_log.append(f"content: {cr['stdout'].strip()[:200]}")
                            for line in cr["stdout"].splitlines():
                                if "host:" in line.lower():
                                    parts = line.split(":", 1)
                                    if len(parts) == 2:
                                        candidate = parts[1].strip().strip('"').strip("'")
                                        if candidate and not candidate.startswith("#"):
                                            discovered_host = candidate
                                            break

                # 3. Docker containers
                if not discovered_host:
                    r = await ssh_client.execute(
                        "docker ps --format '{{.Names}}\\t{{.Image}}' 2>/dev/null"
                        " | grep -i thingsboard"
                    )
                    if r["success"] and r["stdout"].strip():
                        discovery_log.append(f"docker: {r['stdout'].strip()[:200]}")
                        discovered_host = "localhost"

                # 4. UCI config
                if not discovered_host:
                    r = await ssh_client.execute(
                        "uci show 2>/dev/null | grep -i thingsboard | head -5"
                    )
                    if r["success"] and r["stdout"].strip():
                        discovery_log.append(f"uci: {r['stdout'].strip()[:200]}")

            if not discovered_host:
                return {
                    "success": True,
                    "discovered": False,
                    "host": None,
                    "discovery_log": discovery_log,
                    "message": (
                        "ThingsBoard host not found. "
                        "Pass host parameter explicitly or check gateway config."
                    ),
                }

            # Probe reachability (TCP via nc, HTTP via curl)
            reachability: dict[str, Any] = {}

            for label, port in [("mqtt", mqtt_port), ("mqtts", mqtts_port)]:
                r = await ssh_client.execute(
                    f"nc -zv -w{timeout_s} {discovered_host} {port} 2>&1"
                )
                output = (r.get("stdout", "") + r.get("stderr", "")).lower()
                reachability[label] = {
                    "port": port,
                    "reachable": r["success"] or "succeeded" in output or "open" in output,
                }

            r = await ssh_client.execute(
                f"curl -m{timeout_s} -o /dev/null -s -w '%{{http_code}}'"
                f" http://{discovered_host}:{http_port}/api/auth/login"
            )
            http_code = r["stdout"].strip() if r["success"] else "error"
            reachability["http"] = {
                "port": http_port,
                "reachable": http_code not in ("", "error", "000"),
                "http_code": http_code,
            }

            # Guess best transport
            if reachability["mqtts"]["reachable"]:
                transport_guess = "mqtts"
            elif reachability["mqtt"]["reachable"]:
                transport_guess = "mqtt"
            elif reachability["http"]["reachable"]:
                transport_guess = "http"
            else:
                transport_guess = "unreachable"

            return {
                "success": True,
                "discovered": True,
                "host": discovered_host,
                "reachability": reachability,
                "transport_guess": transport_guess,
                "discovery_log": discovery_log,
            }

        except Exception as e:
            logger.error(f"ThingsBoard probe failed: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def observability_health(
        prometheus_url: str = "http://127.0.0.1:9090",
        grafana_url: str = "http://127.0.0.1:3000",
        blackbox_url: str = "http://127.0.0.1:9115",
    ) -> dict[str, Any]:
        """
        Check health of the observability stack (Prometheus, Grafana, blackbox-exporter).

        Probes:
        - Prometheus: GET /-/ready
        - Grafana:    GET /api/health
        - Blackbox:   GET /-/healthy
        - Docker:     docker ps filtered for prom/grafana/blackbox
        - Sockets:    ss -ltn filtered for ports 9090, 3000, 9115

        Args:
            prometheus_url: Prometheus base URL (default: http://127.0.0.1:9090)
            grafana_url:    Grafana base URL     (default: http://127.0.0.1:3000)
            blackbox_url:   Blackbox base URL    (default: http://127.0.0.1:9115)

        Returns:
            dict: all_up, components (per-service http status), containers, listening_sockets
        """
        try:
            await ssh_client.ensure_connected()

            async def probe(url: str) -> dict[str, Any]:
                r = await ssh_client.execute(
                    f"curl -m5 -o /dev/null -s -w '%{{http_code}}' {url}"
                )
                if r["success"] and r["stdout"].strip():
                    code = r["stdout"].strip()
                    return {"up": code in ("200", "204"), "http_code": code}
                return {"up": False, "http_code": "error"}

            components = {
                "prometheus": await probe(f"{prometheus_url}/-/ready"),
                "grafana": await probe(f"{grafana_url}/api/health"),
                "blackbox": await probe(f"{blackbox_url}/-/healthy"),
            }

            # Docker containers
            dr = await ssh_client.execute(
                "docker ps --format '{{.Names}}\\t{{.Status}}' 2>/dev/null"
                " | grep -E 'prom|grafana|blackbox'"
            )
            containers: dict[str, str] = {}
            if dr["success"] and dr["stdout"].strip():
                for line in dr["stdout"].strip().splitlines():
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        containers[parts[0]] = parts[1]

            # Listening sockets
            ss_r = await ssh_client.execute(
                "ss -ltn 2>/dev/null | grep -E ':(9090|3000|9115)[[:space:]]'"
            )
            sockets = ss_r["stdout"].strip() if ss_r["success"] else ""

            return {
                "success": True,
                "all_up": all(c["up"] for c in components.values()),
                "components": components,
                "containers": containers,
                "listening_sockets": sockets,
            }

        except Exception as e:
            logger.error(f"Observability health check failed: {e}")
            return {"success": False, "error": str(e)}

    # ========== Package Management (opkg) Tools ==========

    @staticmethod
    async def opkg_update() -> dict[str, Any]:
        """
        Update package lists from repositories.
        
        Returns:
            dict: Operation result
        """
        command = "opkg update"
        result = await OpenWRTTools.execute_command(command)

        if result["success"]:
            return {
                "success": True,
                "message": "Package lists updated successfully",
                "output": result["output"],
            }
        else:
            return {
                "success": False,
                "error": f"Failed to update package lists: {result['error']}",
            }

    @staticmethod
    async def opkg_install(package_name: str) -> dict[str, Any]:
        """
        Install a package using opkg.
        
        Args:
            package_name: Name of the package to install
            
        Returns:
            dict: Operation result
        """
        # Validate package name (alphanumeric, dash, underscore, dot)
        if not re.match(r'^[a-zA-Z0-9._-]+$', package_name):
            return {
                "success": False,
                "error": "Invalid package name. Use only alphanumeric characters, dash, underscore, and dot.",
            }

        command = f"opkg install {package_name}"
        result = await OpenWRTTools.execute_command(command)

        if result["success"]:
            return {
                "success": True,
                "message": f"Package '{package_name}' installed successfully",
                "output": result["output"],
            }
        else:
            return {
                "success": False,
                "error": f"Failed to install package '{package_name}': {result['error']}",
                "output": result["output"],
            }

    @staticmethod
    async def opkg_remove(package_name: str) -> dict[str, Any]:
        """
        Remove a package using opkg.
        
        Args:
            package_name: Name of the package to remove
            
        Returns:
            dict: Operation result
        """
        # Validate package name
        if not re.match(r'^[a-zA-Z0-9._-]+$', package_name):
            return {
                "success": False,
                "error": "Invalid package name. Use only alphanumeric characters, dash, underscore, and dot.",
            }

        command = f"opkg remove {package_name}"
        result = await OpenWRTTools.execute_command(command)

        if result["success"]:
            return {
                "success": True,
                "message": f"Package '{package_name}' removed successfully",
                "output": result["output"],
            }
        else:
            return {
                "success": False,
                "error": f"Failed to remove package '{package_name}': {result['error']}",
                "output": result["output"],
            }

    @staticmethod
    async def opkg_list_installed() -> dict[str, Any]:
        """
        List all installed packages.
        
        Returns:
            dict: List of installed packages
        """
        command = "opkg list-installed"
        result = await OpenWRTTools.execute_command(command)

        if result["success"]:
            # Parse package list
            packages = []
            for line in result["output"].strip().split("\n"):
                if line:
                    parts = line.split(" - ")
                    if len(parts) >= 2:
                        packages.append({
                            "name": parts[0],
                            "version": parts[1],
                        })

            return {
                "success": True,
                "packages": packages,
                "count": len(packages),
            }
        else:
            return {
                "success": False,
                "error": result["error"],
            }

    @staticmethod
    async def opkg_info(package_name: str) -> dict[str, Any]:
        """
        Get information about a package.
        
        Args:
            package_name: Name of the package
            
        Returns:
            dict: Package information
        """
        # Validate package name
        if not re.match(r'^[a-zA-Z0-9._-]+$', package_name):
            return {
                "success": False,
                "error": "Invalid package name. Use only alphanumeric characters, dash, underscore, and dot.",
            }

        command = f"opkg info {package_name}"
        result = await OpenWRTTools.execute_command(command)

        if result["success"]:
            # Parse package info
            info = {}
            for line in result["output"].strip().split("\n"):
                if ": " in line:
                    key, value = line.split(": ", 1)
                    info[key.lower().replace(" ", "_")] = value

            return {
                "success": True,
                "package_info": info,
            }
        else:
            return {
                "success": False,
                "error": result["error"],
                "output": result["output"],
            }

    @staticmethod
    async def opkg_list_available() -> dict[str, Any]:
        """
        List all available packages from repositories.
        
        Returns:
            dict: List of available packages
        """
        command = "opkg list"
        result = await OpenWRTTools.execute_command(command)

        if result["success"]:
            # Parse package list (can be very large)
            packages = []
            lines = result["output"].strip().split("\n")
            
            for line in lines[:500]:  # Limit to first 500 packages to avoid huge responses
                if line:
                    parts = line.split(" - ")
                    if len(parts) >= 2:
                        packages.append({
                            "name": parts[0],
                            "version": parts[1],
                            "description": parts[2] if len(parts) > 2 else "",
                        })

            total_lines = len(result["output"].strip().split("\n"))
            truncated = total_lines > 500

            return {
                "success": True,
                "packages": packages,
                "count": len(packages),
                "truncated": truncated,
                "total_available": total_lines,
                "note": "List limited to 500 packages. Use opkg_info to search for specific packages." if truncated else "",
            }
        else:
            return {
                "success": False,
                "error": result["error"],
            }
