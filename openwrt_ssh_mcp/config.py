"""Configuration management for OpenWRT SSH MCP Server."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # OpenWRT Router SSH Configuration
    openwrt_host: str = "192.168.1.1"
    openwrt_port: int = 22
    openwrt_user: str = "root"
    openwrt_password: Optional[str] = None
    openwrt_key_file: Optional[str] = None

    # SSH Connection Settings
    ssh_timeout: int = 30
    ssh_keepalive_interval: int = 15

    # Security Settings
    enable_command_validation: bool = True
    enable_audit_logging: bool = True
    log_file: str = "openwrt_mcp.log"

    def validate_auth(self) -> None:
        """Ensure at least one authentication method is configured."""
        if not self.openwrt_password and not self.openwrt_key_file:
            raise ValueError(
                "Either OPENWRT_PASSWORD or OPENWRT_KEY_FILE must be configured"
            )


# Global settings instance
settings = Settings()
