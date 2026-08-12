"""Device inventory and topology management for multi-device OpenWRT network."""

import logging
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DeviceConfig:
    """Configuration for a single OpenWRT device."""

    device_id: str
    host: str
    port: int = 22
    user: str = "root"
    password: Optional[str] = None
    key_file: Optional[str] = None
    role: str = "router"  # wan, gateway, router, ap, etc.
    description: str = ""
    interfaces: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return f"{self.device_id} ({self.host}) [{self.role}]"


@dataclass
class NetworkTopology:
    """Represents the full network topology."""

    name: str
    description: str
    devices: dict[str, DeviceConfig]
    wan_device: Optional[str] = None

    def get_device(self, device_id: str) -> Optional[DeviceConfig]:
        """Get device by ID (case-insensitive)."""
        key = device_id.lower()
        for did, dev in self.devices.items():
            if did.lower() == key:
                return dev
        return None

    def list_devices(self) -> list[DeviceConfig]:
        """List all devices."""
        return list(self.devices.values())

    def get_devices_by_role(self, role: str) -> list[DeviceConfig]:
        """Get devices by role."""
        return [d for d in self.devices.values() if d.role.lower() == role.lower()]

    def get_devices_by_tag(self, tag: str) -> list[DeviceConfig]:
        """Get devices matching a tag."""
        return [d for d in self.devices.values() if tag.lower() in [t.lower() for t in d.tags]]


class DeviceInventory:
    """Manages the network device inventory from YAML configuration."""

    def __init__(self):
        self.topology: Optional[NetworkTopology] = None

    def load_from_yaml(self, config_path: str | Path) -> NetworkTopology:
        """Load network topology from a YAML file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Topology config not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        devices = {}
        for dev_id, dev_data in raw.get("devices", {}).items():
            devices[dev_id] = DeviceConfig(
                device_id=dev_id,
                host=dev_data["host"],
                port=dev_data.get("port", 22),
                user=dev_data.get("user", "root"),
                password=dev_data.get("password"),
                key_file=dev_data.get("key_file"),
                role=dev_data.get("role", "router"),
                description=dev_data.get("description", ""),
                interfaces=dev_data.get("interfaces", []),
                tags=dev_data.get("tags", []),
            )

        self.topology = NetworkTopology(
            name=raw.get("network_name", "OpenWRT Network"),
            description=raw.get("description", ""),
            devices=devices,
            wan_device=raw.get("wan_device"),
        )

        logger.info(
            f"Loaded topology '{self.topology.name}' with {len(devices)} devices"
        )
        return self.topology

    def load_from_dict(self, config: dict) -> NetworkTopology:
        """Load network topology from a dictionary."""
        devices = {}
        for dev_id, dev_data in config.get("devices", {}).items():
            devices[dev_id] = DeviceConfig(
                device_id=dev_id,
                host=dev_data["host"],
                port=dev_data.get("port", 22),
                user=dev_data.get("user", "root"),
                password=dev_data.get("password"),
                key_file=dev_data.get("key_file"),
                role=dev_data.get("role", "router"),
                description=dev_data.get("description", ""),
                interfaces=dev_data.get("interfaces", []),
                tags=dev_data.get("tags", []),
            )

        self.topology = NetworkTopology(
            name=config.get("network_name", "OpenWRT Network"),
            description=config.get("description", ""),
            devices=devices,
            wan_device=config.get("wan_device"),
        )
        return self.topology


# Global inventory instance
device_inventory = DeviceInventory()
