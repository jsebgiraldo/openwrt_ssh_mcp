"""SSH client for executing commands on OpenWRT router."""

import asyncio
import asyncssh
import logging
from typing import Optional
from datetime import datetime

from .config import settings
from .security import audit_logger

logger = logging.getLogger(__name__)


class SSHClient:
    """Manages SSH connection to OpenWRT router."""

    def __init__(self):
        """Initialize SSH client."""
        self.connection: Optional[asyncssh.SSHClientConnection] = None
        self.is_connected = False

    async def connect(self) -> bool:
        """
        Establish SSH connection to the OpenWRT router.
        
        Returns:
            bool: True if connection successful
        """
        try:
            logger.info(
                f"Connecting to {settings.openwrt_user}@{settings.openwrt_host}:{settings.openwrt_port}"
            )

            # Prepare connection parameters
            connect_kwargs = {
                "host": settings.openwrt_host,
                "port": settings.openwrt_port,
                "username": settings.openwrt_user,
                "known_hosts": None,  # Disable host key checking (adjust for production)
                "connect_timeout": settings.ssh_timeout,
                "keepalive_interval": settings.ssh_keepalive_interval,
            }

            # Authentication: prefer key over password
            if settings.openwrt_key_file:
                logger.info(f"Using SSH key authentication: {settings.openwrt_key_file}")
                connect_kwargs["client_keys"] = [settings.openwrt_key_file]
            elif settings.openwrt_password:
                logger.info("Using password authentication")
                connect_kwargs["password"] = settings.openwrt_password
            else:
                raise ValueError("No authentication method configured")

            # Establish connection
            self.connection = await asyncssh.connect(**connect_kwargs)
            self.is_connected = True

            logger.info("SSH connection established successfully")
            audit_logger.log_connection(
                "CONNECT",
                f"{settings.openwrt_user}@{settings.openwrt_host}:{settings.openwrt_port}"
            )

            return True

        except asyncssh.Error as e:
            logger.error(f"SSH connection failed: {e}")
            audit_logger.log_connection("ERROR", str(e))
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error during SSH connection: {e}")
            audit_logger.log_connection("ERROR", str(e))
            self.is_connected = False
            return False

    async def disconnect(self):
        """Close SSH connection."""
        if self.connection:
            self.connection.close()
            await self.connection.wait_closed()
            self.is_connected = False
            logger.info("SSH connection closed")
            audit_logger.log_connection("DISCONNECT", "Connection closed gracefully")

    async def execute(self, command: str, timeout: Optional[int] = None) -> dict:
        """
        Execute a command on the OpenWRT router.
        
        Args:
            command: Command to execute
            timeout: Execution timeout in seconds (defaults to SSH_TIMEOUT)
            
        Returns:
            dict: Execution result with keys:
                - success: bool
                - stdout: str
                - stderr: str
                - exit_code: int
                - execution_time: float
        """
        if not self.is_connected or not self.connection:
            raise ConnectionError("SSH connection not established. Call connect() first.")

        if timeout is None:
            timeout = settings.ssh_timeout

        start_time = datetime.now()
        
        try:
            logger.debug(f"Executing command: {command}")
            
            # Execute command
            result = await asyncio.wait_for(
                self.connection.run(command, check=False),
                timeout=timeout
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Parse result
            response = {
                "success": result.exit_status == 0,
                "stdout": result.stdout.strip() if result.stdout else "",
                "stderr": result.stderr.strip() if result.stderr else "",
                "exit_code": result.exit_status,
                "execution_time": execution_time,
            }

            # Log execution
            audit_logger.log_command(
                command=command,
                success=response["success"],
                output=response["stdout"],
                error=response["stderr"] if not response["success"] else None,
                execution_time=execution_time,
            )

            if response["success"]:
                logger.debug(f"Command succeeded in {execution_time:.2f}s")
            else:
                logger.warning(
                    f"Command failed with exit code {response['exit_code']}: {response['stderr']}"
                )

            return response

        except asyncio.TimeoutError:
            execution_time = (datetime.now() - start_time).total_seconds()
            error = f"Command execution timed out after {timeout}s"
            logger.error(error)
            audit_logger.log_command(
                command=command,
                success=False,
                error=error,
                execution_time=execution_time,
            )
            return {
                "success": False,
                "stdout": "",
                "stderr": error,
                "exit_code": -1,
                "execution_time": execution_time,
            }

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error = f"Command execution error: {str(e)}"
            logger.error(error)
            audit_logger.log_command(
                command=command,
                success=False,
                error=error,
                execution_time=execution_time,
            )
            return {
                "success": False,
                "stdout": "",
                "stderr": error,
                "exit_code": -1,
                "execution_time": execution_time,
            }

    async def ensure_connected(self):
        """Ensure SSH connection is active, reconnect if necessary."""
        if not self.is_connected:
            logger.info("Connection not active, attempting to reconnect...")
            await self.connect()

    async def test_connection(self) -> dict:
        """
        Test SSH connection with a simple command.
        
        Returns:
            dict: Connection test result
        """
        try:
            await self.ensure_connected()
            result = await self.execute("echo 'Connection test successful'")
            
            if result["success"]:
                return {
                    "connected": True,
                    "message": "SSH connection is working",
                    "router_response": result["stdout"],
                }
            else:
                return {
                    "connected": False,
                    "message": "SSH connection failed",
                    "error": result["stderr"],
                }
                
        except Exception as e:
            return {
                "connected": False,
                "message": "SSH connection test failed",
                "error": str(e),
            }


# Global SSH client instance
ssh_client = SSHClient()
