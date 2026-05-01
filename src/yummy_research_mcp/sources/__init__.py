"""Per-source fetchers. Each module exposes pure functions that return JSON-serialisable dicts.

Add a new source by:
  1. creating a module here (e.g. `ecos.py` for 한국은행 ECOS)
  2. exporting top-level fetch_* functions
  3. registering MCP tools in `yummy_research_mcp.server`
"""
