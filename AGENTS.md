# Do

- Use uv for Python package management
- Follow Python 3.10+ syntax and type hints
- Use async/await for I/O operations
- Use TOON output for efficiency

# Don't

- Don't expose API keys or secrets
- Don't use sync HTTP calls
- Don't hardcode credentials

# Quick Commands

- Install dependencies: `uv sync`
- Run server: `python server.py`
- Check syntax: `python -m py_compile server.py tools.py config.py productive_client.py utils.py`

# Repo Map

- `server.py`: FastMCP server setup and tool definitions
- `tools.py`: Implementation of Productive API calls
- `config.py`: Environment variable configuration
- `productive_client.py`: HTTP client for Productive API
- `utils.py`: Helper functions
- `pyproject.toml`: Project metadata and dependencies

# Working Rules

- Use async/await for all I/O operations
- Validate configuration on startup
- Strip HTML and optimize output for LLMs
- Include webapp URLs in responses for direct access
- Handle errors gracefully without exposing internals

# Verification Steps

- Run `python -m file.py` and confirm no startup errors
- Check that all tools are registered in MCP
- Verify TOON/JSON output formats work
- Smoke test the packaged entrypoint: set `PRODUCTIVE_API_KEY` and `PRODUCTIVE_ORGANIZATION`, then run `uv run productive-mcp` and confirm the server starts without `TypeError: 'FastMCP' object is not callable`
- Ask the user for testing instructions when necessary

# Security Boundaries

- API tokens loaded from environment variables only
- No logging of sensitive data
- HTTPS enforced for all API requests
- Error messages don't leak credentials

# PR/Change Checklist

- [ ] Server starts without errors
- [ ] No secrets or credentials committed
- [ ] Type hints added for new functions
- [ ] Output optimized for LLM consumption
- [ ] README updated if tools changed