from langchain_core.callbacks import BaseCallbackHandler


class MCPToolLoggingHandler(BaseCallbackHandler):
    def __init__(self, logger):
        self.logger = logger

    def on_tool_start(self, serialized, input_str, **kwargs):
        name = serialized.get("name")
        self.logger.info(f"[MCP TOOL START] {name} input={input_str}")

    def on_tool_end(self, output, **kwargs):
        self.logger.info(f"[MCP TOOL END] output={output}")
