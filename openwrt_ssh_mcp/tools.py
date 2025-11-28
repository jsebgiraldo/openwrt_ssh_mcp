"""OpenWRT-specific tools for MCP server."""

import json
import logging
from typing import Any

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
