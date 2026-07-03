"""
Agent 工具注册框架 (PBI_04)

每个业务模块的工具需按 AgentTool 格式注册，Agent 编排器会根据用户意图
自动选择合适的工具调用。
"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentTool:
    """Agent 可调用工具的定义"""

    name: str  # 工具唯一标识，如 "text_summary"
    description: str  # 给 LLM 看的描述，用于意图匹配
    parameters: dict  # JSON Schema 格式的参数定义
    handler: Callable[..., Any]  # 工具实际执行函数

    def to_openai_function(self) -> dict:
        """转为 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """工具注册中心 — 管理所有 Agent 可用工具"""

    def __init__(self):
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        """注册一个工具"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> AgentTool | None:
        """按名称获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> list[AgentTool]:
        """列出所有已注册工具"""
        return list(self._tools.values())

    def list_openai_functions(self) -> list[dict]:
        """以 OpenAI function calling 格式列出所有工具"""
        return [t.to_openai_function() for t in self._tools.values()]

    def get_tool_names(self) -> list[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())


# 全局工具注册中心
tool_registry = ToolRegistry()
