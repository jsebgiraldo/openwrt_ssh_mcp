"""Smoke tests for the three new edge-gateway MCP tools."""

import pytest
from unittest.mock import AsyncMock, patch

# Provide env vars before importing the module under test
import os
os.environ.setdefault("ENABLE_AUDIT_LOGGING", "false")
os.environ.setdefault("OPENWRT_HOST", "192.168.1.111")

from openwrt_ssh_mcp.tools import OpenWRTTools


def _ssh_ok(stdout: str = "", stderr: str = "") -> dict:
    """Build a successful ssh_client.execute() return value."""
    return {"success": True, "stdout": stdout, "stderr": stderr, "exit_code": 0, "execution_time": 0.1}


def _ssh_fail(stderr: str = "error") -> dict:
    """Build a failed ssh_client.execute() return value."""
    return {"success": False, "stdout": "", "stderr": stderr, "exit_code": 1, "execution_time": 0.1}


# ──────────────────────────────────────────────────────────────────────────────
# otbr_persist_network
# ──────────────────────────────────────────────────────────────────────────────

class TestOtbrPersistNetwork:
    """Smoke tests for otbr_persist_network."""

    @pytest.mark.asyncio
    async def test_no_active_dataset(self):
        """Returns failure when Thread is not running."""
        with patch("openwrt_ssh_mcp.tools.ssh_client") as mock_ssh:
            mock_ssh.ensure_connected = AsyncMock()
            mock_ssh.execute = AsyncMock(side_effect=[
                _ssh_ok(),          # mkdir -p /etc/otbr
                _ssh_ok(""),        # ot-ctl dataset active -x → empty
            ])
            result = await OpenWRTTools.otbr_persist_network()

        assert result["success"] is False
        assert "dataset" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_persist_via_rclocal(self):
        """Happy path: persists via rc.local when no uci otbr-agent config."""
        tlv = "0e080000000000010000"
        with patch("openwrt_ssh_mcp.tools.ssh_client") as mock_ssh:
            mock_ssh.ensure_connected = AsyncMock()
            mock_ssh.execute = AsyncMock(side_effect=[
                _ssh_ok(),                          # mkdir -p /etc/otbr
                _ssh_ok(tlv + "\nDone"),            # ot-ctl dataset active -x
                _ssh_ok(),                          # write TLV file
                _ssh_ok("Active Timestamp: 1"),     # ot-ctl dataset active (human)
                _ssh_ok(),                          # write human dataset
                _ssh_ok(),                          # write reapply script (heredoc)
                _ssh_ok(""),                        # ls /etc/config/otbr-agent → not found
                _ssh_ok(""),                        # grep marker in rc.local → not found
                _ssh_ok(),                          # sed rc.local
                _ssh_ok(),                          # /etc/init.d/otbr-agent enable && restart
                _ssh_ok(""),                        # grep /etc/otbr/ in sysupgrade.conf
                _ssh_ok(),                          # append /etc/otbr/
                _ssh_ok(""),                        # grep /etc/rc.local in sysupgrade.conf
                _ssh_ok(),                          # append /etc/rc.local
                _ssh_ok("leader\nDone"),            # ot-ctl state
            ])
            result = await OpenWRTTools.otbr_persist_network()

        assert result["success"] is True
        assert result["dataset_saved"] is True
        assert result["mode"] == "rc.local"
        assert result["state_after"] == "leader"


# ──────────────────────────────────────────────────────────────────────────────
# thingsboard_probe
# ──────────────────────────────────────────────────────────────────────────────

class TestThingsboardProbe:
    """Smoke tests for thingsboard_probe."""

    @pytest.mark.asyncio
    async def test_explicit_host_all_unreachable(self):
        """When host is explicit but all ports are closed."""
        with patch("openwrt_ssh_mcp.tools.ssh_client") as mock_ssh:
            mock_ssh.ensure_connected = AsyncMock()
            mock_ssh.execute = AsyncMock(side_effect=[
                _ssh_fail("Connection refused"),  # nc mqtt
                _ssh_fail("Connection refused"),  # nc mqtts
                _ssh_ok("000"),                   # curl http
            ])
            result = await OpenWRTTools.thingsboard_probe(host="10.0.0.1")

        assert result["success"] is True
        assert result["discovered"] is True
        assert result["host"] == "10.0.0.1"
        assert result["reachability"]["mqtt"]["reachable"] is False
        assert result["reachability"]["http"]["reachable"] is False
        assert result["transport_guess"] == "unreachable"

    @pytest.mark.asyncio
    async def test_explicit_host_mqtt_reachable(self):
        """When MQTT port is open."""
        with patch("openwrt_ssh_mcp.tools.ssh_client") as mock_ssh:
            mock_ssh.ensure_connected = AsyncMock()
            mock_ssh.execute = AsyncMock(side_effect=[
                _ssh_ok("succeeded!"),  # nc mqtt — 'succeeded' in output
                _ssh_fail(),            # nc mqtts
                _ssh_ok("000"),         # curl http
            ])
            result = await OpenWRTTools.thingsboard_probe(host="10.0.0.1")

        assert result["success"] is True
        assert result["reachability"]["mqtt"]["reachable"] is True
        assert result["transport_guess"] == "mqtt"

    @pytest.mark.asyncio
    async def test_auto_discover_no_host(self):
        """Returns discovered=False when nothing is found."""
        with patch("openwrt_ssh_mcp.tools.ssh_client") as mock_ssh:
            mock_ssh.ensure_connected = AsyncMock()
            # All discovery steps return empty
            mock_ssh.execute = AsyncMock(return_value=_ssh_ok(""))
            result = await OpenWRTTools.thingsboard_probe()

        assert result["success"] is True
        assert result["discovered"] is False
        assert result["host"] is None


# ──────────────────────────────────────────────────────────────────────────────
# observability_health
# ──────────────────────────────────────────────────────────────────────────────

class TestObservabilityHealth:
    """Smoke tests for observability_health."""

    @pytest.mark.asyncio
    async def test_all_up(self):
        """All components return 200."""
        with patch("openwrt_ssh_mcp.tools.ssh_client") as mock_ssh:
            mock_ssh.ensure_connected = AsyncMock()
            mock_ssh.execute = AsyncMock(side_effect=[
                _ssh_ok("200"),                         # prometheus /-/ready
                _ssh_ok("200"),                         # grafana /api/health
                _ssh_ok("200"),                         # blackbox /-/healthy
                _ssh_ok("prometheus\tUp 2 hours"),      # docker ps
                _ssh_ok("LISTEN 0.0.0.0:9090"),         # ss -ltn
            ])
            result = await OpenWRTTools.observability_health()

        assert result["success"] is True
        assert result["all_up"] is True
        assert result["components"]["prometheus"]["up"] is True
        assert result["components"]["grafana"]["up"] is True
        assert result["components"]["blackbox"]["up"] is True

    @pytest.mark.asyncio
    async def test_grafana_down(self):
        """all_up is False when Grafana is unreachable."""
        with patch("openwrt_ssh_mcp.tools.ssh_client") as mock_ssh:
            mock_ssh.ensure_connected = AsyncMock()
            mock_ssh.execute = AsyncMock(side_effect=[
                _ssh_ok("200"),   # prometheus
                _ssh_ok("error"), # grafana (curl failed)
                _ssh_ok("200"),   # blackbox
                _ssh_ok(""),      # docker ps
                _ssh_ok(""),      # ss
            ])
            result = await OpenWRTTools.observability_health()

        assert result["success"] is True
        assert result["all_up"] is False
        assert result["components"]["grafana"]["up"] is False
