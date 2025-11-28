# Contributing to OpenWRT SSH MCP Server

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## 🚀 Quick Start

1. **Fork the repository**
2. **Clone your fork**
   ```bash
   git clone https://github.com/yourusername/openwrt-ssh-mcp.git
   cd openwrt-ssh-mcp
   ```
3. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   .\venv\Scripts\activate   # Windows
   ```
4. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

## 🛠️ Development Setup

### Prerequisites
- Python 3.10+
- Docker (optional, for containerized testing)
- Access to an OpenWRT router for testing

### Running Tests
```bash
pytest tests/
```

### Code Style
We use:
- `black` for code formatting
- `ruff` for linting
- `mypy` for type checking

Run before committing:
```bash
black .
ruff check --fix .
mypy openwrt_ssh_mcp/
```

## 📝 Making Changes

### Adding New Tools

1. **Add the tool method in `openwrt_ssh_mcp/tools.py`**
   ```python
   @staticmethod
   async def my_new_tool(param: str) -> dict[str, Any]:
       """
       Description of what the tool does.
       
       Args:
           param: Description of parameter
           
       Returns:
           dict: Result with success status
       """
       command = f"some-command {param}"
       result = await OpenWRTTools.execute_command(command)
       return {"success": result["success"], "data": result["output"]}
   ```

2. **Add command patterns to whitelist in `openwrt_ssh_mcp/security.py`**
   ```python
   ALLOWED_PATTERNS = [
       # ... existing patterns ...
       r"^some-command [\w\-]+$",  # Your new command pattern
   ]
   ```

3. **Register the tool in `openwrt_ssh_mcp/server.py`**
   ```python
   # In list_tools()
   Tool(
       name="openwrt_my_new_tool",
       description="What it does",
       inputSchema={
           "type": "object",
           "properties": {
               "param": {
                   "type": "string",
                   "description": "Parameter description",
               },
           },
           "required": ["param"],
       },
   ),
   
   # In call_tool()
   elif name == "openwrt_my_new_tool":
       param = arguments.get("param")
       if not param:
           raise ValueError("Missing required argument: param")
       result = await OpenWRTTools.my_new_tool(param)
   ```

4. **Add tests in `tests/test_tools.py`**

5. **Update documentation in `README.md`**

## 🔒 Security Considerations

When adding new tools:

1. **Always validate input** - Use regex or type checking
2. **Use whitelist approach** - Add specific command patterns to `ALLOWED_PATTERNS`
3. **Never allow arbitrary command execution** without validation
4. **Test with malicious inputs** - Try SQL injection, command injection, etc.
5. **Document security implications** in tool description

### Security Checklist
- [ ] Input validation implemented
- [ ] Command pattern added to whitelist
- [ ] No arbitrary command execution
- [ ] Tested with edge cases
- [ ] Documented in code comments

## 📋 Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes**
   - Write clear, documented code
   - Add tests for new functionality
   - Update documentation

3. **Test thoroughly**
   ```bash
   pytest tests/
   black --check .
   ruff check .
   ```

4. **Commit with clear messages**
   ```bash
   git commit -m "feat: add support for X feature"
   ```
   
   Use conventional commits:
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation changes
   - `test:` Test changes
   - `refactor:` Code refactoring
   - `chore:` Maintenance tasks

5. **Push and create PR**
   ```bash
   git push origin feature/my-new-feature
   ```

6. **PR Review**
   - Ensure CI passes
   - Respond to review comments
   - Update as needed

## 🐛 Bug Reports

When filing a bug report, include:

1. **Description** - What happened vs. what you expected
2. **Steps to reproduce** - Detailed steps
3. **Environment**:
   - OS and version
   - Python version
   - OpenWRT version
   - Router model
4. **Logs** - Include relevant error messages
5. **Configuration** - Sanitized `.env` (remove sensitive data)

## 💡 Feature Requests

For feature requests, describe:

1. **Use case** - What problem does it solve?
2. **Proposed solution** - How should it work?
3. **Alternatives** - What other options did you consider?
4. **Additional context** - Screenshots, examples, etc.

## 📚 Documentation

Help improve documentation:

- Fix typos and unclear instructions
- Add examples and use cases
- Translate to other languages
- Create video tutorials
- Write blog posts

## 🎯 Good First Issues

Look for issues labeled `good-first-issue` to get started!

Common areas for contribution:
- Adding new OpenWRT commands
- Improving error messages
- Writing tests
- Updating documentation
- Docker optimization
- VS Code integration improvements

## 🤝 Code of Conduct

Be respectful and inclusive. We're all learning together!

## 📧 Questions?

- Open a GitHub Discussion
- File an issue with the `question` label
- Check existing documentation

## 🙏 Thank You!

Every contribution helps make this project better. We appreciate your time and effort!

---

**Happy Coding!** 🚀
