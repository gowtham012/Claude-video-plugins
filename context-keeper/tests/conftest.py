"""
conftest.py — mock fastmcp so server.py imports cleanly without installing it.
The @mcp.tool() decorator is made a passthrough so functions remain callable.
"""
import sys
from unittest.mock import MagicMock


class _PassthroughFastMCP:
    """Minimal FastMCP stub. @mcp.tool() is a passthrough decorator."""
    def __init__(self, name: str):
        self.name = name

    def tool(self):
        def decorator(func):
            return func  # keep the original function unchanged
        return decorator

    def run(self):
        pass


_fastmcp_mock = MagicMock()
_fastmcp_mock.FastMCP = _PassthroughFastMCP
sys.modules.setdefault("fastmcp", _fastmcp_mock)
