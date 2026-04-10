"""Simple script to test SSH connection to OpenWRT."""

import asyncio
import asyncssh
import sys

async def test_connection():
    """Test SSH connection to the OpenWRT router."""
    host = "192.168.1.111"
    port = 22
    username = "root"

    try:
        print(f"Connecting to {username}@{host}:{port} ...")
        print("Using default SSH key authentication ...")

        conn = await asyncssh.connect(
            host=host,
            port=port,
            username=username,
            known_hosts=None,
            connect_timeout=10,
        )

        print("SSH connection established successfully!")

        result = await conn.run("uname -a", check=True)
        print(f"\nSystem info:")
        print(result.stdout)

        result = await conn.run("cat /etc/openwrt_version 2>/dev/null || cat /etc/openwrt_release | grep DISTRIB_DESCRIPTION", check=False)
        if result.stdout:
            print(f"OpenWRT version:")
            print(result.stdout)

        result = await conn.run("uci show system.@system[0].hostname 2>/dev/null", check=False)
        if result.stdout:
            print(f"\nHostname:")
            print(result.stdout)

        conn.close()
        await conn.wait_closed()

        print("\nTest completed successfully!")
        print("The MCP server is ready to use with your OpenWRT router.")
        return True

    except asyncssh.Error as e:
        print(f"\nSSH connection error: {e}")
        print("\nPossible fixes:")
        print("1. Verify the router is reachable at", host)
        print("2. Verify SSH is enabled on the router")
        print("3. Authorize your SSH key on the router:")
        print("   ssh-copy-id -i ~/.ssh/id_ed25519.pub root@" + host)
        print("4. Or configure password authentication in .env")
        return False
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
