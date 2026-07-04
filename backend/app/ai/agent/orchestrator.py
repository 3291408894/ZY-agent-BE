"""
Agent 任务编排器 (PBI_04, PBI_12)

负责:
1. 解析用户意图
2. 拆解任务步骤
3. 调用 LLM + 工具链执行
4. 生成思考链（PBI_12）
"""

import json
from typing import AsyncIterator

from loguru import logger

from app.ai.agent.tools import tool_registry
from app.ai.llm_client import llm_client

SYSTEM_PROMPT = """你是智翼（ZhiYi）学习助手，专为 K12 学生提供学习辅导。

你的能力包括：
- 课文总结：对课文/文章进行结构化的精简或详细总结，提取知识点
- 习题生成：根据学科、知识点、难度生成各类练习题
- 习题批改：对学生的作答进行批改，给出评分和纠错建议
- 知识图谱：基于知识点构建知识图谱
- 文件解析：解析上传的学习资料

任务处理流程：
1. 分析用户请求，识别需要完成的任务
2. 将复杂任务拆解为步骤
3. 按步骤执行，需要时调用工具
4. 整合结果返回给用户

请用中文回复。"""


class AgentOrchestrator:
    """Agent 编排器 — 将用户自然语言指令转为多步骤任务执行"""

    @staticmethod
    def parse_intent(message: str) -> list[dict]:
        """
        分析用户消息，返回初步的任务步骤（think 阶段）
        返回格式: [{"step": 1, "title": "需求分析", "description": "..."}]
        """
        # 简单的关键词规则匹配（后续可改为 LLM 判断）
        steps = []
        if any(kw in message for kw in ["总结", "概括", "归纳"]):
            steps.append({"step": 1, "title": "课文总结", "description": "识别到课文总结需求"})
        if any(kw in message for kw in ["出题", "习题", "题目", "练习", "做题"]):
            step_num = len(steps) + 1
            steps.append({"step": step_num, "title": "习题生成", "description": "识别到习题生成需求"})
        if any(kw in message for kw in ["批改", "对答案", "批阅", "改错"]):
            step_num = len(steps) + 1
            steps.append({"step": step_num, "title": "批改反馈", "description": "识别到批改需求"})
        if any(kw in message for kw in ["知识图谱", "知识点", "思维导图"]):
            step_num = len(steps) + 1
            steps.append({"step": step_num, "title": "知识图谱", "description": "识别到知识图谱需求"})
        if not steps:
            steps.append({"step": 1, "title": "通用问答", "description": "通用学习咨询"})
        return steps

    async def run_stream(
        self,
        session_id: str,
        user_message: str,
        history: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """
        流式执行 Agent 任务，通过 SSE yield 事件:
        - {"type": "thought", "step": N, "title": "...", "content": "..."}
        - {"type": "content", "chunk": "..."}
        - {"type": "done", "session_id": "...", "usage": {...}}

        参数:
            session_id: 当前对话会话ID
            user_message: 用户输入
            history: 历史消息列表 [{"role":"user/assistant","content":"..."}]
        """
        # Step 1: 意图分析 → 思考链
        intent_steps = self.parse_intent(user_message)
        for step in intent_steps:
            yield {
                "type": "thought",
                "step": step["step"],
                "title": step["title"],
                "content": step["description"],
            }
            logger.info(
                f"[Agent] session={session_id} | step={step['step']} | {step['title']}"
            )

        # Step 2: 构建消息上下文
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Step 3: 流式调用 LLM
        try:
            available_tools = tool_registry.list_openai_functions()
            tool_names = tool_registry.get_tool_names()

            full_response = ""
            async for chunk in llm_client.chat_stream(messages):
                full_response += chunk
                yield {"type": "content", "chunk": chunk}

            # Step 4: 完成
            yield {
                "type": "done",
                "session_id": session_id,
                "usage": {"tokens": len(full_response)},
            }

        except Exception as e:
            logger.error(f"[Agent] 执行失败 | session={session_id} | error={e}")
            yield {
                "type": "error",
                "message": f"AI 服务暂时不可用，请稍后重试: {str(e)}",
            }


# 全局编排器单例
agent_orchestrator = AgentOrchestrator()
