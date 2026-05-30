from app.agent.tool_registry import ToolDefinition, build_default_tool_registry

TOOL_REGISTRY_BY_NAME: dict[str, ToolDefinition] = {
    tool.name: tool for tool in build_default_tool_registry()
}

def requires_confirmation(tool_name: str) -> bool:
    tool = TOOL_REGISTRY_BY_NAME.get(tool_name)
    if tool is None:
        raise ValueError(f"unknown tool: {tool_name}")
    return tool.confirmation_kind != ""
