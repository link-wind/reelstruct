from importlib import import_module

from app.agent.tool_registry import build_default_tool_registry


_TOOL_MAP = {
    tool.name: {
        "stage": tool.stage,
        "module": f"app.tools.{tool.name}",
    }
    for tool in build_default_tool_registry()
}


def execute_tool(tool_name: str, payload: dict) -> dict:
    tool_config = _TOOL_MAP.get(tool_name)
    if tool_config is None:
        raise ValueError(f"unknown tool: {tool_name}")

    handler = import_module(tool_config["module"]).handle
    return {
        "tool_name": tool_name,
        "stage": tool_config["stage"],
        "data": handler(payload),
    }
