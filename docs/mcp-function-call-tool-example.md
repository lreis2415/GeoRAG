# LangChain Function Call Tool — Example

This shows how to wrap a plain Python function as a LangChain tool using the `@tool` decorator.
It was previously kept as reference code inside `mcp_service.py` but moved here to keep production
files clean.

## Basic pattern

```python
from datetime import datetime
from langchain.tools import tool

@tool("get_current_time", return_direct=True)
def get_current_time():
    """Get the current date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Register it in a tool list that you pass to the agent
tools = [get_current_time]
```

### Key parameters

| Parameter       | Description                                                   |
|-----------------|---------------------------------------------------------------|
| `name`          | First positional arg — the tool name the LLM sees            |
| `return_direct` | If `True`, the tool output is returned directly to the user  |
| docstring       | Becomes the tool description used for LLM tool selection     |

## Using MCP tools instead

In production this project uses `MultiServerMCPClient` to load tools from external MCP servers.
See `app/services/mcp_service.py` and `docs/MCP服务代码文档.md`.
