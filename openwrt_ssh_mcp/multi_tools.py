"""Multi-device OpenWRT tools for the network management agent."""

import json
import logging
import re
from typing import Any, Optional

from .multi_ssh_client import MultiSSHClientManager
from .security import SecurityValidator

logger = logging.getLogger(__name__)


class NetworkAgentTools:
    """Tools for managing multiple OpenWRT devices in a network."""

    def __init__(self, ssh_manager: MultiSSHClientManager):
        self.ssh = ssh_manager

    # ==================== Network-Wide Tools ====================

    async def list_devices(self) -> dict[str, Any]:
        """List all devices in the network inventory."""
        return {
            "success": True,
            "devices": self.ssh.list_devices(),
            "count": len(self.ssh.clients),
        }

    async def test_all_connections(self) -> dict[str, Any]:
        """Test SSH connectivity to all devices."""
        results = await self.ssh.test_all_connections()
        connected = sum(1 for r in results if r.get("connected"))
        return {
            "success": True,
            "results": results,
            "summary": f"{connected}/{len(results)} devices connected",
        }

    async def get_network_overview(self) -> dict[str, Any]:
        """Get system info from all devices for a network-wide overview."""
        overview = {}
        for device_id, client in self.ssh.clients.items():
            try:
                await client.ensure_connected()
                board = await client.execute("ubus call system board")
                info = await client.execute("ubus call system info")

                device_info = {
                    "device_id": device_id,
                    "host": client.device.host,
                    "role": client.device.role,
                    "description": client.device.description,
                    "connected": True,
                }

                if board["success"]:
                    try:
                        device_info["board"] = json.loads(board["stdout"])
                    except json.JSONDecodeError:
                        device_info["board"] = board["stdout"]

                if info["success"]:
                    try:
                        device_info["system"] = json.loads(info["stdout"])
                    except json.JSONDecodeError:
                        device_info["system"] = info["stdout"]

                overview[device_id] = device_info

            except Exception as e:
                overview[device_id] = {
                    "device_id": device_id,
                    "host": client.device.host,
                    "role": client.device.role,
                    "connected": False,
                    "error": str(e),
                }

        return {"success": True, "network_overview": overview}

    async def ping_between_devices(
        self, source_device: str, target_ip: str, count: int = 3
    ) -> dict[str, Any]:
        """Ping a target from a specific device to test inter-device connectivity."""
        result = await self.ssh.execute_on_device(
            source_device, f"ping -c {count} {target_ip}"
        )
        if result["success"]:
            return {
                "success": True,
                "source_device": source_device,
                "target_ip": target_ip,
                "output": result["stdout"],
            }
        return {
            "success": False,
            "source_device": source_device,
            "target_ip": target_ip,
            "error": result.get("stderr", result.get("error", "Unknown error")),
        }

    async def network_connectivity_matrix(self) -> dict[str, Any]:
        """Test connectivity between all device pairs."""
        devices = list(self.ssh.clients.values())
        matrix = {}
        for source in devices:
            matrix[source.device.device_id] = {}
            for target in devices:
                if source.device.device_id == target.device.device_id:
                    matrix[source.device.device_id][target.device.device_id] = "self"
                    continue
                try:
                    await source.ensure_connected()
                    result = await source.execute(
                        f"ping -c 1 {target.device.host}"
                    )
                    matrix[source.device.device_id][target.device.device_id] = (
                        "reachable" if result["success"] else "unreachable"
                    )
                except Exception:
                    matrix[source.device.device_id][target.device.device_id] = "error"

        return {"success": True, "connectivity_matrix": matrix}

    # ==================== Per-Device Tools ====================

    async def execute_command(self, device_id: str, command: str) -> dict[str, Any]:
        """Execute a validated command on a specific device."""
        result = await self.ssh.execute_on_device(device_id, command)
        return {
            "success": result.get("success", False),
            "device_id": device_id,
            "output": result.get("stdout", ""),
            "error": result.get("stderr", result.get("error", "")),
            "exit_code": result.get("exit_code"),
            "execution_time": result.get("execution_time"),
        }

    async def get_system_info(self, device_id: str) -> dict[str, Any]:
        """Get system info from a specific device."""
        client = self.ssh.get_client(device_id)
        if not client:
            return {"success": False, "error": f"Device '{device_id}' not found"}

        try:
            await client.ensure_connected()
            commands = {
                "board": "ubus call system board",
                "info": "ubus call system info",
                "uptime": "cat /proc/uptime",
                "loadavg": "cat /proc/loadavg",
            }
            results = {}
            for key, cmd in commands.items():
                r = await client.execute(cmd)
                if r["success"]:
                    if key in ["board", "info"]:
                        try:
                            results[key] = json.loads(r["stdout"])
                        except json.JSONDecodeError:
                            results[key] = r["stdout"]
                    else:
                        results[key] = r["stdout"]
                else:
                    results[key] = {"error": r["stderr"]}

            return {
                "success": True,
                "device_id": device_id,
                "system_info": results,
            }
        except Exception as e:
            return {"success": False, "device_id": device_id, "error": str(e)}

    async def get_network_config(self, device_id: str) -> dict[str, Any]:
        """Get network configuration (UCI) from a specific device."""
        result = await self.ssh.execute_on_device(device_id, "uci show network")
        if result.get("success"):
            return {
                "success": True,
                "device_id": device_id,
                "config": result["stdout"],
            }
        return {
            "success": False,
            "device_id": device_id,
            "error": result.get("stderr", result.get("error", "")),
        }

    async def get_wifi_status(self, device_id: str) -> dict[str, Any]:
        """Get WiFi status from a specific device."""
        result = await self.ssh.execute_on_device(
            device_id, "ubus call network.wireless status"
        )
        if result.get("success"):
            try:
                wifi_data = json.loads(result["stdout"])
                return {
                    "success": True,
                    "device_id": device_id,
                    "wifi_status": wifi_data,
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "device_id": device_id,
                    "wifi_status": result["stdout"],
                }
        return {
            "success": False,
            "device_id": device_id,
            "error": result.get("stderr", result.get("error", "")),
        }

    async def get_dhcp_leases(self, device_id: str) -> dict[str, Any]:
        """Get DHCP leases from a specific device."""
        for lease_file in ["/tmp/dhcp.leases", "/var/dhcp.leases"]:
            result = await self.ssh.execute_on_device(
                device_id, f"cat {lease_file}"
            )
            if result.get("success") and result.get("stdout"):
                leases = []
                for line in result["stdout"].strip().split("\n"):
                    if line:
                        parts = line.split()
                        if len(parts) >= 4:
                            leases.append({
                                "timestamp": parts[0],
                                "mac": parts[1],
                                "ip": parts[2],
                                "hostname": parts[3] if len(parts) > 3 else "",
                            })
                return {
                    "success": True,
                    "device_id": device_id,
                    "leases": leases,
                    "count": len(leases),
                }

        return {"success": False, "device_id": device_id, "error": "No DHCP leases found"}

    async def get_firewall_rules(self, device_id: str) -> dict[str, Any]:
        """Get firewall rules from a specific device."""
        result = await self.ssh.execute_on_device(device_id, "iptables -L -n -v")
        if result.get("success"):
            return {
                "success": True,
                "device_id": device_id,
                "rules": result["stdout"],
            }
        return {
            "success": False,
            "device_id": device_id,
            "error": result.get("stderr", result.get("error", "")),
        }

    async def read_config(self, device_id: str, config_name: str) -> dict[str, Any]:
        """Read a UCI config from a specific device."""
        allowed = ["network", "wireless", "dhcp", "firewall", "system"]
        if config_name not in allowed:
            return {
                "success": False,
                "error": f"Config '{config_name}' not allowed. Allowed: {', '.join(allowed)}",
            }
        result = await self.ssh.execute_on_device(
            device_id, f"uci show {config_name}"
        )
        if result.get("success"):
            return {
                "success": True,
                "device_id": device_id,
                "config_name": config_name,
                "config": result["stdout"],
            }
        return {
            "success": False,
            "device_id": device_id,
            "error": result.get("stderr", result.get("error", "")),
        }

    async def restart_interface(self, device_id: str, interface: str) -> dict[str, Any]:
        """Restart a network interface on a specific device."""
        if not interface.replace("_", "").isalnum():
            return {"success": False, "error": "Invalid interface name"}

        result = await self.ssh.execute_on_device(
            device_id, f"ubus call network.interface.{interface} restart"
        )
        if result.get("success"):
            return {
                "success": True,
                "device_id": device_id,
                "message": f"Interface '{interface}' restarted on {device_id}",
            }
        return {
            "success": False,
            "device_id": device_id,
            "error": result.get("stderr", result.get("error", "")),
        }

    async def get_routes(self, device_id: str) -> dict[str, Any]:
        """Get routing table from a specific device."""
        result = await self.ssh.execute_on_device(device_id, "ip route show")
        if result.get("success"):
            return {
                "success": True,
                "device_id": device_id,
                "routes": result["stdout"],
            }
        return {
            "success": False,
            "device_id": device_id,
            "error": result.get("stderr", result.get("error", "")),
        }

    async def get_interfaces(self, device_id: str) -> dict[str, Any]:
        """Get IP addresses/interfaces from a specific device."""
        result = await self.ssh.execute_on_device(device_id, "ip addr show")
        if result.get("success"):
            return {
                "success": True,
                "device_id": device_id,
                "interfaces": result["stdout"],
            }
        return {
            "success": False,
            "device_id": device_id,
            "error": result.get("stderr", result.get("error", "")),
        }

    # ==================== OpenThread Tools ====================

    async def thread_get_state(self, device_id: str) -> dict[str, Any]:
        """Get Thread state from a device."""
        result = await self.ssh.execute_on_device(
            device_id, "/usr/sbin/ot-ctl state"
        )
        if result.get("success"):
            return {
                "success": True,
                "device_id": device_id,
                "state": result["stdout"].strip(),
            }
        return {
            "success": False,
            "device_id": device_id,
            "error": result.get("stderr", result.get("error", "")),
        }

    async def thread_get_info(self, device_id: str) -> dict[str, Any]:
        """Get comprehensive Thread info from a device."""
        client = self.ssh.get_client(device_id)
        if not client:
            return {"success": False, "error": f"Device '{device_id}' not found"}

        try:
            await client.ensure_connected()
            commands = {
                "state": "/usr/sbin/ot-ctl state",
                "channel": "/usr/sbin/ot-ctl channel",
                "panid": "/usr/sbin/ot-ctl panid",
                "networkname": "/usr/sbin/ot-ctl networkname",
                "ipaddr": "/usr/sbin/ot-ctl ipaddr",
                "rloc16": "/usr/sbin/ot-ctl rloc16",
                "neighbor_table": "/usr/sbin/ot-ctl neighbor table",
                "child_table": "/usr/sbin/ot-ctl child table",
            }
            info = {}
            for key, cmd in commands.items():
                r = await client.execute(cmd)
                info[key] = r["stdout"].strip() if r["success"] else None

            return {"success": True, "device_id": device_id, "thread_info": info}
        except Exception as e:
            return {"success": False, "device_id": device_id, "error": str(e)}

    # ==================== Package Management ====================

    async def opkg_update(self, device_id: str) -> dict[str, Any]:
        """Update package lists on a device."""
        result = await self.ssh.execute_on_device(device_id, "opkg update")
        return {
            "success": result.get("success", False),
            "device_id": device_id,
            "output": result.get("stdout", ""),
            "error": result.get("stderr", result.get("error", "")),
        }

    async def opkg_install(self, device_id: str, package_name: str) -> dict[str, Any]:
        """Install a package on a device."""
        if not re.match(r"^[a-zA-Z0-9._-]+$", package_name):
            return {"success": False, "error": "Invalid package name"}
        result = await self.ssh.execute_on_device(
            device_id, f"opkg install {package_name}"
        )
        return {
            "success": result.get("success", False),
            "device_id": device_id,
            "output": result.get("stdout", ""),
            "error": result.get("stderr", result.get("error", "")),
        }

    async def opkg_list_installed(self, device_id: str) -> dict[str, Any]:
        """List installed packages on a device."""
        result = await self.ssh.execute_on_device(device_id, "opkg list-installed")
        if result.get("success"):
            packages = []
            for line in result["stdout"].strip().split("\n"):
                if line:
                    parts = line.split(" - ")
                    if len(parts) >= 2:
                        packages.append({"name": parts[0], "version": parts[1]})
            return {
                "success": True,
                "device_id": device_id,
                "packages": packages,
                "count": len(packages),
            }
        return {
            "success": False,
            "device_id": device_id,
            "error": result.get("stderr", result.get("error", "")),
        }
