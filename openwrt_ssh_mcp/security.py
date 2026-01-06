"""Security utilities for command validation and audit logging."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from .config import settings

# Configure logging
logger = logging.getLogger(__name__)


class SecurityValidator:
    """Validates commands before execution to prevent malicious actions."""

    # Whitelist of allowed command patterns
    ALLOWED_PATTERNS = [
        # UBUS calls - OpenWRT service bus
        r"^ubus call network\.interface\.\w+ \w+$",  # Network interface operations
        r"^ubus call network\.wireless status$",  # WiFi status
        r"^ubus call system board$",  # System info
        r"^ubus call system info$",  # System info
        r"^ubus list.*$",  # List available ubus services
        
        # UCI configuration reads
        r"^uci show network$",  # Network config
        r"^uci show wireless$",  # Wireless config
        r"^uci show dhcp$",  # DHCP config
        r"^uci show firewall$",  # Firewall config
        r"^uci show system$",  # System config
        r"^uci get \w+\.\S+$",  # Get specific UCI value
        
        # System information (read-only)
        r"^cat /proc/(uptime|meminfo|cpuinfo|loadavg)$",
        r"^cat /etc/openwrt_release$",
        r"^ip addr show$",
        r"^ip route show$",
        r"^df -h$",
        r"^free$",
        r"^uptime$",
        
        # DHCP lease information
        r"^cat /tmp/dhcp\.leases$",
        r"^cat /var/dhcp\.leases$",
        
        # Firewall status
        r"^iptables -L -n -v$",
        r"^iptables -t nat -L -n -v$",
        
        # Process information
        r"^ps$",
        r"^ps w$",
        r"^top -n 1 -b$",
        
        # Network diagnostics
        r"^ping -c \d+ [\w\.\-]+$",
        r"^traceroute [\w\.\-]+$",
        r"^nslookup [\w\.\-]+$",
        
        # OpenThread Border Router (OTBR) commands
        r"^(/usr/sbin/)?ot-ctl state$",
        r"^(/usr/sbin/)?ot-ctl channel$",
        r"^(/usr/sbin/)?ot-ctl channel \d+$",
        r"^(/usr/sbin/)?ot-ctl panid$",
        r"^(/usr/sbin/)?ot-ctl panid 0x[0-9a-fA-F]+$",
        r"^(/usr/sbin/)?ot-ctl networkkey$",
        r"^(/usr/sbin/)?ot-ctl networkkey [0-9a-fA-F]{32}$",
        r"^(/usr/sbin/)?ot-ctl networkname$",
        r"^(/usr/sbin/)?ot-ctl networkname [\w\-]+$",
        r"^(/usr/sbin/)?ot-ctl extpanid$",
        r"^(/usr/sbin/)?ot-ctl extpanid [0-9a-fA-F]{16}$",
        r"^(/usr/sbin/)?ot-ctl ifconfig$",
        r"^(/usr/sbin/)?ot-ctl ifconfig up$",
        r"^(/usr/sbin/)?ot-ctl ifconfig down$",
        r"^(/usr/sbin/)?ot-ctl thread start$",
        r"^(/usr/sbin/)?ot-ctl thread stop$",
        r"^(/usr/sbin/)?ot-ctl dataset init new$",
        r"^(/usr/sbin/)?ot-ctl dataset commit active$",
        r"^(/usr/sbin/)?ot-ctl dataset active$",
        r"^(/usr/sbin/)?ot-ctl dataset pending$",
        r"^(/usr/sbin/)?ot-ctl dataset active -x$",
        r"^(/usr/sbin/)?ot-ctl dataset set active [0-9a-fA-F]+$",
        r"^(/usr/sbin/)?ot-ctl prefix add [\da-fA-F:]+/\d+ paros$",
        r"^(/usr/sbin/)?ot-ctl prefix$",
        r"^(/usr/sbin/)?ot-ctl neighbor table$",
        r"^(/usr/sbin/)?ot-ctl router table$",
        r"^(/usr/sbin/)?ot-ctl child table$",
        r"^(/usr/sbin/)?ot-ctl ipaddr$",
        r"^(/usr/sbin/)?ot-ctl rloc16$",
        r"^(/usr/sbin/)?ot-ctl leaderdata$",
        r"^(/usr/sbin/)?ot-ctl commissioner start$",
        r"^(/usr/sbin/)?ot-ctl commissioner stop$",
        r"^(/usr/sbin/)?ot-ctl commissioner joiner add \* [\w\-]+$",
        
        # Package management (opkg) commands
        r"^opkg update$",
        r"^opkg list$",
        r"^opkg list-installed$",
        r"^opkg list-upgradable$",
        r"^opkg info [a-zA-Z0-9._-]+$",
        r"^opkg install [a-zA-Z0-9._-]+$",
        r"^opkg remove [a-zA-Z0-9._-]+$",
        r"^opkg upgrade [a-zA-Z0-9._-]+$",
        r"^opkg search [a-zA-Z0-9._-]+$",
    ]

    # Dangerous patterns to explicitly block
    BLOCKED_PATTERNS = [
        r"rm\s+-rf",  # Recursive force delete
        r"dd\s+if=",  # Disk operations
        r"mkfs",  # Format filesystem
        r"shutdown",  # System shutdown
        r"reboot",  # System reboot (use ubus instead)
        r"halt",
        r"poweroff",
        r">/dev/sd",  # Direct disk write
        r"chmod\s+777",  # Insecure permissions
        r"passwd",  # Password change
        r"dropbear.*stop",  # Stop SSH server
        r"killall\s+dropbear",  # Kill SSH
        r"wget.*\|.*sh",  # Download and execute
        r"curl.*\|.*sh",  # Download and execute
        r"\|.*nc\s+",  # Netcat piping
        r"telnet",  # Insecure telnet
    ]

    @classmethod
    def validate_command(cls, command: str) -> tuple[bool, Optional[str]]:
        """
        Validate if a command is safe to execute.
        
        Returns:
            tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        if not settings.enable_command_validation:
            logger.warning("Command validation is DISABLED - executing without checks")
            return True, None

        # Check for blocked patterns first
        for pattern in cls.BLOCKED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                error = f"Command blocked by security policy: matches dangerous pattern '{pattern}'"
                logger.warning(f"SECURITY: Blocked command: {command}")
                return False, error

        # Check against whitelist
        for pattern in cls.ALLOWED_PATTERNS:
            if re.match(pattern, command.strip()):
                logger.debug(f"Command validated: {command}")
                return True, None

        # Command not in whitelist
        error = f"Command not in whitelist: {command}"
        logger.warning(f"SECURITY: Command rejected (not whitelisted): {command}")
        return False, error


