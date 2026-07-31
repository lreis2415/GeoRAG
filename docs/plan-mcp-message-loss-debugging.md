# Plan: MCP message loss debugging

## TODO
- [DONE:1] Trace the chat route, service, MCP invocation, and persistence ordering.
- [DONE:2] Identify cancellation, timeout, serialization, and exception paths that can bypass logs or database writes.
- [DONE:3] Propose correlation IDs, durable audit events, payload-size limits, and a reproducible failure test.

## Acceptance Criteria
- The likely loss points are mapped to the current source code with concrete evidence.
- The debugging design makes every request observable, including failures and client disconnects.
- The approach preserves chat history even when a long MCP tool call fails.
