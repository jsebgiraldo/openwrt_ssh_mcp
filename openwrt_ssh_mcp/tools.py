"""OpenWRT-specific tools for MCP server."""

import json
import logging
import re
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

    # ========== Firmware OTA / Sysupgrade Tools ==========

    @staticmethod
    async def firmware_get_version() -> dict[str, Any]:
        """
        Get current firmware version and board info.

        Returns:
            dict: Firmware version, board model, release info
        """
        try:
            await ssh_client.ensure_connected()

            info = {}

            commands = {
                "version": "cat /etc/openwrt_version",
                "release": "cat /etc/openwrt_release",
                "board": "ubus call system board",
            }

            for key, cmd in commands.items():
                result = await ssh_client.execute(cmd)
                if result["success"]:
                    if key == "board":
                        try:
                            info[key] = json.loads(result["stdout"])
                        except json.JSONDecodeError:
                            info[key] = result["stdout"]
                    else:
                        info[key] = result["stdout"].strip()
                else:
                    info[key] = None

            return {
                "success": True,
                "firmware_info": info,
            }

        except Exception as e:
            logger.error(f"Failed to get firmware version: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @staticmethod
    async def firmware_upload(local_path: str) -> dict[str, Any]:
        """
        Upload a firmware image to the router via SCP.

        Args:
            local_path: Local path to the firmware .img or .bin file

        Returns:
            dict: Upload result with checksum info
        """
        try:
            import os
            import hashlib

            if not os.path.isfile(local_path):
                return {
                    "success": False,
                    "error": f"Local file not found: {local_path}",
                }

            file_size = os.path.getsize(local_path)

            # Compute local SHA256
            sha256 = hashlib.sha256()
            with open(local_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            local_hash = sha256.hexdigest()

            await ssh_client.ensure_connected()

            # Upload via SCP
            logger.info(f"Uploading firmware ({file_size} bytes) to /tmp/firmware.img")
            async with ssh_client.connection.start_sftp_client() as sftp:
                await sftp.put(local_path, "/tmp/firmware.img")

            # Verify remote checksum
            result = await ssh_client.execute("sha256sum /tmp/firmware.img")
            if result["success"]:
                remote_hash = result["stdout"].split()[0]
                checksum_ok = remote_hash == local_hash
            else:
                remote_hash = None
                checksum_ok = False

            if not checksum_ok:
                return {
                    "success": False,
                    "error": "Checksum mismatch after upload",
                    "local_sha256": local_hash,
                    "remote_sha256": remote_hash,
                }

            return {
                "success": True,
                "message": "Firmware uploaded and verified",
                "file_size": file_size,
                "sha256": local_hash,
                "remote_path": "/tmp/firmware.img",
            }

        except Exception as e:
            logger.error(f"Failed to upload firmware: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @staticmethod
    async def firmware_verify() -> dict[str, Any]:
        """
        Verify a previously uploaded firmware image using sysupgrade -T.

        Returns:
            dict: Verification result
        """
        try:
            await ssh_client.ensure_connected()

            result = await ssh_client.execute("ls -la /tmp/firmware.img")
            if not result["success"]:
                return {
                    "success": False,
                    "error": "No firmware image found at /tmp/firmware.img. Upload one first.",
                }

            # sysupgrade -T tests the image without flashing
            result = await ssh_client.execute("sysupgrade -T /tmp/firmware.img")
            if result["success"]:
                return {
                    "success": True,
                    "message": "Firmware image is valid and compatible",
                    "output": result["stdout"],
                }
            else:
                return {
                    "success": False,
                    "error": f"Firmware verification failed: {result['stderr']}",
                    "output": result["stdout"],
                }

        except Exception as e:
            logger.error(f"Failed to verify firmware: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @staticmethod
    async def firmware_flash(keep_settings: bool = True) -> dict[str, Any]:
        """
        Flash the uploaded firmware image using sysupgrade.

        Args:
            keep_settings: If True, preserve UCI configuration across upgrade.
                           If False, perform a clean install (-n flag).

        Returns:
            dict: Flash initiation result
        """
        try:
            await ssh_client.ensure_connected()

            # Check firmware exists
            result = await ssh_client.execute("ls -la /tmp/firmware.img")
            if not result["success"]:
                return {
                    "success": False,
                    "error": "No firmware image at /tmp/firmware.img. Upload and verify first.",
                }

            # Verify first
            result = await ssh_client.execute("sysupgrade -T /tmp/firmware.img")
            if not result["success"]:
                return {
                    "success": False,
                    "error": f"Firmware verification failed. Will not flash. Error: {result['stderr']}",
                }

            # Flash
            flag = "-v" if keep_settings else "-n"
            cmd = f"sysupgrade {flag} /tmp/firmware.img"
            logger.info(f"Initiating sysupgrade: {cmd}")

            # sysupgrade will reboot the system, so the SSH connection will drop.
            # We fire-and-forget and inform the user.
            try:
                result = await ssh_client.execute(cmd, timeout=10)
            except Exception:
                pass  # Expected: connection drops during sysupgrade

            ssh_client.is_connected = False

            return {
                "success": True,
                "message": (
                    f"Sysupgrade initiated ({'keeping settings' if keep_settings else 'clean install'}). "
                    "The router is rebooting with the new firmware. "
                    "It should be available again in 2-5 minutes. "
                    "Use openwrt_test_connection to check when it's back online."
                ),
                "keep_settings": keep_settings,
            }

        except Exception as e:
            logger.error(f"Failed to flash firmware: {e}")
            return {
                "success": False,
                "error": str(e),
            }
