# Testing OpenWRT Package Management Tools

This file documents testing of the new package management tools (opkg) added to the OpenWRT MCP.

## 🎯 Added Tools

**6 new tools** have been added for package management:

1. **openwrt_opkg_update** - Update package lists from repositories
2. **openwrt_opkg_install** - Install packages
3. **openwrt_opkg_remove** - Remove packages
4. **openwrt_opkg_list_installed** - List installed packages
5. **openwrt_opkg_info** - Get detailed package information
6. **openwrt_opkg_list_available** - List available packages (limited to 500)

## 📋 Whitelisted Commands

The following `opkg` commands are now allowed in `security.py`:

```python
r"^opkg update$",
r"^opkg list$",
r"^opkg list-installed$",
r"^opkg list-upgradable$",
r"^opkg info [a-zA-Z0-9._-]+$",
r"^opkg install [a-zA-Z0-9._-]+$",
r"^opkg remove [a-zA-Z0-9._-]+$",
r"^opkg upgrade [a-zA-Z0-9._-]+$",
r"^opkg search [a-zA-Z0-9._-]+$",
```

## 🧪 Recommended Tests

### 1. Update package lists

```
Use tool: openwrt_opkg_update
```

**Expected result:**
```json
{
  "success": true,
  "message": "Package lists updated successfully",
  "output": "..."
}
```

### 2. List installed packages

```
Use tool: openwrt_opkg_list_installed
```

**Expected result:**
```json
{
  "success": true,
  "packages": [
    {"name": "base-files", "version": "1468-r24239-e85ae6ab87"},
    {"name": "busybox", "version": "1.36.1-1"},
    ...
  ],
  "count": 150
}
```

### 3. Search for OpenThread information

```
Use tool: openwrt_opkg_info
Argument: package_name = "ot-br-posix"
```

**Expected result if exists:**
```json
{
  "success": true,
  "package_info": {
    "package": "ot-br-posix",
    "version": "...",
    "description": "OpenThread Border Router",
    ...
  }
}
```

### 4. Install OpenThread Border Router

```
Use tool: openwrt_opkg_install
Argument: package_name = "ot-br-posix"
```

**Expected result:**
```json
{
  "success": true,
  "message": "Package 'ot-br-posix' installed successfully",
  "output": "Installing ot-br-posix..."
}
```

### 5. Install LuCI App for OpenThread

```
Use tool: openwrt_opkg_install
Argument: package_name = "luci-app-openthread"
```

### 6. Verify installation

After installing, verify with:

```
Use tool: openwrt_thread_get_state
```

Should work if OpenThread was installed correctly.

## 🔒 Security Validations

The tools include validations:

1. **Package name validation**: Only alphanumeric characters, dash, underscore, and dot
2. **Whitelisted commands**: Only specific opkg commands are allowed
3. **Result limit**: Available package list is limited to 500 to avoid huge responses

## 📝 Complete Usage Example

### Install OpenThread on your router:

```bash
# 1. Update repositories
openwrt_opkg_update

# 2. Search for package information
openwrt_opkg_info("ot-br-posix")

# 3. Install the package
openwrt_opkg_install("ot-br-posix")

# 4. Verify it works
openwrt_thread_get_state
```

## ⚠️ Important Notes

1. **MCP Restart**: After adding these tools, it's necessary to restart the MCP server for them to load.

2. **Package availability**: Not all OpenWRT routers have OpenThread in their repositories. It depends on:
   - OpenWRT version
   - Hardware architecture
   - Configured repositories

3. **Disk space**: Some packages require considerable space. Check with `openwrt_get_system_info` before installing.

4. **Dependencies**: `opkg` automatically handles dependencies, but some may fail if they're not in the repositories.

## 🔄 Next Steps

Once the tools are working:

1. Test repository update
2. Search if `ot-br-posix` is available for your router
3. If available, install OpenThread
4. Test the Thread tools that were already implemented
5. Document the complete process

## 🐛 Troubleshooting

### Error: "Package not found"
- The package is not in your OpenWRT version's repositories
- Run `opkg update` first
- Check with `opkg_list_available` if the package exists

### Error: "No space left on device"
- The router doesn't have enough space
- Check with `openwrt_get_system_info`
- Consider removing unused packages

### Error: "Command not in whitelist"
- The command is not allowed for security reasons
- Review `security.py` to see allowed commands
- Use only the provided tools

## 📊 Implementation Status

- ✅ Tools implemented in `tools.py`
- ✅ Commands added to whitelist in `security.py`
- ✅ Endpoints added to MCP server in `server.py`
- ⏳ Pending: Tests on real router
- ⏳ Pending: OpenThread installation

---

**Creation date**: November 28, 2025
**Author**: GitHub Copilot
**Version**: 1.0
