# MCP Session Management — Design Notes

This document covers how `MCPService` manages MCP connections in GeoRAG,
and explains the tradeoffs compared to patterns used in production chatbot systems.

---

## Current Implementation

**File:** `app/services/mcp_service.py`

### How it works

`MultiServerMCPClient` is a thin config holder — it stores the server addresses
but **does not open any network connections** at construction time.

```
MCPService.init_mcp_tools()
  └─► MultiServerMCPClient(MCP_CONFIG)   # stores config only, no I/O
  └─► client.get_tools()
        └─► for each server: open session → MCP initialize → list tools → close session
        └─► returns cached BaseTool list
```

After `init_mcp_tools()` completes, `self.mcp_tools` holds the full tool list.
The sessions opened during discovery are **closed immediately after**.

At runtime, when the agent calls a tool, `langchain-mcp-adapters` opens a fresh
session for that single invocation and closes it when the call returns.
This is documented in the library source:

> *"NOTE: a new session will be created for each tool call"*

### Session lifecycle per tool call

```
Agent invokes tool
  └─► TCP connect to MCP server
  └─► HTTP handshake
  └─► MCP initialize (capability negotiation)
  └─► tool call (request / response)
  └─► session closed
```

### Why `cleanup()` only sets references to None

`MultiServerMCPClient` holds no open connections. Its `__aexit__` raises
`NotImplementedError` (context manager support was removed in 0.1.0) and there
is no `aclose()` method. Dropping the Python reference is therefore complete
cleanup — nothing leaks.

---

## How Mature Chatbot Systems Handle This

Production systems (Cursor, Claude Desktop, enterprise gateways) typically apply
one or more of the following patterns.

### Pattern 1 — Persistent session with keepalive

Instead of opening a new session per tool call, a warm session is established
at startup and reused across all calls.

```
Startup:
  open session → MCP initialize → keep alive

Per tool call:
  reuse existing session → tool call

Background:
  heartbeat / reconnect with exponential backoff on failure

Shutdown:
  gracefully close session
```

**Benefit:** eliminates TCP + HTTP + MCP-initialize overhead on every call.
**Cost:** requires reconnect logic, health checks, and async lifecycle management.

For `stdio` transport this is the natural model — the subprocess runs
continuously and the stdin/stdout pipe stays open.

For `streamable_http`, the underlying `httpx.AsyncClient` already pools TCP
connections, so the remaining overhead per new MCP session is mainly the
`initialize` handshake.

### Pattern 2 — MCP gateway / proxy

Used by enterprise platforms (Dify, Amazon Bedrock Agents, internal deployments):

```
Your app  ──►  MCP Gateway  ──►  MCP Server A
                             ──►  MCP Server B
```

The gateway owns all persistent sessions. Your application only talks to the
gateway over a local connection that is always warm. Application restarts do
not tear down the server connections.

### Pattern 3 — Session-per-request (current approach)

Simplest to implement correctly. Each call is stateless; no reconnect logic
needed. This is the deliberate design choice of `langchain-mcp-adapters`.

---

## Tradeoff Summary

| Approach | Latency per tool call | Implementation complexity | Suitable for |
|---|---|---|---|
| Session-per-request (current) | Higher (handshake each time) | Low | Low call frequency |
| Persistent session | Lower (reuse warm session) | High (reconnect, keepalive) | High call frequency |
| Gateway proxy | Lowest (local hop only) | High (separate service) | Multi-app / enterprise |

---

## Decision for GeoRAG

GeoRAG invokes typically **one tool call per agent turn** (spatial model
execution). The per-session overhead is estimated at < 50 ms on a local
network and is negligible compared to model execution time.

The current session-per-request approach is appropriate. Migrating to
persistent sessions would require dropping down to
`langchain_mcp_adapters.sessions.create_session()` directly and managing
reconnect logic manually — complexity that is not justified by the access pattern.

Revisit if benchmarking shows MCP session overhead is a bottleneck, or if
the agent is extended to call many tools per turn at high concurrency.
