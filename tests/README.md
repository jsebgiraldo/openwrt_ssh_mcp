# Tests

This directory contains tests for the OpenWRT SSH MCP Server.

## Current Tests

- `test_security.py` - Security validation and command whitelist tests

## Running Tests

### Prerequisites
```bash
pip install -e ".[dev]"
```

### Run all tests
```bash
pytest tests/
```

### Run with coverage
```bash
pytest --cov=openwrt_ssh_mcp tests/
```

### Run specific test file
```bash
pytest tests/test_security.py -v
```

## Test Categories

### Security Tests (test_security.py)
- Command whitelist validation
- Blocked pattern detection
- Input sanitization
- Edge cases

### Future Tests (TODO)
- [ ] SSH connection tests (requires mock)
- [ ] Tool execution tests (requires mock)
- [ ] Configuration validation tests
- [ ] Integration tests with real router
- [ ] Error handling tests

## Adding New Tests

1. Create test file: `test_<feature>.py`
2. Import pytest and required modules
3. Write test functions starting with `test_`
4. Run tests and ensure they pass
5. Add to CI/CD pipeline

Example:
```python
import pytest
from openwrt_ssh_mcp.tools import OpenWRTTools

@pytest.mark.asyncio
async def test_my_feature():
    result = await OpenWRTTools.my_tool("test")
    assert result["success"] is True
```

## Continuous Integration

Tests should be run automatically on:
- Every commit
- Pull requests
- Before releases

## Test Coverage Goals

- Minimum: 70% code coverage
- Target: 85% code coverage
- Security functions: 100% coverage
