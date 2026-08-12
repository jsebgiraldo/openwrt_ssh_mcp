"""Multi-device SSH client manager for OpenWRT network management."""

import asyncio
import asyncssh
import logging
from typing import Optional
from datetime import datetime

from .devices import DeviceConfig, NetworkTopology
from .security import SecurityValidator, AuditLogger

logger = logging.getLogger(__name__)


class DeviceSSHClient:
    """SSH client for a single device with connection management."""

    def __init__(self, device: DeviceConfig):
        self.device = device
        self.connection: Optional[asyncssh.SSHClientConnection] = None
        self.is_connected = False
        self.audit = AuditLogger()

    async def connect(self) -> bool:
        """Establish SSH connection to the device."""
        try:
            logger.info(f"[{self.device.device_id}] Connecting to {self.device.user}@{self.device.host}:{self.device.port}")

            connect_kwargs = {
                "host": self.device.host,
                "port": self.device.port,
                "username": self.device.user,
                "known_hosts": None,
                "connect_timeout": 30,
                "keepalive_interval": 15,
            }

            if self.device.key_file:
                connect_kwargs["client_keys"] = [self.device.key_file]
            elif self.device.password:
                connect_kwargs["password"] = self.device.password

            self.connection = await asyncssh.connect(**connect_kwargs)
            self.is_connected = True
            logger.info(f"[{self.device.device_id}] SSH connection established")
            self.audit.log_connection("CONNECT", f"{self.device.display_name}")
            return True

        except asyncssh.Error as e:
            logger.error(f"[{self.device.device_id}] SSH connection failed: {e}")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"[{self.device.device_id}] Unexpected error: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Close SSH connection."""
        if self.connection:
            self.connection.close()
            await self.connection.wait_closed()
            self.is_connected = False
            logger.info(f"[{self.device.device_id}] SSH connection closed")

    async def ensure_connected(self):
        """Ensure connection is active, reconnect if needed."""
        if not self.is_connected:
            logger.info(f"[{self.device.device_id}] Reconnecting...")
            await self.connect()

    async def execute(self, command: str, timeout: int = 30) -> dict:
        """Execute a command on the device."""
        if not self.is_connected or not self.connection:
            raise ConnectionError(
                f"[{self.device.device_id}] SSH connection not established"
            )

        start_time = datetime.now()
        try:
            result = await asyncio.wait_for(
                self.connection.run(command, check=False), timeout=timeout
            )
            execution_time = (datetime.now() - start_time).total_seconds()

            response = {
                "success": result.exit_status == 0,
                "stdout": result.stdout.strip() if result.stdout else "",
                "stderr": result.stderr.strip() if result.stderr else "",
                "exit_code": result.exit_status,
                "execution_time": execution_time,
                "device_id": self.device.device_id,
            }

            self.audit.log_command(
                command=f"[{self.device.device_id}] {command}",
                success=response["success"],
                output=response["stdout"],
                error=response["stderr"] if not response["success"] else None,
                execution_time=execution_time,
            )

            return response

        except asyncio.TimeoutError:
            execution_time = (datetime.now() - start_time).total_seconds()
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "exit_code": -1,
                "execution_time": execution_time,
                "device_id": self.device.device_id,
            }
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "execution_time": execution_time,
                "device_id": self.device.device_id,
            }

    async def test_connection(self) -> dict:
        """Test SSH connection with a simple command."""
        try:
            await self.ensure_connected()
            result = await self.execute("echo 'Connection OK'")
            if result["success"]:
                return {
                    "device_id": self.device.device_id,
                    "host": self.device.host,
                    "connected": True,
                    "message": "SSH connection working",
                }
            else:
                return {
                    "device_id": self.device.device_id,
                    "host": self.device.host,
                    "connected": False,
                    "error": result["stderr"],
                }
        except Exception as e:
            return {
                "device_id": self.device.device_id,
                "host": self.device.host,
                "connected": False,
                "error": str(e),
            }


class MultiSSHClientManager:
    """Manages SSH connections to multiple OpenWRT devices."""

    def __init__(self):
        self.clients: dict[str, DeviceSSHClient] = {}

    def register_device(self, device: DeviceConfig):
        """Register a device for SSH management."""
        self.clients[device.device_id] = DeviceSSHClient(device)
        logger.info(f"Registered device: {device.display_name}")

    def register_topology(self, topology: NetworkTopology):
        """Register all devices from a network topology."""
        for device in topology.list_devices():
            self.register_device(device)
        logger.info(f"Registered {len(self.clients)} devices from topology")

    def get_client(self, device_id: str) -> Optional[DeviceSSHClient]:
        """Get SSH client for a specific device."""
        # Case-insensitive lookup
        for did, client in self.clients.items():
            if did.lower() == device_id.lower():
                return client
        return None

    async def connect_all(self) -> dict[str, bool]:
        """Connect to all registered devices."""
        results = {}
        tasks = []
        for device_id, client in self.clients.items():
            tasks.append((device_id, client.connect()))

        for device_id, task in tasks:
            try:
                results[device_id] = await task
            except Exception as e:
                logger.error(f"Failed to connect to {device_id}: {e}")
                results[device_id] = False

        connected = sum(1 for v in results.values() if v)
        logger.info(f"Connected to {connected}/{len(results)} devices")
        return results

    async def disconnect_all(self):
        """Disconnect all devices."""
        for client in self.clients.values():
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting {client.device.device_id}: {e}")

    async def test_all_connections(self) -> list[dict]:
        """Test connectivity to all devices."""
        results = []
        for client in self.clients.values():
            result = await client.test_connection()
            results.append(result)
        return results

    async def execute_on_device(
        self, device_id: str, command: str, validate: bool = True
    ) -> dict:
        """Execute a command on a specific device."""
        client = self.get_client(device_id)
        if not client:
            return {
                "success": False,
                "error": f"Device '{device_id}' not found. Available: {list(self.clients.keys())}",
                "device_id": device_id,
            }

        # Validate command
        if validate:
            is_valid, error_msg = SecurityValidator.validate_command(command)
            if not is_valid:
                return {
                    "success": False,
                    "error": error_msg,
                    "output": "",
                    "device_id": device_id,
                }

        await client.ensure_connected()
        return await client.execute(command)

    async def execute_on_all(
        self, command: str, validate: bool = True
    ) -> dict[str, dict]:
        """Execute a command on all devices."""
        results = {}
        for device_id in self.clients:
            results[device_id] = await self.execute_on_device(
                device_id, command, validate
            )
        return results

    def list_devices(self) -> list[dict]:
        """List all registered devices with status."""
        return [
            {
                "device_id": client.device.device_id,
                "host": client.device.host,
                "port": client.device.port,
                "role": client.device.role,
                "description": client.device.description,
                "connected": client.is_connected,
            }
            for client in self.clients.values()
        ]


# Global multi-SSH client manager
ssh_manager = MultiSSHClientManager()
