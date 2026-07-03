"""Agent 工具注册中心 + 课文总结工具 (PBI_04, PBI_06, PBI_12)"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Any

logger = logging.getLogger(__name__)


@dataclass
class AgentTool:
    """Agent 可用工具定义（对接文档 §4.2）"""
    name: str                             # 工具唯一标识，如 "text_summary"
    description: str                      # LLM 意图匹配描述
    parameters: dict                      # JSON Schema 参数定义
    handler: Callable[..., Any] | None = None  # 实际执行函数


class ToolRegistry:
    """全局工具注册中心 — 管理所有 Agent 可用工具"""

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        self._tools[tool.name] = tool
        logger.info(f"Agent 工具已注册: {tool.name} — {tool.description}")

    def get(self, name: str) -> AgentTool | None:
        return self._tools.get(name)

    def list_all(self) -> list[AgentTool]:
        return list(self._tools.values())

    def export_for_openai(self) -> list[dict]:
        """导出为 OpenAI function calling 格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]


# ── 全局单例 ──
tool_registry = ToolRegistry()


# ═══════════════════════════════════════════════════════════
# 课文总结工具注册 (PBI_06)
# ═══════════════════════════════════════════════════════════

# 工具元数据（会被 Agent 编排器读取并注册到 LLM）
SUMMARY_TOOL_META = {
    "name": "text_summary",
    "description": (
        "对用户提供的课文内容进行智能化结构总结和知识点提取。"
        "支持两种模式：brief（精简版：主旨+段落概要）和 detailed（详细版：主旨+段落精析+考点+写作手法+学习启示）。"
        "当用户说'总结课文'、'帮我总结《xxx》'、'分析这篇文章'时调用此工具。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "需要总结的课文原文内容",
            },
            "mode": {
                "type": "string",
                "enum": ["brief", "detailed"],
                "description": "总结模式：brief=精简版，detailed=详细版。默认为 detailed。",
            },
        },
        "required": ["content"],
    },
    "handler_path": "/api/v1/summaries/generate",  # SSE 端点
}


def register_summary_tool() -> None:
    """将课文总结工具注册到全局工具中心"""
    tool = AgentTool(
        name=SUMMARY_TOOL_META["name"],
        description=SUMMARY_TOOL_META["description"],
        parameters=SUMMARY_TOOL_META["parameters"],
        handler=None,  # SSE 端点由编排器直接调用
    )
    tool_registry.register(tool)


# 模块加载时自动注册
try:
    register_summary_tool()
except Exception as e:
    logger.warning(f"课文总结工具自动注册失败（可能在非完整环境中启动）: {e}")