class AuditLogger:
    """Logs all command executions for security auditing."""

    def __init__(self):
        """Initialize audit logger."""
        if settings.enable_audit_logging:
            self.log_file = Path(settings.log_file)
            self._setup_logging()

    def _setup_logging(self):
        """Configure audit log file."""
        # Create file handler for audit log
        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        
        # Format: timestamp | level | message
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to root logger
        audit_logger = logging.getLogger("audit")
        audit_logger.setLevel(logging.INFO)
        audit_logger.addHandler(file_handler)
        
        self.logger = audit_logger

    def log_command(
        self,
        command: str,
        success: bool,
        output: Optional[str] = None,
        error: Optional[str] = None,
        execution_time: Optional[float] = None,
    ):
        """
        Log command execution details.
        
        Args:
            command: The command that was executed
            success: Whether execution was successful
            output: Command output (truncated if too long)
            error: Error message if failed
            execution_time: Time taken in seconds
        """
        if not settings.enable_audit_logging:
            return

        status = "SUCCESS" if success else "FAILED"
        
        # Truncate output for logging
        log_output = ""
        if output:
            log_output = output[:200] + "..." if len(output) > 200 else output
            log_output = log_output.replace("\n", " ")
        
        log_message = f"COMMAND: {command} | STATUS: {status}"
        
        if execution_time:
            log_message += f" | TIME: {execution_time:.2f}s"
        
        if error:
            log_message += f" | ERROR: {error}"
        elif log_output:
            log_message += f" | OUTPUT: {log_output}"

        self.logger.info(log_message)

    def log_connection(self, event: str, details: Optional[str] = None):
        """
        Log SSH connection events.
        
        Args:
            event: Event type (CONNECT, DISCONNECT, ERROR, etc.)
            details: Additional details
        """
        if not settings.enable_audit_logging:
            return

        log_message = f"SSH {event}"
        if details:
            log_message += f" | {details}"
        
        self.logger.info(log_message)


# Global audit logger instance
audit_logger = AuditLogger()
